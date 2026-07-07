# camera_car_ocr

Monorepo with:
- `backend/` — ALPR + barrier decision backend
- `frontend/` — Next.js dashboard

## Implemented

- HTTP snapshot polling from camera URL.
- FastALPR detection + OCR pipeline.
- Plate normalization and optional fuzzy normalization.
- Temporal voting over a rolling time window.
- Strict whitelist-only decision policy.
- SQLite persistence via SQLAlchemy ORM.
- Daily 1C sync interface with local stub provider.
- Barrier controller with mock/live modes and Home Assistant API integration.
- Live Preview frame in dashboard (annotated snapshot for demo/debug).

## Run Backend Pipeline

```powershell
cd backend
uv sync
uv run python main.py
```

## Run Backend API (for frontend)

```powershell
cd backend
uv sync
uv run uvicorn app.api_server:app --host 0.0.0.0 --port 8000 --reload
```

When running via Docker Compose, backend container starts both the recognition pipeline (`main.py`) and API (`uvicorn`) together.

## Run Frontend Dashboard

```powershell
cd frontend
npm install
npm run dev
```

Frontend reads backend URL from `NEXT_PUBLIC_BACKEND_API_BASE` (default `http://localhost:8000`).

To see live preview on dashboard, the recognition pipeline must be running (`uv run python main.py`) because preview images are generated in the pipeline loop.

## 1C Stub Data

Edit `backend/onec_whitelist_stub.txt` and keep one plate per line.

## Important Environment Variables

- `CAMERA_SNAPSHOT_URL` (default camera snapshot endpoint)
- `CAMERA_USERNAME` (camera login username)
- `CAMERA_PASSWORD` (camera login password)
- `CAMERA_AUTH_MODE` (`digest`/`basic`/`none`, default `digest`)
- `DB_PATH` (default `data/app.db`)
- `ONEC_STUB_FILE` (default `onec_whitelist_stub.txt`)
- `ONEC_SYNC_INTERVAL_HOURS` (default `24`)
- `VOTING_WINDOW_SEC` (default `1.5`)
- `MIN_CONFIRMATIONS` (default `3`)
- `MIN_AVG_CONFIDENCE` (default `0.80`)
- `DRY_RUN_OPEN` (default `1`)
- `BARRIER_ACTION_MODE` (`mock`/`live`, default `mock`)
- `BARRIER_HA_BASE_URL` (e.g. `http://192.168.100.10:8123`)
- `BARRIER_HA_TOKEN` (Home Assistant Long-Lived Access Token)
- `ZONE1_BARRIER_OPEN_ENTITY_ID` (required for zone 1 in live mode)
- `ZONE1_BARRIER_CLOSE_ENTITY_ID` (required for zone 1 in live mode)
- `ZONE1_BARRIER_CLOSE_DELAY_SEC` (zone 1 close delay; `0` means use global delay)
- `ZONE2_BARRIER_OPEN_ENTITY_ID` (required for zone 2 in live mode)
- `ZONE2_BARRIER_CLOSE_ENTITY_ID` (required for zone 2 in live mode)
- `ZONE2_BARRIER_CLOSE_DELAY_SEC` (zone 2 close delay; `0` means use global delay)
- `BARRIER_REQUEST_TIMEOUT_SEC` (default `3.0`)
- `BARRIER_REQUEST_RETRIES` (default `2`)
- `BARRIER_VERIFY_TLS` (`1`/`0`, default `1`)
- `BARRIER_CLOSE_DELAY_SEC` (auto-close delay after successful open, default `5.0`)
- `ENABLE_FUZZY_MATCH` (default `0`)
- `PREVIEW_ENABLED` (default `1`)
- `PREVIEW_WRITE_INTERVAL_SEC` (default `3.0`)
- `PREVIEW_JPEG_QUALITY` (default `85`)
- `RECOGNITION_SNAPSHOT_ENABLED` (default `1`)
- `RECOGNITION_SNAPSHOT_DIR` (default `data/recognized`)
- `RECOGNITION_SNAPSHOT_JPEG_QUALITY` (default `90`)
- `RECOGNITION_SNAPSHOT_RETENTION_DAYS` (default `3`) — зберігати фото подій за останні N днів; старіші видаляються автоматично

Коли будь-який кадр з детекцією зберігається, бекенд зберігає анотований снапшот з накладанням номерного знаку/рішення у `RECOGNITION_SNAPSHOT_DIR`.
Стрічки таблиці дашборду можуть відкривати пов'язаний знімок події через ендпоінт `/api/events/{event_id}/image`.

## Real-time Event Stream (SSE)

The backend exposes a Server-Sent Events endpoint that pushes every new recognition
event to all connected clients in real time. This is the recommended integration
point for guard-room tray apps, secondary displays, or any system that needs to
react to decisions without polling.

### Endpoint

```
GET /api/events/stream
```

**Query parameters**

| Parameter   | Type | Default | Description |
|-------------|------|---------|-------------|
| `after_id`  | int  | `0`     | Only stream events with `id > after_id`. Pass the last received ID to resume after a restart without missing events. |
| `camera_id` | int  | —       | Filter to a single camera. Omit to receive events from all cameras. |

**Reconnect / resume**

The endpoint sets the SSE `id:` field on every message to the event's database ID.
When a browser `EventSource` reconnects it automatically sends `Last-Event-ID`
header, and the server resumes from that point — no manual bookkeeping needed.

Non-browser clients should persist the last received `id` and pass it as
`?after_id=<id>` on reconnect.

**Keepalive**

If no new events arrive for 15 seconds the server sends an SSE comment line
(`: keepalive`) to prevent proxies and firewalls from closing the idle connection.

### Message format

