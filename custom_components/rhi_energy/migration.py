"""Compatibility takeover and observability cleanup for RHI Energy V2."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    COMPAT_READINESS_ENTITY,
    DOMAIN,
    LEGACY_DIAGNOSTIC_ENTITIES,
    LEGACY_PUBLIC_ENTITIES,
    OLD_MONITORING_UNIQUE_IDS,
)

_LOGGER = logging.getLogger(__name__)


def _compat_unique_id(entity_id: str) -> str:
    return f"rhi_energy:compat:{entity_id.split('.', 1)[1]}"


async def async_prepare_legacy_entity_takeover(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, int]:
    """Protect exact V1 compatibility IDs and migrate previous Energy-owned rows.

    E0.12.1 allowed Home Assistant's device-based entity naming to prefix the
    compatibility object ids.  The public contract however requires the exact
    canonical ``sensor.energy_*`` ids.  This migration makes those ids explicit in
    the registry before the sensor platform is loaded and renames already-created
    Energy rows in place.  A live non-registry YAML entity still blocks takeover so
    two producers can never own the same public id concurrently.
    """
    registry = er.async_get(hass)
    removed = 0
    already_owned = 0
    renamed_energy = 0
    created_contract_rows = 0
    removed_obsolete_monitoring = 0

    compatibility_entities = (*LEGACY_PUBLIC_ENTITIES, *LEGACY_DIAGNOSTIC_ENTITIES)

    for entity_id in (*compatibility_entities, COMPAT_READINESS_ENTITY):
        reg_entry = registry.async_get(entity_id)
        if reg_entry is None:
            # A legacy YAML/template entity can exist only in the state machine. Do
            # not silently trample it; the YAML package must be disabled first.
            live = hass.states.get(entity_id)
            if live is not None:
                raise ConfigEntryNotReady(f"legacy_energy_yaml_still_active:{entity_id}")
            continue
        platform = str(getattr(reg_entry, "platform", "") or "")
        if platform == DOMAIN:
            already_owned += 1
            continue
        if platform != "template":
            raise ConfigEntryNotReady(f"legacy_entity_id_owned_by_unexpected_platform:{entity_id}:{platform}")
        live = hass.states.get(entity_id)
        if live is not None:
            raise ConfigEntryNotReady(f"legacy_energy_yaml_still_active:{entity_id}")
        registry.async_remove(entity_id)
        _LOGGER.info("Removed stale legacy Template registry row for compatibility takeover: %s", entity_id)
        removed += 1

    # Canonicalize existing E0.12.1 Energy-owned compatibility rows whose entity ids
    # were prefixed with the Energy device name, then reserve exact ids for fresh
    # installs so the sensor platform adopts them by unique_id.
    for entity_id in compatibility_entities:
        unique_id = _compat_unique_id(entity_id)
        current_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if current_id and current_id != entity_id:
            if registry.async_get(entity_id) is not None:
                raise ConfigEntryNotReady(f"compatibility_entity_id_conflict:{entity_id}:{current_id}")
            registry.async_update_entity(current_id, new_entity_id=entity_id)
            renamed_energy += 1
            current_id = entity_id
            _LOGGER.info("Renamed Energy compatibility entity to canonical V1 id: %s", entity_id)
        if current_id is None:
            registry.async_get_or_create(
                "sensor",
                DOMAIN,
                unique_id,
                suggested_object_id=entity_id.split(".", 1)[1],
                config_entry=entry,
            )
            created_contract_rows += 1

    # Shared monitoring replaces implementation-specific monitoring unique IDs.
    for unique_id in OLD_MONITORING_UNIQUE_IDS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            removed_obsolete_monitoring += 1
            _LOGGER.info("Removed obsolete Energy monitoring entity: %s", entity_id)

    # Pilot-readiness is obsolete internal monitoring. The five historical
    # diagnostic entities remain a deliberate V1 compatibility facade.
    reg_entry = registry.async_get(COMPAT_READINESS_ENTITY)
    if reg_entry is not None and str(getattr(reg_entry, "platform", "") or "") == DOMAIN:
        registry.async_remove(COMPAT_READINESS_ENTITY)
        removed_obsolete_monitoring += 1
        _LOGGER.info("Removed obsolete Energy pilot-readiness entity: %s", COMPAT_READINESS_ENTITY)

    return {
        "removed_stale_template_registry_entries": removed,
        "already_owned_by_rhi_energy": already_owned,
        "renamed_energy_compatibility_entities": renamed_energy,
        "created_compatibility_registry_rows": created_contract_rows,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }
