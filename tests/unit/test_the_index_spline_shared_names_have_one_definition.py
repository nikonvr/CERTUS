"""A name that several modules of the INDEX SPLINE window share is defined once, and imported everywhere else.

The split of the window into modules left copies behind: the corridor defaults were written in three files, each free to
drift from the others. A default that differs between the module that shows it and the module that computes with it gives
a result that looks right and is not the one on screen.

`ONE_SOURCE` names each shared name and the only file of certus/ allowed to define it at module level. `EXPOSED_BY` lists
the modules that go on exposing it (tests and the facade read it there): they hold the very same object.
"""

from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI = "certus/ui/certus_index_spline_"

ONE_SOURCE = {
    "_DEFAULT_CORRIDOR_RMSE_DELTA": f"{UI}corridor_common.py",
    "_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN": f"{UI}corridor_common.py",
    "_CORRIDOR_K_TAB_MIN_HALF_WIDTH": f"{UI}corridor_common.py",
    "_apply_fixed_log_k_axis": f"{UI}corridor_common.py",
    "_K_PLOT_YMIN": f"{UI}corridor_common.py",
    "_K_PLOT_YMAX": f"{UI}corridor_common.py",
}
#: The settings keys and the defaults of the window: the spline core defines them, the interface imports them.
WINDOW_CONSTANTS = (
    "_QS_SPLINE_ORG",
    "_QS_SPLINE_APP",
    "_QS_LAST_SPECTRUM",
    "_QS_SPECTRUM_FIT_T",
    "_QS_SPECTRUM_FIT_TREL",
    "_QS_SPECTRUM_FIT_R",
    "_QS_SPECTRUM_WT",
    "_QS_SPECTRUM_WR",
    "_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV",
    "_QS_MAIN_SPLITTER_STATE",
    "_QS_MAIN_SPLITTER_LAYOUT_REV",
    "_QS_RIGHT_SPLITTER_STATE",
    "_MAIN_SPLITTER_LAYOUT_REV",
    "_UNCERTAINTY_DEFAULTS_REV",
    "SIO2_DEFAULT_D_LO_NM",
    "SIO2_DEFAULT_D_HI_NM",
)
ONE_SOURCE |= dict.fromkeys(WINDOW_CONSTANTS, "certus/spline/certus_index_spline_core.py")
#: The two smart-init keys: `common` defines them, `smart_init` imports them.
SMART_INIT_KEYS = ("_QS_SMART_INIT_DEEP", "_QS_SMART_INIT_TWO_PHASE")
ONE_SOURCE |= dict.fromkeys(SMART_INIT_KEYS, f"{UI}common.py")
#: The payload and the two states of the smart-init dialog: `state_ui` defines them, `smart_init` imports them.
SMART_INIT_CLASSES = ("SmartInitPayload", "_SmartInitState", "SmartInitState")
ONE_SOURCE |= dict.fromkeys(SMART_INIT_CLASSES, f"{UI}state_ui.py")
EXPOSED_BY = {
    "_DEFAULT_CORRIDOR_RMSE_DELTA": ("common", "settings", "corridors"),
    "_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN": ("common", "settings", "corridors"),
    "_CORRIDOR_K_TAB_MIN_HALF_WIDTH": ("common", "settings", "corridors"),
    "_apply_fixed_log_k_axis": ("common", "execution", "rendering", "corridors", "corridor_tab", "layoutextras_mixin"),
    "_K_PLOT_YMIN": ("common", "corridors"),
    "_K_PLOT_YMAX": ("common", "corridors"),
}
EXPOSED_BY |= dict.fromkeys(WINDOW_CONSTANTS, ("common",))
EXPOSED_BY |= dict.fromkeys(("_QS_SPLINE_ORG", "_QS_SPLINE_APP"), ("common", "smart_init"))
EXPOSED_BY |= dict.fromkeys(SMART_INIT_KEYS, ("smart_init",))
EXPOSED_BY |= dict.fromkeys(SMART_INIT_CLASSES, ("smart_init", "mixins_ui", "smartinit_mixin"))
EXPOSED_BY["SmartInitState"] = ("smart_init",)
EXPOSED_BY["_SmartInitState"] = ("smart_init", "smartinit_mixin")
#: The three jobs of a corridor worker thread: `corridor_jobs` defines them, `common` and their callers import them.
CORRIDOR_JOBS = {
    "_worker_corridor_rmse_regular_grid": ("common", "ui"),
    "_worker_corridor_rmse_healer": ("common", "corridorui_mixin"),
    "_worker_curve_minimum_deep_refit": ("common", "eventsextras_mixin"),
}
ONE_SOURCE |= dict.fromkeys(CORRIDOR_JOBS, f"{UI}corridor_jobs.py")
EXPOSED_BY |= CORRIDOR_JOBS
#: A file that keeps a function of the shared name, allowed because the function only imports the shared one, inside its
#: body, and calls it.
DELEGATES = {"_apply_fixed_log_k_axis": (f"{UI}monitor_ui.py",)}


