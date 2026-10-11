"""Native D0/D1 contract from effective or baseline Energy runtime plan.

Do not invent missing buckets, asset allocations, provider selection or execution
authority. A failed optimizer may not erase the independent baseline evidence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONTRACTS = {
    "effective": "RHI_ENERGY_PLANNING_HORIZON_V1",
    "baseline": "RHI_ENERGY_BASELINE_PLANNING_HORIZON_V1",
}


def native_planning_horizon(
    snapshot: dict[str, Any], horizon_id: str, *, variant: str = "effective",
) -> dict[str, Any]:
    if horizon_id not in {"D0", "D1"} or variant not in CONTRACTS:
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
    complete = all(
        isinstance(horizon.get(key), (int, float))
        and not isinstance(horizon.get(key), bool) for key in totals
    )
    quality = horizon.get("quality") or {}
    available = quality.get("availability") == "AVAILABLE" and complete
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
        "execution_authorized": result["execution_authorized"],
    })
    return {
        **result,
        "availability": "AVAILABLE" if available else "INCOMPLETE",
        "reason_code": None if available else (
            "planning_horizon_required_totals_missing" if not complete
            else "planning_horizon_quality_incomplete"
        ),
        "totals_complete": complete,
        "quality": deepcopy(quality),
        "details": details,
    }
