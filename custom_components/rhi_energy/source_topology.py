"""HA-native Energy source binding topology.

Energy semantic provenance points from a logical Energy asset to the exact existing
Home Assistant source device. HA device identity and hierarchy remain owned by the
source integration: Energy never copies source identifiers/connections and never uses
via_device to manufacture a Connected devices relationship.
"""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .runtime.canonical_structure import STRUCTURAL_CANONICAL_ASSETS


def _model_binding_rows(model: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for binding in model.get("accepted_bindings") or []:
        if not isinstance(binding, dict):
            continue
        identity = binding.get("source_identity") or {}
        device_id = identity.get("device_registry_id") if isinstance(identity, dict) else None
        if not device_id:
            continue
        rows.append({
            "source_device_id": str(device_id),
            "logical_asset_id": str(binding.get("asset_id") or binding.get("logical_asset_id") or binding.get("concept_id") or ""),
            "binding_id": str(binding.get("binding_id") or ""),
            "source_owner": str(binding.get("integration_domain") or identity.get("integration_domain") or ""),
        })
    return rows


def _producer_binding_rows(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for collection in ("flexible_assets", "connections"):
        for item in snapshot.get(collection) or []:
            if not isinstance(item, dict):
                continue
            provenance = item.get("source_provenance") or {}
            if not isinstance(provenance, dict):
                provenance = {}
            device_id = (
                item.get("device_registry_id")
                or item.get("device_id")
                or provenance.get("device_registry_id")
                or provenance.get("device_id")
            )
            if not device_id:
                continue
            rows.append({
                "source_device_id": str(device_id),
                "logical_asset_id": str(item.get("asset_id") or item.get("connection_asset_id") or ""),
                "binding_id": str(item.get("binding_id") or provenance.get("binding_id") or ""),
                "source_owner": str(item.get("source_domain") or provenance.get("source_domain") or "mobility"),
            })
    return rows


def source_binding_index(
    model: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return exact source-device provenance; never infer HA topology."""
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"logical_asset_ids": set(), "binding_ids": set(), "source_owners": set()}
    )
    for row in _model_binding_rows(model or {}) + _producer_binding_rows(snapshot or {}):
        device_id = row["source_device_id"]
        if row["logical_asset_id"]:
            grouped[device_id]["logical_asset_ids"].add(row["logical_asset_id"])
        if row["binding_id"]:
            grouped[device_id]["binding_ids"].add(row["binding_id"])
        if row["source_owner"]:
            grouped[device_id]["source_owners"].add(row["source_owner"])
    return {
        device_id: {
            "source_device_id": device_id,
            "logical_asset_ids": sorted(value["logical_asset_ids"]),
            "binding_ids": sorted(value["binding_ids"]),
            "source_owners": sorted(value["source_owners"]),
        }
        for device_id, value in grouped.items()
    }


def source_device_ids(
    model: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
) -> set[str]:
    return set(source_binding_index(model, snapshot))


async def async_sync_source_device_topology(
    hass: HomeAssistant,
    entry: ConfigEntry,
    model: dict[str, Any] | None,
    store,
    snapshot: dict[str, Any] | None = None,
) -> None:
    """Persist exact provenance and remove legacy Energy-created HA hierarchy."""
    started = perf_counter()
    registry = dr.async_get(hass)
    module = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    bindings = source_binding_index(model, snapshot)
    state = store.data.setdefault("source_device_topology", {})

    legacy_attached = {
        str(value)
        for key in ("attached_source_device_ids", "attached_root_device_ids")
        for value in state.pop(key, []) or []
        if value
    }
    if module is not None:
        for device_id in sorted(legacy_attached | set(bindings)):
            device = registry.async_get(device_id)
            if device is not None and device.via_device_id == module.id:
                registry.async_update_device(device.id, via_device_id=None)

    # Remove only obsolete Energy-owned proxy devices from older topology
    # experiments. Never delete a source device that belongs to another integration.
    entity_registry = er.async_get(hass)
    valid_energy_identifiers = {(DOMAIN, entry.entry_id), (DOMAIN, "logical:planning")}
    valid_energy_identifiers.update(
        (DOMAIN, f"logical:{asset['asset_id']}")
        for asset in STRUCTURAL_CANONICAL_ASSETS
        if asset.get("asset_id")
    )
    valid_energy_identifiers.update(
        (DOMAIN, f"logical:{asset['asset_id']}")
        for asset in (snapshot or {}).get("logical_assets") or []
        if isinstance(asset, dict) and asset.get("asset_id")
    )
    valid_energy_identifiers.update(
        (DOMAIN, f"logical:{asset_id}")
        for binding in bindings.values()
        for asset_id in binding.get("logical_asset_ids") or []
        if asset_id
    )
    entry_entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    occupied_device_ids = {
        entity.device_id
        for entity in entry_entities
        if entity.device_id
    }

    orphan_proxy_device_count = 0
    scanned_energy_device_count = 0
    for device in list(registry.devices.values()):
        if device.id == (module.id if module is not None else None):
            continue
        if set(device.config_entries) != {entry.entry_id}:
            continue
        scanned_energy_device_count += 1
        if any(identifier in valid_energy_identifiers for identifier in device.identifiers):
            continue
        if device.id in occupied_device_ids:
            continue
        registry.async_remove_device(device.id)
        orphan_proxy_device_count += 1

    next_state = {
        "source_device_count": len(bindings),
        "source_device_ids": sorted(bindings),
        "bindings_by_source_device_id": bindings,
        "binding_on_exact_source_device": True,
        "ha_relationship_model": "diagnostic_entity_on_existing_source_device",
        "via_device_links_created": 0,
        "copied_source_identity_devices_created": 0,
        "orphan_proxy_device_count": orphan_proxy_device_count,
    }
    current_structural = {
        key: value
        for key, value in state.items()
        if key not in {
            "last_sync_duration_ms",
            "sync_count",
            "last_scanned_energy_device_count",
            "last_entry_entity_count",
        }
    }
    if current_structural != next_state:
        state.clear()
        state.update(next_state)
        await store.async_save()
    else:
        state.update(next_state)

    state["last_sync_duration_ms"] = round((perf_counter() - started) * 1000, 3)
    state["sync_count"] = int(state.get("sync_count") or 0) + 1
    state["last_scanned_energy_device_count"] = scanned_energy_device_count
    state["last_entry_entity_count"] = len(entry_entities)
