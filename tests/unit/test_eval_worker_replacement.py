"""Replacing a running evaluation must not destroy its QThread (D33).

`spectrum_eval_start_worker` overwrites `app.eval_worker`. When the previous evaluation is
still running, that assignment drops its last Python reference, Qt answers with a qFatal and
the whole process dies -- the operator loses the session without a message. The window is
real: DESIGN and RE re-evaluate on every edit, and the code already carries a generation id
precisely because evaluations overlap.

The first test is the mechanism, in a subprocess: dropping the reference kills the process,
retaining it does not. It is the negative control of the fix, and it does not depend on the
application.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: The two branches differ ONLY by the retention call: the import is done first in both, or
#: its cost (pyqtgraph, numpy) would outlast the worker and the thread would already be over.
_PROBE = """
import sys
sys.path.insert(0, {root!r})
from PyQt6.QtCore import QThread, QCoreApplication, QTimer
from certus.ui.certus_spectrum_eval_ui import _retain_until_finished

class Slow(QThread):
    def run(self):
        QThread.msleep(1500)

app = QCoreApplication(sys.argv)
w = Slow()
w.start()
assert w.isRunning()

{retain}

w = None            # the assignment of start_worker, reduced to its essence
import gc; gc.collect()

# Let Qt deliver the posted events -- this is where the qFatal lands.
QTimer.singleShot(2500, app.quit)
app.exec()
print("SURVIVED", flush=True)
"""

_RETAIN = "assert _retain_until_finished(w) is True"


def _run(retain: str) -> subprocess.CompletedProcess:
    code = _PROBE.format(root=str(ROOT), retain=retain)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )


@pytest.mark.unit
def test_dropping_a_running_worker_kills_the_process() -> None:
    """Negative control: without retention, Qt aborts. If this ever passes, Qt changed."""
    run = _run(retain="")
    assert run.returncode != 0 or "SURVIVED" not in run.stdout, (
        "a QThread destroyed while running no longer kills the process: "
        f"rc={run.returncode} out={run.stdout!r} err={run.stderr[-400:]!r}"
    )


@pytest.mark.unit
def test_retaining_it_keeps_the_process_alive() -> None:
    run = _run(retain=_RETAIN)
    assert run.returncode == 0 and "SURVIVED" in run.stdout, (
        f"rc={run.returncode} out={run.stdout!r} err={run.stderr[-800:]!r}"
    )


@pytest.mark.unit
def test_a_finished_worker_is_not_retained(qapp) -> None:
    """Nothing is kept needlessly: the registry stays empty on the normal path."""
    from PyQt6.QtCore import QThread

    from certus.ui.certus_spectrum_eval_ui import _ORPHAN_EVAL_WORKERS, _retain_until_finished

    class Instant(QThread):
        def run(self) -> None:
            return None

    worker = Instant()
    worker.start()
    assert worker.wait(5000)
    before = len(_ORPHAN_EVAL_WORKERS)
    assert _retain_until_finished(worker) is False
    assert _retain_until_finished(None) is False
    assert len(_ORPHAN_EVAL_WORKERS) == before


@pytest.mark.unit
def test_the_registry_empties_once_the_thread_finishes(qapp) -> None:
    from PyQt6.QtCore import QThread

    from certus.ui.certus_spectrum_eval_ui import _ORPHAN_EVAL_WORKERS, _retain_until_finished

    class Slow(QThread):
        def run(self) -> None:
            QThread.msleep(200)

    worker = Slow()
    worker.start()
    assert _retain_until_finished(worker) is True
    assert worker in _ORPHAN_EVAL_WORKERS
    assert worker.wait(10000)
    # `finished` is queued to the GUI thread: the registry empties when events are processed.
    for _ in range(200):
        qapp.processEvents()
        if worker not in _ORPHAN_EVAL_WORKERS:
            break
        QThread.msleep(10)
    assert worker not in _ORPHAN_EVAL_WORKERS


@pytest.mark.unit
def test_start_worker_retains_before_replacing() -> None:
    """The call sites: the retention must precede the assignment, or it protects nothing."""
    src = (ROOT / "certus/ui/certus_spectrum_eval_ui.py").read_text(encoding="utf-8")
    retain = src.index("_retain_until_finished(getattr(app")
    assign = src.index("app.eval_worker = EvalWorker(cfg)")
    assert retain < assign
