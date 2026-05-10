"""Tests unitaires : certus_core — utilitaires headless étendus."""

from __future__ import annotations

import os
import numpy as np
import pytest

from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    certus_timestamp_file,
    certus_timestamp_display,
    TIMESTAMP_FMT_FILE,
    TIMESTAMP_FMT_DISPLAY,
    get_materials_db_hash,
    _get_cpu_count,
    get_resource_path,
    is_frozen,
    get_safe_worker_count,
    get_precision_config,
    get_float_dtype,
    get_complex_dtype,
    get_logger,
    setup_numba_cache,
    set_num_threads,
    build_runtime,
    SystemConfig,
    ConfigManager,
    CertusRuntime,
    wait_warmup,
    SMALL_EPSILON,
    HC_EV_NM,
    PI,
    TWO_PI,
    N_SUPERSTRATE,
    N_MIN_LIMIT,
    N_MAX_LIMIT,
    K_MAX_LIMIT,
    WL_DECIMALS,
    CertusError,
    CertusOptimizationError,
    CertusPhysicsError,
    CertusConfigError,
    ensure_numpy_arrays,
)

from certus_metal_common import normalize_percent_column


class TestCertusTimestampFile:
    def test_returns_string(self) -> None:
        ts = certus_timestamp_file()
        assert isinstance(ts, str)
        assert len(ts) > 0

    def test_no_spaces_or_colons(self) -> None:
        ts = certus_timestamp_file()
        assert " " not in ts
        assert ":" not in ts

    def test_contains_digits(self) -> None:
        ts = certus_timestamp_file()
        assert any(c.isdigit() for c in ts)


class TestCertusTimestampDisplay:
    def test_returns_string(self) -> None:
        ts = certus_timestamp_display()
        assert isinstance(ts, str)
        assert len(ts) > 0

    def test_contains_separators(self) -> None:
        ts = certus_timestamp_display()
        assert "-" in ts or ":" in ts


class TestTimestampFormats:
    def test_fmt_file_is_string(self) -> None:
        assert isinstance(TIMESTAMP_FMT_FILE, str)
        assert "%" in TIMESTAMP_FMT_FILE

    def test_fmt_display_is_string(self) -> None:
        assert isinstance(TIMESTAMP_FMT_DISPLAY, str)
        assert "%" in TIMESTAMP_FMT_DISPLAY


class TestGetMaterialsDbHash:
    def test_returns_string_or_none(self) -> None:
        h = get_materials_db_hash()
        assert h is None or isinstance(h, str)

    def test_deterministic(self) -> None:
        h1 = get_materials_db_hash()
        h2 = get_materials_db_hash()
        assert h1 == h2


class TestGetCpuCount:
    def test_returns_positive_int(self) -> None:
        n = _get_cpu_count()
        assert isinstance(n, int)
        assert n >= 1


class TestGetResourcePath:
    def test_returns_string(self) -> None:
        path = get_resource_path("test.txt")
        assert isinstance(path, str)
        assert "test.txt" in path


class TestIsFrozen:
    def test_returns_bool(self) -> None:
        assert isinstance(is_frozen(), bool)

    def test_not_frozen_in_dev(self) -> None:
        assert not is_frozen()


class TestGetSafeWorkerCount:
    def test_returns_positive(self) -> None:
        n = get_safe_worker_count()
        assert n >= 1

    def test_explicit_workers(self) -> None:
        n = get_safe_worker_count(4)
        assert n >= 1

    def test_explicit_zero_gives_one(self) -> None:
        n = get_safe_worker_count(0)
        assert n >= 1


class TestPrecisionConfig:
    def test_returns_false(self) -> None:
        assert get_precision_config() is False

    def test_float_dtype(self) -> None:
        dt = get_float_dtype()
        assert dt in (np.float32, np.float64)

    def test_complex_dtype(self) -> None:
        dt = get_complex_dtype()
        assert dt in (np.complex64, np.complex128)


