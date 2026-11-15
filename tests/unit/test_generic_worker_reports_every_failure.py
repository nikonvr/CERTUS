"""A GenericWorker whose function fails always says so (audit 2026-11-15, M-L3b).

``GenericWorker.run`` caught the numerical faults only. A KeyError, IndexError, TypeError or AttributeError raised by
the computed function left the thread without ``finished`` nor ``error``: the window that waits for one of them to
re-enable its Run button stayed busy for ever.
"""

from __future__ import annotations

import pytest

from certus.workers.certus_base_workers import GenericWorker


def _raising(exc: type[BaseException]):
    def func():
        raise exc("audit")

    return func


@pytest.mark.parametrize("exc", [ValueError, RuntimeError, KeyError, IndexError, TypeError, AttributeError])
def test_a_failing_function_emits_error(qapp, exc) -> None:
    errors: list[tuple] = []
    finished: list[object] = []
    worker = GenericWorker(_raising(exc))
    worker.signals.error.connect(errors.append)
    worker.signals.finished.connect(finished.append)

    worker.run()

    assert not finished
    assert len(errors) == 1, f"{exc.__name__} reached no signal: the window stays busy"
    assert errors[0][0] is exc


def test_a_successful_function_emits_finished(qapp) -> None:
    errors: list[tuple] = []
    finished: list[object] = []
    worker = GenericWorker(lambda: 7)
    worker.signals.error.connect(errors.append)
    worker.signals.finished.connect(finished.append)

    worker.run()

    assert finished == [7]
    assert not errors
