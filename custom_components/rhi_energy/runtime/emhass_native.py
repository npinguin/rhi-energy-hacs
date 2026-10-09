"""Compose a provider-native EMHASS request without narrowing native capabilities.

Only adapter-owned mappings may set native EMHASS parameter names. All values
come from Energy's canonical configuration and source evidence; this module
does not read or duplicate HA source settings.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .emhass_inputs import CanonicalHour, emhass_day_ahead_payload


class NativeCapabilityError(ValueError):
    pass


def compose_emhass_request(
    hours: list[CanonicalHour],
    *,
    native_parameters: dict[str, Any],
    supported_parameters: set[str],
) -> dict[str, Any]:
    """Fail closed for unsupported native parameters, never silently drop them.

    Version-specific mappings for battery, deferrable loads, costs, thermal
    constraints and optimizer settings must be implemented by the provider
    adapter and tested against the actual EMHASS version.
    """
    base = emhass_day_ahead_payload(hours)
    unknown = set(native_parameters) - supported_parameters
    if unknown:
        raise NativeCapabilityError(
            "unsupported_emhass_parameters:" + ",".join(sorted(unknown))
        )
    overlap = set(base) & set(native_parameters)
    if overlap:
        raise NativeCapabilityError(
            "native_parameters_override_canonical_forecasts:" + ",".join(sorted(overlap))
        )
    return {**base, **deepcopy(native_parameters)}


def validate_native_context(
    *,
    battery_systems: list[dict[str, Any]],
    flexible_loads: list[dict[str, Any]],
    mapped_battery_ids: set[str],
    mapped_load_ids: set[str],
) -> None:
    """Never optimize a partial ecosystem context as if it were complete.

    Unsupported equipment is an explicit blocker for EMHASS primary operation,
    not an excuse to aggregate separate batteries or omit EV constraints.
    Shadow operation may still report the missing capability diagnostics.
    """
    battery_ids = [str(row.get("asset_id") or "") for row in battery_systems]
    load_ids = [str(row.get("asset_id") or "") for row in flexible_loads]
    if any(not x for x in battery_ids + load_ids):
        raise NativeCapabilityError("canonical_asset_identity_missing")
    if len(set(battery_ids)) != len(battery_ids) or len(set(load_ids)) != len(load_ids):
        raise NativeCapabilityError("duplicate_canonical_asset_identity")
    missing_batteries = set(battery_ids) - mapped_battery_ids
    missing_loads = set(load_ids) - mapped_load_ids
    if missing_batteries or missing_loads:
        raise NativeCapabilityError(
            "native_context_not_representable:"
            + "batteries=" + ",".join(sorted(missing_batteries))
            + ";loads=" + ",".join(sorted(missing_loads))
        )
