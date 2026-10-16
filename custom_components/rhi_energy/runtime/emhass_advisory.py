"""Provider-neutral advisory projection for independently accepted native EMHASS rows.

Do not manufacture current-hour decisions from a future-hour MPC horizon.
Execution remains separately governed by Energy/Mobility; this projection is
read-only until target-HA safety qualification proves exact command semantics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from .emhass_result_adapter import AcceptedShadowPlan


class AdvisoryProjectionError(ValueError):
    pass


def _utc(value: Any) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AdvisoryProjectionError("native_timestamp_invalid") from exc
    if dt.tzinfo is None:
        raise AdvisoryProjectionError("native_timestamp_timezone_missing")
    return dt.astimezone(timezone.utc)


def _kw(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise AdvisoryProjectionError(f"native_power_missing:{key}")
    return float(value) / 1000


def project_emhass_advisory(
    accepted: AcceptedShadowPlan, *,
    time_zone: str, now: datetime,
) -> dict[str, Any]:
    """Return Energy-shaped D0/D1 advisory horizons with explicit partial coverage.

    No fallback values or deterministic allocations are copied into the native
    plan. Native output that covers only part of the calendar day retains
    PARTIAL quality; no command authority is granted by this method.
    """
    if not accepted.read_only or accepted.provider != "emhass":
        raise AdvisoryProjectionError("native_plan_not_read_only_accepted")
    if not accepted.rows:
        raise AdvisoryProjectionError("native_plan_empty")
    if accepted.step_minutes not in (30, 60):
        raise AdvisoryProjectionError("native_step_unsupported")
    step_hours = accepted.step_minutes / 60
    zone = ZoneInfo(time_zone)
    if now.tzinfo is None or now.utcoffset() is None:
        raise AdvisoryProjectionError("native_current_time_timezone_missing")
    now_utc = now.astimezone(timezone.utc)
    today = now_utc.astimezone(zone).date()
    horizons: dict[str, dict[str, Any]] = {}
    last_end: datetime | None = None
    seen_assets: set[str] = set()
    for index, row in enumerate(accepted.rows):
        start = _utc(row.get("timestamp"))
        if last_end is not None and start != last_end:
            raise AdvisoryProjectionError("native_horizon_not_contiguous")
        end = start + timedelta(minutes=accepted.step_minutes)
        last_end = end
        horizon_day = start.astimezone(zone).date()
        # A local calendar boundary inside one native interval cannot be
        # assigned wholly to either D0 or D1 without falsifying energy totals.
        # A future source-aware interval splitter can admit it; for now HOLD.
        if end.astimezone(zone).date() != horizon_day and end.astimezone(zone).time() != datetime.min.time():
            raise AdvisoryProjectionError("native_interval_crosses_local_day")
        day_offset = (horizon_day - today).days
        if day_offset not in (0, 1, 2):
            continue
        hid = f"D{day_offset}"
        item = horizons.setdefault(hid, {
            "horizon_id": hid,
            "label": "Today" if hid == "D0" else "Tomorrow" if hid == "D1" else "Day after tomorrow",
            "time_scope": "remaining_today" if hid == "D0" else "full_day_tomorrow" if hid == "D1" else "full_day_after_tomorrow",
            "provider": "emhass", "buckets": [],
            "quality": {"availability": "PARTIAL", "estimated": True,
                        "warnings": ["rolling_native_horizon_not_full_calendar_day"]},
            "supply": {"solar_kwh": 0.0, "grid_import_kwh": 0.0,
                       "battery_support_kwh": 0.0},
            "demand": {"home_kwh": 0.0, "flexible_scheduled_kwh": 0.0},
            "balance": {"expected_grid_export_kwh": 0.0},
            "price_value": {"net_financial_result_eur": 0.0},
        })
        pv = _kw(row, "P_PV")
        home = _kw(row, "P_Load")
        grid = _kw(row, "P_grid")
        if pv < 0 or home < 0:
            raise AdvisoryProjectionError("native_negative_pv_or_baseload")
        flex_allocations: list[dict[str, Any]] = []
        for pos, aid in enumerate(accepted.flexible_ids):
            power = _kw(row, f"P_deferrable{pos}")
            if power < -1e-6:
                raise AdvisoryProjectionError("native_negative_flexible_power")
            seen_assets.add(aid)
            if power > 1e-6:
                flex_allocations.append({
                    "asset_id": aid,
                    "planned_power_kw": round(power, 6),
                    "planned_energy_kwh": round(power * step_hours, 6),
                    "provider": "emhass",
                })
        battery_discharge_kw = 0.0
        battery_charge_kw = 0.0
        for pos, aid in enumerate(accepted.battery_ids):
            key = "P_batt" if len(accepted.battery_ids) == 1 else f"P_batt_{pos}"
            signed_kw = _kw(row, key)
            # Native batteries are independent physical assets. Netting a
            # discharging and a charging unit would conceal both flows.
            battery_discharge_kw += max(0.0, signed_kw)
            battery_charge_kw += max(0.0, -signed_kw)
        flex_kwh = sum(x["planned_energy_kwh"] for x in flex_allocations)
        imported = max(0.0, grid)
        exported = max(0.0, -grid)
        import_price = row.get("unit_load_cost")
        export_price = row.get("unit_prod_price")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
               for v in (import_price, export_price)):
            raise AdvisoryProjectionError("native_price_not_finite")
        financial = (exported * export_price - imported * import_price) * step_hours
        pv_energy, home_energy = pv * step_hours, home * step_hours
        imported_energy, exported_energy = imported * step_hours, exported * step_hours
        battery_support_energy = battery_discharge_kw * step_hours
        item["buckets"].append({
            "start_time": start.astimezone(zone).isoformat(),
            "end_time": end.astimezone(zone).isoformat(),
            "duration_hours": step_hours,
            "asset_allocations": flex_allocations,
            "solar_kwh": round(pv_energy, 6),
            "home_consumption_kwh": round(home_energy, 6),
            "grid_import_kwh": round(imported_energy, 6),
            "grid_export_kwh": round(exported_energy, 6),
            "battery_discharge_kwh": round(battery_support_energy, 6),
            "battery_charge_kwh": round(battery_charge_kw * step_hours, 6),
            "flexible_scheduled_kwh": round(flex_kwh, 6),
            "net_financial_result_eur": round(financial, 6),
            "planning_state": "advisory",
            "execution_authorized": False,
        })
        item["supply"]["solar_kwh"] += pv_energy
        item["supply"]["grid_import_kwh"] += imported_energy
        item["supply"]["battery_support_kwh"] += battery_support_energy
        item["demand"]["home_kwh"] += home_energy
        item["demand"]["flexible_scheduled_kwh"] += flex_kwh
        item["balance"]["expected_grid_export_kwh"] += exported_energy
        item["price_value"]["net_financial_result_eur"] += financial

    for key in ("D0", "D1", "D2"):
        horizon = horizons.get(key)
        if horizon is None:
            continue
        total = len(horizon["buckets"])
        if key == "D0":
            expected_start = now_utc.astimezone(zone).replace(minute=0, second=0, microsecond=0)
            expected_end = datetime.combine(today + timedelta(days=1),
                                            datetime.min.time(), tzinfo=zone)
        else:
            shift = 1 if key == "D1" else 2
            expected_start = datetime.combine(today + timedelta(days=shift),
                                              datetime.min.time(), tzinfo=zone)
            expected_end = datetime.combine(today + timedelta(days=shift + 1),
                                            datetime.min.time(), tzinfo=zone)
        actual_start = _utc(horizon["buckets"][0]["start_time"])
        actual_end = _utc(horizon["buckets"][-1]["end_time"])
        full = (actual_start <= expected_start.astimezone(timezone.utc)
                and actual_end >= expected_end.astimezone(timezone.utc))
        horizon["quality"] = {
            "availability": "AVAILABLE" if full else "PARTIAL",
            "estimated": True,
            "coverage": "COMPLETE" if full else "PARTIAL_ROLLING_HORIZON",
            "covered_hours": total * step_hours,
            "warnings": [] if full else ["rolling_native_horizon_not_full_calendar_day"],
        }
        horizon["flexible_planned_kwh"] = round(horizon["demand"]["flexible_scheduled_kwh"], 6)
        for field in ("supply", "demand", "balance", "price_value"):
            horizon[field] = {
                k: round(v, 6) if isinstance(v, (float, int)) else v
                for k, v in horizon[field].items()
            }
    if not horizons or seen_assets != set(accepted.flexible_ids):
        raise AdvisoryProjectionError("native_advisory_horizon_or_asset_coverage_missing")
    flex_assets = []
    for aid in accepted.flexible_ids:
        today_kwh = round(sum(
            allocation["planned_energy_kwh"]
            for bucket in (horizons.get("D0") or {}).get("buckets") or []
            for allocation in bucket["asset_allocations"]
            if allocation["asset_id"] == aid
        ), 6)
        tomorrow_kwh = round(sum(
            allocation["planned_energy_kwh"]
            for bucket in (horizons.get("D1") or {}).get("buckets") or []
            for allocation in bucket["asset_allocations"]
            if allocation["asset_id"] == aid
        ), 6)
        after_kwh = round(sum(
            allocation["planned_energy_kwh"]
            for bucket in (horizons.get("D2") or {}).get("buckets") or []
            for allocation in bucket["asset_allocations"]
            if allocation["asset_id"] == aid
        ), 6)
        flex_assets.append({
            "asset_id": aid, "planning_eligible": True,
            "planning_status": "ADVISORY_PARTIAL_NEED",
            "planned_today_kwh": today_kwh if "D0" in horizons else None,
            "planned_tomorrow_kwh": tomorrow_kwh if "D1" in horizons else None,
            "planned_day_after_tomorrow_kwh": after_kwh if "D2" in horizons else None,
            # The accepted solver result proves scheduled energy, NOT the
            # consumer's total original Need or that nothing remains beyond
            # its partial rolling horizon. Never turn missing need into zero.
            "energy_need_kwh": None,
            "still_to_plan_kwh": None,
            "need_evidence": "not_proven_by_native_advisory_result",
        })
    flexible_plan = {
        "contract": "energy_flexible_plan_v1",
        "participating_asset_count": len(accepted.flexible_ids),
        "incomplete_asset_count": len(accepted.flexible_ids),
        "totals_complete": False,
        "participating_asset_ids": list(accepted.flexible_ids),
        "assets": flex_assets,
        "known_need_kwh": None,
        "unresolved_need_kwh": None,
        "known_scheduled_kwh": round(sum(accepted.flexible_scheduled_kwh.values()), 6),
        "reason_code": "native_advisory_demand_total_not_proven",
        "horizons": {
            hid: {"scheduled_kwh": h["flexible_planned_kwh"],
                  "quality": h["quality"]}
            for hid, h in horizons.items()
        },
    }
    baseline_plan = {
        "contract": "energy_baseline_plan_v1",
        "horizons": {
            hid: {"supply": dict(h["supply"]),
                  "home_demand_kwh": h["demand"]["home_kwh"],
                  "balance": dict(h["balance"]),
                  "quality": dict(h["quality"])}
            for hid, h in horizons.items()
        },
    }
    return {
        "plan_id": "emhass:" + accepted.generated_at,
        "generated_at": accepted.generated_at,
        "provider": "emhass",
        "read_only": True,
        "execution_authorized": False,
        "planning_horizons": horizons,
        "baseline_plan": baseline_plan,
        "flexible_plan": flexible_plan,
        "unresolved_flexible_need_kwh": 0.0,
        "planning_horizons_json": [horizons[k] for k in ("D0", "D1", "D2") if k in horizons],
        "health": "DEGRADED",
        "reason": "native_mpc_accepted_read_only_need_unproven",
        "net_financial_result_eur": accepted.net_financial_result_eur,
        "flexible_scheduled_kwh": dict(accepted.flexible_scheduled_kwh),
        "battery_discharge_kwh": dict(accepted.battery_discharge_kwh),
    }
