import pytest

from certus.core.certus_design_workers_dto import ColorWorkerRequest
from certus.workers.certus_design_workers import ColorWorker


@pytest.mark.unit
def test_color_worker_init() -> None:
    req = ColorWorkerRequest(cfg={"test": True})
    worker = ColorWorker(req)
    assert worker.cfg == {"test": True}
    assert hasattr(worker, "signals")


@pytest.mark.unit
def test_needle_worker_init() -> None:
    from certus.core.certus_design_workers_dto import NeedleWorkerRequest
    from certus.workers.certus_design_workers import NeedleWorker
    req = NeedleWorkerRequest(cfg={"test": True})
    worker = NeedleWorker(req)
    assert worker.cfg == {"test": True}
    assert hasattr(worker, "signals")
