"""First-class Home Assistant editors over Energy-owned canonical configuration."""
from __future__ import annotations

from typing import Any

from .const import DOMAIN, RELEASE


def configuration_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    configuration = contract.get("configuration") or {}
    pricing = (configuration.get("pricing") or {}).get("properties") or []
    strategy = (configuration.get("strategy") or {}).get("configured_properties") or []
    metering = (configuration.get("metering") or {}).get("properties") or []
    return [
        row for row in [*pricing, *strategy, *metering]
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


def canonical_configuration_rows(runtime, store) -> list[dict[str, Any]]:
    """Native HA editor inputs directly from Energy-owned canonical configuration.

    This is a bounded selector of authoritative property descriptions, not a
    second snapshot, persisted model, or Public V2 contract.
    """
    from .runtime.canonical_semantics import prop, pricing_properties, strategy_properties

    settings = store.data.get("settings") or {}
    facts = runtime.snapshot.get("facts") or {}
    metering = prop(
        "metering",
        "metering.selected_period",
        str(settings.get("metering_selected_period") or "today"),
        editable=True,
        editor="select",
        operation_id="energy.metering.set_property",
        constraints={"allowed": ["hour", "today", "week", "month", "year"]},
        choices=[
            {"value": "hour", "label": "This hour"},
            {"value": "today", "label": "Today"},
            {"value": "week", "label": "This week"},
            {"value": "month", "label": "This month"},
            {"value": "year", "label": "This year"},
        ],
        group="metering",
    )
    # Attach the original write/readback lifecycle to the same native entity.
    # This is a bounded current-property selection, not a second configuration
    # contract or a Public V2 snapshot.
    operations = store.data.get("property_operation_state") or {}
    rows = []
    for raw in [*pricing_properties(facts, settings), *strategy_properties(settings), metering]:
        if not isinstance(raw, dict) or not raw.get("property_id") or raw.get("editable") is not True:
            continue
        row = dict(raw)
        operation = operations.get(str(row["property_id"]))
        if isinstance(operation, dict):
            status = str(operation.get("status") or "UNKNOWN")
            row["write_state"] = status
            row["write_status"] = status
            row["readback_value"] = operation.get("readback_value")
            row["operation"] = {
                "operation_id": operation.get("operation_id"),
                "status": status,
                "reason": operation.get("reason"),
                "requested_value": operation.get("requested_value"),
                "requested_at": operation.get("requested_at"),
                "completed_at": operation.get("completed_at"),
                "readback_value": operation.get("readback_value"),
            }
        rows.append(row)
    return rows


def canonical_configuration_row(runtime, store, property_id: str) -> dict[str, Any]:
    return next(
        (row for row in canonical_configuration_rows(runtime, store)
         if str(row.get("property_id")) == property_id),
        {},
    )


def canonical_editable_rows(runtime, store, editor: str) -> list[dict[str, Any]]:
    return [
        row for row in canonical_configuration_rows(runtime, store)
        if str(row.get("editor") or "") == editor
    ]
