"""No class that is not a widget hands itself to Qt as a parent.

Qt refuses a parent that is not a QWidget with a TypeError, raised only when the line runs.
When the DESIGN window was split into managers (c79316b, 2026-06-13), three calls kept
`self` as the parent while `self` had become a manager: STOP, « Export to Excel » and
« Stack information » raised TypeError until 2026-09-29.

The sweep runs in a fresh interpreter: every class of certus/ and of the root scripts that
is neither a QObject nor a base of one (a mixin's `self` is the widget) is read, and every
call whose first argument or `parent=` is `self` is resolved in the module: a PyQt6 callee,
or a project function whose first parameter is `parent`, `widget` or `window`, is reported.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SWEEP = r'''
import ast, importlib, inspect, os, subprocess, sys, textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())
from PyQt6.QtCore import QObject

files = [f for f in subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout.split()
         if f.startswith("certus/") or "/" not in f]


def resolve(expr, glb):
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name) or expr.id not in glb:
        return None
    obj = glb[expr.id]
    for p in reversed(parts):
        try:
            obj = getattr(obj, p)
        except Exception:
            return None
    return obj


def takes_parent(obj):
    mod = getattr(obj, "__module__", "") or ""
    if mod.startswith("PyQt6"):
        return True
    if mod.startswith(("certus", "CERTUS")) and callable(obj):
        try:
            params = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            return False
        if inspect.isclass(obj) and params[:1] == ["self"]:
            params = params[1:]
        return bool(params) and params[0] in ("parent", "widget", "window", "parent_widget")
    return False


classes = {}
for f in sorted(files):
    mod = importlib.import_module(f[:-3].replace("/", ".").removesuffix(".__init__"))
    for name, cls in vars(mod).items():
        if inspect.isclass(cls) and cls.__module__ == mod.__name__:
            classes[cls] = mod
qobjects = [c for c in classes if issubclass(c, QObject)]
checked = 0
for cls, mod in classes.items():
    if issubclass(cls, QObject) or any(cls in q.__mro__ for q in qobjects):
        continue
    checked += 1
    for attr, fn in vars(cls).items():
        fn = getattr(fn, "__func__", fn)
        if not inspect.isfunction(fn):
            continue
        try:
            lines, start = inspect.getsourcelines(fn)
            tree = ast.parse(textwrap.dedent("".join(lines)))
        except (OSError, TypeError, SyntaxError):
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            first = bool(n.args) and isinstance(n.args[0], ast.Name) and n.args[0].id == "self"
            keyword = any(k.arg == "parent" and isinstance(k.value, ast.Name) and k.value.id == "self" for k in n.keywords)
            if (first or keyword) and takes_parent(resolve(n.func, fn.__globals__)):
                print(f"PARENT {cls.__name__}.{attr}: {ast.unparse(n.func)}(self, ...)")
print(f"CHECKED {checked}")
'''


def test_no_class_but_a_widget_is_handed_to_qt_as_a_parent() -> None:
    out = subprocess.run([sys.executable, "-c", SWEEP], capture_output=True, text=True, cwd=ROOT, timeout=900)
    assert out.returncode == 0, out.stderr[-1500:]
    lines = out.stdout.splitlines()
    [checked] = [line for line in lines if line.startswith("CHECKED ")]
    assert int(checked.split()[1]) > 100, checked
    assert [line for line in lines if line.startswith("PARENT ")] == []
