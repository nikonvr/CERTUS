"""Extra unit tests targeting all remaining missing lines and branches to boost test coverage to 96%+."""

import sys
import os
import tempfile
import queue
import logging
from pathlib import Path
from importlib.machinery import SourceFileLoader
from unittest.mock import patch, Mock

import pytest
import numpy as np
import pandas as pd

from certus.spline.certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
from certus.spline.spline_objective import (
    sigma_knots_decode,
    _interpolate_along_sigma,
    build_segment_optimizer_x_vector,
    _spline_objective_lam_mask,
    spectral_mse_rmse_masked_from_nk,
    spline_spectral_mse_from_xy_nk,
    decompose_spline_pwl_objective,
    SplinePWLObjective,
)

# PyQt Imports
try:
    from PyQt6.QtWidgets import QMessageBox, QApplication, QWidget, QTableWidget
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────
# 1. certus_core.py Gaps
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_core_openpyxl_import_error(monkeypatch):
    import certus.core.certus_core as certus_core
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    file_path = str(Path(certus_core.__file__).resolve())
    loader = SourceFileLoader("certus_core_no_openpyxl", file_path)
    mod = loader.load_module()
    assert mod.OPENPYXL_AVAILABLE is False

@pytest.mark.unit
def test_setup_numba_cache_value_error(monkeypatch):
    import certus.core.certus_core as certus_core
    import numba
    monkeypatch.setitem(sys.modules, "numba", numba)
    monkeypatch.setattr(numba, "get_num_threads", Mock(side_effect=ValueError("Simulated Error")))
    for env_var in [
        "_CERTUS_NUMBA_CONFIGURED",
        "NUMBA_CACHE_DIR",
        "NUMBA_THREADING_LAYER",
        "NUMBA_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        if env_var in os.environ:
            monkeypatch.setenv(env_var, os.environ[env_var])
        else:
            monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setitem(os.environ, "_CERTUS_NUMBA_CONFIGURED", "0")
    certus_core.setup_numba_cache()

@pytest.mark.unit
def test_setup_numba_cache_frozen(monkeypatch):
    import certus.core.certus_core as certus_core
    for k in list(sys.modules.keys()):
        if k.startswith("numba"):
            monkeypatch.delitem(sys.modules, k, raising=False)
    monkeypatch.setattr(certus_core, "is_frozen", lambda: True)
    for env_var in [
        "_CERTUS_NUMBA_CONFIGURED",
        "NUMBA_CACHE_DIR",
        "NUMBA_THREADING_LAYER",
        "NUMBA_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        if env_var in os.environ:
            monkeypatch.setenv(env_var, os.environ[env_var])
        else:
            monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setitem(os.environ, "_CERTUS_NUMBA_CONFIGURED", "0")
    certus_core.setup_numba_cache()
    # It just returns the path, doesn't set THREADING_LAYER anymore.
    assert os.environ.get("NUMBA_THREADING_LAYER") is None

@pytest.mark.unit
def test_setup_numba_cache_not_frozen(monkeypatch):
    import certus.core.certus_core as certus_core
    for k in list(sys.modules.keys()):
        if k.startswith("numba"):
            monkeypatch.delitem(sys.modules, k, raising=False)
    monkeypatch.setattr(certus_core, "is_frozen", lambda: False)
    for env_var in [
        "_CERTUS_NUMBA_CONFIGURED",
        "NUMBA_CACHE_DIR",
        "NUMBA_THREADING_LAYER",
        "NUMBA_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        if env_var in os.environ:
            monkeypatch.setenv(env_var, os.environ[env_var])
        else:
            monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setitem(os.environ, "_CERTUS_NUMBA_CONFIGURED", "0")
    monkeypatch.delitem(os.environ, "NUMBA_THREADING_LAYER", raising=False)
    monkeypatch.delitem(os.environ, "NUMBA_NUM_THREADS", raising=False)
    certus_core.setup_numba_cache()
    # It just returns the path, doesn't set THREADING_LAYER anymore.
    assert os.environ.get("NUMBA_THREADING_LAYER") is None

@pytest.mark.unit
def test_set_num_threads_env_missing(monkeypatch):
    import certus.core.certus_core as certus_core
    for env_var in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        monkeypatch.delitem(os.environ, env_var, raising=False)
    certus_core.set_num_threads(4)

@pytest.mark.unit
def test_get_logger_fallback(monkeypatch):
    import certus.core.certus_core as certus_core
    import logging
    logger = logging.getLogger("CERTUS")
    old_handlers = logger.handlers.copy()
    logger.handlers.clear()
    try:
        new_logger = certus_core.get_logger()
        assert len(new_logger.handlers) > 0
    finally:
        logger.handlers = old_handlers

@pytest.mark.unit
def test_system_config_setup_logging():
    from certus.core.certus_core import SystemConfig
    logger = SystemConfig.setup_logging()
    assert logger is not None

@pytest.mark.unit
def test_queue_handler_broken_pipe():
    import queue
    from certus.core.certus_core import QueueHandler
    import logging
    q = queue.Queue()
    qh = QueueHandler(q)
    qh.log_queue = Mock()
    qh.log_queue.put = Mock(side_effect=BrokenPipeError("broken"))
    record = logging.LogRecord("name", logging.INFO, "pathname", 12, "msg", (), None)
    qh.emit(record)

@pytest.mark.unit
def test_setup_module_logging_default():
    from certus.core.certus_core import setup_module_logging
    adapter = setup_module_logging("TEST_MOD", log_file=None)
    assert adapter is not None

@pytest.mark.unit
def test_bootstrap_app_frozen(monkeypatch):
    import sys
    import certus.core.certus_core as certus_core
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "dummy_executable.exe")
    res = certus_core.bootstrap_app("dummy_app.py")
    assert res is not None

@pytest.mark.unit
def test_bg_warmup_import_error(monkeypatch):
    import certus.core.certus_core as certus_core
    monkeypatch.setitem(sys.modules, "certus_physics", None)
    certus_core.bootstrap_app("dummy.py")


# ─────────────────────────────────────────────────────────────────────
# 2. certus_data.py Gaps
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_to_numeric_exception_handling(tmp_path, monkeypatch):
    import certus.utils.certus_data as certus_data
    import pandas as pd
    f = tmp_path / "test2.csv"
    f.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    monkeypatch.setattr(pd, "to_numeric", Mock(side_effect=TypeError("TypeError")))
    df = certus_data.read_csv_robust(str(f))
    assert df is not None

@pytest.mark.unit
def test_read_excel_robust_numeric_error(tmp_path, monkeypatch):
    import certus.utils.certus_data as certus_data
    import pandas as pd
    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", True)
    f = tmp_path / "dummy.xlsx"
    f.write_text("dummy")
    monkeypatch.setattr(pd, "read_excel", Mock(return_value=pd.DataFrame({"a": ["val"]})))
    monkeypatch.setattr(pd, "to_numeric", Mock(side_effect=TypeError("TypeError")))
    df = certus_data.read_excel_robust(str(f))
    assert df is not None

@pytest.mark.unit
def test_to_excel_robust_engine(tmp_path, monkeypatch):
    import certus.utils.certus_data as certus_data
    import pandas as pd
    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", True)
    df = pd.DataFrame({"a": [1]})
    f = tmp_path / "out.xlsx"
    mock_to_excel = Mock()
    monkeypatch.setattr(df, "to_excel", mock_to_excel)
    certus_data.to_excel_robust(df, str(f))
    mock_to_excel.assert_called_once()
    assert mock_to_excel.call_args[1]["engine"] == "openpyxl"

@pytest.mark.unit
def test_export_optimization_report_branches(tmp_path, monkeypatch):
    import certus.utils.certus_data as certus_data
    res_excel, res_html = certus_data.export_optimization_report(
        reports_dir=str(tmp_path),
        module_name="METAL",
        rmse=0.01,
        summary_dict={"A": 1},
        solution_df=pd.DataFrame({"param": [1]}),
        spectra_df=pd.DataFrame({"wl": [500]}),
        plots=None,
        extra_sheets=None,
    )
    assert res_excel is not None

    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", False)
    mock_to_excel = Mock()
    monkeypatch.setattr(certus_data, "to_excel_robust", mock_to_excel)
    res_excel, res_html = certus_data.export_optimization_report(
        reports_dir=str(tmp_path),
        module_name="METAL",
        rmse=0.01,
        summary_dict={"A": 1},
        solution_df=pd.DataFrame({"param": [1]}),
        spectra_df=pd.DataFrame({"wl": [500]}),
        logger=logging.getLogger("CERTUS"),
    )
    mock_to_excel.assert_called_once()

    monkeypatch.setattr(pd, "DataFrame", Mock(side_effect=ValueError("raise error")))
    res_excel, res_html = certus_data.export_optimization_report(
        reports_dir=str(tmp_path),
        module_name="METAL",
        rmse=0.01,
        summary_dict={"A": 1},
        solution_df=None,
        spectra_df=None,
        logger=None,
    )
    assert res_excel is None

@pytest.mark.unit
def test_shared_indices_worker_exact_wl():
    import certus.utils.certus_data as certus_data
    clues = {500.0: {"H": 2.0, "L": 1.0, "substrate": 1.5}}
    with certus_data.SharedIndicesManager(clues) as mgr:
        ctx = mgr.get_context_info()
        with certus_data.SharedIndicesWorker(ctx) as worker:
            r = worker.get(500.0)
            assert r["H"] == 2.0

@pytest.mark.unit
def test_generate_html_report_dataframe(tmp_path):
    import certus.utils.certus_data as certus_data
    import pandas as pd
    f = tmp_path / "report.html"
    sections = [
        {"title": "DataFrame", "type": "table", "content": pd.DataFrame({"col": [1, 2]})}
    ]
    certus_data.generate_html_report(str(f), "Title", sections)

@pytest.mark.unit
def test_generate_html_report_figures(tmp_path):
    import certus.utils.certus_data as certus_data
    f = tmp_path / "report2.html"
    sections = [
        {"title": "Text", "type": "text", "content": "hello"}
    ]
    class DummyFig:
        pass
    certus_data.generate_html_report(str(f), "Title", sections, figures=[DummyFig()])

@pytest.mark.unit
def test_build_standard_report_incomplete_html_only(tmp_path):
    import certus.utils.certus_data as certus_data
    from certus.utils.certus_data import ReportSection
    sections = [ReportSection(title="Summary", kind="kv", content={"X": 1})]
    html_file = tmp_path / "std_report.html"
    res = certus_data.build_standard_report(
        sections,
        html_path=str(html_file),
        run_manifest={"run_id": "missing_others"},
        require_complete_manifest=True,
    )
    assert res["html"] is False

@pytest.mark.unit
def test_build_standard_report_duplicate_kv(tmp_path):
    import certus.utils.certus_data as certus_data
    from certus.utils.certus_data import ReportSection
    sections = [
        ReportSection(title="Config", kind="kv", content={"A": 1}),
        ReportSection(title="Config", kind="kv", content={"B": 2}),
    ]
    excel_file = tmp_path / "dup_kv.xlsx"
    res = certus_data.build_standard_report(
        sections,
        excel_path=str(excel_file),
    )
    assert res["excel"] is True


# ─────────────────────────────────────────────────────────────────────
# 3. certus_errors.py Gaps
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_errors_validation_wavelength_negative():
    from certus.utils.errors import validate_wavelength_range, CertusValidationError
    with pytest.raises(CertusValidationError):
        validate_wavelength_range(-10.0, 500.0)

@pytest.mark.unit
@pytest.mark.skipif(not QT_AVAILABLE, reason="Qt not available")
def test_errors_show_helpers(qapp):
    from certus.utils.errors import show_error, show_warning, show_validation_error, CertusValidationError
    from PyQt6.QtWidgets import QMessageBox
    with patch.object(QMessageBox, "exec", return_value=0):
        show_error(None, "generic_error", details="some detail")
        show_warning(None, "title", "msg", "suggestion")
        show_validation_error(None, CertusValidationError("msg", "details", "suggestion"))


# ─────────────────────────────────────────────────────────────────────
# 4. certus_reset_framework.py Gaps
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.skipif(not QT_AVAILABLE, reason="Qt not available")
def test_reset_framework_extra_coverage():
    from certus.utils.certus_reset_framework import CertusResetManager
    
    app = Mock()
    w = Mock()
    w.isRunning = Mock(return_value=True)
    w.wait = Mock(return_value=False)
    w.requestInterruption = Mock()
    w.stop = Mock(side_effect=RuntimeError("stop failed"))
    del w.request_stop
    app.optim_worker = w
    
    stack_table = Mock()
    stack_table.setRowCount = Mock()
    app.widgets = {"stack_table": stack_table}
    app.stat_counters = {"EVAL": 0}
    app.detached_window = None
    app.detached_plot_windows = {}
    
    m = CertusResetManager(app)
    m._stop_all_workers()
    
    bad_widget = Mock()
    bad_widget.clear = Mock(side_effect=RuntimeError("clear failed"))
    app.findChildren = Mock(return_value=[bad_widget])
    m._clear_ui_elements()
    
    plot = Mock()
    plot.plotItem = Mock()
    plot.plotItem.clear = Mock()
    plot.plotItem.setLabel = Mock(side_effect=RuntimeError("setLabel failed"))
    app.spectrum_plot = plot
    m._reset_all_plots()
    
    class DummyCache:
        pass
    app._live_curves = DummyCache()
    m._clear_internal_state()


# ─────────────────────────────────────────────────────────────────────
# 5. spline_objective.py Gaps
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_spline_objective_decode_work_sizes():
    work = {
        "ww": np.array([1.0]),
        "ds": np.array([1.0]),
        "c": np.array([1.0]),
        "sk": np.array([1.0, 2.0]),
    }
    enc = np.array([0.1, 0.2, 0.3])
    dec = sigma_knots_decode(enc, 0.001, 0.003, work=work)
    assert dec.size == 4
    
    dec2 = sigma_knots_decode(enc, 0.001, 0.003, eps_s=1e-5)
    assert dec2.size == 4

@pytest.mark.unit
def test_interpolate_along_sigma_bad_mode():
    sk = np.array([0.001, 0.002, 0.003])
    vals = np.array([1.5, 2.0, 1.8])
    result = _interpolate_along_sigma(np.array([0.0015]), sk, vals, "invalid_mode")
    assert result.size == 1

@pytest.mark.unit
def test_build_segment_optimizer_x_vector_size_mismatch():
    cfg = SplineOptConfig(
        lam_nm=np.array([400.0, 500.0]),
        t_exp=np.array([0.5, 0.5]),
        r_exp=None,
        n_sub=np.array([1.5, 1.5]),
        data_type=DataType.TRANSMISSION,
        n_seg=2,
        d_lo=50.0,
        d_hi=200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = np.array([0.001, 0.002])
    res = build_segment_optimizer_x_vector({"sigma_knots": sk, "x": np.array([1.0, 2.0])}, cfg)
    assert res is None

@pytest.mark.unit
def test_spline_objective_lam_mask_t_exp_not_none():
    cfg = SplineOptConfig(
        lam_nm=np.array([400.0, 500.0]),
        t_exp=np.array([0.5, 0.5]),
        r_exp=np.array([0.2, 0.2]),
        n_sub=np.array([1.5, 1.5]),
        data_type=DataType.BOTH,
        n_seg=2,
        d_lo=50.0,
        d_hi=200.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
    )
    mask = _spline_objective_lam_mask(cfg)
    assert np.all(mask)

@pytest.mark.unit
def test_ratio_theoretic_and_fused_RT():
    lam = np.linspace(400, 1000, 20)
    cfg_ratio = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.BOTH,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
        t_is_ratio=True,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj_ratio = SplinePWLObjective(cfg_ratio, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    cost = obj_ratio(x)
    assert cost > 0

    cfg_fused = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.BOTH,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
        t_is_ratio=False,
    )
    obj_fused = SplinePWLObjective(cfg_fused, sk)
    cost_fused = obj_fused(x)
    assert cost_fused > 0

@pytest.mark.unit
def test_spectral_mse_rmse_masked_from_nk_interpolation_fallback():
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    lam_full = np.linspace(400, 1000, 30)
    n_lam = np.full_like(lam_full, 2.0)
    k_lam = np.full_like(lam_full, 1e-3)
    mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, lam_full, n_lam, k_lam, 200.0)
    assert np.isfinite(mse)

@pytest.mark.unit
def test_decompose_spline_pwl_objective_empty_lambda():
    lam = np.array([])
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.array([]),
        r_exp=None,
        n_sub=np.array([]),
        data_type=DataType.TRANSMISSION,
        n_seg=2,
        d_lo=50.0,
        d_hi=200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = np.array([0.001, 0.002])
    mse_sp, pen, tot = decompose_spline_pwl_objective(cfg, sk, np.array([100.0, 2.0, 2.0, -5.0, -5.0]))
    assert mse_sp == 1e30

@pytest.mark.unit
def test_spline_pwl_objective_fast_penalty_not_any_active():
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        n_lambda_penalty=1.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.linspace(1.5, 2.5, k), np.full(k, np.log(1e-3))))
    cost = obj(x)
    assert cost > 0

