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

"""

__version__ = "26_01"


__all__ = [
    # Version
    "__version__",
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
    "SUBSTRATE_MIN_LAMBDA",
    "CAUCHY_PRESETS",
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
    # Internal utilities (for advanced use)
    "_get_cpu_count",
    # Timestamp formats (unified across CERTUS)
    "TIMESTAMP_FMT_FILE",
    "TIMESTAMP_FMT_DISPLAY",
    "certus_timestamp_file",
    "certus_timestamp_display",
]


import json
import hashlib

import logging

import logging.handlers

import os

import queue

import sys

import tempfile

import traceback
from pathlib import Path

from dataclasses import dataclass

from datetime import datetime

from typing import Any, Optional

from certus_logging import attach_jsonl_handler, get_structured_logger


import numpy as np


# --- Dependencies Check ---

try:
    import openpyxl  # noqa: F401  # availability check

    OPENPYXL_AVAILABLE = True

except ImportError:
    OPENPYXL_AVAILABLE = False


def check_svg_availability() -> bool:
    """Check SVG widget availability"""

    try:
        from PyQt6.QtSvgWidgets import QSvgWidget  # noqa: F401  # availability check

        return True

    except ImportError:
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


def _get_cpu_count() -> int:
    """

    Get CPU count with fallback to default.

    Returns:

        Number of CPU cores, or _DEFAULT_CPU_COUNT if unavailable

    """

    return os.cpu_count() or _DEFAULT_CPU_COUNT


def get_resource_path(filename: str) -> str:
    """

    Returns absolute path to resource (PyInstaller/Dev compatible).

    External files (svg, json, xlsx) are next to executable.

    """

    if getattr(sys, "frozen", False):
        # Exe: base path is executable dir

        base_path = Path(sys.executable).resolve().parent

    else:
        # Dev: base path is script dir (assuming this file is in root)

        base_path = Path(__file__).resolve().parent

    return str(base_path / filename)


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
            return hashlib.sha256(db_path.read_bytes()).hexdigest()
    except OSError:
        pass
    return None


def configure_numba_env():
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

    # If Numba is already imported/launched in this process, NEVER change thread env.

    # Keep env aligned with runtime value to avoid:

    # "Cannot set NUMBA_NUM_THREADS to a different value once threads have been launched".

    if "numba" in sys.modules:
        try:
            import numba  # local import to avoid hard dependency at module import time

            cur = str(int(numba.get_num_threads()))

            os.environ["NUMBA_NUM_THREADS"] = cur

            for env_var in [
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            ]:
                os.environ.setdefault(env_var, cur)

            os.environ["_CERTUS_NUMBA_CONFIGURED"] = "1"

            return

        except NUMERICAL_FAULT_EXCEPTIONS :
            # Fallback to standard path if runtime introspection fails.

            pass

    # Skip if already configured (prevents RuntimeError when threads are launched)

    if os.environ.get("_CERTUS_NUMBA_CONFIGURED") == "1":
        return

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


def get_safe_worker_count(default_workers: int | None = None) -> int:
    """

    Get safe number of workers for ThreadPoolExecutor.

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
        # Optimization Python 3.14+: Free-threading allows safe parallelism even in frozen apps

        if sys.version_info >= (3, 14):
            if default_workers is not None:
                return max(1, default_workers)

            return max(1, _get_cpu_count() - _RESERVED_CORES_FOR_WORKERS)

        return 1

    if default_workers is not None:
        return max(1, default_workers)

    return max(1, _get_cpu_count() - _RESERVED_CORES_FOR_WORKERS)


# =============================================================================

# SYSTEM CONFIG

# =============================================================================



@dataclass(frozen=True)
class CertusRuntime:
    """Immutable runtime container shared by CERTUS apps."""

    logger: logging.Logger
    cache_dir: str
    n_cores: int


def setup_numba_cache() -> str:
    """Configures Numba environment and returns the cache directory."""

    configure_numba_env()
    return os.environ.get("NUMBA_CACHE_DIR", "")


def set_num_threads(n_cores: int | None = None) -> int:
    """Sets thread env vars for parallel calculations (idempotent)."""

    if n_cores is None:
        n_cores = max(1, _get_cpu_count() - _RESERVED_CORES_FOR_NUMBA)

    s_cores = str(n_cores)
    env_vars = [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]

    for env_var in env_vars:
        if env_var not in os.environ:
            os.environ[env_var] = s_cores

    return n_cores


