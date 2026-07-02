from __future__ import annotations

from types import SimpleNamespace

from app import orchestrator
from app.pipeline_state import PipelineState

from conftest import make_detection


def test_handle_detections_records_only_observed_without_decision(monkeypatch) -> None:
    recorded: list[tuple[str, str]] = []

    def fake_record_decision_event(*, detection, decision, reason_code, db, camera_id=None):
        recorded.append((decision, reason_code))

    def fail_evaluate_decision(**kwargs):
        raise AssertionError("evaluate_decision must not be called when decision_detection is None")

    monkeypatch.setattr(orchestrator.stages, "record_decision_event", fake_record_decision_event)
    monkeypatch.setattr(orchestrator.stages, "evaluate_decision", fail_evaluate_decision)

    detections = [
        make_detection(plate="AA1111AA", frame_id="f1"),
        make_detection(plate="BB2222BB", frame_id="f1"),
    ]

    result = orchestrator._handle_detections(
        detections=detections,
        decision_detections={},
        db=SimpleNamespace(),
        cfg=SimpleNamespace(),
        barrier=SimpleNamespace(),
        state=PipelineState.create_initial(),
    )

    assert result.frame_last_decision is None
    assert result.frame_last_plate is None
    assert len(recorded) == 2
    assert all(item == ("observed", "raw_detection") for item in recorded)


def test_handle_detections_records_final_open_and_calls_barrier(monkeypatch) -> None:
    recorded: list[tuple[str, str]] = []
    barrier_calls: list[tuple[bool, str, str]] = []

    def fake_record_decision_event(*, detection, decision, reason_code, db, camera_id=None):
        recorded.append((decision, reason_code))

    def fake_evaluate_decision(*, plate, fuzzy_plate, ocr_confidence, camera_id, zone_id, db, cfg):
        return True, "open_approved"

    def fake_execute_barrier_action(*, should_open, detection, reason_code, barrier, cfg, zone_states, barrier_state=None):
        barrier_calls.append((should_open, detection.normalized_text, reason_code))

    monkeypatch.setattr(orchestrator.stages, "record_decision_event", fake_record_decision_event)
    monkeypatch.setattr(orchestrator.stages, "evaluate_decision", fake_evaluate_decision)
    monkeypatch.setattr(orchestrator.stages, "execute_barrier_action", fake_execute_barrier_action)

    detections = [
        make_detection(plate="AA1111AA", frame_id="f1"),
        make_detection(plate="CC3333CC", frame_id="f1"),
    ]
    decision_detection = detections[0]

    result = orchestrator._handle_detections(
        detections=detections,
        decision_detections={decision_detection.zone_id: decision_detection},
        db=SimpleNamespace(),
        cfg=SimpleNamespace(),
        barrier=SimpleNamespace(),
        state=PipelineState.create_initial(),
    )

    assert result.frame_last_decision == "open"
    assert result.frame_last_plate == "AA1111AA"
    assert result.frame_last_reason == "open_approved"
    assert len(recorded) == 3
    assert recorded[-1] == ("open", "open_approved")
    assert barrier_calls == [(True, "AA1111AA", "open_approved")]


def test_handle_detections_processes_two_simultaneous_zones_independently(monkeypatch) -> None:
    """Regression test: two vehicles in two different detection zones on the same
    camera, in the same polling cycle, must each get their own open/deny decision
    and barrier action — one zone's vehicle must not block the other's decision."""
    recorded: list[tuple[int | None, str, str]] = []
    barrier_calls: list[tuple[int | None, bool, str]] = []

    def fake_record_decision_event(*, detection, decision, reason_code, db, camera_id=None):
        recorded.append((detection.zone_id, decision, reason_code))

    def fake_evaluate_decision(*, plate, fuzzy_plate, ocr_confidence, camera_id, zone_id, db, cfg):
        # Zone 1's plate is whitelisted, zone 2's plate is not.
        if zone_id == 1:
            return True, "open_approved"
        return False, "not_whitelisted"

    def fake_execute_barrier_action(*, should_open, detection, reason_code, barrier, cfg, zone_states, barrier_state=None):
        barrier_calls.append((detection.zone_id, should_open, reason_code))

    monkeypatch.setattr(orchestrator.stages, "record_decision_event", fake_record_decision_event)
    monkeypatch.setattr(orchestrator.stages, "evaluate_decision", fake_evaluate_decision)
    monkeypatch.setattr(orchestrator.stages, "execute_barrier_action", fake_execute_barrier_action)

    zone1_detection = make_detection(plate="AA1111AA", zone_id=1, frame_id="f1")
    zone2_detection = make_detection(plate="XX9999XX", zone_id=2, frame_id="f1")
    detections = [zone1_detection, zone2_detection]

    result = orchestrator._handle_detections(
        detections=detections,
        decision_detections={1: zone1_detection, 2: zone2_detection},
        db=SimpleNamespace(),
        cfg=SimpleNamespace(),
        barrier=SimpleNamespace(),
        state=PipelineState.create_initial(),
    )

    # Both zones must have recorded their own decision event (plus the 2 "observed" events).
    decision_events = {(zid, decision, reason) for zid, decision, reason in recorded if decision != "observed"}
    assert decision_events == {
        (1, "open", "open_approved"),
        (2, "deny", "not_whitelisted"),
    }

    # Both zones must have triggered a barrier-action call — zone 1 to actually open,
    # zone 2 as a no-op deny — instead of only the single "winning" zone getting one.
    assert set(barrier_calls) == {
        (1, True, "open_approved"),
        (2, False, "not_whitelisted"),
    }

    # The frame-level preview summary prefers surfacing the "open" outcome.
    assert result.frame_last_decision == "open"
    assert result.frame_last_plate == "AA1111AA"
