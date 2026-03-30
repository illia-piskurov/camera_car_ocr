from __future__ import annotations

import logging

import cv2
import httpx
import numpy as np

LOG = logging.getLogger(__name__)


class SnapshotCameraClient:
    def __init__(self, url: str, timeout_sec: float, retries: int) -> None:
        self.url = url
        self.timeout_sec = timeout_sec
        self.retries = retries
        self._client = httpx.Client(timeout=self.timeout_sec)

    def fetch_frame(self) -> np.ndarray | None:
        for attempt in range(1, self.retries + 2):
            try:
                response = self._client.get(self.url)
                response.raise_for_status()
                img_array = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is None:
                    LOG.warning("Camera returned invalid image bytes")
                return frame
            except Exception as exc:  # noqa: BLE001
                LOG.warning("Snapshot fetch failed (attempt %s): %s", attempt, exc)
        return None

    def close(self) -> None:
        self._client.close()