def setup_logging(log_file: str | None = None, level: int = None) -> "logging.Logger":
    """Configure enhanced logging with detailed context and error handling."""

    import logging as _logging

    if level is None:
        level = _logging.INFO

    logger = _logging.getLogger("CERTUS")
    logger.setLevel(level)
    logger.handlers = []

    formatter = _logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-12s | %(funcName)-20s:%(lineno)-4d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = _logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    if log_file:
        try:
            log_path = log_file
            log_path_obj = Path(log_path)
            if not log_path_obj.is_absolute():
                if log_path_obj.parent == Path("."):
                    log_dir = get_resource_path("logs")
                    Path(log_dir).mkdir(parents=True, exist_ok=True)
                    log_path = str(Path(log_dir) / log_file)
                else:
                    log_path_obj.parent.mkdir(parents=True, exist_ok=True)

            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=MAX_LOG_FILE_SIZE_BYTES,
                backupCount=MAX_LOG_BACKUP_FILES,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(_logging.DEBUG)
            logger.addHandler(file_handler)

            logger.info(f"Logging initialized: file={log_path}, level={_logging.getLevelName(level)}")
        except PermissionError as e:
            _logging.error(f"Permission denied creating log file '{log_file}': {e}")
            logger.warning("Continuing with console logging only")
        except OSError as e:
            _logging.error(f"OS error creating log file '{log_file}': {e}")
            logger.warning("Continuing with console logging only")
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            _logging.error(f"Unexpected error creating log file '{log_file}': {type(e).__name__}: {e}")
            logger.warning("Continuing with console logging only")

    # Structured JSONL stream for cross-run correlation and machine parsing.
    try:
        jsonl_path = Path(get_resource_path("logs")) / "CERTUS.jsonl"
        attach_jsonl_handler(logger, jsonl_path)
    except (
        PermissionError,
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        AttributeError,
        KeyError,
        IndexError,
        FileNotFoundError,
    ) as e:
        logger.warning(f"Structured JSONL handler unavailable: {type(e).__name__}: {e}")

    return logger


