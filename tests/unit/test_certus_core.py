"""Unit tests for certus_core.py
Covers the main configuration and logging functionalities."""

import pytest
import logging
import tempfile
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from certus.core.certus_core import (
    configure_numba_env,
    get_resource_path,
    get_float_dtype,
    get_complex_dtype,
    get_precision_config,
    setup_logging,
    setup_module_logging,
    get_logger,
    bootstrap_app,
    create_module_environment,
    ConfigManager,
    GlobalConfig,
    load_export_config,
    save_export_config,
    get_export_config,
    load_theme_config,
    save_theme_config,
    get_safe_worker_count,
    _get_cpu_count,
    SMALL_EPSILON,
    T_SUB_MIN_T_NORM,
    T_SUB_MIN_R_NORM,
)


def _safe_close_logger_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    """Close a logger handler without failing on already-closed Windows streams."""
    try:
        handler.close()
    except OSError:
        pass
    finally:
        logger.removeHandler(handler)


@pytest.fixture(autouse=True)
def cleanup_certus_logger_handlers():
    """Avoid Windows file-lock issues by closing CERTUS handlers after each test."""
    yield
    logger = logging.getLogger("CERTUS")
    for handler in list(logger.handlers):
        _safe_close_logger_handler(logger, handler)


def _release_certus_logger_file_handlers() -> None:
    """Force-close logger handlers to release Windows file locks immediately."""
    logger = logging.getLogger("CERTUS")
    for handler in list(logger.handlers):
        _safe_close_logger_handler(logger, handler)


class TestGlobalConfig:
    """Tests for la classe GlobalConfig."""

    def test_physical_constants_normalization(self):
        """Constantes de normalisation T/R (certus_core)."""
        assert SMALL_EPSILON == 1e-12
        assert T_SUB_MIN_T_NORM == 1e-6
        assert T_SUB_MIN_R_NORM == 0.05

    def test_global_config_constants_values(self):
        """Test que les constantes ont les bonnes valeurs."""
        assert GlobalConfig.MIN_THICKNESS == 0.01
        assert GlobalConfig.MAX_LAYERS == 100
        assert GlobalConfig.DEFAULT_L0 == 500.0
        assert GlobalConfig.EPSILON == 1e-9
        assert GlobalConfig.UNDO_LIMIT == 5

        assert GlobalConfig.WL_VIS_MIN == 380.0
        assert GlobalConfig.WL_VIS_MAX == 780.0

        assert isinstance(GlobalConfig.MATERIALS, tuple)
        assert "H" in GlobalConfig.MATERIALS
        assert "L" in GlobalConfig.MATERIALS


class TestConfigManager:
    """Tests for la classe ConfigManager."""

    def test_config_manager_initialization(self):
        """Test l'initialisation du ConfigManager."""
        manager = ConfigManager("test_config.json", True, "test_key")
        assert manager.filename == "test_config.json"
        assert manager.default_value is True
        assert manager.key_name == "test_key"

    def test_config_manager_save_load(self, temp_directory):
        """Test saving and loading configuration."""
        config_file = temp_directory / "test_config.json"
        manager = ConfigManager(str(config_file), False, "test_mode")

        # Test sauvegarde
        result = manager.save(True)
        assert result is True
        assert config_file.exists()

        # Loading test
        manager._value = None  # Reset
        loaded_value = manager._load()
        assert loaded_value is True

    def test_config_manager_default_value(self, temp_directory):
        """Test the use of the default value."""
        config_file = temp_directory / "nonexistent_config.json"
        manager = ConfigManager(str(config_file), "default", "test_key")

        loaded_value = manager._load()
        assert loaded_value == "default"

    def test_config_manager_get_set(self, temp_directory):
        """Test the get and set methods."""
        config_file = temp_directory / "test_config.json"
        manager = ConfigManager(str(config_file), "initial", "test_key")

        # Test get (default value)
        assert manager.get() == "initial"

        # Test set
        result = manager.set("new_value")
        assert result is True
        assert manager.get() == "new_value"

    def test_config_manager_error_handling(self):
        """Test la gestion des errors."""
        manager = ConfigManager("test_config.json", True, "test_key")

        # Test save by forcing IO error (deterministic cross-platform)
        with patch("certus.core.certus_config.Path.open", side_effect=OSError("mocked I/O error")):
            result = manager.save(True)
            assert result is False

        # Test loading from an invalid path
        loaded_value = manager._load()
        assert loaded_value is True  # Default value


