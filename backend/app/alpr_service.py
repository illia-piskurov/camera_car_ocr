from __future__ import annotations
# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false

from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import cv2
import numpy as np

from fast_alpr import ALPR

from .normalization import is_valid_ua_plate, normalize_plate
from .types import PlateDetection


class AlprService:
    def __init__(
        self,
        detector_model: str,
        ocr_model: str,
        detector_providers: Sequence[str | tuple[str, dict]] | None = None,
        ocr_providers: Sequence[str | tuple[str, dict]] | None = None,
    ) -> None:
        self.alpr: Any = ALPR(
            detector_model=detector_model,
            ocr_model=ocr_model,
            detector_providers=detector_providers,
            ocr_providers=ocr_providers,
        )  # type: ignore[arg-type]

    def draw_detections(self, frame: np.ndarray, detections: Sequence[PlateDetection]) -> np.ndarray:
        """Draw bounding boxes/labels for already-computed detections.

        Unlike the underlying fast_alpr.draw_predictions(), this does not re-run
        detector+OCR inference — it reuses bbox/text captured by detect() so a
        saved snapshot never pays for a second full inference pass.
        """
        annotated = frame.copy()
        for det in detections:
            if det.bbox is None:
                continue
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (36, 255, 12), 2)
            label = det.normalized_text or det.raw_text
            if label:
                cv2.putText(
                    annotated,
                    label,
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (36, 255, 12),
                    2,
                    cv2.LINE_AA,
                )
        return annotated

    def detect(
        self,
        frame: np.ndarray,
        detected_at: datetime | None = None,
        frame_id: str | None = None,
        zone_id: int | None = None,
        zone_name: str | None = None,
    ) -> list[PlateDetection]:
        when = detected_at or datetime.now(timezone.utc)
        effective_frame_id = frame_id or uuid4().hex
        results: list[Any] = self.alpr.predict(frame)
        detections: list[PlateDetection] = []

        for item in results:
            ocr_obj = getattr(item, "ocr", None)
            raw_text = (getattr(ocr_obj, "text", "") or "").strip()
            if not raw_text:
                continue

            plate = normalize_plate(raw_text)
            if not plate.normalized or not is_valid_ua_plate(plate.normalized):
                continue

            ocr_conf = 0.0
            conf_obj = getattr(ocr_obj, "confidence", None)
            if isinstance(conf_obj, list) and conf_obj:
                ocr_conf = sum(float(v) for v in conf_obj) / len(conf_obj)
            elif isinstance(conf_obj, (float, int)):
                ocr_conf = float(conf_obj)

            bbox_obj = getattr(getattr(item, "detection", None), "bounding_box", None)
            bbox: tuple[int, int, int, int] | None = None
            if bbox_obj is not None:
                bbox = (int(bbox_obj.x1), int(bbox_obj.y1), int(bbox_obj.x2), int(bbox_obj.y2))

            detections.append(
                PlateDetection(
                    frame_id=effective_frame_id,
                    detected_at=when,
                    raw_text=raw_text,
                    normalized_text=plate.normalized,
                    fuzzy_text=plate.fuzzy,
                    detection_confidence=float(getattr(getattr(item, "detection", None), "confidence", 0.0)),
                    ocr_confidence=float(ocr_conf),
                    zone_id=zone_id,
                    zone_name=zone_name,
                    bbox=bbox,
                )
            )

        return detections
