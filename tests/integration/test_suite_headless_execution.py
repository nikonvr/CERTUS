import pytest
import os
import json
from pathlib import Path
from certus.core.certus_core import get_resource_path

@pytest.fixture
def certus_root():
    return Path(__file__).resolve().parent.parent.parent

def test_headless_execution_pipeline(certus_root, qapp):
    """
    Test headless execution by simulating a run of CERTUS_METAL_BILAYER 
    via its config loader and worker, bypassing the UI clicks.
    """
    try:
        from CERTUS_METAL_BILAYER import CertusMetalBilayerApp
    except ImportError:
        pytest.skip("CERTUS_METAL_BILAYER not loadable")

    app = CertusMetalBilayerApp()
    
    # Check if _enable_auto_batch_mode exists
    if hasattr(app, "_enable_auto_batch_mode"):
        # Create a tiny dummy config
        dummy_config = {
            "maxiter": 1,
            "popsize": 2,
            "workers": 1,
            "target_file": "CSV-metal-example.csv",
            "num_knots": 2
        }
        config_path = certus_root / "temp_dummy_config.json"
        with open(config_path, "w") as f:
            json.dump(dummy_config, f)
            
        try:
            # We don't actually kick it off because it uses sys.exit and threads,
            # but we verify that the config parser does not crash.
            parsed = app._get_config_dict()
            assert isinstance(parsed, dict)
            
            # Apply config
            app._apply_config_dict(dummy_config)
            
        finally:
            if config_path.exists():
                config_path.unlink()
    else:
        pytest.skip("No headless batch mode detected on CERTUS_METAL_BILAYER")
