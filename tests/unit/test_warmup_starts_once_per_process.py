"""The background JIT warmup starts once per process, and only once the application is up.

bootstrap_app started a new warmup thread at every call, and create_module_environment calls it
at the import of every application script and of nine library modules. Measured 2026-09-29,
threads started while importing each entry script: DESIGN 4, INDEX 7, INDEX SPLINE, RE and
STRAT 2. Those threads imported modules while the main thread was still importing others, and
the import system could deadlock: `_DeadlockError: deadlock detected by
_ModuleLock('scipy.linalg.cython_lapack')` in an INDEX run of the CI (2026-09-28). Importing now
starts nothing; init_certus_app, called by every application once its imports are done, starts
the warmup through start_jit_warmup, and a second call finds it registered. RE and DESIGN
start their own QThread warmups instead of the global one in a frozen workqueue process.
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import certus.core.certus_core as certus_core

ROOT = Path(__file__).resolve().parents[2]
PROBE = """
import importlib
importlib.import_module("CERTUS_INDEX")
import certus.core.certus_core as core
print(core._WarmupRegistry.thread is None)
"""


@pytest.fixture
def recorded(monkeypatch):
    """Threads the warmup would start, recorded instead of started."""
    monkeypatch.setattr(certus_core._WarmupRegistry, "thread", None)
    monkeypatch.setattr(certus_core._WarmupRegistry, "started", False, raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    started = []

    class _Recorder:
        def __init__(self, target=None, **kwargs):
            self._target = target

        def start(self):
            started.append(self._target.__name__)

        def is_alive(self):
            return False

    monkeypatch.setattr(threading, "Thread", _Recorder)
    return started


def test_bootstrapping_a_module_starts_no_warmup(recorded) -> None:
    certus_core.bootstrap_app(certus_core.__file__, runtime=object())
    certus_core.bootstrap_app(certus_core.__file__, runtime=object())

    assert recorded == []


def test_the_warmup_starts_once(recorded) -> None:
    certus_core.start_jit_warmup()
    certus_core.start_jit_warmup()

    assert recorded == ["_bg_warmup"]


def test_importing_an_entry_script_starts_no_warmup() -> None:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT, env=env, timeout=600)
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip().splitlines()[-1] == "True"


def test_re_boots_with_only_its_qthread_warmup(monkeypatch) -> None:
    import CERTUS_RE

    events = []

    class App:
        def exec(self):
            return 0

    class Window:
        def __init__(self):
            events.append("RE warmup")

        def show(self):
            pass

    def init_app(*args, **kwargs):
        assert kwargs.get("jit_warmup") is False, "RE already starts its own QThread warmup"
        events.append("Qt app")
        return App()

    monkeypatch.setattr(CERTUS_RE, "init_certus_app", init_app)
    monkeypatch.setattr(CERTUS_RE, "CertusREApp", Window)
    monkeypatch.setattr(CERTUS_RE, "open_command_line_file", lambda window: None)

    with pytest.raises(SystemExit) as exited:
        CERTUS_RE.main()

    assert exited.value.code == 0
    assert events == ["Qt app", "RE warmup"]


def test_design_boots_with_only_its_qthread_warmup(monkeypatch) -> None:
    import certus.ui.certus_splash as splash_module

    entry = runpy.run_path(str(ROOT / "CERTUS_DESIGN.py"), run_name="__test_design_entry__")
    entry_globals = entry["main"].__globals__
    events = []

    class App:
        @staticmethod
        def setHighDpiScaleFactorRoundingPolicy(policy):
            pass

        def __init__(self, args):
            pass

        def styleSheet(self):
            return ""

        def setStyleSheet(self, sheet):
            pass

        def exec(self):
            return 0

    class Splash:
        def showMessage(self, *args):
            pass

        def finish(self, window):
            pass

    class Window:
        def __init__(self):
            events.append("DESIGN warmup")

        def show(self):
            pass

    def init_app(*args, **kwargs):
        assert kwargs.get("jit_warmup") is False, "DESIGN already starts its own QThread warmup"
        events.append("Qt app")

    monkeypatch.setitem(entry_globals, "QApplication", App)
    monkeypatch.setitem(entry_globals, "CertusDesignApp", Window)
    monkeypatch.setitem(entry_globals, "init_certus_app", init_app)
    monkeypatch.setitem(entry_globals, "setup_module_logging", lambda *args, **kwargs: None)
    monkeypatch.setitem(entry_globals, "script_dir", str(ROOT))
    monkeypatch.setattr(entry_globals["CertusTheme"], "apply_to_app", lambda app: None)
    monkeypatch.setattr(splash_module, "create_splash", lambda message: Splash())
    monkeypatch.setattr(sys, "argv", ["CERTUS_DESIGN.py"])

    with pytest.raises(SystemExit) as exited:
        entry["main"]()

    assert exited.value.code == 0
    assert events == ["Qt app", "DESIGN warmup"]
