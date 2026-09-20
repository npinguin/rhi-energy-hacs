"""Energy boundary for Mobility public asset and command contracts."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..compat_core import jload
from ..const import MOBILITY_ASSET_ENTITY, MOBILITY_COMMAND_ENTITY


def mobility_entity_ids() -> tuple[str, str]:
    return MOBILITY_ASSET_ENTITY, MOBILITY_COMMAND_ENTITY


def read_mobility_energy_assets(hass: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    state = hass.states.get(MOBILITY_ASSET_ENTITY)
    if not state:
        return [], [], {}
    consumers = jload(state.attributes.get("consumer_assets") or state.attributes.get("consumer_assets_json"), [])
    connections = jload(state.attributes.get("connection_assets") or state.attributes.get("connection_assets_json") or state.attributes.get("connections_json"), [])
    metadata = dict(state.attributes)
    metadata.update({
        "source_entity_id": MOBILITY_ASSET_ENTITY,
        "source_state": state.state,
        "source_last_updated": state.last_updated.isoformat(),
        "source_last_changed": state.last_changed.isoformat(),
    })
    return consumers if isinstance(consumers, list) else [], connections if isinstance(connections, list) else [], metadata


def _mobility_commands(hass: Any) -> list[dict[str, Any]]:
    state = hass.states.get(MOBILITY_COMMAND_ENTITY)
    if not state:
        return []
    rows = jload(state.attributes.get("commands_json") or state.attributes.get("commands"), [])
    return rows if isinstance(rows, list) else []


def _requested_power_command(asset: dict[str, Any]) -> dict[str, Any] | None:
    limits = asset.get("limits") if isinstance(asset.get("limits"), dict) else {}
    if limits.get("requested_power_kw_write_supported") is not True:
        return None
    domain = str(limits.get("requested_power_kw_write_service_domain") or "")
    action = str(limits.get("requested_power_kw_write_service_action") or "")
    target = str(limits.get("requested_power_kw_write_asset_id") or asset.get("effective_connection_id") or asset.get("assigned_connection_id") or asset.get("asset_id") or "")
    if not domain or not action or not target:
        return None
    ready = bool(limits.get("requested_power_execution_ready"))
    return {
        "command_id": "mobility.requested_power.write",
        "command_key": "charger.requested_charge_power_kw",
        "asset_id": str(asset.get("asset_id") or ""),
        "target_asset_id": str(asset.get("asset_id") or ""),
        "supported": True,
        "manual_execution_ready": ready,
        "availability": "AVAILABLE" if ready else "UNAVAILABLE",
        "manual_blocked_reason": None if ready else "mobility_requested_power_not_ready",
        "invoke": {
            "service": f"{domain}.{action}",
            "data": {str(limits.get("requested_power_kw_write_asset_field") or "asset_id"): target},
            "parameter_map": {"requested_power_kw": str(limits.get("requested_power_kw_write_value_field") or "power_kw")},
        },
    }


def _ready(row: dict[str, Any]) -> bool:
    return bool(row.get("execution_allowed") or row.get("action_available") or row.get("public_execution_allowed"))


def _invoke(row: dict[str, Any], executor: str, command_key: str) -> dict[str, Any]:
    out = deepcopy(row)
    if not out.get("invoke") and not out.get("service") and executor and command_key:
        out["invoke"] = {
            "service": "rhi_mobility.execute_command",
            "data": {"asset_id": executor, "command_key": command_key},
        }
    return out


def resolve_mobility_command(hass: Any, asset: dict[str, Any], role: str) -> dict[str, Any] | None:
    """Resolve exact producer-published logical-to-physical command authority."""
    if role == "adjust":
        return _requested_power_command(asset)
    if role not in {"start", "stop"}:
        return None

    command_key = f"charger.command.{role}"
    resolutions = asset.get("command_resolution") if isinstance(asset.get("command_resolution"), dict) else {}
    resolved = resolutions.get(role) if isinstance(resolutions.get(role), dict) else {}
    executor = str(resolved.get("physical_executor_asset_id") or resolved.get("command_source_asset_id") or "")
    if executor and resolved.get("binding_available") is True:
        for raw in _mobility_commands(hass):
            if not isinstance(raw, dict):
                continue
            target = str(raw.get("target_asset_id") or raw.get("asset_id") or "")
            key = str(raw.get("canonical_command_key") or raw.get("command_key") or "")
            command_id = str(raw.get("command_instance_id") or raw.get("command_id") or "")
            if target != executor or (key != command_key and command_id != f"{executor}:{command_key}"):
                continue
            row = _invoke(raw, executor, command_key)
            ready = _ready(row) and bool(resolved.get("execution_allowed"))
            row.update({
                "target_asset_id": str(asset.get("asset_id") or ""),
                "physical_executor_asset_id": executor,
                "logical_command_owner_asset_id": str(asset.get("asset_id") or ""),
                "manual_execution_ready": ready,
                "manual_blocked_reason": None if ready else str(resolved.get("blocked_reason") or row.get("blocked_reason") or "producer_command_not_ready"),
            })
            return row
        return None

    refs = asset.get("command_refs") if isinstance(asset.get("command_refs"), dict) else {}
    ref = refs.get(role)
    wanted = str((ref.get("command_instance_id") or ref.get("command_id") or ref.get("command_key") or "") if isinstance(ref, dict) else ref or "")
    target = str(asset.get("asset_id") or "")
    if not wanted:
        return None
    for raw in _mobility_commands(hass):
        if not isinstance(raw, dict):
            continue
        ids = {str(raw.get(k) or "") for k in ("command_instance_id", "command_id", "command_key")}
        row_target = str(raw.get("target_asset_id") or raw.get("asset_id") or "")
        if wanted not in ids or (row_target and row_target != target):
            continue
        executor = str(raw.get("physical_executor_asset_id") or "")
        key = str(raw.get("canonical_command_key") or "")
        row = _invoke(raw, executor, key)
        row["manual_execution_ready"] = _ready(row)
        return row
    return None
