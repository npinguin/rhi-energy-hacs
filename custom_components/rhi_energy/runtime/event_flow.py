"""Bounded source-event coalescing for the Energy runtime."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later


class SourceEventCoalescer:
    def __init__(self, hass: HomeAssistant, recompute: Callable[[], None]) -> None:
        self.hass = hass
        self.recompute = recompute
        self.pending = None
        self.source_event_count = 0
        self.coalesced_source_event_count = 0
        self.recompute_count = 0
        self.last_source_entity_id: str | None = None

    @callback
    def handle(self, event) -> None:
        self.source_event_count += 1
        self.last_source_entity_id = str(event.data.get("entity_id") or "") or None
        if self.pending is not None:
            self.coalesced_source_event_count += 1
            return
        self.pending = async_call_later(self.hass, 0.25, self._flush)

    @callback
    def _flush(self, _now) -> None:
        self.pending = None
        self.recompute_count += 1
        self.recompute()

    def snapshot(self) -> dict[str, Any]:
        return {
            "source_event_count": self.source_event_count,
            "coalesced_source_event_count": self.coalesced_source_event_count,
            "event_driven_recompute_count": self.recompute_count,
            "recompute_pending": self.pending is not None,
            "last_source_entity_id": self.last_source_entity_id,
            "coalescing_window_ms": 250,
        }

    def stop(self) -> None:
        if callable(self.pending):
            self.pending()
        self.pending = None
