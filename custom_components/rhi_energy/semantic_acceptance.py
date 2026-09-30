"""Energy semantic acceptance for Foundation SelectedDomainBuildInput 1.2.0.

This module mirrors the Mobility domain boundary terminology:
SelectedDomainBuildInput -> semantic acceptance / logical identity ->
AcceptedSourceBinding. It is configuration/build-time code; runtime never reopens structural acceptance.

Foundation performs technical discovery/matching only. Energy consumes exact selected
raw matches plus evidence, applies cardinality and target-scope safety independently per
normalized input, and materializes every semantically safe object/property.  One broken
builder/property never suppresses unrelated safe Energy truth.

The normalized-input vocabulary comes from ``semantic.py``.  Integration-specific value
conventions are deliberately absent here and live in ``adapters/``.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

try:
    from .adapters import get_battery_unit_key_resolver, get_candidate_filter, get_market_role_resolver, get_inverter_identity_resolver, get_inverter_serial_resolver
    from .models import AcceptedSourceBinding, EnergyDomainModel
    from .runtime.logical_assets import build_logical_assets
    from .semantic import input_definitions, source_object_key
except ImportError:  # Direct runpy/static unit-test execution without package context.
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parent
    build_logical_assets = _runpy.run_path(str(_root / "runtime" / "logical_assets.py"))["build_logical_assets"]
    _semantic_module = _runpy.run_path(str(_root / "semantic.py"))
    input_definitions = _semantic_module["input_definitions"]
    source_object_key = _semantic_module["source_object_key"]
    def _adapter_function(integration: str, name: str, default):
        path = _root / "adapters" / f"{integration}.py"
        if not path.is_file():
            return default
        return _runpy.run_path(str(path)).get(name, default)
    def get_candidate_filter(integration):
        return _adapter_function(str(integration or ""), "accept_candidate", lambda _input_id, _candidate: True)
    def get_battery_unit_key_resolver(integration):
        return _adapter_function(str(integration or ""), "battery_unit_key", lambda _candidate: None)
    def get_market_role_resolver(integration):
        return _adapter_function(str(integration or ""), "market_role", lambda candidate: (candidate.get("semantic_metadata") or {}).get("market_role"))
    def get_inverter_identity_resolver(integration):
        return _adapter_function(str(integration or ""), "inverter_identity", lambda _row: None)
    def get_inverter_serial_resolver(integration):
        serial = _adapter_function(str(integration or ""), "inverter_serial", None)
        if callable(serial):
            return serial
        identity = get_inverter_identity_resolver(integration)
        return lambda row: (identity(row) or (None, None))[1]
    AcceptedSourceBinding = dict  # type: ignore[assignment,misc]
    EnergyDomainModel = dict  # type: ignore[assignment,misc]


def _hash(value: Any, length: int = 12) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:length]


def _groups(build_input: dict[str, Any], input_id: str) -> list[dict[str, Any]]:
    return [
        group
        for group in (build_input.get("candidate_groups") or [])
        if isinstance(group, dict) and group.get("input_id") == input_id
    ]


def _candidate_group_key(candidate: dict[str, Any]) -> str:
    source = candidate.get("source_identity") or {}
    evidence = candidate.get("evidence") or {}
    return str(
        source.get("device_registry_id")
        or evidence.get("device_registry_id")
        or source.get("config_entry_id")
        or source.get("entity_registry_id")
        or candidate.get("candidate_id")
        or "unknown"
    )


def _safe_candidates(build_input: dict[str, Any], input_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Return independently cardinality-safe candidates for one normalized input."""
    accepted: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    selection = build_input.get("selection") or {}
    selected_device_ids = {
        str(value) for value in selection.get("selected_device_ids") or [] if value
    }
    restrict_devices = (
        selection.get("device_filter_mode") == "specific_devices"
        and bool(selected_device_ids)
    )
    for group in _groups(build_input, input_id):
        raw_candidates = [item for item in (group.get("candidates") or []) if isinstance(item, dict)]
        candidates = []
        for item in raw_candidates:
            source = item.get("source_identity") or {}
            evidence = item.get("evidence") or {}
            device_id = str(source.get("device_registry_id") or evidence.get("device_registry_id") or "")
            if restrict_devices and device_id and device_id not in selected_device_ids:
                continue
            if not get_candidate_filter(source.get("integration_domain"))(input_id, item):
                continue
            candidates.append(item)
        cardinality = str(group.get("cardinality") or "zero_or_one")
        required = group.get("required") is True
        if cardinality in {"exactly_one", "zero_or_one"}:
            if len(candidates) == 1:
                accepted[str(candidates[0].get("candidate_id"))] = candidates[0]
            elif len(candidates) > 1:
                issues.append(f"{input_id}:ambiguous:count_{len(candidates)}")
            elif required:
                issues.append(f"{input_id}:missing")
            continue
        if cardinality in {"one_or_more", "zero_or_more"}:
            if candidates:
                for candidate in candidates:
                    accepted[str(candidate.get("candidate_id"))] = candidate
            elif required:
                issues.append(f"{input_id}:missing")
            continue
        if cardinality in {"exactly_one_per_group", "zero_or_one_per_group", "one_or_more_per_group", "zero_or_more_per_group"}:
            buckets: dict[str, list[dict[str, Any]]] = {}
            for candidate in candidates:
                buckets.setdefault(_candidate_group_key(candidate), []).append(candidate)
            if cardinality in {"exactly_one_per_group", "zero_or_one_per_group"}:
                for key, rows in buckets.items():
                    if len(rows) == 1:
                        accepted[str(rows[0].get("candidate_id"))] = rows[0]
                    else:
                        issues.append(f"{input_id}:ambiguous:{key}:count_{len(rows)}")
                if required and not accepted:
                    issues.append(f"{input_id}:missing")
            else:
                for rows in buckets.values():
                    for candidate in rows:
                        accepted[str(candidate.get("candidate_id"))] = candidate
                if required and not accepted:
                    issues.append(f"{input_id}:missing")
            continue
        issues.append(f"{input_id}:unsupported_cardinality:{cardinality or 'missing'}")
    return list(accepted.values()), issues


def _raw_capability(candidate: dict[str, Any]) -> str:
    return str((candidate.get("selected_match") or {}).get("raw_capability_id") or "")


