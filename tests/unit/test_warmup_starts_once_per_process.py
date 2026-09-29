"""The background JIT warmup starts once per process, not once per module that bootstraps.

bootstrap_app started a new warmup thread at every call, and create_module_environment calls it
at the import of every application script and of nine library modules. Measured 2026-09-29,
threads started while importing each entry script: DESIGN 4, INDEX 7, INDEX SPLINE, RE and
STRAT 2, each precompiling the same numba kernels. The first call starts the warmup; the next
ones find it registered.
"""

from __future__ import annotations

import sys
import threading

import pytest

import certus.core.certus_core as certus_core


@pytest.fixture(autouse=True)
def _fresh_registry(monkeypatch):
    monkeypatch.setattr(certus_core._WarmupRegistry, "thread", None)
    monkeypatch.setattr(certus_core._WarmupRegistry, "started", False, raising=False)


def test_two_bootstraps_start_one_warmup(monkeypatch) -> None:
    started = []

    class _Recorder:
        def __init__(self, target=None, daemon=None, **kwargs):
            self._target = target

        def start(self):
            started.append(self._target.__name__)

        def is_alive(self):
            return False

    monkeypatch.setattr(threading, "Thread", _Recorder)
    monkeypatch.setattr(sys, "path", list(sys.path))
    runtime = object()
    module_file = certus_core.__file__  # a module of the package: sys.path is left alone
    certus_core.bootstrap_app(module_file, runtime=runtime)
    certus_core.bootstrap_app(module_file, runtime=runtime)

    assert started == ["_bg_warmup"]
