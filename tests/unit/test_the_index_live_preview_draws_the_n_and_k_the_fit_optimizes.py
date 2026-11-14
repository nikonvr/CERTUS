"""INDEX's live preview of the Tauc-Lorentz-Urbach fit draws the n and k the fit optimizes (ETAT D104).

While a TLU fit runs, INDEX redraws n, k, R and T from the best parameters found so far: `CertusIndexApp._on_curve_update` reads
`_index_tlu_live_payload_from_params`, on the grid that `_make_index_tlu_live_ctx` builds. That method unpacked the seven parameters as
(thickness, Eg, A, E0, C, Eu, eps_inf) and gave `epsilon1_TL_analytic` the Urbach energy `Eu` where it takes `eps_inf`, from the initial commit on, while
`TLUObjective.__call__`, `IndexOptimizationStrategy._package_results` and the phase-5 blend of the UI worker all pass `eps_inf`. As eps_inf enters eps1
additively, every curve drawn during the fit stood on an eps1 lower by `eps_inf - Eu`: with the first vector below, the preview's n ran from 1.73 to 2.06
where the fit's runs from 2.23 to 2.49, and its R and T were up to 21.8 points away from the fit's (measured 2026-10-12). The result the fit returns was
never touched, only what the user watched while it ran.

The two payload tests of `test_certus_index_callbacks.py` did not see it: their reference repeated the mistake, `Eu` for `eps_inf`. The reference here is
read where the fit makes it. What is pinned here:

    the n and k of the payload are those that `TLUObjective.__call__` evaluates for the same vector, taken at its call to `epsilon_to_nk`, on the objective
    the worker builds from the same configuration (`IndexOptimizationStrategy._prepare_run_inputs`); the vectors keep `Eu` far from `eps_inf`, so that
    giving one for the other cannot go unseen: a window below the gap, a gap inside the window, and the vector of the older payload tests
    the preview is drawn on the wavelengths of that objective
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

import certus.core.certus_index_objectives as objectives
from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy
from CERTUS_INDEX import CertusIndexApp, DataType, OptimizationConfig

# The seven parameters of the TLU fit: thickness (nm), Eg, A, E0, C, Eu, eps_inf (energies in eV).
VECTORS = {
    "window_below_the_gap": [2950.0, 3.26, 117.85, 5.19, 1.53, 0.26, 2.25],
    "gap_inside_the_window": [800.0, 1.8, 80.0, 4.2, 1.2, 0.15, 3.1],
    "vector_of_the_older_payload_tests": [150.0, 2.5, 200.0, 4.0, 0.5, 0.2, 2.2],
}


def configuration():
    """81 points from 400 to 2000 nm on N-BK7. The targets are read by the cost of the fit, not by the preview."""
    wavelengths = np.linspace(400.0, 2000.0, 81)
    data = pd.DataFrame({"lambda": wavelengths, "T": np.full(81, 0.9), "R": np.full(81, 0.08)})
    return OptimizationConfig(
        target_data=data,
        data_type=DataType.BOTH,
        substrate="N-BK7",
        thickness_min=100.0,
        thickness_max=5000.0,
        lambda_min=400.0,
        lambda_max=2000.0,
        use_normalized=False,
    )


def the_fit_objective(config):
    """The `TLUObjective` the worker builds from this configuration when it starts a fit."""
    worker = MagicMock()
    worker.thickness_initial = 500.0
    *_, objective = IndexOptimizationStrategy._prepare_run_inputs(worker, config)
    return objective


def nk_the_fit_evaluates(monkeypatch, objective, params):
    """The n and k `TLUObjective.__call__` builds for `params`, taken where it hands eps1 and eps2 to `epsilon_to_nk`."""
    taken = []
    real = objectives.epsilon_to_nk

    def spy(*args):
        taken.append(real(*args))
        return taken[-1]

    monkeypatch.setattr(objectives, "epsilon_to_nk", spy)
    objective(params)
    assert len(taken) == 1, "the cost is expected to evaluate the model once per call"
    n, k, valid = taken[0]
    assert valid, "the fit rejects this vector: it proves nothing about the preview"
    return n, k


@pytest.mark.parametrize("vector", list(VECTORS.values()), ids=list(VECTORS))
def test_the_live_preview_draws_the_n_and_k_the_fit_optimizes(monkeypatch, vector):
    config = configuration()
    app = MagicMock()
    app._index_tlu_live_ctx = CertusIndexApp._make_index_tlu_live_ctx(app, config)
    assert app._index_tlu_live_ctx is not None
    objective = the_fit_objective(config)
    params = np.array(vector, dtype=np.float64)

    payload = CertusIndexApp._index_tlu_live_payload_from_params(app, params)
    assert payload is not None, "the preview drew nothing for a vector the fit evaluates"
    n_fit, k_fit = nk_the_fit_evaluates(monkeypatch, objective, params)

    np.testing.assert_array_equal(payload["wls"], objective.wavelengths)
    np.testing.assert_allclose(payload["n"], n_fit, rtol=1e-12, atol=0.0, err_msg="the preview's n is not the n the fit optimizes")
    np.testing.assert_allclose(payload["k"], k_fit, rtol=1e-12, atol=0.0, err_msg="the preview's k is not the k the fit optimizes")
