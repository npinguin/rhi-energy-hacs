"""Strict EMHASS 0.18.5 plan acceptance and bounded, read-only comparison truth."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo
from .emhass_context import CanonicalEmhassContext
from .emhass_native import NativeCapabilityError
from .emhass_v0185_result import validate_native_run


@dataclass(frozen=True)
class AcceptedShadowPlan:
    generated_at: str
    provider: str
    rows: tuple[dict[str, Any], ...]
    battery_ids: tuple[str, ...]
    flexible_ids: tuple[str, ...]
    total_import_kwh: float
    total_export_kwh: float
    net_financial_result_eur: float
    flexible_scheduled_kwh: dict[str, float]
    battery_discharge_kwh: dict[str, float]
    horizon_summary: dict[str, Any] | None = None
    read_only: bool = True


def _finite(row: dict[str, Any], name: str, *, minimum: float | None = None) -> float:
    v = row.get(name)
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not isfinite(v):
        raise NativeCapabilityError("emhass_missing_or_nonfinite:" + name)
    v = float(v)
    if minimum is not None and v < minimum - 1e-6:
        raise NativeCapabilityError("emhass_negative_or_out_of_bounds:" + name)
    return v


def _instant(value: Any) -> datetime:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError("timezone")
        return d.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise NativeCapabilityError("emhass_row_timestamp_invalid") from exc


def accept_shadow_plan(
    plan: dict[str, Any], last_run: dict[str, Any],
    context: CanonicalEmhassContext, *,
    resolution_minutes: int = 60,
    max_stationary_discharge_during_flexible_w: float = 100.0,
) -> AcceptedShadowPlan:
    """Fail closed before publishing evidence; never authorize physical commands.

    Hourly input / output resolution must agree exactly. More frequent native
    solver steps require a separately tested interval mapping, never truncation.
    """
    if resolution_minutes != 60:
        raise NativeCapabilityError("emhass_timestep_not_hourly")
    if last_run.get("action") != "naive-mpc-optim":
        raise NativeCapabilityError("emhass_unexpected_solver_mode")
    raw = validate_native_run(plan, last_run)
    if len(raw) != len(context.timeline_utc):
        raise NativeCapabilityError("emhass_partial_horizon")
    slots = [_instant(t) for t in context.timeline_utc]
    if any(_instant(row.get("timestamp")) != at for row, at in zip(raw, slots, strict=True)):
        raise NativeCapabilityError("emhass_horizon_timestamp_mismatch")
    net_result = imported = exported = 0.0
    flex_energy = {aid: 0.0 for aid in context.flexible_ids}
    battery_discharge = {aid: 0.0 for aid in context.battery_ids}
    battery_count = len(context.battery_ids)
    flexible_active_slots: dict[str, list[int]] = {aid: [] for aid in context.flexible_ids}
    horizon_totals: dict[str, dict[str, Any]] = {}
    zone_name = context.provenance.get("local_timezone")
    zone = ZoneInfo(str(zone_name)) if zone_name else None
    if zone is not None:
        for label in ("D0", "D1"):
            horizon_totals[label] = {
                "flexible_scheduled_kwh": {aid: 0.0 for aid in context.flexible_ids},
                "grid_import_kwh": 0.0, "grid_export_kwh": 0.0,
                "net_financial_result_eur": 0.0, "covered_hours": 0,
            }
    first_day = slots[0].astimezone(zone).date() if zone else None
    for position, row in enumerate(raw):
        if str(row.get("optim_status") or "") != "Optimal":
            raise NativeCapabilityError("emhass_solver_not_strictly_optimal")
        p_grid = _finite(row, "P_grid")
        import_w = max(0.0, p_grid)
        export_w = max(0.0, -p_grid)
        configured_import_w = _finite(context.payload, "maximum_power_from_grid", minimum=0)
        configured_export_w = _finite(context.payload, "maximum_power_to_grid", minimum=0)
        if import_w > configured_import_w + 1e-3 or export_w > configured_export_w + 1e-3:
            raise NativeCapabilityError("emhass_grid_limit_violated")
        source_pv = _finite(row, "P_PV", minimum=0)
        source_load = _finite(row, "P_Load", minimum=0)
        # Native optimization must honor the exact accepted source evidence.
        # PV may be curtailed, but it cannot exceed the accepted forecast;
        # household baseload and tariff values must retain their meaning.
        for forecast_key in ("pv_power_forecast", "load_power_forecast",
                             "load_cost_forecast", "prod_price_forecast"):
            forecasts = context.payload.get(forecast_key)
            if not isinstance(forecasts, list) or len(forecasts) != len(raw):
                raise NativeCapabilityError("emhass_source_horizon_missing:" + forecast_key)
        expected_pv = context.payload["pv_power_forecast"][position]
        expected_load = context.payload["load_power_forecast"][position]
        if source_pv > expected_pv + 1 or abs(source_load - expected_load) > 1:
            raise NativeCapabilityError("emhass_canonical_power_mismatch")
        total_battery_power = 0.0
        for idx, aid in enumerate(context.battery_ids):
            p_key = "P_batt" if battery_count == 1 else f"P_batt_{idx}"
            soc_key = "SOC_opt" if battery_count == 1 else f"SOC_opt_{idx}"
            power = _finite(row, p_key)
            soc = _finite(row, soc_key)
            min_soc = context.payload["battery_minimum_state_of_charge"]
            max_soc = context.payload["battery_maximum_state_of_charge"]
            lower = min_soc if battery_count == 1 else min_soc[idx]
            upper = max_soc if battery_count == 1 else max_soc[idx]
            if not (float(lower) - 1e-6 <= soc <= float(upper) + 1e-6):
                raise NativeCapabilityError("emhass_battery_soc_violated:" + aid)
            charge_max = context.payload["battery_charge_power_max"]
            discharge_max = context.payload["battery_discharge_power_max"]
            if power > (discharge_max if battery_count == 1 else discharge_max[idx]) + 1e-3:
                raise NativeCapabilityError("emhass_battery_discharge_limit:" + aid)
            if -power > (charge_max if battery_count == 1 else charge_max[idx]) + 1e-3:
                raise NativeCapabilityError("emhass_battery_charge_limit:" + aid)
            total_battery_power += power
            battery_discharge[aid] += max(0, power) / 1000
        total_flexible_power = 0.0
        for idx, aid in enumerate(context.flexible_ids):
            power = _finite(row, f"P_deferrable{idx}", minimum=0)
            max_native = context.payload["nominal_power_of_deferrable_loads"][idx]
            if power > max_native + 1e-3:
                raise NativeCapabilityError("emhass_flexible_power_limit:" + aid)
            if idx >= len(context.payload["end_timesteps_of_each_deferrable_load"]):
                raise NativeCapabilityError("emhass_flexible_deadline_missing:" + aid)
            # Only the index-aligned timestep may be scheduled.
            if position >= context.payload["end_timesteps_of_each_deferrable_load"][idx] and power > 1e-4:
                raise NativeCapabilityError("emhass_flexible_deadline_violated:" + aid)
            if power > 1e-4:
                constraints = (context.provenance.get("flexible_constraints") or {}).get(aid) or {}
                required_min_power = constraints.get("min_power_kw")
                if required_min_power is not None and power + 1e-3 < float(required_min_power) * 1000:
                    raise NativeCapabilityError("emhass_flexible_minimum_power_violated:" + aid)
                flexible_active_slots[aid].append(position)
            flex_energy[aid] += power / 1000
            total_flexible_power += power
        if total_flexible_power > 1e-4 and total_battery_power > max_stationary_discharge_during_flexible_w + 1e-3:
            raise NativeCapabilityError("emhass_battery_discharge_guard_violated")
        # The provider must not omit demand or use a different supply balance.
        if abs((source_pv + max(total_battery_power, 0) + import_w)
               - (source_load + total_flexible_power + max(-total_battery_power, 0) + export_w)) > 100:
            raise NativeCapabilityError("emhass_power_balance_unverified")
        import_price = _finite(row, "unit_load_cost")
        export_price = _finite(row, "unit_prod_price")
        if (
            abs(import_price - float(context.payload["load_cost_forecast"][position])) > 1e-6
            or abs(export_price - float(context.payload["prod_price_forecast"][position])) > 1e-6
        ):
            raise NativeCapabilityError("emhass_canonical_tariff_mismatch")
        step_value = (export_w * export_price - import_w * import_price) / 1000
        net_result += step_value
        imported += import_w / 1000
        exported += export_w / 1000
        if zone is not None:
            slot_day = slots[position].astimezone(zone).date()
            horizon = "D0" if slot_day == first_day else "D1" if (slot_day - first_day).days == 1 else None
            if horizon:
                bucket = horizon_totals[horizon]
                bucket["covered_hours"] += 1
                bucket["grid_import_kwh"] += import_w / 1000
                bucket["grid_export_kwh"] += export_w / 1000
                bucket["net_financial_result_eur"] += step_value
                for index, asset_id in enumerate(context.flexible_ids):
                    bucket["flexible_scheduled_kwh"][asset_id] += _finite(row, f"P_deferrable{index}", minimum=0) / 1000

    for aid, active in flexible_active_slots.items():
        constraints = (context.provenance.get("flexible_constraints") or {}).get(aid) or {}
        minimum_minutes = constraints.get("minimum_runtime_minutes")
        if minimum_minutes is not None and active:
            required_steps = int((float(minimum_minutes) + 59) // 60)
            runs = []
            current_run = 0
            previous = None
            for index in active:
                if previous is None or index == previous + 1:
                    current_run += 1
                else:
                    runs.append(current_run)
                    current_run = 1
                previous = index
            runs.append(current_run)
            if any(run < required_steps for run in runs):
                raise NativeCapabilityError("emhass_flexible_minimum_runtime_violated:" + aid)
        expected_need = constraints.get("energy_to_target_kwh")
        if expected_need is not None and flex_energy[aid] + 0.01 < float(expected_need):
            raise NativeCapabilityError("emhass_flexible_energy_need_unmet:" + aid)
        if expected_need is not None and flex_energy[aid] > float(expected_need) + 0.01:
            raise NativeCapabilityError("emhass_flexible_energy_target_exceeded:" + aid)
    for horizon in horizon_totals.values():
        for name in ("grid_import_kwh", "grid_export_kwh", "net_financial_result_eur"):
            horizon[name] = round(horizon[name], 5)
        horizon["flexible_scheduled_kwh"] = {
            name: round(value, 5) for name, value in horizon["flexible_scheduled_kwh"].items()
        }
        horizon["quality"] = "PARTIAL_ROLLING_HORIZON"
    return AcceptedShadowPlan(
        generated_at=str(plan["generated_at"]), provider="emhass",
        rows=tuple(dict(row) for row in raw),
        battery_ids=context.battery_ids, flexible_ids=context.flexible_ids,
        total_import_kwh=round(imported, 5),
        total_export_kwh=round(exported, 5),
        net_financial_result_eur=round(net_result, 5),
        flexible_scheduled_kwh={k: round(v, 5) for k, v in flex_energy.items()},
        battery_discharge_kwh={k: round(v, 5) for k, v in battery_discharge.items()},
        horizon_summary=horizon_totals or None,
    )
