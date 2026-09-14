"""Backward-compatible R1 facade closure over canonical V2 truth.

This module may rename, group and serialize V2 facts. It must not read Home Assistant,
Foundation or producer integrations directly and must not create new business meaning.
"""
from __future__ import annotations

from copy import deepcopy
import json

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"


def _loads(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return deepcopy(default)
    return deepcopy(value) if value is not None else deepcopy(default)


def _dumps(value):
    return json.dumps(value, separators=(",", ":"), default=str)


def _row(key, value, unit="", *, asset_id=None):
    availability = AVAILABLE if value is not None else UNAVAILABLE
    return {
        "asset_id": asset_id or key.split(".", 1)[0],
        "property_id": key,
        "key": key,
        "value": value,
        "unit": unit,
        "availability": availability,
        "health": "OK" if availability == AVAILABLE else availability,
        "editable": False,
        "write_supported": False,
        "source_type": "canonical_v2_runtime",
        "quality": "authoritative" if value is not None else "unknown",
    }


def _property_rows(attrs):
    rows = _loads(attrs.get("properties_json") or attrs.get("properties"), [])
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [deepcopy(row) for row in rows if isinstance(row, dict)]


def _upsert_rows(attrs, additions):
    rows = _property_rows(attrs)
    by_key = {
        str(row.get("key") or row.get("property_key") or row.get("property_id") or ""): row
        for row in rows
        if str(row.get("key") or row.get("property_key") or row.get("property_id") or "")
    }
    for row in additions:
        by_key[str(row["key"])] = deepcopy(row)
    ordered = list(by_key.values())
    attrs["properties"] = _dumps(ordered)
    attrs["properties_json"] = _dumps(ordered)
    attrs["properties_by_key"] = _dumps({str(row.get("key")): row for row in ordered if row.get("key")})
    return ordered


def close_v1_projection(projections, v2):
    """Close only frozen UX fields that already exist canonically in V2."""
    out = deepcopy(projections)
    facts = deepcopy(v2.get("facts") or {})
    plan = deepcopy(v2.get("planning") or {})

    consumption = out.get("energy_consumption_property_index")
    if isinstance(consumption, dict):
        attrs = consumption.setdefault("attributes", {})
        site = facts.get("site_consumption.power_kw")
        home = facts.get("home_consumption.power_kw")
        flexible = facts.get("flexible_loads.power_kw")
        rows = _upsert_rows(
            attrs,
            [
                _row("site_consumption.power_kw", site, "kW", asset_id="site_consumption"),
                _row("home_consumption.power_kw", home, "kW", asset_id="home_consumption"),
                _row("flexible_loads.power_kw", flexible, "kW", asset_id="flexible_loads"),
            ],
        )
        breakdown = [
            {"row_id": "site_consumption", "asset_id": "site_consumption", "power_kw": site, "availability": AVAILABLE if site is not None else UNAVAILABLE},
            {"row_id": "home_consumption", "asset_id": "home_consumption", "power_kw": home, "availability": AVAILABLE if home is not None else UNAVAILABLE},
            {"row_id": "flexible_loads", "asset_id": "flexible_loads", "power_kw": flexible, "availability": AVAILABLE if flexible is not None else UNAVAILABLE},
        ]
        attrs["demand_export_breakdown_json"] = _dumps(breakdown)
        attrs["site_consumption"] = _dumps(breakdown[0])
        attrs["home_consumption"] = _dumps(breakdown[1])
        attrs["flexible_loads"] = _dumps(breakdown[2])
        consumption["state"] = AVAILABLE if any(row.get("value") is not None for row in rows) else UNAVAILABLE

    battery = out.get("energy_battery_property_index")
    if isinstance(battery, dict):
        attrs = battery.setdefault("attributes", {})
        state = facts.get("battery.state")
        power = facts.get("battery.power_kw")
        _upsert_rows(attrs, [_row("battery.state", state, asset_id="battery")])
        attrs["state"] = state
        attrs["flow_projection_json"] = _dumps(
            {
                "state": state,
                "power_kw": abs(float(power)) if isinstance(power, (int, float)) else None,
                "flow_role": "producer" if state == "discharging" else "consumer" if state == "charging" else "inactive" if state == "idle" else "unknown",
                "ux_visible": state is not None,
            }
        )

    grid = out.get("energy_grid_property_index")
    if isinstance(grid, dict):
        attrs = grid.setdefault("attributes", {})
        direction = facts.get("grid.flow_direction")
        _upsert_rows(attrs, [_row("grid.flow_direction", direction, asset_id="grid")])

    planning = out.get("energy_planning_index")
    if isinstance(planning, dict):
        attrs = planning.setdefault("attributes", {})
        planning_assets = deepcopy(plan.get("planning_assets") or v2.get("flexible_assets") or [])
        planning_assets_by_id = deepcopy(plan.get("planning_assets_by_id") or {})
        lane_totals = deepcopy(plan.get("planning_lane_totals") or {})
        horizon_totals = deepcopy(plan.get("planning_horizon_totals") or lane_totals)
        attrs["planning_assets_json"] = _dumps(planning_assets)
        attrs["planning_assets"] = _dumps(planning_assets)
        attrs["planning_assets_by_id"] = _dumps(planning_assets_by_id)
        attrs["planning_today_totals_json"] = _dumps(plan.get("planning_today_totals") or {})
        attrs["planning_lane_totals_json"] = _dumps(lane_totals)
        attrs["planning_horizon_totals_json"] = _dumps(horizon_totals)
        attrs["planning_horizon_totals_by_id"] = _dumps(horizon_totals)
        attrs["current_planning_bucket"] = _dumps(plan.get("current_planning_bucket") or {})

    return out
