"""Audit M-L3b: which exceptions raised by the computed function reach a GenericWorker signal.

Runs the real `certus.workers.certus_base_workers.GenericWorker` (offscreen) on functions that raise, and counts the
`finished` / `error` signals the UI waits for (`certus_index_spline_execution` re-enables Run on them).
    python reports/audit_code_2026-11-15/preuves/p_generic_worker_signaux.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from certus.workers.certus_base_workers import GenericWorker  # noqa: E402

app = QCoreApplication(sys.argv)
sys.excepthook = lambda *a: print(f"    excepthook: {a[0].__name__}")


def make(exc):
    def f():
        if exc is not None:
            raise exc("audit")
        return 1
    return f


for exc in (None, ValueError, RuntimeError, KeyError, IndexError, TypeError, AttributeError):
    got = {"finished": 0, "error": 0}
    w = GenericWorker(make(exc))
    w.signals.finished.connect(lambda *_, g=got: g.__setitem__("finished", g["finished"] + 1))
    w.signals.error.connect(lambda *_, g=got: g.__setitem__("error", g["error"] + 1))
    w.start()
    w.wait(5000)
    for _ in range(5):
        app.processEvents()
    name = "no exception" if exc is None else exc.__name__
    verdict = "UI released" if got["finished"] + got["error"] else "NO SIGNAL: UI stays busy"
    print(f"{name:15s} finished={got['finished']} error={got['error']}  -> {verdict}")