def _validate_candidate(candidate: dict[str, Any], expected_input: str) -> None:
    source = candidate.get("source_identity") or {}
    configured_field = str(candidate.get("configured_surface_field_id") or "")
    if configured_field:
        if configured_field != expected_input:
            raise ValueError(f"semantic_validation_failed:{expected_input}_configured_field_mismatch")
        if source.get("source_kind") != "entity" or not source.get("target_scope"):
            raise ValueError(f"semantic_validation_failed:{expected_input}_configured_source_invalid")
        if not isinstance(candidate.get("technical_capability"), dict):
            raise ValueError(f"semantic_validation_failed:{expected_input}_technical_capability_missing")
        return
    match = candidate.get("selected_match") or {}
    if not _raw_capability(candidate):
        raise ValueError(f"semantic_validation_failed:{expected_input}_raw_capability_missing")
    if match.get("integration_domain") != source.get("integration_domain"):
        raise ValueError(f"semantic_validation_failed:{expected_input}_integration_mismatch")
    if match.get("source_kind") != source.get("source_kind"):
        raise ValueError(f"semantic_validation_failed:{expected_input}_source_kind_mismatch")
    if not source.get("target_scope"):
        raise ValueError(f"semantic_validation_failed:{expected_input}_target_scope_missing")


def _binding(
    asset_id: str,
    role: str,
    candidate: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> AcceptedSourceBinding:
    source = deepcopy(candidate.get("source_identity") or {})
    selected_match = deepcopy(candidate.get("selected_match") or {})
    candidate_id = str(candidate.get("candidate_id") or "")
    binding_id = f"energy:{asset_id}:{role}"
    same = (
        previous
        if previous
        and previous.get("candidate_id") == candidate_id
        and previous.get("raw_capability_id") == selected_match.get("raw_capability_id")
        else None
    )
    binding_revision = int(same.get("binding_revision", 1)) if same else int((previous or {}).get("binding_revision", 0)) + 1
    resolution_revision = int(same.get("resolution_revision", 1)) if same else 1
    if same and (same.get("source_identity") or {}).get("current_entity_id") != source.get("current_entity_id"):
        resolution_revision += 1
    return {
        "kind": "accepted_domain_binding",
        "contract_version": "1.1.0",
        "binding_id": binding_id,
        "binding_owner": "rhi_energy",
        "asset_id": asset_id,
        "semantic_role": role,
        "candidate_id": candidate_id,
        "candidate_revision": candidate.get("candidate_revision"),
        "raw_capability_id": (
            selected_match.get("raw_capability_id")
            or candidate.get("configured_surface_field_id")
        ),
        "published_match": deepcopy(selected_match.get("published_match") or {}),
        "source_identity": source,
        "target_scope": source.get("target_scope"),
        "technical_capability": deepcopy(candidate.get("technical_capability") or {}),
        "evidence": deepcopy(candidate.get("evidence") or {}),
        "quality": deepcopy(candidate.get("quality") or {}),
        "semantic_binding_confidence": "high",
        "binding_revision": binding_revision,
        "resolution_revision": resolution_revision,
    }


def _candidate_count(build_input: dict[str, Any]) -> int:
    return sum(
        len(group.get("candidate_ids") or group.get("candidates") or [])
        for group in (build_input.get("candidate_groups") or [])
        if isinstance(group, dict)
    )


def _required_candidate_count(build_input: dict[str, Any]) -> int:
    return sum(
        len(group.get("candidate_ids") or group.get("candidates") or [])
        for group in (build_input.get("candidate_groups") or [])
        if isinstance(group, dict) and group.get("required") is True
    )


def _selection_explicitly_empty(build_input: dict[str, Any]) -> bool:
    selection = build_input.get("selection") or {}
    mode = selection.get("device_filter_mode")
    selected = [str(value) for value in selection.get("selected_device_ids") or [] if str(value)]
    if mode == "specific_devices":
        return not selected
    if mode == "all_matching":
        return _candidate_count(build_input) == 0
    return False


def _concept_id_for_builder(builder_id: str) -> str | None:
    for concept_id in ("battery_system", "grid_connection", "solar_production", "solar_forecast", "price_source", "gas_meter", "solar_optimizer"):
        if f".{concept_id}." in builder_id:
            return concept_id
    return None


def _candidate_device_id(candidate: dict[str, Any]) -> str:
    """Compatibility wrapper for the pure domain-owned source object key."""
    return source_object_key(candidate)


def _candidate_config_id(candidate: dict[str, Any]) -> str:
    source = candidate.get("source_identity") or {}
    return str(source.get("config_entry_id") or _candidate_device_id(candidate) or candidate.get("candidate_id") or "")


def _candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence") or {}
    source = candidate.get("source_identity") or {}
    return {
        "display_name": evidence.get("device_name") or evidence.get("entity_name") or evidence.get("original_name"),
        "manufacturer": evidence.get("device_manufacturer"),
        "brand": evidence.get("device_manufacturer"),
        "model": evidence.get("device_model"),
        "variant": evidence.get("device_variant"),
        "model_year": evidence.get("device_model_year"),
        "via_device_registry_id": evidence.get("via_device_registry_id"),
        "device_registry_id": source.get("device_registry_id") or evidence.get("device_registry_id"),
        "config_entry_id": source.get("config_entry_id"),
        "source_entity_id": source.get("current_entity_id"),
        "source_unique_id": source.get("unique_id"),
        "device_identifiers": deepcopy(evidence.get("device_identifiers") or []),
        "device_connections": deepcopy(evidence.get("device_connections") or []),
    }


def _safe_for(build_input: dict[str, Any], input_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    candidates, issues = _safe_candidates(build_input, input_id)
    safe: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            _validate_candidate(candidate, input_id)
        except Exception as exc:
            issues.append(f"{input_id}:{exc}")
            continue
        safe.append(candidate)
    return safe, issues


def _safe_inputs(build_input: dict[str, Any], concept: str) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    issues: list[str] = []
    for spec in input_definitions(concept):
        input_id = str(spec.get("input_id") or "")
        if not input_id:
            continue
        candidates, local = _safe_for(build_input, input_id)
        rows[input_id] = candidates
        issues.extend(local)
    return rows, issues


def _single_role(
    bindings: list[AcceptedSourceBinding],
    previous: dict[str, dict[str, Any]],
    asset_id: str,
    role: str,
    rows: list[dict[str, Any]],
    issues: list[str],
) -> str | None:
    if len(rows) == 1:
        binding_id = f"energy:{asset_id}:{role}"
        bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
        return binding_id
    if len(rows) > 1:
        issues.append(f"{role}:ambiguous:count_{len(rows)}")
    return None


def _bind_many(
    bindings: list[AcceptedSourceBinding],
    previous: dict[str, dict[str, Any]],
    asset_id: str,
    role: str,
    rows: list[dict[str, Any]],
) -> list[str]:
    ids: list[str] = []
    for index, candidate in enumerate(rows):
        semantic_role = f"{role}_{index}"
        binding_id = f"energy:{asset_id}:{semantic_role}"
        bindings.append(_binding(asset_id, semantic_role, candidate, previous.get(binding_id)))
        ids.append(binding_id)
    return ids


def _editable_candidate_matches_platform(candidate: dict[str, Any], platform: str | None) -> bool:
    """Require the expected technical write surface without using HA entity-id shape."""
    capability = str((candidate.get("technical_capability") or {}).get("capability_class") or "")
    expected = {
        "number": "number_write_surface",
        "select": "select_write_surface",
        "switch": "binary_write_surface",
    }.get(str(platform or ""))
    return expected is not None and capability == expected


def _accept_battery(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "battery")
    measurement_ids = ["battery_unit_power", "battery_unit_soc", "battery_capacity"]
    builder_id = str(build_input.get("builder_id") or "battery")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    unit_key_resolver = get_battery_unit_key_resolver(integration)

    power_candidates = list(inputs.get("battery_unit_power", []))
    adapter_keys = {
        str(key)
        for candidate in power_candidates
        if (key := unit_key_resolver(candidate))
    }
    use_adapter_units = bool(adapter_keys)

    def unit_key(candidate: dict[str, Any]) -> str:
        adapter_key = unit_key_resolver(candidate)
        if adapter_key:
            return str(adapter_key)
        return "" if use_adapter_units else _candidate_device_id(candidate)

    anchor_keys = sorted({
        unit_key(candidate)
        for candidate in power_candidates
        if unit_key(candidate)
    })
    if not anchor_keys:
        raise ValueError("no_measurement_anchor")

    system_id = f"battery_system_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedSourceBinding] = []
    units: list[dict[str, Any]] = []
    system_roles: dict[str, str] = {}
    device_specs = [spec for spec in input_definitions("battery") if spec.get("object_scope") == "device"]

    # When an integration exposes physical sub-units inside one HA DeviceEntry,
    # non-unit aggregate power/SoC remain authoritative system evidence rather than
    # being duplicated onto every child battery.
    if use_adapter_units:
        for input_id, role in (("battery_unit_power", "power"), ("battery_unit_soc", "soc")):
            rows = [candidate for candidate in inputs.get(input_id, []) if not unit_key_resolver(candidate)]
            if len(rows) == 1:
                binding_id = f"energy:{system_id}:{role}"
                bindings.append(_binding(system_id, role, rows[0], previous.get(binding_id)))
                system_roles[role] = binding_id
            elif len(rows) > 1:
                issues.append(f"battery_system_{role}:ambiguous:count_{len(rows)}")

        capacity_rows = list(inputs.get("battery_capacity", []))
        if len(anchor_keys) > 1:
            if len(capacity_rows) == 1:
                binding_id = f"energy:{system_id}:capacity"
                bindings.append(_binding(system_id, "capacity", capacity_rows[0], previous.get(binding_id)))
                system_roles["capacity"] = binding_id
            elif len(capacity_rows) > 1:
                issues.append(f"battery_system_capacity:ambiguous:count_{len(capacity_rows)}")

    for index, anchor_key in enumerate(anchor_keys, start=1):
        anchor_rows = [candidate for candidate in power_candidates if unit_key(candidate) == anchor_key]
        if not anchor_rows:
            continue
        anchor_device_id = _candidate_device_id(anchor_rows[0])
        asset_id = f"battery_unit_{_hash([builder_id, anchor_key], 10)}"
        role_map: dict[str, str] = {}
        local_candidates: list[dict[str, Any]] = []

        for spec in device_specs:
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if unit_key(candidate) == anchor_key]
            if not rows:
                anchor_config_entries = {
                    str((candidate.get("source_identity") or {}).get("config_entry_id") or "")
                    for candidate in power_candidates
                    if unit_key(candidate) == anchor_key
                    and (candidate.get("source_identity") or {}).get("config_entry_id")
                }
                sibling_rows = [
                    candidate
                    for candidate in inputs.get(input_id, [])
                    if not unit_key_resolver(candidate)
                    and (
                        not (candidate.get("source_identity") or {}).get("config_entry_id")
                        or str((candidate.get("source_identity") or {}).get("config_entry_id") or "")
                        in anchor_config_entries
                    )
                ]
                # Generic single-storage-unit enrichment: controller/system capabilities
                # that cannot identify a specific unit may enrich exactly one unit, never
                # be duplicated across several units.
                if len(anchor_keys) == 1 and len(sibling_rows) == 1:
                    rows = sibling_rows
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"battery_{role}:{anchor_key}:ambiguous")

        if role_map:
            metadata = _candidate_metadata(local_candidates[0] if local_candidates else anchor_rows[0])
            if use_adapter_units:
                metadata["display_name"] = f"Battery {index}"
            units.append({
                "asset_id": asset_id,
                "unit_key": anchor_key,
                "bindings": role_map,
                **metadata,
                "device_registry_id": anchor_device_id,
            })

    if not units:
        raise ValueError("no_semantically_safe_measurement")

    # Physical controls belong to the physical Battery whose accepted measurement
    # evidence proves the same exact source/config-entry identity. Never fan one
    # controller surface out across multiple batteries and never promote a per-device
    # control to the aggregate merely because several candidates exist.
    reserve_binding = None
    reserve_bindings: list[str] = []
    unit_config_entries_by_asset: dict[str, set[str]] = {}
    config_entry_unit_owners: dict[str, set[str]] = {}
    for unit in units:
        owner_id = str(unit.get("asset_id") or "")
        entries = {
            str((binding.get("source_identity") or {}).get("config_entry_id") or "")
            for binding_id in (unit.get("bindings") or {}).values()
            if (binding := next((row for row in bindings if row.get("binding_id") == binding_id), None))
            and (binding.get("source_identity") or {}).get("config_entry_id")
        }
        unit_config_entries_by_asset[owner_id] = entries
        for entry_id in entries:
            config_entry_unit_owners.setdefault(entry_id, set()).add(owner_id)

    for unit in units:
        owner_id = str(unit.get("asset_id") or "")
        unit_config_entries = unit_config_entries_by_asset.get(owner_id, set())
        for spec in (row for row in device_specs if row.get("editable") is True):
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = []
            for candidate in inputs.get(input_id, []):
                if not _editable_candidate_matches_platform(candidate, spec.get("platform")):
                    continue
                source = candidate.get("source_identity") or {}
                config_entry_id = str(source.get("config_entry_id") or "")
                if not config_entry_id or config_entry_id not in unit_config_entries:
                    continue
                # Exact config-entry identity is sufficient only when it identifies
                # one canonical physical Battery. Shared controllers remain fail-closed
                # until the model declares an explicit system-controller policy.
                if len(units) > 1 and config_entry_unit_owners.get(config_entry_id, set()) != {owner_id}:
                    continue
                rows.append(candidate)
            if len(rows) == 1 and role not in (unit.get("bindings") or {}):
                binding_id = f"energy:{owner_id}:{role}"
                bindings.append(_binding(owner_id, role, rows[0], previous.get(binding_id)))
                unit["bindings"][role] = binding_id
                if role == "reserve":
                    reserve_bindings.append(binding_id)
            elif len(rows) > 1:
                issues.append(f"battery_{role}:{owner_id}:ambiguous")

    # Report selected control surfaces that could not be attributed to exactly one
    # physical Battery. This is a real semantic limitation, not permission to guess.
    for spec in (row for row in device_specs if row.get("editable") is True):
        input_id = str(spec.get("input_id") or "")
        role = str(spec.get("role") or "")
        accepted_candidate_ids = {
            str(binding.get("candidate_id") or "")
            for unit in units
            for binding_id in (unit.get("bindings") or {}).values()
            if (binding := next((row for row in bindings if row.get("binding_id") == binding_id), None))
            and str(binding.get("semantic_role") or "") == role
        }
        offered = inputs.get(input_id, [])
        unattributed = [
            candidate for candidate in offered
            if str(candidate.get("candidate_id") or "") not in accepted_candidate_ids
        ]
        if unattributed:
            issues.append(f"battery_{role}:unattributed_control:count_{len(unattributed)}")

    complete = sum(1 for unit in units if {"power", "soc"}.issubset((unit.get("bindings") or {}).keys()))
    return (
        bindings,
        {
            "asset_id": system_id,
            "asset_type": "battery_system",
            "units": units,
            "bindings": system_roles,
            "reserve_binding": reserve_binding,
            "reserve_bindings": sorted(reserve_bindings),
            "builder_id": builder_id,
            "integration_domain": integration,
            "normalization_status": "READY" if complete == len(units) and not issues else "DEGRADED",
        },
        issues,
    )


