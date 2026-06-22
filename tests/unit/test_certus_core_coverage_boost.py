"""Additional coverage tests for certus_core.py — config management, exceptions, utilities.

Targets lines 713-714 (ConfigManager error), 1045-1058 (QueueHandler), 1288 (frozen),
ensure_numpy_array/arrays, CertusError full_message formatting, export/theme config.
"""

import json
import logging
import queue
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus.core.certus_core import (
    CFG,
    CertusConfigError,
    CertusError,
    CertusOptimizationError,
    CertusPhysicsError,
    ConfigManager,
    NUMERICAL_FAULT_EXCEPTIONS,
    QueueHandler,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATES,
    SUBSTRATE_LIST,
    SUBSTRATE_MIN_LAMBDA,
    SystemConfig,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
    ensure_numpy_array,
    ensure_numpy_arrays,
    get_complex_dtype,
    get_export_config,
    get_float_dtype,
    get_logger,
    get_precision_config,
    get_resource_path,
    get_safe_worker_count,
    handle_exception,
    is_frozen,
    setup_gui_logger,
    wait_warmup,
    check_svg_availability,
    get_materials_db_hash,
    setup_logging,
)


# ─────────────────────────────────────────────────────────────────────
# ConfigManager
# ─────────────────────────────────────────────────────────────────────


class TestConfigManager:
    def test_set_and_get(self, tmp_path, monkeypatch):
        f = tmp_path / "test_cfg.json"
        monkeypatch.setattr("certus.core.certus_config.get_resource_path", lambda name: str(tmp_path / name))
        cm = ConfigManager("test_cfg.json", "default_val", "my_key")
        assert cm.get() == "default_val"

        assert cm.set("new_val") is True
        assert cm.get() == "new_val"

    def test_reload(self, tmp_path, monkeypatch):
        monkeypatch.setattr("certus.core.certus_config.get_resource_path", lambda name: str(tmp_path / name))
        cm = ConfigManager("test_cfg2.json", 42, "number")
        cm.save(99)
        cm._value = 0  # simulate stale
        cm.reload()
        assert cm.get() == 99

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        f = tmp_path / "bad.json"
        f.write_text("not json at all {{{")
        monkeypatch.setattr("certus.core.certus_config.get_resource_path", lambda name: str(tmp_path / name))
        cm = ConfigManager("bad.json", "fallback", "k")
        assert cm.get() == "fallback"


# ─────────────────────────────────────────────────────────────────────
# CertusError hierarchy
# ─────────────────────────────────────────────────────────────────────


class TestCertusExceptions:
    def test_base_error_full_message(self):
        e = CertusError("msg", details="det", suggestion="sug")
        assert "msg" in e.full_message
        assert "det" in e.full_message
        assert "sug" in e.full_message

    def test_base_error_no_details(self):
        e = CertusError("simple")
        assert e.full_message == "simple"
        assert e.details == ""

    def test_optimization_error(self):
        e = CertusOptimizationError("opt failed")
        assert isinstance(e, CertusError)

    def test_physics_error(self):
        e = CertusPhysicsError("physics broke")
        assert isinstance(e, CertusError)

    def test_config_error(self):
        e = CertusConfigError("bad config")
        assert isinstance(e, CertusError)

    def test_numerical_fault_exceptions_is_tuple(self):
        assert isinstance(NUMERICAL_FAULT_EXCEPTIONS, tuple)
        assert RuntimeError in NUMERICAL_FAULT_EXCEPTIONS


# ─────────────────────────────────────────────────────────────────────
# QueueHandler & setup_gui_logger
# ─────────────────────────────────────────────────────────────────────


class TestQueueHandler:
    def test_emit_to_queue(self):
        q = queue.Queue()
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        handler.emit(record)
        assert q.get_nowait() == "hello"

    def test_setup_gui_logger_returns_logger(self):
        q = queue.Queue()
        logger = setup_gui_logger(q, "test_gui_logger")
        assert isinstance(logger, logging.Logger)
        logger.info("test message")
        msg = q.get_nowait()
        assert "test message" in msg


