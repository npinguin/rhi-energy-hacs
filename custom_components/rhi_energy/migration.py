"""Compatibility takeover and observability cleanup for RHI Energy V2."""
from __future__ import annotations

import logging

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


async def async_prepare_legacy_entity_takeover(hass: HomeAssistant) -> dict[str, int]:
    """Protect public compatibility IDs and remove obsolete RHI monitoring rows."""
    registry = er.async_get(hass)
    removed = 0
    already_owned = 0
    removed_obsolete_monitoring = 0

    # Public compatibility takeover remains strict: only stale Template rows may be removed.
    for entity_id in (*LEGACY_PUBLIC_ENTITIES, *LEGACY_DIAGNOSTIC_ENTITIES, COMPAT_READINESS_ENTITY):
        reg_entry = registry.async_get(entity_id)
        if reg_entry is None:
            continue
        platform = str(getattr(reg_entry, "platform", "") or "")
        if platform == DOMAIN:
            # These historical engineering entities are intentionally no longer
            # re-created in Baseline 1.7.0; cleanup happens by unique id below.
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

    # Baseline 1.7.0 replaces implementation-specific monitoring with four shared roles.
    for unique_id in OLD_MONITORING_UNIQUE_IDS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            removed_obsolete_monitoring += 1
            _LOGGER.info("Removed obsolete Energy monitoring entity: %s", entity_id)

    # Historical diagnostic compatibility entities and pilot-readiness are engineering
    # monitoring, not the 24 public Energy product interfaces. Remove RHI-owned rows.
    for entity_id in (*LEGACY_DIAGNOSTIC_ENTITIES, COMPAT_READINESS_ENTITY):
        reg_entry = registry.async_get(entity_id)
        if reg_entry is not None and str(getattr(reg_entry, "platform", "") or "") == DOMAIN:
            registry.async_remove(entity_id)
            removed_obsolete_monitoring += 1
            _LOGGER.info("Removed obsolete Energy diagnostic entity: %s", entity_id)

    return {
        "removed_stale_template_registry_entries": removed,
        "already_owned_by_rhi_energy": already_owned,
        "removed_obsolete_monitoring_entities": removed_obsolete_monitoring,
    }
