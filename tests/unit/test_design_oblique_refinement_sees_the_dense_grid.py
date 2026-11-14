"""ALG-03: in oblique mode, DESIGN's final refinement must cost and differentiate on the grid it densified.

Measured 2026-10-16 and again 2026-11-14 (reports/alg03_grille_oblique_2026-11-14/): `maybe_upgrade_grid_tikhonravov`
densified the grid from 2 to 135 points and logged it, but the oblique configurations stayed on the 2 initial points.
Every cost and gradient of the refinement read 2 points, and the worker reported an RMSE of 0.026 for thicknesses
whose RMSE on the dense grid is 0.175. Normal incidence already refined on the 135 points.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

PROBE = Path(__file__).resolve().parents[2] / "reports" / "alg03_grille_oblique_2026-11-14" / "probe_alg03.py"


@pytest.fixture(scope="module")
def probe(qapp):
    spec = importlib.util.spec_from_file_location("probe_alg03", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_oblique_refinement_costs_on_the_dense_grid(qapp, probe) -> None:
    result = probe.worker_grid(True)
    assert "error" not in result, result
    assert result["refine_grid_points"] > 2
    assert result["cost_grid_sizes"] == [result["refine_grid_points"]]
    assert result["gradient_grid_sizes"] == [result["refine_grid_points"]]


def test_the_oblique_rmse_reported_is_the_dense_grid_rmse(qapp, probe) -> None:
    result = probe.worker_grid(True)
    assert np.isclose(result["reported_rmse"], result["direct_dense_rmse"], rtol=1e-9), result


def test_normal_incidence_is_unchanged(qapp, probe) -> None:
    result = probe.worker_grid(False)
    assert result["cost_grid_sizes"] == [result["refine_grid_points"]]
    assert np.isclose(result["reported_rmse"], result["direct_dense_rmse"], rtol=1e-12), result
