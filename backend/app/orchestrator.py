from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import sys
from uuid import uuid4

import cv2
import numpy as np

from .alpr_service import AlprService
from .barrier import BarrierController
from .camera import SnapshotCameraClient
from .config import Settings
from .db import Database
from .logging_utils import configure_logging
from .motion_detector import has_motion_in_zone
from .onec_provider import WhitelistProvider, create_whitelist_provider
from .pipeline_state import PipelineState
from .preview_pipeline import write_preview_artifacts, write_recognition_snapshot
from .runtime_state import ZoneRuntimeState
from .types import PlateDetection
from .zones import crop_zone, draw_zones, paste_zone_image
from . import stages

LOG = logging.getLogger(__name__)

_WORKER_SCRIPT = ["-m", "app.camera_worker"]


def _as_zone_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


@dataclass
class FrameStageContext:
    now: datetime
    frame_id: str
    active_zones: list[dict[str, object]]
    active_zones_by_id: dict[int, dict[str, object]]
    skip_alpr_this_frame: bool


@dataclass
class DetectionStageResult:
    frame_last_decision: str | None
    frame_last_plate: str | None
    frame_last_reason: str | None
    frame_last_zone: str | None
    snapshot_source_detection: PlateDetection | None


def _sync_whitelist(db: Database, provider: WhitelistProvider, cfg: Settings) -> None:
    rows = provider.full_sync()

    if provider.source == "1c_http" and not rows and not cfg.onec_http_allow_empty_sync:
        LOG.warning("1C HTTP sync returned empty list; skipping DB update due to ONEC_HTTP_ALLOW_EMPTY_SYNC=0")
        return

    count = db.upsert_whitelist(rows, source=provider.source)
    db.set_last_sync_now()
    LOG.info("Whitelist synced from %s: %s plates", provider.source, count)


def _process_frame(
    *,
    frame,
    prev_frame,
    camera_id: int | None = None,
    db: Database,
    cfg: Settings,
    state: PipelineState,
) -> FrameStageContext | None:
    now = datetime.now(timezone.utc)
    frame_id = uuid4().hex
    if camera_id is None:
        active_zones = db.get_zones(include_disabled=False)[: max(0, cfg.detection_zones_max)]
    else:
        active_zones = db.get_zones(include_disabled=False, camera_id=camera_id)[: max(0, cfg.detection_zones_max)]

    if not active_zones:
        now_monotonic = time.monotonic()
        if now_monotonic - state.last_no_zone_warning_ts >= 30.0:
            LOG.warning(
                "No active zones configured. ALPR and barrier actions are paused until zones are defined"
            )
            state.last_no_zone_warning_ts = now_monotonic
        # Keep preview alive even without zones so the operator can validate camera feed.
        return FrameStageContext(
            now=now,
            frame_id=frame_id,
            active_zones=[],
            active_zones_by_id={},
            skip_alpr_this_frame=True,
        )

    skip_alpr_this_frame = False
    # Motion detection disabled - analyze every frame without motion filtering
    # if cfg.motion_detection_enabled and prev_frame is not None:
    #     zones_with_motion = []
    #     for zone in active_zones:
    #         if has_motion_in_zone(
    #             prev_frame,
    #             frame,
    #             zone,
    #             threshold=cfg.motion_threshold_percent,
    #             blur_kernel=cfg.motion_blur_kernel,
    #         ):
    #             zones_with_motion.append(zone)
    #
    #     if not zones_with_motion:
    #         LOG.debug("No motion in any zone, skipping ALPR")
    #         skip_alpr_this_frame = True
    #
    #     if zones_with_motion:
    #         active_zones = zones_with_motion

    active_zones_by_id = {}
    for zone in active_zones:
        zone_id = _as_zone_id(zone.get("id"))
        if zone_id is not None:
            active_zones_by_id[zone_id] = zone
    return FrameStageContext(
        now=now,
        frame_id=frame_id,
        active_zones=active_zones,
        active_zones_by_id=active_zones_by_id,
        skip_alpr_this_frame=skip_alpr_this_frame,
    )


