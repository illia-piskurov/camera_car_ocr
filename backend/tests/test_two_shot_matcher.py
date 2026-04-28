from __future__ import annotations

from app.orchestrator import _select_best_detection

from conftest import make_detection


def test_select_best_detection_returns_none_when_empty() -> None:
    result = _select_best_detection(
        detections=[],
        min_ocr_confidence=0.92,
    )
    assert result is None


def test_select_best_detection_returns_none_when_below_threshold() -> None:
    detections = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.85)]

    result = _select_best_detection(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert result is None


def test_select_best_detection_selects_highest_confidence() -> None:
    detections = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.95),
        make_detection(plate="BB2222BB", zone_id=2, ocr=0.98),
        make_detection(plate="CC3333CC", zone_id=1, ocr=0.93),
    ]

    result = _select_best_detection(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert result is not None
    assert result.normalized_text == "BB2222BB"
    assert result.ocr_confidence == 0.98


def test_select_best_detection_single_qualified() -> None:
    detections = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.95),
        make_detection(plate="BB2222BB", zone_id=2, ocr=0.85),
    ]

    result = _select_best_detection(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert result is not None
    assert result.normalized_text == "AA1111AA"
    assert result.ocr_confidence == 0.95