def _accept_grid(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "grid_connection")
    builder_id = str(build_input.get("builder_id") or "grid")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    asset_id = f"grid_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedSourceBinding] = []
    roles: dict[str, Any] = {}
    for spec in input_definitions("grid_connection"):
        role = str(spec.get("role") or "")
        input_id = str(spec.get("input_id") or "")
        rows = inputs.get(input_id, [])
        if spec.get("many"):
            binding_ids = _bind_many(bindings, previous, asset_id, role, rows)
            if binding_ids:
                roles[role] = binding_ids
        else:
            binding_id = _single_role(bindings, previous, asset_id, role, rows, issues)
            if binding_id:
                roles[role] = binding_id

    # Phase structure is determined from the domain-owned raw capability id emitted
    # by the build specification (e.g. grid_phase_current_l1), never from mutable
    # HA entity ids, friendly names or device display names.
    def _phase_rows(prefix: str, definitions: dict[str, str]) -> list[dict[str, Any]]:
        phase_candidates: dict[str, dict[str, dict[str, Any]]] = {}
        for input_id, role in definitions.items():
            rows, local = _safe_for(build_input, input_id)
            issues.extend(local)
            for candidate in rows:
                raw_id = _raw_capability(candidate).lower()
                match = re.search(r"_(l[123])$", raw_id)
                if not match:
                    continue
                phase_candidates.setdefault(match.group(1).upper(), {})[role] = candidate
        result: list[dict[str, Any]] = []
        for phase in ("L1", "L2", "L3"):
            candidates = phase_candidates.get(phase) or {}
            if not candidates:
                continue
            phase_id = f"{prefix}_{_hash([asset_id, phase], 10)}"
            phase_bindings: dict[str, str] = {}
            for role, candidate in candidates.items():
                binding_id = f"energy:{phase_id}:{role}"
                bindings.append(_binding(phase_id, role, candidate, previous.get(binding_id)))
                phase_bindings[role] = binding_id
            result.append({
                "asset_id": phase_id,
                "phase": phase,
                "bindings": phase_bindings,
                **_candidate_metadata(next(iter(candidates.values()))),
            })
        return result

    phases = _phase_rows("grid_phase", {
        "grid_phase_power": "power",
        "grid_phase_current": "current",
        "grid_phase_voltage_ln": "voltage_ln",
        "grid_phase_voltage_ll": "voltage_ll",
    })
    generation_meter_phases = _phase_rows("generation_meter_phase", {
        "generation_phase_power": "power",
        "generation_phase_current": "current",
        "generation_phase_voltage_ln": "voltage_ln",
        "generation_phase_voltage_ll": "voltage_ll",
    })
    if phases:
        roles["phases"] = [
            binding_id for phase in phases for binding_id in (phase.get("bindings") or {}).values()
        ]
    if generation_meter_phases:
        roles["generation_meter_phases"] = [
            binding_id for phase in generation_meter_phases for binding_id in (phase.get("bindings") or {}).values()
        ]

    if not roles:
        raise ValueError("no_semantically_safe_input")
    return bindings, {
        "asset_id": asset_id,
        "asset_type": "grid_connection",
        "bindings": roles,
        "phases": phases,
        "generation_meter_phases": generation_meter_phases,
        "builder_id": builder_id,
        "integration_domain": integration,
        "normalization_status": "READY" if (
            (
                "net_power" in roles
                or (
                    "measured_import_power" in roles
                    and "measured_export_power" in roles
                )
                or (integration == "home_assistant_energy" and roles)
            )
            and not issues
        ) else "DEGRADED",
    }, issues

