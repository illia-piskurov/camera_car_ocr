from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ZoneRuntimeState:
    close_deadline_monotonic: float | None = None
    last_plate: str | None = None
    last_seen_monotonic: float | None = None

    @property
    def is_open(self) -> bool:
        return self.close_deadline_monotonic is not None

    def mark_open(self, plate: str | None, now_monotonic: float, close_delay_sec: float) -> None:
        self.close_deadline_monotonic = now_monotonic + close_delay_sec
        self.last_plate = plate
        self.last_seen_monotonic = now_monotonic

    def refresh_hold(self, plate: str | None, now_monotonic: float, close_delay_sec: float) -> None:
        if not self.is_open:
            return
        self.close_deadline_monotonic = now_monotonic + close_delay_sec
        if plate:
            self.last_plate = plate
        self.last_seen_monotonic = now_monotonic

    def clear(self) -> None:
        self.close_deadline_monotonic = None
        self.last_plate = None
        self.last_seen_monotonic = None
