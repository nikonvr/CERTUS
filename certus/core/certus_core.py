"""

CERTUS Core - System Configuration & Foundations

================================================

Part of CERTUS Suite (Harmonized Architecture 2026)


Contains:

- System Configuration (Logging, cache, threads)

- Physical Constants

- Global App Configuration

- Numba Environment Setup

- Utility functions (paths, frozen state)


# ============================================================================
# 🛑 AI INSTRUCTION - P0 BOUNDARY 🛑
# DO NOT IMPORT PyQt6, QWidget, OR ANY UI COMPONENTS IN THIS FILE.
# This module is strictly for logic, configuration, and data management.
# Violating this boundary will cause circular dependencies and break the architecture.
# ============================================================================

"""

from certus.core.version import (
    APP_VERSION as __version__,
    APP_SUITE_VERSION,
    APP_DISPLAY_NAME,
    APP_FULL_NAME,
)
from certus.core.certus_config import (
    CONFIG_SCHEMA_VERSION,
    ConfigManager,
    get_resource_path as config_get_resource_path,
)
from certus.core.certus_runtime import CertusRuntime, build_runtime, setup_numba_cache, set_num_threads
from certus.core.certus_logging import get_logger, handle_exception, setup_logging
from certus.core.certus_performance import perf_monitor, log_perf, PerformanceMonitor

DISPLAY_VERSION_LABEL = APP_DISPLAY_NAME
DISPLAY_FULL_LABEL = APP_FULL_NAME


__all__ = [
    # Version
    "__version__",
    "APP_SUITE_VERSION",
    # Constants
    "SMALL_EPSILON",
    "HC_EV_NM",
    "PI",
    "TWO_PI",
    "N_SUPERSTRATE",
    "N_MIN_LIMIT",
    "N_MAX_LIMIT",
    "K_MAX_LIMIT",
    "WL_DECIMALS",
    "T_SUB_MIN_T_NORM",
    "T_SUB_MIN_R_NORM",
    "FROSTED_GLASS_N",
    "FROSTED_GLASS_CAUCHY_A",
    "FROSTED_GLASS_CAUCHY_B",
    "OH_BAND_MIN",
    "OH_BAND_MAX",
    "SUBSTRATES",
    "SUBSTRATE_LIST",
    "SUBSTRATE_MAPPING",
    "SUBSTRATE_CHOICES",
    "CANONICAL_SUBSTRATE_LABELS",
    "SUBSTRATE_MIN_LAMBDA",
    # Config Classes
    "CFG",
    "GlobalConfig",
    "CertusRuntime",
    "SystemConfig",
    "ConfigManager",
    # Functions
    "get_resource_path",
    "is_frozen",
    "get_materials_db_hash",
    "configure_numba_env",
    "get_safe_worker_count",
    "get_precision_config",
    "get_float_dtype",
    "get_complex_dtype",
    "load_export_config",
    "save_export_config",
    "get_export_config",
    "load_theme_config",
    "save_theme_config",
    "setup_logging",
    "get_logger",
    "handle_exception",
    "build_runtime",
    # Performance Monitoring
    "perf_monitor",
    "log_perf",
    "PerformanceMonitor",
    # GUI Logging
    "QueueHandler",
    "setup_gui_logger",
    # Dependencies
    "OPENPYXL_AVAILABLE",
    "SVG_AVAILABLE",
    # Bootstrap & Exceptions
    "bootstrap_app",
    "CertusError",
    "CertusOptimizationError",
    "CertusPhysicsError",
    "NUMERICAL_FAULT_EXCEPTIONS",
    "CertusConfigError",
    "wait_warmup",
    # Facade Proxy
    "CertusFacadeModule",
    # Internal utilities (for advanced use)
    "_get_cpu_count",
    # Timestamp formats (unified across CERTUS)
    "TIMESTAMP_FMT_FILE",
    "TIMESTAMP_FMT_DISPLAY",
    "certus_timestamp_file",
    "certus_timestamp_display",
]


import hashlib

import logging

import logging.handlers

import os

import queue

import sys

import tempfile

import traceback
from functools import lru_cache
from pathlib import Path

from dataclasses import dataclass

from datetime import datetime

from typing import Any, Optional

