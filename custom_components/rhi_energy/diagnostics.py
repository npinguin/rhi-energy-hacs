"""Bounded Home Assistant config-entry diagnostics for RHI Energy V2."""
from __future__ import annotations

from copy import deepcopy
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    LEGACY_CONTRACT_VERSION,
    RELEASE,
    RELEASE_NAME,
    SHARED_BASELINE_CHECKSUM,
    SHARED_BASELINE_VERSION,
)


def _binding_row(binding):
    source = binding.get("source_identity") or {}
    return {
        "binding_id": binding.get("binding_id"),
        "candidate_id": binding.get("candidate_id"),
        "technical_capability": binding.get("technical_capability"),
        "raw_capability_id": binding.get("raw_capability_id"),
        "target_scope": binding.get("target_scope"),
        "entity_registry_id": source.get("entity_registry_id"),
        "unique_id": source.get("unique_id"),
        "current_entity_id": source.get("current_entity_id"),
        "integration_domain": source.get("integration_domain"),
        "binding_revision": binding.get("binding_revision"),
        "resolution_revision": binding.get("resolution_revision"),
    }


def _selected_input_row(item):
    selection = item.get("selection") or {}
    assessment = item.get("discovery_assessment") or {}
    evidence_by_id = {
        str(row.get("candidate_id")): row
        for row in (item.get("candidate_evidence") or [])
        if isinstance(row, dict) and row.get("candidate_id")
    }
    groups = []
    required_candidate_count = 0
    for group in (item.get("candidate_groups") or [])[:40]:
        if not isinstance(group, dict):
            continue
        if group.get("required") is True:
            required_candidate_count += int(group.get("candidate_count") or 0)
        match_by_id = {}
        for match in group.get("candidate_matches") or []:
            if isinstance(match, dict) and match.get("candidate_id"):
                match_by_id.setdefault(str(match.get("candidate_id")), []).append(match)
        sources = []
        for candidate_id in [str(v) for v in (group.get("candidate_ids") or [])][:20]:
            candidate = evidence_by_id.get(candidate_id) or {}
            source = candidate.get("source_identity") or {}
            quality = candidate.get("quality") or {}
            matches = match_by_id.get(candidate_id) or []
            sources.append({
                "candidate_id": candidate_id,
                "raw_capability_ids": sorted({str(m.get("raw_capability_id")) for m in matches if m.get("raw_capability_id")})[:6],
                "device_registry_id": source.get("device_registry_id"),
                "config_entry_id": source.get("config_entry_id"),
                "entity_registry_id": source.get("entity_registry_id"),
                "current_entity_id": source.get("current_entity_id"),
                "unique_id": source.get("unique_id"),
                "source_kind": source.get("source_kind"),
                "target_scope": source.get("target_scope"),
                "availability": quality.get("availability"),
            })
        groups.append({
            "input_id": group.get("input_id"),
            "required": group.get("required"),
            "cardinality": group.get("cardinality"),
            "candidate_count": int(group.get("candidate_count") or 0),
            "candidate_match_count": len(group.get("candidate_matches") or []),
            "candidate_sources": sources,
        })
    selected_ids = [str(v) for v in (selection.get("selected_device_ids") or []) if str(v)]
    return {
        "builder_id": item.get("builder_id"),
        "contract_version": item.get("contract_version"),
        "configuration_revision": item.get("configuration_revision"),
        "build_input_revision": item.get("build_input_revision"),
        "publication_revision": selection.get("publication_revision"),
        "concept": selection.get("concept"),
        "integration_domain": selection.get("integration_domain"),
        "device_filter_mode": selection.get("device_filter_mode"),
        "selected_device_count": len(selected_ids),
        "selected_device_ids": selected_ids[:20],
        "candidate_group_count": len(item.get("candidate_groups") or []),
        "candidate_evidence_count": len(item.get("candidate_evidence") or []),
        "required_candidate_count": required_candidate_count,
        "candidate_match_count": sum(
            len(group.get("candidate_matches") or [])
            for group in (item.get("candidate_groups") or [])
            if isinstance(group, dict)
        ),
        "assessment": {
            "required_inputs_complete": assessment.get("required_inputs_complete"),
            "topology_state": assessment.get("topology_state"),
            "review_required": assessment.get("review_required"),
            "issues": [str(value) for value in (assessment.get("issues") or [])][:20],
        },
        "inputs": groups,
    }


