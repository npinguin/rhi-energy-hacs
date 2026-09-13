"""Small Energy boundary for the currently supported producer domain: Mobility.

Mobility owns physical charger/vehicle semantics and execution. Energy only consumes the
public Mobility Energy asset/command surfaces.  This file intentionally is *not* a
plugin registry; add a second producer only when a second real producer domain exists.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant

from ..compat_core import jload
from ..const import MOBILITY_ASSET_ENTITY, MOBILITY_COMMAND_ENTITY


def mobility_entity_ids() -> tuple[str, str]:
    return MOBILITY_ASSET_ENTITY, MOBILITY_COMMAND_ENTITY


def read_mobility_energy_assets(
    hass: HomeAssistant,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
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
    return (
        consumers if isinstance(consumers, list) else [],
        connections if isinstance(connections, list) else [],
        metadata,
    )


def _mobility_commands(hass: HomeAssistant) -> list[dict[str, Any]]:
    state = hass.states.get(MOBILITY_COMMAND_ENTITY)
    if not state:
        return []
    rows = jload(state.attributes.get("commands_json") or state.attributes.get("commands"), [])
    return rows if isinstance(rows, list) else []


def resolve_mobility_command(
    hass: HomeAssistant,
    asset: dict[str, Any],
    role: str,
) -> dict[str, Any] | None:
    refs = asset.get("command_refs") if isinstance(asset.get("command_refs"), dict) else {}
    key = {"start": "start", "stop": "stop", "adjust": "adjust_power"}.get(role, role)
    ref = refs.get(key)
    if ref is None and role == "adjust":
        ref = refs.get("set_power")
    if ref is None:
        return None
    wanted = str(
        (ref.get("command_instance_id") or ref.get("command_id") or ref.get("command_key") or "")
        if isinstance(ref, dict)
        else ref
    )
    if not wanted:
        return None
    target = str(asset.get("asset_id") or "")
    for row in _mobility_commands(hass):
        if not isinstance(row, dict):
            continue
        ids = {
            str(row.get("command_instance_id") or ""),
            str(row.get("command_id") or ""),
            str(row.get("command_key") or ""),
        }
        row_target = str(row.get("target_asset_id") or row.get("asset_id") or "")
        if wanted in ids and (not row_target or row_target == target):
            return deepcopy(row)
    return None
