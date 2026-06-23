"""Barrier open/close state detection via camera frame analysis.

Compares the current frame in a configured "barrier check zone" against a
reference frame captured when the barrier was known to be open.  A large
difference means the arm is present (CLOSED); a small difference means the
arm is absent (OPEN).

The reference is refreshed automatically after a successful open command
(after a short settle delay) and adapts gradually to lighting changes while
the barrier remains open.
"""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np

from .motion_detector import compute_frame_diff
from .zones import crop_zone

LOG = logging.getLogger(__name__)

OPEN = "open"
CLOSED = "closed"
UNKNOWN = "unknown"


class BarrierStateDetector:
    """Detects barrier open/closed state from camera frames.

    Args:
        threshold: Fraction of pixels that must differ for state = CLOSED.
                   Default 0.05 (5%).  Raise if false-positives (shadows,
                   headlights); lower if arm is thin or poorly lit.
        reference_delay_sec: Seconds to wait after open command before
                             capturing the reference frame.  Gives the arm
                             time to fully rise out of frame.
        adapt_alpha: Weight of the current frame blended into the reference
                     each cycle while the barrier is confirmed OPEN.
                     0 = no adaptation; 0.02 = slow drift tracking.
    """

    def __init__(
        self,
        threshold: float = 0.05,
        reference_delay_sec: float = 3.0,
        adapt_alpha: float = 0.02,
    ) -> None:
        self._threshold = threshold
        self._reference_delay_sec = reference_delay_sec
        self._adapt_alpha = adapt_alpha

        self._reference: np.ndarray | None = None
        self._state: str = UNKNOWN
        self._pending_reference_at: float | None = None  # monotonic deadline

    @property
    def state(self) -> str:
        return self._state

    @property
    def has_reference(self) -> bool:
        return self._reference is not None

    def notify_opened(self, now_monotonic: float | None = None) -> None:
        """Call immediately after a successful barrier open command.

        Schedules reference capture once the arm has fully risen.
        """
        t = now_monotonic if now_monotonic is not None else time.monotonic()
        self._pending_reference_at = t + self._reference_delay_sec
        LOG.debug(
            "Barrier state: reference capture scheduled in %.1fs",
            self._reference_delay_sec,
        )

    def capture_reference(self, frame: np.ndarray, zone: dict) -> None:
        """Manually capture a reference frame (barrier must be open)."""
        try:
            zone_frame = crop_zone(frame, zone)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Barrier state: failed to crop zone for reference: %s", exc)
            return
        self._reference = zone_frame.copy()
        self._pending_reference_at = None
        LOG.info("Barrier state: reference frame captured (%dx%d)", zone_frame.shape[1], zone_frame.shape[0])

    def update(self, frame: np.ndarray, zone: dict, now_monotonic: float | None = None) -> str:
        """Process a new camera frame and return the current barrier state.

        Args:
            frame: Full camera frame (BGR numpy array).
            zone: Zone dict with x_min/y_min/x_max/y_max (0-1 normalised).
            now_monotonic: Current time.monotonic() value; fetched if omitted.

        Returns:
            One of OPEN / CLOSED / UNKNOWN.
        """
        t = now_monotonic if now_monotonic is not None else time.monotonic()

        try:
            zone_frame = crop_zone(frame, zone)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Barrier state: failed to crop zone: %s", exc)
            return self._state

        # Capture scheduled reference (arm has had time to rise)
        if self._pending_reference_at is not None and t >= self._pending_reference_at:
            self._reference = zone_frame.copy()
            self._pending_reference_at = None
            LOG.info(
                "Barrier state: reference auto-captured (%dx%d)",
                zone_frame.shape[1],
                zone_frame.shape[0],
            )

        if self._reference is None:
            return UNKNOWN

        # Resize reference if camera resolution changed
        if zone_frame.shape != self._reference.shape:
            self._reference = cv2.resize(
                self._reference,
                (zone_frame.shape[1], zone_frame.shape[0]),
                interpolation=cv2.INTER_LINEAR,
            )

        diff = compute_frame_diff(self._reference, zone_frame)

        if diff > self._threshold:
            self._state = CLOSED
        else:
            self._state = OPEN
            # Slowly blend reference toward current frame to track lighting drift
            if self._adapt_alpha > 0:
                self._reference = cv2.addWeighted(
                    self._reference,
                    1.0 - self._adapt_alpha,
                    zone_frame,
                    self._adapt_alpha,
                    0,
                )

        LOG.debug("Barrier state: diff=%.3f threshold=%.3f state=%s", diff, self._threshold, self._state)
        return self._state
