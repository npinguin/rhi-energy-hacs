"""Migration cleanup for retired Energy transport/monitoring entities.

Only entries owned by this integration and matching exact unique IDs are removed.
Native canonical asset, planning and value entity identities are untouched.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, OLD_MONITORING_UNIQUE_IDS, PUBLIC_V2_UNIQUE_ID


def cleanup_semantic_device_links(registry, entry_id: str) -> int:
    """Remove stale logical-to-logical HA via_device links, not source links.

    The old Energy DeviceInfo mapped semantic composition into native physical
    connectivity. Constrain cleanup to exact Energy logical identifiers and this
    config entry. Called before HA platforms republish verified physical gateway
    topology, so a legitimate explicit gateway link may be restored.
    """
    devices = tuple(registry.devices.values())
    by_id = {device.id: device for device in devices}
    removed = 0
    for device in devices:
        if entry_id not in (getattr(device, "config_entries", ()) or ()):
            continue
        identifiers = getattr(device, "identifiers", ()) or ()
        if not any(
            domain == DOMAIN and str(identifier).partition(":")[0] == "logical" and bool(str(identifier).partition(":")[2])
            for domain, identifier in identifiers
        ):
            continue
        parent_id = getattr(device, "via_device_id", None)
        parent = by_id.get(parent_id) if parent_id else None
        if parent is None:
            continue
        if not any(
            domain == DOMAIN and str(identifier).partition(":")[0] == "logical" and bool(str(identifier).partition(":")[2])
            for domain, identifier in (getattr(parent, "identifiers", ()) or ())
        ):
            continue
        registry.async_update_device(device.id, via_device_id=None)
        removed += 1
    return removed


async def async_cleanup_retired_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, int]:
    device_registry = dr.async_get(hass)
    removed_semantic_links = cleanup_semantic_device_links(device_registry, entry.entry_id)
    registry = er.async_get(hass)
    removed_transport = 0
    removed_obsolete_monitoring = 0
    for unique_id in (PUBLIC_V2_UNIQUE_ID,):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            removed_transport += 1
    for unique_id in OLD_MONITORING_UNIQUE_IDS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            removed_obsolete_monitoring += 1
    return {
        "removed_semantic_ha_device_links": removed_semantic_links,
        "removed_retired_public_v2_entities": removed_transport,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }
