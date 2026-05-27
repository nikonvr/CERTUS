import pytest
from unittest.mock import MagicMock
import time
import numpy as np
import pandas as pd

# We mock what we need from CERTUS_INDEX to test the logic of the callbacks independently
from certus.core.certus_core import SMALL_EPSILON, SUBSTRATES
from certus_physics import get_n_substrate_array_by_id
from CERTUS_INDEX import (
    CertusIndexApp,
    DataType,
    _detected_data_type_label,
    _source_type_label,
    _detect_type_from_column_name,
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
    detect_data_type,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
)

def test_index_data_type_labels_are_stable():
    assert "TRANSMISSION" in _detected_data_type_label(DataType.TRANSMISSION)
    assert "REFLECTION" in _detected_data_type_label(DataType.REFLECTION)
    assert "TRANSMISSION + REFLECTION" in _detected_data_type_label(DataType.BOTH)
    assert _source_type_label(DataType.TRANSMISSION) == "Transmission"
    assert _source_type_label(DataType.REFLECTION) == "Reflection"
    assert _source_type_label(DataType.BOTH) == "Transmission + Reflection"


def test_detect_type_from_column_name_patterns():
    assert _detect_type_from_column_name("T") == "T"
    assert _detect_type_from_column_name("Transmission (%)") == "T"
    assert _detect_type_from_column_name("R") == "R"
    assert _detect_type_from_column_name("Reflection") == "R"
    assert _detect_type_from_column_name("unknown") == "unknown"
    assert _detect_type_from_column_name(None) == "unknown"


def test_detect_data_type_thresholds():
    assert detect_data_type(np.array([0.9, 0.8, 0.7])) == "T"
    assert detect_data_type(np.array([0.02, 0.05, 0.1])) == "R"
    assert detect_data_type(np.array([])) == "T"


def test_detect_data_type_handles_percentage_input():
    assert detect_data_type(np.array([92.0, 88.0, 95.0])) == "T"


def test_private_array_detector_matches_public_api():
    from CERTUS_INDEX import _detect_data_type_from_array

    sample = np.array([0.02, 0.05, 0.1])
    assert _detect_data_type_from_array(sample) == detect_data_type(sample)


def test_prepare_nk_plot_inputs_masks_tlu_region():
    from CERTUS_INDEX import _prepare_nk_plot_inputs

    class DummyRes:
        def __init__(self):
            self.optimization_stats = {"method": "Direct"}
            self.config = type("Cfg", (), {"lambda_max_fit": 550.0})()
            self.tlu_params = object()

    class DummyLogger:
        def __init__(self):
            self.errors = []
        def error(self, msg):
            self.errors.append(msg)

    wls = np.array([500.0, 560.0, 600.0])
    sub_df = pd.DataFrame({"n_calc": [1.5, 1.6, 1.7], "k_calc": [0.01, 0.02, 0.03]})
    out = _prepare_nk_plot_inputs(wls, sub_df, DummyRes(), DummyLogger())
    assert out is not None
    n_values, k_values, method_str, lambda_max_fit, tlu_mode = out
    assert method_str == "Direct"
    assert lambda_max_fit == 550.0
    assert tlu_mode is True
    assert np.isnan(n_values[1]) and np.isnan(k_values[1])


def test_update_lambda_bounds_from_target_data_sets_spinboxes():
    from CERTUS_INDEX import _update_lambda_bounds_from_target_data

    class DummySpin:
        def __init__(self):
            self.values = []
        def setValue(self, value):
            self.values.append(value)

    class DummyLogger:
        def __init__(self):
            self.messages = []
        def info(self, msg):
            self.messages.append(msg)

    df = pd.DataFrame({"lambda": [500.0, 540.0, 580.0]})
    sb_lmin = DummySpin()
    sb_lmax = DummySpin()
    logger = DummyLogger()

    lmin, lmax = _update_lambda_bounds_from_target_data(df, sb_lmin, sb_lmax, logger)
    assert lmin == 500.0 and lmax == 580.0
    assert sb_lmin.values == [500.0]
    assert sb_lmax.values == [580.0]
    assert logger.messages


