"""Barrier state calibration — offline analysis of event snapshots."""
from __future__ import annotations

import base64
import glob
import os

import cv2
import numpy as np

from .motion_detector import compute_frame_diff
from .zones import crop_zone


def find_snapshot_for_frame(frame_id: str, snapshot_dir: str) -> str | None:
    pattern = os.path.join(snapshot_dir, f"*_{frame_id}_*.jpg")
    matches = glob.glob(pattern)
    if not matches:
        return None
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return matches[0]


def load_zone_crop(image_path: str, zone: dict) -> np.ndarray | None:
    img = cv2.imread(image_path)
    if img is None:
        return None
    try:
        return crop_zone(img, zone)
    except Exception:  # noqa: BLE001
        return None


def crop_to_bytes(crop: np.ndarray, quality: int = 80) -> bytes | None:
    ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return encoded.tobytes() if ok else None


def crop_to_base64(crop: np.ndarray, quality: int = 80) -> str | None:
    data = crop_to_bytes(crop, quality)
    return base64.b64encode(data).decode() if data else None


def bytes_to_crop(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def compute_diff_vs_reference(
    crop: np.ndarray,
    reference: np.ndarray,
) -> float:
    ref = reference
    if crop.shape != ref.shape:
        ref = cv2.resize(ref, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_LINEAR)
    return float(compute_frame_diff(ref, crop))


def build_calibration_samples(
    events: list[dict],
    check_zone: dict,
    reference_crop: np.ndarray | None,
    threshold: float,
    existing_labels: dict[int, str],
    snapshot_dir: str,
    max_samples: int = 60,
) -> list[dict]:
    """Load event snapshots, crop barrier zone, compute diff vs closed reference.

    Returns list of sample dicts suitable for the calibration API response.
    diff > threshold → predicted OPEN (differs from closed reference).
    """
    samples: list[dict] = []
    for event in events:
        if len(samples) >= max_samples:
            break
        event_id = int(event["id"])
        frame_id = event.get("frame_id")
        if not frame_id:
            continue
        image_path = find_snapshot_for_frame(str(frame_id), snapshot_dir)
        if not image_path:
            continue
        crop = load_zone_crop(image_path, check_zone)
        if crop is None:
            continue

        diff_score: float | None = None
        predicted_label: str | None = None
        if reference_crop is not None:
            diff_score = compute_diff_vs_reference(crop, reference_crop)
            predicted_label = "open" if diff_score > threshold else "closed"

        samples.append({
            "event_id": event_id,
            "occurred_at": event.get("occurred_at"),
            "image_url": f"/api/events/{event_id}/image",
            "crop_b64": crop_to_base64(crop),
            "diff_score": diff_score,
            "predicted_label": predicted_label,
            "user_label": existing_labels.get(event_id),
        })

    return samples


def compute_optimal_threshold(samples: list[dict]) -> float | None:
    """Compute threshold that best separates labeled open/closed samples.

    Uses closed-reference convention: diff > threshold → OPEN.
    Returns midpoint between max(closed diffs) and min(open diffs).
    If distributions overlap, returns average of both means.
    """
    closed_diffs = [
        s["diff_score"] for s in samples
        if s.get("user_label") == "closed" and s.get("diff_score") is not None
    ]
    open_diffs = [
        s["diff_score"] for s in samples
        if s.get("user_label") == "open" and s.get("diff_score") is not None
    ]
    if not closed_diffs or not open_diffs:
        return None

    max_closed = max(closed_diffs)
    min_open = min(open_diffs)

    if min_open > max_closed:
        return round((max_closed + min_open) / 2, 4)

    # Overlapping — midpoint of means
    mean_closed = sum(closed_diffs) / len(closed_diffs)
    mean_open = sum(open_diffs) / len(open_diffs)
    return round((mean_closed + mean_open) / 2, 4)


def compute_accuracy(samples: list[dict], threshold: float) -> float | None:
    labeled = [s for s in samples if s.get("user_label") and s.get("diff_score") is not None]
    if not labeled:
        return None
    correct = sum(
        1 for s in labeled
        if (s["diff_score"] > threshold) == (s["user_label"] == "open")
    )
    return round(correct / len(labeled), 3)
