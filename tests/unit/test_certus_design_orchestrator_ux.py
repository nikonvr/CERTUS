"""Unit tests for the DesignOrchestrator UX/UI workflows."""

import pytest
from unittest.mock import MagicMock, patch

from certus.core.certus_design_orchestrator import DesignOrchestrator


@pytest.mark.unit
def test_design_orchestrator_shows_guided_error_on_optimization_failure() -> None:
    """Verifies that an optimization failure triggers a guided QMessageBox warning (UX-3)."""
    # 1. Mock the UI object that the orchestrator expects
    mock_ui = MagicMock()
    orchestrator = DesignOrchestrator(mock_ui)

    # 2. Simulate a failure payload from the OptimWorker
    payload = {
        "ok": False,
        "error": "Target thickness cannot be reached."
    }

    # 3. Patch QMessageBox to prevent actual popup during tests
    with patch("certus.core.certus_design_orchestrator.QMessageBox.warning") as mock_warning:
        orchestrator._on_optim_done(payload)

        # 4. Verify that the user is guided with a popup rather than just a console log
        mock_warning.assert_called_once()
        
        args, kwargs = mock_warning.call_args
        
        assert args[0] == mock_ui  # Parent should be the UI
        assert args[1] == "Optimization Failed"  # Expected title
        
        # The body should explain the issue and contain the specific error
        assert "Target thickness cannot be reached." in args[2]

def test_design_orchestrator_needle_state():
    """Verify that DesignOrchestrator tracks _is_in_needle_cycle correctly (Architecture-5)."""
    mock_ui = MagicMock()
    orchestrator = DesignOrchestrator(ui_instance=mock_ui)
    
    # Init state
    assert orchestrator._target_layer_count is None
    assert orchestrator._is_in_needle_cycle() is False
    
    # Assign target count
    orchestrator._target_layer_count = 10
    assert orchestrator._target_layer_count == 10
    
    # Enter needle cycle 1
    orchestrator._needle_cycle_step = 1
    assert orchestrator._is_in_needle_cycle() is True
    
    # Exit needle cycle
    orchestrator._needle_cycle_step = 4
    assert orchestrator._is_in_needle_cycle() is False


def test_reset_run_optim_workflow_state() -> None:
    """Verifies that _reset_run_optim_workflow_state cleans up workflow states (AttributeError fix)."""
    from certus.ui.certus_design_ui_core import CoreManager
    
    # Mock self.ui
    mock_ui = MagicMock()
    mock_ui.front_table = MagicMock()
    mock_ui.front_table.rowCount.return_value = 5
    mock_ui.stat_counters = {}
    mock_ui.best_rmse_label = MagicMock()
    
    # Mock orchestrator on self.ui
    mock_orchestrator = MagicMock()
    mock_orchestrator._needle_cycle_step = 2
    mock_ui.orchestrator = mock_orchestrator
    
    # Instantiate CoreManager
    core_manager = CoreManager(mock_ui)
    
    # Call reset
    core_manager._reset_run_optim_workflow_state(mode="test")
    
    # Verify values were deleted from orchestrator
    assert not hasattr(mock_orchestrator, "_needle_cycle_step")
    # Verify rowCount was set on orchestrator
    assert mock_orchestrator._target_layer_count == 5
