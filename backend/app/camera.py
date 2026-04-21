from __future__ import annotations

import logging

import cv2
import httpx
import numpy as np

LOG = logging.getLogger(__name__)


class SnapshotCameraClient:
    def __init__(
        self,
        url: str,
        timeout_sec: float,
        retries: int,
        username: str = "",
        password: str = "",
        auth_mode: str = "digest",
    ) -> None:
        self.url = url
        self.timeout_sec = timeout_sec
        self.retries = retries
        auth: httpx.Auth | None = None

        if username:
            mode = (auth_mode or "").strip().lower()
            if mode == "none":
                auth = None
            elif mode == "basic":
                auth = httpx.BasicAuth(username=username, password=password)
            else:
                auth = httpx.DigestAuth(username=username, password=password)

        self._client = httpx.Client(timeout=self.timeout_sec, auth=auth)

    def probe_frame(self) -> tuple[np.ndarray | None, str | None]:
        last_error: str | None = None
        for attempt in range(1, self.retries + 2):
            try:
                response = self._client.get(self.url)
                response.raise_for_status()
                img_array = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is None:
                    last_error = "invalid image bytes"
                    LOG.warning("Camera returned invalid image bytes")
                    continue
                return frame, None
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code if exc.response is not None else "n/a"
                    last_error = f"HTTP {status_code}"
                    LOG.warning("Snapshot fetch failed (attempt %s): HTTP %s", attempt, status_code)
                else:
                    last_error = exc.__class__.__name__
                    LOG.warning("Snapshot fetch failed (attempt %s): %s", attempt, exc.__class__.__name__)
        return None, last_error

    def fetch_frame(self) -> np.ndarray | None:
        frame, _ = self.probe_frame()
        return frame

    def close(self) -> None:
        self._client.close()
