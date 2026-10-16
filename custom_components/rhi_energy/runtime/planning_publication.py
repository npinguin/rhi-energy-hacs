"""Native D0/D1 contract from effective or baseline Energy runtime plan.

Do not invent missing buckets, asset allocations, provider selection or execution
authority. A failed optimizer may not erase the independent baseline evidence.
"""
from __future__ import annotations

from copy import deepcopy
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
    selection = snapshot.get("planning_selection") or {}
    plan = snapshot.get("plan" if variant == "effective" else "baseline_plan") or {}
    horizon = (plan.get("planning_horizons") or {}).get(horizon_id)
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
    )
    quality = horizon.get("quality") or {}
    available = quality.get("availability") == "AVAILABLE" and consistent
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
    lanes = (horizon.get("summary") or {}).get("lane_totals") or {}
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
        "totals_complete": consistent,
        "execution_authorized": result["execution_authorized"] and available,
        "quality": out_quality,
        "details": details,
    }
