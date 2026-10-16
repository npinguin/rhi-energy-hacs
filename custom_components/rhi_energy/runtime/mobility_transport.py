"""Validate the actual Mobility Energy V2 HA transport envelope.

Mobility EnergyV2Sensor.native_value publishes a strictly positive monotonically
increasing integer contract revision. HA can retain old attributes when its
sensor state changes to unavailable/unknown. The state and attached revision
must agree before the Energy consumer uses any physical watts or demands.
"""
from __future__ import annotations

from typing import Any
from collections.abc import Mapping


def mobility_energy_transport_ready(state: Any) -> bool:
    if state is None:
        return False
    raw = str(getattr(state, "state", "")).strip()
    if not raw.isascii() or not raw.isdecimal() or int(raw) < 1:
        return False
    attrs = getattr(state, "attributes", None)
    if not isinstance(attrs, Mapping):
        return False
    revision = attrs.get("contract_revision")
    if type(revision) is not int or revision != int(raw):
        return False
    # No consumer may quietly become the price/energy or execution authority.
    if attrs.get("contains_physical_bindings") is not False or any(
        attrs.get(key) != owner for key, owner in (
            ("periodization_owner", "rhi_energy"),
            ("attribution_owner", "rhi_energy"),
            ("planning_owner", "rhi_energy"),
            ("physical_execution_owner", "rhi_mobility"),
        )
    ):
        return False
    fingerprint = attrs.get("content_fingerprint")
    return (
        isinstance(fingerprint, str)
        and len(fingerprint) == 64
        and all(char in "0123456789abcdef" for char in fingerprint.lower())
    )
