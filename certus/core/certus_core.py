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

from certus.core.certus_config import (
    ConfigManager,
)
from certus.core.certus_config import (
    get_resource_path as config_get_resource_path,
)
from certus.core.certus_logging import get_logger, handle_exception, setup_logging
from certus.core.certus_performance import PerformanceMonitor, log_perf, perf_monitor
from certus.core.certus_runtime import CertusRuntime, build_runtime, set_num_threads, setup_numba_cache
from certus.core.version import (
    APP_SUITE_VERSION,
)
from certus.core.version import (
    APP_VERSION as __version__,
)

# The constants that the physics layer reads live in a leaf that imports nothing of CERTUS (certus/domain/constants.py):
# re-exported here, as before, so that the code that imports them from the core keeps working.
from certus.domain.constants import (
    FROSTED_GLASS_CAUCHY_A,
    FROSTED_GLASS_CAUCHY_B,
    FROSTED_GLASS_N,
    N_SUPERSTRATE,
    PI,
    TWO_PI,
    WL_DECIMALS,
    get_complex_dtype,
    get_float_dtype,
)

__all__ = [
    "APP_SUITE_VERSION",
    "CANONICAL_SUBSTRATE_LABELS",
    # Config Classes
    "CFG",
    "FROSTED_GLASS_CAUCHY_A",
    "FROSTED_GLASS_CAUCHY_B",
    "FROSTED_GLASS_N",
    "HC_EV_NM",
    "K_MAX_LIMIT",
    "NUMERICAL_FAULT_EXCEPTIONS",
    "N_MAX_LIMIT",
    "N_MIN_LIMIT",
    "N_SUPERSTRATE",
    "OH_BAND_MAX",
    "OH_BAND_MIN",
    # Dependencies
    "OPENPYXL_AVAILABLE",
    "PI",
    # Constants
    "SMALL_EPSILON",
    "SUBSTRATES",
    "SUBSTRATE_CHOICES",
    "SUBSTRATE_LIST",
    "SUBSTRATE_MAPPING",
    "SUBSTRATE_MIN_LAMBDA",
    "TIMESTAMP_FMT_DISPLAY",
    # Timestamp formats (unified across CERTUS)
    "TIMESTAMP_FMT_FILE",
    "TWO_PI",
    "T_SUB_MIN_R_NORM",
    "T_SUB_MIN_T_NORM",
    "WL_DECIMALS",
    "CertusConfigError",
    "CertusError",
    # Facade Proxy
    "CertusFacadeModule",
    "CertusOptimizationError",
    "CertusPhysicsError",
    "CertusRuntime",
    "ConfigManager",
    "GlobalConfig",
    "PerformanceMonitor",
    # GUI Logging
    "QueueHandler",
    "SystemConfig",
    # Version
    "__version__",
    # Internal utilities (for advanced use)
    "_get_cpu_count",
    # Bootstrap & Exceptions
    "bootstrap_app",
    "build_runtime",
    "certus_timestamp_display",
    "certus_timestamp_file",
    "configure_numba_env",
    "get_complex_dtype",
    "get_export_config",
    "get_float_dtype",
    "get_logger",
    "get_materials_db_hash",
    "get_precision_config",
    # Functions
    "get_resource_path",
    "get_safe_worker_count",
    "handle_exception",
    "is_frozen",
    "load_export_config",
    "load_theme_config",
    "log_perf",
    # Performance Monitoring
    "perf_monitor",
    "save_export_config",
    "save_theme_config",
    "setup_gui_logger",
    "setup_logging",
    "wait_warmup",
]


import hashlib
import logging
import logging.handlers
import os
import queue
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, overload

import numpy as np

from certus.utils.certus_logging import attach_jsonl_handler, get_structured_logger

# --- Dependencies Check ---

try:
    import openpyxl  # noqa: F401  # availability check

    OPENPYXL_AVAILABLE = True

except ImportError:
    OPENPYXL_AVAILABLE = False




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


@lru_cache(maxsize=8)
def _numba_cache_key_of(root: str) -> str:
    digest = hashlib.sha256()
    digest.update(sys.version.encode())
    try:
        from importlib.metadata import version

        digest.update(version("numba").encode())
    except Exception:  # numba absent or its metadata unreadable: the key is still one
        digest.update(b"numba?")
    if is_frozen():
        # No source on disk: the executable is the code.
        try:
            stat = Path(sys.executable).stat()
            digest.update(f"{__version__}|{stat.st_size}|{stat.st_mtime_ns}".encode())
        except OSError:
            digest.update(str(__version__).encode())
        return digest.hexdigest()[:12]
    base = Path(root)
    for package in ("certus", "certus_physics"):
        for path in sorted((base / package).rglob("*.py")):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"numba" in data:
                digest.update(path.relative_to(base).as_posix().encode())
                digest.update(b"\0")
                digest.update(data)
    return digest.hexdigest()[:12]


