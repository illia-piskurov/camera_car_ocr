from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.stages import evaluate_decision


def test_evaluate_decision_approved_for_whitelisted_plate() -> None:
    db = Mock()
    db.is_whitelisted.return_value = True
    db.is_cross_camera_suppressed.return_value = False
    cfg = SimpleNamespace(enable_fuzzy_match=True, fuzzy_edit_enabled=False)

    should_open, reason = evaluate_decision(
        plate="AA1111AA",
        fuzzy_plate="AA1111AA",
        db=db,
        cfg=cfg,
        ocr_confidence=0.95,
        camera_id=1,
    )

    assert should_open is True
    assert reason == "open_approved"
    db.is_whitelisted.assert_called_once_with(
        plate="AA1111AA",
        fuzzy_plate="AA1111AA",
        enable_fuzzy_match=True,
    )


def test_evaluate_decision_denied_for_non_whitelisted_plate() -> None:
    db = Mock()
    db.is_whitelisted.return_value = False
    cfg = SimpleNamespace(enable_fuzzy_match=False, fuzzy_edit_enabled=False)

    should_open, reason = evaluate_decision(
        plate="ZZ9999ZZ",
        fuzzy_plate="ZZ9999ZZ",
        db=db,
        cfg=cfg,
        ocr_confidence=0.95,
        camera_id=1,
    )

    assert should_open is False
    assert reason == "not_whitelisted"
    db.is_whitelisted.assert_called_once_with(
        plate="ZZ9999ZZ",
        fuzzy_plate="ZZ9999ZZ",
        enable_fuzzy_match=False,
    )