# ─────────────────────────────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────────────────────────────


class TestUtilities:
    def test_get_cpu_count(self):
        n = _get_cpu_count()
        assert isinstance(n, int)
        assert n >= 1

    def test_is_frozen(self):
        assert is_frozen() is False  # We are in dev mode

    def test_get_resource_path(self):
        p = get_resource_path("data/test.json")
        assert "data" in p
        assert "test.json" in p

    def test_timestamp_file_format(self):
        ts = certus_timestamp_file()
        assert len(ts) == 15  # YYYYMMDD_HHMMSS
        assert "_" in ts

    def test_timestamp_display_format(self):
        ts = certus_timestamp_display()
        assert "-" in ts
        assert ":" in ts

    def test_get_precision_config(self):
        assert get_precision_config() is False

    def test_get_float_dtype(self):
        assert get_float_dtype() == np.float32

    def test_get_complex_dtype(self):
        assert get_complex_dtype() == np.complex64

    def test_get_safe_worker_count_default(self):
        n = get_safe_worker_count()
        assert n >= 1

    def test_get_safe_worker_count_explicit(self):
        n = get_safe_worker_count(4)
        assert n == 4

    def test_get_safe_worker_count_zero(self):
        n = get_safe_worker_count(0)
        assert n == 1

    def test_handle_exception_keyboard(self):
        # Should not raise
        handle_exception(KeyboardInterrupt, KeyboardInterrupt(), None)

    def test_wait_warmup_noop(self):
        # Should not raise when no warmup thread
        wait_warmup(0.1)


# ─────────────────────────────────────────────────────────────────────
# ensure_numpy_array / ensure_numpy_arrays
# ─────────────────────────────────────────────────────────────────────


class TestEnsureNumpy:
    def test_list_to_array(self):
        a = ensure_numpy_array([1, 2, 3])
        assert isinstance(a, np.ndarray)

    def test_with_dtype(self):
        a = ensure_numpy_array([1, 2], dtype=np.float64)
        assert a.dtype == np.float64

    def test_passthrough(self):
        orig = np.array([1.0, 2.0])
        result = ensure_numpy_array(orig)
        assert result is orig

    def test_dtype_conversion(self):
        orig = np.array([1.0, 2.0], dtype=np.float32)
        result = ensure_numpy_array(orig, dtype=np.float64)
        assert result.dtype == np.float64

    def test_multiple(self):
        a, b = ensure_numpy_arrays([1, 2], [3, 4])
        assert isinstance(a, np.ndarray)
        assert isinstance(b, np.ndarray)


# ─────────────────────────────────────────────────────────────────────
# SystemConfig (legacy)
# ─────────────────────────────────────────────────────────────────────


class TestSystemConfig:
    def test_resource_path(self):
        p = SystemConfig.resource_path("test.json")
        assert "test.json" in p

    def test_get_logger(self):
        logger = SystemConfig.get_logger()
        assert isinstance(logger, logging.Logger)


# ─────────────────────────────────────────────────────────────────────
# Constants sanity
# ─────────────────────────────────────────────────────────────────────


class TestConstants:
    def test_cfg_defaults(self):
        assert CFG.MIN_THICKNESS > 0
        assert CFG.MAX_LAYERS > 0
        assert CFG.DEFAULT_L0 > 0

    def test_substrates(self):
        assert len(SUBSTRATES) >= 5
        assert "SiO2" in SUBSTRATES

    def test_substrate_list(self):
        assert isinstance(SUBSTRATE_LIST, list)
        assert len(SUBSTRATE_LIST) == len(SUBSTRATES)

    def test_sellmeier_coeffs(self):
        assert 0 in SELLMEIER_COEFFS_BY_ID  # SiO2
        assert len(SELLMEIER_COEFFS_BY_ID[0]) == 6



