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

from certus_core import (
    CFG,
    CAUCHY_PRESETS,
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
)


# ─────────────────────────────────────────────────────────────────────
# ConfigManager
# ─────────────────────────────────────────────────────────────────────


class TestConfigManager:
    def test_set_and_get(self, tmp_path, monkeypatch):
        f = tmp_path / "test_cfg.json"
        monkeypatch.setattr("certus_core.get_resource_path", lambda name: str(tmp_path / name))
        cm = ConfigManager("test_cfg.json", "default_val", "my_key")
        assert cm.get() == "default_val"

        assert cm.set("new_val") is True
        assert cm.get() == "new_val"

    def test_reload(self, tmp_path, monkeypatch):
        monkeypatch.setattr("certus_core.get_resource_path", lambda name: str(tmp_path / name))
        cm = ConfigManager("test_cfg2.json", 42, "number")
        cm.save(99)
        cm._value = 0  # simulate stale
        cm.reload()
        assert cm.get() == 99

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        f = tmp_path / "bad.json"
        f.write_text("not json at all {{{")
        monkeypatch.setattr("certus_core.get_resource_path", lambda name: str(tmp_path / name))
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

    def test_cauchy_presets(self):
        assert "Custom" in CAUCHY_PRESETS
        assert CAUCHY_PRESETS["Custom"] == (0.0, 0.0)
