from __future__ import annotations

import glob
import json
import os
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .camera import SnapshotCameraClient
from .config import Settings
from .db import Database, utc_now
from .logging_utils import configure_logging
from .onec_provider import create_whitelist_provider
from .zones import sanitize_zone

cfg = Settings.from_env()
configure_logging(cfg.log_file_path)
db = Database(cfg.db_path)
db.init()
provider = create_whitelist_provider(cfg)

app = FastAPI(title="ALPR Barrier API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ZoneInput(BaseModel):
    id: int | None = None
    name: str | None = None
    ha_open_entity_id: str = Field(default="")
    ha_close_entity_id: str = Field(default="")
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)
    is_enabled: bool = True
    sort_order: int = 0


class ZonesPayload(BaseModel):
    zones: list[ZoneInput] = Field(default_factory=list)


class CameraInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    snapshot_url: str = Field(min_length=1, max_length=512)
    username: str = Field(default="")
    password: str = Field(default="")
    auth_mode: str = Field(default="digest")
    is_active: bool = True
    sort_order: int | None = None


class CameraUpdateInput(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    snapshot_url: str | None = Field(default=None, max_length=512)
    username: str | None = None
    password: str | None = None
    auth_mode: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    sort_order: int | None = None


def _read_preview_meta(meta_path: str) -> dict[str, object]:
    if not os.path.exists(meta_path):
        return {}

    try:
        with open(meta_path, "r", encoding="utf-8") as meta_file:
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


@app.get("/api/cameras")
def list_cameras() -> dict[str, object]:
    return {"cameras": db.list_cameras()}


@app.post("/api/cameras/validate")
def validate_camera(payload: CameraInput) -> dict[str, object]:
    client = SnapshotCameraClient(
        url=payload.snapshot_url,
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
        username=payload.username,
        password=payload.password,
        auth_mode=payload.auth_mode,
    )
    frame, error = client.probe_frame()
    if frame is None:
        raise HTTPException(status_code=400, detail=f"Camera validation failed: {error or 'unreachable'}")
    return {"status": "ok", "available": True}


@app.post("/api/cameras")
def create_camera(payload: CameraInput) -> dict[str, object]:
    validation = validate_camera(payload)
    if validation.get("status") != "ok":
        raise HTTPException(status_code=400, detail="Camera validation failed")

    camera = db.create_camera(
        name=payload.name,
        snapshot_url=payload.snapshot_url,
        username=payload.username,
        password=payload.password,
        auth_mode=payload.auth_mode,
        encryption_key=cfg.get_camera_credentials_encryption_key(),
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    return {"status": "ok", "camera": camera}


@app.put("/api/cameras/{camera_id}")
def update_camera(camera_id: int, payload: CameraUpdateInput) -> dict[str, object]:
    existing_camera = db.get_camera(camera_id)
    if existing_camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    current_credentials = db.get_camera_credentials(camera_id, cfg.get_camera_credentials_encryption_key())
    current_username, current_password, current_auth_mode = current_credentials if current_credentials is not None else ("", "", "digest")

    merged_name = payload.name.strip() if payload.name is not None and payload.name.strip() else str(existing_camera.get("name") or "")
    merged_snapshot_url = (
        payload.snapshot_url.strip() if payload.snapshot_url is not None and payload.snapshot_url.strip() else str(existing_camera.get("snapshot_url") or "")
    )
    merged_username = payload.username.strip() if payload.username is not None and payload.username.strip() else current_username
    merged_password = payload.password.strip() if payload.password is not None and payload.password.strip() else current_password
    merged_auth_mode = payload.auth_mode.strip() if payload.auth_mode is not None and payload.auth_mode.strip() else str(existing_camera.get("auth_mode") or current_auth_mode or "digest")
    merged_is_active = payload.is_active if payload.is_active is not None else bool(existing_camera.get("is_active", True))
    merged_sort_order = payload.sort_order if payload.sort_order is not None else int(existing_camera.get("sort_order") or 0)

    requires_validation = any(
        (
            payload.snapshot_url is not None
            and payload.snapshot_url.strip()
            and payload.snapshot_url.strip() != str(existing_camera.get("snapshot_url") or ""),
            payload.username is not None
            and payload.username.strip()
            and payload.username.strip() != current_username,
            payload.password is not None
            and payload.password.strip()
            and payload.password.strip() != current_password,
        )
    )
    if requires_validation:
        validation = validate_camera(
            CameraInput(
                name=merged_name,
                snapshot_url=merged_snapshot_url,
                username=merged_username,
                password=merged_password,
                auth_mode=merged_auth_mode,
                is_active=merged_is_active,
                sort_order=merged_sort_order,
            )
        )
        if validation.get("status") != "ok":
            raise HTTPException(status_code=400, detail="Camera validation failed")

    camera = db.update_camera(
        camera_id,
        name=payload.name,
        snapshot_url=payload.snapshot_url,
        username=payload.username,
        password=payload.password,
        auth_mode=payload.auth_mode,
        encryption_key=cfg.get_camera_credentials_encryption_key(),
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return {"status": "ok", "camera": camera}


@app.delete("/api/cameras/{camera_id}")
def delete_camera(camera_id: int) -> dict[str, object]:
    existing_camera = db.get_camera(camera_id)
    if existing_camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    deleted = db.delete_camera(camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return {"status": "ok"}


@app.get("/api/zones")
def get_zones() -> dict[str, object]:
    return {
        "max_zones": cfg.detection_zones_max,
        "zones": db.get_zones(include_disabled=True),
    }


@app.put("/api/zones")
def put_zones(payload: ZonesPayload) -> dict[str, object]:
    if len(payload.zones) > cfg.detection_zones_max:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {cfg.detection_zones_max} zones are allowed",
        )

    sanitized = [
        sanitize_zone(zone.model_dump(), default_name=f"Zone {index + 1}")
        for index, zone in enumerate(payload.zones)
    ]
    saved = db.replace_zones(sanitized, max_zones=cfg.detection_zones_max)
    return {
        "status": "ok",
        "max_zones": cfg.detection_zones_max,
        "zones": saved,
    }


@app.post("/api/sync/force")
def force_sync() -> dict[str, object]:
    try:
        rows = provider.full_sync()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from exc

    if provider.source == "1c_http" and not rows and not cfg.onec_http_allow_empty_sync:
        raise HTTPException(
            status_code=502,
            detail="1C HTTP sync returned empty list; update blocked by ONEC_HTTP_ALLOW_EMPTY_SYNC=0",
        )

    synced = db.upsert_whitelist(rows, source=provider.source)
    db.set_last_sync_now()
    last_sync = db.get_last_sync_at()

    return {
        "status": "ok",
        "synced_count": synced,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }


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


# Camera-scoped endpoints
@app.get("/api/cameras/{camera_id}/dashboard")
def camera_dashboard(camera_id: int) -> dict[str, object]:
    """Get dashboard data for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    now = utc_now()
    since = now - timedelta(hours=24)

    counts = db.get_decision_counts_since(since, camera_id=camera_id)
    whitelist = db.get_whitelist_counts()
    last_sync = db.get_last_sync_at()
    recent_events = db.get_recent_events(limit=20, camera_id=camera_id)

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
        "camera": {
            "id": camera_id,
            "name": camera.get("name"),
        },
        "mode": {
            "dry_run_open": cfg.dry_run_open,
            "barrier_action_mode": cfg.barrier_action_mode,
            "barrier_close_delay_sec": cfg.barrier_close_delay_sec,
            "barrier_live_configured": cfg.is_barrier_live_configured(),
            "zone1_barrier_configured": cfg.has_zone_barrier_entities(1),
            "zone2_barrier_configured": cfg.has_zone_barrier_entities(2),
            "zone1_close_delay_sec": cfg.get_zone_close_delay_sec(1),
            "zone2_close_delay_sec": cfg.get_zone_close_delay_sec(2),
            "ocr_open_threshold": cfg.ocr_open_threshold,
            "ocr_extend_threshold": cfg.ocr_extend_threshold,
            "decision_model_version": "single-shot-v1",
            "legacy_config_deprecated": False,
        },
        "sync": {
            "source": provider.source,
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


@app.get("/api/cameras/{camera_id}/zones")
def get_camera_zones(camera_id: int) -> dict[str, object]:
    """Get zones for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return {
        "max_zones": cfg.detection_zones_max,
        "zones": db.get_zones(include_disabled=True, camera_id=camera_id),
    }


@app.put("/api/cameras/{camera_id}/zones")
def put_camera_zones(camera_id: int, payload: ZonesPayload) -> dict[str, object]:
    """Update zones for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    if len(payload.zones) > cfg.detection_zones_max:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {cfg.detection_zones_max} zones are allowed",
        )

    sanitized = [
        sanitize_zone(zone.model_dump(), default_name=f"Zone {index + 1}")
        for index, zone in enumerate(payload.zones)
    ]
    saved = db.replace_zones(sanitized, camera_id=camera_id, max_zones=cfg.detection_zones_max)
    return {
        "status": "ok",
        "max_zones": cfg.detection_zones_max,
        "zones": saved,
    }


@app.get("/api/cameras/{camera_id}/preview")
def camera_preview_meta(camera_id: int) -> dict[str, object]:
    """Get preview metadata for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    meta = _read_preview_meta(cfg.get_preview_meta_path(camera_id))
    available = os.path.exists(cfg.get_preview_image_path(camera_id))
    captured_at = meta.get("captured_at")

    return {
        "available": available,
        "captured_at": captured_at if isinstance(captured_at, str) else None,
        "has_detections": bool(meta.get("has_detections", False)),
        "last_plate": meta.get("last_plate") if isinstance(meta.get("last_plate"), str) else None,
        "last_decision": meta.get("last_decision") if isinstance(meta.get("last_decision"), str) else None,
        "zones": db.get_zones(include_disabled=True, camera_id=camera_id),
        "max_zones": cfg.detection_zones_max,
        "image_url": f"/api/cameras/{camera_id}/preview/image" if available else None,
        "version": captured_at if isinstance(captured_at, str) else None,
    }


@app.get("/api/cameras/{camera_id}/preview/image")
def camera_preview_image(camera_id: int) -> FileResponse:
    """Get preview image for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    image_path = cfg.get_preview_image_path(camera_id)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Preview image not available yet")

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
