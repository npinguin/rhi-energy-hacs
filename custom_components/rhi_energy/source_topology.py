"""Home Assistant source-device topology for Energy troubleshooting.

Only exact source devices already accepted by Energy or published by a producer domain
are considered. The helper never discovers sources or treats HA topology as semantic
truth. It only links real source devices to the Energy module when doing so does not
overwrite an existing native parent.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def _model_source_device_ids(model: dict[str, Any]) -> set[str]:
    return {
        str(((row.get("source_identity") or {}).get("device_registry_id")) or "")
        for row in (model.get("accepted_bindings") or [])
        if isinstance(row, dict)
        and (row.get("source_identity") or {}).get("device_registry_id")
    }


def _producer_source_device_ids(snapshot: dict[str, Any]) -> set[str]:
    """Return producer-published physical source device ids; never infer them."""
    out: set[str] = set()
    for collection in ("flexible_assets", "connections"):
        for row in snapshot.get(collection) or []:
            if not isinstance(row, dict):
                continue
            provenance = row.get("source_provenance") or {}
            device_id = (
                row.get("device_registry_id")
                or row.get("device_id")
                or (provenance.get("device_registry_id") if isinstance(provenance, dict) else None)
                or (provenance.get("device_id") if isinstance(provenance, dict) else None)
            )
            if device_id:
                out.add(str(device_id))
    return out


def source_device_ids(
    model: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
) -> set[str]:
    return _model_source_device_ids(model or {}) | _producer_source_device_ids(snapshot or {})


async def async_sync_source_device_topology(
    hass: HomeAssistant,
    entry: ConfigEntry,
    model: dict[str, Any] | None,
    store,
    snapshot: dict[str, Any] | None = None,
) -> None:
    """Attach exact real source devices to the Energy module when HA permits it.

    A source that already has a native parent keeps that parent. Energy never reparents
    an integration hierarchy or substitutes an integration/root device for the accepted
    physical device merely to make a Connected devices card appear.
    """
    registry = dr.async_get(hass)
    module = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    if module is None:
        return

    accepted = source_device_ids(model, snapshot)
    desired: set[str] = set()
    for device_id in sorted(accepted):
        device = registry.async_get(device_id)
        if device is None or device.id == module.id:
            continue
        if device.via_device_id not in (None, module.id):
            continue
        desired.add(device.id)

    state = store.data.setdefault("source_device_topology", {})
    previous = {str(value) for value in state.get("attached_source_device_ids") or [] if value}
    # Migrate the old key once. Its values represented roots and must not remain
    # authoritative after exact-source topology became the contract.
    previous |= {str(value) for value in state.pop("attached_root_device_ids", []) if value}

    for device_id in sorted(desired):
        device = registry.async_get(device_id)
        if device is not None and device.via_device_id is None:
            registry.async_update_device(device_id, via_device_id=module.id)

    for device_id in sorted(previous - desired):
        device = registry.async_get(device_id)
        if device is not None and device.via_device_id == module.id:
            registry.async_update_device(device_id, via_device_id=None)

    if desired != previous or state.get("source_device_count") != len(accepted):
        state["attached_source_device_ids"] = sorted(desired)
        state["source_device_count"] = len(accepted)
        await store.async_save()
