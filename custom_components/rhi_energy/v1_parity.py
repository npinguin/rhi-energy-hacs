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


def _number_equal(left, right, tolerance=1e-6):
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _public_value(projections, object_id, key):
    projection = projections.get(object_id) or {}
    attrs = projection.get("attributes") or {}
    rows = _loads(attrs.get("properties_by_key"), {})
    row = rows.get(key) if isinstance(rows, dict) else None
    return row.get("value") if isinstance(row, dict) else None


def projection_consistency_issues(projections, v2):
    """Return semantic parity defects between final V1 projections and canonical V2.

    This verifier is deliberately narrow and pure: it only compares already-canonical
    facts with the public fields that represent those same facts. It performs no
    discovery, normalization or business derivation.
    """
    facts = v2.get("facts") or {}
    checks = {
        "energy_grid_property_index": (
            "grid.net_power_kw",
            "grid_import.power_kw",
            "grid_export.power_kw",
            "grid.flow_direction",
        ),
        "energy_battery_property_index": (
            "battery.power_kw",
            "battery.soc_pct",
            "battery.capacity_kwh",
            "battery.available_kwh",
            "battery.state",
        ),
        "energy_consumption_property_index": (
            "site_consumption.power_kw",
            "home_consumption.power_kw",
            "flexible_loads.power_kw",
        ),
    }
    issues = {}
    for object_id, keys in checks.items():
        mismatches = []
        for key in keys:
            canonical = facts.get(key)
            public = _public_value(projections, object_id, key)
            if canonical is None and public is None:
                continue
            if not _number_equal(canonical, public):
                mismatches.append(key)
        if mismatches:
            issues[f"sensor.{object_id}"] = mismatches

    overview = projections.get("energy_overview_experience") or {}
    snapshot = _loads((overview.get("attributes") or {}).get("snapshot_json"), {})
    summary = snapshot.get("summary") if isinstance(snapshot, dict) else {}
    overview_map = {
        "solar_power_kw": "solar.power_kw",
        "site_consumption_power_kw": "site_consumption.power_kw",
        "home_consumption_power_kw": "home_consumption.power_kw",
        "grid_import_power_kw": "grid_import.power_kw",
        "grid_export_power_kw": "grid_export.power_kw",
        "battery_soc_pct": "battery.soc_pct",
    }
    mismatches = []
    for public_key, canonical_key in overview_map.items():
        canonical = facts.get(canonical_key)
        public = (summary or {}).get(public_key)
        if canonical is None and public is None:
            continue
        # Overview intentionally rounds display values.
        if isinstance(canonical, (int, float)) and isinstance(public, (int, float)):
            if abs(float(canonical) - float(public)) > 0.011:
                mismatches.append(canonical_key)
        elif canonical != public:
            mismatches.append(canonical_key)
    if mismatches:
        issues["sensor.energy_overview_experience"] = mismatches
    return issues


def _refresh_standard_health(out, v2):
    issues = projection_consistency_issues(out, v2)
    diagnostic = out.get("energy_home_intelligence_contract_standard_health")
    if not isinstance(diagnostic, dict):
        return issues
    attrs = diagnostic.setdefault("attributes", {})
    current = [
        str(value)
        for value in _loads(attrs.get("degraded_public_entities_json"), [])
        if value
    ]
    degraded = sorted(set(current) | set(issues))
    if degraded:
        diagnostic["state"] = "DEGRADED"
        attrs["health"] = "DEGRADED"
        attrs["health_reason"] = "public_projection_not_consistent_with_canonical_v2"
    else:
        diagnostic["state"] = "OK"
        attrs["health"] = "OK"
        attrs["health_reason"] = "all_product_v1_projections_functional_and_canonical"
    attrs["degraded_public_entities_json"] = _dumps(degraded)
    attrs["canonical_parity_issues_json"] = _dumps(issues)
    return issues


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
        soc = facts.get("battery.soc_pct")
        capacity = facts.get("battery.capacity_kwh")
        available = facts.get("battery.available_kwh")
        _upsert_rows(
            attrs,
            [
                _row("battery.power_kw", power, "kW", asset_id="battery"),
                _row("battery.soc_pct", soc, "%", asset_id="battery"),
                _row("battery.capacity_kwh", capacity, "kWh", asset_id="battery"),
                _row("battery.available_kwh", available, "kWh", asset_id="battery"),
                _row("battery.state", state, asset_id="battery"),
            ],
        )
        attrs.update({
            "state": state,
            "power_kw": power,
            "soc_pct": soc,
            "capacity_kwh": capacity,
            "available_kwh": available,
        })
        attrs["flow_projection_json"] = _dumps(
            {
                "state": state,
                "power_kw": abs(float(power)) if isinstance(power, (int, float)) else None,
                "signed_power_kw": power,
                "flow_role": "producer" if state == "discharging" else "consumer" if state == "charging" else "inactive" if state == "idle" else "unknown",
                "ux_visible": power is not None,
            }
        )

    grid = out.get("energy_grid_property_index")
    if isinstance(grid, dict):
        attrs = grid.setdefault("attributes", {})
        net = facts.get("grid.net_power_kw")
        grid_import = facts.get("grid_import.power_kw")
        grid_export = facts.get("grid_export.power_kw")
        direction = facts.get("grid.flow_direction")
        _upsert_rows(
            attrs,
            [
                _row("grid.net_power_kw", net, "kW", asset_id="grid"),
                _row("grid_import.power_kw", grid_import, "kW", asset_id="grid"),
                _row("grid_export.power_kw", grid_export, "kW", asset_id="grid"),
                _row("grid.flow_direction", direction, asset_id="grid"),
            ],
        )
        attrs.update({
            "net_power_kw": net,
            "grid_net_power_kw": net,
            "import_power_kw": grid_import,
            "grid_import_power_kw": grid_import,
            "export_power_kw": grid_export,
            "grid_export_power_kw": grid_export,
            "flow_direction": direction,
        })

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

    _refresh_standard_health(out, v2)
    return out
