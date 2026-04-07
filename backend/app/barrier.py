from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


class BarrierController:
    def __init__(self, dry_run: bool = True, action_mode: str = "mock") -> None:
        mode = (action_mode or "mock").strip().lower()
        if mode not in {"mock", "live"}:
            mode = "mock"

        # Backward compatibility: dry_run=True always forces mock behavior.
        self.action_mode = "mock" if dry_run else mode

    def open(self, plate: str, reason: str) -> None:
        if self.action_mode != "live":
            LOG.info("MOCK barrier open decision for %s (%s)", plate, reason)
            return

        # Real hardware integration should be implemented here.
        LOG.info("Barrier open requested for %s (%s)", plate, reason)