def _detect_in_zones(
    *,
    frame,
    alpr: AlprService,
    detected_at: datetime,
    frame_id: str,
    active_zones: list[dict[str, object]],
) -> tuple[list[PlateDetection], dict[int, np.ndarray]]:
    detections: list[PlateDetection] = []
    zone_frames: dict[int, np.ndarray] = {}

    if not active_zones:
        return detections, zone_frames

    for zone in active_zones:
        try:
            zone_frame = crop_zone(frame, zone)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Failed to crop zone %s: %s", zone.get("name"), exc)
            continue

        zone_id = _as_zone_id(zone.get("id"))
        if zone_id is not None:
            zone_frames[zone_id] = zone_frame

        zone_label = str(
            zone.get("ha_open_entity_id")
            or zone.get("ha_close_entity_id")
            or zone.get("name")
            or ""
        )

        detections.extend(
            alpr.detect(
                zone_frame,
                detected_at=detected_at,
                frame_id=frame_id,
                zone_id=zone_id,
                zone_name=zone_label,
            )
        )

    return detections, zone_frames


def _select_best_detection(
    *,
    detections: list[PlateDetection],
    min_ocr_confidence: float,
) -> PlateDetection | None:
    """Select the best detection from a single frame based on OCR confidence.

    Prefers high-confidence detections and returns the one with the highest
    confidence that meets the minimum threshold. Returns None if no detections
    meet the threshold.
    """
    if not detections:
        return None

    # Filter detections that meet the OCR confidence threshold
    qualified = [d for d in detections if d.ocr_confidence >= min_ocr_confidence]
    if not qualified:
        return None

    # Return the detection with the highest OCR confidence
    return max(qualified, key=lambda d: d.ocr_confidence)


def _handle_detections(
    *,
    detections: list[PlateDetection],
    decision_detection: PlateDetection | None,
    db: Database,
    cfg: Settings,
    barrier: BarrierController,
    zone_states: dict[int | None, ZoneRuntimeState],
    camera_id: int | None = None,
) -> DetectionStageResult:
    result = DetectionStageResult(
        frame_last_decision=None,
        frame_last_plate=None,
        frame_last_reason=None,
        frame_last_zone=None,
        snapshot_source_detection=detections[0] if detections else None,
    )

    for detection in detections:
        # Record raw detection event
        stages.record_decision_event(
            detection=detection,
            decision="observed",
            reason_code="raw_detection",
            db=db,
            camera_id=camera_id,
        )

    if decision_detection is None:
        return result

    should_open, reason_code = stages.evaluate_decision(
        plate=decision_detection.normalized_text,
        fuzzy_plate=decision_detection.fuzzy_text,
        db=db,
        cfg=cfg,
    )

    result.frame_last_decision = "open" if should_open else "deny"
    result.frame_last_plate = decision_detection.normalized_text
    result.frame_last_reason = reason_code
    result.frame_last_zone = decision_detection.zone_name
    result.snapshot_source_detection = decision_detection

    stages.record_decision_event(
        detection=decision_detection,
        decision=result.frame_last_decision,
        reason_code=reason_code,
        db=db,
        camera_id=camera_id,
    )

    LOG.info(
        "Decision plate=%s ocr_conf=%.3f decision=%s reason=%s",
        decision_detection.normalized_text,
        decision_detection.ocr_confidence,
        result.frame_last_decision,
        reason_code,
    )

    stages.execute_barrier_action(
        should_open=should_open,
        detection=decision_detection,
        reason_code=reason_code,
        barrier=barrier,
        cfg=cfg,
        zone_states=zone_states,
    )

    return result


def _refresh_zone_hold(
    *,
    detections: list[PlateDetection],
    cfg: Settings,
    state: PipelineState,
    now_monotonic: float,
) -> None:
    for detection in detections:
        zone_id = detection.zone_id
        zone_state = state.zone_states.get(zone_id)
        if zone_state is None or not zone_state.is_open:
            continue

        close_delay = max(0.1, cfg.get_zone_close_delay_sec(zone_id))
        hold_plate = detection.normalized_text or detection.raw_text or zone_state.last_plate
        zone_state.refresh_hold(
            plate=hold_plate,
            now_monotonic=now_monotonic,
            close_delay_sec=close_delay,
        )


