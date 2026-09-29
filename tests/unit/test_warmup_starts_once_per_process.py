"""The background JIT warmup starts once per process, and only once the application is up.

bootstrap_app started a new warmup thread at every call, and create_module_environment calls it
at the import of every application script and of nine library modules. Measured 2026-09-29,
threads started while importing each entry script: DESIGN 4, INDEX 7, INDEX SPLINE, RE and
STRAT 2. Those threads imported modules while the main thread was still importing others, and
the import system could deadlock: `_DeadlockError: deadlock detected by
_ModuleLock('scipy.linalg.cython_lapack')` in an INDEX run of the CI (2026-09-28). Importing now
starts nothing; init_certus_app, called by every application once its imports are done, starts
the warmup through start_jit_warmup, and a second call finds it registered.
"""

from __future__ import annotations

import os
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
