"""Every `self.name` a class reads, calls included, is defined somewhere.

Reading an attribute that nothing defines raises AttributeError only when that line runs, and
no linter sees it. The sweeps of 2026-09-29 found four defects. FIELD's post-optimization cleanup
called a method of the stack panel on the window itself (AttributeError after every
optimization that left a thin inner layer, since the cleanup was written); an INDEX SPLINE
handler, connected to nothing, called a worker method that never existed; three INDEX SPLINE
error handlers logged through `self.self.logger` and raised in place of the failure they
caught; the DESIGN colour worker delegated five unused methods to an attribute never set.

The sweep runs in a fresh interpreter, since it imports every module of certus/ and the root
scripts. Each application window is read through its whole MRO, mixins included; every other
class outside the mixins through its own MRO. A read is reported when its name is not an
attribute of the class, not an annotated field, not assigned anywhere in the project nor in
the source of a library base class, and not guarded by `hasattr(self, "name")` or
`getattr(self, "name", ...)` in the same function.
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


def assigned_in(source):
    """Attribute names that `source` assigns: `x.name = ...` or `setattr(x, "name", ...)`."""
    names = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                names.update(x.attr for x in ast.walk(target) if isinstance(x, ast.Attribute))
        elif (isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "setattr"
              and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)):
            names.add(n.args[1].value)
    return names


files = [f for f in subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout.split()
         if f.startswith("certus/") or "/" not in f]
assigned = set()
for f in files:
    assigned |= assigned_in(Path(f).read_text(encoding="utf-8-sig"))
library_sources = {}


def project(klass):
    return klass.__module__.startswith(("certus", "CERTUS"))


def known_names(cls):
    """Class attributes, annotated fields, and what the library base classes assign."""
    names = set(dir(cls))
    for klass in cls.__mro__:
        try:
            names.update(annotationlib.get_annotations(klass, format=annotationlib.Format.FORWARDREF))
        except Exception:
            pass
        if klass is object or project(klass):
            continue
        try:
            source_file = inspect.getsourcefile(klass)
        except TypeError:
            continue  # compiled: PyQt6
        if source_file and source_file not in library_sources:
            try:
                library_sources[source_file] = assigned_in(Path(source_file).read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                library_sources[source_file] = set()
        names |= library_sources.get(source_file, set())
    return names


def undefined_reads(cls):
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
                if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
                        and isinstance(n.value, ast.Name) and n.value.id == "self"):
                    if n.attr not in names and n.attr not in assigned and n.attr not in guarded:
                        found.add((f"{klass.__name__}.{attr}", n.attr))
    return found


report = {}
for spec in WINDOWS:
    module, name = spec.split(":")
    for where, read in undefined_reads(getattr(importlib.import_module(module), name)):
        report.setdefault(f"{where} -> {read}", []).append(name)
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
    # pydantic's __getattr__ create no attribute: those classes stay in the sweep.
    if any("__getattr__" in vars(k) for k in cls.__mro__
           if k is not object and not k.__module__.startswith(("PyQt6", "pydantic"))):
        continue
    for where, read in undefined_reads(cls):
        report.setdefault(f"{where} -> {read}", []).append(name)
print("SWEEP=" + json.dumps({k: sorted(set(v)) for k, v in sorted(report.items())}))
'''

# Hooks of CertusBaseApp that only the windows providing them reach. Each line says why.
ONLY_WHERE_PROVIDED = {
    # The base layout: FIELD, DESIGN and RE build through it and define both panels; INDEX and
    # INDEX SPLINE override _build_ui; STRAT and METAL never call it.
    "CertusBaseApp._build_ui -> _build_left_panel",
    "CertusBaseApp._build_ui -> _build_right_panel",
    # Reached from the front-layer table and its QWOT/thickness columns: DESIGN and RE only.
    "CertusBaseApp._schedule_eval -> run_eval",
    "CertusBaseApp._update_thickness_display -> _get_materials",
    "CertusBaseApp._ep_nm_to_qwot -> _get_materials",
    "CertusBaseApp.eventFilter -> _paste_from_excel",
    # Reached in oblique mode only, which only DESIGN and RE set.
    "CertusBaseApp._auto_scale_spectrum_y -> _get_oblique_tgts",
    "CertusBaseApp._rebuild_target_scatter -> _get_oblique_tgts",
}


def test_every_attribute_read_on_self_is_defined_somewhere() -> None:
    out = subprocess.run([sys.executable, "-c", SWEEP], capture_output=True, text=True, cwd=ROOT, timeout=900)
    assert out.returncode == 0, out.stderr[-1500:]
    [line] = [x for x in out.stdout.splitlines() if x.startswith("SWEEP=")]
    report = json.loads(line.removeprefix("SWEEP="))

    undefined = {read: classes for read, classes in report.items() if read not in ONLY_WHERE_PROVIDED}
    assert undefined == {}, "attributes that nothing defines:\n" + "\n".join(
        f"  {read}   (in {', '.join(classes)})" for read, classes in undefined.items()
    )
    stale = ONLY_WHERE_PROVIDED - set(report)
    assert not stale, f"no longer found, remove from ONLY_WHERE_PROVIDED: {sorted(stale)}"