def _snapshot_stage(
    *,
    cfg: Settings,
    detections: list[PlateDetection],
    detection_result: DetectionStageResult,
    frame: np.ndarray,
    zone_frames: dict[int, np.ndarray],
    stage: FrameStageContext,
    alpr: AlprService,
) -> None:
    """Handle recognition snapshot creation and saving.

    Args:
        cfg: Settings configuration.
        detections: List of detections in current frame.
        detection_result: Result of decision pipeline.
        frame: Full frame image.
        zone_frames: Pre-cropped zone images.
        stage: Frame processing context.
        alpr: ALPR service for drawing predictions.
    """
    if not cfg.recognition_snapshot_enabled or not detections:
        return

    try:
        detection_for_snapshot = detection_result.snapshot_source_detection or detections[0]
        selected_zone = None
        if detection_for_snapshot.zone_id is not None:
            selected_zone = stage.active_zones_by_id.get(detection_for_snapshot.zone_id)

        primary_plate = (
            detection_result.frame_last_plate
            or detection_for_snapshot.normalized_text
            or detection_for_snapshot.raw_text
        )

        snapshot_frame = frame
        apply_alpr_predictions = True
        if selected_zone is not None:
            zone_image = zone_frames.get(detection_for_snapshot.zone_id or -1)
            if zone_image is None:
                zone_image = crop_zone(frame, selected_zone)

            try:
                annotated_zone_image, _ = alpr.draw_predictions(zone_image)
                snapshot_frame = paste_zone_image(snapshot_frame, selected_zone, annotated_zone_image)
            except (ValueError, RuntimeError) as exc:
                LOG.warning("Failed to annotate zone snapshot: %s", exc)
            # Never apply full-frame ALPR predictions if we have a zone; detection was in zone only
            apply_alpr_predictions = False

        write_recognition_snapshot(
            frame=snapshot_frame,
            alpr=alpr,
            captured_at=stage.now,
            frame_id=detection_for_snapshot.frame_id,
            plate=primary_plate,
            decision=detection_result.frame_last_decision,
            reason_code=detection_result.frame_last_reason or "raw_detection",
            zone_name=detection_for_snapshot.zone_name,
            zones=stage.active_zones,
            highlight_zone_id=detection_for_snapshot.zone_id,
            apply_alpr_predictions=apply_alpr_predictions,
            output_dir=cfg.recognition_snapshot_dir,
            jpeg_quality=cfg.recognition_snapshot_jpeg_quality,
            max_files=cfg.recognition_snapshot_max_files,
        )
    except OSError as exc:
        LOG.warning("Failed to save recognition snapshot: %s", exc)