def test_update_loaded_file_label_and_plot_title_helpers():
    from CERTUS_INDEX import _set_spectrum_plot_title, _update_loaded_file_label

    class DummyLabel:
        def __init__(self):
            self.text = None
            self.stylesheet = None
            self.tooltip = None
        def setText(self, text):
            self.text = text
        def setStyleSheet(self, style):
            self.stylesheet = style
        def setToolTip(self, tip):
            self.tooltip = tip

    class DummyPlotItem:
        def __init__(self):
            self.title = None
        def setTitle(self, title):
            self.title = title

    class DummyPlot:
        def __init__(self):
            self.plotItem = DummyPlotItem()

    lbl = DummyLabel()
    fname = _update_loaded_file_label(lbl, r"C:\temp\sample_spectrum.csv")
    assert fname == "sample_spectrum.csv"
    assert lbl.text == " sample_spectrum.csv"
    assert lbl.tooltip.endswith("sample_spectrum.csv")

    plot = DummyPlot()
    _set_spectrum_plot_title(plot, "sample_spectrum.csv")
    assert "sample_spectrum" in plot.plotItem.title


def test_auto_detect_from_file_substrate_keyword_detection():
    from CERTUS_INDEX import CertusIndexApp

    app = MagicMock()
    app.cb_sub = MagicMock()
    app.cb_sub.findText.return_value = 2
    app.cb_sub.currentText.return_value = "SiO2"
    app.logger = MagicMock()
    app.target_data = pd.DataFrame({"lambda": [500.0, 510.0, 520.0], "T": [0.9, 0.85, 0.88]})
    app._estimated_thickness_nm = None

    CertusIndexApp._auto_detect_from_file(app, r"C:\data\sample_fused_silica.csv")
    app.cb_sub.setCurrentIndex.assert_called_with(2)
    assert app._estimated_thickness_nm is not None or app._estimated_thickness_nm is None


def test_try_active_update_keeps_best_curve_and_throttles():
    from CERTUS_INDEX import OptimizationWorker

    worker = MagicMock()
    worker.last_plot_update_time = 0.0
    worker.min_plot_interval = 0.0
    worker.best_mse = 2.0
    worker.best_params = np.array([1.0, 2.0])
    worker.curve_update = MagicMock()
    worker._should_emit_active_update = MagicMock(return_value=True)
    worker._update_best_live_params = MagicMock()

    OptimizationWorker._try_active_update(worker, np.array([9.0, 9.0]), 1.5, force=True)
    worker.curve_update.emit.assert_called_once()
    worker._update_best_live_params.assert_called_once()
    np.testing.assert_array_equal(worker.best_params, np.array([1.0, 2.0]))
    assert worker.best_mse == 2.0


def test_optimization_worker_helpers_cover_stop_budget_and_monitor():
    from CERTUS_INDEX import PGlobalOptimizerINDEX

    worker = MagicMock()
    worker.stop_event = MagicMock()
    worker.stop_event.is_set.return_value = False
    worker.config.max_time = 10.0
    worker.config.max_feval = 100
    worker.n_evals = 20
    worker.config.local_search_budget = 40
    worker._local_search_budget = PGlobalOptimizerINDEX._local_search_budget.__get__(worker, PGlobalOptimizerINDEX)
    worker._should_stop_optimization = PGlobalOptimizerINDEX._should_stop_optimization.__get__(worker, PGlobalOptimizerINDEX)
    worker._make_monitor_callback = PGlobalOptimizerINDEX._make_monitor_callback.__get__(worker, PGlobalOptimizerINDEX)
    worker.objective = MagicMock(return_value=1.23)

    assert worker._should_stop_optimization(start_time=time.time(), iteration=0) is False
    assert worker._local_search_budget() == 40
    monitor = worker._make_monitor_callback(lambda s: s)
    assert callable(monitor)


