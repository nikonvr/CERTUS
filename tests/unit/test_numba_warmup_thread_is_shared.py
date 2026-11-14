"""The threaded Numba warm-up of INDEX, INDEX SPLINE, METAL and STRAT lives once, in the engine mixin of the base class.

Five windows each carried their own `_warmup_numba_thread_runner` (audit A §2.2, chantier 07): the same connect,
status text, daemon thread and guarded emission, with the kernels to compile as the only real difference. The mixin
now owns the runner; a window writes `_compile_numba_kernels` and, when it must, the failure policy.
"""

from __future__ import annotations

import logging

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from certus.ui.certus_base_app_engine_mixin import CertusAppEngineMixin


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _Window(QObject, CertusAppEngineMixin):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()

    def __init__(self, compile_fn) -> None:
        super().__init__()
        self.logger = logging.getLogger("CERTUS.test_warmup")
        self.status_label = _Label()
        self._compile = compile_fn
        self.seen: list[str] = []
        self.sig_numba_ready.connect(lambda: self.seen.append("ready"))
        self.sig_numba_error.connect(lambda: self.seen.append("error"))

    def _compile_numba_kernels(self) -> None:
        self._compile()


def _raise(exc: BaseException):
    def f() -> None:
        raise exc

    return f


def test_a_compiled_warmup_emits_ready_only(qapp) -> None:
    w = _Window(lambda: None)
    w._warmup_numba_thread_runner()
    assert w.seen == ["ready"]


def test_a_numerical_fault_is_logged_and_emits_error(qapp, caplog) -> None:
    w = _Window(_raise(ValueError("bad shape")))
    with caplog.at_level(logging.ERROR, logger="CERTUS.test_warmup"):
        w._warmup_numba_thread_runner()
    assert w.seen == ["error"]
    assert "Numba warmup failed: bad shape" in caplog.text


def test_a_fault_outside_the_window_list_propagates(qapp) -> None:
    w = _Window(_raise(KeyError("x")))
    with pytest.raises(KeyError):
        w._warmup_numba_thread_runner()
    assert w.seen == []


def test_an_emission_on_a_destroyed_window_is_dropped() -> None:
    class _Dead:
        def emit(self) -> None:
            raise RuntimeError("wrapped C/C++ object has been deleted")

    CertusAppEngineMixin._emit_warmup_signal(_Dead())


def test_the_slots_write_the_named_label_and_skip_a_missing_one(qapp) -> None:
    w = _Window(lambda: None)
    w._on_numba_error_ui()
    assert w.status_label.text == "JIT Init Error"
    w.WARMUP_STATUS_LABEL = "lbl_status"
    w._on_numba_error_ui()
    assert w.status_label.text == "JIT Init Error"


def test_one_warmup_runner_is_left_in_certus() -> None:
    import ast
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    files = subprocess.run(
        ["git", "ls-files", "certus/*.py", "CERTUS_*.py"], capture_output=True, text=True, cwd=root, check=True
    ).stdout.splitlines()
    owners = sorted(
        f"{path}:{node.lineno}"
        for path in files
        for node in ast.walk(ast.parse((root / path).read_text(encoding="utf-8-sig")))
        if isinstance(node, ast.FunctionDef) and node.name == "_warmup_numba_thread_runner"
    )
    assert [owner.split(":")[0] for owner in owners] == ["certus/ui/certus_base_app_engine_mixin.py"], owners
