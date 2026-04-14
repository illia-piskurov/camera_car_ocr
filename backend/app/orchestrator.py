from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import cv2
import numpy as np

from .alpr_service import AlprService
from .barrier import BarrierController
from .camera import SnapshotCameraClient
from .config import Settings
from .db import Database
from .motion_detector import has_motion_in_zone
from .onec_provider import WhitelistProvider, create_whitelist_provider
from .pipeline_state import PipelineState
from .preview_pipeline import write_preview_artifacts, write_recognition_snapshot
from .runtime_state import ZoneRuntimeState
from .types import PlateDetection
from .voting import TemporalVoter
from .zones import crop_zone, draw_zones, paste_zone_image
from . import stages

LOG = logging.getLogger(__name__)


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


def _close_expired_zones(
    *,
    zone_states: dict[int | None, ZoneRuntimeState],
    barrier: BarrierController,
    now_monotonic: float,
) -> None:
    for zone_id, state in zone_states.items():
        deadline = state.close_deadline_monotonic
        if deadline is None or now_monotonic < deadline:
            continue

        try:
            barrier.close(reason="auto_close_timer", plate=state.last_plate, zone_id=zone_id)
        except Exception as exc:  # noqa: BLE001
            LOG.warning(
                "Barrier close call failed plate=%s zone=%s reason=auto_close_timer: %s",
                state.last_plate,
                zone_id if zone_id is not None else "full",
                exc,
            )
        finally:
            state.clear()


def _process_frame(
    *,
    frame,
    prev_frame,
    db: Database,
    cfg: Settings,
    state: PipelineState,
) -> FrameStageContext | None:
    now = datetime.now(timezone.utc)
    frame_id = uuid4().hex
    active_zones = db.get_zones(include_disabled=False)[:3]

    if not active_zones:
        now_monotonic = time.monotonic()
        if now_monotonic - state.last_no_zone_warning_ts >= 30.0:
            LOG.warning(
                "No active zones configured. ALPR and barrier actions are paused until zones are defined"
            )
            state.last_no_zone_warning_ts = now_monotonic
        return None

    skip_alpr_this_frame = False
    if cfg.motion_detection_enabled and prev_frame is not None:
        zones_with_motion = []
        for zone in active_zones:
            if has_motion_in_zone(
                prev_frame,
                frame,
                zone,
                threshold=cfg.motion_threshold_percent,
                blur_kernel=cfg.motion_blur_kernel,
            ):
                zones_with_motion.append(zone)

        if not zones_with_motion:
            LOG.debug("No motion in any zone, skipping ALPR")
            skip_alpr_this_frame = True

        if zones_with_motion:
            active_zones = zones_with_motion

    active_zones_by_id = {
        int(zone["id"]): zone
        for zone in active_zones
        if zone.get("id") is not None
    }
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
    stage: FrameStageContext,
) -> tuple[list[PlateDetection], dict[int, np.ndarray]]:
    detections: list[PlateDetection] = []
    zone_frames: dict[int, np.ndarray] = {}

    if stage.skip_alpr_this_frame or not stage.active_zones:
        return detections, zone_frames

    for zone in stage.active_zones:
        try:
            zone_frame = crop_zone(frame, zone)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Failed to crop zone %s: %s", zone.get("name"), exc)
            continue

        zone_id = int(zone.get("id")) if zone.get("id") is not None else None
        if zone_id is not None:
            zone_frames[zone_id] = zone_frame

        detections.extend(
            alpr.detect(
                zone_frame,
                detected_at=stage.now,
                frame_id=stage.frame_id,
                zone_id=zone_id,
                zone_name=str(zone.get("name") or ""),
            )
        )

    return detections, zone_frames


