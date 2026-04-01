from __future__ import annotations

import glob
import json
import os
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import Settings
from .db import Database, utc_now
from .onec_provider import StubFileWhitelistProvider

cfg = Settings.from_env()
db = Database(cfg.db_path)
db.init()
provider = StubFileWhitelistProvider(cfg.onec_stub_file)

app = FastAPI(title="ALPR Barrier API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_preview_meta() -> dict[str, object]:
    if not os.path.exists(cfg.preview_meta_path):
        return {}

    try:
        with open(cfg.preview_meta_path, "r", encoding="utf-8") as meta_file:
            loaded = json.load(meta_file)
        if isinstance(loaded, dict):
            return loaded
    except Exception:  # noqa: BLE001
        return {}

    return {}


def _find_latest_snapshot_for_frame(frame_id: str) -> str | None:
    pattern = os.path.join(cfg.recognition_snapshot_dir, f"*_{frame_id}_*.jpg")
    matches = glob.glob(pattern)
    if not matches:
        return None

    matches.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return matches[0]


@app.get("/health")
def health() -> dict[str, object]:
    db_ok = db.ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "backend",
        "db": "ok" if db_ok else "unreachable",
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, object]:
    now = utc_now()
    since = now - timedelta(hours=24)

    counts = db.get_decision_counts_since(since)
    whitelist = db.get_whitelist_counts()
    last_sync = db.get_last_sync_at()
    recent_events = db.get_recent_events(limit=20)

    avg_confidence = 0.0
    confidence_values = [
        float(item.get("vote_avg_confidence") or 0.0)
        for item in recent_events
        if item.get("decision") in {"open", "deny"}
    ]
    if confidence_values:
        avg_confidence = sum(confidence_values) / len(confidence_values)

    sync_age_seconds: int | None = None
    if last_sync is not None:
        sync_age_seconds = int((now - last_sync).total_seconds())

    return {
        "generated_at": now.isoformat(),
        "mode": {
            "dry_run_open": cfg.dry_run_open,
            "min_confirmations": cfg.min_confirmations,
            "min_avg_confidence": cfg.min_avg_confidence,
            "voting_window_sec": cfg.voting_window_sec,
        },
        "sync": {
            "last_sync_at": last_sync.isoformat() if last_sync else None,
            "sync_age_seconds": sync_age_seconds,
            "is_due": db.is_sync_due(cfg.onec_sync_interval_hours),
        },
        "whitelist": whitelist,
        "kpi_24h": {
            "open": counts.get("open", 0),
            "deny": counts.get("deny", 0),
            "observed": counts.get("observed", 0),
            "avg_confidence": avg_confidence,
        },
        "recent_events": recent_events,
    }


@app.post("/api/sync/force")
def force_sync() -> dict[str, object]:
    rows = provider.full_sync()
    synced = db.upsert_whitelist(rows, source="1c_stub")
    db.set_last_sync_now()
    last_sync = db.get_last_sync_at()

    return {
        "status": "ok",
        "synced_count": synced,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }


@app.get("/api/preview")
def preview_meta() -> dict[str, object]:
    meta = _read_preview_meta()
    available = os.path.exists(cfg.preview_image_path)
    captured_at = meta.get("captured_at")

    return {
        "available": available,
        "captured_at": captured_at if isinstance(captured_at, str) else None,
        "has_detections": bool(meta.get("has_detections", False)),
        "last_plate": meta.get("last_plate") if isinstance(meta.get("last_plate"), str) else None,
        "last_decision": meta.get("last_decision") if isinstance(meta.get("last_decision"), str) else None,
        "image_url": "/api/preview/image" if available else None,
        "version": captured_at if isinstance(captured_at, str) else None,
    }


@app.get("/api/preview/image")
def preview_image() -> FileResponse:
    if not os.path.exists(cfg.preview_image_path):
        raise HTTPException(status_code=404, detail="Preview image not available yet")

    return FileResponse(
        cfg.preview_image_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/events/{event_id}/image")
def event_image(event_id: int) -> FileResponse:
    frame_id = db.get_event_frame_id(event_id)
    if frame_id is None:
        raise HTTPException(status_code=404, detail="Event not found")

    image_path = _find_latest_snapshot_for_frame(frame_id)
    if image_path is None:
        raise HTTPException(status_code=404, detail="Snapshot not available for this event")

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
