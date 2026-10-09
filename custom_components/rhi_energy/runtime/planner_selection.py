"""Pure, fail-closed selection policy for validated planning results.

The selected planner may propose a plan, but only Energy's independent
validation and single command-owner gate may authorize physical execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FallbackPolicy(StrEnum):
    RHI = "rhi"
    HOLD = "hold"


@dataclass(frozen=True)
class PlannerDecision:
    requested_provider: str
    effective_provider: str | None
    reason: str
    plan: dict[str, Any] | None


def select_plan(
    selected: str,
    plans: dict[str, dict[str, Any]],
    validated: dict[str, bool],
    *,
    fallback: FallbackPolicy = FallbackPolicy.RHI,
) -> PlannerDecision:
    """Select only independently validated plans, never based on solver success alone."""
    if selected not in ("rhi_deterministic", "emhass"):
        return PlannerDecision(selected, None, "unknown_provider", None)
    if validated.get(selected) is True and selected in plans:
        return PlannerDecision(selected, selected, "selected_validated", plans[selected])
    if selected == "emhass" and fallback is FallbackPolicy.RHI:
        if validated.get("rhi_deterministic") is True and "rhi_deterministic" in plans:
            return PlannerDecision(selected, "rhi_deterministic", "fallback_to_rhi", plans["rhi_deterministic"])
    return PlannerDecision(selected, None, "no_validated_plan_hold", None)
