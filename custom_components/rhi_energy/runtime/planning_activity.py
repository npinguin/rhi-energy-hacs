"""Bounded evidence for repeated blocked automatic planning ticks.

The one-minute safety/operational tick is not throttled. Only identical
NOT_EXECUTED activity persistence and callback fanout are rate-limited.
A new blocker, a later hourly reminder, or a manual request is always recorded.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def should_record_planning_block(
    previous: tuple[str, datetime] | None,
    reason: str,
    now: datetime,
    *,
    reminder_minutes: int = 60,
) -> bool:
    if not reason or previous is None:
        return True
    old_reason, observed_at = previous
    if now.tzinfo is None or observed_at.tzinfo is None:
        return True
    if reason != old_reason or now < observed_at:
        return True
    return now - observed_at >= timedelta(minutes=reminder_minutes)


def energy_execution_participant(asset: dict[str, Any]) -> bool:
    """An explicit scheduling opt-out is NOT a physical stop instruction.

    Energy does not issue scheduled or protective charger writes to non-managed
    producer assets. The charger/vehicle retains its own independent safeguards.
    Missing participation on older Mobility contracts preserves prior behavior.
    """
    if not isinstance(asset, dict) or asset.get("infrastructure_only") is True:
        return False
    lifecycle = str(asset.get("lifecycle_status") or asset.get("lifecycle_state") or "active").strip().lower()
    if lifecycle in {"disabled", "inactive"}:
        return False
    return str(asset.get("participation_state") or "participating").strip().lower() == "participating"
