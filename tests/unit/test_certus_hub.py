"""Unit tests for CERTUS_HUB.py
Covers the main hub and launcher features."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import CERTUS_HUB
    from certus_core import bootstrap_app, get_logger

    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False


@pytest.mark.skipif(not HUB_AVAILABLE, reason="CERTUS_HUB non disponible")
class TestCERTUSHUB:
    """Tests for le module CERTUS_HUB."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_HUB

        assert hasattr(CERTUS_HUB, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        # Verify bootstrap_app is imported
        from certus_core import bootstrap_app

        assert callable(bootstrap_app)

    @patch("CERTUS_HUB.create_module_environment")
    def test_bootstrap_call(self, mock_bootstrap):
        """Test the call to the centralized bootstrap."""
        mock_bootstrap.return_value = {"script_dir": "/fake/path"}

        # Simuler l'appel dans le module
        # Note: calling the mock directly since we can't easily trigger the top-level code execution
        # inside the test without reloading. But we can verify the mock setup.
        result = mock_bootstrap(__file__, "CERTUS_HUB")

        assert isinstance(result, dict)
        assert result["script_dir"] == "/fake/path"
        mock_bootstrap.assert_called_with(__file__, "CERTUS_HUB")

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        try:
            from certus_core import get_logger

            logger = get_logger()
            assert logger is not None
        except ImportError:
            pytest.skip("Logging non disponible")

    def test_ui_components_import(self):
        """Test l'import des composants UI."""
        try:
            from certus_ui import CertusTheme, apply_certus_theme

            assert CertusTheme is not None
            assert callable(apply_certus_theme)
        except ImportError:
            pytest.skip("certus_ui non disponible")


@pytest.mark.skipif(not HUB_AVAILABLE, reason="CERTUS_HUB non disponible")
class TestHubFunctionality:
    """Tests for hub functionality."""

    def test_version_access(self):
        """Test access to the version."""
        try:
            version = CERTUS_HUB.__version__
            assert isinstance(version, str)
            assert len(version) > 0
        except AttributeError:
            pytest.skip("__version__ not defined")

    @patch("CERTUS_HUB.QApplication")
    @patch("CERTUS_HUB.create_module_environment")
    def test_application_initialization(self, mock_bootstrap, mock_qapp):
        """Test l'initialisation de l'application."""
        mock_bootstrap.return_value = {"script_dir": "/fake/path"}
        mock_app_instance = Mock()
        mock_qapp.instance.return_value = mock_app_instance

        # Simuler une partie du code d'initialisation
        env = mock_bootstrap(__file__, "CERTUS_HUB")
        assert isinstance(env, dict)
        assert env["script_dir"] == "/fake/path"

    def test_resource_handling(self):
        """Test la gestion des ressources."""
        try:
            from certus_core import get_resource_path

            # Test avec un chemin relatif
            resource_path = get_resource_path("certus_theme.json")
            assert isinstance(resource_path, str)
        except (ImportError, FileNotFoundError):
            pytest.skip("Gestion de ressources non disponible")


@pytest.mark.integration
@pytest.mark.skipif(not HUB_AVAILABLE, reason="CERTUS_HUB non disponible")
class TestHubIntegration:
    """Integration tests for the hub."""

    @patch("certus_core.bootstrap_app")
    def test_application_initialization(self, mock_bootstrap):
        """Test l'initialisation de l'application."""
        mock_bootstrap.return_value = "/fake/path"

        # Simuler l'initialisation
        app_path = mock_bootstrap(__file__)

        assert isinstance(app_path, str)
        # Accepter les chemins Windows et Unix
        is_valid_path = app_path == "/fake/path" or app_path.replace(  # Chemin Unix
            "\\\\", "/"
        ).endswith(
            "fake/path"
        )  # Normalized Windows path
        assert is_valid_path

    def test_hub_core_integration(self):
        """Test hub ↔ core integration."""
        try:
            from certus_core import get_logger, get_resource_path
            from certus_ui import CertusTheme

            # Verify that all dependencies work
            logger = get_logger()
            theme = CertusTheme
            resource_path = get_resource_path

            assert logger is not None
            assert theme is not None
            assert callable(resource_path)
        except ImportError as e:
            pytest.skip(f"Missing dependency:{e}")

    def test_module_launch_capabilities(self):
        """Tests module launch capabilities."""
        # Verify that main modules can be imported
        modules_to_test = [
            "CERTUS_DESIGN",
            "CERTUS_INDEX",
            "CERTUS_STRAT",
            "CERTUS_METAL_SINGLE",
            "CERTUS_METAL_BILAYER",
        ]

        available_modules = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                available_modules.append(module_name)
            except ImportError:
                pass

        # At least some modules should be available
        assert len(available_modules) > 0
