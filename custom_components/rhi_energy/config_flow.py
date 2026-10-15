"""Guided canonical configuration flow for Robotix Home Intelligence Energy."""
from __future__ import annotations

from typing import Any
from .runtime.planner_providers import (
    available_selection_ids, provider_catalog, validate_planner_url,
    validate_provider_id, validate_primary_provider_id,
)

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
from .runtime.configuration_write import confirmed_configuration_readback


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
                # A live source may make an initially editable field read-only
                # while its OptionsFlow form is open. Never silently skip Save.
                raise ValueError("canonical_property_not_editable")
            value = user_input[field_name]
            if value == row.get("value"):
                continue
            result = await interaction.write_property(property_id, value)
            if not isinstance(result, dict) or result.get("status") != "CONFIRMED":
                if isinstance(result, dict) and result.get("status") == "REJECTED":
                    raise ValueError("canonical_property_write_rejected")
                raise RuntimeError("canonical_property_write_not_confirmed")
            # Only the matching operation's persisted authoritative readback
            # may complete the editor. Returning from a service call is not proof.
            current_row = self._row_map().get(property_id)
            if not confirmed_configuration_readback(result, value, current_row):
                raise RuntimeError("canonical_property_readback_mismatch")

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
        except RuntimeError as exc:
            return self.async_show_form(
                step_id=step_id,
                data_schema=self._form_schema(fields),
                errors={"base": (
                    "canonical_runtime_unavailable"
                    if str(exc) == "canonical_runtime_unavailable"
                    else "write_not_confirmed"
                )},
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
        """Select the operational planner or edit its independent connection."""
        return self.async_show_menu(
            step_id="planner",
            menu_options=["planner_selection", "emhass", "haeo", "akkudoktor_eos"],
        )

    async def async_step_planner_selection(self, user_input=None):
        """Edit the same config-entry option as the native HA planner selector."""
        options = dict(self.config_entry.options)
        current = str(options.get("planner_provider") or "rhi_deterministic")
        choices = available_selection_ids(options)
        # An unknown previously persisted choice must not be silently replaced.
        if current not in choices:
            choices = (*choices, current)
        catalog = provider_catalog()
        schema = vol.Schema({
            vol.Required("planner_provider", default=current):
                SelectSelector(SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=provider_id,
                            label=(catalog[provider_id].label
                                   if provider_id in catalog else
                                   f"Unknown provider ({provider_id})"),
                        )
                        for provider_id in choices
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )),
        })
        if user_input is None:
            return self.async_show_form(
                step_id="planner_selection", data_schema=schema,
            )
        selected = str(user_input.get("planner_provider") or "")
        if selected not in choices or selected not in catalog:
            return self.async_show_form(
                step_id="planner_selection", data_schema=schema,
                errors={"planner_provider": "invalid_configuration"},
            )
        # A configured native optimizer may only provide shadow advice until
        # its existing provider-catalog execution gate is qualified. Keep the
        # historic request visible (and connection settings intact), but do not
        # silently accept or rewrite it as an operational planner on Save.
        try:
            validate_provider_id(selected)
            validate_primary_provider_id(selected)
        except ValueError:
            error = (
                "emhass_activation_not_yet_supported"
                if selected == "emhass"
                else "invalid_configuration"
            )
            return self.async_show_form(
                step_id="planner_selection", data_schema=schema,
                errors={"planner_provider": error},
            )
        if selected == current:
            return self.async_create_entry(title="", data=options)
        options["planner_provider"] = selected
        return self.async_create_entry(title="", data=options)

    def _connection_settings(self, provider_id: str) -> dict[str, Any]:
        options = dict(self.config_entry.options)
        saved = options.get("planner_connections") or {}
        row = saved.get(provider_id) if isinstance(saved, dict) else None
        if isinstance(row, dict):
            return dict(row)
        if provider_id == "emhass" and options.get("emhass_url"):
            return {
                "url": options["emhass_url"],
                "timeout_seconds": options.get("emhass_timeout_seconds", 30),
            }
        return {}

    def _persist_planner_connection(self, provider_id: str, config: dict[str, Any]):
        options = dict(self.config_entry.options)
        connections = options.get("planner_connections") or {}
        if not isinstance(connections, dict):
            raise ValueError("planner_connections_invalid")
        connections = dict(connections)
        connections[provider_id] = dict(config)
        options["planner_connections"] = connections
        # One migration alias while the existing EMHASS runner reads flat keys.
        # Both values are derived from the same technical source, never from a
        # guessed Home Assistant endpoint.
        if provider_id == "emhass":
            options["emhass_url"] = config["url"]
            options["emhass_timeout_seconds"] = config["timeout_seconds"]
        # Intentional: do NOT touch options["planner_provider"] here.
        return self.async_create_entry(title="", data=options)

    async def async_step_emhass(self, user_input=None):
        """EMHASS 0.18.5 technical connection; Energy owns all optimizer inputs."""
        current = self._connection_settings("emhass")
        schema = vol.Schema({
            vol.Required("url", default=current.get("url") or ""): str,
            vol.Required("timeout_seconds", default=current.get("timeout_seconds", 30)):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
        })
        if user_input is None:
            return self.async_show_form(step_id="emhass", data_schema=schema)
        try:
            url = validate_planner_url(user_input["url"])
        except (KeyError, ValueError):
            return self.async_show_form(
                step_id="emhass", data_schema=schema,
                errors={"url": "invalid_configuration"},
            )
        return self._persist_planner_connection("emhass", {
            "url": url, "timeout_seconds": int(user_input["timeout_seconds"]),
        })

    async def async_step_haeo(self, user_input=None):
        """Bind an existing HAEO integration; do not invent solver API access."""
        entries = list(self.hass.config_entries.async_entries("haeo"))
        candidates = {entry.entry_id: str(entry.title or entry.entry_id) for entry in entries}
        if not candidates:
            return self.async_abort(reason="haeo_config_entry_missing")
        saved = self._connection_settings("haeo")
        current = saved.get("config_entry_id")
        schema = vol.Schema({
            vol.Required("config_entry_id", default=current or next(iter(candidates))):
                vol.In(list(candidates)),
        })
        if user_input is None:
            return self.async_show_form(step_id="haeo", data_schema=schema)
        selected = str(user_input["config_entry_id"])
        if selected not in candidates:
            return self.async_show_form(
                step_id="haeo", data_schema=schema,
                errors={"config_entry_id": "invalid_configuration"},
            )
        # Connection configuration exists, but a verified HAEO OptimizationContext
        # ingestion/result adapter does NOT. The registry marks it DESIGN_ONLY.
        return self._persist_planner_connection("haeo", {
            "config_entry_id": selected,
        })

    async def async_step_akkudoktor_eos(self, user_input=None):
        """Versioned EOS HTTP endpoint; protocol must be explicitly selected."""
        saved = self._connection_settings("akkudoktor_eos")
        schema = vol.Schema({
            vol.Required("url", default=saved.get("url") or ""): str,
            vol.Required(
                "protocol",
                default=saved.get("protocol") or "legacy_optimize_v0",
            ): vol.In(["legacy_optimize_v0", "v1_optimize"]),
            vol.Required("timeout_seconds", default=saved.get("timeout_seconds", 30)):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
        })
        if user_input is None:
            return self.async_show_form(
                step_id="akkudoktor_eos", data_schema=schema,
            )
        try:
            url = validate_planner_url(user_input["url"])
        except (ValueError, KeyError):
            return self.async_show_form(
                step_id="akkudoktor_eos", data_schema=schema,
                errors={"url": "invalid_configuration"},
            )
        return self._persist_planner_connection("akkudoktor_eos", {
            "url": url,
            "protocol": str(user_input["protocol"]),
            "timeout_seconds": int(user_input["timeout_seconds"]),
        })
