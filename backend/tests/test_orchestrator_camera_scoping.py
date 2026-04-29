from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.config import Settings
from app.orchestrator import DetectionStageResult, FrameStageContext, _preview_stage, _process_frame
from app.pipeline_state import PipelineState
from app.types import PlateDetection


class DummyAlpr:
    def draw_predictions(self, frame):
        return frame, ["ABC123"]


def test_process_frame_uses_camera_specific_zones() -> None:
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    db_calls: list[dict[str, object]] = []

    class DummyDb:
        def get_zones(self, include_disabled: bool = False, camera_id: int | None = None):
            db_calls.append({"include_disabled": include_disabled, "camera_id": camera_id})
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

    cfg = Settings(preview_enabled=True)
    state = PipelineState.create_initial()

    result = _process_frame(
        frame=frame,
        prev_frame=None,
        camera_id=42,
        db=DummyDb(),
        cfg=cfg,
        state=state,
    )

    assert isinstance(result, FrameStageContext)
    assert db_calls == [{"include_disabled": False, "camera_id": 42}]


def test_preview_stage_writes_camera_specific_files(tmp_path) -> None:
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    cfg = Settings(
        preview_enabled=True,
        preview_image_path=str(tmp_path / "preview_latest.jpg"),
        preview_meta_path=str(tmp_path / "preview_meta.json"),
    )
    detection = PlateDetection(
        frame_id="frame-1",
        detected_at=datetime.now(timezone.utc),
        raw_text="ABC123",
        normalized_text="ABC123",
        fuzzy_text="ABC123",
        detection_confidence=0.95,
        ocr_confidence=0.96,
        zone_id=None,
        zone_name=None,
    )
    stage = FrameStageContext(
        now=datetime.now(timezone.utc),
        frame_id="frame-1",
        active_zones=[],
        active_zones_by_id={},
        skip_alpr_this_frame=False,
    )
    detection_result = DetectionStageResult(
        frame_last_decision="open",
        frame_last_plate="ABC123",
        frame_last_reason="open_approved",
        frame_last_zone=None,
        snapshot_source_detection=detection,
    )

    _preview_stage(
        cfg=cfg,
        camera_id=7,
        frame=frame,
        detections=[detection],
        detection_result=detection_result,
        stage=stage,
        state=PipelineState.create_initial(),
    )

    scoped_image = tmp_path / "preview_latest_camera_7.jpg"
    scoped_meta = tmp_path / "preview_meta_camera_7.json"

    assert scoped_image.exists()
    assert scoped_meta.exists()
    assert not (tmp_path / "preview_latest.jpg").exists()
    assert not (tmp_path / "preview_meta.json").exists()