def _handle_detections(
    *,
    detections: list[PlateDetection],
    db: Database,
    cfg: Settings,
    voters: dict[str, TemporalVoter],
    barrier: BarrierController,
    zone_states: dict[int | None, ZoneRuntimeState],
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
            vote=None,
            decision="observed",
            reason_code="raw_detection",
            db=db,
        )

        # Route to fast-open or temporal voting
        if cfg.fast_open_enabled and detection.ocr_confidence >= cfg.fast_open_confidence:
            # Fast-open path: treat single high-confidence detection as immediate vote
            should_open, reason_code = stages.evaluate_decision(
                vote_or_detection=detection,
                db=db,
                cfg=cfg,
                is_fast_open=True,
            )

            result.frame_last_decision = "open" if should_open else "deny"
            result.frame_last_plate = detection.normalized_text
            result.frame_last_reason = reason_code
            result.frame_last_zone = detection.zone_name
            result.snapshot_source_detection = detection

            stages.record_decision_event(
                detection=detection,
                vote=None,
                decision=result.frame_last_decision,
                reason_code=reason_code,
                db=db,
            )

            LOG.info(
                "Fast decision plate=%s ocr_conf=%.3f det_conf=%.3f decision=%s reason=%s",
                detection.normalized_text,
                detection.ocr_confidence,
                detection.detection_confidence,
                result.frame_last_decision,
                reason_code,
            )

            stages.execute_barrier_action(
                should_open=should_open,
                detection=detection,
                reason_code=reason_code,
                barrier=barrier,
                cfg=cfg,
                zone_states=zone_states,
            )
            continue

        # Temporal voting path
        vote = stages.apply_temporal_voting(
            detection=detection,
            voters=voters,
            cfg=cfg,
        )
        if vote is None:
            continue

        should_open, reason_code = stages.evaluate_decision(
            vote_or_detection=vote,
            db=db,
            cfg=cfg,
            is_fast_open=False,
        )

        result.frame_last_decision = "open" if should_open else "deny"
        result.frame_last_plate = vote.plate
        result.frame_last_reason = reason_code
        result.frame_last_zone = detection.zone_name
        result.snapshot_source_detection = detection

        stages.record_decision_event(
            detection=detection,
            vote=vote,
            decision=result.frame_last_decision,
            reason_code=reason_code,
            db=db,
        )

        LOG.info(
            "Decision plate=%s confirmations=%s avg_conf=%.3f decision=%s reason=%s",
            vote.plate,
            vote.confirmations,
            vote.avg_confidence,
            result.frame_last_decision,
            reason_code,
        )

        stages.execute_barrier_action(
            should_open=should_open,
            detection=detection,
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


def _initialize_pipeline(
    cfg: Settings,
) -> tuple[SnapshotCameraClient, AlprService, BarrierController, Database, WhitelistProvider]:
    """Initialize all pipeline components.

    Args:
        cfg: Settings configuration.

    Returns:
        Tuple of (camera, alpr, barrier, db, provider) initialized instances.
    """
    db = Database(cfg.db_path)
    db.init()

    provider = create_whitelist_provider(cfg)

    camera = SnapshotCameraClient(
        url=cfg.camera_snapshot_url,
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
        username=cfg.camera_username,
        password=cfg.camera_password,
        auth_mode=cfg.camera_auth_mode,
    )

    try:
        alpr = AlprService(detector_model=cfg.detector_model, ocr_model=cfg.ocr_model)
    except (ValueError, RuntimeError) as exc:
        LOG.error("Failed to initialize ALPR models: %s", exc)
        raise

    barrier = BarrierController(
        dry_run=cfg.dry_run_open,
        action_mode=cfg.barrier_action_mode,
        ha_base_url=cfg.barrier_ha_base_url,
        ha_token=cfg.barrier_ha_token,
        zone_open_entity_ids={
            1: cfg.zone1_barrier_open_entity_id,
            2: cfg.zone2_barrier_open_entity_id,
        },
        zone_close_entity_ids={
            1: cfg.zone1_barrier_close_entity_id,
            2: cfg.zone2_barrier_close_entity_id,
        },
        timeout_sec=cfg.barrier_request_timeout_sec,
        retries=cfg.barrier_request_retries,
        verify_tls=cfg.barrier_verify_tls,
    )

    return camera, alpr, barrier, db, provider


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
                apply_alpr_predictions = False
            except (ValueError, RuntimeError) as exc:
                LOG.warning("Failed to annotate zone snapshot, falling back to full-frame: %s", exc)

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
    frame: np.ndarray,
    detections: list[PlateDetection],
    detection_result: DetectionStageResult,
    stage: FrameStageContext,
    alpr: AlprService,
    state: PipelineState,
) -> None:
    """Handle preview artifacts generation.

    Args:
        cfg: Settings configuration.
        frame: Full frame image.
        detections: List of detections in current frame.
        detection_result: Result of decision pipeline.
        stage: Frame processing context.
        alpr: ALPR service for drawing predictions.
        state: Pipeline state; updates last_preview_write_ts in place.
    """
    if not cfg.preview_enabled:
        return

    now_ts = time.monotonic()
    if now_ts - state.last_preview_write_ts < cfg.preview_write_interval_sec:
        return

    annotated = frame
    preview_plates = [d.normalized_text for d in detections if d.normalized_text]

    if not stage.skip_alpr_this_frame:
        try:
            annotated, draw_plates = alpr.draw_predictions(frame)
            if draw_plates:
                preview_plates = draw_plates
        except (ValueError, RuntimeError) as exc:
            LOG.warning("Preview draw_predictions failed: %s", exc)

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
            image_path=cfg.preview_image_path,
            meta_path=cfg.preview_meta_path,
            captured_at=stage.now,
            has_detections=bool(detections),
            last_plate=preview_plates[0] if preview_plates else None,
            last_decision=detection_result.frame_last_decision,
            jpeg_quality=cfg.preview_jpeg_quality,
        )
        state.last_preview_write_ts = now_ts
    except OSError as exc:
        LOG.warning("Failed to save preview artifacts: %s", exc)