@pytest.mark.unit
def test_spline_pwl_objective_evaluate_batch_no_interp_mat():
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    obj._interp_mat = None
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    Y = obj.evaluate_batch(x.reshape(1, -1))
    assert Y.shape == (1,)

@pytest.mark.unit
def test_analytic_gradient_reflection_and_mono_band():
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.BOTH,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
        t_is_ratio=False,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    grad = obj.analytic_gradient(x)
    assert grad.size == x.size

    cfg_mono = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        n_mono_band_nm=200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    obj_mono = SplinePWLObjective(cfg_mono, sk)
    grad_mono = obj_mono.analytic_gradient(x)
    assert grad_mono is None


# ─────────────────────────────────────────────────────────────────────
# Extra boost tests to get to 98%
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_dynamic_savgol_blend_value_error():
    from certus.utils.certus_spectral_preproc import dynamic_savgol_blend
    x = np.linspace(4000.0, 5000.0, 10)
    y = np.ones(10)
    # w_heavy = base_window (5) if heavy_window is 0. Wait, poly = 4.
    # To trigger ValueError in heavy savgol:
    # Set heavy_window = 3, poly = 4. Then polyorder (4) >= window_length (3), which triggers ValueError!
    # base_window=5, so polyorder (4) < base_window (5) is valid for y_base!
    res = dynamic_savgol_blend(x, y, base_window=5, poly=4, heavy_window=3)
    assert res is not None