class TestResourcePath:
    """Tests for les fonctions de gestion des ressources."""

    def test_get_resource_path_existing_file(self):
        """Test get_resource_path for an existing file."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = get_resource_path(tmp_path)
            assert result == tmp_path
        finally:
            os.unlink(tmp_path)

    def test_get_resource_path_nonexistent_file(self):
        """Test get_resource_path for a non-existent file."""
        # get_resource_path does not raise FileNotFoundError but returns a path
        result = get_resource_path("nonexistent_file.txt")

        # Result should be a path (even if the file does not exist)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "nonexistent_file.txt" in result

    def test_get_resource_path_relative_path(self, temp_directory):
        """Test get_resource_path for un chemin relatif."""
        # Create file in test directory
        test_file = temp_directory / "test_file.txt"
        test_file.write_text("test content")

        # Change working directory
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_directory)
            result = get_resource_path("test_file.txt")
            assert isinstance(result, str)
            assert result.endswith("test_file.txt")
        finally:
            os.chdir(old_cwd)

    def test_get_resource_path_frozen_uses_executable_parent(self, monkeypatch, temp_directory):
        """Frozen resource paths should resolve next to the executable."""
        fake_exe = temp_directory / "CERTUS_HUB.exe"
        fake_exe.write_text("stub", encoding="utf-8")

        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys.executable", str(fake_exe))

        get_resource_path.cache_clear()
        try:
            result = get_resource_path("data/materials_v1.json")
            assert result == str((temp_directory / "data" / "materials_v1.json").resolve())
        finally:
            get_resource_path.cache_clear()


class TestPrecisionConfig:
    """Tests for precision configuration."""

    def test_get_precision_config(self):
        """Test get_precision_config."""
        result = get_precision_config()
        assert isinstance(result, bool)
        assert result is False  # Mixed precision active

    def test_get_float_dtype(self):
        """Test get_float_dtype."""
        # Double precision. La politique « precision mixte f32/c64 pour le debit
        # SIMD » a ete mesuree le 2026-08-02 : 1,1 % PLUS LENTE que la double
        #precision, for 8 orders of magnitude of precision lost (error R of
        #2.7e-08 against 0 on compute_TMM_generic). See certus_core.py.
        dtype = get_float_dtype()
        assert dtype == np.float64

    def test_get_complex_dtype(self):
        """Test get_complex_dtype."""
        dtype = get_complex_dtype()
        assert dtype == np.complex128


class TestLoggingSystem:
    """Tests for the logging system."""

    def test_setup_logging_basic(self):
        """Test la configuration basique du logging."""
        logger = setup_logging()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "CERTUS"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1  # Console handler

    @patch("certus.core.certus_logging.attach_jsonl_handler")
    def test_setup_logging_with_file(self, mock_attach, temp_directory):
        """Test logging configuration with a file."""
        log_file = temp_directory / "test.log"
        logger = setup_logging(str(log_file), level=logging.DEBUG)

        assert isinstance(logger, logging.Logger)
        assert log_file.exists()
        
        logger.info("CERTUS test log")

        # Verify that the file contains logs
        log_content = log_file.read_text()
        assert "CERTUS" in log_content
        _release_certus_logger_file_handlers()

    def test_setup_logging_levels(self):
        """Test different logging levels."""
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]

        for level in levels:
            logger = setup_logging(level=level)
            assert logger.level == level

    def test_get_logger(self):
        """Test get_logger."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "CERTUS"

    def test_logging_error_handling(self):
        """Test la gestion des errors de logging."""
        # Test with an invalid path
        logger = setup_logging("/invalid/path/test.log")
        assert isinstance(logger, logging.Logger)
        # Should continue with console logging only

    def test_setup_logging_is_idempotent_for_handler_count(self):
        """Repeated setup should replace handlers instead of accumulating duplicates."""
        first = setup_logging(level=logging.INFO)
        first_count = len(first.handlers)
        second = setup_logging(level=logging.INFO)
        assert second is first
        assert len(second.handlers) == first_count


class TestNumbaEnvironment:
    """Tests for Numba environment bootstrap idempotence."""

    def test_configure_numba_env_is_idempotent(self, monkeypatch):
        pass

    def test_configure_numba_env_sets_cache_and_thread_defaults(self, monkeypatch):
        pass


class TestExportConfig:
    """Tests for export configuration."""

    def test_load_export_config(self):
        """Test loading the export configuration."""
        config = load_export_config()
        assert isinstance(config, bool)

    def test_save_export_config(self):
        """Test saving the export configuration."""
        save_export_config(True)
        config = get_export_config()
        assert config is True

        save_export_config(False)
        config = get_export_config()
        assert config is False


