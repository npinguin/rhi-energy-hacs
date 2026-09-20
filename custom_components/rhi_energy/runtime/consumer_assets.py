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
_RESOLVED_STATUSES = {"RESOLVED", "NORMALIZED", "MATCHED", "AVAILABLE"}


def _resolved_properties(raw: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read Mobility's typed public rows without laundering resolution errors."""
    if isinstance(raw, dict):
        return deepcopy(raw), []
    values: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("property_id") or row.get("property_key") or row.get("key") or "")
        if not key:
            continue
        resolution = row.get("resolution") if isinstance(row.get("resolution"), dict) else {}
        status = str(resolution.get("status") or row.get("status") or row.get("availability") or "")
        evidence.append({"property_id": key, "status": status, "reason_code": resolution.get("reason_code") or row.get("reason_code") or row.get("reason")})
        if status in _RESOLVED_STATUSES and row.get("value") is not None:
            values[key] = row.get("value")
            values[key.rsplit(".", 1)[-1]] = row.get("value")
    return values, evidence


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
        raw_properties = asset.get("properties")
        typed_properties = isinstance(raw_properties, list)
        props, property_evidence = _resolved_properties(raw_properties)

        def first(*names: str) -> Any:
            if typed_properties:
                return next((props.get(name) for name in names if props.get(name) is not None), None)
            return next((asset.get(name, props.get(name)) for name in names if asset.get(name, props.get(name)) is not None), None)

        power = number(first("power_kw", "actual_power_kw"))
        operating_state = first("operating_state", "state")
        if isinstance(operating_state, str) and operating_state.strip().lower() in _UNKNOWN:
            operating_state = None
        command_refs = deepcopy(asset.get("command_refs") or {})
        # Mobility is the sole physical charging-capability authority. Energy
        # consumes the published kW envelope as-is and never reconstructs it
        # from producer-internal electrical telemetry or source-integration data.
        envelope = asset.get("effective_charging_envelope")
        if not isinstance(envelope, dict):
            envelope = asset.get("effective_power_capability")
        envelope = deepcopy(envelope) if isinstance(envelope, dict) else {}
        envelope_ready = bool(
            envelope
            and envelope.get("available", envelope.get("ready", True)) is not False
        )
        envelope_min_kw = number(
            envelope.get("min_power_kw", envelope.get("minimum_power_kw"))
        ) if envelope_ready else None
        envelope_max_kw = number(
            envelope.get("max_power_kw", envelope.get("maximum_power_kw"))
        ) if envelope_ready else None
        normalized = {
            **deepcopy(asset),
            "asset_id": str(asset["asset_id"]),
            "display_name": display_name,
            "asset_type": "flexible_asset",
            "energy_asset_role": "flexible_load",
            "power_kw": power,
            "energy_to_target_kwh": number(first("energy_to_target_kwh", "required_energy_kwh", "energy_need_kwh")),
            "requested_power_kw": number(first("requested_power_kw", "requested_charge_power_kw")),
            "min_power_kw": envelope_min_kw,
            "max_power_kw": envelope_max_kw,
            "effective_charging_envelope": envelope,
            "requested_power_execution_ready": bool(
                envelope_ready
                and envelope_max_kw is not None
                and (command_refs.get("adjust_power") or command_refs.get("set_power"))
            ),
            "minimum_runtime_minutes": number(first("minimum_runtime_minutes", "min_runtime_minutes")),
            "operating_state": operating_state,
            "availability_state": first("availability_state", "availability") or "AVAILABLE",
            "target_soc_pct": number(first("target_soc_pct")),
            "current_soc_pct": number(first("soc_pct", "current_soc_pct")),
            "deadline": first("deadline", "target_time", "departure_time"),
            "command_refs": command_refs,
            "source_property_resolution": property_evidence,
        }
        useful = ("power_kw", "energy_to_target_kwh", "requested_power_kw", "current_soc_pct", "target_soc_pct", "deadline")
        if any(normalized.get(key) is not None for key in useful) or command_refs or normalized.get("operating_state") is not None:
            out.append(normalized)
    return out


def flexible_power_total(assets: list[dict[str, Any]], *, producer_available: bool) -> float | None:
    """Return authoritative active flexible-load power without treating unknown as zero.

    Producer-published disabled/inactive assets cannot currently consume Energy and are
    excluded from the instantaneous total. Every active asset must still publish an
    actual power value; otherwise the total remains unknown.
    """
    if not producer_available:
        return None
    active = [
        row for row in assets
        if str(row.get("lifecycle_status") or row.get("lifecycle_state") or "active").lower()
        not in {"disabled", "inactive"}
    ]
    if not active:
        return 0.0
    values = [number(row.get("power_kw")) for row in active]
    if any(value is None for value in values):
        return None
    return round(sum(float(value) for value in values if value is not None), 6)


def physical_connection_power_total(
    connections: list[dict[str, Any]], *, producer_available: bool
) -> float | None:
    """Return additive physical flexible-load power from producer-owned connections.

    Vehicle/consumer power is attribution and may legitimately appear more than once
    when multiple logical producer assets point at one physical charger.  Electrical
    balance therefore uses each physical connection asset exactly once.
    """
    if not producer_available:
        return None
    active = [
        row for row in connections
        if isinstance(row, dict)
        and str(row.get("lifecycle_status") or "active").lower()
        not in {"disabled", "inactive"}
    ]
    if not active:
        return 0.0
    values = [number(row.get("power_kw")) for row in active]
    if any(value is None for value in values):
        return None
    return round(sum(max(0.0, float(value)) for value in values if value is not None), 6)
