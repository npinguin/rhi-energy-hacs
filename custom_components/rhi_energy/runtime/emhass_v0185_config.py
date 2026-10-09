"""Native EMHASS 0.18.5 config projection from canonical RHI equipment.

Units are explicit: W, Wh and fractions. Never collapse separate batteries.
This produces EMHASS config keys; it does not silently assume that every
config key is accepted as an optimization runtime parameter.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

from .emhass_native import NativeCapabilityError


def _number(row: dict[str, Any], key: str, *, minimum: float = 0) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NativeCapabilityError(f"{row.get('asset_id', 'asset')}:{key}_missing")
    value = float(value)
    if not isfinite(value) or value < minimum:
        raise NativeCapabilityError(f"{row.get('asset_id', 'asset')}:{key}_invalid")
    return value


def native_battery_config(batteries: list[dict[str, Any]]) -> dict[str, Any]:
    """Map individual battery capability rows to EMHASS 0.18.5 native config.

    Expected RHI normalized inputs: capacity_kwh, charge_max_kw,
    discharge_max_kw, soc_min_pct, soc_max_pct, charge_efficiency,
    discharge_efficiency. SOC is 0-100%; efficiencies are 0-1.
    """
    if not batteries:
        return {"set_use_battery": False}
    ids = [str(x.get("asset_id") or "") for x in batteries]
    if not all(ids) or len(ids) != len(set(ids)):
        raise NativeCapabilityError("battery_identity_missing_or_duplicate")
    result: dict[str, Any] = {
        "set_use_battery": True,
        "number_of_batteries": len(batteries),
    }
    columns = {
        "battery_nominal_energy_capacity": ("capacity_kwh", 1000),
        "battery_charge_power_max": ("charge_max_kw", 1000),
        "battery_discharge_power_max": ("discharge_max_kw", 1000),
        "battery_minimum_state_of_charge": ("soc_min_pct", 0.01),
        "battery_maximum_state_of_charge": ("soc_max_pct", 0.01),
        "battery_charge_efficiency": ("charge_efficiency", 1),
        "battery_discharge_efficiency": ("discharge_efficiency", 1),
    }
    for native_key, (source_key, factor) in columns.items():
        values = [_number(row, source_key) * factor for row in batteries]
        result[native_key] = values if len(values) > 1 else values[0]
    for row in batteries:
        low = _number(row, "soc_min_pct")
        high = _number(row, "soc_max_pct")
        if not (0 <= low < high <= 100):
            raise NativeCapabilityError(f"{row['asset_id']}:soc_bounds_invalid")
        for key in ("charge_efficiency", "discharge_efficiency"):
            if not 0 < _number(row, key) <= 1:
                raise NativeCapabilityError(f"{row['asset_id']}:{key}_invalid")
    return result


def native_deferrable_config(loads: list[dict[str, Any]]) -> dict[str, Any]:
    """Preserve each independent flexible load and its timing constraints."""
    ids = [str(x.get("asset_id") or "") for x in loads]
    if not all(ids) or len(ids) != len(set(ids)):
        raise NativeCapabilityError("flexible_load_identity_missing_or_duplicate")
    result = {
        "number_of_deferrable_loads": len(loads),
        "nominal_power_of_deferrable_loads": [],
        "minimum_power_of_deferrable_loads": [],
        "operating_hours_of_each_deferrable_load": [],
        "start_timesteps_of_each_deferrable_load": [],
        "end_timesteps_of_each_deferrable_load": [],
    }
    for row in loads:
        result["nominal_power_of_deferrable_loads"].append(_number(row, "nominal_kw") * 1000)
        result["minimum_power_of_deferrable_loads"].append(_number(row, "minimum_kw") * 1000)
        result["operating_hours_of_each_deferrable_load"].append(_number(row, "operating_hours"))
        start_step = _number(row, "start_timestep")
        end_step = _number(row, "end_timestep")
        if not start_step.is_integer() or not end_step.is_integer():
            raise NativeCapabilityError(f"{row['asset_id']}:non_integer_timestep")
        result["start_timesteps_of_each_deferrable_load"].append(int(start_step))
        result["end_timesteps_of_each_deferrable_load"].append(int(end_step))
        if row["minimum_kw"] > row["nominal_kw"] or row["end_timestep"] < row["start_timestep"]:
            raise NativeCapabilityError(f"{row['asset_id']}:load_bounds_invalid")
    return result


def native_grid_config(*, import_limit_kw: float, export_limit_kw: float) -> dict[str, float]:
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) or x < 0
           for x in (import_limit_kw, export_limit_kw)):
        raise NativeCapabilityError("grid_limits_invalid")
    return {
        "maximum_power_from_grid": import_limit_kw * 1000,
        "maximum_power_to_grid": export_limit_kw * 1000,
    }
