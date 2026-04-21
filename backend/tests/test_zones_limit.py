from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from fastapi import HTTPException

from app import api_server, orchestrator
from app.pipeline_state import PipelineState


def _make_zone(index: int) -> dict[str, object]:
    return {
        "id": index,
        "name": f"Zone {index}",
        "x_min": 0.0,
        "y_min": 0.0,
        "x_max": 1.0,
        "y_max": 1.0,
        "is_enabled": True,
        "sort_order": index - 1,
    }


def test_put_zones_rejects_more_than_two(monkeypatch) -> None:
    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(detection_zones_max=2))

    payload = api_server.ZonesPayload(
        zones=[
            api_server.ZoneInput(**_make_zone(1)),
            api_server.ZoneInput(**_make_zone(2)),
            api_server.ZoneInput(**_make_zone(3)),
        ]
    )

    try:
        api_server.put_zones(payload)
        raise AssertionError("Expected HTTPException for payload above zone limit")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Maximum 2 zones are allowed"


def test_put_zones_accepts_two_and_passes_limit_to_db(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    class DbStub:
        @staticmethod
        def replace_zones(zones: list[dict[str, object]], max_zones: int = 0) -> list[dict[str, object]]:
            recorded["zones_count"] = len(zones)
            recorded["max_zones"] = max_zones
            return zones

    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(detection_zones_max=2))
    monkeypatch.setattr(api_server, "db", DbStub())

    payload = api_server.ZonesPayload(
        zones=[
            api_server.ZoneInput(**_make_zone(1)),
            api_server.ZoneInput(**_make_zone(2)),
        ]
    )

    result = api_server.put_zones(payload)

    assert result["status"] == "ok"
    assert result["max_zones"] == 2
    assert recorded["zones_count"] == 2
    assert recorded["max_zones"] == 2


def test_process_frame_respects_configured_zone_limit() -> None:
    class DbStub:
        @staticmethod
        def get_zones(include_disabled: bool = False) -> list[dict[str, object]]:
            _ = include_disabled
            return [_make_zone(1), _make_zone(2), _make_zone(3)]

    cfg = SimpleNamespace(
        detection_zones_max=2,
        motion_detection_enabled=False,
        motion_threshold_percent=0.05,
        motion_blur_kernel=5,
    )

    context = orchestrator._process_frame(
        frame=np.zeros((8, 8, 3), dtype=np.uint8),
        prev_frame=None,
        db=DbStub(),
        cfg=cfg,
        state=PipelineState(),
    )

    assert context is not None
    assert len(context.active_zones) == 2
    assert [zone["id"] for zone in context.active_zones] == [1, 2]
