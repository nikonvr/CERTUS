"""Eight static helpers of the INDEX SPLINE window are plain functions of a leaf module, and the mixins call the functions.

The mixins of the window used to reach them as `CertusIndexSplineApp.<static>(...)`, through a stand-in that imports the
module of the window when it is called: a mixin calling back the class that inherits it, a cycle no import shows. The
eight functions take no window and read none; they now live in certus_index_spline_statics.py, and the mixins call them
there. The window keeps each one under its name, as a static method that is the very function, so `self.<static>`, the
fake hosts of the tests and the protocols of certus_index_spline_corridor_host.py are untouched.

What this file pins:

* the window resolves each of the eight names to the function of the leaf module;
* the leaf imports nothing of the interface layer, at any depth: it cannot close a cycle;
* in the modules of the group, the stand-in is read for one thing only, `_prepare_worker_restart`, which the tests call
  outside an instance on fake hosts and which therefore stays a method (plan, Q6).
"""

from __future__ import annotations

import ast
import inspect
import subprocess
from pathlib import Path

import pytest

from certus.ui import certus_index_spline_statics as statics
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

ROOT = Path(__file__).resolve().parents[2]
STATICS = (
    "_rmse_from_result_dict",
    "_runtime_metrics_from_result_dict",
    "_format_lambda_knots_for_log",
    "_manual_mesh_change_log_line",
    "_summarize_manual_mesh_change",
    "_lam_uniform_grid_nm",
    "_status_iteration_metric",
    "_build_manual_repartition_target_sigma_knots",
)
#: The module of the window: there, the name is the class itself, not the stand-in.
WINDOW_MODULE = "certus/ui/certus_index_spline_ui.py"


def group_modules() -> list[str]:
    done = subprocess.run(
        ["git", "ls-files", "certus/ui/certus_index_spline_*.py"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [path for path in done.stdout.split("\n") if path and path != WINDOW_MODULE]


def test_the_leaf_defines_the_eight_functions_and_nothing_else() -> None:
    tree = ast.parse(Path(statics.__file__).read_text(encoding="utf-8-sig"))
    assert [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))] == list(STATICS)


@pytest.mark.parametrize("name", STATICS)
def test_the_window_keeps_the_name_as_a_static_method_that_is_the_function(name) -> None:
    function = vars(statics)[name]
    kept = inspect.getattr_static(CertusIndexSplineApp, name)
    assert isinstance(kept, staticmethod)
    assert kept.__func__ is function
    assert function.__module__ == statics.__name__


def test_the_leaf_imports_nothing_of_the_interface_layer_at_any_depth() -> None:
    tree = ast.parse(Path(statics.__file__).read_text(encoding="utf-8-sig"))
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert [m for m in imported if m.startswith(("certus.ui", "certus.workers"))] == []


def test_the_mixins_read_the_stand_in_for_the_worker_restart_only() -> None:
    read: dict[str, set[str]] = {}
    for path in group_modules():
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == CertusIndexSplineApp.__name__:
                read.setdefault(node.attr, set()).add(path)
    assert set(read) == {"_prepare_worker_restart"}, read
