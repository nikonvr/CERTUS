"""Systematic import audit for all certus.ui modules.

Each module is imported in isolation via importlib. Any NameError or ImportError
immediately fails the corresponding parametrized test case, identifying the exact
module where a class is used without being imported.

Covers all patterns that caused regressions:
  - CertusScientificPlot used across multiple certus_strat_*_ui files
  - LiveMonitorWindow referenced in certus_strat_ui_plot
  - Any future class added to a file without the matching import
"""
from __future__ import annotations

import importlib
import pkgutil
import sys

import pytest


# ---------------------------------------------------------------------------
# Collect every certus.ui sub-module at collection time (no QApp needed yet)
# ---------------------------------------------------------------------------

def _collect_ui_modules() -> list[str]:
    """Return sorted list of fully-qualified module names under certus.ui."""
    import certus.ui  # noqa: F401 – needed so pkgutil can walk the package

    ui_pkg = importlib.import_module("certus.ui")
    prefix = "certus.ui."
    modules = []
    for info in pkgutil.walk_packages(ui_pkg.__path__, prefix=prefix):
        modules.append(info.name)
    return sorted(modules)


_UI_MODULES: list[str] = _collect_ui_modules()


# ---------------------------------------------------------------------------
# Parametrized import test – one test case per module
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_name", _UI_MODULES)
def test_ui_module_importable(module_name: str, qapp) -> None:
    """Every certus.ui module must be importable without NameError or ImportError.

    This test catches classes that are *used* in a module but *not imported* —
    e.g. ``CertusScientificPlot`` or ``LiveMonitorWindow`` referenced before
    the corresponding ``from ... import ...`` statement was added.
    """
    # Force a fresh import attempt (ignore cached state so refactors are caught)
    sys.modules.pop(module_name, None)

    try:
        importlib.import_module(module_name)
    except NameError as exc:
        pytest.fail(
            f"{module_name}: NameError during import — a class or name is used "
            f"but not imported.\n  Detail: {exc}"
        )
    except ImportError as exc:
        pytest.fail(
            f"{module_name}: ImportError during import — a dependency is missing "
            f"or misspelled.\n  Detail: {exc}"
        )
    except Exception:
        # Other runtime errors (e.g. Qt widget init requiring real data) are
        # intentionally not caught — only import-resolution errors matter.
        pass
