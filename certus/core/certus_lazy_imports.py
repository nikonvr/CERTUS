"""
CERTUS Lazy Imports - Deferred Loading of Heavy Dependencies

Part of CERTUS Suite (Harmonized Architecture 2026)

Provides lazy loading wrappers for heavy dependencies to improve startup time:
- scipy (~100ms import time)
- matplotlib (~200ms import time)
- openpyxl (~50ms import time)
- Other heavy libraries

Usage:
    from certus.core.certus_lazy_imports import lazy_scipy, lazy_matplotlib

    # Import happens only when accessed
    result = lazy_scipy().optimize.minimize(...)

    # Or import specific submodules
    from certus.core.certus_lazy_imports import lazy_scipy_optimize
    result = lazy_scipy_optimize().minimize(...)
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Optional


class LazyModule:
    """
    Lazy import wrapper that defers module loading until first access.

    This reduces application startup time by only importing heavy dependencies
    when they are actually needed.
    """

    def __init__(self, module_name: str, import_func: Optional[Callable] = None):
        """
        Args:
            module_name: Fully qualified module name (e.g., 'scipy.optimize')
            import_func: Custom import function (defaults to __import__)
        """
        self._module_name = module_name
        self._import_func = import_func or __import__
        self._module: Optional[Any] = None
        self._loading = False

    def _load(self) -> Any:
        """Load the module if not already loaded."""
        if self._module is None and not self._loading:
            self._loading = True
            try:
                # Check if already in sys.modules
                if self._module_name in sys.modules:
                    self._module = sys.modules[self._module_name]
                else:
                    # Import the module
                    parts = self._module_name.split(".")
                    module = self._import_func(self._module_name)

                    # Navigate to the correct submodule
                    for part in parts[1:]:
                        module = getattr(module, part)

                    self._module = module
            finally:
                self._loading = False

        return self._module

    def __getattr__(self, name: str) -> Any:
        """Trigger import on attribute access."""
        module = self._load()
        return getattr(module, name)

    def __call__(self, *args, **kwargs) -> Any:
        """Support calling the module directly if it's callable."""
        module = self._load()
        return module(*args, **kwargs)

    def __dir__(self):
        """Support dir() for introspection."""
        module = self._load()
        return dir(module)


# ============================================================================
# Scipy - Heavy numerical library
# ============================================================================

_scipy_lazy = None
_scipy_optimize_lazy = None
_scipy_interpolate_lazy = None
_scipy_ndimage_lazy = None


def lazy_scipy() -> Any:
    """
    Lazy import of scipy.

    Returns:
        scipy module (loaded on first access)

    Example:
        sp = lazy_scipy()
        result = sp.optimize.minimize(...)
    """
    global _scipy_lazy
    if _scipy_lazy is None:
        _scipy_lazy = LazyModule("scipy")
    return _scipy_lazy


def lazy_scipy_optimize() -> Any:
    """
    Lazy import of scipy.optimize.

    Returns:
        scipy.optimize module (loaded on first access)

    Example:
        opt = lazy_scipy_optimize()
        result = opt.minimize(...)
    """
    global _scipy_optimize_lazy
    if _scipy_optimize_lazy is None:
        _scipy_optimize_lazy = LazyModule("scipy.optimize")
    return _scipy_optimize_lazy


def lazy_scipy_interpolate() -> Any:
    """Lazy import of scipy.interpolate."""
    global _scipy_interpolate_lazy
    if _scipy_interpolate_lazy is None:
        _scipy_interpolate_lazy = LazyModule("scipy.interpolate")
    return _scipy_interpolate_lazy


def lazy_scipy_ndimage() -> Any:
    """Lazy import of scipy.ndimage."""
    global _scipy_ndimage_lazy
    if _scipy_ndimage_lazy is None:
        _scipy_ndimage_lazy = LazyModule("scipy.ndimage")
    return _scipy_ndimage_lazy


# ============================================================================
# Matplotlib - Heavy plotting library
# ============================================================================

_matplotlib_lazy = None
_matplotlib_pyplot_lazy = None


def lazy_matplotlib() -> Any:
    """
    Lazy import of matplotlib.

    Returns:
        matplotlib module (loaded on first access)
    """
    global _matplotlib_lazy
    if _matplotlib_lazy is None:
        _matplotlib_lazy = LazyModule("matplotlib")
    return _matplotlib_lazy


def lazy_matplotlib_pyplot() -> Any:
    """
    Lazy import of matplotlib.pyplot.

    Returns:
        matplotlib.pyplot module (loaded on first access)

    Example:
        plt = lazy_matplotlib_pyplot()
        plt.figure()
    """
    global _matplotlib_pyplot_lazy
    if _matplotlib_pyplot_lazy is None:
        _matplotlib_pyplot_lazy = LazyModule("matplotlib.pyplot")
    return _matplotlib_pyplot_lazy


# ============================================================================
# OpenPyXL - Excel file handling
# ============================================================================

_openpyxl_lazy = None


def lazy_openpyxl() -> Any:
    """
    Lazy import of openpyxl.

    Returns:
        openpyxl module (loaded on first access)

    Example:
        xl = lazy_openpyxl()
        wb = xl.Workbook()
    """
    global _openpyxl_lazy
    if _openpyxl_lazy is None:
        _openpyxl_lazy = LazyModule("openpyxl")
    return _openpyxl_lazy


# ============================================================================
# Availability checks (without importing)
# ============================================================================


def is_available(module_name: str) -> bool:
    """
    Check if a module is available without importing it.

    Uses importlib.util.find_spec for fast checking.

    Args:
        module_name: Module name to check

    Returns:
        True if module can be imported
    """
    try:
        import importlib.util

        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ImportError, ModuleNotFoundError, ValueError:
        return False


# Cache availability results
_availability_cache = {}


def check_scipy_available() -> bool:
    """Check if scipy is available (cached)."""
    if "scipy" not in _availability_cache:
        _availability_cache["scipy"] = is_available("scipy")
    return _availability_cache["scipy"]


def check_matplotlib_available() -> bool:
    """Check if matplotlib is available (cached)."""
    if "matplotlib" not in _availability_cache:
        _availability_cache["matplotlib"] = is_available("matplotlib")
    return _availability_cache["matplotlib"]


def check_openpyxl_available() -> bool:
    """Check if openpyxl is available (cached)."""
    if "openpyxl" not in _availability_cache:
        _availability_cache["openpyxl"] = is_available("openpyxl")
    return _availability_cache["openpyxl"]


__all__ = [
    # Lazy loaders
    "lazy_scipy",
    "lazy_scipy_optimize",
    "lazy_scipy_interpolate",
    "lazy_scipy_ndimage",
    "lazy_matplotlib",
    "lazy_matplotlib_pyplot",
    "lazy_openpyxl",
    # Availability checks
    "is_available",
    "check_scipy_available",
    "check_matplotlib_available",
    "check_openpyxl_available",
    # Core class
    "LazyModule",
]
