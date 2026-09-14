"""E0.14 runtime closure over the proven event-driven engine."""
from __future__ import annotations
from copy import deepcopy

from .engine_base import EnergyRuntime as _BaseEnergyRuntime


class EnergyRuntime(_BaseEnergyRuntime):
    def _notify_topology_if_changed(self):
        return super()._notify_topology_if_changed()

    def _canonicalize(self, assets, facts, issues):
        super()._canonicalize(assets, facts, issues)
        batteries = [row for row in assets if row.get("object_class") == "battery_system"]
        battery_values = [
            facts.get("battery.power_kw"), facts.get("battery.soc_pct"),
            facts.get("battery.capacity_kwh"), facts.get("battery.available_kwh"),
        ]
        known = sum(value is not None for value in battery_values)
        facts["battery.health"] = "OK" if known >= 2 else "DEGRADED" if batteries and known else "UNKNOWN"

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
                    currency = attrs.get("currency")
                    if currency and facts.get("pricing.currency") is None:
                        facts["pricing.currency"] = str(currency)
                    break
                if facts.get("pricing.future_prices") is not None:
                    break

    def _recompute(self):
        super()._recompute()
        if self.model is None:
            return
        self.snapshot.update({
            "generation": deepcopy(self.model.get("generation") or {}),
            "layer_health": deepcopy(self.model.get("layer_health") or {}),
            "system_assets": deepcopy(self.model.get("system_assets") or []),
            "planning_assets": deepcopy(self.model.get("planning_assets") or []),
            "intelligence_assets": deepcopy(self.model.get("intelligence_assets") or []),
            "model_fingerprint": self.model.get("model_fingerprint"),
            "dependency_diagnostics": deepcopy(self.model.get("dependency_diagnostics") or {}),
        })
