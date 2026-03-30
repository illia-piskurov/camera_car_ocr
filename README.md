# camera_car_ocr

Monorepo with:
- `backend/` — ALPR + barrier decision backend
- `frontend/alrp-front/` — Next.js dashboard

## Implemented

- HTTP snapshot polling from camera URL.
- FastALPR detection + OCR pipeline.
- Plate normalization and optional fuzzy normalization.
- Temporal voting over a rolling time window.
- Strict whitelist-only decision policy.
- SQLite persistence via SQLAlchemy ORM.
- Daily 1C sync interface with local stub provider.
- Dry-run barrier controller (no hardware command yet).

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

## Run Frontend Dashboard

```powershell
cd frontend/alrp-front
npm install
npm run dev
```

Frontend reads backend URL from `NEXT_PUBLIC_BACKEND_API_BASE` (default `http://127.0.0.1:8000`).

## 1C Stub Data

Edit `backend/onec_whitelist_stub.txt` and keep one plate per line.

## Important Environment Variables

- `CAMERA_SNAPSHOT_URL` (default camera snapshot endpoint)
- `DB_PATH` (default `data/app.db`)
- `ONEC_STUB_FILE` (default `onec_whitelist_stub.txt`)
- `ONEC_SYNC_INTERVAL_HOURS` (default `24`)
- `VOTING_WINDOW_SEC` (default `1.5`)
- `MIN_CONFIRMATIONS` (default `3`)
- `MIN_AVG_CONFIDENCE` (default `0.80`)
- `DRY_RUN_OPEN` (default `1`)
- `ENABLE_FUZZY_MATCH` (default `0`)

## Safety Defaults

- Opens only for whitelist plates.
- On uncertainty or errors, the system does not open the barrier.
- Cooldowns prevent rapid repeated open commands.
