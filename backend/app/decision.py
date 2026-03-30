from __future__ import annotations

from datetime import datetime, timedelta

from .types import DecisionResult, VoteOutcome


class BarrierDecisionEngine:
    def __init__(self, plate_cooldown_sec: float, global_cooldown_sec: float) -> None:
        self.plate_cooldown = timedelta(seconds=plate_cooldown_sec)
        self.global_cooldown = timedelta(seconds=global_cooldown_sec)
        self.last_open_global: datetime | None = None
        self.last_open_by_plate: dict[str, datetime] = {}

    def evaluate(self, vote: VoteOutcome, is_whitelisted: bool, now: datetime) -> DecisionResult:
        if not is_whitelisted:
            return DecisionResult(should_open=False, reason_code="not_whitelisted")

        if self.last_open_global and now - self.last_open_global < self.global_cooldown:
            return DecisionResult(should_open=False, reason_code="global_cooldown")

        plate_last_open = self.last_open_by_plate.get(vote.plate)
        if plate_last_open and now - plate_last_open < self.plate_cooldown:
            return DecisionResult(should_open=False, reason_code="plate_cooldown")

        self.last_open_global = now
        self.last_open_by_plate[vote.plate] = now
        return DecisionResult(should_open=True, reason_code="open_approved")
