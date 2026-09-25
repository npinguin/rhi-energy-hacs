"""Bounded Home Assistant config-entry diagnostics for RHI Energy V2."""
from __future__ import annotations

from copy import deepcopy
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .canonical_device import canonical_device_identifier, source_device_ids
from .runtime.canonical_structure import canonical_projection_assets

from .const import (
    DOMAIN,
    LEGACY_BACKEND_RELEASE,
    LEGACY_CONTRACT_VERSION,
    LEGACY_DIAGNOSTIC_ENTITIES,
    LEGACY_PUBLIC_ENTITIES,
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
            "resolution": deepcopy(prop.get("resolution") or {}),
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
        "linked_battery_asset_ids": [
            str(value) for value in (asset.get("linked_battery_asset_ids") or []) if value
        ],
        "battery_correction_required": bool(asset.get("battery_correction_required")),
        "battery_linkage_resolution": asset.get("battery_linkage_resolution"),
        "property_count": len(asset.get("properties") or []),
        "available_property_count": asset.get("available_property_count"),
        "properties": properties,
    }



def _canonical_topology_diagnostics(hass: HomeAssistant, logical_assets) -> dict:
    """Bounded proof that canonical and physical source topology stay separated."""
    registry = dr.async_get(hass)
    assets = canonical_projection_assets([
        row for row in (logical_assets or []) if isinstance(row, dict)
    ])
    canonical_by_asset = {}
    for asset in assets:
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id or asset.get("ha_materialization") is not True:
            continue
        canonical_by_asset[asset_id] = registry.async_get_device(
            identifiers={canonical_device_identifier(asset_id)}
        )

    rows = []
    mismatch_count = 0
    roots = [asset for asset in assets if not asset.get("parent_asset_id")]
    orphan_ids = [
        str(asset.get("asset_id"))
        for asset in assets
        if asset.get("parent_asset_id")
        and str(asset.get("parent_asset_id")) not in canonical_by_asset
    ]
    optimizer_rows = [asset for asset in assets if asset.get("object_class") == "solar_optimizer"]
    optimizer_zone_parented = [
        asset for asset in optimizer_rows
        if (canonical_by_asset and next(
            (
                parent
                for parent in assets
                if str(parent.get("asset_id") or "") == str(asset.get("parent_asset_id") or "")
                and parent.get("object_class") == "solar_zone"
            ),
            None,
        ))
    ]
    canonical_device_ids = {
        device.id for device in canonical_by_asset.values() if device is not None
    }
    source_reparented_to_canonical = []
    seen_sources = set()

    for asset in assets:
        asset_id = str(asset.get("asset_id") or "")
        materialized = asset.get("ha_materialization") is True
        device = canonical_by_asset.get(asset_id)
        parent_asset_id = str(asset.get("parent_asset_id") or "")
        parent = canonical_by_asset.get(parent_asset_id) if parent_asset_id else None
        expected_parent_id = parent.id if materialized and parent is not None else None
        actual_parent_id = device.via_device_id if device is not None else None
        matches = (
            device is not None and actual_parent_id == expected_parent_id
            if materialized
            else device is None
        )
        if not matches:
            mismatch_count += 1

        # Keep the downloadable payload bounded, but never bound the proof scan itself.
        # Counters below must cover the complete canonical/source topology.
        if len(rows) < 80:
            rows.append({
                "asset_id": asset_id,
                "object_class": asset.get("object_class"),
                "device_registry_id": device.id if device is not None else None,
                "parent_asset_id": parent_asset_id or None,
                "expected_via_device_id": expected_parent_id,
                "actual_via_device_id": actual_parent_id,
                "topology_matches": matches,
                "children": list(asset.get("children") or [])[:40],
                "canonical_path": list(asset.get("canonical_path") or []),
                "canonical_depth": asset.get("canonical_depth"),
                "canonical_root": asset.get("canonical_root"),
                "topology_evidence": asset.get("topology_evidence"),
                "topology_key": asset.get("topology_key"),
                "ha_materialization": asset.get("ha_materialization"),
                "topology_kind": asset.get("topology_kind"),
                "source_device_ids": source_device_ids(asset)[:20],
            })

        for source_id in source_device_ids(asset):
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            source = registry.async_get(source_id)
            if source is not None and source.via_device_id in canonical_device_ids:
                source_reparented_to_canonical.append(source_id)

    return {
        "canonical_graph_node_count": len(assets),
        "ha_materialized_expected_count": len(canonical_by_asset),
        "ha_materialized_device_count": sum(device is not None for device in canonical_by_asset.values()),
        "canonical_device_count": sum(device is not None for device in canonical_by_asset.values()),
        "expected_canonical_asset_count": len(canonical_by_asset),
        "canonical_parent_mismatch_count": mismatch_count,
        "canonical_root_count": len(roots),
        "canonical_root_ids": [str(asset.get("asset_id")) for asset in roots],
        "canonical_orphan_count": len(orphan_ids),
        "canonical_orphan_ids": orphan_ids[:20],
        "optimizer_count": len(optimizer_rows),
        "optimizer_zone_parented_count": len(optimizer_zone_parented),
        "optimizer_zone_coverage_pct": (
            round(len(optimizer_zone_parented) / len(optimizer_rows) * 100, 1)
            if optimizer_rows else 100.0
        ),
        "source_device_count": len(seen_sources),
        "source_reparented_to_canonical_count": len(source_reparented_to_canonical),
        "source_reparented_to_canonical_ids": source_reparented_to_canonical[:20],
        "canonical_devices": rows,
    }


