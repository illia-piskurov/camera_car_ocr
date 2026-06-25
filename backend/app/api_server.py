from __future__ import annotations

import asyncio
import glob
import json
import os
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .camera import SnapshotCameraClient
from .calibration import (
    BarrierModel,
    build_calibration_samples,
    bytes_to_crop,
    compute_accuracy,
    compute_optimal_threshold,
    crop_to_bytes,
    find_snapshot_for_frame,
    load_zone_crop,
    train_barrier_model,
)
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
    barrier_id: int | None = None
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)
    is_enabled: bool = True
    sort_order: int = 0
    cross_camera_enabled: bool = True
    cross_zone_id: int | None = None
    zone_type: str = "detection"


class BarrierInput(BaseModel):
    name: str = Field(default="", max_length=128)
    ha_open_entity_id: str = Field(default="", max_length=128)
    ha_close_entity_id: str = Field(default="", max_length=128)


class BarrierUpdateInput(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    ha_open_entity_id: str | None = Field(default=None, max_length=128)
    ha_close_entity_id: str | None = Field(default=None, max_length=128)
    state_check_enabled: bool | None = None
    state_threshold: float | None = Field(default=None, ge=0.001, le=1.0)


class CalibrationReferenceInput(BaseModel):
    event_id: int


class CalibrationLabelInput(BaseModel):
    event_id: int
    label: str | None = Field(default=None, pattern="^(open|closed)$")


class BarrierCheckZoneInput(BaseModel):
    camera_id: int | None = None
    name: str | None = None
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)
    rotation: float = Field(default=0.0, ge=0.0, lt=360.0)


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
    group_id: int | None = None