def _accept_solar(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "solar_production")
    for phase_input in ("phase_power", "phase_current", "phase_voltage_ln", "phase_voltage_ll"):
        phase_rows, local = _safe_for(build_input, phase_input)
        issues.extend(local)
        inputs[phase_input] = phase_rows
    builder_id = str(build_input.get("builder_id") or "solar")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    system_id = f"solar_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedSourceBinding] = []

    # Home Assistant Energy represents production sources, not physical inverter
    # hardware. Accept any selected resource that provides power and/or cumulative
    # production energy and preserve it as a generic source object.
    if integration == "home_assistant_energy" or build_input.get("configured_object_type") == "solar_source":
        anchors = sorted({
            _candidate_device_id(candidate)
            for input_id in ("solar_power", "solar_ac_energy")
            for candidate in inputs.get(input_id, [])
            if _candidate_device_id(candidate)
        })
        sources: list[dict[str, Any]] = []
        for anchor in anchors:
            asset_id = f"solar_source_{_hash([builder_id, anchor], 10)}"
            role_map: dict[str, str] = {}
            local_candidates: list[dict[str, Any]] = []
            for input_id, role in (("solar_power", "power"), ("solar_ac_energy", "ac_energy")):
                rows = [
                    candidate
                    for candidate in inputs.get(input_id, [])
                    if _candidate_device_id(candidate) == anchor
                ]
                if len(rows) == 1:
                    binding_id = f"energy:{asset_id}:{role}"
                    bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                    role_map[role] = binding_id
                    local_candidates.extend(rows)
                elif len(rows) > 1:
                    issues.append(f"solar_source_{role}:{anchor}:ambiguous")
            if role_map:
                metadata = _candidate_metadata(local_candidates[0])
                sources.append({
                    "asset_id": asset_id,
                    "bindings": role_map,
                    "source_key": anchor,
                    **metadata,
                })
        if not sources:
            raise ValueError("no_semantically_safe_input")
        return bindings, {
            "asset_id": system_id,
            "asset_type": "solar_source_collection",
            "sources": sources,
            "inverters": [],
            "builder_id": builder_id,
            "integration_domain": integration,
            "normalization_status": "READY" if not issues else "DEGRADED",
        }, issues

    # Physical Solar integrations materialize Solar Inverter objects and therefore
    # require authoritative realtime solar-power evidence as their anchor.
    anchors = sorted({
        _candidate_device_id(candidate)
        for candidate in inputs.get("solar_power", [])
        if _candidate_device_id(candidate)
    })
    if not anchors:
        raise ValueError("no_semantically_safe_input")
    inverters: list[dict[str, Any]] = []
    device_specs = [spec for spec in input_definitions("solar_production") if spec.get("object_scope") == "device"]
    for device_id in anchors:
        asset_id = f"solar_inverter_{_hash([builder_id, device_id], 10)}"
        role_map: dict[str, Any] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in device_specs:
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if _candidate_device_id(candidate) == device_id]
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"solar_{role}:{device_id}:ambiguous")
        phase_candidates: dict[str, dict[str, dict[str, Any]]] = {"a": {}, "b": {}, "c": {}}
        phase_patterns = {
            "phase_current": (r"_ac_current_([abc])$", "current"),
            "phase_voltage_ln": (r"_ac_voltage_([abc])n$", "voltage_ln"),
            "phase_voltage_ll": (r"_ac_voltage_(ab|bc|ca)$", "voltage_ll"),
            "phase_power": (r"_ac_power_([abc])$", "power"),
        }
        for input_id, (pattern, role) in phase_patterns.items():
            for candidate in inputs.get(input_id, []):
                if _candidate_device_id(candidate) != device_id:
                    continue
                unique_id = str((candidate.get("source_identity") or {}).get("unique_id") or "")
                match = re.search(pattern, unique_id)
                if not match:
                    continue
                token = match.group(1)
                phase = token[0]
                phase_candidates[phase][role] = candidate
        phases = []
        for phase in ("a", "b", "c"):
            candidates = phase_candidates[phase]
            if not candidates:
                continue
            phase_id = f"solar_inverter_phase_{_hash([asset_id, phase], 10)}"
            phase_bindings: dict[str, str] = {}
            for role, candidate in candidates.items():
                binding_id = f"energy:{phase_id}:{role}"
                bindings.append(_binding(phase_id, role, candidate, previous.get(binding_id)))
                phase_bindings[role] = binding_id
            metadata = _candidate_metadata(next(iter(candidates.values())))
            phases.append({
                "asset_id": phase_id,
                "phase": phase.upper(),
                "bindings": phase_bindings,
                **metadata,
            })
        if phases:
            role_map["phases"] = [
                binding_id
                for phase in phases
                for binding_id in (phase.get("bindings") or {}).values()
            ]
        if role_map:
            metadata = _candidate_metadata(local_candidates[0] if local_candidates else phases[0] if phases else {})
            inverters.append({"asset_id": asset_id, "device_registry_id": device_id, "bindings": role_map, "phases": phases, **metadata})
    if not inverters:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": system_id, "asset_type": "solar_system", "inverters": inverters, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if all("power" in (item.get("bindings") or {}) for item in inverters) and not issues else "DEGRADED"}, issues


