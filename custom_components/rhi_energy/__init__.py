"""Robotix Home Intelligence Energy V2 integration — Shared Baseline 1.8.3."""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .builders.layered_manager import LayeredEnergyBuildManager as EnergyBuildManager
from .home_assistant_energy import async_ensure_home_assistant_energy_framework_provider
from .const import (
    DOMAIN,
    DOMAIN_ID,
    INTEROP_PROVIDER_REGISTRY_KEY,
    PLATFORMS,
    PROFILE_CATALOG_PROVIDER_ID,
    RELEASE,
    SHARED_BASELINE_VERSION,
)
from .runtime.interaction import EnergyInteractionEngine
from .runtime.metering import EnergyMetering
from .migration_cleanup import async_cleanup_retired_entities
from .profile_catalog import EnergyProfileCatalogProvider
from .visual_catalog import EnergyVisualAssetCatalogProvider
from .contracts.publication import EnergyBuildSpecificationProvider
from .runtime.engine_base import EnergyRuntime
from .services import async_register_services, async_unregister_services
from .runtime.storage import EnergyStore
from .supervision import (
    EnergyDomainSupervision,
    register_domain_supervision,
    unregister_domain_supervision,
)

_LOGGER = logging.getLogger(__name__)
_PUBLICATION_STATE_KEY = "__domain_build_specification_publication__"


def _shared_registry_api():
    """Load Foundation registry by capability, never by package release identity."""
    try:
        from custom_components.rhi_foundation.shared_registry import (
            register_domain_build_specification_provider,
            unregister_domain_build_specification_provider,
        )
    except Exception as exc:  # Foundation owns the shared registry implementation.
        raise ConfigEntryNotReady(
            f"foundation_shared_registry_api_unavailable:{type(exc).__name__}"
        ) from exc
    if not callable(register_domain_build_specification_provider) or not callable(
        unregister_domain_build_specification_provider
    ):
        raise ConfigEntryNotReady("foundation_shared_registry_capability_unavailable")
    return register_domain_build_specification_provider, unregister_domain_build_specification_provider


def _visual_registry_api():
    try:
        from custom_components.rhi_foundation.visual_asset_registry import (
            register_visual_asset_catalog_provider,
            unregister_visual_asset_catalog_provider,
        )
    except (ImportError, ModuleNotFoundError):
        return None, None
    return register_visual_asset_catalog_provider, unregister_visual_asset_catalog_provider


def _ensure_publication_provider(hass: HomeAssistant) -> EnergyBuildSpecificationProvider:
    """Register Energy's config-time publication and own its provider generation."""
    domain_state = hass.data.setdefault(DOMAIN, {})
    existing = domain_state.get(_PUBLICATION_STATE_KEY)
    if (
        isinstance(existing, dict)
        and isinstance(existing.get("provider"), EnergyBuildSpecificationProvider)
        and existing.get("registered") is True
    ):
        return existing["provider"]

    provider = (
        existing.get("provider")
        if isinstance(existing, dict)
        and isinstance(existing.get("provider"), EnergyBuildSpecificationProvider)
        else EnergyBuildSpecificationProvider.load()
    )
    register_provider, _unregister_provider = _shared_registry_api()
    unsubscribe = register_provider(
        hass,
        publisher_domain=DOMAIN,
        provider=provider,
        publication_revision=provider.publication_revision,
    )
    if not callable(unsubscribe):
        raise ConfigEntryNotReady("foundation_provider_registration_handle_unavailable")
    domain_state[_PUBLICATION_STATE_KEY] = {
        "provider": provider,
        "diagnostic": provider.diagnostic_record(),
        "unsubscribe": unsubscribe,
        "registered": True,
    }
    _LOGGER.info(
        "RHI Energy %s published %s DomainBuildSpecifications revision=%s",
        RELEASE,
        len(provider.specifications),
        provider.publication_revision,
    )
    return provider


