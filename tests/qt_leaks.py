"""Qt methods that a class must inherit, never define itself: what a test leaves behind when it "restores" one.

Measured 2026-09-30, the first time the UI and headless suites ran in ONE process (the coverage measurement):
`tests/headless/test_index.py` failed with `TypeError: exec(self): first argument of unbound method must have
type 'QDialog'`. An earlier UI test had saved `original = QMessageBox.exec`, replaced it, and restored it with
`QMessageBox.exec = original`. Read from the class, an inherited method is the unbound `QDialog.exec`; assigned
back, it becomes an attribute of `QMessageBox` itself and is no longer bound to the box: every later
`box.exec()` fails. The suites passed in their usual separate runs because nothing after that test opened a real
message box; the first order that put one after it failed, far from the cause.

`monkeypatch.setattr` restores it properly (it reads the class `__dict__`, finds nothing, and deletes the
attribute on undo). This module names the attributes that must NOT appear in the `__dict__` of a class, so that
the test that leaks one is the one that fails.

The pristine values are those of PyQt6 6.x, measured with `"exec" in vars(QMessageBox)` in a fresh interpreter.
"""

from __future__ import annotations

import sys

#: class name -> methods it inherits from a base class and must not carry in its own `__dict__`.
INHERITED_QT_METHODS: dict[str, tuple[str, ...]] = {
    "QMessageBox": ("exec", "show"),
    "QMainWindow": ("exec", "show"),
    "QDialog": ("show",),
    "QApplication": ("show",),
    "QWidget": ("exec",),
}


def leaked_inherited_methods(widgets=None) -> list[str]:
    """`Class.method` for every inherited Qt method that some code has made local to its class."""
    widgets = widgets or sys.modules.get("PyQt6.QtWidgets")
    if widgets is None:  # Qt was never imported: nothing can have been patched
        return []
    return [
        f"{cls}.{name}"
        for cls, names in INHERITED_QT_METHODS.items()
        for name in names
        if name in vars(getattr(widgets, cls))
    ]


def repair(leaked: list[str], widgets=None) -> None:
    """Delete what `leaked_inherited_methods` found, so that the leak costs one test and not the rest of the run."""
    widgets = widgets or sys.modules["PyQt6.QtWidgets"]
    for entry in leaked:
        cls, name = entry.split(".")
        delattr(getattr(widgets, cls), name)
