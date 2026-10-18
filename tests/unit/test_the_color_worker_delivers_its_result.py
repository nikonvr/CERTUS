"""The Monte-Carlo color worker delivers its result.

Until 2026-10-18 `ColorWorker.run` passed `run_context=` to `ColorWorkerResult.success`, which has no such
parameter. The TypeError came after the whole Monte-Carlo, escaped `run` (it is not in NUMERICAL_FAULT_EXCEPTIONS)
and neither `finished` nor `error` was emitted. Nothing ran `run`: `test_certus_design_workers.py` builds the worker
only, and `test_design_runs_carry_their_run_id.py` replaces it with a stub.

The three calculations the worker calls (the front spectrum and the two colorimetry kernels) are replaced by
NumPy stand-ins: the defect is in the construction of the result, and the kernels have their own tests. Everything
else is the real path (request DTO, parameters, materials, Monte-Carlo loop, result DTO, signal). The stand-ins also
keep this test from reading the Numba cache, whose entries can crash the process when a kernel is reloaded
(reports/AUDIT_SUITE_CERTUS_2026-10-18.md, C18).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_workers_dto import ColorWorkerRequest
from certus.workers.certus_design_workers import ColorWorker
from certus_physics.structures import Layer

_WORKER = "certus.workers.certus_design_workers"


class _Material:
    """A constant index: all the worker asks of a material is `get_nk(wls)`."""

    def __init__(self, n: float) -> None:
        self.n = n

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        return np.full(wls.shape, self.n, dtype=complex)


def _flat_spectrum(wls, _n_layers, _thicknesses, _n_sub):
    """(T, R) as the front-spectrum kernel returns them."""
    return np.zeros_like(wls), np.full_like(wls, 0.1)


def _xyz(_wls, _reflectance):
    return np.array([0.3, 0.3, 0.3])


def _lab(_xyz_value):
    return np.array([50.0, 0.0, 0.0])


@pytest.mark.unit
def test_the_color_worker_emits_its_result_and_no_error(qapp, monkeypatch) -> None:
    monkeypatch.setattr(f"{_WORKER}.calc_spectrum_front", _flat_spectrum)
    monkeypatch.setattr(f"{_WORKER}.xyz_from_spectrum", _xyz)
    monkeypatch.setattr(f"{_WORKER}.xyz_to_lab", _lab)
    request = ColorWorkerRequest.from_legacy(
        {
            "stack": [Layer("H", 1.0)],
            "ep": [100.0],
            "mats": {"H": _Material(2.3), "substrate": _Material(1.52)},
            "n": 5,
            "sigma": 1.0,
            "run_seed": 1,
            "run_id": "run-7",
            "run_context": object(),  # what the DESIGN window passes
        }
    )
    worker = ColorWorker(request)
    finished: list[dict] = []
    errors: list[str] = []
    worker.signals.finished.connect(finished.append)
    worker.signals.error.connect(errors.append)

    worker.run()

    assert errors == []
    [payload] = finished
    assert payload["ok"] is True
    assert len(payload["lab_nom"]) == 3
    assert np.asarray(payload["labs"]).shape == (5, 3)
    # The identity of the run travels with the result through its trace.
    assert payload["run_id"] == "run-7"
