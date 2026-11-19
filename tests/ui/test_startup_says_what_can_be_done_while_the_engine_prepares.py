"""While its computing engine prepares, a window says what the operator can do, and when computing starts.

UX audit 2026-11-18, item 5: DESIGN and RE said "Waiting for JIT compilation..." and "Compiling JIT kernels...",
INDEX SPLINE "System ready. JIT Warmup complete.": the vocabulary of the implementation, and nothing about what one
may do meanwhile (load a measurement) or when a computation can start.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

TECHNICAL = ("JIT", "Numba", "kernel", "compil", "warm")


def _plain(text: str) -> bool:
    return not any(word.lower() in text.lower() for word in TECHNICAL)


@pytest.fixture
def toasts(monkeypatch) -> list[str]:
    from certus.ui import certus_base_app_engine_mixin as engine

    shown: list[str] = []
    monkeypatch.setattr(engine, "show_toast", lambda _parent, text, *_a, **_k: shown.append(text))
    return shown


def test_a_computation_asked_too_early_says_it_will_start_by_itself(monkeypatch) -> None:
    from PyQt6.QtCore import QTimer

    from certus.ui.certus_spectrum_eval_ui import spectrum_eval_run_preamble

    monkeypatch.setattr(QTimer, "singleShot", lambda *_a, **_k: None)
    app = Mock(_warmup_done=False, _spectrum_eval_jit_wait_logged=False)

    assert spectrum_eval_run_preamble(app, lambda: None) is False

    [(message, _level)] = [c.args for c in app.log.call_args_list]
    assert _plain(message), message
    assert "start by itself once it is ready" in message, message


@pytest.mark.parametrize("slot", ["_on_warmup_done", "_on_numba_ready_ui"])
def test_ready_says_computing_can_start_in_plain_words(toasts, slot) -> None:
    from certus.ui.certus_base_app_engine_mixin import CertusAppEngineMixin

    app = Mock()
    getattr(CertusAppEngineMixin, slot)(app)

    [toast] = toasts
    assert _plain(toast), toast
    assert "can start" in toast, toast
    for label in (app.status_label, app._warmup_status_label.return_value):
        for call in label.setText.call_args_list:
            assert _plain(call.args[0]), call.args[0]


def _design():
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


def _re():
    from CERTUS_RE import CertusREApp

    return CertusREApp()


def _strat():
    from certus.ui.certus_strat_ui import CertusStratApp

    return CertusStratApp()


@pytest.mark.parametrize("make", [_design, _re, _strat], ids=["DESIGN", "RE", "STRAT"])
def test_while_preparing_the_window_says_what_can_be_done_meanwhile(qapp, make) -> None:
    window = make()
    try:
        # The engine reports ready through a queued signal: until the event loop runs, the window is preparing.
        text = window.status_label.text()
        assert _plain(text), text
        assert "load a measurement" in text, text
    finally:
        window.close()
