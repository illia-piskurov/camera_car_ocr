from __future__ import annotations
# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
from fast_alpr import ALPR

from .normalization import normalize_plate
from .types import PlateDetection


class AlprService:
    def __init__(self, detector_model: str, ocr_model: str) -> None:
        self.alpr: Any = ALPR(detector_model=detector_model, ocr_model=ocr_model)  # type: ignore[arg-type]

    def draw_predictions(self, frame: np.ndarray) -> tuple[np.ndarray, list[str]]:
        drawn: Any = self.alpr.draw_predictions(frame)
        annotated = getattr(drawn, "image", frame)
        raw_results: list[Any] = list(getattr(drawn, "results", []) or [])

        plates: list[str] = []
        for item in raw_results:
            ocr_obj = getattr(item, "ocr", None)
            raw_text = (getattr(ocr_obj, "text", "") or "").strip()
            if not raw_text:
                continue

            plate = normalize_plate(raw_text)
            if plate.normalized:
                plates.append(plate.normalized)
            else:
                plates.append(raw_text)

        return annotated, plates

    def detect(self, frame: np.ndarray, detected_at: datetime | None = None) -> list[PlateDetection]:
        when = detected_at or datetime.now(timezone.utc)
        frame_id = uuid4().hex
        results: list[Any] = self.alpr.predict(frame)
        detections: list[PlateDetection] = []

        for item in results:
            ocr_obj = getattr(item, "ocr", None)
            raw_text = (getattr(ocr_obj, "text", "") or "").strip()
            if not raw_text:
                continue

            plate = normalize_plate(raw_text)
            if not plate.normalized:
                continue

            ocr_conf = 0.0
            conf_obj = getattr(ocr_obj, "confidence", None)
            if isinstance(conf_obj, list) and conf_obj:
                ocr_conf = sum(float(v) for v in conf_obj) / len(conf_obj)
            elif isinstance(conf_obj, (float, int)):
                ocr_conf = float(conf_obj)

            detections.append(
                PlateDetection(
                    frame_id=frame_id,
                    detected_at=when,
                    raw_text=raw_text,
                    normalized_text=plate.normalized,
                    fuzzy_text=plate.fuzzy,
                    detection_confidence=float(getattr(getattr(item, "detection", None), "confidence", 0.0)),
                    ocr_confidence=float(ocr_conf),
                )
            )

        return detections
