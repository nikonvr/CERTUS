"""A manager never guards a name it does not hold: the window holds it.

DESIGN's window is split into managers (`DesignOrchestrator`, `WorkerManager`, `PlotManager`...).
Each keeps its window as `self.ui` and holds none of the window's state. A guard written on the
manager itself, `getattr(self, "_workflow_stopped", False)` or `hasattr(self, "pre_polish_check")`,
is therefore always false: the default answers, the branch it protects never runs, and nothing
fails. Since the split of 2026-06-13 this made STOP inert, the automatic export silent, the
progress counters restart at every stage, and two checkboxes of the window (topology growth,
local polish before PGLOBAL) unread. `test_self_attributes_are_defined.py` cannot see it: it
skips every name that a `hasattr`/`getattr` guard mentions.

The sweep is static. It takes each class without a base that assigns `self.ui`, `self.app` or
`self.window`, gathers what the class holds (methods, class attributes, `self.name = ...`
anywhere in its body, `setattr(self, "name", ...)`), and reports every `getattr`/`hasattr` guard
on `self` for a name outside that set. Mixins are not concerned: they run on the window itself.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DELEGATES = {"ui", "app", "window"}

_PLOT_THEME = (
    "Reading the plots on the window applies the compact theme to them at start-up: their "
    "background goes from #ffffff to the theme's #eef2f7. A change of rendering awaits the "
    "interface review (docs/ETAT.md, section 5)."
)

# Guards on a name the manager does not hold that are deliberately left as they are. Each entry
# is a prefix of the report line, with the reason.
ALLOWED: dict[str, str] = {
    "certus/ui/certus_design_ui_worker.py::WorkerManager guards 'allow_growth_check'": (
        "Reading the checkbox on the window caps the global optimization as soon as the topology "
        "growth is ticked, which it is by default (`needle_coupled`): the default budget of the "
        "global phase changes. Owner decision (docs/ETAT.md, section 5)."
    ),
    "certus/ui/certus_design_ui_layout.py::LayoutManager guards 'spectrum_plot'": _PLOT_THEME,
    "certus/ui/certus_design_ui_layout.py::LayoutManager guards 'profile_plot'": _PLOT_THEME,
    "certus/ui/certus_design_ui_layout.py::LayoutManager guards 'nk_plot'": _PLOT_THEME,
    "certus/ui/certus_design_ui_layout.py::LayoutManager guards 'color_plot'": _PLOT_THEME,
    "certus/ui/certus_design_ui_layout.py::LayoutManager guards 'plot_convergence'": _PLOT_THEME,
}


def _assigned_self_attributes(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
            for target in targets:
                names.update(
                    x.attr
                    for x in ast.walk(target)
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id == "self"
                )
        elif (
            isinstance(sub, ast.Call)
            and getattr(sub.func, "id", "") == "setattr"
            and len(sub.args) >= 2
            and isinstance(sub.args[0], ast.Name)
            and sub.args[0].id == "self"
            and isinstance(sub.args[1], ast.Constant)
            and isinstance(sub.args[1].value, str)
        ):
            names.add(sub.args[1].value)
    return names


def _held_names(cls: ast.ClassDef) -> set[str]:
    held = _assigned_self_attributes(cls)
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            held.add(node.name)
        elif isinstance(node, ast.Assign):
            held.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            held.add(node.target.id)
    return held


def _is_manager(cls: ast.ClassDef) -> bool:
    if any(not (isinstance(base, ast.Name) and base.id == "object") for base in cls.bases):
        return False
    return bool(_assigned_self_attributes(cls) & DELEGATES)


def _guards_on_self(cls: ast.ClassDef) -> list[tuple[str, int]]:
    return [
        (node.args[1].value, node.lineno)
        for node in ast.walk(cls)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") in ("getattr", "hasattr")
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "self"
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ]


def _swept_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "certus/*.py"], capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout
    return sorted(out.split())


def _unheld_guards() -> tuple[set[str], int]:
    found: set[str] = set()
    managers = 0
    for path in _swept_files():
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if not _is_manager(cls):
                continue
            managers += 1
            held = _held_names(cls)
            for name, _line in _guards_on_self(cls):
                if not name.startswith("__") and name not in held:
                    found.add(f"{path}::{cls.name} guards '{name}'")
    return found, managers


def test_no_manager_guards_a_name_it_does_not_hold() -> None:
    found, managers = _unheld_guards()

    assert managers >= 8, f"the sweep found only {managers} managers: it no longer sees them"
    unexpected = sorted(x for x in found if not any(x.startswith(prefix) for prefix in ALLOWED))
    assert unexpected == [], (
        "a manager guards a name that only its window holds; read it on `self.ui`:\n  " + "\n  ".join(unexpected)
    )


def test_every_allowed_guard_is_still_there() -> None:
    found, _managers = _unheld_guards()

    stale = sorted(prefix for prefix in ALLOWED if not any(x.startswith(prefix) for x in found))
    assert stale == [], "fixed since: remove them from ALLOWED:\n  " + "\n  ".join(stale)


def test_the_sweep_sees_the_defect_it_looks_for() -> None:
    """A control: a manager written with the defect is reported."""
    source = (
        "class Manager:\n"
        "    def __init__(self, ui):\n"
        "        self.ui = ui\n"
        "    def run(self):\n"
        "        return getattr(self, 'stopped', False) or hasattr(self, 'box')\n"
    )
    [cls] = [n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)]

    assert _is_manager(cls)
    assert {name for name, _ in _guards_on_self(cls)} - _held_names(cls) == {"stopped", "box"}
