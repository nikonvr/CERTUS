"""The hub says why a module died (audit UX-06, plan S6.3).

`on_process_finished` ignored the exit codes 1, 15 and -1 as "the user closed it", and for any other code kept the
FIRST 200 characters of the module's error output: the header of a traceback, never the error. An uncaught exception
exits with code 1, so a module that failed to start left nothing at all. A native crash was worse:
`errorOccurred(Crashed)` reached a handler that told the user "Could not start" of a module that had run.

The tests that matter run REAL child processes: what the fix depends on is what Qt reports for a real exit, and a
double that returns what the author expects proves nothing about it.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "CERTUS_STRAT.py", line 159, in <module>\n'
    "    main()\n"
    '  File "CERTUS_STRAT.py", line 120, in main\n'
    "    window = CertusStratApp()\n"
    "ValueError: no such wavelength: 1550\n"
)

RAISES = "raise ValueError('no such wavelength: 1550')\n"
EXITS_NORMALLY = "print('bye')\n"
EXITS_WITH_ONE = "raise SystemExit(1)\n"
# 0xC0000005 is the status of an access violation; Qt reads that range of exit codes as a crash on Windows.
CRASHES = (
    "import os, signal, sys\n"
    "if sys.platform == 'win32':\n"
    "    os._exit(-1073741819)\n"
    "os.kill(os.getpid(), signal.SIGSEGV)\n"
)
SLEEPS = "import time\ntime.sleep(120)\n"


# =============================================================================
# What is said: the pure part
# =============================================================================


def test_the_error_is_the_last_line_of_the_traceback() -> None:
    """The hub kept the first 200 characters: `Traceback (most recent call last): File "..."`."""
    from CERTUS_HUB import describe_module_stop

    stop = describe_module_stop("CERTUS_STRAT", 1, False, TRACEBACK)

    assert stop is not None
    assert stop.cause == "ValueError: no such wavelength: 1550"
    assert stop.details.splitlines()[-1] == "ValueError: no such wavelength: 1550"
    assert stop.details.splitlines()[0].startswith("Traceback")
    assert "CERTUS_STRAT" in stop.headline and "exit code 1" in stop.headline
    assert not stop.crashed


def test_a_normal_exit_says_nothing_whatever_the_module_wrote() -> None:
    from CERTUS_HUB import describe_module_stop

    assert describe_module_stop("CERTUS_STRAT", 0, False, "QFont::setPointSize: Point size <= 0\n") is None


@pytest.mark.parametrize("code", [1, 15, -1])
def test_a_module_stopped_from_outside_says_nothing_when_it_wrote_nothing(code: int) -> None:
    """Task Manager's "End task" exits with 1, `kill` with 15: the user did that, and knows."""
    from CERTUS_HUB import describe_module_stop

    assert describe_module_stop("CERTUS_STRAT", code, False, "") is None
    assert describe_module_stop("CERTUS_STRAT", code, False, "  \r\n\n") is None


@pytest.mark.parametrize("code", [1, 15, -1])
def test_the_same_codes_say_it_when_the_module_wrote_an_error(code: int) -> None:
    """Code 1 IS how an uncaught exception ends: it was the code the hub explained away."""
    from CERTUS_HUB import describe_module_stop

    stop = describe_module_stop("CERTUS_STRAT", code, False, TRACEBACK)

    assert stop is not None and stop.cause.startswith("ValueError")


def test_a_module_killed_on_purpose_says_nothing_although_the_system_calls_it_a_crash() -> None:
    """On Unix `kill` ends a process with signal 15 and Qt reports a CrashExit: the user did it, and knows."""
    from CERTUS_HUB import describe_module_stop

    assert describe_module_stop("CERTUS_STRAT", 15, True, "") is None


def test_a_crash_is_reported_even_without_a_word_on_the_error_output() -> None:
    """A native crash has no traceback: the status is all there is, and it is shown as Windows names it."""
    from CERTUS_HUB import describe_module_stop

    stop = describe_module_stop("CERTUS_STRAT", -1073741819, True, "")

    assert stop is not None and stop.crashed
    assert "crashed" in stop.headline and "0xC0000005" in stop.headline
    assert stop.cause == "It wrote no error message."
    assert stop.details == ""