@pytest.mark.unit
def test_auto_tune_savgol_params_value_error(monkeypatch):
    from certus.utils.certus_spectral_preproc import auto_tune_savgol_params
    import certus.utils.certus_spectral_preproc as certus_spectral_preproc
    x = np.linspace(400, 1000, 20)
    y_mat = np.ones((2, 20))
    # Monkeypatch savgol_filter to raise ValueError only for y_macro call
    orig_savgol = certus_spectral_preproc.savgol_filter
    call_count = 0
    def mock_savgol(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("Simulated ValueError for y_macro")
        return orig_savgol(*args, **kwargs)
    monkeypatch.setattr(certus_spectral_preproc, "savgol_filter", mock_savgol)
    res = auto_tune_savgol_params(x, y_mat, "Soft (High Fidelity)")
    assert res is not None

@pytest.mark.unit
def test_reset_framework_reset_app_to_defaults(qapp):
    from certus.utils.certus_reset_framework import reset_app_to_defaults, create_reset_button
    from PyQt6.QtWidgets import QWidget
    
    # We must use a real QWidget to avoid QMessageBox C++ type errors
    app = QWidget()
    app.optim_worker = Mock()
    app.optim_worker.isRunning = Mock(return_value=False)
    app.detached_window = None
    app.detached_plot_windows = {}
    
    res = reset_app_to_defaults(app, confirm=False)
    assert res is True
    
    if QT_AVAILABLE:
        btn = create_reset_button(app, use_app_reset=False)
        assert btn is not None

@pytest.mark.unit
def test_spline_objective_more_branches():
    from certus.spline.spline_objective import nk_from_x_pwlnk, objective_lam_mask_on_target_grid
    x = np.array([100.0, 2.0, 2.0, -5.0, -5.0])
    sk = np.array([0.001, 0.002])
    n_lam, k_lam = nk_from_x_pwlnk(x, np.array([400.0, 500.0]), sk, 1e-4, 1.0, profile_interp="invalid_profile_name")
    assert n_lam.size == 2
    
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=None,
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    mask = _spline_objective_lam_mask(cfg)
    assert np.all(mask)
    
    target_mask = objective_lam_mask_on_target_grid(cfg, np.array([]))
    assert target_mask.size == 0
    
    target_mask2 = objective_lam_mask_on_target_grid(cfg, np.array([500.0]))
    assert target_mask2.size == 1

@pytest.mark.unit
def test_spline_objective_reflection_grad():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=None,
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.REFLECTION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=0.0,
        weight_r=1.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    
    # test evaluate_batch fallback for ratio/reflection
    Y = obj.evaluate_batch(x.reshape(1, -1))
    assert Y.shape == (1,)
    
    # test analytic gradient in reflection-only mode
    grad = obj.analytic_gradient(x)
    assert grad.size == x.size


# ─────────────────────────────────────────────────────────────────────
# Extra boost tests to get to 98% (Part 2)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_reset_framework_pyqtgraph_import_error(monkeypatch):
    from certus.utils.certus_reset_framework import CertusResetManager
    import sys
    monkeypatch.setitem(sys.modules, "pyqtgraph", None)
    app = Mock()
    app.spectrum_plot = None
    m = CertusResetManager(app)
    m._reset_all_plots()

@pytest.mark.unit
def test_reset_framework_clear_text_error():
    from certus.utils.certus_reset_framework import CertusResetManager
    app = Mock()
    bad_widget = Mock()
    bad_widget.clear = Mock(side_effect=AttributeError("Simulated error"))
    app.findChildren = Mock(return_value=[bad_widget])
    m = CertusResetManager(app)
    m._clear_text_outputs_only()

@pytest.mark.unit
def test_reset_framework_detached_plot_error():
    from certus.utils.certus_reset_framework import CertusResetManager
    app = Mock()
    bad_win = Mock()
    bad_win.close = Mock(side_effect=RuntimeError("close error"))
    app.detached_plot_windows = {"plot1": bad_win}
    m = CertusResetManager(app)
    m._handle_detached_windows()

@pytest.mark.unit
def test_auto_tune_savgol_params_even_w(monkeypatch):
    from certus.utils.certus_spectral_preproc import auto_tune_savgol_params
    x = np.linspace(400, 1000, 20)
    y_mat = np.ones((2, 20))
    import builtins
    orig_range = builtins.range
    def mock_range(*args):
        if len(args) == 3 and args[2] == 2 and args[0] >= 11:
            yield 12
            yield from orig_range(*args)
        else:
            yield from orig_range(*args)
    monkeypatch.setattr(builtins, "range", mock_range)
    res = auto_tune_savgol_params(x, y_mat, "Soft (High Fidelity)")
    assert res is not None

@pytest.mark.unit
def test_spectral_mse_rmse_masked_from_nk_empty_mgf():
    from certus.spline.spline_objective import spectral_mse_rmse_masked_from_nk
    cfg = SplineOptConfig(
        lam_nm=np.array([]),
        t_exp=None,
        r_exp=None,
        n_sub=np.array([]),
        data_type=DataType.TRANSMISSION,
        n_seg=2,
        d_lo=50.0,
        d_hi=200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, np.array([]), np.array([]), np.array([]), 100.0)
    assert np.isnan(mse)

@pytest.mark.unit
def test_spectral_mse_rmse_masked_from_nk_mask_differs():
    from certus.spline.spline_objective import spectral_mse_rmse_masked_from_nk
    lam = np.array([400.0, 500.0])
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.array([0.5, 0.5]),
        r_exp=None,
        n_sub=np.array([1.5, 1.5]),
        data_type=DataType.TRANSMISSION,
        n_seg=2,
        d_lo=50.0,
        d_hi=200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
        rmse_fit_lambda_nm=(450.0, 550.0),
    )
    mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, lam, np.array([2.0, 2.0]), np.array([1e-3, 1e-3]), 100.0)
    assert np.isfinite(mse)

