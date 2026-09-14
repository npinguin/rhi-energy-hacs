"""Active layered Energy compiler for E0.14."""
from __future__ import annotations

try:
    from .layered_model_base import materialize_layered_energy_model as _base
    from .closure_model import close_layered_energy_model as _close
except ImportError:
    from pathlib import Path
    import runpy

    _here = Path(__file__).resolve().parent
    _base = runpy.run_path(str(_here / "layered_model_base.py"))[
        "materialize_layered_energy_model"
    ]
    _close = runpy.run_path(str(_here / "closure_model.py"))[
        "close_layered_energy_model"
    ]

LAYERED_MODEL_CONTRACT = {
    "runtime_may_mutate_topology": False,
    "runtime_may_discover_assets": False,
    "telemetry_may_trigger_compile": False,
    "structural_changes_require_new_generation": True,
    "compatibility_projection_may_create_semantics": False,
    "planning_concepts": (
        "planning_model",
        "planning_horizon",
        "planning_asset",
        "energy_need",
        "constraint_set",
        "allocation_set",
        "operational_plan",
    ),
    "intelligence_concepts": (
        "energy_outlook",
        "cost_outlook",
        "energy_intelligence",
        "planning_experience",
    ),
}


def materialize_layered_energy_model(model):
    layered = _base(model)
    layered.setdefault("runtime_rules", {}).update(
        {
            key: value
            for key, value in LAYERED_MODEL_CONTRACT.items()
            if isinstance(value, bool)
        }
    )
    return _close(layered)