def _logical_asset_row(asset):
    properties = []
    for prop in (asset.get("properties") or [])[:24]:
        if not isinstance(prop, dict):
            continue
        properties.append({
            "property_key": prop.get("property_key"),
            "display_name": prop.get("display_name"),
            "input_id": prop.get("input_id"),
            "status": prop.get("status"),
            "availability": prop.get("availability"),
            "value": prop.get("value"),
            "unit": prop.get("unit"),
            "required": prop.get("required"),
            "candidate_count": prop.get("candidate_count"),
            "binding_id": prop.get("binding_id"),
            "raw_capability_id": prop.get("raw_capability_id"),
            "integration_domain": prop.get("integration_domain"),
            "device_registry_id": prop.get("device_registry_id"),
            "config_entry_id": prop.get("config_entry_id"),
            "entity_registry_id": prop.get("entity_registry_id"),
            "current_entity_id": prop.get("current_entity_id"),
            "unique_id": prop.get("unique_id"),
            "issues": [str(v) for v in (prop.get("issues") or [])][:8],
        })
    return {
        "asset_id": asset.get("asset_id"),
        "object_class": asset.get("object_class"),
        "display_name": asset.get("display_name"),
        "health": asset.get("health"),
        "normalization_status": asset.get("normalization_status"),
        "runtime_truth": asset.get("runtime_truth"),
        "builder_id": asset.get("builder_id"),
        "integration_domain": asset.get("integration_domain"),
        "selection_mode": asset.get("selection_mode"),
        "selected_device_ids": [str(v) for v in (asset.get("selected_device_ids") or [])][:20],
        "parent_asset_id": asset.get("parent_asset_id"),
        "property_count": len(asset.get("properties") or []),
        "available_property_count": asset.get("available_property_count"),
        "properties": properties,
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    state = (hass.data.get(DOMAIN) or {}).get(entry.entry_id) or {}
    manager = state.get("build_manager")
    runtime = state.get("runtime")
    store = state.get("store")
    provider = state.get("provider")
    model = (getattr(manager, "compiled_model", None) or {}) if manager else {}
    snap = (getattr(runtime, "snapshot", {}) or {}) if runtime else {}
    facts = snap.get("facts") or {}
    store_data = (getattr(store, "data", {}) or {}) if store else {}
    metering = store_data.get("metering", {})
    command_state = store_data.get("command_state", {})
    activity = store_data.get("activity", [])
    evidence = store_data.get("pilot_evidence", {})
    periods = metering.get("periods") or {}
    specifications = tuple(provider.iter_specifications()) if provider else ()

    selected_registry = hass.data.get("rhi_selected_domain_build_input_registry", {}) or {}
    selected_entry = selected_registry.get("energy") if isinstance(selected_registry, dict) else None
    selected_inputs = (selected_entry or {}).get("inputs") or [] if isinstance(selected_entry, dict) else []

    return {
        "identity": {
            "release": RELEASE,
            "release_name": RELEASE_NAME,
            "shared_baseline_version": SHARED_BASELINE_VERSION,
            "shared_baseline_checksum": SHARED_BASELINE_CHECKSUM,
            "foundation_target": "F1.6.0",
            "public_contract": LEGACY_CONTRACT_VERSION,
            "known_accepted_technical_debt": 0,
        },
        "health": {
            "foundation_status": getattr(manager, "foundation_status", None),
            "configuration_status": getattr(manager, "configuration_status", None),
            "build_health": getattr(manager, "build_health", None),
            "runtime_health": snap.get("health"),
            "reason": getattr(manager, "reason", None),
            "last_success": getattr(manager, "last_success", None),
        },
        "configuration": {
            "configuration_status": getattr(manager, "configuration_status", None),
            "handoff_present": getattr(manager, "handoff_present", False),
            "configuration_revision": getattr(manager, "configuration_revision", 0),
            "last_configuration_revision": getattr(manager, "last_configuration_revision", 0),
            "build_input_revision": getattr(manager, "build_input_revision", 0),
            "domain_build_specification_count": len(specifications),
            "domain_build_specification_contract": "1.2.0",
            "selected_input_contracts": [item.get("contract_version") for item in selected_inputs[:40] if isinstance(item, dict)],
            "selected_builder_ids": [item.get("builder_id") for item in selected_inputs[:40] if isinstance(item, dict)],
        },
        "build_handoff": {
            "registry_entry_present": isinstance(selected_entry, dict),
            "selected_input_count": len(selected_inputs),
            "inputs": [_selected_input_row(item) for item in selected_inputs[:40] if isinstance(item, dict)],
            "domain_assessments": deepcopy(getattr(manager, "builder_assessments", {}) or {}),
            "affected_scope": list(getattr(manager, "affected_scope", []) or [])[:20],
            "event_contract": "rhi_selected_domain_build_inputs_changed",
            "event_payload_used_as_runtime_truth": False,
            "domain_rescans_ha_registries": False,
        },
        "binding": {
            "accepted_binding_owner": "rhi_energy",
            "accepted_binding_count": len(model.get("accepted_bindings") or []),
            "bindings": [_binding_row(x) for x in (model.get("accepted_bindings") or [])[:80]],
        },
        "logical_objects": {
            "object_model": "energy_object_centric_v1",
            "logical_object_count": len(snap.get("logical_assets") or model.get("logical_assets") or []),
            "object_classes": sorted({
                str(row.get("object_class"))
                for row in (snap.get("logical_assets") or model.get("logical_assets") or [])
                if isinstance(row, dict) and row.get("object_class")
            }),
            "objects": [_logical_asset_row(row) for row in (snap.get("logical_assets") or model.get("logical_assets") or [])[:120] if isinstance(row, dict)],
        },
        "compile": {
            "compiled_model_revision": model.get("compiled_model_revision"),
            "concepts": sorted((model.get("concepts") or {}).keys()),
            "concept_assessments": deepcopy(model.get("concept_assessments") or {}),
            "technical_observations": deepcopy(model.get("technical_observations") or {}),
            "normalized_concept_count": len(model.get("concepts") or {}),
            "accepted_binding_count": len(model.get("accepted_bindings") or []),
            "issues": deepcopy((model.get("issues") or [])[:40]),
            "atomic_last_good_retention": True,
            "partial_concept_normalization": True,
            "object_centric_logical_assets": True,
            "semantic_registry_authoritative": bool((model.get("normalization") or {}).get("semantic_registry_authoritative")),
            "integration_adapter_boundary": bool((model.get("normalization") or {}).get("integration_adapter_boundary")),
            "producer_adapter_boundary": True,
            "legacy_compatibility_surface_preserved": True,
        },
        "execution": {
            "measurement_fast_path": "accepted_source_listener_to_rhi_energy_runtime",
            "foundation_in_measurement_fast_path": False,
            "fact_health": {
                k: ("AVAILABLE" if v is not None else "UNAVAILABLE")
                for k, v in facts.items()
                if k.endswith(".health") or k in {
                    "solar.power_kw", "grid.net_power_kw", "battery.power_kw",
                    "home_consumption.power_kw", "forecast.solar_today_kwh",
                    "forecast.solar_remaining_today_kwh", "pricing.spot_eur_kwh",
                }
            },
            "flexible_asset_count": len(snap.get("flexible_assets") or []),
            "metering": {
                "last_update": metering.get("last_update"),
                "baseload_last_sample_bucket": metering.get("baseload_last_sample_bucket"),
                "period_quality": {k: (v or {}).get("quality") for k, v in periods.items()},
            },
            "commands": {
                "count": len(command_state),
                "terminal_states": ["CONFIRMED", "REJECTED", "TIMED_OUT"],
                "durable_admission_before_dispatch": True,
                "idempotency_key_persisted": True,
                "recent": deepcopy(list(command_state.values())[-20:]),
            },
            "recent_activity": deepcopy(activity[-20:]),
        },
        "runtime_evidence": {
            "target_ha_lifecycle_complete": evidence.get("target_ha_lifecycle_complete") is True,
            "pilot_evidence": deepcopy(evidence),
            "release_decision": "PILOT_READY" if evidence.get("target_ha_lifecycle_complete") is True else "PILOT_CANDIDATE",
            "reason": "target_home_assistant_lifecycle_evidence_complete" if evidence.get("target_ha_lifecycle_complete") is True else "target_home_assistant_runtime_proof_pending",
        },
    }
