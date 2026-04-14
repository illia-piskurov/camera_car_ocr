from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

import cv2
import numpy as np

from .alpr_service import AlprService
from .barrier import BarrierController
from .camera import SnapshotCameraClient
from .config import Settings
from .db import Database
from .decision import BarrierDecisionEngine
from .motion_detector import has_motion, has_motion_in_zone
from .onec_provider import WhitelistProvider, create_whitelist_provider
from .types import VoteOutcome
from .voting import TemporalVoter
from .zones import crop_zone, draw_zones, paste_zone_image

LOG = logging.getLogger(__name__)


def _sync_whitelist(db: Database, provider: WhitelistProvider, cfg: Settings) -> None:
    rows = provider.full_sync()

    if provider.source == "1c_http" and not rows and not cfg.onec_http_allow_empty_sync:
        LOG.warning("1C HTTP sync returned empty list; skipping DB update due to ONEC_HTTP_ALLOW_EMPTY_SYNC=0")
        return

    count = db.upsert_whitelist(rows, source=provider.source)
    db.set_last_sync_now()
    LOG.info("Whitelist synced from %s: %s plates", provider.source, count)


def _write_preview_artifacts(
    *,
    image,
    image_path: str,
    meta_path: str,
    captured_at: datetime,
    has_detections: bool,
    last_plate: str | None,
    last_decision: str | None,
    jpeg_quality: int,
) -> None:
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)

    quality = max(40, min(100, int(jpeg_quality)))
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode preview image")

    with open(image_path, "wb") as image_file:
        image_file.write(encoded.tobytes())

    payload = {
        "captured_at": captured_at.isoformat(),
        "has_detections": has_detections,
        "last_plate": last_plate,
        "last_decision": last_decision,
    }
    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump(payload, meta_file, ensure_ascii=False)


def _safe_file_segment(value: str | None, fallback: str = "unknown") -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return cleaned if cleaned else fallback


def _prune_old_snapshots(directory: str, max_files: int) -> None:
    if max_files <= 0:
        return

    entries: list[tuple[float, str]] = []
    for name in os.listdir(directory):
        if not name.lower().endswith(".jpg"):
            continue
        path = os.path.join(directory, name)
        try:
            entries.append((os.path.getmtime(path), path))
        except OSError:
            continue

    if len(entries) <= max_files:
        return

    entries.sort(key=lambda item: item[0])
    for _, path in entries[: len(entries) - max_files]:
        try:
            os.remove(path)
        except OSError:
            continue