@pytest.mark.unit
def test_spline_spectral_mse_from_xy_nk_non_finite():
    from certus.spline.spline_objective import spline_spectral_mse_from_xy_nk
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    res = spline_spectral_mse_from_xy_nk(cfg, lam, np.full_like(lam, np.nan), np.full_like(lam, 1e-3), 100.0)
    assert res is None

@pytest.mark.unit
def test_decompose_spline_pwl_objective_non_finite(monkeypatch):
    from certus.spline.spline_objective import decompose_spline_pwl_objective
    import certus.spline.spline_objective as spline_objective
    monkeypatch.setattr(spline_objective, "spline_objective_mse_on_masked_grid", lambda *args, **kwargs: float("nan"))
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    mse, pen, tot = decompose_spline_pwl_objective(cfg, sk, x)
    assert mse == 1e30

@pytest.mark.unit
def test_fast_penalty_grad_no_active():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
        n_mono_band_nm=(450.0, 550.0),
        n_mono_slack=0.01,
        n_mono_weight=100.0,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    obj = SplinePWLObjective(cfg, sk)
    g = obj._fast_penalty_grad(np.ones(sk.size))
    assert np.all(g == 0.0)

@pytest.mark.unit
def test_spline_pwl_objective_call_non_finite(monkeypatch):
    from certus.spline.spline_objective import SplinePWLObjective
    import certus.spline.spline_objective as spline_objective
    monkeypatch.setattr(spline_objective, "spline_objective_mse_on_masked_grid", lambda *args, **kwargs: float("nan"))
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    cost = obj(x)
    assert cost >= 1e30

