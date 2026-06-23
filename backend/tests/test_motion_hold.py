from __future__ import annotations

import numpy as np
import pytest

from app.orchestrator import _refresh_zone_hold_motion
from app.pipeline_state import PipelineState
from app.runtime_state import ZoneRuntimeState


class MotionCfg:
    motion_hold_threshold = 0.02

    @staticmethod
    def get_zone_close_delay_sec(zone_id: int | None) -> float:
        return 5.0


ZONE = {"x_min": 0.0, "y_min": 0.0, "x_max": 1.0, "y_max": 1.0}


def _black_frame(h: int = 64, w: int = 64) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _noisy_frame(h: int = 64, w: int = 64, noise: int = 60) -> np.ndarray:
    frame = np.full((h, w, 3), noise, dtype=np.uint8)
    frame[16:48, 16:48] = 180
    return frame


def test_motion_extends_deadline() -> None:
    state = PipelineState.create_initial()
    state.zone_states[1] = ZoneRuntimeState(close_deadline_monotonic=10.0, last_plate="AA1111AA")

    _refresh_zone_hold_motion(
        prev_frame=_black_frame(),
        curr_frame=_noisy_frame(),
        active_zones_by_id={1: ZONE},
        cfg=MotionCfg(),
        state=state,
        now_monotonic=100.0,
    )

    # deadline should be refreshed to now + close_delay = 105.0
    assert state.zone_states[1].close_deadline_monotonic == pytest.approx(105.0)


def test_no_motion_does_not_extend_deadline() -> None:
    state = PipelineState.create_initial()
    state.zone_states[1] = ZoneRuntimeState(close_deadline_monotonic=10.0, last_plate="AA1111AA")

    identical = _black_frame()
    _refresh_zone_hold_motion(
        prev_frame=identical,
        curr_frame=identical.copy(),
        active_zones_by_id={1: ZONE},
        cfg=MotionCfg(),
        state=state,
        now_monotonic=100.0,
    )

    # deadline unchanged
    assert state.zone_states[1].close_deadline_monotonic == 10.0


def test_motion_ignored_when_zone_not_open() -> None:
    state = PipelineState.create_initial()
    state.zone_states[1] = ZoneRuntimeState()  # not open

    _refresh_zone_hold_motion(
        prev_frame=_black_frame(),
        curr_frame=_noisy_frame(),
        active_zones_by_id={1: ZONE},
        cfg=MotionCfg(),
        state=state,
        now_monotonic=100.0,
    )

    assert not state.zone_states[1].is_open


def test_motion_ignored_for_unknown_zone() -> None:
    state = PipelineState.create_initial()
    state.zone_states[2] = ZoneRuntimeState(close_deadline_monotonic=10.0, last_plate="AA1111AA")

    _refresh_zone_hold_motion(
        prev_frame=_black_frame(),
        curr_frame=_noisy_frame(),
        active_zones_by_id={1: ZONE},  # zone 2 not in active_zones_by_id
        cfg=MotionCfg(),
        state=state,
        now_monotonic=100.0,
    )

    assert state.zone_states[2].close_deadline_monotonic == 10.0