def _solar_battery_correction_rows(logical_assets):
    """Expose bounded semantic proof for SolarEdge inverter battery correction."""
    rows = []
    for asset in logical_assets or []:
        if not isinstance(asset, dict) or asset.get("object_class") != "solar_inverter":
            continue
        rows.append({
            "inverter_asset_id": asset.get("asset_id"),
            "integration_domain": asset.get("integration_domain"),
            "device_registry_id": asset.get("device_registry_id"),
            "config_entry_id": asset.get("config_entry_id"),
            "linked_battery_asset_ids": [
                str(value)
                for value in (asset.get("linked_battery_asset_ids") or [])
                if value
            ][:8],
            "battery_correction_required": bool(
                asset.get("battery_correction_required")
            ),
            "battery_linkage_resolution": asset.get("battery_linkage_resolution"),
        })
    return rows[:16]


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    state = (hass.data.get(DOMAIN) or {}).get(entry.entry_id) or {}
    manager = state.get("build_manager")
    runtime = state.get("runtime")
    store = state.get("store")
    provider = state.get("provider")
    model = (getattr(manager, "domain_model", None) or {}) if manager else {}
    snap = (getattr(runtime, "snapshot", {}) or {}) if runtime else {}
    facts = snap.get("facts") or {}
    store_data = (getattr(store, "data", {}) or {}) if store else {}
    metering = store_data.get("metering", {})
    command_state = store_data.get("command_state", {})
    property_operation_state = store_data.get("property_operation_state", {})
    activity = store_data.get("activity", [])
    evidence = store_data.get("pilot_evidence", {})
    periods = metering.get("periods") or {}
    specifications = tuple(provider.iter_specifications()) if provider else ()
    registry = er.async_get(hass)
    public_surface = []
    compatibility_entities = (*LEGACY_PUBLIC_ENTITIES, *LEGACY_DIAGNOSTIC_ENTITIES)
    for entity_id in compatibility_entities:
        registry_entry = registry.async_get(entity_id)
        public_surface.append(
            {
                "expected_entity_id": entity_id,
                "registered": registry_entry is not None,
                "platform": getattr(registry_entry, "platform", None),
                "owned_by_energy": (
                    getattr(registry_entry, "platform", None) == DOMAIN
                    if registry_entry is not None
                    else False
                ),
                "live_state_present": hass.states.get(entity_id) is not None,
            }
        )

    selected_registry = hass.data.get("rhi_selected_domain_build_input_registry", {}) or {}
    selected_entry = selected_registry.get("energy") if isinstance(selected_registry, dict) else None
    selected_inputs = (selected_entry or {}).get("inputs") or [] if isinstance(selected_entry, dict) else []

    solaredge_multi_inputs = [
        item
        for item in selected_inputs
        if isinstance(item, dict)
        and str((item.get("selection") or {}).get("integration_domain") or "") == "solaredge_modbus_multi"
    ]
    solaredge_multi_issues = [
        str(issue)
        for item in solaredge_multi_inputs
        for issue in ((item.get("discovery_assessment") or {}).get("issues") or [])
        if issue
    ]
    solaredge_multi_bindings = [
        binding
        for binding in (model.get("accepted_bindings") or [])
        if isinstance(binding, dict)
        and str(
            binding.get("integration_domain")
            or ((binding.get("source_identity") or {}).get("integration_domain") if isinstance(binding.get("source_identity"), dict) else "")
        ) == "solaredge_modbus_multi"
    ]
    solaredge_multi_assets = [
        asset
        for asset in (snap.get("logical_assets") or model.get("logical_assets") or [])
        if isinstance(asset, dict)
        and str(asset.get("integration_domain") or "") == "solaredge_modbus_multi"
    ]

    return {
        "identity": {
            "release": RELEASE,
            "release_name": RELEASE_NAME,
            "shared_baseline_version": SHARED_BASELINE_VERSION,
            "shared_baseline_checksum": SHARED_BASELINE_CHECKSUM,
            "compatibility_backend_release": LEGACY_BACKEND_RELEASE,
            "public_contract": LEGACY_CONTRACT_VERSION,
            "known_accepted_technical_debt": 0,
        },
        "setup_performance": deepcopy(state.get("setup_performance") or {}),
        "logical_projection": deepcopy((state.get("store").data.get("logical_projection") if state.get("store") else {}) or {}),
        "supervision": (state.get("supervision").snapshot() if state.get("supervision") else None),
        "health": {
            "foundation_supervisory_contract": "RHI_DOMAIN_SUPERVISORY_STATUS_V1",
            "foundation_status": getattr(manager, "foundation_status", None),
            "configuration_status": getattr(manager, "configuration_status", None),
            "build_health": getattr(manager, "build_health", None),
            "runtime_health": snap.get("health"),
            "reason": getattr(manager, "reason", None),
            "last_success": getattr(manager, "last_success", None),
            "contract_alignment": {
                "shared_baseline": SHARED_BASELINE_VERSION,
                "selected_input_contracts": sorted({
                    str(item.get("contract_version"))
                    for item in selected_inputs
                    if isinstance(item, dict) and item.get("contract_version")
                }),
            },
        },
        "event_flow": (runtime.event_flow.snapshot() if runtime and hasattr(runtime, "event_flow") else {}),
        "public_projection": (
            state.get("public_projector").projection_diagnostics()
            if state.get("public_projector")
            and hasattr(state.get("public_projector"), "projection_diagnostics")
            else {}
        ),
        "canonical_coverage": deepcopy(
            ((state.get("public_projector").get_v2() if state.get("public_projector") else {}) or {}).get("coverage") or {}
        ),
        "property_operations": {
            "count": len(property_operation_state),
            "pending_count": sum(
                1 for row in property_operation_state.values()
                if isinstance(row, dict) and row.get("status") == "PENDING"
            ),
            "rows": [
                {
                    "property_id": key,
                    "operation_id": row.get("operation_id"),
                    "status": row.get("status"),
                    "reason": row.get("reason"),
                    "requested_at": row.get("requested_at"),
                    "completed_at": row.get("completed_at"),
                }
                for key, row in list(property_operation_state.items())[-40:]
                if isinstance(row, dict)
            ],
        },
        "public_surface": {
            "expected_entity_count": len(compatibility_entities),
            "product_entity_count": len(LEGACY_PUBLIC_ENTITIES),
            "diagnostic_entity_count": len(LEGACY_DIAGNOSTIC_ENTITIES),
            "expected_entity_ids": list(compatibility_entities),
            "registered_entity_count": sum(row["registered"] for row in public_surface),
            "owned_entity_count": sum(row["owned_by_energy"] for row in public_surface),
            "live_state_count": sum(row["live_state_present"] for row in public_surface),
            "takeover": deepcopy(state.get("migration") or {}),
            "entities": public_surface,
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
        "layered_model": {
            "runtime_status_authority": "runtime_evaluated_system_planning_intelligence_assets",
            "materialization_records_scope": "structural_compile_state_not_runtime_readiness",
            "generation": deepcopy(model.get("generation") or snap.get("generation") or {}),
            "layer_contract_version": model.get("layer_contract_version"),
            "model_fingerprint": model.get("model_fingerprint") or snap.get("model_fingerprint"),
            "layer_health": deepcopy(snap.get("layer_health") or model.get("layer_health") or {}),
            "logical_asset_count": len(model.get("logical_layer") or []),
            "system_asset_count": len(model.get("system_assets") or []),
            "planning_asset_count": len(model.get("planning_assets") or []),
            "intelligence_asset_count": len(model.get("intelligence_assets") or []),
            "dependency_edge_count": len(model.get("dependencies") or []),
            "dependency_diagnostics": deepcopy(model.get("dependency_diagnostics") or {}),
            "system_assets": deepcopy(snap.get("system_assets") or model.get("system_assets") or []),
            "planning_assets": deepcopy(snap.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_assets": deepcopy(snap.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "materialization_records": deepcopy(model.get("materialization_records") or []),
            "runtime_rules": deepcopy(model.get("runtime_rules") or {}),
        },
        "semantic_acceptance": {
            "domain_model_revision": model.get("domain_model_revision"),
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
        "canonical_device_topology": _canonical_topology_diagnostics(
            hass,
            snap.get("logical_assets") or model.get("logical_assets") or [],
        ),
        "source_device_topology": {
            "policy": "exact_source_device_provenance_with_entity_registry_diagnostic",
            "semantic_truth_source": False,
            "source_device_count": int(
                (store_data.get("source_device_topology") or {}).get("source_device_count")
                or 0
            ),
            "source_device_ids": list(
                (store_data.get("source_device_topology") or {}).get("source_device_ids")
                or []
            )[:80],
            "bindings_by_source_device_id": deepcopy(
                (store_data.get("source_device_topology") or {}).get(
                    "bindings_by_source_device_id"
                )
                or {}
            ),
            "binding_on_exact_source_device": bool(
                (store_data.get("source_device_topology") or {}).get(
                    "binding_on_exact_source_device"
                )
            ),
            "via_device_links_created": int(
                (store_data.get("source_device_topology") or {}).get(
                    "via_device_links_created"
                )
                or 0
            ),
            "copied_source_identity_devices_created": int(
                (store_data.get("source_device_topology") or {}).get(
                    "copied_source_identity_devices_created"
                )
                or 0
            ),
            "orphan_proxy_device_count": int(
                (store_data.get("source_device_topology") or {}).get(
                    "orphan_proxy_device_count"
                )
                or 0
            ),
            "last_sync_duration_ms": (store_data.get("source_device_topology") or {}).get("last_sync_duration_ms"),
            "sync_count": int((store_data.get("source_device_topology") or {}).get("sync_count") or 0),
            "last_scanned_energy_device_count": int(
                (store_data.get("source_device_topology") or {}).get("last_scanned_energy_device_count") or 0
            ),
            "last_entry_entity_count": int(
                (store_data.get("source_device_topology") or {}).get("last_entry_entity_count") or 0
            ),
            "solar_inverter_battery_corrections": _solar_battery_correction_rows(
                snap.get("logical_assets") or model.get("logical_assets") or []
            ),
            "solar_inverter_battery_correction_count": len(
                _solar_battery_correction_rows(
                    snap.get("logical_assets") or model.get("logical_assets") or []
                )
            ),
        },
        "solaredge_modbus_multi": {
            "selected_builder_count": len(solaredge_multi_inputs),
            "selected_builder_ids": [
                str(item.get("builder_id") or "")
                for item in solaredge_multi_inputs
            ][:20],
            "assessment_issue_count": len(solaredge_multi_issues),
            "assessment_issues": solaredge_multi_issues[:40],
            "accepted_binding_count": len(solaredge_multi_bindings),
            "logical_asset_count": len(solaredge_multi_assets),
            "logical_asset_ids": [
                str(asset.get("asset_id") or "")
                for asset in solaredge_multi_assets
                if asset.get("asset_id")
            ][:40],
            "inverter_battery_corrections": [
                row
                for row in _solar_battery_correction_rows(
                    snap.get("logical_assets") or model.get("logical_assets") or []
                )
                if str(row.get("integration_domain") or "") == "solaredge_modbus_multi"
            ],
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
                    "pricing.import_price_current_eur_kwh",
                    "pricing.export_price_current_eur_kwh",
                }
            },
            "flexible_asset_count": len(snap.get("flexible_assets") or []),
            "connection_asset_count": len(snap.get("connections") or []),
            "producer_publication_availability": deepcopy(snap.get("producer_publication_availability") or {}),
            "producer_publication_metadata": deepcopy(snap.get("producer_publication_metadata") or {}),
            "runtime_issues": deepcopy(snap.get("runtime_issues") or []),
            "public_contract_states": {
                entity_id: (state.get("public_projector").get(entity_id.removeprefix("sensor.")) or {}).get("state")
                for entity_id in LEGACY_PUBLIC_ENTITIES
            } if state.get("public_projector") else {},
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
