from __future__ import annotations

from abc import ABC, abstractmethod

from .normalization import normalize_plate


class WhitelistProvider(ABC):
    @abstractmethod
    def full_sync(self) -> list[tuple[str, str]]:
        raise NotImplementedError


class StubFileWhitelistProvider(WhitelistProvider):
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

        # Remove duplicates while preserving order.
        dedup = list(dict.fromkeys(values))
        return dedup
