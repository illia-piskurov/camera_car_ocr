from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app import orchestrator


def test_run_uses_same_frame_id_for_two_shot_cycle(monkeypatch) -> None:
    detect_calls: list[str] = []

    class CameraStub:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_frame(self):
            self.calls += 1
            if self.calls <= 2:
                return np.zeros((8, 8, 3), dtype=np.uint8)
            return np.zeros((8, 8, 3), dtype=np.uint8)

        def close(self) -> None:
            return

    class DbStub:
        @staticmethod
        def is_sync_due(_hours: float) -> bool:
            return False

        @staticmethod
        def get_zones(include_disabled: bool = False):
            _ = include_disabled
            return [
                {
                    "id": 1,
                    "name": "Zone 1",
                    "x_min": 0.0,
                    "y_min": 0.0,
                    "x_max": 1.0,
                    "y_max": 1.0,
                    "is_enabled": True,
                    "sort_order": 0,
                }
            ]

    class BarrierStub:
        @staticmethod
        def close(reason: str, plate: str | None, zone_id: int | None = None) -> bool:
            _ = (reason, plate, zone_id)
            return True

    cfg = SimpleNamespace(
        onec_sync_interval_hours=24.0,
        dry_run_open=True,
        barrier_action_mode="mock",
        poll_interval_sec=0.4,
        detection_zones_max=2,
        motion_detection_enabled=False,
        motion_threshold_percent=0.05,
        motion_blur_kernel=5,
        two_shot_max_pairs=1,
        two_shot_gap_ms=0,
        ocr_open_threshold=0.92,
    )

    camera = CameraStub()
    db = DbStub()
    barrier = BarrierStub()

    monkeypatch.setattr(
        orchestrator,
        "_initialize_pipeline",
        lambda _cfg: (camera, SimpleNamespace(), barrier, db, SimpleNamespace(source="stub")),
    )

    def fake_detect_in_zones(*, frame, alpr, detected_at, frame_id, active_zones):
        _ = (frame, alpr, detected_at, active_zones)
        detect_calls.append(frame_id)
        return [], {}

    monkeypatch.setattr(orchestrator, "_detect_in_zones", fake_detect_in_zones)
    monkeypatch.setattr(
        orchestrator,
        "_handle_detections",
        lambda **kwargs: orchestrator.DetectionStageResult(
            frame_last_decision=None,
            frame_last_plate=None,
            frame_last_reason=None,
            frame_last_zone=None,
            snapshot_source_detection=None,
        ),
    )
    monkeypatch.setattr(orchestrator, "_refresh_zone_hold", lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, "_snapshot_stage", lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, "_preview_stage", lambda **kwargs: None)

    sleep_calls = {"count": 0}

    def fake_sleep(_seconds: float) -> None:
        sleep_calls["count"] += 1
        # First sleep is intra two-shot gap; second sleep is end-of-loop pause.
        if sleep_calls["count"] >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr(orchestrator.time, "sleep", fake_sleep)

    orchestrator.run(settings=cfg)

    assert len(detect_calls) == 2
    assert detect_calls[0] == detect_calls[1]
