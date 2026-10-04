"""Guided canonical configuration flow for Robotix Home Intelligence Energy."""
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
)

from .const import DOMAIN
from .v2_configuration import configuration_rows


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
    """Guided product configuration over canonical Public V2 properties."""

    _PRICING_FIELDS = {
        "market_price_fallback": "pricing.spot_eur_kwh",
        "network_cost": "pricing.import_network_eur_kwh",
        "levies": "pricing.import_levies_eur_kwh",
        "vat": "pricing.import_vat_pct",
        "export_fee": "pricing.export_fee_eur_kwh",
    }
    _METERING_FIELDS = {
        "display_period": "metering.selected_period",
    }
    _STRATEGY_FIELDS = {
        "home": {
            "operating_mode": "energy.operating_mode",
            "primary_objective": "home.primary_objective",
        },
        "battery": {
            "objective": "battery.objective",
            "grid_policy": "battery.grid_policy",
            "solar_policy": "battery.solar_policy",
            "battery_policy": "battery.battery_policy",
            "surplus_policy": "battery.surplus_policy",
            "reserve_target": "battery.reserve_target_pct",
        },
        "solar": {
            "objective": "solar.surplus_objective",
            "grid_policy": "solar.grid_policy",
            "solar_policy": "solar.solar_policy",
            "battery_policy": "solar.battery_policy",
            "surplus_policy": "solar.surplus_policy",
        },
        "grid": {
            "home_battery_policy": "grid.home_battery_policy",
            "flexible_load_policy": "grid.flexible_load_policy",
        },
        "ev_charging": {
            "objective": "flexible_loads.objective",
            "grid_policy": "flexible_loads.grid_policy",
            "solar_policy": "flexible_loads.solar_policy",
            "battery_policy": "flexible_loads.battery_policy",
            "surplus_policy": "flexible_loads.surplus_policy",
        },
        "resilience": {
            "objective": "resilience.objective",
            "grid_policy": "resilience.grid_policy",
            "battery_policy": "resilience.battery_policy",
        },
    }

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

    def _row_map(self) -> dict[str, dict[str, Any]]:
        return {
            str(row.get("property_id")): row
            for row in configuration_rows(self._contract())
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
            if not row:
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
            if not row:
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
        return_step,
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

        # Stay inside the exact section the user just configured. Rebuild the form
        # from Public V2 so saved readback is visible immediately and no hidden
        # wizard state becomes a second authority.
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._form_schema(fields),
        )

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["pricing", "strategy", "metering"],
        )

    async def async_step_pricing(self, user_input=None):
        return await self._edit(
            step_id="pricing",
            fields=self._PRICING_FIELDS,
            user_input=user_input,
            return_step=self.async_step_init,
        )

    async def async_step_strategy(self, user_input=None):
        return self.async_show_menu(
            step_id="strategy",
            menu_options=["home", "battery", "solar", "grid", "ev_charging", "resilience"],
        )

    async def async_step_metering(self, user_input=None):
        return await self._edit(
            step_id="metering",
            fields=self._METERING_FIELDS,
            user_input=user_input,
            return_step=self.async_step_init,
        )

    async def async_step_home(self, user_input=None):
        return await self._edit(
            step_id="home",
            fields=self._STRATEGY_FIELDS["home"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )

    async def async_step_battery(self, user_input=None):
        return await self._edit(
            step_id="battery",
            fields=self._STRATEGY_FIELDS["battery"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )

    async def async_step_solar(self, user_input=None):
        return await self._edit(
            step_id="solar",
            fields=self._STRATEGY_FIELDS["solar"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )

    async def async_step_grid(self, user_input=None):
        return await self._edit(
            step_id="grid",
            fields=self._STRATEGY_FIELDS["grid"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )

    async def async_step_ev_charging(self, user_input=None):
        return await self._edit(
            step_id="ev_charging",
            fields=self._STRATEGY_FIELDS["ev_charging"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )

    async def async_step_resilience(self, user_input=None):
        return await self._edit(
            step_id="resilience",
            fields=self._STRATEGY_FIELDS["resilience"],
            user_input=user_input,
            return_step=self.async_step_strategy,
        )
