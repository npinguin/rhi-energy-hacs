"""E0.14.1 runtime closure over the proven event-driven engine."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ..compat_core import deterministic_plan, intelligence, overview_snapshot
from .engine_base import EnergyRuntime as _BaseEnergyRuntime
from .parity import battery_state, close_current_energy_facts, close_planning_views, grid_direction


class EnergyRuntime(_BaseEnergyRuntime):
    """Keep measurement ownership in the base runtime and close canonical product truth."""

    def __init__(self, hass, store) -> None:
        super().__init__(hass, store)
        self._canonical_snapshot_revision = 0

    def _notify_topology_if_changed(self):
        return super()._notify_topology_if_changed()

    def _canonicalize(self, assets, facts, issues):
        super()._canonicalize(assets, facts, issues)
        batteries = [row for row in assets if row.get("object_class") == "battery_system"]
        battery_values = [
            facts.get("battery.power_kw"),
            facts.get("battery.soc_pct"),
            facts.get("battery.capacity_kwh"),
            facts.get("battery.available_kwh"),
        ]
        known = sum(value is not None for value in battery_values)
        facts["battery.health"] = (
            "OK" if known >= 2 else "DEGRADED" if batteries and known else "UNKNOWN"
        )
        facts["battery.state"] = battery_state(facts)
        facts["grid.flow_direction"] = grid_direction(facts)

        if facts.get("pricing.future_prices") is None:
            for asset in assets:
                if asset.get("object_class") != "price_source" or asset.get("market_role") == "export":
                    continue
                for prop in asset.get("properties") or []:
                    if prop.get("property_key") != "pricing.spot_eur_kwh":
                        continue
                    binding_id = prop.get("binding_id") or next(iter(prop.get("binding_ids") or []), None)
                    _raw, _unit, attrs = self._read(binding_id)
                    today = attrs.get("raw_today") or attrs.get("prices")
                    tomorrow = attrs.get("raw_tomorrow")
                    intervals = []
                    if isinstance(today, list):
                        intervals.extend(deepcopy(today))
                    if isinstance(tomorrow, list):
                        intervals.extend(deepcopy(tomorrow))
                    if intervals:
                        facts["pricing.future_prices"] = intervals
                    if attrs.get("currency") and facts.get("pricing.currency") is None:
                        facts["pricing.currency"] = str(attrs["currency"])
                    break
                if facts.get("pricing.future_prices") is not None:
                    break

    def _recompute(self):
        super()._recompute()
        if self.model is None:
            return

        flexible = deepcopy(self.snapshot.get("flexible_assets") or [])
        producer_available = bool(
            (self.snapshot.get("producer_publication_availability") or {}).get("mobility")
        )
        facts, inconsistent = close_current_energy_facts(
            self.snapshot.get("facts") or {}, flexible, producer_available
        )
        if inconsistent:
            issues = list(self.snapshot.get("runtime_issues") or [])
            issues.append("consumption_split_inconsistent:flexible_exceeds_site")
            self.snapshot["runtime_issues"] = sorted(set(issues))

        settings = deepcopy(self.store.data.get("settings") or {})
        settings["baseload_profile"] = deepcopy(
            (self.store.data.get("metering") or {}).get("baseload_profile") or {}
        )
        now_local = datetime.now(ZoneInfo(self.hass.config.time_zone))
        plan = close_planning_views(
            deterministic_plan(facts, settings, flexible, now_local), flexible
        )
        intel = intelligence(plan, facts, settings, flexible)
        overview = overview_snapshot(facts)

        self._canonical_snapshot_revision += 1
        self.snapshot.update(
            {
                "facts": facts,
                "plan": plan,
                "intelligence": intel,
                "overview": overview,
                "snapshot_revision": self._canonical_snapshot_revision,
                "observed_at": datetime.now(UTC).isoformat(),
                "generation": deepcopy(self.model.get("generation") or {}),
                "layer_health": deepcopy(self.model.get("layer_health") or {}),
                "system_assets": deepcopy(self.model.get("system_assets") or []),
                "planning_assets": deepcopy(self.model.get("planning_assets") or []),
                "intelligence_assets": deepcopy(self.model.get("intelligence_assets") or []),
                "model_fingerprint": self.model.get("model_fingerprint"),
                "dependency_diagnostics": deepcopy(self.model.get("dependency_diagnostics") or {}),
            }
        )
