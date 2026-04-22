from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import api_server, config as config_module
from app.db import Database


@pytest.fixture
def test_db(tmp_path):
    """Create a test database in temporary directory."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    database.init()
    return database


@pytest.fixture
def test_config():
    """Create test configuration."""
    return config_module.Settings(
        db_path=":memory:",
        detection_zones_max=2,
        barrier_close_delay_sec=3,
    )


@pytest.fixture
def test_camera(test_db):
    """Create a test camera in the database."""
    result = test_db.create_camera(
        name="Test Camera",
        snapshot_url="http://test.local/snapshot",
        username="admin",
        password="password",
        auth_mode="http_basic",
        encryption_key="test-camera-encryption-key",
        is_active=True,
        sort_order=0,
    )
    return result


def test_camera_dashboard_returns_camera_scoped_data(monkeypatch, test_db, test_config, test_camera) -> None:
    """Verify that camera dashboard endpoint returns data scoped to the camera."""
    camera_id = test_camera["id"]

    # Create events for this camera
    test_db.record_event(
        occurred_at=datetime.now(timezone.utc),
        frame_id="frame1",
        raw_plate="ABC123",
        plate="ABC123",
        fuzzy_plate="ABC123",
        detection_confidence=0.95,
        ocr_confidence=0.95,
        decision="open",
        reason_code="open_approved",
        zone_id=1,
        zone_name="Zone 1",
        camera_id=camera_id,
    )

    # Mock the global db and cfg
    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", test_config)
    monkeypatch.setattr(api_server, "provider", SimpleNamespace(source="test"))

    # Call the endpoint
    result = api_server.camera_dashboard(camera_id)

    # Verify response structure and camera info
    assert result["camera"]["id"] == camera_id
    assert result["camera"]["name"] == "Test Camera"
    assert "recent_events" in result
    assert "kpi_24h" in result
    assert len(result["recent_events"]) == 1
    assert result["recent_events"][0]["plate"] == "ABC123"
    assert result["kpi_24h"]["open"] == 1


def test_camera_dashboard_returns_404_for_missing_camera(monkeypatch, test_db, test_config) -> None:
    """Verify that camera dashboard returns 404 for non-existent camera."""
    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", test_config)

    with pytest.raises(api_server.HTTPException) as exc_info:
        api_server.camera_dashboard(9999)

    assert exc_info.value.status_code == 404


def test_camera_zones_returns_camera_scoped_zones(monkeypatch, test_db, test_config, test_camera) -> None:
    """Verify that camera zones endpoint returns zones for the camera."""
    camera_id = test_camera["id"]

    # Create zones for this camera
    test_db.replace_zones(
        [
            {
                "name": "Zone 1",
                "x_min": 0.0,
                "y_min": 0.0,
                "x_max": 0.5,
                "y_max": 1.0,
                "is_enabled": True,
                "sort_order": 0,
            },
            {
                "name": "Zone 2",
                "x_min": 0.5,
                "y_min": 0.0,
                "x_max": 1.0,
                "y_max": 1.0,
                "is_enabled": True,
                "sort_order": 1,
            },
        ],
        camera_id=camera_id,
        max_zones=2,
    )

    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", test_config)

    result = api_server.get_camera_zones(camera_id)

    assert result["max_zones"] == 2
    assert len(result["zones"]) == 2
    assert all(zone["camera_id"] == camera_id for zone in result["zones"])


def test_camera_zones_returns_404_for_missing_camera(monkeypatch, test_db, test_config) -> None:
    """Verify that camera zones returns 404 for non-existent camera."""
    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", test_config)

    with pytest.raises(api_server.HTTPException) as exc_info:
        api_server.get_camera_zones(9999)

    assert exc_info.value.status_code == 404


def test_put_camera_zones_saves_zones_for_camera(monkeypatch, test_db, test_config, test_camera) -> None:
    """Verify that put camera zones endpoint saves zones for the specific camera."""
    camera_id = test_camera["id"]

    payload = api_server.ZonesPayload(
        zones=[
            api_server.ZoneInput(
                name="Test Zone 1",
                x_min=0.1,
                y_min=0.1,
                x_max=0.5,
                y_max=0.5,
                is_enabled=True,
                sort_order=0,
                ha_open_entity_id="cover.zone1_open",
                ha_close_entity_id="cover.zone1_close",
            )
        ]
    )

    monkeypatch.setattr(api_server, "db", test_db)
    monkeypatch.setattr(api_server, "cfg", test_config)

    result = api_server.put_camera_zones(camera_id, payload)

    assert result["status"] == "ok"
    assert len(result["zones"]) == 1
    assert result["zones"][0]["name"] == "Test Zone 1"
    assert result["zones"][0]["ha_open_entity_id"] == "cover.zone1_open"
    assert result["zones"][0]["ha_close_entity_id"] == "cover.zone1_close"


def test_global_and_camera_zones_are_independent(test_db, test_config) -> None:
    """Verify that zones for one camera don't affect global zones."""
    camera = test_db.create_camera(
        name="Camera 1",
        snapshot_url="http://test.local/snapshot",
        username="admin",
        password="password",
        auth_mode="http_basic",
        encryption_key="test-camera-encryption-key",
    )
    camera_id = camera["id"]

    # Create global zones (camera_id = None)
    global_zones = test_db.replace_zones(
        [{"name": "Global Zone", "x_min": 0.0, "y_min": 0.0, "x_max": 1.0, "y_max": 1.0, "is_enabled": True, "sort_order": 0}],
        camera_id=None,
        max_zones=2,
    )

    # Create camera-specific zones
    camera_zones = test_db.replace_zones(
        [{"name": "Camera Zone", "x_min": 0.1, "y_min": 0.1, "x_max": 0.9, "y_max": 0.9, "is_enabled": True, "sort_order": 0}],
        camera_id=camera_id,
        max_zones=2,
    )

    # Verify they are separate
    assert len(global_zones) == 1
    assert global_zones[0]["name"] == "Global Zone"
    assert global_zones[0]["camera_id"] is None

    assert len(camera_zones) == 1
    assert camera_zones[0]["name"] == "Camera Zone"
    assert camera_zones[0]["camera_id"] == camera_id

    # Verify get_zones with and without camera_id returns separate results
    all_global = test_db.get_zones(include_disabled=True, camera_id=None)
    all_camera = test_db.get_zones(include_disabled=True, camera_id=camera_id)

    assert len(all_global) == 1
    assert all_global[0]["name"] == "Global Zone"
    assert len(all_camera) == 1
    assert all_camera[0]["name"] == "Camera Zone"
