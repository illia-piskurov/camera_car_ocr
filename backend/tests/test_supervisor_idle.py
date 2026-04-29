from __future__ import annotations

from types import SimpleNamespace

from app import orchestrator


def test_supervisor_idles_when_no_cameras(monkeypatch) -> None:
    spawned: list[list[str]] = []

    class DbStub:
        @staticmethod
        def init():
            return

        @staticmethod
        def is_sync_due(_hours: float) -> bool:
            return False

        @staticmethod
        def list_cameras(is_active: bool = True):
            _ = is_active
            return []

    monkeypatch.setattr(orchestrator.Database, "__new__", lambda *args, **kwargs: DbStub())
    monkeypatch.setattr(orchestrator, "create_whitelist_provider", lambda cfg: SimpleNamespace(source="stub"))
    monkeypatch.setattr(orchestrator.subprocess, "Popen", lambda command: spawned.append(command))

    sleep_calls = {"count": 0}

    def fake_sleep(_seconds: float) -> None:
        sleep_calls["count"] += 1
        raise KeyboardInterrupt()

    monkeypatch.setattr(orchestrator.time, "sleep", fake_sleep)

    orchestrator.run(settings=SimpleNamespace(db_path=":memory:", onec_sync_interval_hours=24.0, poll_interval_sec=0.1, log_file_path=None))

    assert spawned == []
    assert sleep_calls["count"] == 1
