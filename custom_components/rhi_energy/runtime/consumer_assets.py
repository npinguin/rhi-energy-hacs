"""Validation and normalization of producer-domain Energy consumers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .canonical_semantics import number
except ImportError:  # Direct runpy/static regression execution.
    from pathlib import Path as _Path
    import runpy as _runpy
    number = _runpy.run_path(str(_Path(__file__).resolve().parent / "canonical_semantics.py"))["number"]

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


def normalize_mobility_consumers(
    consumers: list[dict[str, Any]],
    connections: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize Mobility consumers without confusing attribution with electrical truth.

    Vehicle-side charge power may be stale or duplicated attribution. Site/actual flexible
    power is owned by the physical Mobility connection asset. Preserve producer attribution
    separately while projecting per-consumer actual_now_kw only from its effective physical
    connection.
    """
    out: list[dict[str, Any]] = []
    connection_by_id = {
        str(row.get("asset_id") or ""): row
        for row in (connections or [])
        if isinstance(row, dict) and row.get("asset_id")
    }

    def connection_actual_kw(connection_id: str) -> float | None:
        row = connection_by_id.get(connection_id)
        if not row:
            return None
        value = number(row.get("power_kw"))
        if value is not None:
            return max(0.0, float(value))
        operating = str(row.get("operating_state") or "").strip().lower()
        return 0.0 if operating in {"idle", "stopped"} else None
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

        producer_attributed_power = number(first("power_kw", "actual_power_kw"))
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
        if not isinstance(envelope, dict):
            # Mobility V2 publishes the authoritative physical kW envelope and
            # requested-power write/readback readiness under its limits contract.
            envelope = asset.get("limits")
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
        lifecycle_state = str(first("lifecycle_state", "lifecycle_status") or "active").strip().lower()
        source_asset_kind = str(asset.get("source_asset_kind") or "").strip().lower()
        source_context = asset.get("source_context") if isinstance(asset.get("source_context"), dict) else {}
        mobility_context = source_context.get("mobility") if isinstance(source_context.get("mobility"), dict) else {}
        consumer_fallback = str(mobility_context.get("consumer_fallback") or "").strip().lower()
        planning_input_value = first("planning_input_ready")
        if planning_input_value is None:
            planning_input_value = asset.get("planning_input_ready")
        planning_input_ready = None if planning_input_value is None else bool(planning_input_value)
        infrastructure_only = (
            source_asset_kind == "charger"
            or consumer_fallback == "unassigned_charger"
            or str(asset.get("asset_type") or "").strip().lower() in {"charger", "connection"}
        )
        if lifecycle_state in {"disabled", "inactive"}:
            participation_state = "disabled"
        elif infrastructure_only:
            participation_state = "infrastructure_only"
        else:
            # Planning readiness is orthogonal to consumer identity. A real
            # vehicle/load may be temporarily not ready for Tactical Planning
            # while remaining a valid consumer on Flow/Consumers/Operational.
            participation_state = "participating"
        assigned_connection_id = str(
            asset.get("assigned_connection_id")
            or asset.get("effective_connection_id")
            or asset.get("connection_asset_id")
            or asset.get("charger_asset_id")
            or ""
        )
        physical_identity_proven = bool(asset.get("physical_identity_proven"))
        physical_connection_id = str(asset.get("physical_connection_id") or "") if physical_identity_proven else ""
        assigned_row = connection_by_id.get(assigned_connection_id) if assigned_connection_id else None
        assigned_state = str(
            asset.get("assigned_connection_state")
            or (assigned_row or {}).get("connection_state")
            or ""
        ).strip().lower()
        assigned_occupied = asset.get("assigned_connection_occupied")
        if assigned_occupied is None and assigned_state:
            assigned_occupied = assigned_state in {"asset_connected", "connected", "occupied"}
        actual_now_kw = (
            connection_actual_kw(physical_connection_id)
            if physical_connection_id
            else 0.0
            if connections is not None and assigned_connection_id and assigned_occupied is False
            else (
                producer_attributed_power
                if connections is None or infrastructure_only
                else None
            )
        )

        planning_eligible = bool(
            not infrastructure_only
            and lifecycle_state not in {"disabled", "inactive"}
            and planning_input_ready is True
        )
        connected = bool(physical_connection_id and physical_identity_proven)
        if lifecycle_state in {"disabled", "inactive"}:
            user_status = "Disabled"
        elif connected:
            user_status = "Connected"
        elif asset.get("assigned_connection_id"):
            user_status = "Assigned · not physically connected"
        else:
            user_status = "Not connected"

        normalized = {
            **deepcopy(asset),
            "asset_id": str(asset["asset_id"]),
            "display_name": display_name,
            "asset_type": "flexible_asset",
            "energy_asset_role": "flexible_load",
            "visible": True,
            "show_in_primary_ux": True,
            "participation_state": participation_state,
            "planning_input_ready": False if infrastructure_only else (False if planning_input_ready is None else planning_input_ready),
            "planning_eligible": planning_eligible,
            "user_status": user_status,
            "technical_status": {
                "relationship_status": asset.get("relationship_status"),
                "relationship_reason": asset.get("relationship_reason"),
                "planning_blockers": list(asset.get("planning_blockers") or []),
            },
            "planning_blockers": list(asset.get("planning_blockers") or ((asset.get("planning_readiness") or {}).get("blockers") if isinstance(asset.get("planning_readiness"), dict) else []) or []),
            "producer_runtime_revision": asset.get("runtime_revision"),
            "producer_observed_at": asset.get("source_observed_at"),
            "infrastructure_only": infrastructure_only,
            # power_kw remains the canonical Energy actual-now field for backwards
            # compatibility, but it is now physical-connection authoritative.
            "power_kw": actual_now_kw,
            "actual_now_kw": actual_now_kw,
            "producer_attributed_power_kw": producer_attributed_power,
            "power_authority": (
                "mobility_physical_connection"
                if physical_connection_id and physical_connection_id in connection_by_id
                else "mobility_infrastructure"
                if infrastructure_only and producer_attributed_power is not None
                else "unresolved"
            ),
            "assigned_connection_id": assigned_connection_id or None,
            "assigned_connection_display_name": asset.get("assigned_connection_display_name"),
            "effective_connection_id": str(asset.get("effective_connection_id") or assigned_connection_id or "") or None,
            "effective_connection_display_name": asset.get("effective_connection_display_name") or asset.get("assigned_connection_display_name"),
            "physical_connection_id": physical_connection_id or None,
            "physical_connection_display_name": asset.get("physical_connection_display_name"),
            "physical_identity_proven": physical_identity_proven,
            "energy_to_target_kwh": number(first("energy_to_target_kwh", "required_energy_kwh", "energy_need_kwh")),
            "requested_power_kw": number(first("requested_power_kw", "requested_charge_power_kw")),
            "min_power_kw": envelope_min_kw,
            "max_power_kw": envelope_max_kw,
            "effective_charging_envelope": envelope,
            "requested_power_execution_ready": bool(
                envelope_ready
                and envelope_max_kw is not None
                and (
                    asset.get("requested_power_execution_ready")
                    or envelope.get("requested_power_execution_ready")
                    or envelope.get("requested_power_kw_write_supported")
                    or command_refs.get("adjust_power")
                    or command_refs.get("set_power")
                )
            ),
            "minimum_runtime_minutes": number(first("minimum_runtime_minutes", "min_runtime_minutes")),
            "operating_state": operating_state,
            "availability_state": first("availability_state", "availability") or "AVAILABLE",
            "target_soc_pct": number(first("target_soc_pct")),
            "current_soc_pct": number(first("soc_pct", "current_soc_pct")),
            "deadline": first("ready_by", "deadline", "target_time", "departure_time"),
            "ready_by": first("ready_by", "deadline", "target_time", "departure_time"),
            "command_refs": command_refs,
            "producer_command_refs": deepcopy(command_refs),
            "command_resolution": deepcopy(asset.get("command_resolution") or {}),
            "command_support": deepcopy(asset.get("command_support") or {}),
            "source_property_resolution": property_evidence,
        }
        # Producer-published consumer identity is product truth even while telemetry,
        # planning inputs or physical connection are unavailable. Preserve only rows
        # that are explicitly producer-owned or carry real Energy semantics.
        producer_identified = (
            str(asset.get("source_domain") or "").strip().lower() == "mobility"
            or source_asset_kind in {"vehicle", "flexible_load", "consumer"}
            or object_type in {"vehicle", "flexible_load", "consumer"}
            or str(asset.get("publisher") or "").strip().lower() == "rhi_mobility"
            or str(asset.get("contract_id") or "").strip().upper() == "MOBILITY_ENERGY_V2"
        )
        has_energy_truth = bool(
            actual_now_kw is not None
            or producer_attributed_power is not None
            or operating_state is not None
            or command_refs
            or normalized.get("energy_to_target_kwh") is not None
            or normalized.get("requested_power_kw") is not None
            or physical_connection_id
            or asset.get("assigned_connection_id")
        )
        if producer_identified or has_energy_truth:
            out.append(normalized)
    return out


