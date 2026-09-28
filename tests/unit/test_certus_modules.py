"""Tests for remaining modules - INDEX, STRAT, METAL
Covers core modules without specific tests."""

import pytest
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# A module that no longer imports must fail these tests, never skip them.
MODULES = {
    name: __import__(name)
    for name in ("CERTUS_INDEX", "CERTUS_STRAT", "CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER")
}


class TestCERTUSIndex:
    """Tests for CERTUS_INDEX."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_INDEX

        assert hasattr(CERTUS_INDEX, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        from certus.core.certus_core import bootstrap_app

        assert callable(bootstrap_app)

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        from certus.core.certus_core import get_logger

        logger = get_logger()
        assert logger is not None

    def test_physics_integration(self):
        """Test the integration with certus_physics."""
        from certus_physics import Layer, Target, Sample

        assert Layer is not None
        assert Target is not None
        assert Sample is not None


class TestCERTUSStrat:
    """Tests for CERTUS_STRAT."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_STRAT

        assert hasattr(CERTUS_STRAT, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        from certus.core.certus_core import bootstrap_app

        assert callable(bootstrap_app)

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        from certus.core.certus_core import get_logger

        logger = get_logger()
        assert logger is not None


    def test_multiprocessing_integration(self):
        """Test multiprocessing integration."""
        import CERTUS_STRAT

        # Verify multiprocessing is used
        has_multiprocessing = (
            "multiprocessing" in open(CERTUS_STRAT.__file__, encoding="utf-8").read()
        )
        assert has_multiprocessing


class TestCERTUSMetalSingle:
    """Tests for CERTUS_METAL_SINGLE."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_METAL_SINGLE

        assert hasattr(CERTUS_METAL_SINGLE, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        from certus.core.certus_core import bootstrap_app

        assert callable(bootstrap_app)

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        from certus.core.certus_core import get_logger

        logger = get_logger()
        assert logger is not None


    def test_optimization_integration(self):
        """Test the integration with scipy.optimize."""
        import inspect

        import CERTUS_METAL_SINGLE

        # Verify scipy.optimize is used -- in the file that defines the beam-analysis
        # worker, reached through the launcher. The launcher itself only re-exports it,
        # and the one mention it keeps (a warnings filter) would pass for the wrong reason.
        worker_file = inspect.getsourcefile(CERTUS_METAL_SINGLE.BeamAnalysisWorker)
        has_optimization = (
            "scipy.optimize"
            in open(worker_file, encoding="utf-8").read()
        )
        assert has_optimization


class TestCERTUSMetalBilayer:
    """Tests for CERTUS_METAL_BILAYER."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_METAL_BILAYER

        assert hasattr(CERTUS_METAL_BILAYER, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        from certus.core.certus_core import bootstrap_app

        assert callable(bootstrap_app)

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        from certus.core.certus_core import get_logger

        logger = get_logger()
        assert logger is not None


@pytest.mark.integration
class TestModulesIntegration:
    """Integration tests for all modules."""

    def test_modules_core_integration(self):
        """Test the modules ↔ core integration."""
        from certus.core.certus_core import get_logger, get_resource_path
        from certus.ui.certus_ui import CertusTheme

        logger = get_logger()
        theme = CertusTheme
        resource_path = get_resource_path

        assert logger is not None
        assert theme is not None
        assert callable(resource_path)

    def test_modules_physics_integration(self):
        """Test the integration of modules ↔ physics."""
        from certus_physics import Layer, Target, Sample

        # Create test objects
        layer = Layer(mat="SiO2", qwot=1.0)
        target = Target(lmin=550.0, lmax=550.0, tmin=0.5, tmax=0.5, w=1.0)

        assert layer.mat == "SiO2"
        assert target.lmin == 550.0


    def test_modules_error_handling(self):
        """Test error handling in modules."""
        from certus.utils.errors import CertusError, CertusValidationError

        #Test that exceptions are available
        error = CertusError("Test error")
        validation_error = CertusValidationError("Test validation")

        assert isinstance(error, Exception)
        assert isinstance(validation_error, CertusError)