def _accept_provider_semantics(
    build_input: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    concept: str,
    asset_id: str,
) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, concept)
    bindings: list[AcceptedSourceBinding] = []
    roles: dict[str, Any] = {}
    for spec in input_definitions(concept):
        role = str(spec.get("role") or "")
        input_id = str(spec.get("input_id") or "")
        rows = inputs.get(input_id, [])
        if spec.get("many"):
            ids = _bind_many(bindings, previous, asset_id, role, rows)
            if ids:
                roles[role] = ids
        else:
            binding_id = _single_role(bindings, previous, asset_id, role, rows, issues)
            if binding_id:
                roles[role] = binding_id
    return bindings, roles, issues


def _accept_forecast(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    builder_id = str(build_input.get("builder_id") or "forecast")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    asset_id = f"forecast_{_hash([integration, builder_id], 8)}"
    bindings, roles, issues = _accept_provider_semantics(build_input, previous, "solar_forecast", asset_id)
    if not roles:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": asset_id, "asset_type": "solar_forecast", "bindings": roles, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if roles.get("today_energy") and not issues else "DEGRADED"}, issues


def _accept_price(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    builder_id = str(build_input.get("builder_id") or "price")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "price")
    inputs, issues = _safe_inputs(build_input, "price_source")
    current_rows = inputs.get("current_price", [])
    if not current_rows:
        raise ValueError("no_semantically_safe_input")
    bindings: list[AcceptedSourceBinding] = []
    sources: list[dict[str, Any]] = []
    for current in current_rows:
        anchor = _candidate_config_id(current)
        asset_id = f"price_source_{_hash([builder_id, anchor], 10)}"
        role_map: dict[str, Any] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in input_definitions("price_source"):
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if _candidate_config_id(candidate) == anchor]
            if spec.get("many"):
                ids = _bind_many(bindings, previous, asset_id, role, rows)
                if ids:
                    role_map[role] = ids
                    local_candidates.extend(rows)
            elif len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"price_{role}:{anchor}:ambiguous")
        if "current" not in role_map:
            continue
        metadata = _candidate_metadata(local_candidates[0] if local_candidates else current)
        market_role = get_market_role_resolver(integration)(current)
        if market_role not in {"import", "export"}:
            if len(current_rows) == 1:
                market_role = "import"
            else:
                issues.append(f"price_market_role:{anchor}:unresolved")
                continue
        sources.append({
            "asset_id": asset_id,
            "asset_type": "price_source",
            "bindings": role_map,
            "builder_id": builder_id,
            "integration_domain": integration,
            "market_role": market_role,
            "semantic_completeness": sum(1 for key in ("current", "future", "currency", "tariff") if key in role_map),
            "normalization_status": "READY",
            **metadata,
        })
    if not sources:
        raise ValueError("no_semantically_safe_input")
    collection_id = f"price_provider_{_hash([integration, builder_id], 8)}"
    return bindings, {
        "asset_id": collection_id,
        "asset_type": "price_source_collection",
        "sources": sources,
        "builder_id": builder_id,
        "integration_domain": integration,
        "normalization_status": "READY" if not issues else "DEGRADED",
    }, issues