def _preview_stage(
    *,
    cfg: Settings,
    camera_id: int | None,
    frame: np.ndarray,
    detections: list[PlateDetection],
    detection_result: DetectionStageResult,
    stage: FrameStageContext,
    state: PipelineState,
) -> None:
    """Handle preview artifacts generation.

    Args:
        cfg: Settings configuration.
        camera_id: Camera ID for scoped preview paths.
        frame: Full frame image.
        detections: List of detections in current frame.
        detection_result: Result of decision pipeline.
        stage: Frame processing context.
        state: Pipeline state; updates last_preview_write_ts in place.
    """
    if not cfg.preview_enabled:
        return

    now_ts = time.monotonic()
    if now_ts - state.last_preview_write_ts < cfg.preview_write_interval_sec:
        return

    annotated = frame
    preview_plates = [d.normalized_text for d in detections if d.normalized_text]

    if stage.active_zones:
        annotated = draw_zones(annotated, stage.active_zones)

    preview_status = "detect" if detections else (
        "idle-motion-skip" if stage.skip_alpr_this_frame else "idle"
    )
    preview_overlay = f"{stage.now.strftime('%Y-%m-%d %H:%M:%S')} | status={preview_status}"
    cv2.putText(
        annotated,
        preview_overlay,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    try:
        write_preview_artifacts(
            image=annotated,
            image_path=cfg.get_preview_image_path(camera_id),
            meta_path=cfg.get_preview_meta_path(camera_id),
            captured_at=stage.now,
            has_detections=bool(detections),
            last_plate=preview_plates[0] if preview_plates else None,
            last_decision=detection_result.frame_last_decision,
            jpeg_quality=cfg.preview_jpeg_quality,
        )
        state.last_preview_write_ts = now_ts
    except OSError as exc:
        LOG.warning("Failed to save preview artifacts: %s", exc)


def _poll_single_camera(
    *,
    camera_record: dict,
    camera: SnapshotCameraClient,
    alpr: AlprService,
    barrier: BarrierController,
    db: Database,
    cfg: Settings,
    state: PipelineState,
) -> None:
    """Poll and process a single camera's frame.

    Args:
        camera_record: Camera dict from database (with id, name, etc.)
        camera: SnapshotCameraClient instance for this camera.
        alpr: ALPR service instance.
        barrier: BarrierController instance.
        db: Database connection.
        cfg: Settings configuration.
        state: Pipeline state with zone_states and prev_frame.
    """
    camera_id = camera_record.get("id")
    camera_name = camera_record.get("name", "unknown")

    # Fetch frame
    frame = camera.fetch_frame()
    if frame is None:
        state.close_all_zones(barrier)
        return

    # Process frame (zone filtering, motion detection)
    stage = _process_frame(
        frame=frame,
        prev_frame=state.prev_frame,
        camera_id=camera_id,
        db=db,
        cfg=cfg,
        state=state,
    )
    if stage is None:
        state.close_all_zones(barrier)
        state.update_frame(frame)
        return

    # Detect plates in zones using single-shot detection
    detections: list[PlateDetection] = []
    zone_frames: dict[int, np.ndarray] = {}
    decision_detection: PlateDetection | None = None

    if not stage.skip_alpr_this_frame:
        detections, zone_frames = _detect_in_zones(
            frame=frame,
            alpr=alpr,
            detected_at=stage.now,
            frame_id=stage.frame_id,
            active_zones=stage.active_zones,
        )

        decision_detection = _select_best_detection(
            detections=detections,
            min_ocr_confidence=cfg.ocr_open_threshold,
        )

    # Make decisions and act on detections
    detection_result = _handle_detections(
        detections=detections,
        decision_detection=decision_detection,
        db=db,
        cfg=cfg,
        barrier=barrier,
        zone_states=state.zone_states,
        camera_id=camera_id,
    )

    # Manage zone hold times
    _refresh_zone_hold(
        detections=detections,
        cfg=cfg,
        state=state,
        now_monotonic=time.monotonic(),
    )
    state.close_all_zones(barrier)

    # Generate artifacts (snapshots and preview)
    _snapshot_stage(
        cfg=cfg,
        detections=detections,
        detection_result=detection_result,
        frame=frame,
        zone_frames=zone_frames,
        stage=stage,
        alpr=alpr,
    )

    _preview_stage(
        cfg=cfg,
        camera_id=camera_id,
        frame=frame,
        detections=detections,
        detection_result=detection_result,
        stage=stage,
        state=state,
    )

    # Prepare for next iteration
    state.update_frame(frame)


def run_camera_worker(camera_id: int, settings: Settings | None = None) -> None:
    """Run the pipeline for one camera."""
    cfg = settings or Settings.from_env()
    configure_logging(cfg.log_file_path)

    db = Database(cfg.db_path)
    db.init()

    camera_record = db.get_camera(camera_id)
    if camera_record is None or not camera_record.get("is_active", False):
        LOG.warning("Camera %s is missing or inactive; worker will exit", camera_id)
        return

    encryption_key = cfg.get_camera_credentials_encryption_key()
    creds = db.get_camera_credentials(camera_id, encryption_key)
    if creds is None:
        LOG.error("Failed to retrieve credentials for camera %s (id=%s)", camera_record.get("name"), camera_id)
        return
    username, password, auth_mode = creds

    try:
        alpr = AlprService(detector_model=cfg.detector_model, ocr_model=cfg.ocr_model)
    except (ValueError, RuntimeError) as exc:
        LOG.error("Failed to initialize ALPR models: %s", exc)
        raise

    zones = db.get_zones(include_disabled=True, camera_id=camera_id)
    barrier = BarrierController(
        dry_run=cfg.dry_run_open,
        action_mode=cfg.barrier_action_mode,
        ha_base_url=cfg.barrier_ha_base_url,
        ha_token=cfg.barrier_ha_token,
        zone_open_entity_ids={
            int(zone["id"]): str(zone.get("ha_open_entity_id") or "")
            for zone in zones
            if zone.get("ha_open_entity_id")
        },
        zone_close_entity_ids={
            int(zone["id"]): str(zone.get("ha_close_entity_id") or "")
            for zone in zones
            if zone.get("ha_close_entity_id")
        },
        timeout_sec=cfg.barrier_request_timeout_sec,
        retries=cfg.barrier_request_retries,
        verify_tls=cfg.barrier_verify_tls,
    )

    camera = SnapshotCameraClient(
        url=str(camera_record.get("snapshot_url") or ""),
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
        username=username,
        password=password,
        auth_mode=auth_mode,
    )
    state = PipelineState.create_initial()

    LOG.info("Camera worker started for camera %s (id=%s)", camera_record.get("name"), camera_id)

    try:
        while True:
            current_camera = db.get_camera(camera_id)
            if current_camera is None or not current_camera.get("is_active", False):
                LOG.info("Camera %s became inactive; stopping worker", camera_id)
                return

            try:
                _poll_single_camera(
                    camera_record=current_camera,
                    camera=camera,
                    alpr=alpr,
                    barrier=barrier,
                    db=db,
                    cfg=cfg,
                    state=state,
                )
            except Exception as exc:  # noqa: BLE001
                LOG.error("Error processing camera %s (id=%s): %s", current_camera.get("name"), camera_id, exc)

            time.sleep(cfg.poll_interval_sec)
    except KeyboardInterrupt:
        LOG.info("Camera worker interrupted by user")
    finally:
        try:
            camera.close()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Error closing camera client: %s", exc)


def run(settings: Settings | None = None) -> None:
    """Run the camera worker supervisor.

    The supervisor owns whitelist sync and camera process lifecycle. It stays idle
    when no cameras exist, and starts one subprocess per active camera when cameras
    are present.
    """
    cfg = settings or Settings.from_env()
    configure_logging(cfg.log_file_path)

    db = Database(cfg.db_path)
    db.init()
    provider = create_whitelist_provider(cfg)

    processes: dict[int, subprocess.Popen] = {}
    last_idle_log = 0.0

    def stop_process(camera_id: int) -> None:
        process = processes.pop(camera_id, None)
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    try:
        while True:
            if db.is_sync_due(cfg.onec_sync_interval_hours):
                try:
                    _sync_whitelist(db, provider, cfg)
                except (IOError, TimeoutError) as exc:
                    LOG.warning("Scheduled whitelist sync failed: %s", exc)

            active_cameras = [camera for camera in db.list_cameras(is_active=True) if camera.get("id") is not None]
            active_ids = {int(camera["id"]) for camera in active_cameras}

            for camera_id in list(processes):
                if camera_id not in active_ids:
                    LOG.info("Stopping camera worker for removed/inactive camera id=%s", camera_id)
                    stop_process(camera_id)

            for camera in active_cameras:
                camera_id = int(camera["id"])
                process = processes.get(camera_id)
                if process is not None and process.poll() is None:
                    continue

                if process is not None:
                    processes.pop(camera_id, None)

                command = [sys.executable, *_WORKER_SCRIPT, "--camera-id", str(camera_id)]
                LOG.info("Starting worker subprocess for camera id=%s", camera_id)
                processes[camera_id] = subprocess.Popen(command)

            if not active_ids:
                now_ts = time.monotonic()
                if now_ts - last_idle_log >= 30.0:
                    LOG.info("No active cameras in database; supervisor is idle")
                    last_idle_log = now_ts

            for camera_id, process in list(processes.items()):
                if process.poll() is None:
                    continue
                LOG.warning("Camera worker exited for camera id=%s with code=%s; restarting", camera_id, process.returncode)
                processes.pop(camera_id, None)

            time.sleep(cfg.poll_interval_sec)

    except KeyboardInterrupt:
        LOG.info("Supervisor interrupted by user")
    finally:
        for camera_id in list(processes):
            stop_process(camera_id)


