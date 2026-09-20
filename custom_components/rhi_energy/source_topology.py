"""Home Assistant source-device topology for Energy troubleshooting.

Only exact source devices already accepted by Energy are considered. The helper never
uses HA device relationships as semantic truth. It only attaches native source roots
under the RHI Energy module for Home Assistant navigation while preserving each
integration's existing child hierarchy.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def _source_device_ids(model: dict[str, Any]) -> set[str]:
    return {
        str(((row.get("source_identity") or {}).get("device_registry_id")) or "")
        for row in (model.get("accepted_bindings") or [])
        if isinstance(row, dict)
        and (row.get("source_identity") or {}).get("device_registry_id")
    }


def _native_root(registry: dr.DeviceRegistry, device_id: str, module_device_id: str):
    device = registry.async_get(device_id)
    seen: set[str] = set()
    while device is not None and device.id not in seen:
        seen.add(device.id)
        parent_id = device.via_device_id
        if not parent_id or parent_id == module_device_id:
            return device
        parent = registry.async_get(parent_id)
        if parent is None:
            return device
        device = parent
    return device


async def async_sync_source_device_topology(
    hass: HomeAssistant,
    entry: ConfigEntry,
    model: dict[str, Any] | None,
    store,
) -> None:
    """Attach accepted native source roots to the Energy module for troubleshooting."""
    registry = dr.async_get(hass)
    module = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    if module is None:
        return

    desired: set[str] = set()
    for device_id in sorted(_source_device_ids(model or {})):
        root = _native_root(registry, device_id, module.id)
        if root is None or root.id == module.id:
            continue
        # Never steal a root that already belongs below another unrelated parent.
        if root.via_device_id not in (None, module.id):
            continue
        desired.add(root.id)

    state = store.data.setdefault("source_device_topology", {})
    previous = {str(value) for value in state.get("attached_root_device_ids") or [] if value}

    for device_id in sorted(desired):
        device = registry.async_get(device_id)
        if device is not None and device.via_device_id is None:
            registry.async_update_device(device_id, via_device_id=module.id)

    for device_id in sorted(previous - desired):
        device = registry.async_get(device_id)
        if device is not None and device.via_device_id == module.id:
            registry.async_update_device(device_id, via_device_id=None)

    if desired != previous:
        state["attached_root_device_ids"] = sorted(desired)
        state["source_device_count"] = len(_source_device_ids(model or {}))
        await store.async_save()