def numba_cache_key(root: Path | None = None) -> str:
    """Twelve hex digits that name what the compiled code of the Numba cache was compiled from.

    Numba drops a cached function when ITS source file changes, and only then: a function of one file
    that calls a function of another keeps its cached machine code, with the OLD callee inside, when
    the callee's file changes. Measured here: `cost_numba_fast` (gradient_utils.py) went on running the
    `calc_spectrum_full_exact` of the previous version of certus_tmm_matrix.py, and its cost ignored the
    absorbing substrate that the new code reads, until the cache was emptied by hand. Numerical results of
    an old version, silently, after an update.

    The cache directory carries this key (`numba_cache_dir`): the sources whose text mentions `numba` (its
    kernels, and the modules that give them constants), the version of Python and that of Numba. A change
    in one of them opens another directory, and the machine code of the old sources is never read. A file
    that does not mention `numba` (the interface) does not move the key: editing a label does not recompile
    the kernels.

    `root` is the folder that holds `certus/` and `certus_physics/` (the repository, by default).
    """
    return _numba_cache_key_of(str(Path(__file__).resolve().parents[2] if root is None else root))


def numba_cache_dir() -> str:
    """The directory of the Numba cache for this version of the sources; created if missing."""
    path = Path(tempfile.gettempdir()) / "CERTUS_Numba_Cache" / numba_cache_key()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def ensure_numba_cache_dir() -> str:
    """Point Numba at the directory of this version of the sources unless the caller chose another; return it.

    For the code that imports the kernels without going through the entry point of an application, which calls
    `configure_numba_env` first: the test session. Left alone, Numba writes its cache next to the sources, in
    `certus/physics/__pycache__`, where a function keeps the machine code of an OLD callee of another file after
    an update (see `numba_cache_key`). Measured on 2026-09-30: `cost_numba_fast` went on ignoring the substrate
    loss of the new `calc_spectrum_full_exact`, and four oracle tests failed on code that was right.

    Only the directory: no thread count, no threading layer. `configure_numba_env` sets those for the
    applications, and a change of the thread count changes the order of a parallel sum, so the last bits of a
    result. Must run before the first `import numba`: Numba fixes its cache location when it is imported.
    """

    if "NUMBA_CACHE_DIR" not in os.environ:
        os.environ["NUMBA_CACHE_DIR"] = numba_cache_dir()
    return os.environ["NUMBA_CACHE_DIR"]


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
        ensure_numba_cache_dir()
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
            sys._certus_numba_configured = True  # type: ignore[attr-defined]
            return
        except Exception:
            # Fallback to standard path if runtime introspection fails.
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    # Setup cache directory
    # A deterministic temp dir per version of the sources ensures reuse across runs of the same code, and
    # never the machine code of another one (see `numba_cache_key`)
    cache_dir = numba_cache_dir()
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
    sys._certus_numba_configured = True  # type: ignore[attr-defined]


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

    def __init__(self, use_color: bool = True) -> None:
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

    def __init__(self) -> None:
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
    def setup_logging(log_file: str | None = None, level: int | None = None) -> logging.Logger:
        return setup_logging(log_file=log_file, level=level)

    @staticmethod
    def get_logger() -> logging.Logger:
        return get_logger()

    @staticmethod
    def handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None) -> None:
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

    thread: threading.Thread | None = None
    # Set by the first start_jit_warmup call of the process, never reset: the warmup runs once.
    started = False


def _bg_warmup() -> None:
    try:
        from certus_physics import warmup_physics

        warmup_physics(silent=True)
    except ImportError:
        pass

    try:
        from certus.core.certus_re_objectives import _warmup_re_physics

        _warmup_re_physics()
    except Exception:
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


def start_jit_warmup() -> None:
    """Start the background JIT warmup, once per process, once the application's imports are done.

    bootstrap_app used to start it, at the top of every entry script and at the import of nine
    library modules: its thread then imported modules while the main thread imported others,
    and the import system could deadlock (CI, 2026-09-28: `_DeadlockError: deadlock detected by
    _ModuleLock('scipy.linalg.cython_lapack')` in an INDEX run). init_certus_app calls this.
    """
    if _WarmupRegistry.started:
        return
    _WarmupRegistry.started = True
    import threading

    thread = threading.Thread(target=_bg_warmup, name="CertusJitWarmup", daemon=True)
    thread.start()
    # Stored on the registry so callers can wait if needed
    _WarmupRegistry.thread = thread


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

