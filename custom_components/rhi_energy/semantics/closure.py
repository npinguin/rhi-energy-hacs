from __future__ import annotations
from copy import deepcopy


def derive_consumption(number, solar_kw, grid_net_kw, battery_kw, max_home_kw=None):
    values = [number(v) for v in (solar_kw, grid_net_kw, battery_kw)]
    if any(v is None for v in values):
        return {"power_kw": None, "health": "UNAVAILABLE", "reason": "required_energy_balance_input_missing", "raw_balance_kw": None}
    raw = sum(values)
    if raw < -0.08:
        return {"power_kw": None, "health": "DEGRADED", "reason": "physical_balance_inconsistent_negative_balance_above_deadband", "raw_balance_kw": round(raw, 3)}
    value = max(0.0, raw)
    if max_home_kw is not None and value > float(max_home_kw):
        return {"power_kw": None, "health": "DEGRADED", "reason": "implausible_home_consumption_above_configured_site_limit", "raw_balance_kw": round(raw, 3)}
    return {"power_kw": round(value, 3), "health": "OK", "reason": "derived_from_energy_balance", "raw_balance_kw": round(raw, 3)}


def overview_snapshot(number, split_battery_power, available, facts, demand_breakdown=None):
    solar = number(facts.get("solar.power_kw")); home = number(facts.get("home_consumption.power_kw"))
    gi = number(facts.get("grid_import.power_kw")); ge = number(facts.get("grid_export.power_kw"))
    bp = number(facts.get("battery.power_kw")); soc = number(facts.get("battery.soc_pct"))
    charge, discharge = split_battery_power(bp)
    complete = all(v is not None for v in (solar, home, gi, ge))
    if not complete: code, title, primary, key = "unavailable", "Energy data unavailable", None, "home_consumption.power_kw"
    elif ge > 0.05: code, title, primary, key = "exporting", "Exporting surplus", ge, "grid_export.power_kw"
    elif gi > 0.05: code, title, primary, key = "importing", "Importing from grid", gi, "grid_import.power_kw"
    elif discharge is not None and discharge > 0.05: code, title, primary, key = "battery_support", "Battery supporting home", home, "home_consumption.power_kw"
    elif solar > 0.05: code, title, primary, key = "self_powered", "Solar powering home", home, "home_consumption.power_kw"
    else: code, title, primary, key = "idle", "Energy balanced", home, "home_consumption.power_kw"
    return {
        "schema": "energy_overview_snapshot_v3",
        "status": {"code": code, "title": title, "available": complete},
        "primary_metric": {"value": round(primary, 3) if primary is not None else None, "unit": "kW", "property_key": key},
        "summary": {"solar_power_kw": solar, "home_consumption_power_kw": home, "home_power_kw": home, "grid_import_power_kw": gi, "grid_export_power_kw": ge, "battery_charge_power_kw": charge, "battery_discharge_power_kw": discharge, "battery_soc_pct": soc},
        "flow": {"sources": [{"participant_id": "solar", "power_kw": solar}, {"participant_id": "battery", "power_kw": discharge}, {"participant_id": "grid", "direction": "import", "power_kw": gi}], "demands": deepcopy(demand_breakdown or [])},
        "ownership": {"status_and_primary_metric": "sensor.energy_overview_experience", "physical_facts": "domain_property_indexes", "ux_recalculation_allowed": False},
        "complete": complete,
        "optional_battery_flow_available": bp is not None,
    }


def enrich_plan(number, available, incomplete, plan, flexible_assets):
    horizons = plan.get("planning_horizons") or {}
    baseline_ready = bool(horizons) and all((row or {}).get("quality", {}).get("availability") == available for row in horizons.values())
    participating = sum(number(a.get("energy_to_target_kwh")) is not None for a in flexible_assets)
    flexible_ready = baseline_ready and participating > 0
    plan["baseline_plan"] = {"availability": available if baseline_ready else incomplete, "horizon_ids": sorted(horizons)}
    plan["flexible_plan"] = {"availability": available if flexible_ready else incomplete, "participating_asset_count": participating, "reason": None if flexible_ready else "producer_needs_or_constraints_incomplete"}
    plan["planning_mode"] = "BASELINE_AND_FLEXIBLE" if flexible_ready else "BASELINE_ONLY" if baseline_ready else "INCOMPLETE"
    return plan
