"""Canonical V2 parity semantics for the frozen R1 Energy UX."""
from __future__ import annotations

from copy import deepcopy


def _number(value):
    try:
        if value is None or str(value).lower() in {"unknown", "unavailable", "none", ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def complete_flexible_power(assets, producer_available: bool):
    if not producer_available:
        return None
    if not assets:
        return 0.0
    values = [_number(asset.get("power_kw")) for asset in assets]
    if any(value is None for value in values):
        return None
    return round(sum(values), 6)


def battery_state(facts):
    power = _number(facts.get("battery.power_kw"))
    if power is not None:
        if power > 0.05:
            return "discharging"
        if power < -0.05:
            return "charging"
        return "idle"
    raw = str(facts.get("battery.status") or "").strip().lower()
    if raw in {"charging", "charge"}:
        return "charging"
    if raw in {"discharging", "discharge"}:
        return "discharging"
    if raw in {"idle", "standby", "available", "ready"}:
        return "idle"
    return raw or None


def grid_direction(facts):
    grid_import = _number(facts.get("grid_import.power_kw"))
    grid_export = _number(facts.get("grid_export.power_kw"))
    if grid_export is not None and grid_export > 0.05:
        return "exporting"
    if grid_import is not None and grid_import > 0.05:
        return "importing"
    if grid_import is not None and grid_export is not None:
        return "balanced"
    return None


def close_current_energy_facts(facts, flexible_assets, producer_available: bool):
    """Split total site demand into frozen R1 site/home/flexible semantics."""
    out = deepcopy(facts)
    site = _number(out.get("home_consumption.power_kw"))
    flexible = complete_flexible_power(flexible_assets, producer_available)
    home = None
    inconsistent = False
    if site is not None and flexible is not None:
        residual = site - flexible
        if residual >= -0.08:
            home = round(max(0.0, residual), 6)
        else:
            inconsistent = True
    out["site_consumption.power_kw"] = site
    out["flexible_loads.power_kw"] = flexible
    out["home_consumption.power_kw"] = home
    out["consumption.power_kw"] = site
    out["consumption.health"] = (
        "OK" if site is not None and home is not None else "DEGRADED" if site is not None else "UNAVAILABLE"
    )
    out["battery.state"] = battery_state(out)
    out["grid.flow_direction"] = grid_direction(out)
    return out, inconsistent


def close_planning_views(plan, flexible_assets):
    """Publish Planning-owned aliases consumed by the frozen R1 UX."""
    out = deepcopy(plan)
    horizons = out.get("planning_horizons") or {}
    lane_totals = {
        horizon_id: deepcopy(((row.get("summary") or {}).get("lane_totals") or {}))
        for horizon_id, row in horizons.items()
        if isinstance(row, dict)
    }
    d0 = horizons.get("D0") or {}
    buckets = [row for row in (d0.get("buckets") or []) if isinstance(row, dict)]
    out["planning_assets"] = deepcopy(flexible_assets)
    out["planning_assets_by_id"] = {
        str(row.get("asset_id")): deepcopy(row)
        for row in flexible_assets
        if isinstance(row, dict) and row.get("asset_id")
    }
    out["planning_lane_totals"] = lane_totals
    out["planning_horizon_totals"] = deepcopy(lane_totals)
    out["planning_today_totals"] = deepcopy(lane_totals.get("D0") or {})
    out["current_planning_bucket"] = deepcopy(buckets[0]) if buckets else {}
    return out
