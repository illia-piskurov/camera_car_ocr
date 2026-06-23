"""Pipeline runtime state management.

Encapsulates all mutable state throughout the main run loop to simplify
function signatures and improve state consistency.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .barrier import BarrierController
from .barrier_state import BarrierStateDetector
from .runtime_state import ZoneRuntimeState

LOG = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Encapsulates all mutable pipeline state.

    Provides a single source of truth for zone states, voter tracking,
    frame history, and timing information throughout the run loop.
    """

    zone_states: dict[int | None, ZoneRuntimeState] = field(default_factory=dict)
    last_preview_write_ts: float = 0.0
    last_no_zone_warning_ts: float = 0.0
    prev_frame: Any = None  # np.ndarray | None — kept for motion detection
    barrier_detectors: dict[int, BarrierStateDetector] = field(default_factory=dict)
    # Suppress repeated deny/observed events for same plate+zone
    _deny_ts: dict[tuple[str, int | None], float] = field(default_factory=dict)
    _observed_ts: dict[tuple[str, int | None], float] = field(default_factory=dict)
    # Suppress all events from the same zone for N seconds after any event fires.
    # Prevents spam from repeated OCR frames of the same passing vehicle.
    # Open decisions always bypass this cooldown so a whitelisted plate is never blocked.
    _zone_cooldown_ts: dict[int | None, float] = field(default_factory=dict)

    DENY_SUPPRESS_SEC: float = 300.0     # 5 min — same plate can't spam deny alerts
    OBSERVED_SUPPRESS_SEC: float = 120.0 # 2 min — raw detection events
    ZONE_COOLDOWN_SEC: float = 8.0       # 8 s  — one vehicle pass per zone

    def is_deny_suppressed(self, plate: str, zone_id: int | None) -> bool:
        return time.monotonic() - self._deny_ts.get((plate, zone_id), 0.0) < self.DENY_SUPPRESS_SEC

    def mark_deny(self, plate: str, zone_id: int | None) -> None:
        self._deny_ts[(plate, zone_id)] = time.monotonic()

    def is_observed_suppressed(self, plate: str, zone_id: int | None) -> bool:
        return time.monotonic() - self._observed_ts.get((plate, zone_id), 0.0) < self.OBSERVED_SUPPRESS_SEC

    def mark_observed(self, plate: str, zone_id: int | None) -> None:
        self._observed_ts[(plate, zone_id)] = time.monotonic()

    def is_zone_in_cooldown(self, zone_id: int | None) -> bool:
        return time.monotonic() - self._zone_cooldown_ts.get(zone_id, 0.0) < self.ZONE_COOLDOWN_SEC

    def mark_zone_event(self, zone_id: int | None) -> None:
        self._zone_cooldown_ts[zone_id] = time.monotonic()

    def close_all_zones(
        self,
        barrier: BarrierController,
        open_only: bool = False,
        zone_barrier_ids: dict[int | None, int | None] | None = None,
        barrier_states: dict[int, str] | None = None,
    ) -> None:
        """Close all currently open zones whose deadline has expired.

        open_only: skip close commands (for barriers with own auto-close timer).
        zone_barrier_ids: mapping of zone_id → barrier_id for per-barrier state lookup.
        barrier_states: mapping of barrier_id → detected state string.
          If state is CLOSED — skip close (already closed, toggle would open).
        """
        from .barrier_state import CLOSED as BS_CLOSED

        now_monotonic = time.monotonic()
        closed_entities: set[str] = set()

        for zone_id, state in self.zone_states.items():
            deadline = state.close_deadline_monotonic
            if deadline is None or now_monotonic < deadline:
                continue

            if open_only:
                LOG.info(
                    "Barrier close skipped (open_only mode) plate=%s zone=%s",
                    state.last_plate,
                    zone_id if zone_id is not None else "full",
                )
                state.clear()
                continue

            bid = zone_barrier_ids.get(zone_id) if zone_barrier_ids else None
            barrier_state = barrier_states.get(bid) if (barrier_states and bid is not None) else None
            if barrier_state == BS_CLOSED:
                LOG.info(
                    "Barrier close skipped (camera: already closed) plate=%s zone=%s barrier=%s",
                    state.last_plate,
                    zone_id if zone_id is not None else "full",
                    bid,
                )
                state.clear()
                continue

            entity_id = (
                barrier.zone_close_entity_ids.get(zone_id, "")
                if zone_id is not None
                else ""
            )

            try:
                if entity_id and entity_id in closed_entities:
                    LOG.info(
                        "Barrier close suppressed: entity=%s already closed this cycle zone=%s",
                        entity_id,
                        zone_id,
                    )
                else:
                    barrier.close(reason="auto_close_timer", plate=state.last_plate, zone_id=zone_id)
                    if entity_id:
                        closed_entities.add(entity_id)
            except (IOError, TimeoutError) as exc:
                LOG.warning(
                    "Barrier close call failed plate=%s zone=%s reason=auto_close_timer: %s",
                    state.last_plate,
                    zone_id if zone_id is not None else "full",
                    exc,
                )
            finally:
                state.clear()

    @classmethod
    def create_initial(cls) -> PipelineState:
        """Factory method to create initial pipeline state.

        Returns:
            Fresh PipelineState with all defaults.
        """
        return cls(
            zone_states={},
            last_preview_write_ts=0.0,
            last_no_zone_warning_ts=0.0,
            _deny_ts={},
            _observed_ts={},
            _zone_cooldown_ts={},
        )