def _accept_gas(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "gas_meter")
    anchors = sorted({
        _candidate_device_id(candidate) or _candidate_config_id(candidate)
        for rows in inputs.values() for candidate in rows
        if _candidate_device_id(candidate) or _candidate_config_id(candidate)
    })
    if not anchors:
        raise ValueError("gas_total_unavailable")
    builder_id = str(build_input.get("builder_id") or "gas")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "gas")
    provider_id = f"gas_provider_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedSourceBinding] = []
    meters: list[dict[str, Any]] = []
    required_roles = {str(spec.get("role") or "") for spec in input_definitions("gas_meter") if spec.get("required")}
    for anchor in anchors:
        asset_id = f"gas_meter_{_hash([builder_id, anchor], 10)}"
        role_map: dict[str, str] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in input_definitions("gas_meter"):
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if (_candidate_device_id(candidate) or _candidate_config_id(candidate)) == anchor]
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"gas_{role}:{anchor}:ambiguous")
        if role_map:
            metadata = _candidate_metadata(local_candidates[0]) if local_candidates else {}
            meters.append({"asset_id": asset_id, "bindings": role_map, "binding": role_map.get("total"), "integration_domain": integration, **metadata})
    if not meters:
        raise ValueError("gas_total_unavailable")
    complete = all(required_roles.issubset(set(meter.get("bindings") or {})) for meter in meters)
    return bindings, {"asset_id": provider_id, "asset_type": "gas_meter_collection", "meters": meters, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if complete and not issues else "DEGRADED"}, issues


def _accept_optimizer(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedSourceBinding], dict[str, Any], list[str]]:
    # The integration exposes three technical layers in the same config entry:
    # site summary, zone/string summaries and leaf optimizers. Foundation discovers
    # candidates; Energy classifies them from exact capability evidence.
    inputs: dict[str, list[dict[str, Any]]] = {}
    issues: list[str] = []
    seen_inputs: set[str] = set()
    for object_class in ("solar_optimizer_site", "solar_zone", "solar_optimizer"):
        for spec in input_definitions(object_class):
            input_id = str(spec.get("input_id") or "")
            if not input_id or input_id in seen_inputs:
                continue
            seen_inputs.add(input_id)
            rows, local = _safe_for(build_input, input_id)
            inputs[input_id] = rows
            issues.extend(local)

    def anchor_for(candidate):
        return _candidate_device_id(candidate) or str(
            (candidate.get("source_identity") or {}).get("entity_registry_id")
            or candidate.get("candidate_id")
            or ""
        )

    anchors = sorted({
        anchor_for(candidate)
        for rows in inputs.values()
        for candidate in rows
        if anchor_for(candidate)
    })
    if not anchors:
        raise ValueError("no_semantically_safe_input")

    builder_id = str(build_input.get("builder_id") or "optimizer")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    provider_id = f"optimizer_provider_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedSourceBinding] = []
    sites: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    optimizers: list[dict[str, Any]] = []

    site_markers = {
        "site_peak_power", "site_installation_date", "site_last_polled",
        "site_inverter_count", "site_obtained_from",
    }
    zone_markers = {
        "zone_voltage_average", "zone_current_average", "zone_child_count",
        "zone_max_active_power",
    }

    for anchor in anchors:
        present_inputs = {
            input_id
            for input_id, rows in inputs.items()
            if any(anchor_for(candidate) == anchor for candidate in rows)
        }
        if present_inputs & site_markers:
            object_class, prefix, target = "solar_optimizer_site", "solar_optimizer_site", sites
        elif present_inputs & zone_markers:
            object_class, prefix, target = "solar_zone", "solar_zone", zones
        else:
            object_class, prefix, target = "solar_optimizer", "solar_optimizer", optimizers

        asset_id = f"{prefix}_{_hash([builder_id, anchor], 10)}"
        role_map: dict[str, str] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in input_definitions(object_class):
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [
                candidate for candidate in inputs.get(input_id, [])
                if anchor_for(candidate) == anchor
            ]
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"{object_class}_{role}:{anchor}:ambiguous")

        if role_map:
            metadata = _candidate_metadata(local_candidates[0]) if local_candidates else {}
            target.append({
                "asset_id": asset_id,
                "asset_type": object_class,
                "bindings": role_map,
                **metadata,
                "device_registry_id": metadata.get("device_registry_id") or anchor,
            })

    if not sites and not zones and not optimizers:
        raise ValueError("no_semantically_safe_input")
    leaf_ready = all("power" in (item.get("bindings") or {}) for item in optimizers)
    return bindings, {
        "asset_id": provider_id,
        "asset_type": "solar_optimizer_collection",
        "sites": sites,
        "zones": zones,
        "optimizers": optimizers,
        "builder_id": builder_id,
        "integration_domain": integration,
        "normalization_status": "READY" if leaf_ready and not issues else "DEGRADED",
    }, issues


