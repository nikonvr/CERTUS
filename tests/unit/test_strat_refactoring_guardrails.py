import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

# Ensure the workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Force headless Qt for testing if needed
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread
from certus.workers.certus_strat_workers import LiveFeedMonitor
from certus.ui.certus_strat_ui import StrategySpectralPerformanceWindow
from certus.core.certus_strat_core import APP_CONTEXT

# Initialize session-wide QApplication to avoid crashes
_qapp = QApplication.instance() or QApplication([])

def test_live_feed_monitor_thread_affinity_guardrail():
    """Verify that starting LiveFeedMonitor from the wrong thread raises AssertionError."""
    # Create the monitor
    signals = MagicMock()
    monitor = LiveFeedMonitor(
        live_preview_queue=MagicMock(),
        signals=signals,
        p_thick_nominal=[100.0],
        clues_at_wl={}
    )
    
    # Do not call moveToThread, so affinity remains the main GUI thread.
    # Now simulate start() called on a different QThread
    class TestThread(QThread):
        def __init__(self, target):
            super().__init__()
            self.target = target
            self.error = None
        def run(self):
            try:
                self.target.start()
            except AssertionError as e:
                self.error = e

    thread = TestThread(monitor)
    thread.start()
    thread.wait()
    
    assert thread.error is not None
    assert "CERTUS-STRAT-E-THREAD-AFFINITY" in str(thread.error)


def test_strategy_spectral_performance_window_db_assertion_guardrail():
    """Verify that StrategySpectralPerformanceWindow raises AssertionError if database is completely missing."""
    # Ensure APP_CONTEXT does not have the database
    old_db = APP_CONTEXT.get("materials_db")
    if "materials_db" in APP_CONTEXT:
        del APP_CONTEXT["materials_db"]
        
    try:
        strategy_result = {
            "strategy": {"strategy_id": 1},
            "results_per_noise": [{"noise_level": 2.0}]
        }
        opti_results = {
            "p_thick_nominal": [100.0]
        }
        params = {
            "wl_range": [400.0, 600.0],
            "wl_step": 1.0,
            "nH_id": "TiO2",
            "nL_id": "SiO2",
            "nSub_id": "BK7"
            # Note: materials_db_instance and materials_db are omitted
        }
        
        # Instantiate window - constructor internally calls _calculate_and_plot which should assert
        with pytest.raises(AssertionError) as exc_info:
            StrategySpectralPerformanceWindow(
                parent=None,
                strategy_result=strategy_result,
                opti_results=opti_results,
                params=params
            )
            
        assert "CERTUS-STRAT-E-DB-MISSING" in str(exc_info.value)
        
    finally:
        # Restore APP_CONTEXT
        if old_db is not None:
            APP_CONTEXT["materials_db"] = old_db


def test_worker_block_calculation_db_assertion_guardrail():
    """Verify that block calculation raises AssertionError if database is missing."""
    from certus.workers.certus_strat_workers import _finalize_and_export_pipeline_results
    
    # Ensure APP_CONTEXT does not have the database
    old_db = APP_CONTEXT.get("materials_db")
    if "materials_db" in APP_CONTEXT:
        del APP_CONTEXT["materials_db"]
        
    try:
        params = {
            "logger": MagicMock(),
            "wl_range": [400.0, 600.0],
            "wl_step": 1.0,
            "nH_id": "TiO2",
            "nL_id": "SiO2",
            "nSub_id": "BK7",
            "show_plots": True
            # database is omitted
        }
        
        pre_calc_data = {
            "p_thick_nominal": [100.0],
            "clues_at_wl": {},
            "raw_results_thickness": {}
        }
        
        strategy_res = {
            "robustness_score": 0.1,
            "strategy": {
                "strategy_id": 1,
                "n_blocks": 1,
                "blocks": []
            },
            "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.1, "rmse_mean": 0.05, "rmse_std": 0.01, "thicknesses_all": [[100.0]]}]
        }
        accumulated_strategies_results = [strategy_res]
        
        # Invoking the step calculation should assert
        with pytest.raises(AssertionError) as exc_info:
            _finalize_and_export_pipeline_results(
                accumulated_strategies_results=accumulated_strategies_results,
                pre_calc_data=pre_calc_data,
                nominal_res=None,
                params=params,
                signals=MagicMock(),
                timing_logger=None
            )
            
        assert "CERTUS-STRAT-E-DB-MISSING" in str(exc_info.value)
        
    finally:
        # Restore APP_CONTEXT
        if old_db is not None:
            APP_CONTEXT["materials_db"] = old_db


