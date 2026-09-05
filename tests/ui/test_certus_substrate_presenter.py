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
    # We need a column with 'sub' to trigger the substrate logic and at least 5 points
    df = pd.DataFrame({
        "Wavelength": [400, 500, 600, 700, 800],
        "T 7157 sapphire_nu_2f": [90.0, 92.0, 93.0, 94.0, 94.5]
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
    assert len(x_result) == 5
    
    assert isinstance(n_results_raw, dict)
    assert "n (T 7157 sapphire_nu_2f)" in n_results_raw
    assert len(n_results_raw["n (T 7157 sapphire_nu_2f)"]) == 5

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


def test_substrate_index_gui_lifecycle_and_attributes(qapp):
    """Guardrail for SubstrateIndexGUI lifecycle (filter attributes, proxy properties, preview)."""
    from certus.ui.certus_substrate_ui import SubstrateIndexGUI

    window = SubstrateIndexGUI()

    # 1. Smoothing filter attributes
    assert hasattr(window, "current_window")
    assert hasattr(window, "current_poly")
    assert hasattr(window, "current_heavy")
    assert window.current_window == 15
    assert window.current_poly == 2
    assert window.current_heavy is False

    # 2. Presenter proxy properties
    assert hasattr(window, "last_run_manifest")
    assert hasattr(window, "validation_status")
    assert window.last_run_manifest is None
    assert window.validation_status == "OK"

    # 3. Preview plot doesn't crash on missing attributes
    df = pd.DataFrame({
        "Wavelength": [400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0],
        "T 7157 sapphire_nu_2f": [90.0, 91.0, 92.0, 93.0, 93.5, 94.0, 94.5],
    })
    window.df = df
    window.preview_plot()

    # 4. _set_busy doesn't crash on missing attributes
    window._set_busy(True)
    window._set_busy(False)

