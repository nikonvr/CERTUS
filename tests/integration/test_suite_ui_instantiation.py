import pytest
from PyQt6.QtCore import QTimer
import importlib

CERTUS_APPS_MAPPING = {
    "CERTUS_DESIGN": "CertusDesignApp",
    "CERTUS_FIELD": "CertusFieldApp",
    # La classe QMainWindow du Hub s'appelle CertusHub (CERTUS_HUB.py:182).
    #"CertusHubApp" never existed: the test failed as soon as it was created.
    "CERTUS_HUB": "CertusHub",
    "CERTUS_INDEX": "CertusIndexApp",
    "CERTUS_INDEX_SPLINE": "CertusIndexSplineApp",
    "CERTUS_METAL_BILAYER": "CertusMetalBilayerApp",
    "CERTUS_METAL_SINGLE": "CertusMetalSingleApp",
    "CERTUS_STRAT": "CertusStratApp",
}

@pytest.mark.parametrize("module_name, class_name", CERTUS_APPS_MAPPING.items())
def test_ui_instantiation(qapp, module_name, class_name):
    """
    Test that the main UI classes can be instantiated and shown without crashing.
    Requires the qapp fixture from conftest.py which runs offscreen.
    """
    # Dynamically import the module
    module = importlib.import_module(module_name)
    
    # Get the app class
    AppClass = getattr(module, class_name)
    
    # Instantiate the application window
    app_window = AppClass()
    
    # Use a QTimer to close the window shortly after it is shown
    QTimer.singleShot(100, app_window.close)
    
    # Show the window
    app_window.show()
    
    # Process events to execute the timer and close the window
    qapp.processEvents()
    
    # Verify the window was created
    assert app_window is not None