def delegation_source(func: ast.AST, name: str) -> str | None:
    """The module a function delegates `name` to, if its body is `from <module> import <name> [as x]` then one call of it."""
    if not isinstance(func, ast.FunctionDef):
        return None
    body = [n for n in func.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    if len(body) != 2 or not isinstance(body[0], ast.ImportFrom) or not isinstance(body[1], (ast.Expr, ast.Return)):
        return None
    imported, call = body[0], body[1].value
    if len(imported.names) != 1 or imported.names[0].name != name or imported.level:
        return None
    alias = imported.names[0].asname or name
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == alias):
        return None
    return imported.module


def module_level_definitions() -> dict[str, list[str]]:
    """Name -> the tracked files of certus/ that assign it, or define a function or a class of that name, at module level."""
    done = subprocess.run(["git", "ls-files", "certus/*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    found: dict[str, list[str]] = {name: [] for name in ONE_SOURCE}
    for path in done.stdout.split("\n"):
        if not path:
            continue
        for node in ast.parse((ROOT / path).read_text(encoding="utf-8-sig")).body:
            names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    names |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
            for name in names & set(found):
                if path in DELEGATES.get(name, ()) and delegation_source(node, name):
                    continue
                found[name].append(path)
    return found


DEFINITIONS = module_level_definitions()


@pytest.mark.parametrize("name", sorted(ONE_SOURCE))
def test_a_shared_name_is_defined_in_one_file(name) -> None:
    assert DEFINITIONS[name] == [ONE_SOURCE[name]]


@pytest.mark.parametrize("name", sorted(EXPOSED_BY))
def test_the_modules_that_expose_a_shared_name_hold_the_same_object(name) -> None:
    source = importlib.import_module(ONE_SOURCE[name].removesuffix(".py").replace("/", "."))
    for stem in EXPOSED_BY[name]:
        module = importlib.import_module(f"certus.ui.certus_index_spline_{stem}")
        assert getattr(module, name) is getattr(source, name), f"{stem}.{name} is a copy"


@pytest.mark.parametrize(("name", "path"), [(name, path) for name, paths in sorted(DELEGATES.items()) for path in paths])
def test_a_delegate_reaches_the_one_definition(name, path) -> None:
    source = importlib.import_module(ONE_SOURCE[name].removesuffix(".py").replace("/", "."))
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    targets = [delegation_source(node, name) for node in tree.body if getattr(node, "name", None) == name]
    assert len(targets) == 1, f"{path} must define {name} once"
    assert targets[0], f"{path} defines {name} otherwise than by delegating"
    assert getattr(importlib.import_module(targets[0]), name) is getattr(source, name)


def test_smart_init_imported_first_and_alone_takes_its_keys_from_common() -> None:
    """`smart_init` now imports `common` at module level: in a fresh interpreter that must not close an import cycle."""
    script = "; ".join(
        [
            "import sys",
            "import certus.ui.certus_index_spline_smart_init as smart_init",
            "common = sys.modules.get('certus.ui.certus_index_spline_common')",
            "assert common is not None, 'smart_init did not load common'",
            f"assert all(getattr(smart_init, n) is getattr(common, n) for n in {SMART_INIT_KEYS!r})",
        ]
    )
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