def test_a_crash_after_an_error_line_keeps_the_line() -> None:
    from CERTUS_HUB import describe_module_stop

    stop = describe_module_stop("CERTUS_STRAT", 139, True, "Fatal Python error: Segmentation fault\n")

    assert stop is not None and stop.cause == "Fatal Python error: Segmentation fault"
    assert "0x" not in stop.headline, "a POSIX exit code needs no hexadecimal: it is not an NTSTATUS"


def test_only_the_end_of_a_long_output_is_kept() -> None:
    from CERTUS_HUB import STDERR_TAIL_LINES, describe_module_stop

    output = "".join(f"line {i}\n" for i in range(100))

    stop = describe_module_stop("CERTUS_STRAT", 2, False, output)

    assert stop is not None
    assert stop.details.splitlines() == [f"line {i}" for i in range(100 - STDERR_TAIL_LINES, 100)]
    assert stop.cause == "line 99"


def test_a_very_long_last_line_is_cut_and_blank_lines_are_dropped() -> None:
    from CERTUS_HUB import describe_module_stop

    stop = describe_module_stop("CERTUS_STRAT", 2, False, "first\r\n\r\n" + "x" * 5000 + "\r\n\r\n")

    assert stop is not None
    assert len(stop.cause) <= 300 and stop.cause.endswith("...")
    assert stop.details.splitlines()[0] == "first", "Windows line endings and blank lines must not reach the dialog"
    assert len(stop.details.splitlines()) == 2


# =============================================================================
# What the hub does: real processes
# =============================================================================


@pytest.fixture
def dialogs(monkeypatch):
    """The static dialogs of the hub, recorded: a real one would block the suite for good (nobody answers it).

    The `hub` fixture depends on it, so that a regression shows as a failure and not as a hang: on the code that
    this file was written against, killing a module in the teardown opened a real "Could not start" box.
    """
    from PyQt6.QtWidgets import QMessageBox

    shown: list[tuple[str, str, str]] = []

    def record(kind):
        def fake(_parent, title, text, *_a, **_k):
            shown.append((kind, title, text))
            return QMessageBox.StandardButton.Ok

        return fake

    for kind in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, kind, record(kind))
    # A box built by hand and run with `exec` (the hub's confirmation) blocks just the same: it is answered "no".
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(("exec", box.windowTitle(), box.text())) or 0)
    return shown


@pytest.fixture
def hub(qapp, dialogs):
    from PyQt6.QtCore import Qt

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win._closing = True  # what the hub is about to do to its modules is not what the tests look at
        for process in list(win.active_processes):  # a test that fails must not leave its child running
            process.kill()
            process.waitForFinished(5000)
        win.active_processes.clear()
        win.close()


def wait_until(predicate, timeout_s: float = 30.0) -> bool:
    from PyQt6.QtCore import QCoreApplication, QEventLoop

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return True
        time.sleep(0.01)
    return False


def run_module(hub, tmp_path: Path, source: str) -> None:
    """Start `source` as a module of the hub and let it end: the hub has handled its exit when this returns."""
    script = tmp_path / "CERTUS_PROBE.py"
    script.write_text(source, encoding="utf-8")
    hub.launch_module(str(script))
    assert hub.active_processes, "the hub did not register the module it started"
    assert wait_until(lambda: not hub.active_processes), "the module did not end, or the hub never handled its end"


def boxes_of(hub):
    from PyQt6.QtWidgets import QMessageBox

    return hub.findChildren(QMessageBox)


