"""Pipeline runtime state management.

Encapsulates all mutable state throughout the main run loop to simplify
function signatures and improve state consistency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .barrier import BarrierController
from .runtime_state import ZoneRuntimeState
from .voting import TemporalVoter


@dataclass
class PipelineState:
    """Encapsulates all mutable pipeline state.

    Provides a single source of truth for zone states, voter tracking,
    frame history, and timing information throughout the run loop.
    """

    zone_states: dict[int | None, ZoneRuntimeState] = field(default_factory=dict)
    voters: dict[str, TemporalVoter] = field(default_factory=dict)
    last_preview_write_ts: float = 0.0
    last_no_zone_warning_ts: float = 0.0
    prev_frame: np.ndarray | None = None

    def close_all_zones(self, barrier: BarrierController) -> None:
        """Close all currently open zones.

        Args:
            barrier: BarrierController instance to send close commands.
        """
        now_monotonic = time.monotonic()
        for zone_id, state in self.zone_states.items():
            deadline = state.close_deadline_monotonic
            if deadline is None or now_monotonic < deadline:
                continue

            try:
                barrier.close(reason="auto_close_timer", plate=state.last_plate, zone_id=zone_id)
            except (IOError, TimeoutError) as exc:
                import logging
                LOG = logging.getLogger(__name__)
                LOG.warning(
                    "Barrier close call failed plate=%s zone=%s reason=auto_close_timer: %s",
                    state.last_plate,
                    zone_id if zone_id is not None else "full",
                    exc,
                )
            finally:
                state.clear()

    def update_frame(self, frame: np.ndarray) -> None:
        """Update previous frame for motion detection.

        Args:
            frame: Current frame to store for next iteration.
        """
        self.prev_frame = frame

    @classmethod
    def create_initial(cls) -> PipelineState:
        """Factory method to create initial pipeline state.

        Returns:
            Fresh PipelineState with all defaults.
        """
        return cls(
            zone_states={},
            voters={},
            last_preview_write_ts=0.0,
            last_no_zone_warning_ts=0.0,
            prev_frame=None,
        )
