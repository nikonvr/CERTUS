"""The METAL SINGLE beam must judge its R-only scan against an R-only reference (audit 2026-11-15, C-L6b).

The beam scan refits n, k at each fixed thickness on R alone (objective_function_fixed_eM), but its acceptance
threshold was 1.5 x optimal_mse, the main fit's MSE averaged over R, T and Rback. When T or Rback fit worse than R the
threshold was far too loose (or too tight in the other case), and the reported thickness range was wrong. The
reference is now the R-only cost of the optimum itself.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core._certus_physics_impl import get_n_substrate_array_by_id
from certus.metal.certus_metal_single_physics import objective_function_fixed_eM
from certus_physics import calculate_RTRback_incoherent_vectorized, get_nk_from_spline

NUM_KNOTS = 4
MIN_KNOT_DIST = 20.0
EM_TRUE = 20.0
N_KNOTS = np.array([0.4, 0.6, 0.9, 1.3])
K_KNOTS = np.array([2.5, 3.2, 4.0, 4.8])
LAMBDA_INTERNES = np.array([550.0, 700.0])


def _synthetic() -> tuple[dict, np.ndarray]:
    lam = np.linspace(400.0, 900.0, 51)
    knot_l = np.concatenate(([lam.min()], LAMBDA_INTERNES, [lam.max()]))
    n, k = get_nk_from_spline(np.concatenate((N_KNOTS, K_KNOTS)), knot_l, lam)
    n_sub = get_n_substrate_array_by_id(0, lam).astype(np.complex128)
    r, _t, _rb = calculate_RTRback_incoherent_vectorized(
        np.array([EM_TRUE]), (n - 1j * k).reshape(-1, 1), n_sub, lam
    )
    params = {
        "num_knots": NUM_KNOTS,
        "target_lambda": lam,
        "target_r": np.asarray(r, dtype=np.float64),
        "min_knot_dist": MIN_KNOT_DIST,
        "substrate_id": 0,
        "eM_min": 1.0,
        "eM_max": 100.0,
        "nk_min": 0.01,
        "nk_max": 10.0,
    }
    x_opt = np.concatenate(([EM_TRUE], N_KNOTS, K_KNOTS, LAMBDA_INTERNES))
    return params, x_opt


@pytest.mark.unit
def test_the_beam_threshold_comes_from_the_r_only_cost_of_the_optimum(qapp) -> None:
    from certus.metal.certus_metal_single_app import BeamAnalysisWorker

    params, x_opt = _synthetic()
    lam = params["target_lambda"]
    precomputed = {
        "min_lambda": lam.min(),
        "max_lambda": lam.max(),
        "nSub_complex_array": get_n_substrate_array_by_id(0, lam).astype(np.complex128),
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(NUM_KNOTS, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * NUM_KNOTS, dtype=np.float64),
    }
    r_only = objective_function_fixed_eM(
        np.concatenate((N_KNOTS, K_KNOTS)), EM_TRUE, NUM_KNOTS, lam, params["target_r"], MIN_KNOT_DIST,
        precomputed, lambda_internes_fixed=LAMBDA_INTERNES,
    )
    joint_mse = 0.02  # the main fit's mean over R, T and Rback, with T and Rback fitted far worse than R
    stats: dict = {}
    worker = BeamAnalysisWorker(params, x_opt.copy(), joint_mse, step_nm=10.0, mse_tolerance=0.1)
    worker.finished.connect(stats.update)
    worker.error.connect(lambda message: stats.update(error=message))
    worker.run()

    assert "error" not in stats, stats.get("error")
    assert stats["threshold"] == pytest.approx(max(r_only * 1.5 + 1e-5, 5e-5), rel=1e-12)