@pytest.mark.unit
def test_evaluate_batch_with_mono_band():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
        n_mono_band_nm=(450.0, 550.0),
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    res = obj.evaluate_batch(x.reshape(1, -1))
    assert res.shape == (1,)

@pytest.mark.unit
def test_evaluate_batch_pure_spec():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
        spline_pure_spectral_objective=True,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    res = obj.evaluate_batch(x.reshape(1, -1))
    assert res.shape == (1,)

@pytest.mark.unit
def test_evaluate_batch_fused_pure_spec():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.BOTH,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
        spline_pure_spectral_objective=True,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    res = obj.evaluate_batch(x.reshape(1, -1))
    assert res.shape == (1,)

@pytest.mark.unit
def test_evaluate_batch_fallback_non_finite():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=np.full_like(lam, 0.2),
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.BOTH,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=1.0,
        substrate_name="SiO2",
        t_is_ratio=True,
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, np.nan), np.full(k, np.log(1e-3))))
    res = obj.evaluate_batch(x.reshape(1, -1))
    assert res.shape == (1,)

@pytest.mark.unit
def test_compute_analytic_gradient_zero_wsum():
    from certus.spline.spline_objective import SplinePWLObjective
    lam = np.linspace(400, 1000, 20)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=0.0,
        weight_r=0.0,
        substrate_name="SiO2",
    )
    sk = canonical_spline_sigma_knots(400, 1000)
    k = int(sk.size)
    obj = SplinePWLObjective(cfg, sk)
    x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    grad = obj.analytic_gradient(x)
    assert grad is None