class CameraUpdateInput(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    snapshot_url: str | None = Field(default=None, max_length=512)
    username: str | None = None
    password: str | None = None
    auth_mode: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    sort_order: int | None = None
    group_id: int | None = Field(default=None)


class CameraGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    cross_suppress_sec: int = Field(default=120, ge=0)


class CameraGroupUpdateInput(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cross_suppress_sec: int | None = Field(default=None, ge=0)


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


@app.get("/api/barriers")
def list_barriers() -> dict[str, object]:
    return {"barriers": db.list_barriers()}


@app.post("/api/barriers")
def create_barrier(payload: BarrierInput) -> dict[str, object]:
    barrier = db.create_barrier(
        name=payload.name,
        ha_open_entity_id=payload.ha_open_entity_id,
        ha_close_entity_id=payload.ha_close_entity_id,
    )
    return {"status": "ok", "barrier": barrier}


@app.put("/api/barriers/{barrier_id}")
def update_barrier(barrier_id: int, payload: BarrierUpdateInput) -> dict[str, object]:
    barrier = db.update_barrier(
        barrier_id,
        name=payload.name,
        ha_open_entity_id=payload.ha_open_entity_id,
        ha_close_entity_id=payload.ha_close_entity_id,
        state_check_enabled=payload.state_check_enabled,
        state_threshold=payload.state_threshold,
    )
    if barrier is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    return {"status": "ok", "barrier": barrier}


@app.delete("/api/barriers/{barrier_id}")
def delete_barrier(barrier_id: int) -> dict[str, object]:
    ok = db.delete_barrier(barrier_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    return {"status": "ok"}


@app.get("/api/barriers/{barrier_id}/check-zone")
def get_barrier_check_zone(barrier_id: int) -> dict[str, object]:
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    zone = db.get_barrier_check_zone(barrier_id)
    return {"zone": zone}


@app.put("/api/barriers/{barrier_id}/check-zone")
def put_barrier_check_zone(barrier_id: int, payload: BarrierCheckZoneInput) -> dict[str, object]:
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    zone_data = sanitize_zone(
        {
            "camera_id": payload.camera_id,
            "name": payload.name or "Barrier check",
            "x_min": payload.x_min,
            "y_min": payload.y_min,
            "x_max": payload.x_max,
            "y_max": payload.y_max,
            "rotation": payload.rotation,
        },
        default_name="Barrier check",
    )
    saved = db.replace_barrier_check_zone(zone_data, barrier_id=barrier_id)
    return {"zone": saved}


@app.delete("/api/barriers/{barrier_id}/check-zone")
def delete_barrier_check_zone(barrier_id: int) -> dict[str, object]:
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    db.replace_barrier_check_zone(None, barrier_id=barrier_id)
    return {"status": "ok"}


@app.get("/api/barriers/{barrier_id}/calibration")
def get_barrier_calibration(barrier_id: int, limit: int = Query(default=100, le=500)) -> dict[str, object]:
    barrier = db.get_barrier(barrier_id)
    if barrier is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")

    check_zone = db.get_barrier_check_zone(barrier_id)
    if check_zone is None:
        return {
            "barrier_id": barrier_id,
            "reference_event_id": barrier.get("state_reference_event_id"),
            "has_reference": barrier.get("has_reference", False),
            "has_model": barrier.get("has_model", False),
            "threshold": barrier.get("state_threshold", 0.05),
            "samples": [],
            "error": "No check zone configured for this barrier",
        }

    camera_id = check_zone.get("camera_id")
    events = db.get_recent_events(limit=limit, camera_id=camera_id)
    existing_labels = db.get_calibration_labels(barrier_id)

    ref_bytes = db.get_barrier_reference_crop(barrier_id)
    reference_crop = bytes_to_crop(ref_bytes) if ref_bytes else None

    model_bytes = db.get_barrier_model(barrier_id)
    model: BarrierModel | None = BarrierModel.from_bytes(model_bytes) if model_bytes else None

    samples = build_calibration_samples(
        events=events,
        check_zone=check_zone,
        reference_crop=reference_crop,
        threshold=float(barrier.get("state_threshold") or 0.05),
        existing_labels=existing_labels,
        snapshot_dir=cfg.recognition_snapshot_dir,
        max_samples=limit,
        model=model,
    )

    return {
        "barrier_id": barrier_id,
        "reference_event_id": barrier.get("state_reference_event_id"),
        "has_reference": barrier.get("has_reference", False),
        "has_model": barrier.get("has_model", False),
        "threshold": barrier.get("state_threshold", 0.05),
        "samples": samples,
    }


@app.post("/api/barriers/{barrier_id}/calibration/reference")
def set_calibration_reference(barrier_id: int, payload: CalibrationReferenceInput) -> dict[str, object]:
    barrier = db.get_barrier(barrier_id)
    if barrier is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")

    check_zone = db.get_barrier_check_zone(barrier_id)
    if check_zone is None:
        raise HTTPException(status_code=400, detail="No check zone configured for this barrier")

    frame_id = db.get_event_frame_id(payload.event_id)
    if frame_id is None:
        raise HTTPException(status_code=404, detail=f"Event {payload.event_id} not found")

    image_path = find_snapshot_for_frame(frame_id, cfg.recognition_snapshot_dir)
    if image_path is None:
        raise HTTPException(status_code=404, detail="Snapshot image not found for this event")

    crop = load_zone_crop(image_path, check_zone)
    if crop is None:
        raise HTTPException(status_code=422, detail="Could not crop zone from event image")

    crop_bytes = crop_to_bytes(crop)
    if crop_bytes is None:
        raise HTTPException(status_code=500, detail="Failed to encode crop")

    barrier_row = db.set_barrier_calibration_reference(barrier_id, payload.event_id, crop_bytes)
    return {"status": "ok", "barrier": barrier_row}


@app.post("/api/barriers/{barrier_id}/calibration/label")
def set_calibration_label(barrier_id: int, payload: CalibrationLabelInput) -> dict[str, object]:
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    db.upsert_calibration_label(barrier_id, payload.event_id, payload.label)
    return {"status": "ok"}


@app.post("/api/barriers/{barrier_id}/calibration/apply")
def apply_barrier_calibration(barrier_id: int) -> dict[str, object]:
    barrier = db.get_barrier(barrier_id)
    if barrier is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")

    check_zone = db.get_barrier_check_zone(barrier_id)
    if check_zone is None:
        raise HTTPException(status_code=400, detail="No check zone configured")

    existing_labels = db.get_calibration_labels(barrier_id)
    if not existing_labels:
        raise HTTPException(status_code=400, detail="No labeled samples. Label some event photos first.")

    ref_bytes = db.get_barrier_reference_crop(barrier_id)
    reference_crop = bytes_to_crop(ref_bytes) if ref_bytes else None
    if reference_crop is None:
        raise HTTPException(status_code=400, detail="No reference image. Set a closed-state reference first.")

    # Load ALL labeled events (not just recent) for training
    camera_id = check_zone.get("camera_id")
    events = db.get_recent_events(limit=500, camera_id=camera_id)

    samples = build_calibration_samples(
        events=events,
        check_zone=check_zone,
        reference_crop=reference_crop,
        threshold=float(barrier.get("state_threshold") or 0.05),
        existing_labels=existing_labels,
        snapshot_dir=cfg.recognition_snapshot_dir,
        max_samples=2000,
    )

    n_open = sum(1 for s in samples if s.get("user_label") == "open")
    n_closed = sum(1 for s in samples if s.get("user_label") == "closed")

    if n_open == 0 or n_closed == 0:
        raise HTTPException(
            status_code=400,
            detail="Need at least 1 labeled 'open' and 1 labeled 'closed' photo with a snapshot to train.",
        )

    # --- Train logistic regression model ---
    # Collect (crop, label) pairs for samples that have snapshots
    labeled_crops: list[tuple] = []
    for s in samples:
        if s.get("user_label") and s.get("crop_b64"):
            import base64, numpy as _np
            crop_bytes = base64.b64decode(s["crop_b64"])
            arr = _np.frombuffer(crop_bytes, dtype=_np.uint8)
            import cv2 as _cv2
            crop = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
            if crop is not None:
                labeled_crops.append((crop, s["user_label"]))

    model_accuracy: float | None = None
    if len(labeled_crops) >= 2:
        result = train_barrier_model(labeled_crops)
        if result is not None:
            model, model_accuracy = result
            db.set_barrier_model(barrier_id, model.to_bytes())

    # --- Also compute diff-based threshold (fallback) ---
    threshold = compute_optimal_threshold(samples)
    if threshold is not None:
        db.apply_calibration_threshold(barrier_id, threshold)
    else:
        threshold = float(barrier.get("state_threshold") or 0.05)

    diff_accuracy = compute_accuracy(samples, threshold)

    return {
        "status": "ok",
        "threshold": threshold,
        "diff_accuracy": diff_accuracy,
        "model_accuracy": model_accuracy,
        "n_open": n_open,
        "n_closed": n_closed,
        "n_total_labeled": len(labeled_crops),
    }


@app.delete("/api/barriers/{barrier_id}/calibration")
def clear_barrier_calibration(barrier_id: int) -> dict[str, object]:
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")
    db.clear_calibration_labels(barrier_id)
    return {"status": "ok"}


@app.post("/api/barriers/{barrier_id}/calibration/capture")
def capture_calibration_frames(
    barrier_id: int, count: int = Query(default=1, ge=1, le=10)
) -> dict[str, object]:
    """Grab live frames from the barrier's camera and save them as training snapshots."""
    if db.get_barrier(barrier_id) is None:
        raise HTTPException(status_code=404, detail=f"Barrier {barrier_id} not found")

    check_zone = db.get_barrier_check_zone(barrier_id)
    if check_zone is None:
        raise HTTPException(status_code=400, detail="No check zone configured for this barrier")

    camera_id = check_zone.get("camera_id")
    if camera_id is None:
        raise HTTPException(status_code=400, detail="Barrier check zone has no camera assigned")

    camera = db.get_camera(int(camera_id))
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    creds = db.get_camera_credentials(int(camera_id), cfg.get_camera_credentials_encryption_key())
    if creds is None:
        raise HTTPException(status_code=500, detail="Could not load camera credentials")

    username, password, auth_mode = creds
    client = SnapshotCameraClient(
        url=str(camera["snapshot_url"]),
        timeout_sec=10.0,
        retries=1,
        username=username,
        password=password,
        auth_mode=auth_mode,
    )

    os.makedirs(cfg.recognition_snapshot_dir, exist_ok=True)
    captured = []
    try:
        for _ in range(count):
            frame = client.fetch_frame()
            if frame is None:
                raise HTTPException(status_code=502, detail="Failed to fetch frame from camera")

            import cv2 as _cv2
            import uuid as _uuid

            now = utc_now()
            frame_id = _uuid.uuid4().hex[:12]
            timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{timestamp}_{frame_id}___observed.jpg"
            out_path = os.path.join(cfg.recognition_snapshot_dir, filename)

            ok, encoded = _cv2.imencode(".jpg", frame, [int(_cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                raise HTTPException(status_code=500, detail="Failed to encode frame")
            with open(out_path, "wb") as f:
                f.write(encoded.tobytes())

            event_info = db.record_manual_capture(
                camera_id=int(camera_id),
                frame_id=frame_id,
                occurred_at=now,
            )
            captured.append(event_info)
    finally:
        client.close()

    return {"status": "ok", "captured": captured}


@app.get("/api/camera-groups")
def list_camera_groups() -> dict[str, object]:
    return {"groups": db.list_camera_groups()}


@app.post("/api/camera-groups")
def create_camera_group(payload: CameraGroupInput) -> dict[str, object]:
    group = db.create_camera_group(name=payload.name, cross_suppress_sec=payload.cross_suppress_sec)
    return {"status": "ok", "group": group}


@app.put("/api/camera-groups/{group_id}")
def update_camera_group(group_id: int, payload: CameraGroupUpdateInput) -> dict[str, object]:
    group = db.update_camera_group(group_id, name=payload.name, cross_suppress_sec=payload.cross_suppress_sec)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Camera group {group_id} not found")
    return {"status": "ok", "group": group}


@app.delete("/api/camera-groups/{group_id}")
def delete_camera_group(group_id: int) -> dict[str, object]:
    deleted = db.delete_camera_group(group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Camera group {group_id} not found")
    return {"status": "ok"}


@app.get("/api/cameras/{camera_id}/peer-zones")
def get_camera_peer_zones(camera_id: int) -> dict[str, object]:
    """Return zones from all peer cameras in the same group (for cross-zone config)."""
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return {"peer_zones": db.get_group_peer_zones(camera_id)}


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
        group_id=payload.group_id,
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

    group_id_update = payload.group_id if "group_id" in payload.model_fields_set else ...
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
        group_id=group_id_update,
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


class ManualPlateInput(BaseModel):
    plate: str
    note: str = ""


class PlateUpdateInput(BaseModel):
    note: str | None = None
    is_active: bool | None = None


@app.get("/api/status")
def system_status() -> dict[str, object]:
    import time as _time
    status = db.get_system_status()

    # Augment camera entries with worker-alive (check preview meta file mtime)
    for cam in status["cameras"]:  # type: ignore[union-attr]
        cid: int = cam["id"]  # type: ignore[index]
        meta_path = cfg.get_preview_meta_path(cid)
        try:
            mtime = os.path.getmtime(meta_path)
            age = _time.time() - mtime
            cam["worker_alive"] = age < 30.0  # type: ignore[index]
            cam["preview_age_sec"] = round(age, 1)  # type: ignore[index]
        except OSError:
            cam["worker_alive"] = False  # type: ignore[index]
            cam["preview_age_sec"] = None  # type: ignore[index]

    return status


@app.get("/api/whitelist")
def list_whitelist(
    search: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    return db.list_whitelist(search=search, offset=offset, limit=limit)


@app.post("/api/whitelist")
def add_whitelist_plate(payload: ManualPlateInput) -> dict[str, object]:
    from .normalization import normalize_plate

    raw = payload.plate.strip()
    if not raw:
        raise HTTPException(status_code=422, detail="plate is empty")
    norm = normalize_plate(raw)
    if not norm.normalized:
        raise HTTPException(status_code=422, detail=f"Could not normalize plate: {raw!r}")
    entry = db.add_plate_manual(plate=norm.normalized, fuzzy=norm.fuzzy, note=payload.note)
    return {"entry": entry}


@app.put("/api/whitelist/{plate_id}")
def update_whitelist_plate(plate_id: int, payload: PlateUpdateInput) -> dict[str, object]:
    entry = db.update_plate(plate_id, note=payload.note, is_active=payload.is_active)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plate not found")
    return {"entry": entry}


@app.delete("/api/whitelist/{plate_id}")
def delete_whitelist_plate(plate_id: int) -> dict[str, object]:
    ok = db.delete_plate(plate_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Plate not found or not manually added")
    return {"status": "ok"}


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
            "barrier_live_configured": cfg.is_ha_configured() and any(
                b.get("ha_open_entity_id") for b in db.list_barriers()
            ),
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


@app.get("/api/events")
def list_events(
    camera_id: int | None = Query(None),
    search: str | None = Query(None),
    decision: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, object]:
    events = db.get_events(limit=limit, offset=offset, camera_id=camera_id, search=search, decision=decision)
    total = db.count_events(camera_id=camera_id, search=search, decision=decision)
    return {
        "events": events,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@app.get("/api/events/latest-id")
def latest_event_id() -> dict[str, object]:
    return {"id": db.get_max_event_id()}


@app.get("/api/events/stream")
async def stream_events(
    request: Request,
    after_id: int = Query(0, ge=0),
    camera_id: int | None = Query(None),
) -> StreamingResponse:
    """SSE stream of recognition events.

    Yields one SSE message per new event as soon as it is written to the DB.
    The client should reconnect on disconnect; the browser EventSource does this
    automatically using the SSE ``id:`` field sent with every message.
    """
    # Honor Last-Event-ID header sent by browser on automatic reconnect
    raw_last_id = request.headers.get("last-event-id")
    if raw_last_id and raw_last_id.isdigit():
        after_id = int(raw_last_id)

    async def generator() -> object:
        current_id = after_id
        last_keepalive = asyncio.get_event_loop().time()
        while True:
            if await request.is_disconnected():
                break

            new_events = db.get_events_after(current_id, camera_id=camera_id)
            for evt in new_events:
                current_id = int(str(evt["id"]))
                data = json.dumps(evt, ensure_ascii=False)
                yield f"id: {current_id}\ndata: {data}\n\n"
                last_keepalive = asyncio.get_event_loop().time()

            now = asyncio.get_event_loop().time()
            if now - last_keepalive >= 15:
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(1)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
        "barriers": db.list_barriers(),
        "barrier_zones": db.get_barrier_check_zones_for_camera(camera_id),
        "barrier_motion_zones": db.get_barrier_motion_zones_for_camera(camera_id),
        "max_zones": cfg.detection_zones_max,
        "image_url": f"/api/cameras/{camera_id}/preview/image" if available else None,
        "version": captured_at if isinstance(captured_at, str) else None,
    }


@app.get("/api/cameras/{camera_id}/preview/image")
def camera_preview_image(camera_id: int) -> StreamingResponse:
    """Get preview image for a specific camera."""
    # Verify camera exists
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    image_path = cfg.get_preview_image_path(camera_id)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Preview image not available yet")

    try:
        # Read entire file into memory to avoid race conditions when file is being written
        with open(image_path, "rb") as f:
            image_data = f.read()
    except OSError as exc:
        raise HTTPException(status_code=404, detail=f"Failed to read preview image: {exc}")

    # Return as streaming response with explicit content-length to avoid h11 protocol errors
    return StreamingResponse(
        iter([image_data]),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Content-Length": str(len(image_data)),
        },
    )


# ----------------------------------------------------------------- barrier motion zones

class MotionZoneInput(BaseModel):
    barrier_id: int | None = None
    camera_id: int | None = None
    name: str | None = None
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@app.get("/api/cameras/{camera_id}/motion-zones")
def list_motion_zones(camera_id: int) -> dict[str, object]:
    if db.get_camera(camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    zones = db.get_barrier_motion_zones_for_camera(camera_id)
    return {"motion_zones": zones}


@app.post("/api/cameras/{camera_id}/motion-zones")
def create_motion_zone(camera_id: int, payload: MotionZoneInput) -> dict[str, object]:
    if db.get_camera(camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    zone = db.save_barrier_motion_zone({
        "barrier_id": payload.barrier_id,
        "camera_id": camera_id,
        "name": payload.name or "Motion Zone",
        "x_min": payload.x_min,
        "y_min": payload.y_min,
        "x_max": payload.x_max,
        "y_max": payload.y_max,
    })
    return {"zone": zone}


@app.put("/api/motion-zones/{zone_id}")
def update_motion_zone(zone_id: int, payload: MotionZoneInput) -> dict[str, object]:
    zone = db.save_barrier_motion_zone({
        "id": zone_id,
        "barrier_id": payload.barrier_id,
        "camera_id": payload.camera_id,
        "name": payload.name or "Motion Zone",
        "x_min": payload.x_min,
        "y_min": payload.y_min,
        "x_max": payload.x_max,
        "y_max": payload.y_max,
    })
    return {"zone": zone}


@app.delete("/api/motion-zones/{zone_id}")
def delete_motion_zone(zone_id: int) -> dict[str, object]:
    ok = db.delete_barrier_motion_zone(zone_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Motion zone {zone_id} not found")
    return {"status": "deleted"}
