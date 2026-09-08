"""Persistent Energy configuration, metering and interaction state."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..compat_core import default_settings
from ..const import STORE_KEY, STORE_VERSION


class EnergyStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass=hass
        self._store=Store(hass, STORE_VERSION, STORE_KEY)
        self.data: dict[str,Any] = {
            "settings": default_settings(),
            "metering": {"periods": {}, "last_update": None, "last_powers": {}, "last_flexible_powers": {}, "baseload_profile": {}, "baseload_last_sample_bucket": None},
            "command_state": {},
            "pilot_evidence": {},
            "activity": [],
        }
        self._callbacks: list[Callable[[],None]]=[]

    async def async_load(self) -> None:
        raw=await self._store.async_load()
        if isinstance(raw,dict):
            # Merge defaults so later additive properties do not require migration scripts.
            settings=default_settings()
            for k,v in (raw.get("settings") or {}).items():
                if isinstance(v,dict) and isinstance(settings.get(k),dict): settings[k].update(v)
                else: settings[k]=v
            self.data.update(raw); self.data["settings"]=settings

    async def async_save(self) -> None:
        await self._store.async_save(self.data)
        self.notify()

    def add_callback(self, cb: Callable[[],None]) -> Callable[[],None]:
        self._callbacks.append(cb); return lambda: self._callbacks.remove(cb) if cb in self._callbacks else None

    def notify(self) -> None:
        for cb in tuple(self._callbacks): cb()

    def add_activity(self, row: dict[str,Any]) -> None:
        rows=list(self.data.setdefault("activity",[]))
        rows.append({"at":datetime.now(ZoneInfo(self.hass.config.time_zone)).isoformat(),**row})
        self.data["activity"]=rows[-40:]
