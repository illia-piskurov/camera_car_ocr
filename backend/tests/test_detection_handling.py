from __future__ import annotations

from types import SimpleNamespace

from app import orchestrator

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
        decision_detection=None,
        db=SimpleNamespace(),
        cfg=SimpleNamespace(),
        barrier=SimpleNamespace(),
        zone_states={},
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

    def fake_evaluate_decision(*, plate, fuzzy_plate, db, cfg):
        return True, "open_approved"

    def fake_execute_barrier_action(*, should_open, detection, reason_code, barrier, cfg, zone_states):
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
        decision_detection=decision_detection,
        db=SimpleNamespace(),
        cfg=SimpleNamespace(),
        barrier=SimpleNamespace(),
        zone_states={},
    )

    assert result.frame_last_decision == "open"
    assert result.frame_last_plate == "AA1111AA"
    assert result.frame_last_reason == "open_approved"
    assert len(recorded) == 3
    assert recorded[-1] == ("open", "open_approved")
    assert barrier_calls == [(True, "AA1111AA", "open_approved")]
