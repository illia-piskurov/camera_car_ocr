from __future__ import annotations

from app.orchestrator import _select_best_detection, _select_best_per_zone

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


def test_select_best_per_zone_returns_a_winner_for_each_qualifying_zone() -> None:
    """Two vehicles present in two different zones in the same frame must each get
    their own winning detection — not have one zone's detection crowd out the other."""
    detections = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.99),
        make_detection(plate="BB2222BB", zone_id=2, ocr=0.93),
    ]

    result = _select_best_per_zone(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert set(result.keys()) == {1, 2}
    assert result[1].normalized_text == "AA1111AA"
    assert result[2].normalized_text == "BB2222BB"


def test_select_best_per_zone_picks_highest_confidence_within_each_zone() -> None:
    detections = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.95),
        make_detection(plate="CC3333CC", zone_id=1, ocr=0.98),
        make_detection(plate="BB2222BB", zone_id=2, ocr=0.93),
    ]

    result = _select_best_per_zone(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert result[1].normalized_text == "CC3333CC"
    assert result[2].normalized_text == "BB2222BB"


def test_select_best_per_zone_omits_zones_below_threshold() -> None:
    detections = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.99),
        make_detection(plate="BB2222BB", zone_id=2, ocr=0.50),
    ]

    result = _select_best_per_zone(
        detections=detections,
        min_ocr_confidence=0.92,
    )

    assert set(result.keys()) == {1}


def test_select_best_per_zone_empty_when_no_detections() -> None:
    assert _select_best_per_zone(detections=[], min_ocr_confidence=0.92) == {}