Each message is a JSON-encoded recognition event:

```jsonc
{
  "id": 4821,
  "occurred_at": "2025-06-18T14:32:01.123456+00:00",
  "plate": "AA1234BB",
  "raw_plate": "AA1234BB",
  "decision": "open",          // "open" | "deny" | "observed"
  "reason_code": "whitelist_match",
  "camera_id": 2,
  "zone_id": 5,
  "zone_name": "Entry",
  "ocr_confidence": 0.97,
  "vote_confirmations": 4,
  "vote_avg_confidence": 0.96,
  "detection_confidence": 0.91,
  "frame_id": "cam2_1718720921_4a3f"
}
```

### JavaScript / Tauri example

```javascript
let lastId = Number(localStorage.getItem("lastEventId") ?? "0")

const source = new EventSource(
  `http://192.168.100.112:8000/api/events/stream?after_id=${lastId}`
)

source.onmessage = (e) => {
  const event = JSON.parse(e.data)
  lastId = event.id
  localStorage.setItem("lastEventId", String(lastId))

  if (event.decision === "open") {
    // show green notification: plate allowed
  } else if (event.decision === "deny") {
    // show persistent red alert: plate denied
  }
}

source.onerror = () => {
  // EventSource reconnects automatically; last-event-id is sent by browser
}
```

### curl example

```bash
# Stream all events (Ctrl-C to stop)
curl -N "http://localhost:8000/api/events/stream"

# Resume from a specific event ID
curl -N "http://localhost:8000/api/events/stream?after_id=4820"

# Filter to camera 2
curl -N "http://localhost:8000/api/events/stream?camera_id=2"
```

---

## Home Assistant Barrier Mode

1. In Home Assistant, generate a Long-Lived Access Token.
2. Set `DRY_RUN_OPEN=0` and `BARRIER_ACTION_MODE=live`.
3. Configure `BARRIER_HA_BASE_URL`, `BARRIER_HA_TOKEN`, `ZONE1_BARRIER_*`, and `ZONE2_BARRIER_*`.
4. Backend sends `POST /api/services/input_button/press` for open/close and schedules close by configured delay.
5. While barrier is open, detections in that same zone refresh only that zone close deadline to `now + delay` (deadline is replaced, not accumulated).
6. If no active zones are configured, backend does not run ALPR or barrier actions.

If Home Assistant is unavailable or token is invalid, backend logs warning and keeps OCR loop running.

## Safety Defaults

- Opens only for whitelist plates.
- On uncertainty or errors, the system does not open the barrier.
- While barrier is open, same-zone detections keep it open by refreshing close deadline.

---

## Autostart via systemd (Linux / Proxmox)

Service files are stored in `systemd/` in the repo root. They are **templates** — copy them
to `/etc/systemd/system/` to install.

### Services

| Service | What it runs |
|---|---|
| `camera-car-api` | `uv run uvicorn app.api_server:app --host 0.0.0.0 --port 8000 --reload` |
| `camera-car-worker` | `uv run python main.py` (orchestrator + ALPR) |
| `camera-car-frontend` | `npm run dev` (Next.js dashboard) |

### Install (first time)

```bash
cp systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable camera-car-api camera-car-worker camera-car-frontend
systemctl start  camera-car-api camera-car-worker camera-car-frontend
```

### Restart after code changes

API server (`--reload` перезагружает Python-файлы автоматически, но если не помогло):
```bash
systemctl restart camera-car-api
```

Worker (основная логика, ALPR, оркестратор — всегда нужен рестарт):
```bash
systemctl restart camera-car-worker
```

Перезапустить всё сразу:
```bash
systemctl restart camera-car-api camera-car-worker camera-car-frontend
```

### Status & logs

```bash
# Статус всех трёх
systemctl status camera-car-api camera-car-worker camera-car-frontend

# Логи в реальном времени
journalctl -u camera-car-worker -f
journalctl -u camera-car-api -f
journalctl -u camera-car-frontend -f

# Последние 100 строк
journalctl -u camera-car-worker -n 100
```

### Stop / disable autostart

```bash
systemctl stop    camera-car-api camera-car-worker camera-car-frontend
systemctl disable camera-car-api camera-car-worker camera-car-frontend
```

### Autoboot after power loss

Убедись что в BIOS/UEFI выставлено **AC Power Recovery → Power On** (или
"Restore on AC Power Loss = On"). Тогда при включении света Proxmox поднимется
сам, а systemd запустит все три сервиса автоматически.

### Update service files

Если изменил файл в `systemd/` — скопируй его заново и перезагрузи конфиг:
```bash
cp systemd/camera-car-worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart camera-car-worker
```

# OpenVINO on Linux!!

1. Знайшов реальну помилку
  Запустив python -c "import onnxruntime" — отримав повне повідомлення:
  cannot enable executable stack as shared object requires: Invalid argument

2. Підтвердив причину
  Перевірив заголовки .so-файлу через readelf:
  GNU_STACK   RWE   ← виконуваний стек (Read + Write + Execute)
  Ядро Proxmox (hardened / LXC-контейнер) блокує завантаження бібліотек, які вимагають виконуваного стеку — це захист від певного класу експлойтів.

3. Встановив patchelf
  apt-get install -y patchelf

4. Прибрав прапор виконуваного стеку з .so-файлу
  patchelf --clear-execstack onnxruntime_pybind11_state.cpython-311-x86_64-linux-gnu.so
  Це змінює один біт в ELF-заголовку файлу — сам код бібліотеки не змінюється.

  ---
  Важливо: якщо ти оновиш або перевстановиш onnxruntime через uv, нова версія .so знову матиме цей прапор, і треба буде повторити команду patchelf.