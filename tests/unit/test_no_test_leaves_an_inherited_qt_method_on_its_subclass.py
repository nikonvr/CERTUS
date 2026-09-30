"""The guard against a test that "restores" an inherited Qt method by assignment (tests/qt_leaks.py).

Measured 2026-09-30, the first time the UI and headless suites ran in one process: `tests/headless/test_index.py`
failed on `box.exec()` with "first argument of unbound method must have type 'QDialog'", because an earlier UI test
had done `original = QMessageBox.exec ... QMessageBox.exec = original`. The autouse fixture of `tests/conftest.py`
now fails the test that does it. These tests check the check: what it sees, what it repairs, and what it lets
through (`monkeypatch` restores an inherited method properly).
"""

from __future__ import annotations

import pytest
from qt_leaks import INHERITED_QT_METHODS, leaked_inherited_methods, repair

from PyQt6 import QtWidgets


def test_the_pristine_qt_classes_carry_none_of_the_inherited_methods() -> None:
    assert leaked_inherited_methods(QtWidgets) == []


def test_restoring_an_inherited_method_by_assignment_is_seen_and_repaired(qapp) -> None:
    original = QtWidgets.QMessageBox.exec  # what the leaking test did: read from the class...
    QtWidgets.QMessageBox.exec = original  # ...and put back "to restore it"
    try:
        assert leaked_inherited_methods(QtWidgets) == ["QMessageBox.exec"]
        box = QtWidgets.QMessageBox()
        with pytest.raises(TypeError, match="unbound method"):
            box.exec()  # the victim's error: the method no longer binds to the box
        box.deleteLater()
    finally:
        repair(leaked_inherited_methods(QtWidgets), QtWidgets)

    assert leaked_inherited_methods(QtWidgets) == []


def test_monkeypatch_restores_an_inherited_method_by_deleting_it(monkeypatch) -> None:
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: 0)
    assert leaked_inherited_methods(QtWidgets) == ["QMessageBox.exec"]  # local while it is patched, as expected

    monkeypatch.undo()

    assert leaked_inherited_methods(QtWidgets) == []


def test_the_pristine_values_are_those_of_the_installed_pyqt() -> None:
    """The table is measured, not assumed: if a PyQt update makes a class define one of them itself, this fails
    and the table is corrected, instead of every test being accused."""
    for cls, names in INHERITED_QT_METHODS.items():
        assert not any(name in vars(getattr(QtWidgets, cls)) for name in names), cls
