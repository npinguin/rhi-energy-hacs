"""Runtime readiness evaluation for the fixed Energy layer topology.

This module is deliberately pure: it consumes canonical runtime evidence and marks the
already-materialized topology. It never discovers assets or mutates structural truth.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .presence import concept_present
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    concept_present = _runpy.run_path(str(_Path(__file__).with_name("presence.py")))["concept_present"]


def _layer_health(rows: list[dict[str, Any]]) -> str:
    states = {
        str(row.get("status") or "INCOMPLETE")
        for row in rows
        if isinstance(row, dict)
        and str(row.get("status") or "INCOMPLETE") != "NOT_APPLICABLE"
    }
    if not states or states == {"READY"}:
        return "OK"
    if "READY" in states:
        return "DEGRADED"
    return "INCOMPLETE"


def evaluate_runtime_layers(
    model: dict[str, Any] | None,
    metering: dict[str, Any],
    facts: dict[str, Any],
    flexible: list[dict[str, Any]],
    logical_assets: list[dict[str, Any]],
    producer_available: bool,
    plan: dict[str, Any],
    intel: dict[str, Any],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Evaluate runtime readiness while separating absence from incompleteness."""
    model = model or {}
    systems = deepcopy(model.get("system_assets") or [])
    planning = deepcopy(model.get("planning_assets") or [])
    intelligence_rows = deepcopy(model.get("intelligence_assets") or [])
    meter_today = (((metering or {}).get("periods") or {}).get("today") or {})
    d0 = (plan.get("planning_horizons") or {}).get("D0") or {}
    d1 = (plan.get("planning_horizons") or {}).get("D1") or {}
    d0_ready = ((d0.get("quality") or {}).get("availability") == "AVAILABLE")
    d1_ready = ((d1.get("quality") or {}).get("availability") == "AVAILABLE")
    active_flexible = [
        row for row in flexible
        if str(row.get("lifecycle_status") or row.get("lifecycle_state") or "active").lower() not in {"disabled", "inactive"}
        and str(row.get("participation_state") or "participating").lower() == "participating"
        and row.get("planning_input_ready", True) is not False
        and row.get("infrastructure_only", False) is not True
    ]
    flex_ready = producer_available and all(row.get("power_kw") is not None for row in active_flexible)
    battery_present = concept_present(model, "battery_system", logical_assets)
    pricing_present = concept_present(model, "price_source", logical_assets)

    system_ready = {
        "battery_system": all(facts.get(key) is not None for key in ("battery.power_kw", "battery.soc_pct", "battery.capacity_kwh", "battery.available_kwh")),
        "solar_production_system": facts.get("solar.power_kw") is not None,
        "site_energy_balance": facts.get("site_consumption.power_kw") is not None,
        "home_consumption": facts.get("home_consumption.power_kw") is not None,
        "solar_forecast_system": facts.get("forecast.solar_today_kwh") is not None,
        "pricing_system": facts.get("pricing.import_price_current_eur_kwh") is not None,
        "flexible_load_system": flex_ready,
        "connection_system": producer_available,
        "metering_system": str(meter_today.get("quality") or "UNKNOWN") == "OK",
        "strategy_system": bool(settings.get("strategy")),
        "value_accounting_system": str(meter_today.get("quality") or "UNKNOWN") == "OK" and facts.get("pricing.import_price_current_eur_kwh") is not None,
        "grid_system": facts.get("grid.net_power_kw") is not None and facts.get("site_consumption.power_kw") is not None,
    }
    for row in systems:
        concept = str(row.get("concept_id") or "")
        if (
            (concept == "battery_system" and not battery_present)
            or (concept in {"pricing_system", "value_accounting_system"} and not pricing_present)
        ):
            row["status"] = "NOT_APPLICABLE"
            row["reason"] = "capability_not_configured"
            continue
        ready = bool(system_ready.get(concept, False))
        row["status"] = "READY" if ready else "INCOMPLETE"
        if ready:
            row.pop("reason", None)
        else:
            row["reason"] = "runtime_evidence_incomplete"

    planning_inputs_ready = producer_available and all(
        row.get("planning_input_ready") is True
        for row in flexible
        if str(row.get("participation_state") or "participating").lower() == "participating"
        and row.get("infrastructure_only", False) is not True
    )
    planning_ready = {
        "planning_model": d0_ready and d1_ready,
        "planning_asset": all(facts.get(key) is not None for key in ("battery.capacity_kwh", "battery.available_kwh")),
        "planning_pricing": facts.get("pricing.import_price_current_eur_kwh") is not None,
        "constraint_set": bool(settings.get("strategy")),
        "energy_need": planning_inputs_ready,
        "allocation_set": d0_ready,
        "baseline_energy_plan": d0_ready and d1_ready,
        "flexible_load_plan": d0_ready and d1_ready and planning_inputs_ready,
    }
    for row in planning:
        aid = str(row.get("asset_id") or "")
        concept = str(row.get("concept_id") or "")
        if (
            (concept == "planning_asset" and aid.endswith("battery") and not battery_present)
            or (concept == "planning_pricing" and not pricing_present)
        ):
            row["status"] = "NOT_APPLICABLE"
            row["reason"] = "capability_not_configured"
            continue
        ready = planning_ready.get(concept, False)
        if concept == "planning_horizon":
            ready = d0_ready if aid.endswith("D0") else d1_ready if aid.endswith("D1") else False
        elif concept == "planning_supply":
            ready = facts.get("forecast.solar_today_kwh") is not None if aid.endswith("solar") else facts.get("site_consumption.power_kw") is not None
        elif concept == "planning_demand":
            ready = flex_ready if aid.endswith("flexible") else facts.get("home_consumption.power_kw") is not None
        row["status"] = "READY" if bool(ready) else "INCOMPLETE"
        if ready:
            row.pop("reason", None)
        else:
            row["reason"] = "runtime_evidence_incomplete"

    intel_ready = {
        "operational_plan": d0_ready,
        "energy_outlook": d0_ready,
        "cost_outlook": d0_ready and facts.get("pricing.import_price_current_eur_kwh") is not None,
        "resilience_state": facts.get("battery.available_kwh") is not None,
        "optimization_opportunity": intel.get("availability") == "AVAILABLE",
        "energy_intelligence": intel.get("availability") == "AVAILABLE",
        "planning_experience": d0_ready and intel.get("availability") == "AVAILABLE",
        "energy_retrospective": str(meter_today.get("quality") or "UNKNOWN") == "OK",
    }
    for row in intelligence_rows:
        concept = str(row.get("concept_id") or "")
        if (
            (concept == "resilience_state" and not battery_present)
            or (concept == "cost_outlook" and not pricing_present)
        ):
            row["status"] = "NOT_APPLICABLE"
            row["reason"] = "capability_not_configured"
            continue
        ready = bool(intel_ready.get(concept, False))
        row["status"] = "READY" if ready else "INCOMPLETE"
        if ready:
            row.pop("reason", None)
        else:
            row["reason"] = "runtime_evidence_incomplete"

    runtime_logical = [row for row in logical_assets if row.get("runtime_truth")]
    logical_states = {str(row.get("health") or "UNKNOWN") for row in runtime_logical}
    logical_health = (
        "OK" if runtime_logical and logical_states == {"OK"}
        else "DEGRADED" if any(state == "OK" for state in logical_states)
        else "INCOMPLETE"
    )
    health = {
        "logical": logical_health,
        "system": _layer_health(systems),
        "planning": _layer_health(planning),
        "intelligence": _layer_health(intelligence_rows),
    }
    return systems, planning, intelligence_rows, health
