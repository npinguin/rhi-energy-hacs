"""Legacy SolarEdge Energy value conventions."""
from __future__ import annotations

from typing import Any


def normalize(role: str, value: Any, context: dict[str, Any]) -> Any:
    if value is None:
        return None
    if role == "grid.net_power_kw":
        return -float(value)
    return value
