from __future__ import annotations

from app.orchestrator import _select_two_shot_candidate

from conftest import make_detection


def test_two_shot_returns_none_when_no_plate_match() -> None:
    first = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.97)]
    second = [make_detection(plate="BB2222BB", zone_id=1, ocr=0.98)]

    result = _select_two_shot_candidate(
        first=first,
        second=second,
        min_ocr_confidence=0.92,
    )

    assert result is None


def test_two_shot_requires_threshold_on_both_shots() -> None:
    first = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.95)]
    second = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.85)]

    result = _select_two_shot_candidate(
        first=first,
        second=second,
        min_ocr_confidence=0.92,
    )

    assert result is None


def test_two_shot_matches_same_plate_in_same_zone() -> None:
    first = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.95)]
    second = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.96)]

    result = _select_two_shot_candidate(
        first=first,
        second=second,
        min_ocr_confidence=0.92,
    )

    assert result is not None
    assert result.normalized_text == "AA1111AA"
    assert result.zone_id == 1


def test_two_shot_does_not_match_same_plate_across_different_zones() -> None:
    first = [make_detection(plate="AA1111AA", zone_id=1, ocr=0.96)]
    second = [make_detection(plate="AA1111AA", zone_id=2, ocr=0.97)]

    result = _select_two_shot_candidate(
        first=first,
        second=second,
        min_ocr_confidence=0.92,
    )

    assert result is None


def test_two_shot_prefers_highest_pair_score_candidate() -> None:
    first = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.96),
        make_detection(plate="CC3333CC", zone_id=1, ocr=0.98),
    ]
    second = [
        make_detection(plate="AA1111AA", zone_id=1, ocr=0.96),
        make_detection(plate="CC3333CC", zone_id=1, ocr=0.93),
    ]

    result = _select_two_shot_candidate(
        first=first,
        second=second,
        min_ocr_confidence=0.92,
    )

    assert result is not None
    assert result.normalized_text == "AA1111AA"
