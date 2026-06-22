import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from certus.utils.certus_progress_tracker import build_progress_callback, StepState
from certus.ui.certus_base_app import CertusBaseApp
from certus.ui.certus_design_ui import CertusDesignApp

def test_progress_callback_adapter():
    """Verify that build_progress_callback creates an adapter that emits correct snapshots."""
    emitted = []
    
    cb = build_progress_callback(emitted.append, "test_module", "test_phase")
    cb(45, "Running optimization step")
    
    assert len(emitted) == 1
    snapshot = emitted[0]
    assert snapshot.progress_ratio == 0.45
    assert snapshot.message == "Running optimization step"
    assert snapshot.module == "test_module"
    assert snapshot.phase == "test_phase"
    assert snapshot.state == StepState.RUNNING

def test_busy_state_refcounting_and_force_idle():
    """Verify that busy refcounting increments correctly and _force_idle resets it."""
    class DummyApp(CertusBaseApp):
        def __init__(self):
            # Bypass base QMainWindow/mixins init to avoid GUI creation
            self._busy_count = 0
            self._is_busy = False
            self.status_label = MagicMock()
            self.progress_bar = MagicMock()
        
        def _update_busy_ui(self, busy):
            pass

    app = DummyApp()
    
    # 1. Init state
    assert app._busy_count == 0
    assert app._is_busy is False
    
    # 2. Increments
    app._set_busy(True)
    assert app._busy_count == 1
    assert app._is_busy is True
    
    app._set_busy(True)
    assert app._busy_count == 2
    assert app._is_busy is True
    
    # 3. Decrement (still busy)
    app._set_busy(False)
    assert app._busy_count == 1
    assert app._is_busy is True
    
    # 4. Force idle resets state
    app._force_idle()
    assert app._busy_count == 0
    assert app._is_busy is False

def test_smart_pareto_decimation_skip_releasing_busy():
    """Verify that _start_smart_pareto_decimation skips and releases busy state when skipped."""
    mock_ui = MagicMock()
    mock_ui.front_table.rowCount.return_value = 3  # < 4 layers
    mock_ui.ep_current = None
    mock_ui._is_busy = True
    
    # Execute method
    CertusDesignApp._start_smart_pareto_decimation(mock_ui)
    
    # Verify it logged skipped message and released busy state
    mock_ui.log.assert_called_once()
    mock_ui._set_busy.assert_called_once_with(False)

def test_pareto_table_sorting_by_rmse():
    """Verify that _refresh_pareto_table sorts entries by best_rmse descending (best/lowest first)."""
    from certus.ui.certus_design_ui_plot import PlotManager
    
    mock_ui = MagicMock()
    mock_ui.pareto_history = {
        10: {"best_rmse": 0.05, "best_mc": 0.1, "best_fab": 0.1, "catalog": []},
        20: {"best_rmse": 0.01, "best_mc": 0.1, "best_fab": 0.1, "catalog": []},
        15: {"best_rmse": 0.03, "best_mc": 0.1, "best_fab": 0.1, "catalog": []},
    }
    
    inserted_rows = []
    
    def mock_insert_row(row):
        inserted_rows.append(row)
        
    mock_ui.pareto_table.insertRow = mock_insert_row
    
    plot_manager = PlotManager(mock_ui)
    
    # Mock row population to track the order N is inserted
    populated_order = []
    def mock_populate_row(row_index, N, rec):
        populated_order.append(N)
        
    plot_manager._populate_pareto_table_row = mock_populate_row
    
    plot_manager._refresh_pareto_table()
    
    # N=20 (RMSE 0.01) is best, N=15 (RMSE 0.03) is 2nd, N=10 (RMSE 0.05) is 3rd.
    # So populated_order must be [20, 15, 10]
    assert populated_order == [20, 15, 10]

def test_smart_decimation_loads_best_overall_rmse():
    """Verify that _finish_smart_decimation restores the absolute best solution by RMSE."""
    from certus.ui.certus_design_ui_optimization import OptimizationManager
    import numpy as np
    
    mock_ui = MagicMock()
    # Design before decimation had N=27, RMSE=0.0042
    mock_ui.pareto_history = {
        27: {"best_rmse": 0.0042, "ep_rmse": np.array([10.0]*27), "table_rmse": [{"mat": "H", "qw": 1.0}]},
        23: {"best_rmse": 0.0041, "ep_rmse": np.array([10.0]*23), "table_rmse": [{"mat": "L", "qw": 1.0}]},
        15: {"best_rmse": 0.0150, "ep_rmse": np.array([10.0]*15), "table_rmse": [{"mat": "H", "qw": 1.0}]},
    }
    mock_ui.front_table.rowCount.return_value = 15
    
    manager = OptimizationManager(mock_ui)
    
    # We should track if _restore_table_state was called with the best champion's table state
    restored_table_states = []
    manager._restore_table_state = restored_table_states.append
    manager._clear_smart_decimation_state = MagicMock()
    manager._finalize_completed_optimization_workflow = MagicMock()
    
    # Trigger completion
    manager._finish_smart_decimation()
    
    # Should restore the N=23 champion because 0.0041 is the absolute minimum RMSE!
    assert len(restored_table_states) == 1
    assert restored_table_states[0] == [{"mat": "L", "qw": 1.0}]
    assert mock_ui.ep_current.shape == (23,)
    assert mock_ui._workflow_best_rmse == 0.0041

