"""E0.14.4 runtime closure over the proven event-driven engine."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ..compat_core import deterministic_plan, intelligence, overview_snapshot
from .engine_base import EnergyRuntime as _BaseEnergyRuntime
from .parity import battery_state, close_current_energy_facts, close_planning_views, grid_direction


def _has(value) -> bool:
    return value is not None and str(value).lower() not in {"unknown", "unavailable", "none", ""}


def _runtime_layers(model, facts, plan, flexible, producer_available):
    """Project live dependency truth onto compile-owned topology without adding topology."""
    systems = deepcopy(model.get("system_assets") or [])
    planning = deepcopy(model.get("planning_assets") or [])
    intelligence_rows = deepcopy(model.get("intelligence_assets") or [])

    battery_ready = all(_has(facts.get(key)) for key in ("battery.power_kw", "battery.soc_pct", "battery.capacity_kwh"))
    solar_ready = _has(facts.get("solar.power_kw"))
    grid_ready = _has(facts.get("grid.net_power_kw"))
    site_ready = _has(facts.get("site_consumption.power_kw"))
    home_ready = _has(facts.get("home_consumption.power_kw"))
    forecast_d0 = _has(facts.get("forecast.solar_remaining_today_kwh")) or _has(facts.get("forecast.solar_today_kwh"))
    forecast_d1 = _has(facts.get("forecast.solar_tomorrow_kwh"))
    future_prices = facts.get("pricing.future_prices")
    pricing_ready = isinstance(future_prices, list) and bool(future_prices)

    flexible_ready = bool(producer_available)
    if flexible_ready and flexible:
        flexible_ready = all(
            row.get("asset_id")
            and row.get("power_kw") is not None
            and row.get("planning_input_ready") is not False
            for row in flexible
            if isinstance(row, dict)
        )

    system_truth = {
        "battery_system": (battery_ready, "battery_runtime_evidence_incomplete"),
        "solar_production_system": (solar_ready, "solar_runtime_evidence_incomplete"),
        "grid_system": (grid_ready, "grid_runtime_evidence_incomplete"),
        "site_energy_balance": (site_ready and solar_ready and grid_ready, "energy_balance_inputs_incomplete"),
        "home_consumption": (home_ready, "home_consumption_unavailable"),
        "solar_forecast_system": (forecast_d0 and forecast_d1, "forecast_d0_d1_incomplete"),
        "pricing_system": (pricing_ready, "pricing_horizon_incomplete"),
        "flexible_load_system": (flexible_ready, "mobility_planning_publication_incomplete"),
        "connection_system": (bool(producer_available), "mobility_connection_publication_unavailable"),
    }
    for row in systems:
        if not isinstance(row, dict):
            continue
        truth = system_truth.get(str(row.get("concept_id") or ""))
        if truth is None:
            continue
        ready, reason = truth
        row["status"] = "READY" if ready else "INCOMPLETE"
        if ready:
            row.pop("reason", None)
        else:
            row["reason"] = reason

    planning_truth = {
        "planning_supply": None,
        "planning_asset": (battery_ready, "battery_planning_input_incomplete"),
        "planning_demand": None,
        "planning_pricing": (pricing_ready, "pricing_horizon_incomplete"),
        "energy_need": (flexible_ready, "flexible_energy_need_incomplete"),
    }
    horizons = plan.get("planning_horizons") or {}
    d0 = horizons.get("D0") if isinstance(horizons, dict) else None
    d1 = horizons.get("D1") if isinstance(horizons, dict) else None
    d0_ready = isinstance(d0, dict) and ((d0.get("quality") or {}).get("availability") == "AVAILABLE")
    d1_ready = isinstance(d1, dict) and ((d1.get("quality") or {}).get("availability") == "AVAILABLE")

    for row in planning:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("asset_id") or "")
        concept = str(row.get("concept_id") or "")
        truth = planning_truth.get(concept)
        if aid == "planning_supply:solar":
            truth = (forecast_d0 and forecast_d1, "forecast_d0_d1_incomplete")
        elif aid == "planning_supply:grid":
            truth = (grid_ready, "grid_planning_input_incomplete")
        elif aid == "planning_demand:home":
            truth = (home_ready, "home_demand_incomplete")
        elif aid == "planning_demand:flexible":
            truth = (flexible_ready, "flexible_demand_incomplete")
        elif aid.startswith("planning_horizon:D0"):
            truth = (d0_ready, "d0_required_inputs_incomplete")
        elif aid.startswith("planning_horizon:D1"):
            truth = (d1_ready, "d1_required_inputs_incomplete")
        elif concept == "baseline_energy_plan":
            truth = (d0_ready and d1_ready, "baseline_plan_dependencies_incomplete")
        elif concept == "flexible_load_plan":
            truth = (d0_ready and d1_ready and flexible_ready, "flexible_plan_dependencies_incomplete")
        if truth is None:
            continue
        ready, reason = truth
        row["status"] = "READY" if ready else "INCOMPLETE"
        if ready:
            row.pop("reason", None)
        else:
            row["reason"] = reason

    plan_complete = d0_ready and d1_ready
    for row in intelligence_rows:
        if not isinstance(row, dict):
            continue
        concept = str(row.get("concept_id") or "")
        if concept in {"operational_plan", "energy_outlook", "cost_outlook", "energy_intelligence", "planning_experience"}:
            row["status"] = "READY" if plan_complete else "INCOMPLETE"
            if plan_complete:
                row.pop("reason", None)
            else:
                row["reason"] = "operational_plan_dependencies_incomplete"

    def health(rows):
        states = {str(row.get("status") or "INCOMPLETE") for row in rows if isinstance(row, dict)}
        if states and states == {"READY"}:
            return "OK"
        if "READY" in states:
            return "DEGRADED"
        return "INCOMPLETE"

    return systems, planning, intelligence_rows, {
        "system": health(systems),
        "planning": health(planning),
        "intelligence": health(intelligence_rows),
    }


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
        battery_values = [facts.get("battery.power_kw"), facts.get("battery.soc_pct"), facts.get("battery.capacity_kwh"), facts.get("battery.available_kwh")]
        known = sum(value is not None for value in battery_values)
        facts["battery.health"] = "OK" if known >= 2 else "DEGRADED" if batteries and known else "UNKNOWN"
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
        producer_available = bool((self.snapshot.get("producer_publication_availability") or {}).get("mobility"))
        facts, inconsistent = close_current_energy_facts(self.snapshot.get("facts") or {}, flexible, producer_available)
        if inconsistent:
            issues = list(self.snapshot.get("runtime_issues") or [])
            issues.append("consumption_split_inconsistent:flexible_exceeds_site")
            self.snapshot["runtime_issues"] = sorted(set(issues))

        settings = deepcopy(self.store.data.get("settings") or {})
        settings["baseload_profile"] = deepcopy((self.store.data.get("metering") or {}).get("baseload_profile") or {})
        now_local = datetime.now(ZoneInfo(self.hass.config.time_zone))
        plan = close_planning_views(deterministic_plan(facts, settings, flexible, now_local), flexible)
        intel = intelligence(plan, facts, settings, flexible)
        overview = overview_snapshot(facts)
        systems, planning, intelligence_rows, runtime_health = _runtime_layers(self.model, facts, plan, flexible, producer_available)
        layer_health = deepcopy(self.model.get("layer_health") or {})
        layer_health.update(runtime_health)

        self._canonical_snapshot_revision += 1
        self.snapshot.update({
            "facts": facts,
            "plan": plan,
            "intelligence": intel,
            "overview": overview,
            "snapshot_revision": self._canonical_snapshot_revision,
            "observed_at": datetime.now(UTC).isoformat(),
            "generation": deepcopy(self.model.get("generation") or {}),
            "layer_health": layer_health,
            "system_assets": systems,
            "planning_assets": planning,
            "intelligence_assets": intelligence_rows,
            "model_fingerprint": self.model.get("model_fingerprint"),
            "dependency_diagnostics": deepcopy(self.model.get("dependency_diagnostics") or {}),
        })
