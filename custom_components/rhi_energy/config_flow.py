"""Canonical configuration flow for Robotix Home Intelligence Energy."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import DOMAIN
from .v2_configuration import configuration_rows


class RhiEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single Energy module config entry."""

    VERSION = 3

    @staticmethod
    def async_get_options_flow(config_entry):
        return RhiEnergyOptionsFlow()

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="Robotix Home Intelligence - Energy Module",
                data={},
            )
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class RhiEnergyOptionsFlow(config_entries.OptionsFlow):
    """Edit canonical Public V2 Energy configuration without a parallel config model."""

    _GROUPS = ("pricing", "strategy", "metering")
    _target_group: str | None = None

    def _state(self) -> dict[str, Any]:
        return (
            (getattr(self, "hass", None).data.get(DOMAIN, {}) or {})
            .get(self.config_entry.entry_id, {})
        )

    def _contract(self) -> dict[str, Any]:
        projector = self._state().get("public_projector")
        return deepcopy(projector.get_v2() or {}) if projector is not None else {}

    def _interaction(self):
        return self._state().get("interaction")

    def _rows(self, group: str) -> list[dict[str, Any]]:
        rows = configuration_rows(self._contract())
        if group == "pricing":
            return [row for row in rows if str(row.get("property_id") or "").startswith("pricing.")]
        if group == "metering":
            return [row for row in rows if str(row.get("property_id") or "").startswith("metering.")]
        return [
            row for row in rows
            if not str(row.get("property_id") or "").startswith(("pricing.", "metering."))
        ]

    @staticmethod
    def _selector(row: dict[str, Any]):
        editor = str(row.get("editor") or "text")
        constraints = row.get("constraints") or {}
        choices = row.get("choices") or []
        if editor == "select":
            options = [
                SelectOptionDict(
                    value=str(choice.get("value")),
                    label=str(choice.get("label") or choice.get("value")),
                )
                for choice in choices
                if isinstance(choice, dict) and choice.get("value") is not None
            ]
            if not options:
                options = [
                    SelectOptionDict(value=str(value), label=str(value))
                    for value in (constraints.get("allowed") or [])
                ]
            return SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )
        if editor == "number":
            return NumberSelector(
                NumberSelectorConfig(
                    min=constraints.get("min"),
                    max=constraints.get("max"),
                    step=constraints.get("step"),
                    unit_of_measurement=row.get("unit"),
                )
            )
        if editor == "switch":
            return bool
        return TextSelector(TextSelectorConfig())

    def _schema(self, rows: list[dict[str, Any]]) -> vol.Schema:
        fields: dict[Any, Any] = {}
        for row in rows:
            property_id = str(row.get("property_id") or "")
            if not property_id:
                continue
            value = row.get("value")
            marker = (
                vol.Optional(property_id, description={"suggested_value": value})
                if value not in (None, "")
                else vol.Optional(property_id)
            )
            fields[marker] = self._selector(row)
        return vol.Schema(fields)

    async def async_step_init(self, user_input=None):
        available = [group for group in self._GROUPS if self._rows(group)]
        if not available:
            return self.async_abort(reason="canonical_configuration_unavailable")
        return self.async_show_menu(step_id="init", menu_options=available)

    async def _edit_group(self, group: str, step_id: str, user_input=None):
        rows = self._rows(group)
        if not rows:
            return await self.async_step_init()
        if user_input is None:
            self._target_group = group
            return self.async_show_form(
                step_id=step_id,
                data_schema=self._schema(rows),
                description_placeholders={
                    "authority": "Values are written through the canonical Energy Public V2 property contract."
                },
            )

        interaction = self._interaction()
        if interaction is None:
            return self.async_show_form(
                step_id=step_id,
                data_schema=self._schema(rows),
                errors={"base": "canonical_runtime_unavailable"},
            )
        current = {str(row.get("property_id")): row.get("value") for row in rows}
        try:
            for property_id, value in user_input.items():
                if property_id not in current or value == current[property_id]:
                    continue
                await interaction.write_property(str(property_id), value)
        except (TypeError, ValueError):
            return self.async_show_form(
                step_id=step_id,
                data_schema=self._schema(rows),
                errors={"base": "invalid_configuration"},
            )
        return await self.async_step_init()

    async def async_step_pricing(self, user_input=None):
        return await self._edit_group("pricing", "pricing", user_input)

    async def async_step_strategy(self, user_input=None):
        return await self._edit_group("strategy", "strategy", user_input)

    async def async_step_metering(self, user_input=None):
        return await self._edit_group("metering", "metering", user_input)
