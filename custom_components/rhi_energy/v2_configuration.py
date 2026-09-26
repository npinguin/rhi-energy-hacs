"""First-class Home Assistant editors over canonical Energy Public V2 configuration."""
from __future__ import annotations

from typing import Any

from .const import DOMAIN, RELEASE


def configuration_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    configuration = contract.get("configuration") or {}
    pricing = (configuration.get("pricing") or {}).get("properties") or []
    strategy = (configuration.get("strategy") or {}).get("configured_properties") or []
    return [
        row for row in [*pricing, *strategy]
        if isinstance(row, dict) and row.get("property_id") and row.get("editable") is True
    ]


def configuration_row(contract: dict[str, Any], property_id: str) -> dict[str, Any]:
    return next(
        (row for row in configuration_rows(contract) if str(row.get("property_id")) == property_id),
        {},
    )


def editable_rows(contract: dict[str, Any], editor: str) -> list[dict[str, Any]]:
    return [
        row for row in configuration_rows(contract)
        if str(row.get("editor") or "") == editor
    ]


def configuration_device_info() -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, "logical:configuration")},
        "name": "Energy Configuration",
        "manufacturer": "Robotix Home Intelligence",
        "model": "Energy canonical configuration",
        "sw_version": RELEASE,
    }