# PI, TWO_PI, N_SUPERSTRATE: certus/domain/constants.py (imported at the top of this file)


# --- Optical Index Limits ---

N_MIN_LIMIT: float = 1.0

N_MAX_LIMIT: float = 10.0

K_MAX_LIMIT: float = 8.0


# --- Precision ---

# WL_DECIMALS: certus/domain/constants.py (imported at the top of this file)


# --- T/R normalization (T_substrate thresholds to avoid explosion 1/T) ---

T_SUB_MIN_T_NORM: float = 1e-6  # threshold for T_nu = T/T_sub

T_SUB_MIN_R_NORM: float = 0.05  # threshold for R_nu = R/T_sub (absorption band guard)

# =============================================================================


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

    # The policy "mixed precision f32/c64 for SIMD throughput" was MEASURED on
    # 2026-08-02 and does not hold. On compute_TMM_generic, 12-layer stack,
    # best time over 5 passes of 5000 calls:
    #
    #     c128/f64 : 0.9045 us/call   R error = 0        (reference: TMM oracle)
    #     c64/f32  : 0.9144 us/call   R error = 2.7e-08
    #
    # That is 1.1% SLOWER, for eight orders of magnitude lost in precision. LLVM does
    # not vectorize complex64 better than complex128 on this loop, and conversions
    # cost more than they bring.
    #
    # These two functions feed 20 call sites, including certus_opt_tmm.py:507 and
    # design workers. An error of 2.7e-08 on R remains below spectrophotometer
    # noise, but is disastrous for finite difference gradients: with step h = 1e-6,
    # it translates to ~3% error on the derivative.
    #
    # Reverted to double precision. Strictly beneficial change.

    return False


# `get_float_dtype` and `get_complex_dtype` (double precision, per the measurement above) live in
# certus/domain/constants.py, next to the constants that the physics layer reads; imported at the top of this file.


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


CFG = GlobalConfig()


# =============================================================================

# CONSTANTS & PRESETS

# =============================================================================


# --- Frosted Glass (Infinite Substrate) ---

# FROSTED_GLASS_N, FROSTED_GLASS_CAUCHY_A, FROSTED_GLASS_CAUCHY_B: certus/domain/constants.py (imported at the top of this file)


# --- Absorption Bands ---

OH_BAND_MIN: float = 1360.0

OH_BAND_MAX: float = 1460.0


from certus.core.certus_substrate_db import (
    CANONICAL_SUBSTRATE_LABELS,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATE_CHOICES,
    SUBSTRATE_LIST,
    SUBSTRATE_MAPPING,
    SUBSTRATE_MIN_LAMBDA,
    SUBSTRATES,
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

    def __init__(self, log_queue: queue.Queue) -> None:

        super().__init__()

        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
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

    def __init__(self, message: str, details: str = "", suggestion: str = "") -> None:

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
    log_file: str | None = None,
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


@overload
def bootstrap_app(
    app_file: str,
    _log_name: str | None = None,
    *,
    runtime: CertusRuntime | None = None,
    return_runtime: Literal[False] = False,
) -> str: ...


@overload
def bootstrap_app(
    app_file: str,
    _log_name: str | None = None,
    *,
    runtime: CertusRuntime | None = None,
    return_runtime: Literal[True],
) -> tuple[str, CertusRuntime]: ...


@overload
def bootstrap_app(
    app_file: str,
    _log_name: str | None = None,
    *,
    runtime: CertusRuntime | None = None,
    return_runtime: bool,
) -> str | tuple[str, CertusRuntime]: ...


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

    # An application script puts its folder on sys.path. A module of the certus package does
    # not: with certus/core or certus/ui on sys.path, each of their modules could be imported a
    # second time under its bare name, as a separate module object.

    package_dir = Path(__file__).resolve().parents[1]

    if script_dir not in sys.path and not Path(script_dir).resolve().is_relative_to(package_dir):
        sys.path.insert(0, script_dir)

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import threading
    from types import TracebackType


class CertusFacadeModule(types.ModuleType):
    """Generic proxy module to support pytest monkeypatching.

    Delegates attribute access and modification to underlying submodules.
    """

    def __init__(self, name: str, submodules: list) -> None:
        super().__init__(name)
        self._submodules = submodules
        if name in sys.modules:
            for k, v in sys.modules[name].__dict__.items():
                self.__dict__[k] = v

    def __getattr__(self, name: str) -> Any:
        if name == "_submodules":
            raise AttributeError(name)
        for sub in self._submodules:
            if hasattr(sub, name):
                return getattr(sub, name)
        raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name != "_submodules" and hasattr(self, "_submodules"):
            for sub in self._submodules:
                if hasattr(sub, name):
                    setattr(sub, name, value)
