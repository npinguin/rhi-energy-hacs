"""Tiny Energy integration-adapter boundary.

Adapters only normalize integration-specific value conventions. They never discover
entities, inspect Foundation-private state or choose semantic bindings.

For a new integration with ordinary conventions, no adapter is needed. For a real quirk,
add ``adapters/<integration_domain>.py`` exposing ``normalize(role, value, context)``.
"""
from __future__ import annotations

import importlib
import re
from typing import Any, Callable

_SAFE_DOMAIN = re.compile(r"^[a-z0-9_]+$")
Normalizer = Callable[[str, Any, dict[str, Any]], Any]
_CACHE: dict[str, Normalizer] = {}


def _neutral(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value


def get_normalizer(integration_domain: str | None):
    domain = str(integration_domain or "").strip().lower()
    if not domain or not _SAFE_DOMAIN.fullmatch(domain):
        return _neutral
    cached = _CACHE.get(domain)
    if cached is not None:
        return cached
    module_name = f"{__name__}.{domain}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        normalizer = _neutral
    else:
        normalizer = getattr(module, "normalize", None)
        if not callable(normalizer):
            raise RuntimeError(f"energy_adapter_invalid:{domain}:normalize_missing")
    _CACHE[domain] = normalizer
    return normalizer
