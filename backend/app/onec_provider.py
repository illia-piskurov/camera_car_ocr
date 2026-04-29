from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import httpx

from .normalization import normalize_plate

LOG = logging.getLogger(__name__)

TEST_PLATE = "AA1234ZE"


class WhitelistProvider(ABC):
    source: str = "unknown"

    @abstractmethod
    def full_sync(self) -> list[tuple[str, str]]:
        raise NotImplementedError


class StubFileWhitelistProvider(WhitelistProvider):
    source = "1c_stub"

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def full_sync(self) -> list[tuple[str, str]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                raw = [line.strip() for line in file.readlines()]
        except FileNotFoundError:
            return []

        values: list[tuple[str, str]] = []
        for line in raw:
            if not line or line.startswith("#"):
                continue
            norm = normalize_plate(line)
            if not norm.normalized:
                continue
            values.append((norm.normalized, norm.fuzzy))

        test_norm = normalize_plate(TEST_PLATE)
        values.append((test_norm.normalized, test_norm.fuzzy))

        # Remove duplicates while preserving order.
        dedup = list(dict.fromkeys(values))
        return dedup


class HttpWhitelistProvider(WhitelistProvider):
    source = "1c_http"

    def __init__(self, url: str, timeout_sec: float = 10.0, retries: int = 2) -> None:
        self.url = url
        self.timeout_sec = timeout_sec
        self.retries = max(0, retries)

    def full_sync(self) -> list[tuple[str, str]]:
        if not self.url:
            raise ValueError("ONEC_HTTP_URL is empty")

        attempts = self.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_sec) as client:
                    response = client.get(self.url)
                    response.raise_for_status()
                    payload = response.json()
                return self._parse_payload(payload)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < attempts:
                    time.sleep(0.3 * attempt)
                    continue

        raise RuntimeError(f"1C HTTP sync failed after {attempts} attempts: {last_error}")

    def _parse_payload(self, payload: object) -> list[tuple[str, str]]:
        if not isinstance(payload, dict):
            raise ValueError("1C payload must be an object")

        raw_list = payload.get("Список")
        if not isinstance(raw_list, list):
            raise ValueError("1C payload has no 'Список' array")

        values: list[tuple[str, str]] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue

            plate_raw = item.get("Номер")
            if not isinstance(plate_raw, str):
                continue

            norm = normalize_plate(plate_raw)
            if not norm.normalized:
                continue

            values.append((norm.normalized, norm.fuzzy))
            test_norm = normalize_plate(TEST_PLATE)
            values.append((test_norm.normalized, test_norm.fuzzy))

        return list(dict.fromkeys(values))


def create_whitelist_provider(settings) -> WhitelistProvider:
    mode = (getattr(settings, "onec_provider_mode", "stub") or "stub").strip().lower()
    if mode == "http":
        url = str(getattr(settings, "onec_http_url", "") or "")
        timeout_sec = float(getattr(settings, "onec_http_timeout_sec", 10.0))
        retries = int(getattr(settings, "onec_http_retries", 2))
        LOG.info("Whitelist provider mode=http")
        return HttpWhitelistProvider(url=url, timeout_sec=timeout_sec, retries=retries)

    LOG.info("Whitelist provider mode=stub")
    return StubFileWhitelistProvider(str(getattr(settings, "onec_stub_file", "onec_whitelist_stub.txt")))