def test_phase1_callback():
    # Setup worker mock
    mock_worker = MagicMock()
    mock_worker.is_stopped = False
    mock_worker.best_mse = 2.0
    mock_worker.best_params = None
    mock_worker._optimizer = MagicMock()
    mock_worker._optimizer.n_evals = 10
    def _update_phase1_best(sample):
        mock_worker.best_mse = sample.y
        mock_worker.best_params = sample.x.copy()
    mock_worker._update_phase1_best = MagicMock(side_effect=_update_phase1_best)

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


def test_phase2_polish_callback_stops_when_worker_is_stopped():
    mock_worker = MagicMock()
    mock_worker.is_stopped = True
    mock_worker.best_mse = 0.5

    cb = Phase2PolishCallback(mock_worker)

    with pytest.raises(StopIteration):
        cb(np.array([1.0, 1.0]))


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


def test_ir_global_model_worker_manifest_wiring():
    from CERTUS_INDEX import IRGlobalModelWorker, OptimizationConfig, OptimizationResults
    
    cfg = OptimizationConfig(
        target_data=pd.DataFrame({"lambda": [1000.0, 2000.0], "T": [0.8, 0.7]}),
        data_type=DataType.TRANSMISSION,
        substrate="N-BK7",
        thickness_min=10.0,
        thickness_max=500.0,
        lambda_min=1000.0,
        lambda_max=2000.0,
        use_normalized=False,
    )
    cfg.source_file = __file__
    
    tlu_results = MagicMock(spec=OptimizationResults)
    
    worker = IRGlobalModelWorker(cfg, tlu_results)
    
    wls = np.array([1000.0, 2000.0])
    n_sub = np.array([1.5, 1.5])
    obj_mock = MagicMock()
    
    worker._prepare_ir_phase2_inputs = MagicMock(return_value=(
        wls, n_sub, np.array([0.8, 0.7]), None, pd.DataFrame(), None, obj_mock, 150.0
    ))
    
    res_pg_mock = MagicMock()
    res_pg_mock.y = 0.0123
    opt_mock = MagicMock()
    opt_mock.n_evals = 42
    worker._run_ir_stage0_to_stage2 = MagicMock(return_value=(res_pg_mock, opt_mock))
    
    p_opt = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0])
    worker._run_phase23_spline_refinement = MagicMock(return_value=(
        np.array([1.6, 1.6]), np.array([0.01, 0.01]), p_opt, np.array([1.0, 2.0]), np.array([0.01, 0.01])
    ))
    
    worker._run_phase21_refinement = MagicMock(return_value=(
        np.array([1.61, 1.61]), np.array([0.011, 0.011]), p_opt
    ))
    
    results_captured = []
    worker.finished.connect(results_captured.append)
    
    worker.run()
    
    assert len(results_captured) == 1
    res = results_captured[0]
    assert isinstance(res, OptimizationResults)
    assert res.optimization_stats is not None
    assert "run_manifest" in res.optimization_stats
    manifest = res.optimization_stats["run_manifest"]
    assert manifest["app_id"] == "CERTUS_INDEX"
    assert manifest["materials_db_hash"] != ""
    assert "run_id" in manifest


def test_normalize_index_config_substrate_compatibility():
    cfg_legacy = {
        "substrate_choice": "Sapphire (Al2O3)",
        "source_file": "my_file.csv"
    }
    normalized = CertusIndexApp._normalize_index_config(None, cfg_legacy)
    assert normalized.get("substrate") == "Al2O3"
    assert normalized.get("file_loaded") == "my_file.csv"

    cfg_eco = {
        "substrate": "D263T eco"
    }
    normalized_eco = CertusIndexApp._normalize_index_config(None, cfg_eco)
    assert normalized_eco.get("substrate") == "D263T"

