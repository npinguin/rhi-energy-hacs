"""Bounded tactical-planning cadence separate from telemetry recompute."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

from .canonical_semantics import deterministic_plan
from .planning_input_revision import planning_input_revision


TACTICAL_PLANNING_INTERVAL_MINUTES = 5
OPERATIONAL_EXECUTION_INTERVAL_MINUTES = 1


class TacticalPlanningCadence:
    """Cache tactical planning and refresh it on a bounded five-minute cadence."""

    def __init__(self, hass, recompute: Callable[[], None], local_timezone) -> None:
        self.hass = hass
        self._recompute = recompute
        self._local_timezone = local_timezone
        self._remove_timer = None
        self._refresh_requested = True
        self._plan: dict[str, Any] = {}
        self._refresh_count = 0
        self._last_refresh_at: str | None = None
        self._last_input_revision: str | None = None

    def start(self) -> None:
        self.request_refresh()
        if self._remove_timer is None:
            self._remove_timer = async_track_time_interval(
                self.hass,
                self._tick,
                timedelta(minutes=TACTICAL_PLANNING_INTERVAL_MINUTES),
            )

    def stop(self) -> None:
        if callable(self._remove_timer):
            self._remove_timer()
        self._remove_timer = None

    def request_refresh(self) -> None:
        self._refresh_requested = True

    def activate(self, active: bool) -> None:
        if not active:
            self.stop()

    def refresh_now(self) -> None:
        self.request_refresh()
        self._recompute()

    @callback
    def _tick(self, _now) -> None:
        # HA time helpers run undecorated synchronous handlers in an executor.
        # This timer recomputes canonical state and notifies HA entities, so it
        # must execute on the event loop like the source-event callback.
        self.refresh_now()

    def resolve(
        self,
        facts: dict[str, Any],
        settings: dict[str, Any],
        flexible_assets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        # A changed planning bucket resolution changes the complete horizon
        # contract and must invalidate the cached tactical plan immediately.
        # Keep the existing deterministic planner as the sole authority.
        resolution = (settings.get("planning") or {}).get("resolution_minutes", 60)
        if type(resolution) is not int or resolution not in (15, 30, 60):
            raise ValueError("deterministic_planning_resolution_invalid")
        now_local = datetime.now(self._local_timezone)
        revision = planning_input_revision(
            facts, settings, flexible_assets, day_key=now_local.date().isoformat()
        )
        if (self._refresh_requested or not self._plan
                or self._plan.get("resolution_minutes") != resolution
                or self._last_input_revision != revision):
            self._plan = deterministic_plan(facts, settings, flexible_assets, now_local)
            self._last_input_revision = revision
            self._refresh_requested = False
            self._refresh_count += 1
            self._last_refresh_at = datetime.now(UTC).isoformat()
        return deepcopy(self._plan)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "tactical_interval_minutes": TACTICAL_PLANNING_INTERVAL_MINUTES,
            "tactical_refresh_count": self._refresh_count,
            "last_tactical_refresh_at": self._last_refresh_at,
            "operational_interval_minutes": OPERATIONAL_EXECUTION_INTERVAL_MINUTES,
            "tactical_refresh_pending": self._refresh_requested,
            "planning_input_revision": self._last_input_revision,
        }