def test_a_module_that_raises_is_explained(hub, dialogs, tmp_path) -> None:
    """The scene of the audit: the module dies at start-up with a traceback, and the hub said nothing."""
    run_module(hub, tmp_path, RAISES)

    boxes = boxes_of(hub)
    assert len(boxes) == 1, "a module that died on an exception left the user without a word"
    box = boxes[0]
    assert "CERTUS_PROBE" in box.text() and "exit code 1" in box.text()
    assert box.informativeText() == "ValueError: no such wavelength: 1550"
    assert "Traceback" in box.detailedText() and "raise ValueError" in box.detailedText()
    log = hub.log_text.toPlainText()
    assert "CERTUS_PROBE exited with code 1" in log and "ValueError: no such wavelength: 1550" in log
    assert not dialogs, f"the hub used a blocking dialog: {dialogs}"
    for box in boxes:
        box.close()


def test_the_message_does_not_block_the_hub(hub, dialogs, tmp_path) -> None:
    """The other modules are still running: the message is a window of its own, not a modal wall."""
    from PyQt6.QtCore import Qt

    run_module(hub, tmp_path, RAISES)

    (box,) = boxes_of(hub)
    assert box.windowModality() == Qt.WindowModality.NonModal
    assert box.isVisible()
    box.close()


def test_a_module_that_exits_normally_opens_no_dialog(hub, dialogs, tmp_path) -> None:
    run_module(hub, tmp_path, EXITS_NORMALLY)

    assert not boxes_of(hub) and not dialogs
    assert "CERTUS_PROBE exited normally." in hub.log_text.toPlainText()


def test_a_module_stopped_from_outside_opens_no_dialog(hub, dialogs, tmp_path) -> None:
    """Exit code 1 with nothing on the error output: the user ended it, and the log says how."""
    run_module(hub, tmp_path, EXITS_WITH_ONE)

    assert not boxes_of(hub) and not dialogs
    assert "CERTUS_PROBE exited with code 1." in hub.log_text.toPlainText()


def test_a_module_that_crashes_is_reported_as_a_crash_not_as_a_launch_failure(hub, dialogs, tmp_path) -> None:
    """`errorOccurred(Crashed)` used to end in "Could not start CERTUS_x" for a module that had been running."""
    run_module(hub, tmp_path, CRASHES)

    assert not dialogs, f"the hub called a crash a launch failure: {dialogs}"
    (box,) = boxes_of(hub)
    assert "crashed" in box.text() and "CERTUS_PROBE" in box.text()
    assert box.informativeText() == "It wrote no error message."
    box.close()


def test_a_module_that_cannot_start_still_says_so(hub, dialogs, tmp_path, monkeypatch) -> None:
    """The message that the crash used to borrow belongs to this case, and it must stay."""
    script = tmp_path / "CERTUS_PROBE.py"
    script.write_text(EXITS_NORMALLY, encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "no_such_python.exe"))

    hub.launch_module(str(script))

    assert wait_until(lambda: dialogs), "a module that could not start left the user without a word"
    assert dialogs[0][:2] == ("warning", "Launch Error") and "CERTUS_PROBE" in dialogs[0][2]
    assert not hub.active_processes
    assert not boxes_of(hub), "a module that never ran has no exit to explain"


# =============================================================================
# Closing the hub stops the modules: that is not a crash
# =============================================================================


def start_sleeping_module(hub, tmp_path: Path):
    script = tmp_path / "CERTUS_SLEEPER.py"
    script.write_text(SLEEPS, encoding="utf-8")
    hub.launch_module(str(script))
    (process,) = hub.active_processes
    assert process.waitForStarted(20_000), "the module did not start"
    return process


def test_the_modules_the_hub_stops_on_purpose_are_not_reported_as_crashes(hub, dialogs, tmp_path) -> None:
    from PyQt6.QtCore import QProcess
    from PyQt6.QtGui import QCloseEvent

    process = start_sleeping_module(hub, tmp_path)

    event = QCloseEvent()
    hub.closeEvent(event)
    wait_until(lambda: False, timeout_s=0.5)  # let a late `finished` reach the hub

    assert event.isAccepted()
    assert process.state() == QProcess.ProcessState.NotRunning
    assert not boxes_of(hub), "stopping a module on purpose was reported as if it had crashed"
    assert not dialogs, f"closing the hub opened a dialog while it stopped its own modules: {dialogs}"
