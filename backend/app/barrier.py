from __future__ import annotations

import logging
import time

import httpx

LOG = logging.getLogger(__name__)


class BarrierController:
    def __init__(
        self,
        dry_run: bool = True,
        action_mode: str = "mock",
        ha_base_url: str = "",
        ha_token: str = "",
        open_entity_id: str = "",
        close_entity_id: str = "",
        timeout_sec: float = 3.0,
        retries: int = 2,
        verify_tls: bool = True,
    ) -> None:
        mode = (action_mode or "mock").strip().lower()
        if mode not in {"mock", "live"}:
            mode = "mock"

        # Backward compatibility: dry_run=True always forces mock behavior.
        self.action_mode = "mock" if dry_run else mode
        self.ha_base_url = (ha_base_url or "").strip().rstrip("/")
        self.ha_token = (ha_token or "").strip()
        self.open_entity_id = (open_entity_id or "").strip()
        self.close_entity_id = (close_entity_id or "").strip()
        self.timeout_sec = max(0.1, float(timeout_sec))
        self.retries = max(1, int(retries))
        self.verify_tls = bool(verify_tls)

        self._enabled_live = self.action_mode == "live"
        if self._enabled_live and not self._is_live_configured():
            LOG.warning(
                "Barrier action mode is live but HA settings are incomplete. Falling back to mock mode"
            )
            self._enabled_live = False

    def _is_live_configured(self) -> bool:
        return all(
            [
                self.ha_base_url,
                self.ha_token,
                self.open_entity_id,
                self.close_entity_id,
            ]
        )

    def _press_input_button(self, *, entity_id: str, plate: str | None, reason: str, action: str) -> bool:
        if not self._enabled_live:
            label = plate if plate else "-"
            LOG.info("MOCK barrier %s decision for %s (%s)", action, label, reason)
            return True

        url = f"{self.ha_base_url}/api/services/input_button/press"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}

        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_sec, verify=self.verify_tls) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                LOG.info(
                    "Barrier %s executed entity_id=%s plate=%s reason=%s",
                    action,
                    entity_id,
                    plate or "-",
                    reason,
                )
                return True
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(0.3 * attempt)

        LOG.warning(
            "Barrier %s failed entity_id=%s plate=%s reason=%s error=%s",
            action,
            entity_id,
            plate or "-",
            reason,
            last_exc,
        )
        return False

    def open(self, plate: str, reason: str) -> bool:
        return self._press_input_button(
            entity_id=self.open_entity_id,
            plate=plate,
            reason=reason,
            action="open",
        )

    def close(self, reason: str, plate: str | None = None) -> bool:
        return self._press_input_button(
            entity_id=self.close_entity_id,
            plate=plate,
            reason=reason,
            action="close",
        )
