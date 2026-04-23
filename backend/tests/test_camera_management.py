from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import api_server


def test_validate_camera_accepts_live_snapshot(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def probe_frame(self):
            return object(), None

    monkeypatch.setattr(api_server, "SnapshotCameraClient", FakeClient)
    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(request_timeout_sec=1.0, request_retries=0))

    result = api_server.validate_camera(
        api_server.CameraInput(
            name="Gate 1",
            snapshot_url="http://camera/snapshot.jpg",
            username="admin",
            password="secret",
            auth_mode="digest",
        )
    )

    assert result == {"status": "ok", "available": True}


def test_validate_camera_rejects_invalid_snapshot(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def probe_frame(self):
            return None, "HTTP 401"

    monkeypatch.setattr(api_server, "SnapshotCameraClient", FakeClient)
    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(request_timeout_sec=1.0, request_retries=0))

    with pytest.raises(HTTPException) as exc_info:
        api_server.validate_camera(
            api_server.CameraInput(
                name="Gate 1",
                snapshot_url="http://camera/snapshot.jpg",
                username="admin",
                password="wrong",
                auth_mode="digest",
            )
        )

    assert exc_info.value.status_code == 400
    assert "Camera validation failed" in exc_info.value.detail


def test_put_zones_preserves_entity_ids(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    class DbStub:
        @staticmethod
        def replace_zones(zones: list[dict[str, object]], max_zones: int = 0) -> list[dict[str, object]]:
            recorded["zones"] = zones
            recorded["max_zones"] = max_zones
            return zones

    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(detection_zones_max=2))
    monkeypatch.setattr(api_server, "db", DbStub())

    payload = api_server.ZonesPayload(
        zones=[
            api_server.ZoneInput(
                id=1,
                name="North Gate",
                ha_open_entity_id="input_button.north_gate_open",
                ha_close_entity_id="input_button.north_gate_close",
                x_min=0.1,
                y_min=0.2,
                x_max=0.3,
                y_max=0.4,
            )
        ]
    )

    result = api_server.put_zones(payload)

    assert result["status"] == "ok"
    assert recorded["max_zones"] == 2
    assert recorded["zones"][0]["ha_open_entity_id"] == "input_button.north_gate_open"
    assert recorded["zones"][0]["ha_close_entity_id"] == "input_button.north_gate_close"
