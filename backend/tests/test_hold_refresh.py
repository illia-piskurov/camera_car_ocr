from __future__ import annotations

from app.orchestrator import _refresh_zone_hold
from app.pipeline_state import PipelineState
from app.runtime_state import ZoneRuntimeState

from conftest import make_detection


class HoldCfg:
    ocr_extend_threshold = 0.80

    @staticmethod
    def get_zone_close_delay_sec(zone_id: int | None) -> float:
        return 5.0


def test_refresh_zone_hold_extends_even_for_low_ocr_detection() -> None:
    state = PipelineState.create_initial()
    zone_state = ZoneRuntimeState(close_deadline_monotonic=10.0, last_plate="OLD")
    state.zone_states[1] = zone_state

    detection = make_detection(plate="AA1111AA", zone_id=1, ocr=0.79)

    _refresh_zone_hold(
        detections=[detection],
        cfg=HoldCfg(),
        state=state,
        now_monotonic=100.0,
    )

    assert zone_state.close_deadline_monotonic == 105.0
    assert zone_state.last_plate == "AA1111AA"
    assert zone_state.last_seen_monotonic == 100.0


def test_refresh_zone_hold_extends_deadline_and_updates_plate() -> None:
    state = PipelineState.create_initial()
    zone_state = ZoneRuntimeState(close_deadline_monotonic=10.0, last_plate="OLD")
    state.zone_states[1] = zone_state

    detection = make_detection(plate="AA1111AA", zone_id=1, ocr=0.92)

    _refresh_zone_hold(
        detections=[detection],
        cfg=HoldCfg(),
        state=state,
        now_monotonic=100.0,
    )

    assert zone_state.close_deadline_monotonic == 105.0
    assert zone_state.last_plate == "AA1111AA"
    assert zone_state.last_seen_monotonic == 100.0
