from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import api_server
from app.db import Database


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    database.init()
    return database


@pytest.fixture
def test_camera(test_db):
    return test_db.create_camera(
        name="Test Camera",
        snapshot_url="http://test.local/snapshot",
        username="admin",
        password="password",
        auth_mode="http_basic",
        encryption_key="test-camera-encryption-key",
        is_active=True,
        sort_order=0,
    )


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


def test_update_camera_preserves_credentials_and_skips_validation(monkeypatch, test_db, test_camera) -> None:
    camera_id = test_camera["id"]

    def fail_validation(*_args, **_kwargs):
        raise AssertionError("validate_camera should not be called for metadata-only edits")

    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(get_camera_credentials_encryption_key=lambda: "test-camera-encryption-key"))
    monkeypatch.setattr(api_server, "validate_camera", fail_validation)

    result = api_server.update_camera(
        camera_id,
        api_server.CameraUpdateInput(
            name="Updated Gate",
            is_active=False,
            sort_order=7,
        ),
    )

    assert result["status"] == "ok"
    assert result["camera"]["name"] == "Updated Gate"
    assert result["camera"]["is_active"] is False
    assert result["camera"]["sort_order"] == 7

    credentials = test_db.get_camera_credentials(camera_id, "test-camera-encryption-key")
    assert credentials == ("admin", "password", "http_basic")


def test_update_camera_returns_404_for_missing_camera(monkeypatch, test_db) -> None:
    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", SimpleNamespace(get_camera_credentials_encryption_key=lambda: "test-camera-encryption-key"))

    with pytest.raises(api_server.HTTPException) as exc_info:
        api_server.update_camera(9999, api_server.CameraUpdateInput(name="Missing"))

    assert exc_info.value.status_code == 404


def test_delete_camera_returns_404_for_missing_camera(monkeypatch, test_db) -> None:
    monkeypatch.setattr(api_server, "db", test_db)

    with pytest.raises(api_server.HTTPException) as exc_info:
        api_server.delete_camera(9999)

    assert exc_info.value.status_code == 404
