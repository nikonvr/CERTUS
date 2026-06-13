import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, call
from certus.ui.certus_substrate_presenter import CertusSubstratePresenter

def test_substrate_presenter_headless():
    """Test the CertusSubstratePresenter in headless mode (no GUI)."""
    # Arrange
    mock_view = Mock()
    mock_view.is_cancel_requested.return_value = False
    
    presenter = CertusSubstratePresenter(mock_view)
    
    # Create a mock dataframe
    # We need a column with 'sub' to trigger the substrate logic
    df = pd.DataFrame({
        "Wavelength": [400, 500, 600, 700],
        "n sub": [1.5, 1.48, 1.47, 1.46]
    })
    
    sellmeier_settings = {
        "auto": False,
        "timeout": 1.0,
        "de_iter": 10,
        "ls_nfev": 10,
        "log_l1l2": False
    }
    fit_range = (400.0, 700.0)
    
    # Act
    presenter.calculate_index(df, fit_range, sellmeier_settings)
    
    # Assert
    # Verify the view was notified appropriately
    mock_view.set_busy.assert_called_once_with(True)
    mock_view.log_message.assert_any_call("Substrate index calculation started.", "INFO")
    
    # Verify display_results was called with expected types
    assert mock_view.display_results.called
    args, kwargs = mock_view.display_results.call_args
    x_result = args[0]
    n_results_raw = args[1]
    
    assert isinstance(x_result, np.ndarray)
    assert len(x_result) == 4
    
    assert isinstance(n_results_raw, dict)
    assert "n (n sub)" in n_results_raw
    assert len(n_results_raw["n (n sub)"]) == 4

def test_substrate_presenter_headless_invalid_input():
    """Test the presenter behavior on invalid inputs."""
    mock_view = Mock()
    presenter = CertusSubstratePresenter(mock_view)
    
    # A dataframe without 'sub' columns
    df = pd.DataFrame({
        "Wavelength": [400, 500, 600],
        "R": [0.1, 0.2, 0.3]
    })
    
    presenter.calculate_index(df, (400, 800), {})
    
    assert mock_view.show_warning.called
    assert mock_view.stop_progress.called
    assert "Invalid input" in mock_view.stop_progress.call_args[0][0]
    assert not mock_view.display_results.called
