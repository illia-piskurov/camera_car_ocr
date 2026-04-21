from __future__ import annotations

from typing import Any, TypedDict

import cv2
import numpy as np


class ZonePayload(TypedDict):
    id: int
    name: str
    ha_open_entity_id: str
    ha_close_entity_id: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    is_enabled: bool
    sort_order: int


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def sanitize_zone(raw: dict[str, object], default_name: str) -> dict[str, object]:
    x0 = _clamp_01(_as_float(raw.get("x_min", 0.0), 0.0))
    y0 = _clamp_01(_as_float(raw.get("y_min", 0.0), 0.0))
    x1 = _clamp_01(_as_float(raw.get("x_max", 1.0), 1.0))
    y1 = _clamp_01(_as_float(raw.get("y_max", 1.0), 1.0))

    x_min = min(x0, x1)
    x_max = max(x0, x1)
    y_min = min(y0, y1)
    y_max = max(y0, y1)

    min_span = 0.01
    if x_max - x_min < min_span:
        x_max = min(1.0, x_min + min_span)
    if y_max - y_min < min_span:
        y_max = min(1.0, y_min + min_span)

    return {
        "name": str(raw.get("name") or default_name),
        "ha_open_entity_id": str(raw.get("ha_open_entity_id") or raw.get("open_entity_id") or ""),
        "ha_close_entity_id": str(raw.get("ha_close_entity_id") or raw.get("close_entity_id") or ""),
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "is_enabled": bool(raw.get("is_enabled", True)),
        "sort_order": _as_int(raw.get("sort_order", 0), 0),
    }


def zone_to_pixels(zone: dict[str, object], frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
    x_min = _clamp_01(_as_float(zone.get("x_min", 0.0), 0.0))
    y_min = _clamp_01(_as_float(zone.get("y_min", 0.0), 0.0))
    x_max = _clamp_01(_as_float(zone.get("x_max", 1.0), 1.0))
    y_max = _clamp_01(_as_float(zone.get("y_max", 1.0), 1.0))

    left = int(round(min(x_min, x_max) * frame_width))
    top = int(round(min(y_min, y_max) * frame_height))
    right = int(round(max(x_min, x_max) * frame_width))
    bottom = int(round(max(y_min, y_max) * frame_height))

    left = max(0, min(frame_width - 1, left))
    top = max(0, min(frame_height - 1, top))
    right = max(left + 1, min(frame_width, right))
    bottom = max(top + 1, min(frame_height, bottom))

    return left, top, right, bottom


def crop_zone(frame: np.ndarray, zone: dict[str, object]) -> np.ndarray:
    h, w = frame.shape[:2]
    left, top, right, bottom = zone_to_pixels(zone, w, h)
    return frame[top:bottom, left:right]


def paste_zone_image(
    image: np.ndarray,
    zone: dict[str, object],
    zone_image: np.ndarray,
) -> np.ndarray:
    h, w = image.shape[:2]
    left, top, right, bottom = zone_to_pixels(zone, w, h)
    target_width = right - left
    target_height = bottom - top

    if zone_image.shape[1] != target_width or zone_image.shape[0] != target_height:
        zone_image = cv2.resize(zone_image, (target_width, target_height), interpolation=cv2.INTER_LINEAR)

    result = image.copy()
    result[top:bottom, left:right] = zone_image
    return result


def draw_zones(
    image: np.ndarray,
    zones: list[dict[str, object]],
    highlight_zone_id: int | None = None,
) -> np.ndarray:
    if not zones:
        return image

    h, w = image.shape[:2]
    result = image.copy()
    for idx, zone in enumerate(zones):
        if not bool(zone.get("is_enabled", True)):
            continue

        left, top, right, bottom = zone_to_pixels(zone, w, h)
        zone_id = _as_int(zone.get("id"), -1)
        if zone_id < 0:
            zone_id = None
        is_highlighted = highlight_zone_id is not None and zone_id == highlight_zone_id
        color = (0, 255, 255) if is_highlighted else (120, 120, 120)
        thickness = 3 if is_highlighted else 1
        cv2.rectangle(result, (left, top), (right, bottom), color, thickness)

        label = str(zone.get("name") or f"Zone {idx + 1}")
        cv2.putText(
            result,
            label,
            (left + 6, max(20, top + 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65 if is_highlighted else 0.55,
            color,
            2 if is_highlighted else 1,
            cv2.LINE_AA,
        )

    return result