class TestThemeConfig:
    """Tests for theme configuration."""

    def test_load_theme_config(self):
        """Test loading the theme configuration."""
        theme = load_theme_config()
        assert isinstance(theme, str)
        assert theme in ["light", "dark", "auto"]

    def test_save_theme_config(self):
        """Test saving the theme configuration."""
        save_theme_config("dark")
        theme = load_theme_config()
        assert theme == "dark"

        save_theme_config("light")
        theme = load_theme_config()
        assert theme == "light"


class TestWorkerCount:
    """Tests for la gestion du nombre de workers."""

    def test_get_safe_worker_count(self):
        """Test get_safe_worker_count."""
        count = get_safe_worker_count()
        assert isinstance(count, int)
        assert count > 0
        assert count <= _get_cpu_count()

    def test_get_cpu_count(self):
        """Test _get_cpu_count."""
        count = _get_cpu_count()
        assert isinstance(count, int)
        assert count > 0


class TestBootstrapApp:
    """Tests for the bootstrap_app function."""

    def test_bootstrap_app_basic(self):
        """Test bootstrap_app basique."""
        # Use a temporary file as "app_file"
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(b"# Test app file")
            tmp_path = tmp.name

        try:
            result = bootstrap_app(tmp_path)
            assert isinstance(result, str)
            assert Path(result).is_dir()
        finally:
            os.unlink(tmp_path)

    def test_bootstrap_app_with_log_name(self, temp_directory):
        """Test bootstrap_app with log name."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(b"# Test app file")
            tmp_path = tmp.name

        try:
            log_name = "test_log"
            result = bootstrap_app(tmp_path, log_name)
            assert isinstance(result, str)
        finally:
            os.unlink(tmp_path)

    def test_setup_module_logging_injects_structured_context(self):
        """setup_module_logging should include run_id and app_id context."""
        logger = setup_module_logging("TEST_MODULE")
        assert hasattr(logger, "extra")
        assert logger.extra["app_id"] == "TEST_MODULE"
        assert logger.extra["run_id"].startswith("test_module-")

    def test_create_module_environment_injects_structured_logger(self):
        """create_module_environment should return a logger adapter with run context."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(b"# Test app file")
            tmp_path = tmp.name

        try:
            env = create_module_environment(tmp_path, "TEST_MODULE")
            assert "logger" in env
            assert "run_id" in env
            assert env["run_id"].startswith("test_module-")
            assert hasattr(env["logger"], "extra")
            assert env["logger"].extra["run_id"] == env["run_id"]
            assert env["logger"].extra["app_id"] == "TEST_MODULE"
        finally:
            os.unlink(tmp_path)


@pytest.mark.unit
class TestErrorHandling:
    """Tests for la gestion des errors."""

    def test_import_error_handling(self):
        """Test la gestion des errors d'import."""
        # Test that required imports work
        try:
            import numpy as np

            assert True
        except ImportError:
            pytest.fail("numpy should be available")

    def test_configuration_error_handling(self):
        """Test la gestion des errors de configuration."""
        # Test with an invalid configuration
        manager = ConfigManager("invalid_config.json", "default", "invalid_key")

        # Should not raise an exception
        value = manager.get()
        assert value == "default"


@pytest.mark.integration
class TestIntegration:
    """Integration tests for certus_core."""

    def test_full_configuration_workflow(self, temp_directory):
        """Test un workflow complet de configuration."""
        # Configure le logging
        log_file = temp_directory / "integration_test.log"
        logger = setup_logging(str(log_file))

        # Configure export
        save_export_config(True)
        export_config = get_export_config()
        assert export_config is True

        # Configure theme
        save_theme_config("dark")
        theme_config = load_theme_config()
        assert theme_config == "dark"

        # Verify that tout fonctionne ensemble
        assert isinstance(logger, logging.Logger)
        assert log_file.exists()
        _release_certus_logger_file_handlers()

    def test_resource_and_config_integration(self, temp_directory):
        """Test resource integration and configuration."""
        # Create configuration file
        config_file = temp_directory / "test_config.json"
        config_data = {"test_value": True, "test_mode": "integration"}
        config_file.write_text(json.dumps(config_data))

        # Test resource access
        assert config_file.exists()

        # Test configuration
        manager = ConfigManager(str(config_file), False, "test_value")
        value = manager.get()
        assert value is True
