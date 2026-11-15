"""The displayed RE evaluation applies the backside column by column, like the RE worker (audit 2026-11-15, M-L6a).

A workbook with one column measured with the backside (BK) and one without (noBK) ticks the global backside box. The
evaluation worker grouped the targets by (angle, polarisation, include_backside) but computed every group with the
global flag: the noBK curve shown next to the measurement carried a backside the fit never used.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from certus.workers import certus_spectral_workers as sw


class _Material:
    _is_tabular = True

    def __init__(self, n: complex) -> None:
        self._n = n

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        return np.full(len(wls), self._n, dtype=np.complex128)


def _target(include_backside: bool) -> SimpleNamespace:
    return SimpleNamespace(angle=8.0, pol="s", include_backside=include_backside, valid=lambda: True)


def test_a_no_backside_column_is_evaluated_without_the_backside(qapp) -> None:
    wls = np.linspace(450.0, 750.0, 31)
    ep = np.array([80.0, 120.0])
    cfg = {
        "mats": {"H": _Material(2.3 + 0j), "L": _Material(1.46 + 0j), "Substrate": _Material(1.52 + 0j)},
        "stack": [SimpleNamespace(mat="H"), SimpleNamespace(mat="L")],
        "ep": ep,
        "tgts": [],
        "oblique_mode": True,
        "oblique_tgts": [_target(True), _target(False)],
        "wls_vis": wls,
        "wls_optim": np.zeros(0),
        "back": True,
        "l0": 550.0,
    }
    received: list[dict] = []
    worker = sw.EvalWorker(cfg)
    worker.signals.finished.connect(received.append)
    worker.run()
    assert received, "the evaluation worker returned nothing"
    spectra = received[0]["spectra_vis"]

    n_front_T = np.ascontiguousarray(np.array([np.full(31, 2.3 + 0j), np.full(31, 1.46 + 0j)]).T)
    n_sub = np.full(31, 1.52 + 0j)
    r_front, t_front = sw.calc_spectrum_oblique_vectorized(wls, n_front_T, ep, n_sub, 8.0, "s")
    r_back, t_back = sw.calc_spectrum_oblique_backside_vectorized(wls, n_front_T, ep, n_sub, 8.0, "s")
    assert np.max(np.abs(r_back - r_front)) > 0.01, "the two references must differ for the test to mean anything"

    np.testing.assert_allclose(spectra[(8.0, "s", True)]["R"], r_back, rtol=1e-12)
    np.testing.assert_allclose(spectra[(8.0, "s", True)]["T"], t_back, rtol=1e-12)
    np.testing.assert_allclose(spectra[(8.0, "s", False)]["R"], r_front, rtol=1e-12)
    np.testing.assert_allclose(spectra[(8.0, "s", False)]["T"], t_front, rtol=1e-12)
