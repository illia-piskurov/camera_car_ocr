from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.types import PlateDetection


def make_detection(
    *,
    plate: str,
    zone_id: int | None = 1,
    ocr: float = 0.95,
    det: float = 0.40,
    frame_id: str = "frame-1",
    zone_name: str | None = "Zone 1",
) -> PlateDetection:
    return PlateDetection(
        frame_id=frame_id,
        detected_at=datetime.now(timezone.utc),
        raw_text=plate,
        normalized_text=plate,
        fuzzy_text=plate,
        detection_confidence=det,
        ocr_confidence=ocr,
        zone_id=zone_id,
        zone_name=zone_name,
    )
