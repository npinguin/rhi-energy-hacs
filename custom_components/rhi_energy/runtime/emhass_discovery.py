"""Resolve an installed EMHASS HA add-on without guessed LAN addresses.

Only the official Home Assistant Supervisor add-on catalogue is consulted.
Never scan the network and never use 0.0.0.0 or localhost as a host.
"""
from __future__ import annotations
from typing import Any


class EmhassDiscoveryError(ValueError):
    pass


def candidate_from_supervisor(addons: dict[str, Any]) -> str:
    matches = []
    for slug, info in addons.items():
        if not isinstance(info, dict) or not isinstance(slug, str):
            continue
        name = str(info.get("name") or "")
        if "emhass" not in (slug + " " + name).lower():
            continue
        if str(info.get("state") or "").lower() != "started":
            continue
        # Supervisor port mappings describe host exposure, not whether the
        # add-on is listening on its internal network. Never require them.
        host = slug.replace("_", "-")
        if not host.replace("-", "").isalnum():
            raise EmhassDiscoveryError("unsafe_addon_slug")
        matches.append(f"http://{host}:5000")
    if len(matches) != 1:
        raise EmhassDiscoveryError(
            "emhass_addon_not_found_or_ambiguous" if not matches else "emhass_addon_ambiguous"
        )
    return matches[0]


def discover_emhass_addon(hass: Any) -> str:
    if "hassio" not in hass.data:
        raise EmhassDiscoveryError("supervisor_not_available")
    from homeassistant.components.hassio import get_addons_info
    try:
        result = get_addons_info(hass)
    except Exception as exc:
        raise EmhassDiscoveryError("supervisor_addon_metadata_unavailable") from exc
    return candidate_from_supervisor(result)
