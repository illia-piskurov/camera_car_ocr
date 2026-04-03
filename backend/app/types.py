from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PlateDetection:
    frame_id: str
    detected_at: datetime
    raw_text: str
    normalized_text: str
    fuzzy_text: str
    detection_confidence: float
    ocr_confidence: float
    zone_id: int | None = None
    zone_name: str | None = None

    @property
    def combined_confidence(self) -> float:
        return (self.detection_confidence + self.ocr_confidence) / 2.0


@dataclass(frozen=True)
class VoteOutcome:
    plate: str
    fuzzy_plate: str
    confirmations: int
    avg_confidence: float
    window_sec: float


@dataclass(frozen=True)
class DecisionResult:
    should_open: bool
    reason_code: str
