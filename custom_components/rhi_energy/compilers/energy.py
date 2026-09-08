"""Energy-owned semantic compiler for Foundation SelectedDomainBuildInput 1.2.0.

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
from typing import Any

try:
    from ..models import AcceptedBinding, CompiledEnergyModel
    from ..runtime.logical_assets import build_logical_assets
    from ..semantic import input_definitions
except ImportError:  # Direct runpy/static unit-test execution without package context.
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parents[1]
    build_logical_assets = _runpy.run_path(str(_root / "runtime" / "logical_assets.py"))["build_logical_assets"]
    input_definitions = _runpy.run_path(str(_root / "semantic.py"))["input_definitions"]
    AcceptedBinding = dict  # type: ignore[assignment,misc]
    CompiledEnergyModel = dict  # type: ignore[assignment,misc]


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
    for group in _groups(build_input, input_id):
        candidates = [item for item in (group.get("candidates") or []) if isinstance(item, dict)]
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
) -> AcceptedBinding:
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
        "raw_capability_id": selected_match.get("raw_capability_id"),
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
    source = candidate.get("source_identity") or {}
    evidence = candidate.get("evidence") or {}
    return str(source.get("device_registry_id") or evidence.get("device_registry_id") or "")


def _candidate_config_id(candidate: dict[str, Any]) -> str:
    source = candidate.get("source_identity") or {}
    return str(source.get("config_entry_id") or _candidate_device_id(candidate) or candidate.get("candidate_id") or "")


def _candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence") or {}
    source = candidate.get("source_identity") or {}
    return {
        "display_name": evidence.get("device_name") or evidence.get("entity_name") or evidence.get("original_name"),
        "manufacturer": evidence.get("device_manufacturer"),
        "model": evidence.get("device_model"),
        "via_device_registry_id": evidence.get("via_device_registry_id"),
        "device_registry_id": source.get("device_registry_id") or evidence.get("device_registry_id"),
        "config_entry_id": source.get("config_entry_id"),
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
    bindings: list[AcceptedBinding],
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
    bindings: list[AcceptedBinding],
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


def _compile_battery(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "battery_system")
    measurement_ids = ["battery_unit_power", "battery_unit_soc", "battery_capacity"]
    device_ids = sorted(
        {
            _candidate_device_id(candidate)
            for input_id in measurement_ids
            for candidate in inputs.get(input_id, [])
            if _candidate_device_id(candidate)
        }
    )
    if not device_ids:
        raise ValueError("no_measurement_anchor")
    builder_id = str(build_input.get("builder_id") or "battery")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    system_id = f"battery_system_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedBinding] = []
    units: list[dict[str, Any]] = []
    device_specs = [spec for spec in input_definitions("battery_system") if spec.get("object_scope") == "device"]
    for device_id in device_ids:
        asset_id = f"battery_unit_{_hash([builder_id, device_id], 10)}"
        role_map: dict[str, str] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in device_specs:
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if _candidate_device_id(candidate) == device_id]
            if role == "capacity" and not rows and len(inputs.get(input_id, [])) == 1 and not _candidate_device_id(inputs[input_id][0]):
                rows = inputs[input_id]
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"battery_{role}:{device_id}:ambiguous")
        if role_map:
            metadata = _candidate_metadata(local_candidates[0]) if local_candidates else {}
            units.append({"asset_id": asset_id, "bindings": role_map, **metadata, "device_registry_id": device_id})
    if not units:
        raise ValueError("no_semantically_safe_measurement")

    reserve_binding = None
    reserves = inputs.get("reserve_write_surface", [])
    entity_reserves = [
        candidate
        for candidate in reserves
        if (candidate.get("source_identity") or {}).get("source_kind") == "entity"
        and str((candidate.get("source_identity") or {}).get("current_entity_id") or "").startswith("number.")
    ]
    if len(entity_reserves) == 1:
        reserve = entity_reserves[0]
        source = reserve.get("source_identity") or {}
        scope = source.get("target_scope")
        config_entries = {
            (candidate.get("source_identity") or {}).get("config_entry_id")
            for input_id in measurement_ids
            for candidate in inputs.get(input_id, [])
            if (candidate.get("source_identity") or {}).get("config_entry_id")
        }
        target = source.get("target") or {}
        target_device = source.get("device_registry_id") or target.get("device_registry_id")
        attributable = scope not in {None, "none"}
        if scope == "config_entry":
            attributable = source.get("config_entry_id") in config_entries or target.get("config_entry_id") in config_entries
        elif scope == "device":
            attributable = target_device in set(device_ids)
        if attributable:
            binding_id = f"energy:{system_id}:reserve"
            bindings.append(_binding(system_id, "reserve", reserve, previous.get(binding_id)))
            reserve_binding = binding_id
        else:
            issues.append("reserve_write_surface:not_attributable")
    elif len(entity_reserves) > 1:
        issues.append(f"reserve_write_surface:ambiguous:count_{len(entity_reserves)}")
    elif reserves:
        issues.append("reserve_write_surface:no_executable_number_entity")

    complete = sum(1 for unit in units if {"power", "soc", "capacity"}.issubset((unit.get("bindings") or {}).keys()))
    return (
        bindings,
        {
            "asset_id": system_id,
            "asset_type": "battery_system",
            "units": units,
            "reserve_binding": reserve_binding,
            "builder_id": builder_id,
            "integration_domain": integration,
            "normalization_status": "READY" if complete == len(units) and not issues else "DEGRADED",
        },
        issues,
    )


def _compile_grid(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "grid_connection")
    builder_id = str(build_input.get("builder_id") or "grid")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    asset_id = f"grid_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedBinding] = []
    roles: dict[str, Any] = {}
    for spec in input_definitions("grid_connection"):
        role = str(spec.get("role") or "")
        input_id = str(spec.get("input_id") or "")
        binding_id = _single_role(bindings, previous, asset_id, role, inputs.get(input_id, []), issues)
        if binding_id:
            roles[role] = binding_id
    phase_rows, local = _safe_for(build_input, "grid_phase_power")
    issues.extend(local)
    phases = []
    for candidate in phase_rows:
        phase_id = f"grid_phase_{_hash([asset_id, candidate.get('candidate_id')], 10)}"
        binding_id = f"energy:{phase_id}:power"
        bindings.append(_binding(phase_id, "power", candidate, previous.get(binding_id)))
        phases.append({"asset_id": phase_id, "binding": binding_id, **_candidate_metadata(candidate)})
    if phases:
        roles["phases"] = [phase["binding"] for phase in phases]
    if not roles:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": asset_id, "asset_type": "grid_connection", "bindings": roles, "phases": phases, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if "net_power" in roles and not issues else "DEGRADED"}, issues


def _compile_solar(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "solar_production")
    phase_rows, local = _safe_for(build_input, "phase_power")
    issues.extend(local)
    inputs["phase_power"] = phase_rows
    anchors = sorted({_candidate_device_id(candidate) for rows in inputs.values() for candidate in rows if _candidate_device_id(candidate)})
    if not anchors:
        raise ValueError("no_semantically_safe_input")
    builder_id = str(build_input.get("builder_id") or "solar")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    system_id = f"solar_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedBinding] = []
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
        phases = []
        for candidate in [candidate for candidate in inputs.get("phase_power", []) if _candidate_device_id(candidate) == device_id]:
            phase_id = f"solar_inverter_phase_{_hash([asset_id, candidate.get('candidate_id')], 10)}"
            binding_id = f"energy:{phase_id}:power"
            bindings.append(_binding(phase_id, "power", candidate, previous.get(binding_id)))
            phases.append({"asset_id": phase_id, "binding": binding_id, **_candidate_metadata(candidate)})
        if phases:
            role_map["phases"] = [phase["binding"] for phase in phases]
        if role_map:
            metadata = _candidate_metadata(local_candidates[0] if local_candidates else phases[0] if phases else {})
            inverters.append({"asset_id": asset_id, "device_registry_id": device_id, "bindings": role_map, "phases": phases, **metadata})
    if not inverters:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": system_id, "asset_type": "solar_system", "inverters": inverters, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if all("power" in (item.get("bindings") or {}) for item in inverters) and not issues else "DEGRADED"}, issues


def _compile_provider_semantics(
    build_input: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    concept: str,
    asset_id: str,
) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, concept)
    bindings: list[AcceptedBinding] = []
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


def _compile_forecast(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    builder_id = str(build_input.get("builder_id") or "forecast")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    asset_id = f"forecast_{_hash([integration, builder_id], 8)}"
    bindings, roles, issues = _compile_provider_semantics(build_input, previous, "solar_forecast", asset_id)
    if not roles:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": asset_id, "asset_type": "solar_forecast", "bindings": roles, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if roles.get("today_energy") and not issues else "DEGRADED"}, issues


def _compile_price(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    builder_id = str(build_input.get("builder_id") or "price")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "price")
    asset_id = f"price_source_{_hash([integration, builder_id], 8)}"
    bindings, roles, issues = _compile_provider_semantics(build_input, previous, "price_source", asset_id)
    if not roles:
        raise ValueError("no_semantically_safe_input")
    completeness = sum(1 for key in ("current", "future", "currency", "tariff") if key in roles)
    return bindings, {"asset_id": asset_id, "asset_type": "price_source", "bindings": roles, "builder_id": builder_id, "integration_domain": integration, "semantic_completeness": completeness, "normalization_status": "READY" if "current" in roles and not issues else "DEGRADED"}, issues


def _compile_gas(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
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
    bindings: list[AcceptedBinding] = []
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


def _compile_optimizer(build_input: dict[str, Any], previous: dict[str, dict[str, Any]]) -> tuple[list[AcceptedBinding], dict[str, Any], list[str]]:
    inputs, issues = _safe_inputs(build_input, "solar_optimizer")
    anchors = sorted(
        {
            _candidate_device_id(candidate)
            or str((candidate.get("source_identity") or {}).get("entity_registry_id") or candidate.get("candidate_id") or "")
            for rows in inputs.values()
            for candidate in rows
            if _candidate_device_id(candidate)
            or (candidate.get("source_identity") or {}).get("entity_registry_id")
            or candidate.get("candidate_id")
        }
    )
    if not anchors:
        raise ValueError("no_semantically_safe_input")
    builder_id = str(build_input.get("builder_id") or "optimizer")
    integration = str((build_input.get("selection") or {}).get("integration_domain") or "")
    provider_id = f"optimizer_provider_{_hash([integration, builder_id], 8)}"
    bindings: list[AcceptedBinding] = []
    optimizers: list[dict[str, Any]] = []

    def anchor_for(candidate):
        return _candidate_device_id(candidate) or str((candidate.get("source_identity") or {}).get("entity_registry_id") or candidate.get("candidate_id") or "")

    for anchor in anchors:
        asset_id = f"solar_optimizer_{_hash([builder_id, anchor], 10)}"
        role_map: dict[str, str] = {}
        local_candidates: list[dict[str, Any]] = []
        for spec in input_definitions("solar_optimizer"):
            role = str(spec.get("role") or "")
            input_id = str(spec.get("input_id") or "")
            rows = [candidate for candidate in inputs.get(input_id, []) if anchor_for(candidate) == anchor]
            if len(rows) == 1:
                binding_id = f"energy:{asset_id}:{role}"
                bindings.append(_binding(asset_id, role, rows[0], previous.get(binding_id)))
                role_map[role] = binding_id
                local_candidates.extend(rows)
            elif len(rows) > 1:
                issues.append(f"optimizer_{role}:{anchor}:ambiguous")
        if role_map:
            metadata = _candidate_metadata(local_candidates[0]) if local_candidates else {}
            optimizers.append({"asset_id": asset_id, "bindings": role_map, **metadata, "device_registry_id": metadata.get("device_registry_id") or anchor})
    if not optimizers:
        raise ValueError("no_semantically_safe_input")
    return bindings, {"asset_id": provider_id, "asset_type": "solar_optimizer_collection", "optimizers": optimizers, "builder_id": builder_id, "integration_domain": integration, "normalization_status": "READY" if all("power" in (item.get("bindings") or {}) for item in optimizers) and not issues else "DEGRADED"}, issues


_COMPILERS = {
    "battery_system": _compile_battery,
    "grid_connection": _compile_grid,
    "solar_production": _compile_solar,
    "solar_forecast": _compile_forecast,
    "price_source": _compile_price,
    "gas_meter": _compile_gas,
    "solar_optimizer": _compile_optimizer,
}
_COLLECTION_CONCEPTS = set(_COMPILERS)


def compile_energy_build_inputs(
    build_inputs: dict[str, dict[str, Any]],
    previous_model: dict[str, Any] | None = None,
    *,
    preflight_issues: list[str] | None = None,
) -> CompiledEnergyModel:
    previous_by_id = {
        binding["binding_id"]: binding
        for binding in (previous_model or {}).get("accepted_bindings", [])
        if isinstance(binding, dict) and binding.get("binding_id")
    }
    concepts: dict[str, Any] = {}
    bindings: list[AcceptedBinding] = []
    issues = list(preflight_issues or [])
    revisions = []
    explicitly_absent: set[str] = set()
    assessments: dict[str, dict[str, Any]] = {}
    technical_observations: dict[str, Any] = {}
    provider_assets: dict[str, list[dict[str, Any]]] = {concept: [] for concept in _COLLECTION_CONCEPTS}

    for builder_id, build_input in sorted(build_inputs.items()):
        concept_id = _concept_id_for_builder(builder_id) or "unknown"
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
            compiler = _COMPILERS.get(concept_id)
            if compiler is None:
                raise ValueError("unsupported_builder")
            compiled_bindings, asset, local_issues = compiler(build_input, previous_by_id)
            bindings.extend(compiled_bindings)
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
    interim = {
        "concepts": concepts,
        "accepted_bindings": bindings,
        "concept_assessments": assessments,
        "technical_observations": technical_observations,
    }
    logical_assets = build_logical_assets(build_inputs, interim)
    base: CompiledEnergyModel = {
        "kind": "compiled_domain_model",
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
    previous_revision = int(previous.pop("compiled_model_revision", 0) or 0)
    revision = previous_revision if previous and previous == base else previous_revision + 1
    base["compiled_model_revision"] = max(1, revision)
    return base
