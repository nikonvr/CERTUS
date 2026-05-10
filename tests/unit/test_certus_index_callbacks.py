import pytest
from unittest.mock import MagicMock
import numpy as np
import pandas as pd

# We mock what we need from CERTUS_INDEX to test the logic of the callbacks independently
from certus_core import SMALL_EPSILON, SUBSTRATES
from certus_physics import get_n_substrate_array_by_id
from CERTUS_INDEX import (
    CertusIndexApp,
    DataType,
    HC_EV_NM,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    OptimizationConfig,
    Phase1Callback,
    Phase2PolishCallback,
    OptimizationWorker,
    calculate_relative_R_normalization,
    calculate_RT_single_layer_backside_array,
    calculate_bare_substrate_RT,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
)

def test_phase1_callback():
    # Setup worker mock
    mock_worker = MagicMock()
    mock_worker.is_stopped = False
    mock_worker.best_mse = 2.0
    mock_worker.best_params = None
    mock_worker._optimizer = MagicMock()
    mock_worker._optimizer.n_evals = 10

    cb = Phase1Callback(mock_worker, max_evals=100)

    # Fake a sample from optimizer
    class Sample:
        def __init__(self, x, y):
            self.x = x
            self.y = y
    
    # 1. Test case where y < best_mse
    s_improved = Sample(np.array([1.0, 2.0]), 1.0)
    cb(s_improved)
    
    assert mock_worker.best_mse == 1.0
    np.testing.assert_array_equal(mock_worker.best_params, np.array([1.0, 2.0]))
    mock_worker._try_active_update.assert_called_with(s_improved.x, s_improved.y, force=True)
    mock_worker.progress.emit.assert_called_with(6, "Global Search...", 1.0)

def test_phase2_polish_callback():
    mock_worker = MagicMock()
    mock_worker.is_stopped = False
    mock_worker.best_mse = 0.5

    cb = Phase2PolishCallback(mock_worker)
    
    xk = np.array([1.5, 2.5])
    cb(xk)
    
    assert cb.polish_iters == 1
    # 15 * 1 / 200 = 0 -> prog_polish = min(75, 60+0) = 60
    mock_worker.progress.emit.assert_called_with(60, "Polish 1", None)
    mock_worker._try_active_update.assert_called_with(xk, 0.5, force=False)


def _tlu_reference_rt_norm(wls, n_sub, params):
    """Référence identique à _package_results / _index_tlu_live_payload_from_params (non frosted)."""
    p = np.asarray(params, dtype=np.float64).ravel()
    thickness = float(p[0])
    Eg, A, E0, C, Eu, eps_inf = (float(p[i]) for i in range(1, 7))
    E_arr = HC_EV_NM / wls
    eps2 = epsilon2_TLU_array(E_arr, Eg, A, E0, C, Eu)
    eps1 = epsilon1_TL_analytic(E_arr, Eg, A, E0, C, Eu)
    n_calc, k_calc, is_valid = epsilon_to_nk(
        eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT
    )
    assert is_valid
    R_calc, T_calc = calculate_RT_single_layer_backside_array(
        wls, n_calc, k_calc, thickness, n_sub
    )
    T_sub = calculate_bare_substrate_RT(wls, n_sub)
    with np.errstate(divide="ignore", invalid="ignore"):
        T_sub_safe = np.where(T_sub > SMALL_EPSILON, T_sub, 1.0)
        T_norm = np.where(T_sub > SMALL_EPSILON, T_calc / T_sub_safe, np.nan)
        T_norm = np.maximum(T_norm, 0.0)
    R_norm = calculate_relative_R_normalization(R_calc, T_sub)
    return R_calc, T_calc, R_norm, T_norm


def test_index_tlu_live_payload_normalized_matches_package_convention():
    """Live TLU : T_plot/R_plot = T/T_sub et R_rel quand use_normalized (aligné _package_results)."""
    wls = np.linspace(400.0, 800.0, 50, dtype=np.float64)
    n_sub = get_n_substrate_array_by_id(SUBSTRATES["N-BK7"]["id"], wls)
    df = pd.DataFrame(
        {
            "lambda": wls,
            "T": np.full(wls.shape, 0.5),
            "R": np.full(wls.shape, 0.05),
        }
    )
    cfg = OptimizationConfig(
        target_data=df,
        data_type=DataType.BOTH,
        substrate="N-BK7",
        thickness_min=10.0,
        thickness_max=500.0,
        lambda_min=400.0,
        lambda_max=800.0,
        use_normalized=True,
    )
    mock_self = MagicMock()
    mock_self._index_tlu_live_ctx = {"config": cfg, "wls": wls, "n_sub": n_sub}
    params = np.array([150.0, 2.5, 200.0, 4.0, 0.5, 0.2, 2.2], dtype=np.float64)
    payload = CertusIndexApp._index_tlu_live_payload_from_params(mock_self, params)
    assert payload is not None
    _, _, R_norm_exp, T_norm_exp = _tlu_reference_rt_norm(wls, n_sub, params)
    np.testing.assert_allclose(payload["T_calc"], T_norm_exp, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(payload["R_calc"], R_norm_exp, rtol=1e-10, atol=1e-12)


def test_index_tlu_live_payload_raw_when_not_normalized():
    """Sans normalisation, le live doit tracer T et R physiques."""
    wls = np.linspace(400.0, 800.0, 50, dtype=np.float64)
    n_sub = get_n_substrate_array_by_id(SUBSTRATES["N-BK7"]["id"], wls)
    df = pd.DataFrame(
        {
            "lambda": wls,
            "T": np.full(wls.shape, 0.5),
            "R": np.full(wls.shape, 0.05),
        }
    )
    cfg = OptimizationConfig(
        target_data=df,
        data_type=DataType.BOTH,
        substrate="N-BK7",
        thickness_min=10.0,
        thickness_max=500.0,
        lambda_min=400.0,
        lambda_max=800.0,
        use_normalized=False,
    )
    mock_self = MagicMock()
    mock_self._index_tlu_live_ctx = {"config": cfg, "wls": wls, "n_sub": n_sub}
    params = np.array([150.0, 2.5, 200.0, 4.0, 0.5, 0.2, 2.2], dtype=np.float64)
    payload = CertusIndexApp._index_tlu_live_payload_from_params(mock_self, params)
    R_raw, T_raw, _, _ = _tlu_reference_rt_norm(wls, n_sub, params)
    np.testing.assert_allclose(payload["T_calc"], T_raw, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(payload["R_calc"], R_raw, rtol=1e-10, atol=1e-12)
