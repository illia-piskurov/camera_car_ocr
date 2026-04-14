from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import api_server


def test_dashboard_mode_payload_keeps_frontend_compatibility(monkeypatch) -> None:
    fixed_now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)

    class CfgStub:
        dry_run_open = True
        barrier_action_mode = "mock"
        barrier_close_delay_sec = 5.0
        ocr_open_threshold = 0.92
        ocr_extend_threshold = 0.80
        two_shot_gap_ms = 200
        two_shot_max_pairs = 2
        onec_sync_interval_hours = 24.0

        @staticmethod
        def is_barrier_live_configured() -> bool:
            return False

        @staticmethod
        def has_zone_barrier_entities(zone_id: int) -> bool:
            return zone_id == 1

        @staticmethod
        def get_zone_close_delay_sec(zone_id: int | None) -> float:
            return 5.0 if zone_id in {1, 2} else 5.0

    class DbStub:
        @staticmethod
        def get_decision_counts_since(_since):
            return {"open": 3, "deny": 1, "observed": 7}

        @staticmethod
        def get_whitelist_counts():
            return {"active": 10, "inactive": 2}

        @staticmethod
        def get_last_sync_at():
            return fixed_now - timedelta(hours=1)

        @staticmethod
        def get_recent_events(limit: int = 20):
            assert limit == 20
            return []

        @staticmethod
        def is_sync_due(_hours: float) -> bool:
            return False

    monkeypatch.setattr(api_server, "utc_now", lambda: fixed_now)
    monkeypatch.setattr(api_server, "cfg", CfgStub())
    monkeypatch.setattr(api_server, "db", DbStub())
    monkeypatch.setattr(api_server, "provider", SimpleNamespace(source="stub"))

    payload = api_server.dashboard()
    mode = payload["mode"]

    expected_keys = {
        "dry_run_open",
        "barrier_action_mode",
        "barrier_close_delay_sec",
        "barrier_live_configured",
        "zone1_barrier_configured",
        "zone2_barrier_configured",
        "zone1_close_delay_sec",
        "zone2_close_delay_sec",
        "ocr_open_threshold",
        "ocr_extend_threshold",
        "two_shot_gap_ms",
        "two_shot_max_pairs",
        "min_confirmations",
        "min_avg_confidence",
        "voting_window_sec",
    }
    assert expected_keys.issubset(mode.keys())

    assert mode["ocr_open_threshold"] == 0.92
    assert mode["ocr_extend_threshold"] == 0.80
    assert mode["two_shot_gap_ms"] == 200
    assert mode["two_shot_max_pairs"] == 2

    # Legacy frontend compatibility fields
    assert mode["min_confirmations"] == 2
    assert mode["min_avg_confidence"] == mode["ocr_open_threshold"]
    assert mode["voting_window_sec"] == mode["two_shot_gap_ms"] / 1000.0
