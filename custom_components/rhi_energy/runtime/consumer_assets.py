"""Validation and normalization of producer-domain Energy consumers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from ..compat_core import number
except ImportError:  # Direct runpy/static regression execution.
    from pathlib import Path as _Path
    import runpy as _runpy
    number = _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "compat_core.py"))["number"]

_UNKNOWN = {"unknown", "unavailable", "none", ""}


def normalize_mobility_consumers(consumers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only real Mobility consumers with at least one usable Energy surface."""
    out: list[dict[str, Any]] = []
    for asset in consumers:
        if not isinstance(asset, dict) or not asset.get("asset_id"):
            continue
        display_name = str(asset.get("display_name") or asset.get("name") or asset["asset_id"])
        object_type = str(asset.get("asset_type") or asset.get("object_class") or "").lower()
        if "robotix home intelligence" in display_name.lower() or object_type in {"module", "foundation", "integration"}:
            continue
        props = asset.get("properties") if isinstance(asset.get("properties"), dict) else {}

        def first(*names: str) -> Any:
            return next((asset.get(name, props.get(name)) for name in names if asset.get(name, props.get(name)) is not None), None)

        power = number(first("power_kw", "actual_power_kw"))
        operating_state = first("operating_state", "state")
        if isinstance(operating_state, str) and operating_state.strip().lower() in _UNKNOWN:
            operating_state = None
        command_refs = deepcopy(asset.get("command_refs") or {})
        normalized = {
            **deepcopy(asset),
            "asset_id": str(asset["asset_id"]),
            "display_name": display_name,
            "asset_type": "flexible_asset",
            "energy_asset_role": "flexible_load",
            "power_kw": power,
            "energy_to_target_kwh": number(first("energy_to_target_kwh", "required_energy_kwh", "energy_need_kwh")),
            "requested_power_kw": number(first("requested_power_kw", "requested_charge_power_kw")),
            "min_power_kw": number(first("min_power_kw", "minimum_power_kw")),
            "max_power_kw": number(first("max_power_kw", "maximum_power_kw")),
            "minimum_runtime_minutes": number(first("minimum_runtime_minutes", "min_runtime_minutes")),
            "operating_state": operating_state or ("running" if power is not None and abs(power) > 0.05 else "idle" if power is not None else None),
            "availability_state": first("availability_state", "availability") or "AVAILABLE",
            "target_soc_pct": number(first("target_soc_pct")),
            "current_soc_pct": number(first("soc_pct", "current_soc_pct")),
            "deadline": first("deadline", "target_time", "departure_time"),
            "command_refs": command_refs,
        }
        useful = ("power_kw", "energy_to_target_kwh", "requested_power_kw", "current_soc_pct", "target_soc_pct", "deadline")
        if any(normalized.get(key) is not None for key in useful) or command_refs or normalized.get("operating_state") is not None:
            out.append(normalized)
    return out
