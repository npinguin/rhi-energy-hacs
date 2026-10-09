"""Build EMHASS 0.18.5 input exclusively from timestamped, accepted Energy evidence.

This is a pure adapter. Missing interval, property, SOC or load constraint is an
error, not a replacement with zero or an implicit native solver default.
Physical controls remain owned by their producer domains.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import floor, isfinite
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .emhass_inputs import CanonicalHour, PlanningInputError
from .emhass_native import NativeCapabilityError, compose_emhass_request, validate_native_context
from .emhass_v0185_config import native_battery_config, native_deferrable_config, native_grid_config


@dataclass(frozen=True)
class CanonicalEmhassContext:
    payload: dict[str, Any]
    battery_ids: tuple[str, ...]
    flexible_ids: tuple[str, ...]
    timeline_utc: tuple[str, ...]
    provenance: dict[str, Any]


def _timestamp(value: Any, label: str) -> datetime:
    try:
        date = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise PlanningInputError(label + "_invalid_timestamp") from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise PlanningInputError(label + "_missing_timezone")
    return date.astimezone(timezone.utc)


def _finite(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise PlanningInputError(label + "_not_finite")
    value = float(value)
    if nonnegative and value < 0:
        raise PlanningInputError(label + "_negative")
    return value


def _hourly_map(rows: Any, *, key_label: str, value_label: str) -> dict[datetime, float]:
    """Normalize explicit interval-start evidence; never interpolate or extrapolate."""
    result: dict[datetime, float] = {}
    if isinstance(rows, Mapping):
        source_rows = list(rows.items())
    elif isinstance(rows, list):
        source_rows = []
        for row in rows:
            if not isinstance(row, dict):
                raise PlanningInputError(key_label + "_invalid_row")
            at = row.get("time") or row.get("start") or row.get("start_time")
            value = row.get("price") if "price" in row else row.get("value")
            source_rows.append((at, value))
    else:
        raise PlanningInputError(key_label + "_missing")
    for raw_at, raw_value in source_rows:
        at = _timestamp(raw_at, key_label)
        if at.minute or at.second or at.microsecond:
            raise PlanningInputError(key_label + "_not_hourly")
        if at in result:
            raise PlanningInputError(key_label + "_duplicate_slot")
        result[at] = _finite(raw_value, value_label, nonnegative=value_label == "pv_w")
    return result


def _hourly_baseload(profile: dict[str, Any], utc_at: datetime, zone: ZoneInfo) -> float:
    local_hour = utc_at.astimezone(zone).hour
    row = profile.get(f"{local_hour:02d}") if isinstance(profile, dict) else None
    if not isinstance(row, dict) or not isinstance(row.get("samples"), int) or row["samples"] < 1:
        raise PlanningInputError(f"baseload_hour_unlearned:{local_hour:02d}")
    return _finite(row.get("avg_kw"), "baseload_kw", nonnegative=True)


def _battery_rows(
    units: list[dict[str, Any]],
    configured: Mapping[str, dict[str, Any]],
    *,
    reserve_target_pct: float | None,
) -> tuple[list[dict[str, Any]], list[float]]:
    result: list[dict[str, Any]] = []
    live_soc: list[float] = []
    for unit in units:
        aid = str(unit.get("asset_id") or "")
        if not aid or aid not in configured:
            raise NativeCapabilityError("battery_unconfigured:" + aid)
        row = configured[aid]
        capacity = _finite(unit.get("capacity_kwh"), aid + ":capacity_kwh", nonnegative=True)
        soc_pct = _finite(unit.get("soc_pct"), aid + ":soc_pct", nonnegative=True)
        configured_min = _finite(row.get("soc_min_pct"), aid + ":soc_min_pct", nonnegative=True)
        minimum = max(configured_min, reserve_target_pct) if reserve_target_pct is not None else configured_min
        maximum = _finite(row.get("soc_max_pct"), aid + ":soc_max_pct", nonnegative=True)
        if not (capacity > 0 and 0 <= minimum <= soc_pct <= maximum <= 100):
            raise NativeCapabilityError("battery_limits_or_current_soc_invalid:" + aid)
        config = {
            "asset_id": aid,
            "capacity_kwh": capacity,
            "charge_max_kw": _finite(row.get("charge_max_kw"), aid + ":charge_max_kw", nonnegative=True),
            "discharge_max_kw": _finite(row.get("discharge_max_kw"), aid + ":discharge_max_kw", nonnegative=True),
            "soc_min_pct": minimum,
            "soc_max_pct": maximum,
            "charge_efficiency": _finite(row.get("charge_efficiency"), aid + ":charge_efficiency"),
            "discharge_efficiency": _finite(row.get("discharge_efficiency"), aid + ":discharge_efficiency"),
        }
        result.append(config)
        live_soc.append(soc_pct / 100)
    if set(configured) - {row["asset_id"] for row in result}:
        raise NativeCapabilityError("stale_or_extra_battery_configuration")
    return result, live_soc


def _deferrable_rows(
    assets: list[dict[str, Any]],
    start_utc: datetime,
    count: int,
) -> list[dict[str, Any]]:
    rows = []
    for asset in assets:
        if str(asset.get("participation_state") or "participating").lower() != "participating":
            continue
        if asset.get("infrastructure_only") is True:
            continue
        aid = str(asset.get("asset_id") or "")
        if asset.get("planning_input_ready") is not True:
            raise NativeCapabilityError("flexible_planning_input_incomplete:" + aid)
        nominal = _finite(asset.get("max_power_kw"), aid + ":max_power_kw", nonnegative=True)
        minimum = _finite(asset.get("min_power_kw"), aid + ":min_power_kw", nonnegative=True)
        need = _finite(asset.get("energy_to_target_kwh"), aid + ":energy_to_target_kwh", nonnegative=True)
        if nominal <= 0 or minimum > nominal:
            raise NativeCapabilityError("flexible_power_invalid:" + aid)
        deadline = _timestamp(asset.get("ready_by") or asset.get("deadline"), aid + ":deadline")
        available = (deadline - start_utc).total_seconds() / 3600
        end_step = min(count, max(0, floor(available)))
        if available <= 0 or need > end_step * nominal + 1e-8:
            raise NativeCapabilityError("flexible_deadline_infeasible:" + aid)
        min_runtime = _finite(asset.get("minimum_runtime_minutes", 0), aid + ":min_runtime", nonnegative=True)
        if min_runtime > 0 and need + 1e-8 < minimum * min_runtime / 60:
            raise NativeCapabilityError("flexible_minimum_runtime_infeasible:" + aid)
        rows.append({
            "asset_id": aid,
            "nominal_kw": nominal,
            "minimum_kw": minimum,
            "operating_hours": need / nominal,
            "start_timestep": 0,
            "end_timestep": end_step,
        })
    return rows


def build_emhass_context(
    *,
    start_utc: datetime,
    horizon_hours: int,
    local_timezone: str,
    pv_watts: Mapping[str, float],
    import_price_intervals: list[dict[str, Any]],
    currency: str,
    export_price_eur_kwh: float | None,
    baseload_profile: dict[str, Any],
    battery_units: list[dict[str, Any]],
    battery_configuration: Mapping[str, dict[str, Any]],
    flexible_assets: list[dict[str, Any]],
    grid_import_limit_kw: float | None,
    grid_export_limit_kw: float | None,
    reserve_target_pct: float | None = None,
    supported_native_parameters: set[str],
) -> CanonicalEmhassContext:
    """Produce a strict native MPC payload and stable positional asset map.

    The site forecast is Home Consumption only: flexible consumption and battery
    charging remain independent optimization lanes to prevent double counting.
    All time-series slots are UTC-contiguous; local hour learning tolerates DST.
    """
    start = _timestamp(start_utc, "horizon_start")
    if start.minute or start.second or start.microsecond:
        raise PlanningInputError("horizon_start_must_be_hour_boundary")
    if not isinstance(horizon_hours, int) or isinstance(horizon_hours, bool) or not 1 <= horizon_hours <= 48:
        raise PlanningInputError("invalid_horizon_hours")
    if currency != "EUR":
        raise PlanningInputError("unsupported_tariff_currency")
    zone = ZoneInfo(local_timezone)
    pv = _hourly_map(pv_watts, key_label="pv_forecast", value_label="pv_w")
    prices = _hourly_map(import_price_intervals, key_label="import_prices", value_label="import_eur_kwh")
    export_price = _finite(export_price_eur_kwh, "export_eur_kwh")
    hours: list[CanonicalHour] = []
    for idx in range(horizon_hours):
        stamp = start + timedelta(hours=idx)
        if stamp not in pv or stamp not in prices:
            missing = "pv_forecast" if stamp not in pv else "import_prices"
            raise PlanningInputError(missing + "_missing_slot:" + stamp.isoformat())
        hours.append(CanonicalHour(
            stamp.isoformat(), pv[stamp] / 1000,
            _hourly_baseload(baseload_profile, stamp, zone),
            prices[stamp], export_price,
        ))
    reserve = _finite(reserve_target_pct, "reserve_target_pct", nonnegative=True) if reserve_target_pct is not None else None
    batteries, soc = _battery_rows(battery_units, battery_configuration, reserve_target_pct=reserve)
    loads = _deferrable_rows(flexible_assets, start, horizon_hours)
    validate_native_context(
        battery_systems=batteries, flexible_loads=loads,
        mapped_battery_ids={x["asset_id"] for x in batteries},
        mapped_load_ids={x["asset_id"] for x in loads},
    )
    native = {}
    native.update(native_battery_config(batteries))
    if batteries:
        native["soc_init"] = soc if len(soc) > 1 else soc[0]
        native["soc_final"] = soc if len(soc) > 1 else soc[0]
    native.update(native_deferrable_config(loads))
    native.update(native_grid_config(
        import_limit_kw=_finite(grid_import_limit_kw, "grid_import_limit_kw", nonnegative=True),
        export_limit_kw=_finite(grid_export_limit_kw, "grid_export_limit_kw", nonnegative=True),
    ))
    native["prediction_horizon"] = horizon_hours
    payload = compose_emhass_request(
        hours, native_parameters=native,
        supported_parameters=supported_native_parameters,
    )
    return CanonicalEmhassContext(
        payload=payload,
        battery_ids=tuple(row["asset_id"] for row in batteries),
        flexible_ids=tuple(row["asset_id"] for row in loads),
        timeline_utc=tuple(row.timestamp for row in hours),
        provenance={
            "solar_forecast": "accepted_source_service_response",
            "local_timezone": local_timezone,
            "home_baseload": "persistent_hourly_metered_profile",
            "import_prices": "canonical_timestamped_future_prices",
            "export_price": "explicit_configured_fixed_price",
            "battery_configuration": "explicit_per_asset_limits",
            "flexible_loads": "mobility_public_producer",
            "flexible_constraints": {
                str(row.get("asset_id")): {
                    "min_power_kw": row.get("min_power_kw"),
                    "minimum_runtime_minutes": row.get("minimum_runtime_minutes"),
                    "energy_to_target_kwh": row.get("energy_to_target_kwh"),
                    "ready_by": row.get("ready_by") or row.get("deadline"),
                }
                for row in flexible_assets
                if str(row.get("asset_id")) in {item["asset_id"] for item in loads}
            },
        },
    )
