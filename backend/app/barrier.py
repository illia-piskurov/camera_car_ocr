from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


class BarrierController:
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def open(self, plate: str, reason: str) -> None:
        if self.dry_run:
            LOG.info("DRY_RUN barrier open requested for %s (%s)", plate, reason)
            return

        # Real hardware integration should be implemented here.
        LOG.info("Barrier open requested for %s (%s)", plate, reason)
