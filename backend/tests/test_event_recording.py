from __future__ import annotations

from unittest.mock import Mock

from app.stages import record_decision_event

from conftest import make_detection


def test_record_decision_event_writes_expected_payload_with_empty_vote_fields() -> None:
    detection = make_detection(plate="AA1111AA", zone_id=2, ocr=0.94, det=0.37)
    db = Mock()

    record_decision_event(
        detection=detection,
        decision="observed",
        reason_code="raw_detection",
        db=db,
    )

    db.record_event.assert_called_once()
    kwargs = db.record_event.call_args.kwargs

    assert kwargs["occurred_at"] == detection.detected_at
    assert kwargs["frame_id"] == detection.frame_id
    assert kwargs["raw_plate"] == detection.raw_text
    assert kwargs["plate"] == detection.normalized_text
    assert kwargs["fuzzy_plate"] == detection.fuzzy_text
    assert kwargs["detection_confidence"] == detection.detection_confidence
    assert kwargs["ocr_confidence"] == detection.ocr_confidence
    assert kwargs["vote_confirmations"] is None
    assert kwargs["vote_avg_confidence"] is None
    assert kwargs["zone_id"] == detection.zone_id
    assert kwargs["zone_name"] == detection.zone_name
    assert kwargs["decision"] == "observed"
    assert kwargs["reason_code"] == "raw_detection"
