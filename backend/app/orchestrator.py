from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from .alpr_service import AlprService
from .barrier import BarrierController
from .camera import SnapshotCameraClient
from .config import Settings
from .db import Database
from .decision import BarrierDecisionEngine
from .onec_provider import StubFileWhitelistProvider
from .voting import TemporalVoter

LOG = logging.getLogger(__name__)


def _sync_whitelist(db: Database, provider: StubFileWhitelistProvider) -> None:
    rows = provider.full_sync()
    count = db.upsert_whitelist(rows, source="1c_stub")
    db.set_last_sync_now()
    LOG.info("Whitelist synced from stub: %s plates", count)


def run(settings: Settings | None = None) -> None:
    cfg = settings or Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(cfg.db_path)
    db.init()

    provider = StubFileWhitelistProvider(cfg.onec_stub_file)
    if db.is_sync_due(cfg.onec_sync_interval_hours):
        _sync_whitelist(db, provider)

    camera = SnapshotCameraClient(
        url=cfg.camera_snapshot_url,
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
    )
    alpr = AlprService(detector_model=cfg.detector_model, ocr_model=cfg.ocr_model)
    voter = TemporalVoter(
        window_sec=cfg.voting_window_sec,
        min_confirmations=cfg.min_confirmations,
        min_avg_confidence=cfg.min_avg_confidence,
    )
    decider = BarrierDecisionEngine(
        plate_cooldown_sec=cfg.plate_cooldown_sec,
        global_cooldown_sec=cfg.global_cooldown_sec,
    )
    barrier = BarrierController(dry_run=cfg.dry_run_open)

    LOG.info("Pipeline started. dry_run=%s", cfg.dry_run_open)

    try:
        while True:
            if db.is_sync_due(cfg.onec_sync_interval_hours):
                _sync_whitelist(db, provider)

            frame = camera.fetch_frame()
            if frame is None:
                time.sleep(cfg.poll_interval_sec)
                continue

            now = datetime.now(timezone.utc)
            detections = alpr.detect(frame, detected_at=now)
            if not detections:
                time.sleep(cfg.poll_interval_sec)
                continue

            for detection in detections:
                db.record_event(
                    occurred_at=detection.detected_at,
                    frame_id=detection.frame_id,
                    raw_plate=detection.raw_text,
                    plate=detection.normalized_text,
                    fuzzy_plate=detection.fuzzy_text,
                    detection_confidence=detection.detection_confidence,
                    ocr_confidence=detection.ocr_confidence,
                    decision="observed",
                    reason_code="raw_detection",
                )

                vote = voter.observe(detection)
                if vote is None:
                    continue

                whitelisted = db.is_whitelisted(
                    plate=vote.plate,
                    fuzzy_plate=vote.fuzzy_plate,
                    enable_fuzzy_match=cfg.enable_fuzzy_match,
                )
                decision = decider.evaluate(vote=vote, is_whitelisted=whitelisted, now=detection.detected_at)

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
                    decision="open" if decision.should_open else "deny",
                    reason_code=decision.reason_code,
                )

                LOG.info(
                    "Decision plate=%s confirmations=%s avg_conf=%.3f decision=%s reason=%s",
                    vote.plate,
                    vote.confirmations,
                    vote.avg_confidence,
                    "open" if decision.should_open else "deny",
                    decision.reason_code,
                )

                if decision.should_open:
                    barrier.open(vote.plate, decision.reason_code)

            time.sleep(cfg.poll_interval_sec)
    except KeyboardInterrupt:
        LOG.info("Pipeline interrupted by user")
    finally:
        camera.close()
