"""
Shared fixtures for CERTUS tests.
Provides common test data and configurations.
"""

import pytest
import numpy as np
import tempfile
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# The Windows console is in cp1252: any print of a character outside Latin-1 raises
#UnicodeEncodeError and FAILS the test, even though it is just a message
# diagnostic. The typical case is a test which crashes while writing its SUCCESS line
#("✅ analytic=..., fd=..."). 48 occurrences of ✅/❌/⚠ in 12 test files.
#We force UTF-8 on the test flows: a diagnostic print must never be able to
#to fail an assertion which itself has passed.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import os

# Force Qt offscreen platform for headless CI/test environments.
# Must be set BEFORE any QApplication is created.
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Disable automatic onboarding tour during tests
try:
    from certus.ui.certus_base_app import CertusBaseApp
    CertusBaseApp._maybe_run_first_time_tour = lambda self: None
except ImportError:
    pass

try:
    from PyQt6.QtWidgets import QApplication

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

try:
    from certus_physics import Layer, Target, Sample
    from certus.core.certus_core import get_float_dtype, get_complex_dtype
    from certus.utils.errors import CertusError, CertusValidationError

    PHYSICS_AVAILABLE = True
except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
    PHYSICS_AVAILABLE = False


@pytest.fixture(scope="session")
def qapp():
    """QT Application for UI tests (headless offscreen)."""
    if not QT_AVAILABLE:
        pytest.skip("PyQt6 non disponible")

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
    # Do not call app.quit() — breaks other session-scoped fixtures on teardown


@pytest.fixture(scope="session")
def float_dtype():
    """Default float data type."""
    if PHYSICS_AVAILABLE:
        return get_float_dtype()
    return np.float32


@pytest.fixture(scope="session")
def complex_dtype():
    """Default data complex type."""
    if PHYSICS_AVAILABLE:
        return get_complex_dtype()
    return np.complex64


@pytest.fixture
def sample_layers(float_dtype):
    """Test layers for optical calculations."""
    if not PHYSICS_AVAILABLE:
        pytest.skip("certus_physics non disponible")

    return [
        Layer(mat="SiO2", qwot=1.0),
        Layer(mat="TiO2", qwot=2.0),
        Layer(mat="Al2O3", qwot=0.5),
    ]


@pytest.fixture
def sample_wavelengths():
    """Longueurs d'onde de test (nm)."""
    return np.linspace(400, 800, 100)


@pytest.fixture
def sample_targets():
    """Cibles d'optimisation de test."""
    if not PHYSICS_AVAILABLE:
        pytest.skip("certus_physics non disponible")

    return [
        Target(lmin=550.0, lmax=550.0, tmin=0.5, tmax=0.5, w=1.0),
        Target(lmin=650.0, lmax=650.0, tmin=0.8, tmax=0.8, w=0.5),
    ]


@pytest.fixture
def sample_spectrum(sample_wavelengths):
    """Test spectrum (R, T)."""
    n_points = len(sample_wavelengths)
    R = np.random.uniform(0.1, 0.9, n_points)
    T = np.random.uniform(0.1, 0.9, n_points)
    return R, T


# Deplace vers tests/spectrum_helpers.py : un conftest.py declare des fixtures,
#it must not serve as a library importable by bare name (several
# conftest.py coexistent, le nom "conftest" est ambigu).
from spectrum_helpers import compute_spectrum_simple  # noqa: E402,F401


@pytest.fixture
def temp_directory():
    """Temporary directory for file tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_file(temp_directory):
    """Test configuration file."""
    config_file = temp_directory / "test_config.json"
    config_file.write_text('{"test_mode": true, "version": "test"}')
    return config_file


@pytest.fixture
def sample_data_file(temp_directory):
    """Test data file."""
    data_file = temp_directory / "test_data.csv"
    data_file.write_text("wavelength,R,T\n400,0.5,0.4\n500,0.6,0.3\n600,0.7,0.2\n")
    return data_file


@pytest.fixture
def mock_logger():
    """Mock logger for tests."""
    import logging
    from unittest.mock import Mock

    logger = Mock(spec=logging.Logger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture
def sample_materials_data():
    """Test material data."""
    return {
        "SiO2": {
            "n": [1.45, 1.46, 1.47],
            "k": [0.0, 0.0, 0.0],
            "wavelengths": [400, 600, 800],
        },
        "TiO2": {
            "n": [2.35, 2.40, 2.45],
            "k": [0.0, 0.0, 0.0],
            "wavelengths": [400, 600, 800],
        },
    }


@pytest.fixture
def validation_test_cases():
    """Test cases for validation functions."""
    return {
        "wavelength_valid": (400.0, 800.0),
        "wavelength_invalid": (800.0, 400.0),
        "wavelength_nan": (np.nan, 800.0),
        "thickness_valid": 100.0,
        "thickness_invalid": -10.0,
        "refractive_valid": (1.5, 0.1),
        "refractive_invalid": (-1.0, 0.1),
    }


@pytest.fixture
def performance_benchmark_data():
    """Data for performance benchmarks."""
    n_layers = 50
    n_wavelengths = 1000

    layers = []
    for i in range(n_layers):
        thickness = np.random.uniform(10, 200)
        material = "SiO2" if i % 2 == 0 else "TiO2"
        if PHYSICS_AVAILABLE:
            layers.append(Layer(mat=material, qwot=thickness / 100.0))

    wavelengths = np.linspace(400, 800, n_wavelengths)

    return layers, wavelengths


@pytest.fixture
def ui_test_widgets(qapp):
    """Basic UI widgets for tests."""
    if not QT_AVAILABLE:
        pytest.skip("PyQt6 non disponible")

    from PyQt6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout

    widget = QWidget()
    layout = QVBoxLayout()

    button = QPushButton("Test Button")
    label = QLabel("Test Label")

    layout.addWidget(button)
    layout.addWidget(label)
    widget.setLayout(layout)

    return widget, button, label


# Custom markers
def pytest_configure(config):
    """Configuration of pytest markers."""
    config.addinivalue_line("markers", "unit: Isolated unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Tests de performance")
    config.addinivalue_line("markers", "ui: Tests d'interface utilisateur")
    config.addinivalue_line("markers", "e2e: Tests end-to-end")
    config.addinivalue_line("markers", "slow: Tests lents")
    config.addinivalue_line("markers", "benchmark: Benchmarks de performance")
    config.addinivalue_line("markers", "regression: Performance regression tests")
    config.addinivalue_line(
        "markers",
        "index_spline_smoke: Smoke INDEX SPLINE (scripts/smoke_index_spline.py)",
    )


@pytest.fixture(autouse=True)
def isolate_environ():
    """Backup and restore os.environ between tests to prevent Numba env pollution."""
    old_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configuration automatique de l'environnement de test."""
    import logging

    # Reduce CERTUS noise only (do not mutate the root logger: hides real config problems).
    _certus = logging.getLogger("CERTUS")
    _prev = _certus.level
    _certus.setLevel(logging.CRITICAL)

    yield

    _certus.setLevel(_prev)

    for handler in _certus.handlers[:]:
        handler.close()
        _certus.removeHandler(handler)

