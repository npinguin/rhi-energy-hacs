"""Native EMHASS result acceptance is separate from HTTP success.

A 2xx response does not establish a feasible plan. The adapter must never
authorize physical execution on the basis of a success status alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmhassResultAcceptance:
    accepted: bool
    reason: str
    native_result: Any


def accept_emhass_result(
    native_result: Any,
    *,
    validated_plan: dict[str, Any] | None,
    all_assets_represented: bool,
    constraints_verified: bool,
) -> EmhassResultAcceptance:
    if not isinstance(validated_plan, dict) or not validated_plan:
        return EmhassResultAcceptance(False, "canonical_plan_not_validated", native_result)
    if not all_assets_represented:
        return EmhassResultAcceptance(False, "incomplete_asset_coverage", native_result)
    if not constraints_verified:
        return EmhassResultAcceptance(False, "operational_constraints_not_verified", native_result)
    return EmhassResultAcceptance(True, "validated", native_result)
