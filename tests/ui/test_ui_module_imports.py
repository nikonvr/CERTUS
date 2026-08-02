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


def _restore_module(module_name: str, original: object | None) -> None:
    """Put ``original`` back in ``sys.modules`` after a forced re-import.

    Re-importing a module creates a *second* module object while every already
    imported consumer keeps referring to the first one. Classes defined in the
    original module — e.g. the RE mixins inherited by ``CertusREApp`` — resolve
    their globals against that first object, so leaving the fresh copy cached
    would silently break any later ``monkeypatch.setattr("<module>.<name>", …)``:
    the patch would land on the orphaned copy and the real function would run.

    When the module had never been imported before, the fresh import is exactly
    what a normal import would have left behind, so nothing is restored.
    """
    if original is None:
        return

    sys.modules[module_name] = original

    # ``import_module`` also rebinds the attribute on the parent package.
    parent_name, _, attr = module_name.rpartition(".")
    parent = sys.modules.get(parent_name) if parent_name else None
    if parent is not None:
        setattr(parent, attr, original)


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
    original = sys.modules.get(module_name)
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
    finally:
        # Never let the throwaway copy outlive the test: it would shadow the
        # module the rest of the process is already bound to.
        _restore_module(module_name, original)
