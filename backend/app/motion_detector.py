"""Motion detection for frame differencing.

Detects motion by comparing consecutive frames.
Supports both full-frame and zone-based motion detection.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

LOG = logging.getLogger(__name__)


def compute_frame_diff(
    prev_frame: np.ndarray, curr_frame: np.ndarray, blur_kernel: int = 5
) -> float:
    """Compute frame difference as percentage of changed pixels.

    Args:
        prev_frame: Previous frame (BGR or grayscale)
        curr_frame: Current frame (BGR or grayscale)
        blur_kernel: Gaussian blur kernel size (odd number) to reduce noise

    Returns:
        Percentage of significantly changed pixels (0.0 to 1.0)
    """
    if prev_frame is None or curr_frame is None:
        return 0.0

    if prev_frame.shape != curr_frame.shape:
        LOG.warning("Frame shapes differ: prev=%s, curr=%s", prev_frame.shape, curr_frame.shape)
        return 0.0

    # Convert to grayscale if needed
    if len(prev_frame.shape) == 3 and prev_frame.shape[2] == 3:
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    else:
        prev_gray = prev_frame
        curr_gray = curr_frame

    # Apply Gaussian blur to reduce camera noise
    prev_blurred = cv2.GaussianBlur(prev_gray, (blur_kernel, blur_kernel), 0)
    curr_blurred = cv2.GaussianBlur(curr_gray, (blur_kernel, blur_kernel), 0)

    # Compute absolute difference
    diff = cv2.absdiff(prev_blurred, curr_blurred)

    # Threshold to identify significant changes (> 30 pixel intensity diff)
    # This reduces false positives from minor noise/compression artifacts
    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

    # Count non-zero pixels
    non_zero = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]

    motion_percent = float(non_zero) / float(total_pixels)
    return motion_percent


def has_motion(
    prev_frame: np.ndarray, curr_frame: np.ndarray, threshold: float = 0.05, blur_kernel: int = 5
) -> bool:
    """Check if there is motion between two frames.

    Args:
        prev_frame: Previous frame
        curr_frame: Current frame
        threshold: Motion threshold (0.0 to 1.0, default 0.05 = 5%)
        blur_kernel: Gaussian blur kernel size for noise reduction

    Returns:
        True if motion percentage > threshold, False otherwise
    """
    motion_percent = compute_frame_diff(prev_frame, curr_frame, blur_kernel=blur_kernel)
    has_motion_result = motion_percent > threshold

    if has_motion_result:
        LOG.debug("Motion detected: %.2f%% change (threshold: %.2f%%)", motion_percent * 100, threshold * 100)

    return has_motion_result


def has_motion_in_zone(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    zone: dict[str, object],
    threshold: float = 0.05,
    blur_kernel: int = 5,
) -> bool:
    """Check if there is motion in a specific zone.

    Args:
        prev_frame: Previous frame
        curr_frame: Current frame
        zone: Zone dict with normalized coordinates (x_min, x_max, y_min, y_max, all 0-1)
        threshold: Motion threshold (default 0.05 = 5%)
        blur_kernel: Gaussian blur kernel size for noise reduction

    Returns:
        True if motion detected in zone, False otherwise
    """
    from .zones import crop_zone

    try:
        prev_zone_frame = crop_zone(prev_frame, zone)
        curr_zone_frame = crop_zone(curr_frame, zone)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Failed to crop zone for motion detection: %s", exc)
        return False

    return has_motion(prev_zone_frame, curr_zone_frame, threshold=threshold, blur_kernel=blur_kernel)
