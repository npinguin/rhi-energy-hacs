"""Tiny Energy integration-adapter boundary.

Adapters normalize integration-specific value conventions and refine candidates that
Foundation already selected mechanically. They never discover entities, inspect
Foundation-private state, or scan Home Assistant at runtime.

For a new integration with ordinary conventions, no adapter is needed. For a real quirk,
add ``adapters/<integration_domain>.py`` exposing ``normalize(role, value, context)``.
"""
from __future__ import annotations

import importlib
import re
from typing import Any, Callable

_SAFE_DOMAIN = re.compile(r"^[a-z0-9_]+$")
Normalizer = Callable[[str, Any, dict[str, Any]], Any]
CandidateFilter = Callable[[str, dict[str, Any]], bool]
MarketRoleResolver = Callable[[dict[str, Any]], str | None]
TopologyKeyResolver = Callable[[dict[str, Any]], str | None]
_MODULE_CACHE: dict[str, Any | None] = {}


def _neutral(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value


def _module(integration_domain: str | None):
    domain = str(integration_domain or "").strip().lower()
    if not domain or not _SAFE_DOMAIN.fullmatch(domain):
        return None
    if domain in _MODULE_CACHE:
        return _MODULE_CACHE[domain]
    module_name = f"{__name__}.{domain}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        module = None
    _MODULE_CACHE[domain] = module
    return module


def get_normalizer(integration_domain: str | None) -> Normalizer:
    module = _module(integration_domain)
    if module is None:
        return _neutral
    normalizer = getattr(module, "normalize", None)
    if not callable(normalizer):
        raise RuntimeError(f"energy_adapter_invalid:{integration_domain}:normalize_missing")
    return normalizer


def get_candidate_filter(integration_domain: str | None) -> CandidateFilter:
    predicate = getattr(_module(integration_domain), "accept_candidate", None)
    return predicate if callable(predicate) else lambda _input_id, _candidate: True


def get_market_role_resolver(integration_domain: str | None) -> MarketRoleResolver:
    resolver = getattr(_module(integration_domain), "market_role", None)
    return resolver if callable(resolver) else lambda candidate: (
        str((candidate.get("semantic_metadata") or {}).get("market_role"))
        if (candidate.get("semantic_metadata") or {}).get("market_role") in {"import", "export"}
        else None
    )


def get_topology_key_resolver(integration_domain: str | None) -> TopologyKeyResolver:
    """Return adapter-owned stable topology-key extraction, never display-name inference."""
    resolver = getattr(_module(integration_domain), "topology_key", None)
    return resolver if callable(resolver) else lambda _row: None
