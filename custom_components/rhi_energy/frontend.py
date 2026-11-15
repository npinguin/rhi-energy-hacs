"""Optional bundled frontend transport; never expose data or arbitrary files."""
from __future__ import annotations

from hashlib import sha256
import json
import logging
from pathlib import Path
import re

from .const import DOMAIN, UX_OPTION

_LOGGER = logging.getLogger(__name__)
RESOURCE_ROOT = "/rhi_energy/frontend"
BUNDLE = "rhi-energy-ux.js"
_MIME = {".js": "text/javascript", ".webp": "image/webp",
         ".svg": "image/svg+xml", ".png": "image/png",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_ASSET = re.compile(r"assets/(?:[a-z0-9][a-z0-9_.-]*/)*[a-z0-9][a-z0-9_.-]*\.(?:webp|svg|png|jpg|jpeg)")


def load_frontend(root: Path, version: str) -> dict[str, tuple[bytes, str]]:
    """Verify the packaged inventory; serve only declared JS and image bytes."""
    manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["product"] != DOMAIN or manifest["version"] != version or manifest["bundle_filename"] != BUNDLE:
        raise ValueError("frontend identity mismatch")
    payloads = {}
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        if name in seen:
            raise ValueError("duplicate frontend path")
        seen.add(name)
        if name == BUNDLE + ".sha256":
            continue
        if name != BUNDLE and (not _ASSET.fullmatch(name) or ".." in name):
            raise ValueError("unapproved frontend path")
        file = root / name
        if not file.resolve().is_relative_to(root.resolve()):
            raise ValueError("frontend path escapes package")
        data = file.read_bytes()
        if len(data) != row["bytes"]:
            raise ValueError("frontend size mismatch")
        if sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("frontend file checksum mismatch")
        payloads[name] = (data, _MIME[file.suffix])
    if BUNDLE not in payloads or sha256(payloads[BUNDLE][0]).hexdigest() != manifest["runtime_sha256"]:
        raise ValueError("frontend bundle checksum mismatch")
    return payloads


async def async_register_frontend(hass):
    """Register the verified static routes, even when the optional frontend is disabled."""
    if getattr(hass, "http", None) is None:
        return
    from aiohttp import web
    from homeassistant.components.http import HomeAssistantView
    from homeassistant.config_entries import ConfigEntryState

    def load():
        root = Path(__file__).parent
        version = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["version"]
        try:
            return version, load_frontend(root / "frontend", version)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            _LOGGER.warning("Energy frontend unavailable: %s", type(exc).__name__)
            return version, {}

    version, payloads = await hass.async_add_executor_job(load)

    class EnergyFrontendView(HomeAssistantView):
        def __init__(self, asset, payload):
            self.url = RESOURCE_ROOT + "/" + asset
            self.name = "rhi_energy:frontend:" + asset
            self.payload = payload

        requires_auth = False  # Static public artwork and JS only, not HA data.

        def _response(self, request, head=False):
            headers = {"Cache-Control": "no-store", "X-RHI-Version": version,
                       "X-Content-Type-Options": "nosniff"}
            entries = hass.config_entries.async_entries(DOMAIN)
            enabled = (len(entries) == 1
                       and entries[0].state == ConfigEntryState.LOADED
                       and entries[0].options.get(UX_OPTION, True) is True)
            asset = self.payload if enabled else None
            if asset is None:
                return web.Response(status=404, headers=headers)
            data, content_type = asset
            return web.Response(body=b"" if head else data, content_type=content_type, headers=headers)

        async def get(self, request):
            return self._response(request)

        async def head(self, request):
            return self._response(request, head=True)

    for asset, payload in payloads.items():
        hass.http.register_view(EnergyFrontendView(asset, payload))


def async_setup_ux(hass, entry):
    """Load the owned card through HA, preserving dashboard and resource ownership."""
    from homeassistant.components import frontend
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.core import callback

    resource = RESOURCE_ROOT + "/" + BUNDLE
    owned = False

    @callback
    def sync():
        nonlocal owned
        manager = hass.data.get(frontend.DATA_EXTRA_MODULE_URL)
        if manager is None:
            return
        enabled = entry.state is ConfigEntryState.LOADED and entry.options.get(UX_OPTION, True) is True
        if enabled and resource not in manager.urls:
            frontend.add_extra_js_url(hass, resource)
            owned = True
        elif not enabled and owned:
            if resource in manager.urls:
                frontend.remove_extra_js_url(hass, resource)
            owned = False

    async def updated(hass, entry):
        sync()

    entry.async_on_unload(entry.async_on_state_change(sync))
    entry.async_on_unload(entry.add_update_listener(updated))
    sync()
