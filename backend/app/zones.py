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

    # Normalize rotation to [0, 360)
    rotation = _as_float(raw.get("rotation", 0.0), 0.0)
    rotation = rotation % 360.0

    result: dict[str, object] = {
        "name": str(raw.get("name") or default_name),
        "ha_open_entity_id": str(raw.get("ha_open_entity_id") or raw.get("open_entity_id") or ""),
        "ha_close_entity_id": str(raw.get("ha_close_entity_id") or raw.get("close_entity_id") or ""),
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "is_enabled": bool(raw.get("is_enabled", True)),
        "sort_order": _as_int(raw.get("sort_order", 0), 0),
        "rotation": rotation,
    }
    if "barrier_id" in raw:
        result["barrier_id"] = raw["barrier_id"]
    if "camera_id" in raw:
        result["camera_id"] = raw["camera_id"]
    if "zone_group_id" in raw:
        result["zone_group_id"] = raw["zone_group_id"]
    if "cross_camera_enabled" in raw:
        result["cross_camera_enabled"] = raw["cross_camera_enabled"]
    if "cross_zone_id" in raw:
        result["cross_zone_id"] = raw["cross_zone_id"]
    return result


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
    rotation = _as_float(zone.get("rotation", 0.0), 0.0)

    # If no rotation or not a barrier zone, use simple cropping
    if abs(rotation % 360.0) < 0.01 or str(zone.get("zone_type")) != "barrier_check":
        left, top, right, bottom = zone_to_pixels(zone, w, h)
        return frame[top:bottom, left:right]

    # For rotated barrier zones, rotate the image so the zone is axis-aligned
    x_min_norm = _clamp_01(_as_float(zone.get("x_min", 0.0), 0.0))
    y_min_norm = _clamp_01(_as_float(zone.get("y_min", 0.0), 0.0))
    x_max_norm = _clamp_01(_as_float(zone.get("x_max", 1.0), 1.0))
    y_max_norm = _clamp_01(_as_float(zone.get("y_max", 1.0), 1.0))

    # Ensure proper ordering
    x_min = min(x_min_norm, x_max_norm)
    x_max = max(x_min_norm, x_max_norm)
    y_min = min(y_min_norm, y_max_norm)
    y_max = max(y_min_norm, y_max_norm)

    # Zone center (in pixels)
    cx_px = int(round((x_min + x_max) / 2.0 * w))
    cy_px = int(round((y_min + y_max) / 2.0 * h))

    # Zone dimensions (in pixels)
    zone_w_px = int(round((x_max - x_min) * w))
    zone_h_px = int(round((y_max - y_min) * h))

    # Create a mask with the rotated rectangle
    mask = np.zeros((h, w), dtype=np.uint8)

    # Define the 4 corners of the zone (axis-aligned, then rotated)
    half_w = zone_w_px // 2
    half_h = zone_h_px // 2
    corners = [
        (cx_px - half_w, cy_px - half_h),  # top-left
        (cx_px + half_w, cy_px - half_h),  # top-right
        (cx_px + half_w, cy_px + half_h),  # bottom-right
        (cx_px - half_w, cy_px + half_h),  # bottom-left
    ]

    # Rotate corners according to zone rotation
    rad = np.radians(rotation)
    cos_a = np.cos(rad)
    sin_a = np.sin(rad)

    rotated_corners = []
    for x, y in corners:
        rx = (x - cx_px) * cos_a - (y - cy_px) * sin_a + cx_px
        ry = (x - cx_px) * sin_a + (y - cy_px) * cos_a + cy_px
        rotated_corners.append((rx, ry))

    cv2.fillPoly(mask, [np.array(rotated_corners, dtype=np.int32)], 255)

    # Rotate the image around the zone center (derotate)
    # Also rotate the mask with the same transformation
    M = cv2.getRotationMatrix2D((cx_px, cy_px), -rotation, 1.0)
    rotated = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rotated_mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)

    # Crop the now-axis-aligned zone from the rotated image
    left = max(0, cx_px - zone_w_px // 2)
    right = min(w, cx_px + zone_w_px // 2)
    top = max(0, cy_px - zone_h_px // 2)
    bottom = min(h, cy_px + zone_h_px // 2)

    crop = rotated[top:bottom, left:right]
    crop_mask = rotated_mask[top:bottom, left:right]

    # Apply mask - set pixels outside the zone to black
    crop = cv2.bitwise_and(crop, crop, mask=crop_mask)

    return crop


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

        zone_id = _as_int(zone.get("id"), -1)
        if zone_id < 0:
            zone_id = None
        is_highlighted = highlight_zone_id is not None and zone_id == highlight_zone_id
        color = (0, 255, 255) if is_highlighted else (120, 120, 120)
        thickness = 3 if is_highlighted else 1

        rotation = _as_float(zone.get("rotation", 0.0), 0.0)

        # Draw rotated rectangle for barrier zones with rotation
        if abs(rotation % 360.0) > 0.01 and str(zone.get("zone_type")) == "barrier_check":
            x_min_norm = _clamp_01(_as_float(zone.get("x_min", 0.0), 0.0))
            y_min_norm = _clamp_01(_as_float(zone.get("y_min", 0.0), 0.0))
            x_max_norm = _clamp_01(_as_float(zone.get("x_max", 1.0), 1.0))
            y_max_norm = _clamp_01(_as_float(zone.get("y_max", 1.0), 1.0))

            x_min = min(x_min_norm, x_max_norm)
            x_max = max(x_min_norm, x_max_norm)
            y_min = min(y_min_norm, y_max_norm)
            y_max = max(y_min_norm, y_max_norm)

            cx_norm = (x_min + x_max) / 2.0
            cy_norm = (y_min + y_max) / 2.0
            half_w_norm = (x_max - x_min) / 2.0
            half_h_norm = (y_max - y_min) / 2.0

            cx_px = int(round(cx_norm * w))
            cy_px = int(round(cy_norm * h))
            half_w_px = int(round(half_w_norm * w))
            half_h_px = int(round(half_h_norm * h))

            # Calculate rotated corners
            rad = np.radians(rotation)
            cos_a = np.cos(rad)
            sin_a = np.sin(rad)

            corners = [
                (-half_w_px, -half_h_px),
                (half_w_px, -half_h_px),
                (half_w_px, half_h_px),
                (-half_w_px, half_h_px),
            ]

            rotated_corners = []
            for x, y in corners:
                rx = x * cos_a - y * sin_a
                ry = x * sin_a + y * cos_a
                rotated_corners.append((cx_px + rx, cy_px + ry))

            # Draw as polygon
            pts = np.array(rotated_corners, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(result, [pts], True, color, thickness)

            # Get label position (top of rotated rect)
            top_x = int(round((rotated_corners[0][0] + rotated_corners[1][0]) / 2))
            top_y = int(round(min(rotated_corners[0][1], rotated_corners[1][1])))
            label = str(zone.get("name") or f"Zone {idx + 1}")
            cv2.putText(
                result,
                label,
                (top_x + 6, max(20, top_y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65 if is_highlighted else 0.55,
                color,
                2 if is_highlighted else 1,
                cv2.LINE_AA,
            )
        else:
            # Simple rectangle for non-rotated zones
            left, top, right, bottom = zone_to_pixels(zone, w, h)
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
