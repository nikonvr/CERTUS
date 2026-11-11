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
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI = "certus/ui/certus_index_spline_"

ONE_SOURCE = {
    "_DEFAULT_CORRIDOR_RMSE_DELTA": f"{UI}corridor_common.py",
    "_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN": f"{UI}corridor_common.py",
    "_CORRIDOR_K_TAB_MIN_HALF_WIDTH": f"{UI}corridor_common.py",
}
EXPOSED_BY = {
    "_DEFAULT_CORRIDOR_RMSE_DELTA": ("common", "settings", "corridors"),
    "_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN": ("common", "settings", "corridors"),
    "_CORRIDOR_K_TAB_MIN_HALF_WIDTH": ("common", "settings", "corridors"),
}


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