def _unregister_publication_provider(hass: HomeAssistant) -> None:
    """Release only the provider generation owned by this Energy load."""
    state = hass.data.setdefault(DOMAIN, {}).get(_PUBLICATION_STATE_KEY)
    if not isinstance(state, dict) or state.get("registered") is not True:
        return
    unsubscribe = state.get("unsubscribe")
    if callable(unsubscribe):
        unsubscribe()
    state["unsubscribe"] = None
    state["registered"] = False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Publish build specifications before config-entry runtime setup.

    Publication is configuration-time domain metadata and must not depend on a
    successful semantic build/runtime activation. Foundation can therefore ingest
    Energy specifications even while Energy is not configured yet.
    """
    _ensure_publication_provider(hass)
    await async_ensure_home_assistant_energy_framework_provider(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    setup_started = perf_counter()
    setup_performance: dict[str, float] = {}

    stage_started = perf_counter()
    migration_cleanup = await async_cleanup_retired_entities(hass, entry)
    setup_performance["migration_cleanup_ms"] = round((perf_counter() - stage_started) * 1000, 3)

    provider = _ensure_publication_provider(hass)
    store = EnergyStore(hass)
    stage_started = perf_counter()
    await store.async_load()
    setup_performance["store_load_ms"] = round((perf_counter() - stage_started) * 1000, 3)
    manager = EnergyBuildManager(hass)
    runtime = EnergyRuntime(hass, store)
    metering = EnergyMetering(hass, store, runtime)
    interaction = EnergyInteractionEngine(hass, store, runtime, metering, manager)
    supervision = EnergyDomainSupervision(hass, entry.entry_id)
    profile_catalog_provider = EnergyProfileCatalogProvider()
    visual_catalog_provider = EnergyVisualAssetCatalogProvider()
    interop = hass.data.setdefault(INTEROP_PROVIDER_REGISTRY_KEY, {})
    visual_registration_unsub = None
    services = None
    manager.add_model_callback(runtime.activate_model)
    try:
        services = await async_register_services(hass, interaction, manager)
        state = {
            "provider": provider, "store": store, "build_manager": manager, "runtime": runtime,
            "metering": metering, "interaction": interaction,
            "services": services, "migration_cleanup": migration_cleanup, "supervision": supervision,
            "supervision_unsubscribe": None,
            "profile_catalog_provider": profile_catalog_provider,
            "visual_catalog_provider": visual_catalog_provider,
            "visual_registration_unsub": None,
            "setup_performance": setup_performance,
            "execution_model": "prebound_canonical_v2_runtime",
            "shared_baseline_version": SHARED_BASELINE_VERSION,
        }
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = state
        interop[PROFILE_CATALOG_PROVIDER_ID] = profile_catalog_provider
        register_visual, _unregister_visual = _visual_registry_api()
        if callable(register_visual):
            handle = register_visual(
                hass,
                publisher_domain=DOMAIN,
                provider=visual_catalog_provider,
                publication_revision=visual_catalog_provider.publication_revision,
            )
            visual_registration_unsub = handle if callable(handle) else None
            state["visual_registration_unsub"] = visual_registration_unsub
        stage_started = perf_counter()
        await manager.async_start()
        setup_performance["manager_start_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        # Canonical HA-device convergence is presentation work, not an Energy
        # runtime activation prerequisite. Slow/large source integrations must never
        # keep Public V2 or the HA platforms behind Device Registry reconciliation.
        stage_started = perf_counter()
        await metering.async_start()
        setup_performance["metering_start_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        stage_started = perf_counter()
        await interaction.async_start()
        setup_performance["interaction_start_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        stage_started = perf_counter()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        setup_performance["platform_setup_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        # Pre-topology boot model: canonical HA devices are materialized naturally
        # by Home Assistant from entity DeviceInfo during platform registration.
        # Energy never performs a second explicit Device Registry convergence pass.
        setup_performance["canonical_device_sync_mode"] = "entity_device_info_only"

        # Shared Baseline 1.8.3 supervision is structural, not telemetry-driven.
        # Foundation 1.8.3 additionally makes provider lifetime generation-safe.
        stage_started = perf_counter()
        state["supervision_unsubscribe"] = register_domain_supervision(hass, supervision)
        setup_performance["supervision_registration_ms"] = round((perf_counter() - stage_started) * 1000, 3)
        setup_performance["total_setup_ms"] = round((perf_counter() - setup_started) * 1000, 3)
    except Exception:
        _LOGGER.exception("RHI Energy setup failed")
        await interaction.async_stop()
        await metering.async_stop()
        await runtime.async_stop()
        await manager.async_stop()
        await async_unregister_services(hass, services)
        state = (hass.data.get(DOMAIN) or {}).get(entry.entry_id) or {}
        supervision_unsubscribe = state.get("supervision_unsubscribe")
        if callable(supervision_unsubscribe):
            supervision_unsubscribe()
        else:
            unregister_domain_supervision(hass, supervision)
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if interop.get(PROFILE_CATALOG_PROVIDER_ID) is profile_catalog_provider:
            interop.pop(PROFILE_CATALOG_PROVIDER_ID, None)
        if callable(visual_registration_unsub):
            visual_registration_unsub()
        # Keep DBS publication registered after a runtime setup failure. It is an
        # independent configuration-time contract and lets Foundation diagnose/configure.
        raise
    _LOGGER.info("RHI Energy %s setup complete", RELEASE)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    state = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    interop = hass.data.get(INTEROP_PROVIDER_REGISTRY_KEY, {})
    profile_catalog_provider = state.get("profile_catalog_provider")
    if interop.get(PROFILE_CATALOG_PROVIDER_ID) is profile_catalog_provider:
        interop.pop(PROFILE_CATALOG_PROVIDER_ID, None)
    visual_registration_unsub = state.get("visual_registration_unsub")
    if callable(visual_registration_unsub):
        visual_registration_unsub()
    supervision = state.get("supervision")
    supervision_unsubscribe = state.get("supervision_unsubscribe")
    if callable(supervision_unsubscribe):
        supervision_unsubscribe()
    elif isinstance(supervision, EnergyDomainSupervision):
        unregister_domain_supervision(hass, supervision)
    for key in (
        "button_projection",
        "logical_action_button_projection",
        "number_projection",
        "logical_number_projection",
        "select_projection",
        "switch_projection",
        "datetime_projection",
        "entity_projection",
        "interaction",
        "metering",
        "runtime",
        "build_manager",
    ):
        obj = state.get(key)
        if obj is not None and hasattr(obj, "async_stop"):
            await obj.async_stop()
    await async_unregister_services(hass, state.get("services"))
    # Provider absence during unload/reload is structural availability only.
    # Persisted Energy technical intent remains Foundation-owned and survives reload.
    _unregister_publication_provider(hass)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove Foundation-owned Energy technical intent only on genuine entry deletion."""
    from custom_components.rhi_foundation.shared_registry import (
        async_remove_domain_configuration,
    )

    await async_remove_domain_configuration(
        hass,
        domain_id=DOMAIN_ID,
        publisher_domain=DOMAIN,
    )
