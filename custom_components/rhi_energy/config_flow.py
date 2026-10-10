"""Guided canonical configuration flow for Robotix Home Intelligence Energy."""
from __future__ import annotations

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
)

from .const import DOMAIN
from .v2_configuration import canonical_configuration_rows
from .runtime.capability_service import EnergyCapabilityService


class RhiEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single Energy module config entry."""

    # OptionsFlow presentation changed in E0.15.95/E0.15.96, but the persisted
    # config-entry schema did not. Keep VERSION 2 so existing entries never require
    # a migration handler for a UI-only change.
    VERSION = 2

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
    """Guided product configuration over Energy-owned canonical properties."""

    def _state(self) -> dict[str, Any]:
        return (
            (getattr(self, "hass", None).data.get(DOMAIN, {}) or {})
            .get(self.config_entry.entry_id, {})
        )

    def _interaction(self):
        return self._state().get("interaction")

    def _row_map(self) -> dict[str, dict[str, Any]]:
        state = self._state()
        runtime = state.get("runtime")
        store = state.get("store")
        if runtime is None or store is None:
            return {}
        return {
            str(row.get("property_id")): row
            for row in canonical_configuration_rows(runtime, store)
            if isinstance(row, dict) and row.get("property_id")
        }

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
                    SelectOptionDict(value=str(value), label=str(value).replace("_", " ").title())
                    for value in (constraints.get("allowed") or [])
                ]
            return SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )
        if editor in {"number", "slider"}:
            return NumberSelector(
                NumberSelectorConfig(
                    min=constraints.get("min"),
                    max=constraints.get("max"),
                    step=constraints.get("step"),
                    unit_of_measurement=row.get("unit"),
                )
            )
        return str

    def _form_schema(self, fields: dict[str, str]) -> vol.Schema:
        rows = self._row_map()
        schema: dict[Any, Any] = {}
        for field_name, property_id in fields.items():
            row = rows.get(property_id)
            if not EnergyCapabilityService.editable_definition(row):
                continue
            value = row.get("value")
            key = (
                vol.Optional(field_name, description={"suggested_value": value})
                if value not in (None, "")
                else vol.Optional(field_name)
            )
            schema[key] = self._selector(row)
        return vol.Schema(schema)

    async def _write_fields(
        self,
        fields: dict[str, str],
        user_input: dict[str, Any],
    ) -> None:
        rows = self._row_map()
        interaction = self._interaction()
        if interaction is None:
            raise RuntimeError("canonical_runtime_unavailable")
        for field_name, property_id in fields.items():
            if field_name not in user_input:
                continue
            row = rows.get(property_id)
            if not EnergyCapabilityService.editable_definition(row):
                continue
            value = user_input[field_name]
            if value == row.get("value"):
                continue
            await interaction.write_property(property_id, value)

    async def _edit(
        self,
        *,
        step_id: str,
        fields: dict[str, str],
        user_input,
    ):
        schema = self._form_schema(fields)
        if not schema.schema:
            return self.async_abort(reason="canonical_configuration_unavailable")
        if user_input is None:
            return self.async_show_form(step_id=step_id, data_schema=schema)
        try:
            await self._write_fields(fields, user_input)
        except RuntimeError:
            return self.async_show_form(
                step_id=step_id,
                data_schema=schema,
                errors={"base": "canonical_runtime_unavailable"},
            )
        except (TypeError, ValueError):
            return self.async_show_form(
                step_id=step_id,
                data_schema=schema,
                errors={"base": "invalid_configuration"},
            )

        # Rebuild from the canonical store so saved readback is visible immediately.
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._form_schema(fields),
        )

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["pricing", "strategy", "metering", "planner"],
        )

    async def async_step_pricing(self, user_input=None):
        return await self._edit(
            step_id="pricing",
            fields=EnergyCapabilityService.configuration_fields("pricing"),
            user_input=user_input,
        )

    async def async_step_strategy(self, user_input=None):
        return self.async_show_menu(
            step_id="strategy",
            menu_options=["home", "battery", "solar", "grid", "ev_charging", "resilience"],
        )

    async def async_step_metering(self, user_input=None):
        return await self._edit(
            step_id="metering",
            fields=EnergyCapabilityService.configuration_fields("metering"),
            user_input=user_input,
        )

    async def async_step_home(self, user_input=None):
        return await self._edit(
            step_id="home",
            fields=EnergyCapabilityService.configuration_fields("home"),
            user_input=user_input,
        )

    async def async_step_battery(self, user_input=None):
        return await self._edit(
            step_id="battery",
            fields=EnergyCapabilityService.configuration_fields("battery"),
            user_input=user_input,
        )

    async def async_step_solar(self, user_input=None):
        return await self._edit(
            step_id="solar",
            fields=EnergyCapabilityService.configuration_fields("solar"),
            user_input=user_input,
        )

    async def async_step_grid(self, user_input=None):
        return await self._edit(
            step_id="grid",
            fields=EnergyCapabilityService.configuration_fields("grid"),
            user_input=user_input,
        )

    async def async_step_ev_charging(self, user_input=None):
        return await self._edit(
            step_id="ev_charging",
            fields=EnergyCapabilityService.configuration_fields("ev_charging"),
            user_input=user_input,
        )

    async def async_step_resilience(self, user_input=None):
        return await self._edit(
            step_id="resilience",
            fields=EnergyCapabilityService.configuration_fields("resilience"),
            user_input=user_input,
        )


    async def async_step_planner(self, user_input=None):
        """One user choice; all optimization parameters belong to RHI domains."""
        current = dict(self.config_entry.options)
        schema = vol.Schema({
            vol.Required(
                "planner_provider",
                default=current.get("planner_provider", "rhi_deterministic"),
            ): vol.In(["rhi_deterministic", "emhass"]),
        })
        if user_input is None:
            return self.async_show_form(step_id="planner", data_schema=schema)
        provider = str(user_input["planner_provider"])
        # Preserve legacy technical values during migration, never require
        # the user to maintain them in the planner selection wizard.
        current["planner_provider"] = provider
        return self.async_create_entry(title="", data=current)
