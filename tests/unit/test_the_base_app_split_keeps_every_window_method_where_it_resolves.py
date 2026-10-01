"""`CertusBaseApp` was a class of 2 311 lines and 99 methods; 84 of them moved to seven mixins (audit v2, plan S5.3).

Every window of the suite inherits that class, so what must not change is where a name RESOLVES. It was checked once with a checksum of the
bytecode of every attribute of the nine window classes, before and after (508 to 720 attributes each, none different); this file pins what
that checksum cannot, the shape of the split:

* each mixin comes AFTER `QMainWindow` in the bases (a method that a Qt class also defines would be masked by it: the Qt overrides of the
  window, `closeEvent`, `eventFilter`, `timerEvent`, `dragEnterEvent`, `dropEvent`, and its two signals stay in the class);
* a method defined by a mixin is defined by NO other class of the MRO, so no order of the bases can change which one a window calls;
* no mixin calls `super()` (a moved method would reach a different next class: the tool refuses them, the test keeps them out);
* no mixin imports the module of the class it came from (that is a cycle in waiting);
* the module of the class is no longer a long file.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "certus" / "ui"
MIXINS = {
    "certus_base_app_config_mixin": "CertusAppConfigMixin",
    "certus_base_app_engine_mixin": "CertusAppEngineMixin",
    "certus_base_app_stack_mixin": "CertusAppFrontStackMixin",
    "certus_base_app_plot_mixin": "CertusAppPlotMixin",
    "certus_base_app_undo_mixin": "CertusAppUndoMixin",
    "certus_base_app_run_mixin": "CertusAppRunStateMixin",
    "certus_base_app_info_mixin": "CertusAppStackInfoMixin",
}
STAYS_IN_THE_CLASS = ("closeEvent", "eventFilter", "timerEvent", "dragEnterEvent", "dropEvent", "sig_numba_ready", "sig_numba_error")


def base_app():
    return importlib.import_module("certus.ui.certus_base_app")


def mixin_class(module_name: str):
    return getattr(importlib.import_module(f"certus.ui.{module_name}"), MIXINS[module_name])


def test_the_class_takes_its_seven_mixins_after_the_qt_class():
    cls = base_app().CertusBaseApp
    mro = cls.__mro__
    qt = next(k for k in mro if k.__name__ == "QMainWindow")
    for module_name, name in MIXINS.items():
        mixin = mixin_class(module_name)
        assert mixin.__name__ == name
        assert mro.count(mixin) == 1, name
        assert mro.index(qt) < mro.index(mixin), f"{name} precedes QMainWindow: it would mask the Qt methods it shares a name with"
        assert getattr(base_app(), name) is mixin, f"{name} is no longer importable from certus_base_app"


def test_the_qt_overrides_and_the_signals_stay_in_the_class():
    cls = base_app().CertusBaseApp
    for name in STAYS_IN_THE_CLASS:
        assert name in vars(cls), f"{name} left CertusBaseApp"


@pytest.mark.parametrize("module_name", MIXINS)
def test_a_method_of_a_mixin_is_what_the_class_resolves(module_name):
    cls = base_app().CertusBaseApp
    mixin = mixin_class(module_name)
    methods = {k: v for k, v in vars(mixin).items() if inspect.isfunction(v)}
    assert len(methods) >= 4, f"{mixin.__name__} holds {len(methods)} methods"
    for name, function in methods.items():
        assert getattr(cls, name) is function, name


def test_no_name_of_a_mixin_is_defined_by_another_class_of_the_mro():
    cls = base_app().CertusBaseApp
    owners: dict[str, list[str]] = {}
    for klass in cls.__mro__:
        for name in vars(klass):
            if not (name.startswith("__") and name.endswith("__")):
                owners.setdefault(name, []).append(klass.__name__)
    for module_name in MIXINS:
        mixin = mixin_class(module_name)
        for name in vars(mixin):
            if name.startswith("__") and name.endswith("__"):
                continue
            assert owners[name] == [mixin.__name__], f"{name} is defined by {owners[name]}: the order of the bases would decide"


@pytest.mark.parametrize("module_name", MIXINS)
def test_no_mixin_calls_super_or_imports_the_module_it_came_from(module_name):
    tree = ast.parse((UI / f"{module_name}.py").read_text(encoding="utf-8-sig"))
    calls = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "super"]
    assert not calls, f"super() at {calls}: it would reach another class than before the move"
    imports = [
        n.lineno
        for n in ast.walk(tree)
        if (isinstance(n, ast.ImportFrom) and n.module == "certus.ui.certus_base_app")
        or (isinstance(n, ast.Import) and any(a.name == "certus.ui.certus_base_app" for a in n.names))
    ]
    assert not imports, f"{module_name} imports the module of the class it came from, at {imports}"


def test_the_module_of_the_class_is_no_longer_a_long_file():
    n = len((UI / "certus_base_app.py").read_text(encoding="utf-8-sig").splitlines())
    assert n <= 1500, n
