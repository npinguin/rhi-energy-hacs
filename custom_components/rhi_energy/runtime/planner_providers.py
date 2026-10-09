"""Provider-neutral metadata for the first planning backend milestone.

The deterministic planner is always available. EMHASS is an optional external
service and MUST be validated before enabling a shadow optimization run.
This module does not probe endpoints or issue physical commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlannerMode(StrEnum):
    PRIMARY = "primary"
    SHADOW = "shadow"
    SELECTABLE = "selectable"


@dataclass(frozen=True, slots=True)
class PlannerProvider:
    provider_id: str
    label: str
    built_in: bool
    mode: PlannerMode
    requires_service: bool
    can_issue_commands: bool = False


RHI_DETERMINISTIC = PlannerProvider(
    provider_id="rhi_deterministic",
    label="RHI Deterministic",
    built_in=True,
    mode=PlannerMode.PRIMARY,
    requires_service=False,
)

EMHASS = PlannerProvider(
    provider_id="emhass",
    label="EMHASS",
    built_in=False,
    mode=PlannerMode.SELECTABLE,
    requires_service=True,
)


def available_planner_providers(*, emhass_validated: bool = False) -> tuple[PlannerProvider, ...]:
    """Return runnable providers; selection alone never bypasses validation."""
    return (RHI_DETERMINISTIC, EMHASS) if emhass_validated else (RHI_DETERMINISTIC,)
