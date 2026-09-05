"""SMOOTHER must report a file it cannot open, not crash on it.

The save path was hardened on 2026-09-04 (certus_curve_smoother.py:409 catches
``(*NUMERICAL_FAULT_EXCEPTIONS, OSError)``), but the LOAD path kept catching
NUMERICAL_FAULT_EXCEPTIONS alone - a tuple of RuntimeError, FloatingPointError,
ValueError, ZeroDivisionError, OverflowError and LinAlgError, with no OSError in
it (certus/core/certus_core.py:993).

So the single most common failure of all - the operator still has the workbook
open in Excel, which raises PermissionError - escaped as a raw traceback instead
of the QMessageBox that every other error path shows.
"""

from __future__ import annotations

import pytest

MODULE = "certus.utils.certus_curve_smoother"


@pytest.mark.parametrize(
    "raised",
    [
        PermissionError(13, "The process cannot access the file"),  # workbook open in Excel
        FileNotFoundError(2, "No such file or directory"),  # moved between dialog and read
        OSError(5, "Input/output error"),  # dead network share
    ],
)
def test_load_reports_an_unreadable_workbook(qapp, monkeypatch, raised) -> None:
    """No OSError may escape load_file: the operator must get a message."""
    import importlib

    mod = importlib.import_module(MODULE)

    def _boom(*_a, **_k):
        raise raised

    monkeypatch.setattr(mod, "open_measurement_excel_interactive", _boom)

    shown: list[str] = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: shown.append(str(a[2]) if len(a) > 2 else "")),
    )

    win = mod.CurveSmootherGUI()
    try:
        win.load_file()
    finally:
        win.close()

    assert shown, f"{type(raised).__name__} escaped load_file instead of reaching a QMessageBox"
