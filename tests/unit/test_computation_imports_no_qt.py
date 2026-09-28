"""The computation modules load without Qt (CLAUDE.md, section 8).

Until 2026-09-28 `certus.core.certus_core` computed the SVG-widget flag at import time, so
importing the core — and every computation module that imports it, the TMM and the METAL
physics included — loaded QtWidgets, QtGui, QtSvg and QtSvgWidgets. The check now lives in
`certus.ui.certus_qt_svg`. Each module is imported in a fresh interpreter: in this process Qt
is already loaded by other tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

QT_FREE = [
    "certus.core.certus_core",
    "certus.core._certus_physics_impl",
    "certus.physics.certus_opt_tmm",
    "certus.physics.certus_strat_growth",
    "certus.spline.spline_objective",
    "certus.metal.certus_metal_single_physics",
    "certus.metal.certus_metal_bilayer_physics",
    "certus_physics",
]


@pytest.mark.parametrize("module", QT_FREE)
def test_importing_a_computation_module_loads_no_qt(module) -> None:
    code = (
        "import importlib, sys\n"
        f"importlib.import_module({module!r})\n"
        "print(','.join(sorted(m for m in sys.modules if m.startswith('PyQt6'))))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip() == "", f"{module} loads {out.stdout.strip()}"