def flexible_power_total(assets: list[dict[str, Any]], *, producer_available: bool) -> float | None:
    """Return producer-attributed vehicle power as diagnostics, never site truth.

    Electrical balance uses physical_connection_power_total(). This aggregate preserves
    Mobility's vehicle-side attribution only as a separate diagnostic and excludes
    infrastructure-only charger fallbacks to avoid double counting.
    """
    if not producer_available:
        return None
    active = [
        row for row in assets
        if str(row.get("lifecycle_status") or row.get("lifecycle_state") or "active").lower()
        not in {"disabled", "inactive"}
        and row.get("infrastructure_only", False) is not True
    ]
    if not active:
        return 0.0
    values = [
        number(
            row.get("producer_attributed_power_kw")
            if "producer_attributed_power_kw" in row
            else row.get("power_kw")
        )
        for row in active
    ]
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
    values: list[float] = []
    for row in active:
        value = number(row.get("power_kw"))
        if value is not None:
            values.append(max(0.0, float(value)))
            continue
        # A producer-owned canonical idle state is authoritative evidence that the
        # connection is not drawing charging power. This is not "unknown = 0":
        # unknown/running/charging connections without power still fail closed.
        operating_state = str(row.get("operating_state") or "").strip().lower()
        if operating_state in {"idle", "stopped"}:
            # Producer-owned canonical non-flow states are authoritative zero-flow
            # evidence. This is distinct from coercing unknown telemetry to zero.
            values.append(0.0)
            continue
        return None
    return round(sum(values), 6)
