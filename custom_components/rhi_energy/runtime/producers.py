"""Energy boundary for public Mobility V2 HA contract surfaces."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..compat_core import jload
from ..const import MOBILITY_COMMAND_V2_ENTITY, MOBILITY_ENERGY_V2_ENTITY


def mobility_entity_ids() -> tuple[str, str]:
    return MOBILITY_ENERGY_V2_ENTITY, MOBILITY_COMMAND_V2_ENTITY


def read_mobility_energy_assets(hass: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    state = hass.states.get(MOBILITY_ENERGY_V2_ENTITY)
    if not state or state.attributes.get("contract_id") != "MOBILITY_ENERGY_V2":
        return [], [], {}
    consumers = jload(state.attributes.get("consumer_assets"), [])
    connections = jload(state.attributes.get("connection_assets"), [])
    metadata = {
        "contract_id": state.attributes.get("contract_id"),
        "publisher": state.attributes.get("publisher"),
        "command_provider_id": state.attributes.get("command_provider_id"),
        "contains_physical_bindings": bool(state.attributes.get("contains_physical_bindings")),
        "periodization_owner": state.attributes.get("periodization_owner"),
        "attribution_owner": state.attributes.get("attribution_owner"),
        "planning_owner": state.attributes.get("planning_owner"),
        "physical_execution_owner": state.attributes.get("physical_execution_owner"),
        "source_entity_id": MOBILITY_ENERGY_V2_ENTITY,
        "source_state": state.state,
        "source_last_updated": state.last_updated.isoformat(),
    }
    return (
        deepcopy(consumers) if isinstance(consumers, list) else [],
        deepcopy(connections) if isinstance(connections, list) else [],
        metadata,
    )


def _mobility_commands(hass: Any) -> list[dict[str, Any]]:
    state = hass.states.get(MOBILITY_COMMAND_V2_ENTITY)
    if not state or state.attributes.get("contract_id") != "MOBILITY_COMMAND_V2":
        return []
    rows = jload(state.attributes.get("commands"), [])
    return deepcopy(rows) if isinstance(rows, list) else []


def _requested_power_command(asset: dict[str, Any]) -> dict[str, Any] | None:
    limits = asset.get("limits") if isinstance(asset.get("limits"), dict) else {}
    target = str(limits.get("requested_power_kw_write_asset_id") or asset.get("effective_connection_id") or "")
    if limits.get("requested_power_kw_write_supported") is not True or not target:
        return None
    ready = bool(limits.get("requested_power_execution_ready"))
    return {
        "command_id": "mobility.requested_power.write",
        "command_key": "charger.requested_charge_power_kw",
        "asset_id": str(asset.get("asset_id") or ""),
        "target_asset_id": str(asset.get("asset_id") or ""),
        "physical_executor_asset_id": target,
        "supported": True,
        "manual_execution_ready": ready,
        "manual_blocked_reason": None if ready else "mobility_requested_power_not_ready",
        "invoke": {
            "service": "rhi_mobility.set_requested_power",
            "data": {"asset_id": target},
            "parameter_map": {"requested_power_kw": "power_kw"},
        },
    }


def resolve_mobility_command(hass: Any, asset: dict[str, Any], role: str) -> dict[str, Any] | None:
    if role == "adjust":
        return _requested_power_command(asset)
    if role not in {"start", "stop"}:
        return None
    resolutions = asset.get("command_resolution") if isinstance(asset.get("command_resolution"), dict) else {}
    resolved = resolutions.get(role) if isinstance(resolutions.get(role), dict) else {}
    executor = str(resolved.get("physical_executor_asset_id") or asset.get("effective_connection_id") or "")
    if not executor:
        return None
    wanted_key = f"charger.command.{role}"
    for raw in _mobility_commands(hass):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("asset_id") or "") != executor or str(raw.get("command_key") or "") != wanted_key:
            continue
        row = deepcopy(raw)
        ready = bool(row.get("execution_allowed")) and bool(resolved.get("execution_allowed", True))
        row.update({
            "target_asset_id": str(asset.get("asset_id") or ""),
            "physical_executor_asset_id": executor,
            "logical_command_owner_asset_id": str(asset.get("asset_id") or ""),
            "producer_command_id": row.get("command_id"),
            "producer_command_key": row.get("command_key"),
            "manual_execution_ready": ready,
            "manual_blocked_reason": None if ready else str(resolved.get("blocked_reason") or row.get("blocked_reason") or "producer_command_not_ready"),
            "invoke": {
                "service": "rhi_mobility.execute_command",
                "data": {"asset_id": executor, "command_key": wanted_key},
            },
        })
        return row
    return None