def get_logger() -> "logging.Logger":
    """Returns the configured logger or creates a default one."""

    logger = logging.getLogger("CERTUS")
    if not logger.handlers:
        return setup_logging()
    return logger


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler for uncaught exceptions."""

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"Uncaught exception:\n{error_msg}")


def build_runtime(
    *,
    log_file: str | None = None,
    level: int | None = None,
    n_cores: int | None = None,
) -> CertusRuntime:
    """Build an immutable runtime object for dependency injection."""

    cache_dir = setup_numba_cache()
    resolved_n_cores = set_num_threads(n_cores)
    logger = setup_logging(log_file=log_file, level=level)
    return CertusRuntime(logger=logger, cache_dir=cache_dir, n_cores=resolved_n_cores)


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
    def setup_logging(log_file: str | None = None, level: int = None) -> "logging.Logger":
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


class ConfigManager:
    """Generic JSON config manager.

    Factorizes repeated pattern for precision, export, theme configs."""

    def __init__(self, filename: str, default_value: Any, key_name: str):
        """

        Args:

            filename: Config file name (e.g., "certus_precision.json")

            default_value: Default if file missing

            key_name: Key in JSON (e.g., "use_single_precision")

        """

        self.filename = filename

        self.default_value = default_value

        self.key_name = key_name

        self._value = default_value

        self._load()

    def _load(self) -> Any:
        """Loads config from file."""

        try:
            config_path = get_resource_path(self.filename)

            if Path(config_path).exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                    self._value = config.get(self.key_name, self.default_value)

                    return self._value

        except (IOError, json.JSONDecodeError, KeyError) as e:
            logging.debug(f"Could not load {self.filename}: {e}")

        return self.default_value

    def save(self, value: Any) -> bool:
        """

        Saves config to file.

        Args:

            value: Value to save

        Returns:

            True if success, False otherwise

        """

        try:
            config_path = get_resource_path(self.filename)

            config = {self.key_name: value}

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            self._value = value

            return True

        except (IOError, OSError, TypeError) as e:
            logging.warning(f"Could not save {self.filename}: {e}")

            return False

    def get(self) -> Any:
        """Returns curr config val."""

        return self._value

    def reload(self) -> Any:
        """Reload config from disk. Returns the loaded value."""

        return self._load()

    def set(self, value: Any) -> bool:
        """Sets and saves value."""

        return self.save(value)


# =============================================================================

# PRECISION POLICY (Opus 4.6 - Hardcoded Mixed Precision)

# =============================================================================

# Non-gradient computation: f32/c64 (TMM, spectra, STRAT, cost eval)

# Gradient computation:     f64/c128 (hardcoded in gradient kernels)

# Numba kernels auto-adapt to input dtype via JIT multi-signature.


def get_precision_config() -> bool:
    """Backward compatibility stub. Always returns False (mixed precision active)."""

    return False


def get_float_dtype():
    """Default float dtype for non-gradient computation (f32 for SIMD throughput)."""

    return np.float32


def get_complex_dtype():
    """Default complex dtype for non-gradient computation (c64 for SIMD throughput)."""

    return np.complex64


# =============================================================================

# EXPORT CONFIGURATION

# =============================================================================


_export_manager = ConfigManager("certus_export.json", True, "auto_export_enabled")


def load_export_config() -> bool:
    """Loads auto export config."""

    return _export_manager._load()


def save_export_config(enabled: bool):
    """Saves auto export config."""

    _export_manager.save(enabled)


def get_export_config() -> bool:
    """Returns curr auto export config."""

    return _export_manager.get()


# =============================================================================

# THEME CONFIGURATION

# =============================================================================


_theme_manager = ConfigManager("certus_theme.json", "light", "theme_mode")


def load_theme_config() -> str:
    """Loads theme config."""

    return _theme_manager._load()


def save_theme_config(mode: str):
    """Saves theme config."""

    _theme_manager.save(mode)


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


# Sellmeier Coefficients for Substrates (Single Source of Truth)

# Format: (B1, C1, B2, C2, B3, C3)

SELLMEIER_COEFFS_BY_ID: dict[int, tuple[float, ...]] = {
    0: (
        0.6961663,
        0.0684043**2,
        0.4079426,
        0.1162414**2,
        0.8974794,
        9.896161**2,
    ),  # SiO2/Silica
    1: (
        1.03961212,
        0.00600069867,
        0.231792344,
        0.0200179144,
        1.01046945,
        103.560653,
    ),  # N-BK7
    2: (
        0.90963095,
        0.0047563071,
        0.37290409,
        0.01621977,
        0.92110613,
        105.77911,
    ),  # D263T
    3: (
        1.4313493,
        0.0726631**2,
        0.65054713,
        0.1193242**2,
        5.3414021,
        18.028251**2,
    ),  # Sapphire
    4: (
        0.90110328,
        0.0045578115,
        0.39734436,
        0.016601149,
        0.94615601,
        111.88593,
    ),  # B270i
}

# Legacy alias

SELLMEIER_COEFFS_TUPLE = SELLMEIER_COEFFS_BY_ID


# Substrate Definitions

SUBSTRATES: dict[str, dict[str, Any]] = {
    "SiO2": {"id": 0, "min_lambda": 230.0},
    "N-BK7": {"id": 1, "min_lambda": 400.0},
    "D263T eco": {"id": 2, "min_lambda": 360.0},
    "Sapphire (Al2O3)": {"id": 3, "min_lambda": 230.0},
    "B270i": {"id": 4, "min_lambda": 400.0},
    "Silicon (Si)": {"id": -1, "min_lambda": 200.0},  # Absorbing - tabulated n,k from clues.xlsx
}


SUBSTRATE_MAPPING: dict[str, str] = {
    "N-BK7": "N-BK7",
    "SiO2": "SiO2",
    "Sapphire": "Sapphire",
    "Si-substrate": "Si-substrate",
}


SUBSTRATE_LIST = list(SUBSTRATES.keys())


SUBSTRATE_MIN_LAMBDA: dict[int, float] = {
    0: 230.0,
    1: 400.0,
    2: 360.0,
    3: 230.0,
    4: 400.0,
}


# Cauchy Presets for Materials

CAUCHY_PRESETS = {
    "Custom": (0.0, 0.0),  # User-defined (editable)
    "TiO2 (H)": (2.35, 2.30),
    "SiO2 (L)": (1.46, 1.46),
    "Ta2O5 (H)": (2.10, 2.05),
    "MgF2 (L)": (1.38, 1.37),
    "N-BK7 (Sub)": (1.52, 1.51),
    "Al2O3 (M)": (1.63, 1.62),
    "ZrO2 (H)": (2.15, 2.10),
}


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

        except (BrokenPipeError, OSError):
            self.handleError(record)


def setup_gui_logger(log_queue: queue.Queue, logger_name: str = "CERTUS") -> logging.Logger:
    """

    Configures logger with QueueHandler for GUI integration ONLY.

    No console output - all logs go to the GUI 'Show Details' panel.

    """

    logger = logging.getLogger(logger_name)

    logger.setLevel(logging.INFO)

    logger.handlers = []

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt=TIMESTAMP_FMT_DISPLAY)

    # Handler for GUI queue ONLY - no console output

    queue_handler = QueueHandler(log_queue)

    queue_handler.setFormatter(formatter)

    logger.addHandler(queue_handler)

    # Suppress propagation to root logger (prevents console output)

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
    """

    Setup logging for a specific CERTUS module.

    Args:

        module_name: Name of the module for logging

        log_file: Optional log file path

    Returns:

        Logger adapter with run_id and app_id context

    Example:

        >>> logger = setup_module_logging("CERTUS_DESIGN")

    """

    # Generate log file name if not provided

    if log_file is None:
        log_file = f"certus_{module_name.lower()}.log"

    run_id = f"{module_name.lower()}-{certus_timestamp_file()}"
    base_logger = setup_logging(log_file=log_file)
    logger = get_structured_logger(base_logger, run_id=run_id, app_id=module_name)

    logger.info(f"{module_name} initialized")

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
