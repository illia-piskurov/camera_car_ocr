"""Decision-making stage functions extracted from orchestrator.

This module encapsulates temporal voting, whitelist evaluation, event recording,
and barrier actuation logic. Orchestrator.py becomes a thin coordinator that chains
these stages in sequence.
"""

import logging
import time

from .config import Settings
from .db import Database
from .barrier import BarrierController
from .fuzzy_edit import find_best_edit_match
from .runtime_state import ZoneRuntimeState
from .types import PlateDetection

LOG = logging.getLogger(__name__)


def evaluate_decision(
    *,
    plate: str,
    fuzzy_plate: str,
    ocr_confidence: float,
    db: Database,
    cfg: Settings,
) -> tuple[bool, str]:
    """Evaluate whitelist-based decision.

    Checks if the plate is whitelisted and returns (should_open, reason_code).
    Reason codes: "open_approved", "open_fuzzy_edit", or "not_whitelisted".

    Step 1: strict match (and optional visual-fuzzy match via ENABLE_FUZZY_MATCH).
    Step 2: if FUZZY_EDIT_ENABLED and confidence >= FUZZY_EDIT_THRESHOLD,
            compare against every whitelist plate using Levenshtein distance;
            allow if the closest match is within FUZZY_EDIT_MAX_DISTANCE.
    """
    whitelisted = db.is_whitelisted(
        plate=plate,
        fuzzy_plate=fuzzy_plate,
        enable_fuzzy_match=cfg.enable_fuzzy_match,
    )
    if whitelisted:
        return True, "open_approved"

    if cfg.fuzzy_edit_enabled and ocr_confidence >= cfg.fuzzy_edit_threshold:
        active_plates = db.get_active_plates()
        matched, dist = find_best_edit_match(plate, active_plates, cfg.fuzzy_edit_max_distance)
        if matched is not None:
            LOG.info(
                "Fuzzy edit match: plate=%s matched=%s dist=%d ocr_conf=%.3f",
                plate,
                matched,
                dist,
                ocr_confidence,
            )
            return True, "open_fuzzy_edit"

    return False, "not_whitelisted"


def record_decision_event(
    detection: PlateDetection,
    decision: str,
    reason_code: str,
    db: Database,
    camera_id: int | None = None,
) -> None:
    """Record a decision event to the database.

    Args:
        detection: The plate detection.
        decision: "observed", "open", or "deny".
        reason_code: Event reason code (e.g., "raw_detection", "open_approved").
        db: Database connection.
        camera_id: Optional camera ID for event attribution.
    """
    db.record_event(
        occurred_at=detection.detected_at,
        frame_id=detection.frame_id,
        raw_plate=detection.raw_text,
        plate=detection.normalized_text,
        fuzzy_plate=detection.fuzzy_text,
        detection_confidence=detection.detection_confidence,
        ocr_confidence=detection.ocr_confidence,
        vote_confirmations=None,
        vote_avg_confidence=None,
        zone_id=detection.zone_id,
        zone_name=detection.zone_name,
        decision=decision,
        reason_code=reason_code,
        camera_id=camera_id,
    )


def execute_barrier_action(
    should_open: bool,
    detection: PlateDetection,
    reason_code: str,
    barrier: BarrierController,
    cfg: Settings,
    zone_states: dict[int | None, ZoneRuntimeState],
) -> None:
    """Execute barrier open/close action based on decision.

    If should_open is False, this is a no-op. Otherwise, attempts to open the
    barrier for the zone and updates ZoneRuntimeState to track the hold period.

    Suppresses duplicate open commands if zone is already open.

    Args:
        should_open: Whether whitelist approved the plate.
        detection: The plate detection (for plate/zone/reason logging).
        reason_code: Reason code for logging.
        barrier: BarrierController instance.
        cfg: Settings for zone close-delay configuration.
        zone_states: Dict of zone runtime states, updated on successful open.
    """
    if not should_open:
        LOG.info(
            "Barrier open not attempted: decision is not open plate=%s zone=%s reason=%s",
            detection.normalized_text,
            detection.zone_id if detection.zone_id is not None else "full",
            reason_code,
        )
        return

    zone_id = detection.zone_id
    plate = detection.normalized_text

    # Get or create zone state
    state = zone_states.setdefault(zone_id, ZoneRuntimeState())

    # Suppress duplicate open if zone already open
    if state.is_open:
        LOG.info(
            "Barrier open suppressed: zone already open plate=%s zone=%s hold_until=%.3f",
            plate,
            zone_id if zone_id is not None else "full",
            state.close_deadline_monotonic,
        )
        return

    # Attempt barrier open
    opened = False
    try:
        opened = barrier.open(plate, reason_code, zone_id=zone_id)
    except Exception as exc:  # noqa: BLE001
        LOG.warning(
            "Barrier open call failed plate=%s zone=%s reason=%s: %s",
            plate,
            zone_id if zone_id is not None else "full",
            reason_code,
            exc,
        )

    # If successful, mark zone as open and set close deadline
    if opened:
        now_monotonic = time.monotonic()
        close_delay = max(0.1, cfg.get_zone_close_delay_sec(zone_id))
        state.mark_open(plate=plate, now_monotonic=now_monotonic, close_delay_sec=close_delay)
        LOG.info(
            "Barrier open confirmed plate=%s zone=%s close_delay_sec=%.2f",
            plate,
            zone_id if zone_id is not None else "full",
            close_delay,
        )
        return

    LOG.warning(
        "Barrier open was attempted but not confirmed plate=%s zone=%s reason=%s",
        plate,
        zone_id if zone_id is not None else "full",
        reason_code,
    )