_SEMANTIC_ACCEPTORS = {
    "battery_system": _accept_battery,
    "grid_connection": _accept_grid,
    "solar_production": _accept_solar,
    "solar_forecast": _accept_forecast,
    "price_source": _accept_price,
    "gas_meter": _accept_gas,
    "solar_optimizer": _accept_optimizer,
}
_COLLECTION_CONCEPTS = set(_SEMANTIC_ACCEPTORS)


def _materialize_structural_relations(concepts: dict[str, Any]) -> None:
    """Resolve Energy source relations once from Foundation-selected evidence.

    Explicit HA device topology is authoritative when Foundation publishes it.
    SolarEdge Modbus Multi currently exposes battery and inverter entities under
    the same config entry without exporting their HA via-device relation through
    SelectedDomainBuildInput.  For that integration only, a unique accepted
    inverter within the exact same config entry is sufficient semantic evidence
    to associate its accepted battery unit(s).  Ambiguous config-entry topology
    is never guessed and is marked as correction-required so runtime fails closed.
    """
    batteries_by_parent: dict[str, list[str]] = {}
    batteries_by_config: dict[tuple[str, str], list[str]] = {}
    inverters_by_config: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for provider in ((concepts.get("battery_system") or {}).get("providers") or []):
        integration = str(provider.get("integration_domain") or "")
        for unit in provider.get("units") or []:
            asset_id = str(unit.get("asset_id") or "")
            parent_device_id = str(unit.get("via_device_registry_id") or "")
            config_entry_id = str(unit.get("config_entry_id") or "")
            if parent_device_id and asset_id:
                batteries_by_parent.setdefault(parent_device_id, []).append(asset_id)
            if integration and config_entry_id and asset_id:
                batteries_by_config.setdefault(
                    (integration, config_entry_id), []
                ).append(asset_id)

    solar_providers = (concepts.get("solar_production") or {}).get("providers") or []
    for provider in solar_providers:
        integration = str(provider.get("integration_domain") or "")
        for inverter in provider.get("inverters") or []:
            config_entry_id = str(inverter.get("config_entry_id") or "")
            if integration and config_entry_id:
                inverters_by_config.setdefault(
                    (integration, config_entry_id), []
                ).append(inverter)

    for provider in solar_providers:
        integration = str(provider.get("integration_domain") or "")
        for inverter in provider.get("inverters") or []:
            inverter_device_id = str(inverter.get("device_registry_id") or "")
            explicit = sorted(set(batteries_by_parent.get(inverter_device_id, [])))
            config_entry_id = str(inverter.get("config_entry_id") or "")
            config_key = (integration, config_entry_id)
            same_config_batteries = sorted(set(batteries_by_config.get(config_key, [])))

            linked = explicit
            resolution = "explicit_via_device" if explicit else "not_required"
            correction_required = bool(explicit)

            if (
                not linked
                and integration == "solaredge_modbus_multi"
                and same_config_batteries
            ):
                correction_required = True
                if len(inverters_by_config.get(config_key, [])) == 1:
                    linked = same_config_batteries
                    resolution = "unique_config_entry"
                else:
                    resolution = "ambiguous_config_entry"

            inverter["linked_battery_asset_ids"] = linked
            inverter["battery_correction_required"] = correction_required
            inverter["battery_linkage_resolution"] = resolution

    # SolarEdge master/slave composition: local Modbus owns canonical inverter
    # identity and realtime truth; optimizer cloud contributes delayed topology.
    # Matching is fail-closed on stable hardware model + normalized serial only.
    master_by_identity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    master_by_serial: dict[str, list[dict[str, Any]]] = {}
    master_by_model: dict[str, list[dict[str, Any]]] = {}
    for provider in solar_providers:
        integration = str(provider.get("integration_domain") or "")
        if integration != "solaredge_modbus_multi":
            continue
        identity_resolver = get_inverter_identity_resolver(integration)
        serial_resolver = get_inverter_serial_resolver(integration)
        for inverter in provider.get("inverters") or []:
            identity = identity_resolver(inverter)
            if identity:
                master_by_identity.setdefault(identity, []).append(inverter)
            serial = serial_resolver(inverter)
            if serial:
                master_by_serial.setdefault(str(serial), []).append(inverter)
            model = str(inverter.get("model") or inverter.get("device_model") or "").strip().upper()
            if model:
                master_by_model.setdefault(model, []).append(inverter)

    for provider in ((concepts.get("solar_optimizer") or {}).get("providers") or []):
        integration = str(provider.get("integration_domain") or "")
        if integration != "solaredgeoptimizers":
            continue
        identity_resolver = get_inverter_identity_resolver(integration)
        serial_resolver = get_inverter_serial_resolver(integration)
        for zone in provider.get("zones") or []:
            identity = identity_resolver(zone)
            serial = serial_resolver(zone)
            matches = master_by_identity.get(identity) or [] if identity else []
            resolution = "hardware_model_and_normalized_serial"
            if not matches and serial:
                matches = master_by_serial.get(str(serial)) or []
                resolution = "exact_normalized_serial"
            # Some SolarEdge Optimizers versions expose the exact hardware model
            # on their inverter node but no hardware serial. A model-only link is
            # authoritative only when the exact model is unique across the accepted
            # local inverter set. Duplicate models remain unresolved; ordering,
            # display names and topology indexes are never used as evidence.
            if not matches and not serial:
                model = str(zone.get("model") or zone.get("device_model") or "").strip().upper()
                model_matches = master_by_model.get(model) or [] if model else []
                if len(model_matches) == 1:
                    matches = model_matches
                    resolution = "unique_exact_hardware_model"
                elif len(model_matches) > 1:
                    zone["master_linkage_resolution"] = "ambiguous_exact_hardware_model"
                    matches = []
            if len(matches) == 1:
                zone["master_inverter_asset_id"] = str(matches[0].get("asset_id") or "")
                zone["master_linkage_resolution"] = resolution
                zone["slave_topology_only"] = True
            elif len(matches) > 1:
                zone["master_linkage_resolution"] = (
                    "ambiguous_master_identity" if identity else "ambiguous_master_serial"
                )
            elif identity or serial:
                zone["master_linkage_resolution"] = "master_not_found"
            elif not zone.get("master_linkage_resolution"):
                zone["master_linkage_resolution"] = "insufficient_authoritative_inverter_identity"


