"""Canonical Public V2 registry preparation and retired-surface cleanup."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    OLD_MONITORING_UNIQUE_IDS,
    PUBLIC_V2_ENTITY,
    PUBLIC_V2_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


def canonical_public_v2_transport_status(hass: HomeAssistant) -> dict[str, object]:
    """Return exact registry/live-state proof for the canonical Public V2 endpoint."""
    registry = er.async_get(hass)
    current_id = registry.async_get_entity_id("sensor", DOMAIN, PUBLIC_V2_UNIQUE_ID)
    row = registry.async_get(current_id) if current_id else None
    result = {
        "expected_entity_id": PUBLIC_V2_ENTITY,
        "current_entity_id": current_id,
        "unique_id": getattr(row, "unique_id", None),
        "registered": row is not None,
        "owned_by_energy": getattr(row, "platform", None) == DOMAIN if row is not None else False,
        "canonical_entity_id_match": current_id == PUBLIC_V2_ENTITY,
        "canonical_unique_id_match": getattr(row, "unique_id", None) == PUBLIC_V2_UNIQUE_ID if row is not None else False,
        "live_state_present": hass.states.get(PUBLIC_V2_ENTITY) is not None,
    }
    result["ready"] = all((
        result["registered"],
        result["owned_by_energy"],
        result["canonical_entity_id_match"],
        result["canonical_unique_id_match"],
        result["live_state_present"],
    ))
    return result


async def async_prepare_public_entity_takeover(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, int]:
    """Reserve the single canonical Public V2 transport and remove obsolete monitoring."""
    registry = er.async_get(hass)
    removed_obsolete_monitoring = 0
    public_v2_already_canonical = 0
    public_v2_renamed = 0
    public_v2_reserved = 0

    target_entry = registry.async_get(PUBLIC_V2_ENTITY)
    current_v2_id = registry.async_get_entity_id("sensor", DOMAIN, PUBLIC_V2_UNIQUE_ID)
    if target_entry is not None:
        target_platform = str(getattr(target_entry, "platform", "") or "")
        target_unique_id = str(getattr(target_entry, "unique_id", "") or "")
        if target_platform != DOMAIN or target_unique_id != PUBLIC_V2_UNIQUE_ID:
            raise ConfigEntryNotReady(
                f"canonical_public_v2_entity_id_conflict:{PUBLIC_V2_ENTITY}:"
                f"{target_platform}:{target_unique_id}"
            )
    if current_v2_id is not None and current_v2_id != PUBLIC_V2_ENTITY:
        if target_entry is not None:
            raise ConfigEntryNotReady(
                f"canonical_public_v2_entity_id_conflict:{PUBLIC_V2_ENTITY}:{current_v2_id}"
            )
        registry.async_update_entity(current_v2_id, new_entity_id=PUBLIC_V2_ENTITY)
        public_v2_renamed = 1
        current_v2_id = PUBLIC_V2_ENTITY
    elif current_v2_id == PUBLIC_V2_ENTITY:
        public_v2_already_canonical = 1

    if current_v2_id is None:
        if target_entry is None and hass.states.get(PUBLIC_V2_ENTITY) is not None:
            raise ConfigEntryNotReady(f"canonical_public_v2_state_conflict:{PUBLIC_V2_ENTITY}")
        registry.async_get_or_create(
            "sensor", DOMAIN, PUBLIC_V2_UNIQUE_ID,
            suggested_object_id=PUBLIC_V2_ENTITY.split(".", 1)[1],
            config_entry=entry,
        )
        public_v2_reserved = 1

    for unique_id in OLD_MONITORING_UNIQUE_IDS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            removed_obsolete_monitoring += 1

    return {
        "canonical_public_v2_entity": PUBLIC_V2_ENTITY,
        "canonical_public_v2_unique_id": PUBLIC_V2_UNIQUE_ID,
        "public_v2_already_canonical": public_v2_already_canonical,
        "public_v2_renamed_to_canonical": public_v2_renamed,
        "public_v2_reserved": public_v2_reserved,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }
