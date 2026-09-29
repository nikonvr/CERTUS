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


ALL_TOGETHER = """
import importlib, subprocess, sys
files = subprocess.run(
    ["git", "ls-files", "certus/core/*.py", "certus/physics/*.py", "certus/domain/*.py", "certus/domain/**/*.py"],
    capture_output=True, text=True, check=True,
).stdout.split()
for module in sorted({f[:-3].replace("/", ".").removesuffix(".__init__") for f in files}):
    importlib.import_module(module)
    if any(name.startswith("PyQt6") for name in sys.modules):
        print("QT AFTER", module)
        break
else:
    print("NO QT")
"""


def test_every_computation_module_together_loads_no_qt() -> None:
    """All of certus/core, certus/physics and certus/domain in one interpreter: no PyQt6.

    Measured 2026-09-29: 72 of the 73 load without Qt one by one; the last,
    certus.physics.gradient_analytic, cannot be imported first on its own (cycle with
    gradient_utils) but loads here after the others. Until then the STRAT core pulled Qt in
    through imports it never used (D26, D44).
    """
    out = subprocess.run([sys.executable, "-c", ALL_TOGETHER], capture_output=True, text=True, cwd=ROOT, timeout=900)
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip().splitlines()[-1] == "NO QT", out.stdout.strip()[-300:]