def accept_energy_selected_inputs(
    build_inputs: dict[str, dict[str, Any]],
    previous_model: dict[str, Any] | None = None,
    *,
    preflight_issues: list[str] | None = None,
) -> EnergyDomainModel:
    previous_by_id = {
        binding["binding_id"]: binding
        for binding in (previous_model or {}).get("accepted_bindings", [])
        if isinstance(binding, dict) and binding.get("binding_id")
    }
    concepts: dict[str, Any] = {}
    bindings: list[AcceptedSourceBinding] = []
    issues = list(preflight_issues or [])
    revisions = []
    explicitly_absent: set[str] = set()
    assessments: dict[str, dict[str, Any]] = {}
    technical_observations: dict[str, Any] = {}
    provider_assets: dict[str, list[dict[str, Any]]] = {concept: [] for concept in _COLLECTION_CONCEPTS}

    for builder_id, build_input in sorted(build_inputs.items()):
        concept_id = (
            str((build_input.get("selection") or {}).get("concept") or "")
            or _concept_id_for_builder(builder_id)
            or "unknown"
        )
        revisions.append((build_input.get("configuration_revision"), build_input.get("candidate_revision"), build_input.get("build_input_revision")))
        if _selection_explicitly_empty(build_input):
            explicitly_absent.add(concept_id)
            assessments[builder_id] = {
                "status": "ABSENT",
                "concept": concept_id,
                "integration_domain": (build_input.get("selection") or {}).get("integration_domain"),
                "accepted_binding_count": 0,
                "usable_inputs": [],
                "issues": [],
            }
            continue

        before = len(bindings)
        local_issues: list[str] = []
        try:
            acceptor = _SEMANTIC_ACCEPTORS.get(concept_id)
            if acceptor is None:
                raise ValueError("unsupported_builder")
            accepted_bindings, asset, local_issues = acceptor(build_input, previous_by_id)
            bindings.extend(accepted_bindings)
            provider_assets[concept_id].append(asset)
        except Exception as exc:
            message = str(exc)
            local_issues.append(message)
            if message in {"no_measurement_anchor", "no_semantically_safe_measurement"}:
                technical_observations[builder_id] = {
                    "asset_type": f"{concept_id}_technical_observation",
                    "candidate_count": _candidate_count(build_input),
                    "required_candidate_count": _required_candidate_count(build_input),
                    "normalization_status": "DEGRADED",
                    "runtime_truth": False,
                }

        new_bindings = bindings[before:]
        usable = sorted({str(binding.get("semantic_role") or "") for binding in new_bindings if binding.get("semantic_role")})
        observation = technical_observations.get(builder_id)
        provider = provider_assets.get(concept_id, [])[-1] if provider_assets.get(concept_id) else {}
        status = str(provider.get("normalization_status")) if new_bindings else "DEGRADED" if observation else "BLOCKED"
        issues.extend(f"{builder_id}:{value}" for value in local_issues if value)
        assessments[builder_id] = {
            "status": status,
            "concept": concept_id,
            "integration_domain": (build_input.get("selection") or {}).get("integration_domain"),
            "accepted_binding_count": len(new_bindings),
            "usable_inputs": usable,
            "issues": [str(value) for value in local_issues][:20],
        }

    for concept, providers in provider_assets.items():
        if providers:
            concepts[concept] = {
                "asset_type": f"{concept}_provider_collection",
                "providers": providers,
                "normalization_status": "READY" if all(provider.get("normalization_status") == "READY" for provider in providers) else "DEGRADED",
            }
    explicitly_absent.difference_update(concepts.keys())
    _materialize_structural_relations(concepts)
    interim = {
        "concepts": concepts,
        "accepted_bindings": bindings,
        "concept_assessments": assessments,
        "technical_observations": technical_observations,
    }
    logical_assets = build_logical_assets(build_inputs, interim)
    base: EnergyDomainModel = {
        "kind": "energy_domain_model",
        "contract_version": "1.2.0",
        "domain_id": "energy",
        "concepts": concepts,
        "accepted_bindings": bindings,
        "explicitly_absent_concepts": sorted(explicitly_absent),
        "concept_assessments": assessments,
        "technical_observations": technical_observations,
        "logical_assets": logical_assets,
        "issues": issues,
        "source_revisions": revisions,
        "normalization": {
            "partial_concept_normalization": True,
            "none_is_not_zero": True,
            "foundation_outside_measurement_fast_path": True,
            "binding_from_selected_raw_match_only": True,
            "entity_name_guessing_for_binding": False,
            "unsafe_or_ambiguous_inputs_are_skipped_not_guessed": True,
            "object_centric_logical_assets": True,
            "logical_assets_survive_partial_normalization": True,
            "multi_provider_normalization": True,
            "semantic_registry_authoritative": True,
            "integration_adapter_boundary": True,
        },
    }
    previous = deepcopy(previous_model or {})
    previous_revision = int(previous.pop("domain_model_revision", 0) or 0)
    revision = previous_revision if previous and previous == base else previous_revision + 1
    base["domain_model_revision"] = max(1, revision)
    return base
