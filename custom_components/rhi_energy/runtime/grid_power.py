"""Pure Grid power fact normalization for the Energy runtime."""
from __future__ import annotations

from typing import Any

try:
    from .canonical_semantics import normalize_grid_power
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    normalize_grid_power = _runpy.run_path(
        str(_Path(__file__).resolve().parent / "canonical_semantics.py")
    )["normalize_grid_power"]


def apply_grid_power_facts(
    props: dict[str, dict[str, Any]],
    facts: dict[str, Any],
) -> None:
    """Materialize canonical net/import/export from either supported source shape."""
    net_key = str((props.get("grid.net_power_kw") or {}).get("fact_key") or "")
    import_key = str((props.get("grid.measured_import_power_kw") or {}).get("fact_key") or "")
    export_key = str((props.get("grid.measured_export_power_kw") or {}).get("fact_key") or "")
    normalized = normalize_grid_power(
        facts.get(net_key) if net_key else None,
        facts.get(import_key) if import_key else None,
        facts.get(export_key) if export_key else None,
    )
    if net_key:
        facts[net_key] = normalized["net_power_kw"]
    if "grid_import.power_kw" in props:
        facts[str(props["grid_import.power_kw"].get("fact_key"))] = normalized["import_power_kw"]
    if "grid_export.power_kw" in props:
        facts[str(props["grid_export.power_kw"].get("fact_key"))] = normalized["export_power_kw"]
