"""Two FIELD minors of the audit of 2026-11-15 (L3-m6, L5-m3).

L3-m6: the tolerance Monte Carlo and the optimisation of FIELD drew from the global np.random, unseeded: two identical
       analyses gave two yields, and another module drawing in between shifted them (owner's decision: a seed).
L5-m3: a synthesis chains workers from the `finished` signal, emitted inside run() before the thread ends; when the
       previous thread was still running, _start_worker returned silently and the window stayed busy for good.
"""

from __future__ import annotations

import inspect

from certus.ui.certus_field_workers_mixin import CertusFieldWorkersMixin
from certus.workers import certus_field_workers as fw


def test_l3_m6_field_never_draws_from_the_global_random_state() -> None:
    source = inspect.getsource(fw)
    assert "np.random.normal(" not in source
    assert "np.random.uniform(" not in source
    assert "default_rng(" in source


def test_l3_m6_the_field_pglobal_run_is_seeded() -> None:
    source = inspect.getsource(fw)
    assert "with_overrides(random_seed=FIELD_RANDOM_SEED)" in source


class _Still:
    def __init__(self, finishes: bool) -> None:
        self.finishes = finishes
        self.waited: list[int] = []

    def isRunning(self) -> bool:
        return True

    def wait(self, ms: int) -> bool:
        self.waited.append(ms)
        return self.finishes


class _Button:
    def __init__(self) -> None:
        self.enabled = False

    def setEnabled(self, value: bool) -> None:
        self.enabled = value


class _Window(CertusFieldWorkersMixin):
    def __init__(self, worker) -> None:
        self.worker = worker
        self.btn_calc, self.btn_opt, self.btn_mc = _Button(), _Button(), _Button()
        self._synthesis_active = True
        self._is_running = True
        self.logged: list[str] = []
        self.logger = type("L", (), {"warning": lambda _s, msg, *a: self.logged.append(msg % a if a else msg)})()


def test_l5_m3_a_worker_still_ending_is_waited_for_not_ignored() -> None:
    previous = _Still(finishes=False)
    win = _Window(previous)
    request = type("R", (), {"action": "calculate"})()

    win._start_worker(request)

    assert previous.waited, "the previous thread was not waited for"
    assert win.btn_calc.enabled, "the window stayed busy"
    assert win.btn_opt.enabled
    assert win.btn_mc.enabled
    assert win._synthesis_active is False
    assert win.logged