class TestSetNumThreads:
    def test_returns_positive_int(self) -> None:
        n = set_num_threads()
        assert isinstance(n, int)
        assert n >= 1

    def test_explicit_value(self) -> None:
        n = set_num_threads(2)
        assert n == 2


class TestSetupNumbaCache:
    def test_returns_string(self) -> None:
        d = setup_numba_cache()
        assert isinstance(d, str)


class TestBuildRuntime:
    def test_returns_runtime(self) -> None:
        rt = build_runtime()
        assert isinstance(rt, CertusRuntime)
        assert rt.n_cores >= 1


class TestWaitWarmup:
    def test_no_error_when_no_thread(self) -> None:
        wait_warmup(timeout=0.1)  # should not raise


class TestGetLogger:
    def test_returns_logger(self) -> None:
        logger = get_logger()
        assert logger is not None


class TestSystemConfig:
    def test_setup_numba_cache(self) -> None:
        d = SystemConfig.setup_numba_cache()
        assert isinstance(d, str)

    def test_resource_path(self) -> None:
        p = SystemConfig.resource_path("test.txt")
        assert "test.txt" in p


class TestConfigManager:
    def test_creates_with_defaults(self, tmp_path) -> None:
        mgr = ConfigManager("nonexistent_config.json", True, "my_key")
        assert mgr.get() is True

    def test_set_and_get(self, tmp_path) -> None:
        mgr = ConfigManager("nonexistent_config.json", True, "my_key")
        # get() should return the default since file doesn't exist
        assert mgr.get() is True


class TestPhysicalConstants:
    def test_small_epsilon(self) -> None:
        assert SMALL_EPSILON > 0
        assert SMALL_EPSILON < 1e-6

    def test_hc_ev_nm(self) -> None:
        assert abs(HC_EV_NM - 1239.84193) < 0.01

    def test_pi(self) -> None:
        assert abs(PI - np.pi) < 1e-15

    def test_two_pi(self) -> None:
        assert abs(TWO_PI - 2 * np.pi) < 1e-12

    def test_n_superstrate(self) -> None:
        assert N_SUPERSTRATE == 1.0

    def test_n_limits(self) -> None:
        assert N_MIN_LIMIT < N_MAX_LIMIT
        assert K_MAX_LIMIT > 0


class TestNumericalFaultExceptions:
    def test_is_tuple(self) -> None:
        assert isinstance(NUMERICAL_FAULT_EXCEPTIONS, tuple)

    def test_contains_common_types(self) -> None:
        assert ValueError in NUMERICAL_FAULT_EXCEPTIONS
        assert RuntimeError in NUMERICAL_FAULT_EXCEPTIONS


class TestBaseExceptions:
    def test_certus_error(self) -> None:
        assert issubclass(CertusError, Exception)

    def test_optimization_error(self) -> None:
        assert issubclass(CertusOptimizationError, CertusError)

    def test_physics_error(self) -> None:
        assert issubclass(CertusPhysicsError, CertusError)

    def test_config_error(self) -> None:
        assert issubclass(CertusConfigError, CertusError)


class TestEnsureNumpyArrays:
    def test_converts_lists(self) -> None:
        result = ensure_numpy_arrays([1.0, 2.0], [3.0, 4.0])
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestNormalizePercentColumn:
    def test_values_above_1_divided(self) -> None:
        arr = np.array([50.0, 80.0, 100.0])
        result = normalize_percent_column(arr)
        np.testing.assert_allclose(result, [0.5, 0.8, 1.0])

    def test_values_below_1_unchanged(self) -> None:
        arr = np.array([0.5, 0.8, 1.0])
        result = normalize_percent_column(arr)
        np.testing.assert_allclose(result, arr)

    def test_empty_array(self) -> None:
        arr = np.array([])
        result = normalize_percent_column(arr)
        assert result.size == 0