def test_robust_material_database_refactoring_guardrails():
    """Verify that RobustMaterialDatabase standardizes, merges, and queries Excel sheets correctly,
    and falls back to Sellmeier coefficients or Air when appropriate."""
    import pandas as pd
    import numpy as np
    from certus.utils.certus_strat_db import RobustMaterialDatabase

    # 1. Prepare fake Excel sheet data
    # Sheet 1: H800-SiO2 with standard headers
    df_sio2_vis = pd.DataFrame({
        "Wavelength (nm)": [400.0, 500.0, 600.0],
        "n_index": [1.46, 1.45, 1.44],
        "k_extinction": [0.0, 0.0, 0.0]
    })

    # Sheet 2: IR-H800-SiO2 headerless format
    df_sio2_ir = pd.DataFrame([
        [700.0, 1.43, 0.0],
        [800.0, 1.42, 0.0]
    ], columns=[600.0, 1.44, 0.0])  # columns will be floats which triggers is_headerless standardization

    # Sheet 3: H800-Nb2O5 with missing K column (2 columns only)
    df_nb = pd.DataFrame({
        "wave": [400.0, 500.0],
        "refractive n": [2.30, 2.25]
    })

    fake_sheets = {
        "H800-SiO2": df_sio2_vis,
        "IR-H800-SiO2": df_sio2_ir,
        "H800-Nb2O5": df_nb
    }

    # Mock pd.read_excel and Path.exists
    with patch("pandas.read_excel", return_value=fake_sheets), \
         patch("pathlib.Path.exists", return_value=True):

        db = RobustMaterialDatabase("dummy_path.xlsx")

        # Verify sheets loaded
        assert "H800-SiO2" in db.materials
        assert "IR-H800-SiO2" in db.materials
        assert "H800-Nb2O5" in db.materials

        # Test MergedMaterialDict lookup and blending for 'SiO2'
        # SiO2 query matches both "H800-SiO2" and "IR-H800-SiO2"
        sio2_data = db.materials["SiO2"]
        assert sio2_data is not None
        assert np.allclose(sio2_data["wl"], [400.0, 500.0, 600.0, 700.0, 800.0])

        # Test get_refractive_index (direct/blended interpolation)
        idx_500 = db.get_refractive_index("SiO2", 500.0)
        assert idx_500.real == pytest.approx(1.45)

        # Test get_refractive_clues_vectorized
        clues = db.get_refractive_clues_vectorized("SiO2", np.array([400.0, 800.0]))
        assert np.allclose(clues, [1.46 + 0j, 1.42 + 0j])

        # Test Nb alias resolution
        nb_data = db.materials["Nb"]
        assert nb_data is not None
        assert np.allclose(nb_data["wl"], [400.0, 500.0])

        # Test standard Sellmeier fallback (e.g., N-BK7, Sapphire)
        idx_bk7 = db.get_refractive_index("N-BK7", 500.0)
        assert idx_bk7.real > 1.40 and idx_bk7.real < 1.60

        # Un matériau introuvable doit LEVER, pas retomber sur l'air.
        #
        # L'ancienne assertion exigeait `idx_air == 1.0 + 0j`, c'est-à-dire qu'une faute
        # de frappe dans un nom de matériau produise une couche d'indice 1 — optiquement
        # invisible dans l'air. Le calcul se poursuivait alors sur un empilement amputé
        # d'une couche, sans exception ni journal : un résultat faux et silencieux.
        # KeyError appartient à NUMERICAL_FAULT_EXCEPTIONS, donc les appelants STRAT
        # basculent sur leur repli déjà journalisé.
        with pytest.raises(KeyError, match="introuvable"):
            db.get_refractive_index("Air_Nonexistent", 600.0)

        with pytest.raises(KeyError, match="introuvable"):
            db.get_refractive_clues_vectorized("Air_Nonexistent", np.array([500.0]))


def test_successive_halving_execution_guardrail():
    """Verify Successive Halving reduces evaluation candidate pool at each stage (Action 5.5)."""
    from certus.core.certus_strat_robustness import _execute_robustness_tasks

    strategies = [
        {
            "strategy_id": f"s_{i}",
            "n_blocks": 1,
            "blocks": [{"start_layer": 0, "end_layer": 7, "monitoring_wavelength": 550.0}],
        }
        for i in range(20)
    ]
    params = {"enable_successive_halving": True}
    logger = MagicMock()

    wl_arr = np.array([550.0], dtype=np.float64)
    nH_arr = np.array([2.35], dtype=np.float64)
    nL_arr = np.array([1.48], dtype=np.float64)
    nSub_arr = np.array([1.52], dtype=np.float64)
    T_nom = np.array([0.9], dtype=np.float64)
    p_thick_nominal = [100.0] * 8
    clues = {"nH": 2.35, "nL": 1.48, "nSub": 1.52}

    res = _execute_robustness_tasks(
        all_strategies=strategies,
        noise_levels=[0.001],
        num_runs=40,
        p_thick_nominal=p_thick_nominal,
        clues_at_wl=clues,
        params_safe=params,
        wl_arr=wl_arr,
        nH_arr=nH_arr,
        nL_arr=nL_arr,
        nSub_arr=nSub_arr,
        T_nom=T_nom,
        full_dyn_grid={},
        params=params,
        logger=logger,
    )
    assert len(res) <= 20
    logger_calls = [call.args[0] for call in logger.info.call_args_list if call.args]
    assert any("[HALVING] Successive Halving enabled" in msg for msg in logger_calls)