# ─────────────────────────────────────────────────────────────────────
# Additional Coverage Boost for certus_core.py
# ─────────────────────────────────────────────────────────────────────


class TestCoreCoverageBoost:
    def test_check_svg_availability_env_overrides(self, monkeypatch):
        # Test explicit override '0'
        monkeypatch.setenv("CERTUS_SVG_ICONS", "0")
        assert check_svg_availability() is False

        # Test explicit override 'false'
        monkeypatch.setenv("CERTUS_SVG_ICONS", "false")
        assert check_svg_availability() is False

        # Test explicit override '1'
        monkeypatch.setenv("CERTUS_SVG_ICONS", "1")
        # In this case it should try to import QSvgWidget
        res = check_svg_availability()
        assert isinstance(res, bool)

    def test_check_svg_availability_win32_py314(self, monkeypatch):
        # If no override is provided, the function simply attempts to import QSvgWidget.
        # It should succeed if PyQt6 is installed, hence we expect a boolean result.
        monkeypatch.delenv("CERTUS_SVG_ICONS", raising=False)
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr("sys.version_info", (3, 14, 0))
        res = check_svg_availability()
        assert isinstance(res, bool)

    def test_check_svg_availability_linux_py314(self, monkeypatch):
        # Linux + Python >= 3.14 should try to import (not automatically False)
        monkeypatch.delenv("CERTUS_SVG_ICONS", raising=False)
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("sys.version_info", (3, 14, 0))
        res = check_svg_availability()
        assert isinstance(res, bool)

    def test_get_materials_db_hash_not_found(self, monkeypatch):
        # Mock Path.exists to always return False
        monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
        # Should gracefully return None when file doesn't exist
        assert get_materials_db_hash() is None

    def test_get_materials_db_hash_os_error(self, monkeypatch):
        # If read_bytes raises OSError, it should catch it and return None
        monkeypatch.setattr("certus.core.certus_core.get_resource_path", lambda x: __file__)
        def mock_read_bytes():
            raise OSError("Access denied")
        monkeypatch.setattr("pathlib.Path.read_bytes", lambda self: mock_read_bytes())
        assert get_materials_db_hash() is None

    def test_get_safe_worker_count_frozen(self, monkeypatch):
        monkeypatch.setattr("certus.core.certus_core.is_frozen", lambda: True)
        assert get_safe_worker_count() >= 1
        assert get_safe_worker_count(4) == 4

    def test_setup_logging_permission_error(self, monkeypatch):
        # setup_logging should catch PermissionError/OSError when path is invalid or unwritable
        # Pass a directory name as file name to trigger OSError on file creation
        invalid_path = str(Path(__file__).parent)
        logger = setup_logging(log_file=invalid_path, level=logging.INFO)
        assert logger is not None
        # Assert that it has stream handlers
        assert len(logger.handlers) >= 1

    def test_setup_logging_jsonl_error(self, monkeypatch):
        # Make attach_jsonl_handler raise ValueError to cover exception path
        def mock_attach(*args):
            raise TypeError("Mock error")
        monkeypatch.setattr("certus.core.certus_core.attach_jsonl_handler", mock_attach)
        logger = setup_logging(log_file=None, level=logging.INFO)
        assert logger is not None

    def test_system_config_wrappers(self, monkeypatch):
        # Verify compatibility wrappers in SystemConfig execute cleanly
        assert SystemConfig.setup_numba_cache() is not None
        assert SystemConfig.set_num_threads(2) == 2
        
        # Test handle_exception compatibility wrap
        calls = []
        monkeypatch.setattr("certus.core.certus_core.handle_exception", lambda *args: calls.append(args))
        SystemConfig.handle_exception(ValueError, ValueError("test"), None)
        assert len(calls) == 1

    def test_handle_exception_non_keyboard(self, monkeypatch):
        calls = []
        monkeypatch.setattr("logging.critical", lambda msg, *args, **kwargs: calls.append(msg % args if args else msg))
        handle_exception(ValueError, ValueError("test error"), None)
        assert any("uncaught_exception" in msg for msg in calls)

    def test_check_svg_availability_importerror(self, monkeypatch):
        monkeypatch.setenv("CERTUS_SVG_ICONS", "1")
        import sys
        orig_val = sys.modules.get("PyQt6.QtSvgWidgets", None)
        try:
            sys.modules["PyQt6.QtSvgWidgets"] = None
            res = check_svg_availability()
            assert res is False
        finally:
            if orig_val is None:
                sys.modules.pop("PyQt6.QtSvgWidgets", None)
            else:
                sys.modules["PyQt6.QtSvgWidgets"] = orig_val

    def test_save_error(self, tmp_path, monkeypatch):
        cm = ConfigManager("test_err_save.json", "default", "key")
        from unittest.mock import patch
        with patch("certus.core.certus_config.Path.open", side_effect=OSError("mocked I/O error")):
            assert cm.save("val") is False

    def test_export_config_wrappers(self, tmp_path, monkeypatch):
        monkeypatch.setattr("certus.core.certus_core.get_resource_path", lambda name: str(tmp_path / name))
        from certus.core.certus_core import load_export_config, save_export_config, get_export_config
        save_export_config(False)
        assert get_export_config() is False
        assert load_export_config() is False

    def test_theme_config_wrappers(self, tmp_path, monkeypatch):
        monkeypatch.setattr("certus.core.certus_core.get_resource_path", lambda name: str(tmp_path / name))
        from certus.core.certus_core import load_theme_config, save_theme_config
        save_theme_config("dark")
        assert load_theme_config() == "dark"

    def test_queue_handler_emit_error(self, monkeypatch):
        q = queue.Queue()
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        
        # Force log_queue.put to raise OSError
        def mock_put(msg):
            raise OSError("Queue closed")
        monkeypatch.setattr(q, "put", mock_put)
        
        # Verify it handles the error and doesn't raise exception
        handler.emit(record)

    def test_setup_numba_cache_and_build_runtime(self, tmp_path, monkeypatch):
        monkeypatch.setattr("certus.core.certus_core.get_resource_path", lambda name: str(tmp_path / name))
        from certus.core.certus_core import build_runtime
        runtime = build_runtime(log_file=str(tmp_path / "runtime.log"), level=logging.DEBUG, n_cores=2)
        assert runtime.n_cores == 2
        assert runtime.logger is not None

    def test_wait_warmup_with_thread(self):
        import threading
        from certus.core.certus_core import _WarmupRegistry
        t = threading.Thread(target=lambda: None)
        t.start()
        _WarmupRegistry.thread = t
        wait_warmup(1.0)
        assert _WarmupRegistry.thread is None

    def test_resource_path_frozen(self, monkeypatch):
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys.executable", "C:\\test\\bin\\certus.exe")
        p = get_resource_path("test.json")
        assert "C:\\test\\bin\\test.json" in p or "C:/test/bin/test.json" in p

    def test_setup_module_logging(self, tmp_path):
        from certus.core.certus_core import setup_module_logging
        logger = setup_module_logging("TEST_MODULE", log_file=str(tmp_path / "test_module.log"))
        assert logger is not None
        assert logger.name == "CERTUS"

    def test_create_module_environment(self, tmp_path):
        from certus.core.certus_core import create_module_environment
        env = create_module_environment(__file__, "TEST_MODULE")
        assert env["module_name"] == "TEST_MODULE"
        assert env["script_dir"] is not None

    def test_bootstrap_app(self):
        from certus.core.certus_core import bootstrap_app
        script_dir = bootstrap_app(__file__)
        assert script_dir is not None
        
        # Test return_runtime=True
        script_dir2, runtime = bootstrap_app(__file__, return_runtime=True)
        assert script_dir2 == script_dir
        assert runtime is not None


