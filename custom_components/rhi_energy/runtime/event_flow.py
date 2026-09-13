"""Bounded source-event coalescing for the Energy runtime."""
from __future__ import annotations

from time import monotonic, perf_counter
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later


class SourceEventCoalescer:
    """Coalesce physical and producer bursts without starving runtime updates.

    E0.12.5 used a leading 250 ms window. A long Mobility/OCPP publication burst could
    therefore still trigger one full Energy recompute every 250 ms. E0.12.5 switches
    to a bounded trailing debounce: events extend the quiet window, but a continuous
    burst is forced through at least once per second. This keeps freshness bounded
    while preventing producer-publication amplification.
    """

    QUIET_WINDOW_SECONDS = 0.25
    MAX_BURST_SECONDS = 1.0

    def __init__(self, hass: HomeAssistant, recompute: Callable[[], Any]) -> None:
        self.hass = hass
        self.recompute = recompute
        self.pending = None
        self.source_event_count = 0
        self.physical_source_event_count = 0
        self.mobility_publication_event_count = 0
        self.coalesced_source_event_count = 0
        self.recompute_count = 0
        self.last_source_entity_id: str | None = None
        self._burst_started_at: float | None = None
        self.last_recompute_duration_ms = 0.0
        self.max_recompute_duration_ms = 0.0
        self.total_recompute_duration_ms = 0.0

    @callback
    def handle(self, event) -> None:
        self.source_event_count += 1
        entity_id = str(event.data.get("entity_id") or "") or None
        self.last_source_entity_id = entity_id
        if entity_id and entity_id.startswith("sensor.mobility_"):
            self.mobility_publication_event_count += 1
        else:
            self.physical_source_event_count += 1

        now = monotonic()
        if self._burst_started_at is None:
            self._burst_started_at = now
        elapsed = now - self._burst_started_at

        if callable(self.pending):
            self.pending()
            self.pending = None
            self.coalesced_source_event_count += 1

        remaining = max(0.0, self.MAX_BURST_SECONDS - elapsed)
        delay = min(self.QUIET_WINDOW_SECONDS, remaining)
        # async_call_later(0) is valid but a tiny positive delay keeps the callback
        # outside the current state-change stack under a saturated producer burst.
        self.pending = async_call_later(self.hass, max(0.001, delay), self._flush)

    @callback
    def _flush(self, _now) -> None:
        self.pending = None
        self._burst_started_at = None
        self.recompute_count += 1
        started = perf_counter()
        try:
            self.recompute()
        finally:
            duration = (perf_counter() - started) * 1000.0
            self.last_recompute_duration_ms = round(duration, 3)
            self.max_recompute_duration_ms = round(max(self.max_recompute_duration_ms, duration), 3)
            self.total_recompute_duration_ms += duration

    def snapshot(self) -> dict[str, Any]:
        average = self.total_recompute_duration_ms / self.recompute_count if self.recompute_count else 0.0
        return {
            "source_event_count": self.source_event_count,
            "physical_source_event_count": self.physical_source_event_count,
            "mobility_publication_event_count": self.mobility_publication_event_count,
            "coalesced_source_event_count": self.coalesced_source_event_count,
            "event_driven_recompute_count": self.recompute_count,
            "recompute_pending": self.pending is not None,
            "last_source_entity_id": self.last_source_entity_id,
            "quiet_window_ms": int(self.QUIET_WINDOW_SECONDS * 1000),
            "max_burst_ms": int(self.MAX_BURST_SECONDS * 1000),
            "last_recompute_duration_ms": self.last_recompute_duration_ms,
            "average_recompute_duration_ms": round(average, 3),
            "max_recompute_duration_ms": self.max_recompute_duration_ms,
        }

    def stop(self) -> None:
        if callable(self.pending):
            self.pending()
        self.pending = None
        self._burst_started_at = None
