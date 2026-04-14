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
from .runtime_state import ZoneRuntimeState
from .types import PlateDetection, VoteOutcome
from .voting import TemporalVoter

LOG = logging.getLogger(__name__)


def apply_temporal_voting(
    detection: PlateDetection,
    voters: dict[str, TemporalVoter],
    cfg: Settings,
) -> VoteOutcome | None:
    """Apply temporal voting to a detection.

    Gets or creates a TemporalVoter for the zone, calls voter.observe(),
    and returns the accumulated vote if thresholds are met, else None.

    Args:
        detection: The plate detection to vote on.
        voters: Dict of zone voters, keyed by "zone:<id>" or "full".
        cfg: Settings with voting window, min confirmations, min confidence.

    Returns:
        VoteOutcome if voting thresholds met, None otherwise.
    """
    voter_key = f"zone:{detection.zone_id}" if detection.zone_id is not None else "full"
    voter = voters.get(voter_key)

    if voter is None:
        voter = TemporalVoter(
            window_sec=cfg.voting_window_sec,
            min_confirmations=cfg.min_confirmations,
            min_avg_confidence=cfg.min_avg_confidence,
        )
        voters[voter_key] = voter

    return voter.observe(detection)


def evaluate_decision(
    vote_or_detection: VoteOutcome | PlateDetection,
    db: Database,
    cfg: Settings,
    is_fast_open: bool = False,
) -> tuple[bool, str]:
    """Evaluate whitelist-based decision.

    Checks if the plate is whitelisted and returns (should_open, reason_code).
    Reason codes: "fast_open_approved", "fast_not_whitelisted", "open_approved", "not_whitelisted".

    Args:
        vote_or_detection: VoteOutcome (voting path) or PlateDetection (fast-open path).
        db: Database for whitelist lookup.
        cfg: Settings for fuzzy matching config.
        is_fast_open: True if fast-open path, False for voting path.

    Returns:
        Tuple of (should_open: bool, reason_code: str).
    """
    plate = vote_or_detection.plate
    fuzzy_plate = vote_or_detection.fuzzy_plate

    whitelisted = db.is_whitelisted(
        plate=plate,
        fuzzy_plate=fuzzy_plate,
        enable_fuzzy_match=cfg.enable_fuzzy_match,
    )

    if is_fast_open:
        reason_code = "fast_open_approved" if whitelisted else "fast_not_whitelisted"
    else:
        reason_code = "open_approved" if whitelisted else "not_whitelisted"

    return whitelisted, reason_code


def record_decision_event(
    detection: PlateDetection,
    vote: VoteOutcome | None,
    decision: str,
    reason_code: str,
    db: Database,
) -> None:
    """Record a decision event to the database.

    Args:
        detection: The plate detection.
        vote: VoteOutcome if voting path, None for raw/fast-open.
        decision: "observed", "open", or "deny".
        reason_code: Event reason code (e.g., "raw_detection", "open_approved").
        db: Database connection.
    """
    db.record_event(
        occurred_at=detection.detected_at,
        frame_id=detection.frame_id,
        raw_plate=detection.raw_text,
        plate=detection.normalized_text,
        fuzzy_plate=detection.fuzzy_text,
        detection_confidence=detection.detection_confidence,
        ocr_confidence=detection.ocr_confidence,
        vote_confirmations=vote.confirmations if vote else None,
        vote_avg_confidence=vote.avg_confidence if vote else None,
        zone_id=detection.zone_id,
        zone_name=detection.zone_name,
        decision=decision,
        reason_code=reason_code,
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
        return

    zone_id = detection.zone_id
    plate = detection.normalized_text

    # Get or create zone state
    state = zone_states.setdefault(zone_id, ZoneRuntimeState())

    # Suppress duplicate open if zone already open
    if state.is_open:
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
