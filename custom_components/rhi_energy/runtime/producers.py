"""Energy boundary for public Mobility V2 HA contract surfaces."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .canonical_semantics import jload
from ..const import MOBILITY_COMMAND_V2_ENTITY, MOBILITY_ENERGY_V2_ENTITY


def mobility_entity_ids() -> tuple[str, str]:
    return MOBILITY_ENERGY_V2_ENTITY, MOBILITY_COMMAND_V2_ENTITY


def read_mobility_energy_assets(hass: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    state = hass.states.get(MOBILITY_ENERGY_V2_ENTITY)
    if not state:
        return [], [], {}
    attrs = state.attributes
    if attrs.get("contract_id") != "MOBILITY_ENERGY_V2":
        return [], [], {}
    if attrs.get("publisher") != "rhi_mobility" or attrs.get("command_provider_id") != "mobility.command.v2" or attrs.get("contains_physical_bindings") is True:
        return [], [], {}
    consumers = jload(attrs.get("consumer_assets"), [])
    connections = jload(attrs.get("connection_assets"), [])
    metadata = {
        "contract_id": attrs.get("contract_id"),
        "publisher": attrs.get("publisher"),
        "command_provider_id": attrs.get("command_provider_id"),
        "contains_physical_bindings": bool(attrs.get("contains_physical_bindings")),
        "periodization_owner": attrs.get("periodization_owner"),
        "attribution_owner": attrs.get("attribution_owner"),
        "planning_owner": attrs.get("planning_owner"),
        "physical_execution_owner": attrs.get("physical_execution_owner"),
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
    published = limits.get("requested_power_command") if isinstance(limits.get("requested_power_command"), dict) else {}
    target = str(published.get("physical_executor_asset_id") or limits.get("requested_power_kw_write_asset_id") or asset.get("effective_connection_id") or "")
    supported = published.get("supported", limits.get("requested_power_kw_write_supported"))
    if supported is not True or not target:
        return None
    invoke = deepcopy(published.get("invoke")) if isinstance(published.get("invoke"), dict) else {
        "service": "rhi_mobility.set_requested_power", "data": {"asset_id": target}
    }
    invoke["parameter_map"] = deepcopy(published.get("parameter_map")) if isinstance(published.get("parameter_map"), dict) else {"requested_power_kw": "power_kw"}
    ready = bool(limits.get("requested_power_execution_ready"))
    return {
        "command_id": "mobility.requested_power.write",
        "command_key": str(published.get("command_key") or "charger.requested_charge_power_kw"),
        "provider_id": str(published.get("provider_id") or "mobility.command.v2"),
        "asset_id": str(asset.get("asset_id") or ""),
        "target_asset_id": str(asset.get("asset_id") or ""),
        "physical_executor_asset_id": target,
        "supported": True,
        "manual_execution_ready": ready,
        "manual_blocked_reason": None if ready else "mobility_requested_power_not_ready",
        "invoke": invoke,
    }


def resolve_mobility_command(hass: Any, asset: dict[str, Any], role: str) -> dict[str, Any] | None:
    if role == "adjust":
        return _requested_power_command(asset)
    if role not in {"start", "stop"}:
        return None
    resolutions = asset.get("command_resolution") if isinstance(asset.get("command_resolution"), dict) else {}
    resolved = resolutions.get(role) if isinstance(resolutions.get(role), dict) else {}
    published_ref = resolved.get("producer_command_ref") if isinstance(resolved.get("producer_command_ref"), dict) else {}
    executor = str(published_ref.get("physical_executor_asset_id") or resolved.get("physical_executor_asset_id") or asset.get("effective_connection_id") or "")
    if not executor:
        return None
    wanted_key = str(published_ref.get("command_key") or resolved.get("producer_command_key") or f"charger.command.{role}")
    wanted_id = published_ref.get("command_id") if published_ref else None
    for raw in _mobility_commands(hass):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("asset_id") or "") != executor or str(raw.get("command_key") or "") != wanted_key:
            continue
        if wanted_id not in (None, "") and str(raw.get("command_id") or "") != str(wanted_id):
            continue
        row = deepcopy(raw)
        ready = bool(row.get("execution_allowed")) and bool(resolved.get("execution_allowed", True))
        invoke = deepcopy(published_ref.get("invoke")) if isinstance(published_ref.get("invoke"), dict) else (
            deepcopy(row.get("invoke")) if isinstance(row.get("invoke"), dict)
            else {"service": "rhi_mobility.execute_command", "data": {"asset_id": executor, "command_key": wanted_key}}
        )
        row.update({
            "target_asset_id": str(asset.get("asset_id") or ""),
            "physical_executor_asset_id": executor,
            "logical_command_owner_asset_id": str(asset.get("asset_id") or ""),
            "producer_command_id": row.get("command_id"),
            "producer_command_key": row.get("command_key"),
            "producer_command_ref": {
                "provider_id": str(published_ref.get("provider_id") or row.get("provider_id") or "mobility.command.v2"),
                "command_id": row.get("command_id"),
                "command_key": row.get("command_key"),
                "physical_executor_asset_id": executor,
                "invoke": deepcopy(invoke),
            },
            "manual_execution_ready": ready,
            "manual_blocked_reason": None if ready else str(resolved.get("blocked_reason") or row.get("blocked_reason") or "producer_command_not_ready"),
            "invoke": invoke,
        })
        return row
    return None