def run(settings: Settings | None = None) -> None:
    """Run the main ALPR pipeline loop.

    Args:
        settings: Optional Settings instance; loads from env if not provided.
    """
    cfg = settings or Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # Initialize all components
    camera, alpr, barrier, db, provider = _initialize_pipeline(cfg)

    # Initial whitelist sync
    if db.is_sync_due(cfg.onec_sync_interval_hours):
        try:
            _sync_whitelist(db, provider, cfg)
        except (IOError, TimeoutError) as exc:
            LOG.warning("Initial whitelist sync failed: %s", exc)

    LOG.info(
        "Pipeline started. dry_run=%s barrier_action_mode=%s whitelist_provider=%s",
        cfg.dry_run_open,
        cfg.barrier_action_mode,
        provider.source,
    )

    # Create pipeline state
    state = PipelineState.create_initial()

    try:
        while True:
            # Periodic whitelist sync
            if db.is_sync_due(cfg.onec_sync_interval_hours):
                try:
                    _sync_whitelist(db, provider, cfg)
                except (IOError, TimeoutError) as exc:
                    LOG.warning("Scheduled whitelist sync failed: %s", exc)

            # Fetch frame
            frame = camera.fetch_frame()
            if frame is None:
                state.close_all_zones(barrier)
                time.sleep(cfg.poll_interval_sec)
                continue

            # Process frame (zone filtering, motion detection)
            stage = _process_frame(
                frame=frame,
                prev_frame=state.prev_frame,
                db=db,
                cfg=cfg,
                state=state,
            )
            if stage is None:
                state.close_all_zones(barrier)
                state.update_frame(frame)
                time.sleep(cfg.poll_interval_sec)
                continue

            # Detect plates in zones
            detections, zone_frames = _detect_in_zones(
                frame=frame,
                alpr=alpr,
                stage=stage,
            )

            # Make decisions and act on detections
            detection_result = _handle_detections(
                detections=detections,
                db=db,
                cfg=cfg,
                voters=state.voters,
                barrier=barrier,
                zone_states=state.zone_states,
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
                frame=frame,
                detections=detections,
                detection_result=detection_result,
                stage=stage,
                alpr=alpr,
                state=state,
            )

            # Prepare for next iteration
            state.update_frame(frame)
            time.sleep(cfg.poll_interval_sec)

    except KeyboardInterrupt:
        LOG.info("Pipeline interrupted by user")
    finally:
        camera.close()

