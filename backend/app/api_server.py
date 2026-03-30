from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
