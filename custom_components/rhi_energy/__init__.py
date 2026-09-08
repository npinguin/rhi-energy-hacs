"""Robotix Home Intelligence Energy V2 integration — Shared Baseline 1.7.0."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .builders.build_manager import EnergyBuildManager
from .const import DOMAIN, PLATFORMS, RELEASE
from .runtime.interaction import EnergyInteractionEngine
from .runtime.metering import EnergyMetering
from .migration import async_prepare_legacy_entity_takeover
from .public_contract import PublicContractProjector
from .contracts.publication import EnergyBuildSpecificationProvider
from .runtime.engine import EnergyRuntime
from .services import async_register_services, async_unregister_services
from .runtime.storage import EnergyStore

_LOGGER = logging.getLogger(__name__)
_PUBLICATION_STATE_KEY = "__domain_build_specification_publication__"


def _shared_registry_api():
    try:
        from custom_components.rhi_foundation.shared_registry import (
            register_domain_build_specification_provider,
            unregister_domain_build_specification_provider,
        )
    except Exception as exc:  # Foundation owns the shared registry implementation.
        raise ConfigEntryNotReady(f"foundation_shared_registry_api_unavailable:{type(exc).__name__}") from exc
    return register_domain_build_specification_provider, unregister_domain_build_specification_provider


def _ensure_publication_provider(hass: HomeAssistant) -> EnergyBuildSpecificationProvider:
    """Register Energy's bounded config-time publication independently of domain runtime build state."""
    domain_state = hass.data.setdefault(DOMAIN, {})
    existing = domain_state.get(_PUBLICATION_STATE_KEY)
    if isinstance(existing, dict) and isinstance(existing.get("provider"), EnergyBuildSpecificationProvider):
        return existing["provider"]

    provider = EnergyBuildSpecificationProvider.load()
    register_provider, _ = _shared_registry_api()
    register_provider(
        hass,
        publisher_domain=DOMAIN,
        provider=provider,
        publication_revision=provider.publication_revision,
    )
    domain_state[_PUBLICATION_STATE_KEY] = {
        "provider": provider,
        "diagnostic": provider.diagnostic_record(),
    }
    _LOGGER.info(
        "RHI Energy %s published %s DomainBuildSpecifications revision=%s",
        RELEASE,
        len(provider.specifications),
        provider.publication_revision,
    )
    return provider


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Publish build specifications before config-entry runtime setup.

    Publication is configuration-time domain metadata and must not depend on a
    successful semantic build/runtime activation. Foundation can therefore ingest
    Energy specifications even while Energy is not configured yet.
    """
    _ensure_publication_provider(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    migration = await async_prepare_legacy_entity_takeover(hass)
    provider = _ensure_publication_provider(hass)
    store = EnergyStore(hass)
    await store.async_load()
    manager = EnergyBuildManager(hass)
    runtime = EnergyRuntime(hass, store)
    metering = EnergyMetering(hass, store, runtime)
    interaction = EnergyInteractionEngine(hass, store, runtime, metering, manager)
    projector = PublicContractProjector(runtime, store, metering, interaction, manager)
    services = None
    manager.add_model_callback(runtime.activate_model)
    try:
        services = await async_register_services(hass, interaction, manager)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "provider": provider, "store": store, "build_manager": manager, "runtime": runtime,
            "metering": metering, "interaction": interaction, "public_projector": projector,
            "services": services, "migration": migration,
            "execution_model": "compiled_model_direct_source_listeners",
            "shared_baseline_version": "1.7.0",
        }
        await manager.async_start()
        runtime.activate_model(manager.compiled_model)
        await metering.async_start()
        await interaction.async_start()
        projector.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        _LOGGER.exception("RHI Energy setup failed")
        await projector.async_stop()
        await interaction.async_stop()
        await metering.async_stop()
        await runtime.async_stop()
        await manager.async_stop()
        await async_unregister_services(hass, services)
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        # Do not unregister the DomainBuildSpecification provider here. Publication
        # is an independent configuration-time contract and remains available so
        # Foundation can diagnose/configure the domain after a runtime setup failure.
        raise
    _LOGGER.info("RHI Energy %s setup complete", RELEASE)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    state = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    for key in ("entity_projection", "public_projector", "interaction", "metering", "runtime", "build_manager"):
        obj = state.get(key)
        if obj is not None and hasattr(obj, "async_stop"):
            await obj.async_stop()
    await async_unregister_services(hass, state.get("services"))
    # DomainBuildSpecification publication belongs to the loaded integration domain,
    # not to one config-entry runtime instance. Keep it registered across entry
    # reload/unload so Foundation never observes a spurious provider disappearance.
    return True
