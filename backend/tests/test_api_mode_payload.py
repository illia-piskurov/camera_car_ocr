from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import api_server


def test_dashboard_mode_payload_exposes_single_shot_only(monkeypatch) -> None:
    fixed_now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)

    class CfgStub:
        dry_run_open = True
        barrier_action_mode = "mock"
        barrier_close_delay_sec = 5.0
        ocr_open_threshold = 0.92
        ocr_extend_threshold = 0.80
        onec_sync_interval_hours = 24.0

        @staticmethod
        def is_ha_configured() -> bool:
            return False

    class DbStub:
        @staticmethod
        def get_camera(camera_id: int):
            if camera_id == 7:
                return {"id": 7, "name": "Gate Camera"}
            return None

        @staticmethod
        def get_decision_counts_since(_since, camera_id: int | None = None):
            assert camera_id == 7
            return {"open": 3, "deny": 1, "observed": 7}

        @staticmethod
        def get_whitelist_counts():
            return {"active": 10, "inactive": 2}

        @staticmethod
        def get_last_sync_at():
            return fixed_now - timedelta(hours=1)

        @staticmethod
        def get_recent_events(limit: int = 20, camera_id: int | None = None):
            assert limit == 20
            assert camera_id == 7
            return []

        @staticmethod
        def get_zones(include_disabled: bool = True, camera_id: int | None = None):
            return []

        @staticmethod
        def is_sync_due(_hours: float) -> bool:
            return False

    monkeypatch.setattr(api_server, "utc_now", lambda: fixed_now)
    monkeypatch.setattr(api_server, "cfg", CfgStub())
    monkeypatch.setattr(api_server, "db", DbStub())
    monkeypatch.setattr(api_server, "provider", SimpleNamespace(source="stub"))

    payload = api_server.camera_dashboard(7)
    mode = payload["mode"]

    expected_keys = {
        "dry_run_open",
        "barrier_action_mode",
        "barrier_close_delay_sec",
        "barrier_live_configured",
        "ocr_open_threshold",
        "ocr_extend_threshold",
        "decision_model_version",
        "legacy_config_deprecated",
    }
    assert expected_keys.issubset(mode.keys())
    assert mode.keys() == expected_keys

    assert mode["ocr_open_threshold"] == 0.92
    assert mode["ocr_extend_threshold"] == 0.80
    assert mode["decision_model_version"] == "single-shot-v1"
    assert mode["legacy_config_deprecated"] is False
    assert mode["barrier_live_configured"] is False
    assert "zone1_barrier_configured" not in mode
    assert "zone2_barrier_configured" not in mode
    assert "zone1_close_delay_sec" not in mode
    assert "zone2_close_delay_sec" not in mode
    assert "two_shot_gap_ms" not in mode
    assert "two_shot_max_pairs" not in mode
