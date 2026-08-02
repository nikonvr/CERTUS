import subprocess
import pytest
import sys
from pathlib import Path

# Applications principales de CERTUS
CERTUS_APPS = [
    "CERTUS_DESIGN.py",
    "CERTUS_FIELD.py",
    "CERTUS_HUB.py",
    "CERTUS_INDEX.py",
    "CERTUS_INDEX_SPLINE.py",
    "CERTUS_METAL_BILAYER.py",
    "CERTUS_METAL_SINGLE.py",
    "CERTUS_RE.py",
    "CERTUS_STRAT.py",
]

@pytest.mark.parametrize("app_filename", CERTUS_APPS)
def test_entry_point_imports_without_circular_errors(app_filename):
    """
    Test that each main entry point can be imported without circular import errors.
    We use subprocess to run each import in an isolated Python environment.
    This guarantees that previous tests haven't masked an import loop by pre-loading a module.
    """
    
    # Path to the root directory
    tests_dir = Path(__file__).resolve().parent.parent.parent
    app_path = tests_dir / app_filename
    
    if not app_path.exists():
        pytest.skip(f"App {app_filename} not found at {app_path}")
        
    module_name = app_filename.replace(".py", "")
    
    # Run a python subprocess to import the module
    cmd = [sys.executable, "-c", f"import {module_name}"]
    
    result = subprocess.run(
        cmd,
        cwd=str(tests_dir),
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        # Check specifically if it's an ImportError or ModuleNotFoundError
        error_msg = result.stderr.strip()
        pytest.fail(f"Failed to import {module_name}.\nError:\n{error_msg}")