from certus.utils.certus_logging import attach_jsonl_handler, get_structured_logger

import numpy as np


# --- Dependencies Check ---

try:
    import openpyxl  # noqa: F401  # availability check

    OPENPYXL_AVAILABLE = True

except ImportError:
    OPENPYXL_AVAILABLE = False


def check_svg_availability() -> bool:
    """Check SVG widget availability.

    Returns False if explicitly disabled or if PyQt6.QtSvgWidgets is missing.
    """
    # Respect manual override if requested
    o = os.environ.get("CERTUS_SVG_ICONS", "").strip().lower()
    if o in ("0", "false", "no", "off"):
        return False

    try:
        from PyQt6.QtSvgWidgets import QSvgWidget  # noqa: F401  # availability check

        return True

    except ImportError, ModuleNotFoundError:
        return False


SVG_AVAILABLE = check_svg_availability()


# Unified timestamp formats for all CERTUS modules (logs, reports, filenames)

TIMESTAMP_FMT_FILE = "%Y%m%d_%H%M%S"  # e.g. 20260310_183349 for filenames

TIMESTAMP_FMT_DISPLAY = "%Y-%m-%d %H:%M:%S"  # e.g. 2026-03-10 18:33:49 for logs/reports


def certus_timestamp_file() -> str:
    """Current time formatted for filenames (YYYYMMDD_HHMMSS). Single source for all CERTUS."""

    return datetime.now().strftime(TIMESTAMP_FMT_FILE)


def certus_timestamp_display() -> str:
    """Current time formatted for logs/reports (YYYY-MM-DD HH:MM:SS). Single source for all CERTUS."""

    return datetime.now().strftime(TIMESTAMP_FMT_DISPLAY)


# =============================================================================

# UTILS & ENVIRONMENT

# =============================================================================


# Constants for CPU/Thread management

_DEFAULT_CPU_COUNT: int = 4

_RESERVED_CORES_FOR_NUMBA: int = 1  # Reserve 1 core for Numba

