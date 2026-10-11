"""Immutable-source planning input contract for all Energy optimizer adapters.

This boundary rejects incomplete pricing, estimated daily-sine solar, missing
battery constraints, fabricated baseload and unverified source provenance.
Native adapters consume this contract, not Home Assistant entity scans.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any

CONTRACT = "RHI_ENERGY_PLANNING_CONTEXT_V1"
STEP_MINUTES = frozenset({15, 30, 60})
REQUIRED_SLOT_VALUES = (
    "solar_generation_kwh", "home_baseload_kwh",
    "import_price_eur_kwh", "export_price_eur_kwh",
)
REQUIRED_BATTERY_FIELDS = (
    "capacity_kwh", "soc_pct", "min_soc_pct", "max_soc_pct",
    "max_charge_power_kw", "max_discharge_power_kw",
    "charge_efficiency", "discharge_efficiency",
)

def _stamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("planning_timestamp_missing:" + path)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("planning_timestamp_invalid:" + path) from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("planning_timestamp_not_utc:" + path)
    return dt.astimezone(timezone.utc)

def _number(value: Any, path: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("planning_value_missing_or_nonfinite:" + path)
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError("planning_value_out_of_bounds:" + path)
    return float(value)

def _source(source: Any, path: str) -> None:
    if not isinstance(source, dict):
        raise ValueError("planning_source_evidence_missing:" + path)
    if source.get("availability") != "AVAILABLE":
        raise ValueError("planning_source_unavailable:" + path)
    if not isinstance(source.get("binding_id"), str) or not source["binding_id"]:
        raise ValueError("planning_source_identity_missing:" + path)
    _stamp(source.get("observed_at"), path + ".observed_at")

def validate_planning_context(data: Any, *, hours: int = 24) -> dict[str, Any]:
    """Fail closed on any incomplete/ambiguous interval in the requested horizon."""
    if not isinstance(data, dict) or data.get("contract_id") != CONTRACT:
        raise ValueError("planning_context_contract_invalid")
    if isinstance(hours, bool) or not isinstance(hours, int) or hours not in (24, 48):
        raise ValueError("planning_context_horizon_unsupported")
    if data.get("time_zone") != "UTC":
        raise ValueError("planning_context_timezone_invalid")
    _stamp(data.get("generated_at"), "generated_at")
    grid = data.get("site")
    if not isinstance(grid, dict):
        raise ValueError("planning_site_capacity_missing")
    for key in ("grid_import_limit_kw", "grid_export_limit_kw"):
        _number(grid.get(key), "site." + key, positive=True)
    _source(grid.get("source"), "site.source")
    batteries = data.get("batteries")
    if not isinstance(batteries, list):
        raise ValueError("planning_battery_list_missing")
    seen_batteries = set()
    for index, battery in enumerate(batteries):
        path = f"batteries[{index}]"
        if not isinstance(battery, dict):
            raise ValueError("planning_battery_invalid:" + path)
        uid = battery.get("asset_id")
        if not isinstance(uid, str) or not uid or uid in seen_batteries:
            raise ValueError("planning_battery_identity_invalid:" + path)
        seen_batteries.add(uid)
        for key in REQUIRED_BATTERY_FIELDS:
            val = _number(battery.get(key), path + "." + key,
                          positive=key in ("capacity_kwh", "max_charge_power_kw", "max_discharge_power_kw",
                                           "charge_efficiency", "discharge_efficiency"),
                          nonnegative=key in ("soc_pct", "min_soc_pct", "max_soc_pct"))
            if key.endswith("_pct") and val > 100 or key.endswith("_efficiency") and val > 1:
                raise ValueError("planning_battery_constraint_invalid:" + path + "." + key)
        if not battery["min_soc_pct"] <= battery["soc_pct"] <= battery["max_soc_pct"]:
            raise ValueError("planning_battery_soc_outside_bounds:" + path)
        _source(battery.get("source"), path + ".source")
    loads = data.get("flexible_loads")
    if not isinstance(loads, list):
        raise ValueError("planning_flexible_loads_missing")
    seen_loads = set()
    for index, load in enumerate(loads):
        path = f"flexible_loads[{index}]"
        if not isinstance(load, dict):
            raise ValueError("planning_flexible_load_invalid:" + path)
        uid = load.get("asset_id")
        if not isinstance(uid, str) or not uid or uid in seen_loads:
            raise ValueError("planning_flexible_load_identity_invalid:" + path)
        seen_loads.add(uid)
        _number(load.get("energy_need_kwh"), path + ".energy_need_kwh", nonnegative=True)
        _number(load.get("max_power_kw"), path + ".max_power_kw", positive=True)
        _stamp(load.get("ready_by_utc"), path + ".ready_by_utc")
        _source(load.get("source"), path + ".source")
    slots = data.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("planning_intervals_missing")
    requested_seconds = hours * 3600
    first = None
    prior_end = None
    step = None
    for index, slot in enumerate(slots):
        path = f"slots[{index}]"
        if not isinstance(slot, dict):
            raise ValueError("planning_interval_invalid:" + path)
        start = _stamp(slot.get("start_utc"), path + ".start_utc")
        end = _stamp(slot.get("end_utc"), path + ".end_utc")
        if first is None:
            first = start
        if prior_end is not None and start != prior_end:
            raise ValueError("planning_interval_gap_or_overlap:" + path)
        minutes = (end - start).total_seconds() / 60
        if minutes not in STEP_MINUTES or (step is not None and minutes != step):
            raise ValueError("planning_interval_resolution_invalid:" + path)
        step = minutes
        prior_end = end
        for key in REQUIRED_SLOT_VALUES:
            _number(slot.get(key), path + "." + key,
                    nonnegative=key in ("solar_generation_kwh", "home_baseload_kwh"))
        provenance = slot.get("sources")
        if not isinstance(provenance, dict):
            raise ValueError("planning_interval_sources_missing:" + path)
        for key in REQUIRED_SLOT_VALUES:
            _source(provenance.get(key), path + ".sources." + key)
    if first is None or prior_end is None or (prior_end - first).total_seconds() != requested_seconds:
        raise ValueError("planning_context_horizon_incomplete")
    # Canonical JSON provides a stable, versioned source-evidence fingerprint.
    normalized = json.loads(json.dumps(data, sort_keys=True, allow_nan=False))
    normalized["planning_context_fingerprint"] = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return normalized
