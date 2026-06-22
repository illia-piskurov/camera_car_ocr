"""Pipeline runtime state management.

Encapsulates all mutable state throughout the main run loop to simplify
function signatures and improve state consistency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .barrier import BarrierController
from .runtime_state import ZoneRuntimeState


@dataclass
class PipelineState:
    """Encapsulates all mutable pipeline state.

    Provides a single source of truth for zone states, voter tracking,
    frame history, and timing information throughout the run loop.
    """

    zone_states: dict[int | None, ZoneRuntimeState] = field(default_factory=dict)
    last_preview_write_ts: float = 0.0
    last_no_zone_warning_ts: float = 0.0
    # Suppress repeated deny/observed events for same plate+zone
    _deny_ts: dict[tuple[str, int | None], float] = field(default_factory=dict)
    _observed_ts: dict[tuple[str, int | None], float] = field(default_factory=dict)

    DENY_SUPPRESS_SEC: float = 300.0     # 5 min — same plate can't spam deny alerts
    OBSERVED_SUPPRESS_SEC: float = 120.0 # 2 min — raw detection events

    def is_deny_suppressed(self, plate: str, zone_id: int | None) -> bool:
        return time.monotonic() - self._deny_ts.get((plate, zone_id), 0.0) < self.DENY_SUPPRESS_SEC

    def mark_deny(self, plate: str, zone_id: int | None) -> None:
        self._deny_ts[(plate, zone_id)] = time.monotonic()

    def is_observed_suppressed(self, plate: str, zone_id: int | None) -> bool:
        return time.monotonic() - self._observed_ts.get((plate, zone_id), 0.0) < self.OBSERVED_SUPPRESS_SEC

    def mark_observed(self, plate: str, zone_id: int | None) -> None:
        self._observed_ts[(plate, zone_id)] = time.monotonic()

    def close_all_zones(self, barrier: BarrierController) -> None:
        """Close all currently open zones.

        Deduplicates close commands by entity_id so that multiple zones mapped
        to the same toggle/impulse button (e.g. KNX) only send one press.

        Args:
            barrier: BarrierController instance to send close commands.
        """
        import logging
        LOG = logging.getLogger(__name__)

        now_monotonic = time.monotonic()
        closed_entities: set[str] = set()

        for zone_id, state in self.zone_states.items():
            deadline = state.close_deadline_monotonic
            if deadline is None or now_monotonic < deadline:
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
        )
