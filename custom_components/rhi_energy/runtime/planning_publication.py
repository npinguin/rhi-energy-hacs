"""Native D0/D1 contract from effective or baseline Energy runtime plan.

Do not invent missing buckets, asset allocations, provider selection or execution
authority. A failed optimizer may not erase the independent baseline evidence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

CONTRACTS = {
    "effective": "RHI_ENERGY_PLANNING_HORIZON_V1",
    "baseline": "RHI_ENERGY_BASELINE_PLANNING_HORIZON_V1",
}


def native_planning_horizon(
    snapshot: dict[str, Any], horizon_id: str, *, variant: str = "effective",
) -> dict[str, Any]:
    if horizon_id not in {"D0", "D1", "D2"} or variant not in CONTRACTS:
        raise ValueError("native_planning_horizon_selector_invalid")
    selection = snapshot.get("planning_selection")
    if not isinstance(selection, dict):
        selection = {}
    plan = snapshot.get("plan" if variant == "effective" else "baseline_plan")
    if not isinstance(plan, dict):
        plan = {}
    horizons = plan.get("planning_horizons")
    horizon = horizons.get(horizon_id) if isinstance(horizons, dict) else None
    provider = selection.get("effective_provider") if variant == "effective" else "rhi_deterministic"
    result = {
        "canonical_contract": CONTRACTS[variant],
        "canonical_source": "rhi_energy.runtime",
        "horizon_id": horizon_id,
        "variant": variant,
        "provider_id": provider,
        "requested_provider": selection.get("requested_provider"),
        "plan_id": plan.get("plan_id"),
        "generated_at": plan.get("generated_at"),
        "domain_model_revision": snapshot.get("domain_model_revision"),
        "execution_authorized": (
            plan.get("execution_authorized") is True if variant == "effective" else False
        ),
    }
    if not isinstance(horizon, dict) or horizon.get("horizon_id") != horizon_id:
        return {
            **result, "availability": "UNAVAILABLE",
            "reason_code": (
                str(selection.get("reason") or plan.get("reason") or "effective_horizon_not_published")
                if variant == "effective" else "baseline_horizon_not_published"
            ),
            "quality": {"availability": "UNAVAILABLE"},
            "totals_complete": False, "details": None,
        }
    totals = (
        "required_kwh", "planned_kwh", "still_to_plan_kwh",
        "flexible_required_kwh", "flexible_planned_kwh",
        "flexible_still_to_plan_kwh",
    )
    # Only finite, physical nonnegative energy totals are valid. A NaN/Infinity
    # from a failed optimiser would otherwise be marked AVAILABLE and published
    # into native HA/UX as an apparently complete plan.
    complete = all(
        isinstance(horizon.get(key), (int, float))
        and not isinstance(horizon.get(key), bool)
        and isfinite(horizon[key])
        and horizon[key] >= 0
        for key in totals
    )
    # A solver can produce six finite but mathematically impossible totals.
    # Never publish "Need < Planned" or a nonzero difference hidden from Still.
    # At four-decimal kWh precision, 0.001 kWh covers independent rounding.
    consistent = complete and (
        abs(horizon["required_kwh"] -
            horizon["planned_kwh"] - horizon["still_to_plan_kwh"]) <= 0.001
        and abs(horizon["flexible_required_kwh"] -
                horizon["flexible_planned_kwh"] -
                horizon["flexible_still_to_plan_kwh"]) <= 0.001
        and horizon["planned_kwh"] + 0.001 >= horizon["flexible_planned_kwh"]
        and horizon["required_kwh"] + 0.001 >= horizon["flexible_required_kwh"]
        # Flexible deferred energy is part of total deferred energy, never a
        # larger independent balance masked by otherwise consistent totals.
        and horizon["still_to_plan_kwh"] + 0.001 >= horizon["flexible_still_to_plan_kwh"]
    )
    # A complete numeric summary without valid chronological buckets does
    # not prove a usable horizon. Bucket identity and UTC ordering must hold
    # independently of an optimizer's quality flag and the six summed totals.
    # Partial native D2 evidence remains visible below as an incomplete
    # preview; this gate never invents absent D2 totals.
    buckets = horizon.get("buckets")
    buckets_sound = isinstance(buckets, list) and bool(buckets)
    prior_end = None
    if buckets_sound:
        for bucket in buckets:
            if not isinstance(bucket, dict):
                buckets_sound = False
                break
            try:
                start = datetime.fromisoformat(
                    str(bucket.get("start_time") or bucket.get("start_at")).replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    str(bucket.get("end_time") or bucket.get("end_at")).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                buckets_sound = False
                break
            if (start.tzinfo is None or start.utcoffset() is None
                    or end.tzinfo is None or end.utcoffset() is None):
                buckets_sound = False
                break
            start_utc = start.astimezone(timezone.utc)
            end_utc = end.astimezone(timezone.utc)
            if end_utc <= start_utc or (prior_end is not None and start_utc != prior_end):
                buckets_sound = False
                break
            prior_end = end_utc

    # D1 is a *calendar day*, not an arbitrary contiguous 24-hour rolling
    # segment. During DST a complete local day is 23 or 25 physical hours.
    # A one-hour slice with balanced totals must never claim complete D1.
    if buckets_sound and horizon_id == "D1":
        if horizon.get("time_scope") != "full_day_tomorrow":
            buckets_sound = False
        else:
            try:
                generated = datetime.fromisoformat(str(plan.get("generated_at")).replace("Z", "+00:00"))
                first = datetime.fromisoformat(str(buckets[0].get("start_time") or buckets[0].get("start_at")).replace("Z", "+00:00"))
                final = datetime.fromisoformat(str(buckets[-1].get("end_time") or buckets[-1].get("end_at")).replace("Z", "+00:00"))
                if (generated.tzinfo is None or generated.utcoffset() is None
                        or first.date() != generated.date() + timedelta(days=1)
                        or final.date() != first.date() + timedelta(days=1)
                        or (first.hour, first.minute, first.second, first.microsecond) != (0, 0, 0, 0)
                        or (final.hour, final.minute, final.second, final.microsecond) != (0, 0, 0, 0)):
                    buckets_sound = False
            except (ValueError, TypeError, OverflowError):
                buckets_sound = False

    # Native summary energy is no more authoritative than its physical bucket
    # evidence. A full horizon with 10 kWh of claimed solar but zero solar in
    # every published slot is NOT complete, even when total Need balances.
    # Validate only a lane the producer actually publishes; unsupported optional
    # lanes remain unknown rather than interpreted as zero.
    lane_pairs = (
        ("supply", "solar_kwh", "solar_forecast_kwh"),
        ("demand", "home_kwh", "base_demand_forecast_kwh"),
        ("demand", "flexible_scheduled_kwh", "planned_flexible_kwh"),
        ("balance", "expected_grid_import_kwh", "expected_grid_import_kwh"),
        ("balance", "expected_grid_export_kwh", "expected_grid_export_kwh"),
    )
    if buckets_sound:
        for section, aggregate_key, bucket_key in lane_pairs:
            aggregate_row = horizon.get(section)
            if not isinstance(aggregate_row, dict) or aggregate_key not in aggregate_row:
                continue
            expected = aggregate_row[aggregate_key]
            if expected is None:
                continue
            if (not isinstance(expected, (int, float)) or isinstance(expected, bool)
                    or not isfinite(expected) or expected < 0):
                buckets_sound = False
                break
            measurements = [row.get(bucket_key) for row in buckets]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool)
                   or not isfinite(value) or value < 0 for value in measurements):
                buckets_sound = False
                break
            tolerance = max(0.001, len(buckets) * 0.00011)
            if abs(sum(measurements) - expected) > tolerance:
                buckets_sound = False
                break

    raw_quality = horizon.get("quality")
    quality = raw_quality if isinstance(raw_quality, dict) else {}
    available = quality.get("availability") == "AVAILABLE" and consistent and buckets_sound
    # Preserve the producer's explicit source/HOLD blocker on an incomplete
    # horizon. A generic missing-total reason must not obscure the real cause
    # (e.g. a missing selected forecast), but no reason may authorize values.
    stated_reason = (
        quality.get("reason_code") or quality.get("reason")
        if quality.get("availability") != "AVAILABLE" else None
    )
    if not complete:
        reason = stated_reason or "planning_horizon_required_totals_missing"
    elif not consistent:
        reason = stated_reason or "planning_horizon_totals_inconsistent"
    elif not buckets_sound:
        reason = stated_reason or "planning_horizon_bucket_evidence_invalid"
    elif not available:
        reason = stated_reason or "planning_horizon_quality_incomplete"
    else:
        reason = None
    out_quality = deepcopy(quality)
    degraded_availability = (
        quality.get("availability")
        if quality.get("availability") in {"UNAVAILABLE", "STALE", "INVALID"}
        else "INCOMPLETE"
    )
    if not available:
        out_quality["availability"] = degraded_availability
        out_quality["reason_code"] = reason
    details = deepcopy(horizon)
    flexible = plan.get("flexible_plan") or {}
    summary = horizon.get("summary")
    lanes = summary.get("lane_totals") if isinstance(summary, dict) else None
    if not isinstance(lanes, dict):
        lanes = {}
    details.update({
        "plan_id": plan.get("plan_id"),
        "provider_id": provider,
        "generated_at": plan.get("generated_at"),
        "planning_assets": deepcopy(flexible.get("assets")) if isinstance(flexible, dict) else None,
        "source_lanes": deepcopy(lanes.get("sources")),
        "consumer_lanes": deepcopy(lanes.get("consumers")),
        "execution_policy": deepcopy(plan.get("execution_policy")),
        "execution_authorized": result["execution_authorized"] and available,
    })
    return {
        **result,
        "availability": "AVAILABLE" if available else degraded_availability,
        "reason_code": reason,
        # A mathematically consistent set of numbers is not complete when
        # the authoritative producer labels its evidence incomplete/stale.
        # Consumers must not interpret a mere numeric balance as full coverage.
        "totals_complete": available,
        "execution_authorized": result["execution_authorized"] and available,
        "quality": out_quality,
        "details": details,
    }
