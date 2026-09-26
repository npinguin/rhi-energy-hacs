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
    PUBLIC_V2_ENTITY,
    PUBLIC_V2_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


def _compat_unique_id(entity_id: str) -> str:
    return f"rhi_energy:compat:{entity_id.split('.', 1)[1]}"


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
    """Enforce canonical public transport IDs before any Energy platform is loaded.

    Public V2 is the only authoritative UX transport. Its entity id is part of the
    canonical interface contract and cannot be left to device-prefixed naming.
    Existing rows reconcile by immutable unique-id, fresh installs reserve the exact
    address, and collisions fail closed. Frozen V1 compatibility IDs are handled in
    the same pre-platform transaction.


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
    public_v2_already_canonical = 0
    public_v2_renamed = 0
    public_v2_reserved = 0

    # Canonical Public V2 transport. The immutable unique-id locates the producer;
    # the exact entity-id is a governed interface address rather than presentation.
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
        _LOGGER.info("Renamed Energy Public V2 transport to canonical entity id: %s", PUBLIC_V2_ENTITY)
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
        "canonical_public_v2_entity": PUBLIC_V2_ENTITY,
        "canonical_public_v2_unique_id": PUBLIC_V2_UNIQUE_ID,
        "public_v2_already_canonical": public_v2_already_canonical,
        "public_v2_renamed_to_canonical": public_v2_renamed,
        "public_v2_reserved": public_v2_reserved,
        "removed_stale_template_registry_entries": removed,
        "already_owned_by_rhi_energy": already_owned,
        "renamed_energy_compatibility_entities": renamed_energy,
        "created_compatibility_registry_rows": created_contract_rows,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }


# Compatibility import for external tooling; runtime uses the authority-named API.
async_prepare_legacy_entity_takeover = async_prepare_public_entity_takeover
