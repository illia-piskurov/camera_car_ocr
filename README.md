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
- `BARRIER_OPEN_ENTITY_ID` (e.g. `input_button.testovyi_shlagbaum_otkryt`)
- `BARRIER_CLOSE_ENTITY_ID` (e.g. `input_button.testovyi_shlagbaum_zakryt`)
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
- `RECOGNITION_SNAPSHOT_MAX_FILES` (default `500`)

When any detection frame is produced, backend saves an annotated snapshot with plate/decision overlay into `RECOGNITION_SNAPSHOT_DIR`.
Dashboard table rows can open related event snapshot via backend endpoint `/api/events/{event_id}/image`.

## Home Assistant Barrier Mode

1. In Home Assistant, generate a Long-Lived Access Token.
2. Set `DRY_RUN_OPEN=0` and `BARRIER_ACTION_MODE=live`.
3. Configure `BARRIER_HA_BASE_URL`, `BARRIER_HA_TOKEN`, `BARRIER_OPEN_ENTITY_ID`, and `BARRIER_CLOSE_ENTITY_ID`.
4. Backend sends `POST /api/services/input_button/press` for open/close and schedules close by `BARRIER_CLOSE_DELAY_SEC`.

If Home Assistant is unavailable or token is invalid, backend logs warning and keeps OCR loop running.

## Safety Defaults

- Opens only for whitelist plates.
- On uncertainty or errors, the system does not open the barrier.
- Cooldowns prevent rapid repeated open commands.
