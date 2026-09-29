"""Every `self.name(...)` call reaches a method that exists.

A call to a method that no class defines raises AttributeError only when it runs, and no
linter sees it. The first sweep, on 2026-09-29, found two: FIELD's post-optimization cleanup
called a method of the stack panel on the window itself (AttributeError after every
optimization that left a thin inner layer, since the cleanup was written), and an INDEX
SPLINE handler, connected to nothing, called a worker method that never existed.

The sweep runs in a fresh interpreter, since it imports every module of certus/ and the root
scripts. Each application window is read through its whole MRO, mixins included; every other
class outside the mixins through its own MRO. A call is reported when its name is not an
attribute of the class, not an annotated field, not assigned anywhere in the project, and not
guarded by `hasattr(self, "name")` or `getattr(self, "name", ...)` in the same function.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SWEEP = r'''
import annotationlib, ast, importlib, inspect, json, os, subprocess, sys, textwrap
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())

WINDOWS = [
    "certus.ui.certus_design_ui:CertusDesignApp",
    "certus.ui.certus_field_ui:CertusFieldApp",
    "certus.ui.certus_index_ui:CertusIndexApp",
    "certus.ui.certus_index_spline_ui:CertusIndexSplineApp",
    "CERTUS_RE:CertusREApp",
    "certus.ui.certus_strat_ui:CertusStratApp",
    "certus.metal.certus_metal_single_app:CertusMetalSingleApp",
    "certus.metal.certus_metal_bilayer_app:CertusMetalBilayerApp",
    "CERTUS_HUB:CertusHub",
]

files = [f for f in subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout.split()
         if f.startswith("certus/") or "/" not in f]
assigned = set()
for f in files:
    for n in ast.walk(ast.parse(Path(f).read_text(encoding="utf-8-sig"))):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                assigned.update(x.attr for x in ast.walk(target) if isinstance(x, ast.Attribute))
        elif (isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "setattr"
              and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)):
            assigned.add(n.args[1].value)


def project(klass):
    return klass.__module__.startswith(("certus", "CERTUS"))


def known_names(cls):
    names = set(dir(cls))
    for klass in cls.__mro__:
        try:
            names.update(annotationlib.get_annotations(klass, format=annotationlib.Format.FORWARDREF))
        except Exception:
            pass
    return names


def dead_calls(cls):
    names = known_names(cls)
    found = set()
    for klass in cls.__mro__:
        if not project(klass):
            continue
        for attr, fn in vars(klass).items():
            fn = getattr(fn, "__func__", fn)
            if attr.startswith("__annotate") or not inspect.isfunction(fn):
                continue
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            except (OSError, TypeError, SyntaxError):
                continue
            guarded = {n.args[1].value for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("hasattr", "getattr")
                       and len(n.args) >= 2 and isinstance(n.args[0], ast.Name) and n.args[0].id == "self"
                       and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)}
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"):
                    name = n.func.attr
                    if name not in names and name not in assigned and name not in guarded:
                        found.add((f"{klass.__name__}.{attr}", name))
    return found


report = {}
for spec in WINDOWS:
    module, name = spec.split(":")
    for where, called in dead_calls(getattr(importlib.import_module(module), name)):
        report.setdefault(f"{where} -> {called}", []).append(name)
classes = {}
for f in sorted(files):
    module = importlib.import_module(f[:-3].replace("/", ".").removesuffix(".__init__"))
    for name, cls in vars(module).items():
        if inspect.isclass(cls) and cls.__module__ == module.__name__ and "Mixin" not in name:
            classes[cls] = name
for cls, name in classes.items():
    if any(other is not cls and cls in other.__mro__ for other in classes):
        continue  # a base: its hooks are defined, and read, in its subclasses
    # Attributes resolved at run time (pyqtgraph's PlotWidget, lazy facades). QObject's and
    # pydantic's __getattr__ create no method: those classes stay in the sweep.
    if any("__getattr__" in vars(k) for k in cls.__mro__
           if k is not object and not k.__module__.startswith(("PyQt6", "pydantic"))):
        continue
    for where, called in dead_calls(cls):
        report.setdefault(f"{where} -> {called}", []).append(name)
print("SWEEP=" + json.dumps({k: sorted(set(v)) for k, v in sorted(report.items())}))
'''

# Hooks of CertusBaseApp that only the windows providing them reach. Each line says why.
ONLY_WHERE_PROVIDED = {
    # The base layout: FIELD, DESIGN and RE build through it and define both panels; INDEX and
    # INDEX SPLINE override _build_ui; STRAT and METAL never call it.
    "CertusBaseApp._build_ui -> _build_left_panel",
    "CertusBaseApp._build_ui -> _build_right_panel",
    # Reached from the front-layer table and its QWOT/thickness columns: DESIGN and RE only.
    "CertusBaseApp._update_thickness_display -> _get_materials",
    "CertusBaseApp._ep_nm_to_qwot -> _get_materials",
    "CertusBaseApp.eventFilter -> _paste_from_excel",
    # Reached in oblique mode only, which only DESIGN and RE set.
    "CertusBaseApp._auto_scale_spectrum_y -> _get_oblique_tgts",
    "CertusBaseApp._rebuild_target_scatter -> _get_oblique_tgts",
}


def test_self_calls_reach_a_method() -> None:
    out = subprocess.run([sys.executable, "-c", SWEEP], capture_output=True, text=True, cwd=ROOT, timeout=900)
    assert out.returncode == 0, out.stderr[-1500:]
    [line] = [x for x in out.stdout.splitlines() if x.startswith("SWEEP=")]
    report = json.loads(line.removeprefix("SWEEP="))

    dead = {call: classes for call, classes in report.items() if call not in ONLY_WHERE_PROVIDED}
    assert dead == {}, "calls to methods that no class defines:\n" + "\n".join(
        f"  {call}   (in {', '.join(classes)})" for call, classes in dead.items()
    )
    stale = ONLY_WHERE_PROVIDED - set(report)
    assert not stale, f"no longer found, remove from ONLY_WHERE_PROVIDED: {sorted(stale)}"
