"""A DESIGN optimization that carries a run id logs it, instead of raising TypeError.

OptimWorker.run builds its logger with get_structured_logger(..., trace=...), a keyword the
function has never taken: every run with a run id raised TypeError before its first line of
work. None did, because the window never passed its run id to the worker (found on
2026-09-29 while wiring it); this test comes first so that wiring it breaks nothing.
"""

from __future__ import annotations

import logging

import pytest


def test_a_traced_optimization_logs_its_run_id(qapp, caplog) -> None:
    from certus.workers.certus_design_workers import OptimWorker

    worker = OptimWorker({"run_id": "run-42"})

    # The configuration holds nothing to optimize: the run stops at its first read of it.
    with caplog.at_level(logging.INFO, logger="CERTUS"), pytest.raises(KeyError):
        worker.run()

    [start] = [r for r in caplog.records if "Starting optimization worker" in r.getMessage()]
    assert start.run_id == "run-42"
