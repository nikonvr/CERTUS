"""The spectral weights of the RMSE live in the domain layer, under the programs that share them.

`spectral_rmse_weights` gives each wavelength the weight of its interval in ln(lambda), so that a densely sampled
band does not weigh more than a sparse one. INDEX, DESIGN and RE all use it, and it lived in the utilities of INDEX:
the DESIGN workers and the RE helpers imported a module of another program for it, and the analytic gradient, in the
physics layer, imported the utilities, a layer above its own (audit of the corridors, F12; plan, phase 7b).

It is in `certus.domain.spectral_weights` now, under all of them. The utilities of INDEX import it back, so what reads
it there gets the very same function.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
NAME = "spectral_rmse_weights"
HOME = "certus.domain.spectral_weights"
OLD_HOME = "certus.utils.certus_index_utils"
#: The three modules that reached into the utilities of INDEX for the weights.
MOVED_READERS = ("certus/workers/certus_design_workers.py", "certus/core/certus_re_worker_utils.py", "certus/physics/gradient_analytic.py")


def imports_of(path: Path) -> dict[str, set[str]]:
    """module -> the names `path` imports from it, at module level or inside a function."""
    found: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.setdefault(node.module, set()).update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.setdefault(alias.name, set())
    return found


def test_the_utilities_of_index_expose_the_very_same_function():
    home = importlib.import_module(HOME)
    assert getattr(importlib.import_module(OLD_HOME), NAME) is getattr(home, NAME)
    assert getattr(home, NAME).__module__ == HOME


@pytest.mark.parametrize("reader", MOVED_READERS)
def test_a_reader_takes_the_weights_from_the_domain(reader):
    imports = imports_of(ROOT / reader)
    assert NAME in imports.get(HOME, set())
    assert NAME not in imports.get(OLD_HOME, set())


def test_no_module_of_the_physics_layer_imports_the_utilities_of_index():
    offenders = [path.name for path in sorted((ROOT / "certus" / "physics").glob("*.py")) if OLD_HOME in imports_of(path)]
    assert offenders == []


def test_the_domain_module_imports_nothing_of_certus():
    assert [module for module in imports_of(ROOT / "certus" / "domain" / "spectral_weights.py") if module.startswith(("certus", "PyQt"))] == []


def test_the_weights_are_the_intervals_in_log_lambda_normalised_to_the_number_of_points():
    weights = getattr(importlib.import_module(HOME), NAME)
    lam = np.array([400.0, 500.0, 800.0, 1600.0])
    log = np.log(lam)
    raw = np.array([log[1] - log[0], 0.5 * (log[2] - log[0]), 0.5 * (log[3] - log[1]), log[3] - log[2]])
    np.testing.assert_allclose(weights(lam), raw * lam.size / raw.sum(), rtol=1e-15)
    np.testing.assert_array_equal(weights(lam[::-1]), weights(lam)[::-1])
    np.testing.assert_array_equal(weights(np.array([500.0])), [1.0])
