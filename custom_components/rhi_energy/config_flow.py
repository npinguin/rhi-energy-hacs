"""Config flow for Robotix Home Intelligence Energy.

The flow intentionally imports only Home Assistant config-flow primitives and local
constants. Foundation is validated during config-entry setup, not while Home
Assistant is trying to construct this flow handler.
"""
from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class RhiEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single Energy module config entry."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Create the Energy entry; single-instance policy is manifest-owned."""
        return self.async_create_entry(
            title="Robotix Home Intelligence - Energy Module",
            data={},
        )
