"""Migration cleanup for retired Energy transport/monitoring entities.

Only entries owned by this integration and matching exact unique IDs are removed.
Native canonical asset, planning and value entity identities are untouched.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, OLD_MONITORING_UNIQUE_IDS, PUBLIC_V2_UNIQUE_ID


async def async_cleanup_retired_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, int]:
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
        "removed_retired_public_v2_entities": removed_transport,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }
