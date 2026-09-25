"""Temporary Energy V1 compatibility imports.

Canonical business semantics live in runtime.canonical_semantics. This module exists
only so the frozen R1.89.x facade can keep its import surface during the V2 pilot.
No canonical runtime module may import from compat_core.
"""
from __future__ import annotations

try:
    from .runtime.canonical_semantics import *  # noqa: F401,F403
except ImportError:  # standalone runpy regression/contract tests
    from pathlib import Path as _Path
    import runpy as _runpy

    _symbols = _runpy.run_path(
        str(_Path(__file__).resolve().parent / "runtime" / "canonical_semantics.py")
    )
    globals().update({
        key: value
        for key, value in _symbols.items()
        if not key.startswith("__")
    })
