"""A module that sits, or sat, in an import cycle can be imported FIRST, ALONE, in a fresh interpreter.

A cycle that works in one order only is a fault waiting for the first script, test or plugin that imports in another
order. Measured on 2026-09-30, before S4.2, in a fresh interpreter: `import certus.physics.gradient_analytic` failed
("cannot import name 'make_cost_function' from partially initialized module": gradient_utils re-exported it from the end
of its file), and so did `certus.ui.certus_index_spline_managers_ui` and `certus_index_spline_mixins_ui`. Nothing in the
suite noticed, because everything imports through the facades that happen to go in the working order.

The modules of the cycles that remain (tests/architecture_debt.json) are checked as they stand: a cycle is allowed to
exist, not to depend on who comes first. The modules of the cycles that were broken stay here for good.

The imports run in parallel, in interpreters with Numba's JIT off (importing is all that is asked of them).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Broken on 2026-09-30 (S4.2). Add the members of every cycle that a later step breaks.
WERE_IN_A_CYCLE = [
    "certus.domain.optical.entities.optical_stack",
    "certus.physics.gradient_analytic",
    "certus.physics.gradient_utils",
    "certus.ui.certus_index_spline_common",
    "certus.ui.certus_index_spline_managers_ui",
    "certus.ui.certus_index_spline_mixins_ui",
]

STILL_IN_ONE = sorted(
    {module for cycle in json.loads((ROOT / "tests" / "architecture_debt.json").read_text("utf-8"))["cycles"] for module in cycle}
)
MODULES = sorted({*WERE_IN_A_CYCLE, *STILL_IN_ONE})


@pytest.fixture(scope="module")
def imports() -> dict[str, tuple[int, str]]:
    env = {**os.environ, "NUMBA_DISABLE_JIT": "1", "QT_QPA_PLATFORM": "offscreen"}
    processes = {
        module: subprocess.Popen(
            [sys.executable, "-c", f"import {module}"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for module in MODULES
    }
    results = {}
    for module, process in processes.items():
        output, _ = process.communicate(timeout=600)
        results[module] = (process.returncode, output[-600:])
    return results


@pytest.mark.parametrize("module", MODULES)
def test_the_module_imports_first_and_alone(module, imports) -> None:
    code, output = imports[module]

    assert code == 0, f"`import {module}` as the first import of a fresh interpreter fails:\n{output}"


def test_the_list_is_not_empty_and_names_modules_that_exist() -> None:
    assert len(MODULES) >= 15
    for module in MODULES:
        path = ROOT / Path(*module.split("."))
        assert path.with_suffix(".py").exists() or (path / "__init__.py").exists(), module