def _write_recognition_snapshot(
    *,
    frame,
    alpr: AlprService,
    captured_at: datetime,
    frame_id: str,
    plate: str | None,
    decision: str | None,
    reason_code: str | None,
    zone_name: str | None,
    output_dir: str,
    jpeg_quality: int,
    max_files: int,
    zones: list[dict[str, object]] | None = None,
    highlight_zone_id: int | None = None,
    apply_alpr_predictions: bool = True,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    annotated = frame
    if apply_alpr_predictions:
        try:
            annotated, _ = alpr.draw_predictions(frame)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Snapshot draw_predictions failed, saving raw frame: %s", exc)

    if zones is not None:
        annotated = draw_zones(annotated, zones, highlight_zone_id=highlight_zone_id)

    overlay = (
        f"{captured_at.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"plate={plate or '-'} | zone={zone_name or 'full'} | decision={decision} | reason={reason_code or '-'}"
    )
    cv2.putText(
        annotated,
        overlay,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    quality = max(40, min(100, int(jpeg_quality)))
    ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode recognition snapshot")

    timestamp = captured_at.strftime("%Y%m%d_%H%M%S_%f")
    frame_part = _safe_file_segment(frame_id, fallback="frame")
    plate_part = _safe_file_segment(plate)
    decision_part = _safe_file_segment(decision, fallback="observed")
    filename = f"{timestamp}_{frame_part}_{plate_part}_{decision_part}.jpg"
    out_path = os.path.join(output_dir, filename)

    with open(out_path, "wb") as out_file:
        out_file.write(encoded.tobytes())

    _prune_old_snapshots(output_dir, max_files=max_files)


def run(settings: Settings | None = None) -> None:
    cfg = settings or Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(cfg.db_path)
    db.init()

    provider = create_whitelist_provider(cfg)
    if db.is_sync_due(cfg.onec_sync_interval_hours):
        try:
            _sync_whitelist(db, provider, cfg)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Initial whitelist sync failed: %s", exc)

    camera = SnapshotCameraClient(
        url=cfg.camera_snapshot_url,
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
        username=cfg.camera_username,
        password=cfg.camera_password,
        auth_mode=cfg.camera_auth_mode,
    )
    alpr = AlprService(detector_model=cfg.detector_model, ocr_model=cfg.ocr_model)
    voters: dict[str, TemporalVoter] = {}
    decider = BarrierDecisionEngine(
        plate_cooldown_sec=cfg.plate_cooldown_sec,
        global_cooldown_sec=cfg.global_cooldown_sec,
    )
    barrier = BarrierController(
        dry_run=cfg.dry_run_open,
        action_mode=cfg.barrier_action_mode,
        ha_base_url=cfg.barrier_ha_base_url,
        ha_token=cfg.barrier_ha_token,
        open_entity_id=cfg.barrier_open_entity_id,
        close_entity_id=cfg.barrier_close_entity_id,
        timeout_sec=cfg.barrier_request_timeout_sec,
        retries=cfg.barrier_request_retries,
        verify_tls=cfg.barrier_verify_tls,
    )

    LOG.info(
        "Pipeline started. dry_run=%s barrier_action_mode=%s whitelist_provider=%s",
        cfg.dry_run_open,
        cfg.barrier_action_mode,
        provider.source,
    )
    last_preview_write_ts = 0.0
    prev_frame: np.ndarray | None = None
    pending_close_at: float | None = None
    pending_close_plate: str | None = None

    try:
        while True:
            now_monotonic = time.monotonic()
            if pending_close_at is not None and now_monotonic >= pending_close_at:
                try:
                    barrier.close(reason="auto_close_timer", plate=pending_close_plate)
                except Exception as exc:  # noqa: BLE001
                    LOG.warning(
                        "Barrier close call failed plate=%s reason=auto_close_timer: %s",
                        pending_close_plate,
                        exc,
                    )
                finally:
                    pending_close_at = None
                    pending_close_plate = None

            if db.is_sync_due(cfg.onec_sync_interval_hours):
                try:
                    _sync_whitelist(db, provider, cfg)
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("Scheduled whitelist sync failed: %s", exc)

            frame = camera.fetch_frame()
            if frame is None:
                time.sleep(cfg.poll_interval_sec)
                continue

            skip_alpr_this_frame = False

            # Motion-gated ALPR: skip expensive inference if no motion detected
            if cfg.motion_detection_enabled and prev_frame is not None:
                now = datetime.now(timezone.utc)
                frame_id = uuid4().hex
                active_zones = db.get_zones(include_disabled=False)[:3]

                if active_zones:
                    # Per-zone motion check: only process zones with motion
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
                        # No motion in any zone, skip ALPR this frame
                        LOG.debug("No motion in any zone, skipping ALPR")
                        skip_alpr_this_frame = True

                    # Filter to only zones with motion
                    if zones_with_motion:
                        active_zones = zones_with_motion
                else:
                    # Full-frame motion check
                    if not has_motion(
                        prev_frame,
                        frame,
                        threshold=cfg.motion_threshold_percent,
                        blur_kernel=cfg.motion_blur_kernel,
                    ):
                        # No motion in full frame, skip ALPR this frame
                        LOG.debug("No motion in full frame, skipping ALPR")
                        skip_alpr_this_frame = True

            else:
                # Motion detection disabled or first frame: initialize normally
                now = datetime.now(timezone.utc)
                frame_id = uuid4().hex
                active_zones = db.get_zones(include_disabled=False)[:3]

            active_zones_by_id: dict[int, dict[str, object]] = {
                int(zone["id"]): zone for zone in active_zones if zone.get("id") is not None
            }

            detections = []
            zone_frames: dict[int, np.ndarray] = {}
            if not skip_alpr_this_frame and active_zones:
                for zone in active_zones:
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
                            detected_at=now,
                            frame_id=frame_id,
                            zone_id=zone_id,
                            zone_name=str(zone.get("name") or ""),
                        )
                    )
            elif not skip_alpr_this_frame:
                detections = alpr.detect(frame, detected_at=now, frame_id=frame_id)

            frame_last_decision: str | None = None
            frame_last_plate: str | None = None
            frame_last_reason: str | None = None
            frame_last_zone: str | None = None
            snapshot_source_detection = detections[0] if detections else None

            if detections:
                for detection in detections:
                    db.record_event(
                        occurred_at=detection.detected_at,
                        frame_id=detection.frame_id,
                        raw_plate=detection.raw_text,
                        plate=detection.normalized_text,
                        fuzzy_plate=detection.fuzzy_text,
                        detection_confidence=detection.detection_confidence,
                        ocr_confidence=detection.ocr_confidence,
                        zone_id=detection.zone_id,
                        zone_name=detection.zone_name,
                        decision="observed",
                        reason_code="raw_detection",
                    )

                    # Fast-path for very confident OCR: decide immediately.
                    if cfg.fast_open_enabled and detection.ocr_confidence >= cfg.fast_open_confidence:
                        fast_vote = VoteOutcome(
                            plate=detection.normalized_text,
                            fuzzy_plate=detection.fuzzy_text,
                            confirmations=1,
                            avg_confidence=detection.ocr_confidence,
                            window_sec=cfg.voting_window_sec,
                        )
                        whitelisted = db.is_whitelisted(
                            plate=fast_vote.plate,
                            fuzzy_plate=fast_vote.fuzzy_plate,
                            enable_fuzzy_match=cfg.enable_fuzzy_match,
                        )
                        decision = decider.evaluate(
                            vote=fast_vote,
                            is_whitelisted=whitelisted,
                            now=detection.detected_at,
                        )
                        frame_last_decision = "open" if decision.should_open else "deny"
                        frame_last_plate = fast_vote.plate
                        frame_last_reason = (
                            f"fast_{decision.reason_code}" if decision.reason_code else "fast_open_approved"
                        )
                        frame_last_zone = detection.zone_name
                        snapshot_source_detection = detection

                        db.record_event(
                            occurred_at=detection.detected_at,
                            frame_id=detection.frame_id,
                            raw_plate=detection.raw_text,
                            plate=fast_vote.plate,
                            fuzzy_plate=fast_vote.fuzzy_plate,
                            detection_confidence=detection.detection_confidence,
                            ocr_confidence=detection.ocr_confidence,
                            vote_confirmations=fast_vote.confirmations,
                            vote_avg_confidence=fast_vote.avg_confidence,
                            zone_id=detection.zone_id,
                            zone_name=detection.zone_name,
                            decision=frame_last_decision,
                            reason_code=frame_last_reason,
                        )

                        LOG.info(
                            "Fast decision plate=%s ocr_conf=%.3f det_conf=%.3f decision=%s reason=%s",
                            fast_vote.plate,
                            detection.ocr_confidence,
                            detection.detection_confidence,
                            frame_last_decision,
                            frame_last_reason,
                        )

                        if decision.should_open:
                            opened = False
                            try:
                                opened = barrier.open(fast_vote.plate, frame_last_reason)
                            except Exception as exc:  # noqa: BLE001
                                LOG.warning(
                                    "Barrier open call failed plate=%s reason=%s: %s",
                                    fast_vote.plate,
                                    frame_last_reason,
                                    exc,
                                )
                            if opened:
                                pending_close_at = time.monotonic() + max(
                                    0.1,
                                    cfg.barrier_close_delay_sec,
                                )
                                pending_close_plate = fast_vote.plate
                        continue

                    voter_key = f"zone:{detection.zone_id}" if detection.zone_id is not None else "full"
                    voter = voters.get(voter_key)
                    if voter is None:
                        voter = TemporalVoter(
                            window_sec=cfg.voting_window_sec,
                            min_confirmations=cfg.min_confirmations,
                            min_avg_confidence=cfg.min_avg_confidence,
                        )
                        voters[voter_key] = voter

                    vote = voter.observe(detection)
                    if vote is None:
                        continue

                    whitelisted = db.is_whitelisted(
                        plate=vote.plate,
                        fuzzy_plate=vote.fuzzy_plate,
                        enable_fuzzy_match=cfg.enable_fuzzy_match,
                    )
                    decision = decider.evaluate(vote=vote, is_whitelisted=whitelisted, now=detection.detected_at)
                    frame_last_decision = "open" if decision.should_open else "deny"
                    frame_last_plate = vote.plate
                    frame_last_reason = decision.reason_code
                    frame_last_zone = detection.zone_name
                    snapshot_source_detection = detection

                    db.record_event(
                        occurred_at=detection.detected_at,
                        frame_id=detection.frame_id,
                        raw_plate=detection.raw_text,
                        plate=vote.plate,
                        fuzzy_plate=vote.fuzzy_plate,
                        detection_confidence=detection.detection_confidence,
                        ocr_confidence=detection.ocr_confidence,
                        vote_confirmations=vote.confirmations,
                        vote_avg_confidence=vote.avg_confidence,
                        zone_id=detection.zone_id,
                        zone_name=detection.zone_name,
                        decision=frame_last_decision,
                        reason_code=decision.reason_code,
                    )

                    LOG.info(
                        "Decision plate=%s confirmations=%s avg_conf=%.3f decision=%s reason=%s",
                        vote.plate,
                        vote.confirmations,
                        vote.avg_confidence,
                        frame_last_decision,
                        decision.reason_code,
                    )

                    if decision.should_open:
                        opened = False
                        try:
                            opened = barrier.open(vote.plate, decision.reason_code)
                        except Exception as exc:  # noqa: BLE001
                            LOG.warning(
                                "Barrier open call failed plate=%s reason=%s: %s",
                                vote.plate,
                                decision.reason_code,
                                exc,
                            )
                        if opened:
                            pending_close_at = time.monotonic() + max(
                                0.1,
                                cfg.barrier_close_delay_sec,
                            )
                            pending_close_plate = vote.plate

            if (
                cfg.recognition_snapshot_enabled
                and detections
            ):
                try:
                    detection_for_snapshot = snapshot_source_detection or detections[0]
                    selected_zone = None
                    if detection_for_snapshot.zone_id is not None:
                        selected_zone = active_zones_by_id.get(detection_for_snapshot.zone_id)

                    primary_plate = (
                        frame_last_plate
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
                        except Exception as exc:  # noqa: BLE001
                            LOG.warning("Failed to annotate zone snapshot, falling back to full-frame snapshot: %s", exc)

                    _write_recognition_snapshot(
                        frame=snapshot_frame,
                        alpr=alpr,
                        captured_at=now,
                        frame_id=detection_for_snapshot.frame_id,
                        plate=primary_plate,
                        decision=frame_last_decision,
                        reason_code=frame_last_reason or "raw_detection",
                        zone_name=detection_for_snapshot.zone_name,
                        zones=active_zones,
                        highlight_zone_id=detection_for_snapshot.zone_id,
                        apply_alpr_predictions=apply_alpr_predictions,
                        output_dir=cfg.recognition_snapshot_dir,
                        jpeg_quality=cfg.recognition_snapshot_jpeg_quality,
                        max_files=cfg.recognition_snapshot_max_files,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("Failed to save recognition snapshot: %s", exc)

            if cfg.preview_enabled:
                now_ts = time.monotonic()
                if now_ts - last_preview_write_ts >= cfg.preview_write_interval_sec:
                    last_preview_write_ts = now_ts

                    annotated = frame
                    preview_plates = [d.normalized_text for d in detections if d.normalized_text]
                    if not skip_alpr_this_frame:
                        try:
                            annotated, draw_plates = alpr.draw_predictions(frame)
                            if draw_plates:
                                preview_plates = draw_plates
                        except Exception as exc:  # noqa: BLE001
                            LOG.warning("Preview draw_predictions failed, using raw frame: %s", exc)

                    if active_zones:
                        annotated = draw_zones(annotated, active_zones)

                    preview_status = "detect" if detections else ("idle-motion-skip" if skip_alpr_this_frame else "idle")
                    preview_overlay = f"{now.strftime('%Y-%m-%d %H:%M:%S')} | status={preview_status}"
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

                    _write_preview_artifacts(
                        image=annotated,
                        image_path=cfg.preview_image_path,
                        meta_path=cfg.preview_meta_path,
                        captured_at=now,
                        has_detections=bool(detections),
                        last_plate=preview_plates[0] if preview_plates else None,
                        last_decision=frame_last_decision,
                        jpeg_quality=cfg.preview_jpeg_quality,
                    )

            prev_frame = frame
            time.sleep(cfg.poll_interval_sec)
    except KeyboardInterrupt:
        LOG.info("Pipeline interrupted by user")
    finally:
        camera.close()
