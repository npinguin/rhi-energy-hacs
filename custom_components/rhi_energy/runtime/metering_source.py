"""Canonical physical-power validity gate for event-driven metering and baseload.

Negative or nonfinite physical values are NOT real zeros and must not be
integrated or used as a learned baseload sample. Valid zero remains a fact.
Signed net battery power has its own gross-direction module.
"""
from __future__ import annotations

from math import isfinite
from typing import Any


def finite_nonnegative_source_power(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not isfinite(value) or value < 0:
        return None
    return float(value)


def finite_signed_money_rate(value: Any) -> float | None:
    """EUR per hour may genuinely be negative at negative energy prices."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None
