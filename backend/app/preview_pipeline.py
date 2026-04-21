from __future__ import annotations

import json
import os
import re
from datetime import datetime

import cv2

from .alpr_service import AlprService
from .zones import draw_zones


def write_preview_artifacts(
    *,
    image,
    image_path: str,
    meta_path: str,
    captured_at: datetime,
    has_detections: bool,
    last_plate: str | None,
    last_decision: str | None,
    jpeg_quality: int,
) -> None:
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)

    quality = max(40, min(100, int(jpeg_quality)))
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode preview image")

    with open(image_path, "wb") as image_file:
        image_file.write(encoded.tobytes())

    payload = {
        "captured_at": captured_at.isoformat(),
        "has_detections": has_detections,
        "last_plate": last_plate,
        "last_decision": last_decision,
    }
    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump(payload, meta_file, ensure_ascii=False)


def _safe_file_segment(value: str | None, fallback: str = "unknown") -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return cleaned if cleaned else fallback


def _prune_old_snapshots(directory: str, max_files: int) -> None:
    if max_files <= 0:
        return

    entries: list[tuple[float, str]] = []
    for name in os.listdir(directory):
        if not name.lower().endswith(".jpg"):
            continue
        path = os.path.join(directory, name)
        try:
            entries.append((os.path.getmtime(path), path))
        except OSError:
            continue

    if len(entries) <= max_files:
        return

    entries.sort(key=lambda item: item[0])
    for _, path in entries[: len(entries) - max_files]:
        try:
            os.remove(path)
        except OSError:
            continue


def write_recognition_snapshot(
    *,
    frame,
    alpr: AlprService,
    captured_at: datetime,
    frame_id: str,
    plate: str | None,
    decision: str | None,
    reason_code: str | None,
    zone_name: str | None,
    output_dir: str,
    jpeg_quality: int,
    max_files: int,
    zones: list[dict[str, object]] | None = None,
    highlight_zone_id: int | None = None,
    apply_alpr_predictions: bool = True,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    annotated = frame
    if apply_alpr_predictions:
        try:
            annotated, _ = alpr.draw_predictions(frame)
        except Exception:
            # Keep snapshot generation resilient even if prediction rendering fails.
            annotated = frame

    if zones is not None:
        annotated = draw_zones(annotated, zones, highlight_zone_id=highlight_zone_id)

    overlay = (
        f"{captured_at.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"plate={plate or '-'} | zone={zone_name or 'full'} | decision={decision} | reason={reason_code or '-'}"
    )
    cv2.putText(
        annotated,
        overlay,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    quality = max(40, min(100, int(jpeg_quality)))
    ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode recognition snapshot")

    timestamp = captured_at.strftime("%Y%m%d_%H%M%S_%f")
    frame_part = _safe_file_segment(frame_id, fallback="frame")
    plate_part = _safe_file_segment(plate)
    decision_part = _safe_file_segment(decision, fallback="observed")
    filename = f"{timestamp}_{frame_part}_{plate_part}_{decision_part}.jpg"
    out_path = os.path.join(output_dir, filename)

    with open(out_path, "wb") as out_file:
        out_file.write(encoded.tobytes())

    _prune_old_snapshots(output_dir, max_files=max_files)
