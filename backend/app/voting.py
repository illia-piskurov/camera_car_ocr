from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .types import PlateDetection, VoteOutcome


@dataclass(frozen=True)
class _VoteSample:
    ts: datetime
    plate: str
    fuzzy_plate: str
    confidence: float


class TemporalVoter:
    def __init__(self, window_sec: float, min_confirmations: int, min_avg_confidence: float) -> None:
        self.window = timedelta(seconds=window_sec)
        self.window_sec = window_sec
        self.min_confirmations = min_confirmations
        self.min_avg_confidence = min_avg_confidence
        self.samples: deque[_VoteSample] = deque()

    def observe(self, detection: PlateDetection) -> VoteOutcome | None:
        now = detection.detected_at
        self.samples.append(
            _VoteSample(
                ts=now,
                plate=detection.normalized_text,
                fuzzy_plate=detection.fuzzy_text,
                confidence=detection.combined_confidence,
            )
        )
        self._evict_old(now)

        grouped: dict[str, list[_VoteSample]] = defaultdict(list)
        for sample in self.samples:
            grouped[sample.plate].append(sample)

        best_plate = None
        best_avg = 0.0
        for plate, values in grouped.items():
            count = len(values)
            avg_conf = sum(v.confidence for v in values) / count
            if count >= self.min_confirmations and avg_conf >= self.min_avg_confidence and avg_conf >= best_avg:
                best_plate = (plate, values[0].fuzzy_plate, count, avg_conf)
                best_avg = avg_conf

        if best_plate is None:
            return None

        plate, fuzzy_plate, count, avg_conf = best_plate
        return VoteOutcome(
            plate=plate,
            fuzzy_plate=fuzzy_plate,
            confirmations=count,
            avg_confidence=avg_conf,
            window_sec=self.window_sec,
        )

    def _evict_old(self, now: datetime) -> None:
        while self.samples and now - self.samples[0].ts > self.window:
            self.samples.popleft()