_RESERVED_CORES_FOR_WORKERS: int = min(2, max(1, (os.cpu_count() or 4) // 8))  # Adaptive: 1 on <=8 cores, 2 on 16+


# Logging constants

MAX_LOG_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB

MAX_LOG_BACKUP_FILES: int = 1

JSON_INDENT: int = 2


# Thread safety constants

DEFAULT_THREAD_TIMEOUT_MS: int = 3000  # 3 seconds


@lru_cache(maxsize=1)
def _get_cpu_count() -> int:
    """

    Get CPU count with fallback to default.

    Cached to avoid repeated syscalls (os.cpu_count()).

    Returns:

        Number of CPU cores, or _DEFAULT_CPU_COUNT if unavailable

    """

    return os.cpu_count() or _DEFAULT_CPU_COUNT


@lru_cache(maxsize=128)
def get_resource_path(filename: str) -> str:
    """
    Returns absolute path to resource (PyInstaller/Dev compatible).

    Cached for performance (file path resolution → cache hit).
    Cache stats: get_resource_path.cache_info()
    """

    return config_get_resource_path(filename)


def is_frozen() -> bool:
    """Check if running in a frozen (compiled) environment."""

    return getattr(sys, "frozen", False)


def get_materials_db_hash() -> str | None:
    """Returns SHA256 of the current materials DB if available."""
    try:
        db_path = Path(get_resource_path("data/materials_v1.json"))
        if not db_path.exists():
            db_path = Path("data/materials_v1.json")
        if db_path.exists():
            content = db_path.read_bytes().replace(b"\r\n", b"\n")
            return hashlib.sha256(content).hexdigest()
    except OSError:
        pass
    return None


def configure_numba_env() -> None:
    """

    Configure Numba environment variables for safe operation in frozen executables.

    CRITICAL: Must be called BEFORE importing any module that uses @njit.

    This function is idempotent - safe to call multiple times.

    Configuration:

    - Frozen mode: Single-threaded (prevents deadlocks)

    - Development mode: Multi-threaded with reserved cores for OS/GUI

    Environment variables set:

    - NUMBA_CACHE_DIR: Cache directory for compiled functions

    - NUMBA_NUM_THREADS: Number of threads for Numba

    - NUMBA_THREADING_LAYER: Threading layer ('workqueue' or 'omp')

    - OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS: Thread limits

    """

    # sys flag is the fast path, but only if the env var also confirms "done".
    # If a test resets _CERTUS_NUMBA_CONFIGURED to "0", we must re-run full config.
    if getattr(sys, "_certus_numba_configured", False) and os.environ.get("_CERTUS_NUMBA_CONFIGURED") == "1":
        if "NUMBA_CACHE_DIR" not in os.environ:
            os.environ["NUMBA_CACHE_DIR"] = str(Path(tempfile.gettempdir()) / "CERTUS_Numba_Cache")
        if "NUMBA_THREADING_LAYER" not in os.environ:
            os.environ["NUMBA_THREADING_LAYER"] = "workqueue" if is_frozen() else "omp"
        return

    if os.environ.get("_CERTUS_NUMBA_CONFIGURED") == "1":
        return

    # If Numba is already imported/launched in this process, NEVER change thread env.
    # Keep env aligned with runtime value to avoid:
    # "Cannot set NUMBA_NUM_THREADS to a different value once threads have been launched".
    if "numba" in sys.modules or any(k.startswith("numba.") for k in sys.modules):
        try:
            import numba  # local import to avoid hard dependency at module import time

            cur = str(int(numba.get_num_threads()))
            for env_var in [
                "NUMBA_NUM_THREADS",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            ]:
                os.environ.setdefault(env_var, cur)
            os.environ["NUMBA_NUM_THREADS"] = cur
            os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue" if is_frozen() else "omp")
            os.environ["_CERTUS_NUMBA_CONFIGURED"] = "1"
            sys._certus_numba_configured = True
            return
        except Exception:
            # Fallback to standard path if runtime introspection fails.
            pass

    # Setup cache directory
    # Using a deterministic temp dir ensures reuse across runs
    cache_dir = str(Path(tempfile.gettempdir()) / "CERTUS_Numba_Cache")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = cache_dir

    if is_frozen():
        # In frozen mode: force workqueue (standard python threading)
        # TBB is hard to bundle correctly with PyInstaller.
        # workqueue is safe because we enforce max_workers=1 in get_safe_worker_count() below.
        os.environ["NUMBA_THREADING_LAYER"] = "workqueue"
        os.environ.setdefault("NUMBA_NUM_THREADS", "1")
        for env_var in [
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ]:
            os.environ.setdefault(env_var, "1")
    else:
        # Development mode: use optimal thread count
        n_cores = max(1, _get_cpu_count() - _RESERVED_CORES_FOR_NUMBA)
        s_cores = str(n_cores)
        if "NUMBA_THREADING_LAYER" not in os.environ:
            os.environ["NUMBA_THREADING_LAYER"] = "omp"
        for env_var in [
            "NUMBA_NUM_THREADS",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ]:
            if env_var not in os.environ:
                os.environ[env_var] = s_cores

    os.environ["_CERTUS_NUMBA_CONFIGURED"] = "1"
    sys._certus_numba_configured = True


@lru_cache(maxsize=8)
def get_safe_worker_count(default_workers: int | None = None) -> int:
    """

    Get safe number of workers for ThreadPoolExecutor.

    Cached to avoid repeated CPU count checks.

    Returns 1 in frozen mode to avoid Numba locking issues.

    In development mode, reserves cores for OS and GUI.

    Args:

        default_workers: Optional explicit worker count. If provided,

                        returns max(1, default_workers). If None, calculates

                        based on CPU count.

    Returns:

        Number of workers (int): 1 in frozen mode, otherwise

        max(1, cpu_count - 2) or default_workers if provided.

    Example:

        >>> workers = get_safe_worker_count()  # Auto-calculate

        >>> workers = get_safe_worker_count(8)  # Explicit count

    """

    if is_frozen():
        if default_workers is not None:
            return max(1, default_workers)

        return max(1, _get_cpu_count() - _RESERVED_CORES_FOR_WORKERS)

    if default_workers is not None:
        return max(1, default_workers)

    return max(1, _get_cpu_count() - _RESERVED_CORES_FOR_WORKERS)


# =============================================================================

# SYSTEM CONFIG

# =============================================================================


def _supports_color() -> bool:
    """Check if the console stdout supports ANSI colors."""
    if os.environ.get("CERTUS_NO_COLOR", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform != "win32":
        return True
    return "ANSICON" in os.environ or "WT_SESSION" in os.environ or os.environ.get("TERM") == "xterm-256color"


def _supports_utf8() -> bool:
    """Check if the stdout stream supports UTF-8 characters."""
    try:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        return "utf" in encoding.lower()
    except Exception:
        return False


class CertusConsoleFormatter(logging.Formatter):
    """Clean, elegant, and colorized log formatter for the terminal console."""

    def __init__(self, use_color: bool = True):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color
        self.use_unicode = _supports_utf8()

    def format(self, record: logging.LogRecord) -> str:
        sep1 = "✦" if self.use_unicode else "*"
        sep2 = "➔" if self.use_unicode else "->"

        time_str = self.formatTime(record, self.datefmt)
        msg = record.getMessage()

        if self.use_color:
            c_reset = "\033[0m"
            c_bold = "\033[1m"
            c_grey = "\033[90m"

            if record.levelno >= logging.CRITICAL:
                c_level = "\033[97;41m"
                lvl_name = " CRIT "
            elif record.levelno >= logging.ERROR:
                c_level = "\033[91m"
                lvl_name = " ERROR "
            elif record.levelno >= logging.WARNING:
                c_level = "\033[93m"
                lvl_name = " WARN  "
            elif record.levelno >= logging.INFO:
                c_level = "\033[92m"
                lvl_name = " INFO  "
            else:
                c_level = "\033[90m"
                lvl_name = " DEBUG "

            details = f"{c_grey}[{record.module}.{record.funcName}:{record.lineno}]{c_reset}"
            level_str = f"{c_level}{c_bold}{lvl_name}{c_reset}"
            formatted = f"{time_str} {sep1} {level_str} {details} {sep2} {msg}"
        else:
            lvl_name = record.levelname.ljust(5)
            details = f"[{record.module}.{record.funcName}:{record.lineno}]"
            formatted = f"{time_str} {sep1} {lvl_name} {details} {sep2} {msg}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


class CertusGuiFormatter(logging.Formatter):
    """Clean, structured log formatter for the GUI Log panels."""

    def __init__(self):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_unicode = _supports_utf8()

    def format(self, record: logging.LogRecord) -> str:
        sep1 = "✦" if self.use_unicode else "*"
        sep2 = "➔" if self.use_unicode else "->"

        time_str = self.formatTime(record, self.datefmt)
        lvl_name = record.levelname.ljust(5)
        msg = record.getMessage()
        formatted = f"{time_str} {sep1} {lvl_name} {sep2} {msg}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


class SystemConfig:
    """Compatibility wrapper kept for legacy call sites."""

    @staticmethod
    def setup_numba_cache() -> str:
        return setup_numba_cache()

    @staticmethod
    def set_num_threads(n_cores: int | None = None) -> int:
        return set_num_threads(n_cores)

    @staticmethod
    def resource_path(relative_path: str) -> str:
        """DEPRECATED: Use get_resource_path() instead."""

        return get_resource_path(relative_path)

    @staticmethod
    def setup_logging(log_file: str | None = None, level: int | None = None) -> "logging.Logger":
        return setup_logging(log_file=log_file, level=level)

    @staticmethod
    def get_logger() -> "logging.Logger":
        return get_logger()

    @staticmethod
    def handle_exception(exc_type, exc_value, exc_traceback):
        handle_exception(exc_type, exc_value, exc_traceback)


# Auto Initialization on module import

setup_numba_cache()


# Background warmup thread registry (set by bootstrap_app)


class _WarmupRegistry:
    """Holds the optional background warmup thread set by bootstrap_app.

    Replaces the previous `_certus_warmup_thread` module-level global (P1-13
    pilot 2). The class attribute is mutated in place so callers do not need
    to redeclare `global` in every accessor.
    """

    thread = None


def wait_warmup(timeout: float = 30.0) -> None:
    """Wait for background JIT warmup to complete (called before first calculation)."""

    if _WarmupRegistry.thread is not None and _WarmupRegistry.thread.is_alive():
        _WarmupRegistry.thread.join(timeout=timeout)

    _WarmupRegistry.thread = None


# =============================================================================

# PHYSICAL CONSTANTS

# =============================================================================


SMALL_EPSILON: float = 1e-12

HC_EV_NM: float = 1239.84193  # h*c in eV·nm

PI: float = np.pi

TWO_PI: float = 6.283185307179586

N_SUPERSTRATE: float = 1.0  # Air


# --- Optical Index Limits ---

N_MIN_LIMIT: float = 1.0

N_MAX_LIMIT: float = 10.0

K_MAX_LIMIT: float = 8.0


# --- Precision ---

WL_DECIMALS: int = 6


# --- T/R normalization (T_substrate thresholds to avoid explosion 1/T) ---

T_SUB_MIN_T_NORM: float = 1e-6  # threshold for T_nu = T/T_sub

T_SUB_MIN_R_NORM: float = 0.05  # threshold for R_nu = R/T_sub (absorption band guard)

# =============================================================================


CONFIG_SCHEMA_VERSION = 1


# =============================================================================

# PRECISION POLICY (Opus 4.6 - Hardcoded Mixed Precision)

# =============================================================================

# Non-gradient computation: f32/c64 (TMM, spectra, STRAT, cost eval)

# Gradient computation:     f64/c128 (hardcoded in gradient kernels)

# Numba kernels auto-adapt to input dtype via JIT multi-signature.


@lru_cache(maxsize=1)
def get_precision_config() -> bool:
    """Backward compatibility stub. Always returns False (mixed precision active).

    Cached to avoid repeated calls.
    """

    return False


@lru_cache(maxsize=1)
def get_float_dtype():
    """Default float dtype for non-gradient computation (f32 for SIMD throughput).

    Cached for performance.
    """

    return np.float32


@lru_cache(maxsize=1)
def get_complex_dtype():
    """Default complex dtype for non-gradient computation (c64 for SIMD throughput).

    Cached for performance.
    """

    return np.complex64


# =============================================================================

# EXPORT CONFIGURATION

# =============================================================================


_export_manager = ConfigManager("certus_export.json", True, "auto_export_enabled")


@lru_cache(maxsize=1)
def load_export_config() -> bool:
    """Loads auto export config (cached)."""

    return _export_manager.reload()


def save_export_config(enabled: bool) -> bool:
    """Saves auto export config."""

    return _export_manager.save(enabled)


def get_export_config() -> bool:
    """Returns current auto export config."""

    return _export_manager.get()


# =============================================================================

# THEME CONFIGURATION

# =============================================================================


_theme_manager = ConfigManager("certus_theme.json", "light", "theme_mode")
_font_manager = ConfigManager("certus_theme.json", "Default", "font_family")


def load_theme_config() -> str:
    """Loads theme config."""

    return _theme_manager.reload()


def save_theme_config(mode: str) -> bool:
    """Saves theme config."""

    return _theme_manager.save(mode)


def load_font_config() -> str:
    """Loads font config."""

    return _font_manager.reload()


def save_font_config(font_family: str) -> bool:
    """Saves font config."""

    return _font_manager.save(font_family)


# =============================================================================

# GLOBAL CONFIG

# =============================================================================


@dataclass(frozen=True)
class GlobalConfig:
    """Global immutable configuration"""

    # Layer constraints

    MIN_THICKNESS: float = 0.01

    MAX_LAYERS: int = 100

    DEFAULT_L0: float = 500.0

    EPSILON: float = 1e-9

    UNDO_LIMIT: int = 5

    MATERIALS: tuple[str, ...] = ("H", "L", "A", "B", "C", "Substrate")

    # Wavelength defaults (nm)

    WL_VIS_MIN: float = 380.0

    WL_VIS_MAX: float = 780.0

    WL_DEFAULT_MIN: float = 400.0

    WL_DEFAULT_MAX: float = 700.0

    WL_DEFAULT_POINTS: int = 50

    # Optimization defaults

    MAX_FEVAL_LOCAL: int = 10000

    MAX_FEVAL_GLOBAL: int = 150000

    MAX_FEVAL_INDEX: int = 80000

    MAX_FEVAL_METAL: int = 80000

    DEFAULT_SAMPLES_PER_ITER: int = 6000

    # Visuals

    CONVERGENCE_CURVE_COLOR: str = "#c0392b"

    CONVERGENCE_CURVE_WIDTH: int = 2


CFG = GlobalConfig()


# =============================================================================

# CONSTANTS & PRESETS

# =============================================================================


# --- Frosted Glass (Infinite Substrate) ---

FROSTED_GLASS_N: float = 1.52  # Average index

FROSTED_GLASS_CAUCHY_A: float = 1.5046

FROSTED_GLASS_CAUCHY_B: float = 4200.0  # nm²


# --- Absorption Bands ---

OH_BAND_MIN: float = 1360.0

OH_BAND_MAX: float = 1460.0


from certus.core.certus_substrate_db import (
    CANONICAL_SUBSTRATE_LABELS,
    SUBSTRATES,
    SUBSTRATE_CHOICES,
    SUBSTRATE_LIST,
    SUBSTRATE_MAPPING,
    SUBSTRATE_MIN_LAMBDA,
    SELLMEIER_COEFFS_BY_ID,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
    substrate_sellmeier_id,
)


# =============================================================================

# GUI LOGGING (Thread-Safe Queue Handler)

# =============================================================================


class QueueHandler(logging.Handler):
    """

    Logging handler sending messages to a queue for processing

    in GUI thread (thread-safe).

    """

    def __init__(self, log_queue: queue.Queue):

        super().__init__()

        self.log_queue = log_queue

    def emit(self, record):
        """Emits message to queue"""

        try:
            msg = self.format(record)

            self.log_queue.put(msg)

        except BrokenPipeError, OSError:
            self.handleError(record)


def setup_gui_logger(log_queue: queue.Queue, logger_name: str = "CERTUS") -> logging.Logger:
    """

    Configures logger with QueueHandler for GUI integration ONLY.

    No console output - all logs go to the GUI 'Show Details' panel.

    """

    logger = logging.getLogger(logger_name)

    logger.setLevel(logging.INFO)

    formatter = CertusGuiFormatter()

    # Handler for GUI queue; keep any existing file/console handlers intact so
    # the same CERTUS log stream continues to reach Show Details as well.
    if not any(isinstance(h, QueueHandler) and getattr(h, "log_queue", None) is log_queue for h in logger.handlers):
        queue_handler = QueueHandler(log_queue)
        queue_handler.setFormatter(formatter)
        logger.addHandler(queue_handler)

    # Suppress propagation to root logger (prevents duplicate console output)
    logger.propagate = False

    return logger


# =============================================================================

# CUSTOM EXCEPTIONS (Single Source of Truth)

# =============================================================================

# All CERTUS exception classes are defined here.

# certus_errors re-exports them and adds validation-only subclasses.


class CertusError(Exception):
    """Base exception for CERTUS suite.

    Attributes:

        message:    Short human-readable description.

        details:    Optional technical details.

        suggestion: Optional remediation hint shown to the user.

    """

    def __init__(self, message: str, details: str = "", suggestion: str = ""):

        self.message = message

        self.details = details

        self.suggestion = suggestion

        super().__init__(self.full_message)

    @property
    def full_message(self) -> str:

        parts = [self.message]

        if self.details:
            parts.append(f"\n\nDetails: {self.details}")

        if self.suggestion:
            parts.append(f"\n\n💡 Suggestion: {self.suggestion}")

        return "".join(parts)


class CertusOptimizationError(CertusError):
    """Error during optimization process."""

    pass


class CertusPhysicsError(CertusError):
    """Error in physics calculations."""

    pass


class CertusConfigError(CertusError):
    """Error in configuration."""

    pass


# Tuple of numerical exceptions commonly caught in solvers/physics
NUMERICAL_FAULT_EXCEPTIONS = (
    RuntimeError,
    FloatingPointError,
    ValueError,
    ZeroDivisionError,
    OverflowError,
    np.linalg.LinAlgError,
)


# =============================================================================

# APPLICATION BOOTSTRAP

# =============================================================================


def setup_module_logging(
    module_name: str,
    log_file: Optional[str] = None,
) -> logging.LoggerAdapter:
    """Setup logging for a specific CERTUS module."""

    if log_file is None:
        if module_name.upper() == "STRAT":
            log_file = "strat.log"
        else:
            log_file = f"certus_{module_name.lower()}.log"
    elif log_file == "certus_strat.log":
        log_file = "strat.log"

    run_id = f"{module_name.lower()}-{certus_timestamp_file()}"
    base_logger = setup_logging(log_file=log_file)
    logger = get_structured_logger(base_logger, run_id=run_id, app_id=module_name)

    logger.info("logger=certus module=%s status=initialized", module_name)
    return logger


def create_module_environment(module_file: str, module_name: str) -> dict[str, Any]:
    """

    Create complete environment for a CERTUS module.

    Args:

        module_file: Path to the module file

        module_name: Name of the module

    Returns:

        Dictionary with module environment info

    """

    if module_name.upper() == "STRAT":
        log_file = "strat.log"
    else:
        log_file = f"certus_{module_name.lower()}.log"

    script_dir, runtime = bootstrap_app(module_file, _log_name=log_file, return_runtime=True)

    run_id = f"{module_name.lower()}-{certus_timestamp_file()}"
    logger = get_structured_logger(runtime.logger, run_id=run_id, app_id=module_name)

    return {
        "script_dir": script_dir,
        "logger": logger,
        "runtime": runtime,
        "run_id": run_id,
        "module_name": module_name,
        "module_file": module_file,
        "log_file": log_file,
    }


def bootstrap_app(
    app_file: str,
    _log_name: str | None = None,
    *,
    runtime: CertusRuntime | None = None,
    return_runtime: bool = False,
) -> str | tuple[str, CertusRuntime]:
    """

    Standard bootstrap for all CERTUS applications.

    Configures:

    - sys.path for imports

    - Numba environment (idempotent)

    Args:

        app_file: __file__ of the calling module

        log_name: Optional log file name used during runtime logger creation.

    Returns:

        Script directory path, or (script_dir, runtime) when return_runtime=True.

    Example:

        >>> script_dir = bootstrap_app(__file__)

    """

    import sys

    # Determine base directory

    if getattr(sys, "frozen", False):
        script_dir = str(Path(sys.executable).resolve().parent)

    else:
        script_dir = str(Path(app_file).resolve(strict=False).parent)

    # Setup path (only if not already present)

    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # Launch JIT warmup in background thread (non-blocking startup)

    import threading

    def _bg_warmup():

        try:
            from certus_physics import warmup_physics

            warmup_physics(silent=True)
        except ImportError:
            pass

        try:
            from certus.core.certus_re_objectives import _warmup_re_physics

            _warmup_re_physics()
        except Exception:
            pass

    _warmup_thread = threading.Thread(target=_bg_warmup, daemon=True)

    _warmup_thread.start()

    # Store on the registry so callers can wait if needed

    _WarmupRegistry.thread = _warmup_thread

    active_runtime = runtime if runtime is not None else build_runtime(log_file=_log_name)

    if return_runtime:
        return script_dir, active_runtime

    return script_dir


# =============================================================================

# DATA UTILS (Migrated from certus_utils)

# =============================================================================


def ensure_numpy_array(data: Any, dtype: Any = None) -> np.ndarray:
    """

    Convert data to numpy array if needed.

    """

    if not isinstance(data, np.ndarray):
        return np.array(data, dtype=dtype)

    elif dtype is not None and data.dtype != dtype:
        return data.astype(dtype)

    return data


def ensure_numpy_arrays(*arrays: Any) -> tuple[np.ndarray, ...]:
    """

    Convert multiple arrays to numpy arrays.

    """

    return tuple(ensure_numpy_array(arr) for arr in arrays)


import types


class CertusFacadeModule(types.ModuleType):
    """Generic proxy module to support pytest monkeypatching.

    Delegates attribute access and modification to underlying submodules.
    """

    def __init__(self, name: str, submodules: list):
        super().__init__(name)
        self._submodules = submodules
        if name in sys.modules:
            for k, v in sys.modules[name].__dict__.items():
                self.__dict__[k] = v

    def __getattr__(self, name: str):
        if name == "_submodules":
            raise AttributeError(name)
        for sub in self._submodules:
            if hasattr(sub, name):
                return getattr(sub, name)
        raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        super().__setattr__(name, value)
        if name != "_submodules" and hasattr(self, "_submodules"):
            for sub in self._submodules:
                if hasattr(sub, name):
                    setattr(sub, name, value)
