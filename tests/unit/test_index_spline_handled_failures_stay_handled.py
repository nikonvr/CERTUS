"""INDEX SPLINE: a failure the code catches is logged, not turned into AttributeError.

Three handlers of `_DataMixin` logged through `self.self.logger`: the window has no `self`
attribute, so each time the failure they catch happened — the substrate index of the « Data
TH » table, the RMSE of the manual delta-ns preview — the handler itself raised
AttributeError, and the table or the preview was lost instead of degrading as intended
(found on 2026-09-29 by reading every `self.name` that nothing defines).
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

import certus.spline.certus_index_spline_corridor_data as data_module
import certus.spline.certus_index_spline_corridors as corridors


class _Window(corridors._DataMixin):
    """The part of CertusIndexSplineApp these two methods read."""

    df = None
    sub_name = "BK7"

    def __init__(self) -> None:
        self.logger = logging.getLogger("test.index_spline.handled_failures")
        self.plotted: list[str] = []
        self.status = ""

    def _lam_piecewise_report_grid_nm(self, lo: float, hi: float) -> np.ndarray:
        return np.linspace(lo, hi, 5)


def _failing(*_args, **_kwargs):
    raise ValueError("measured failure")


def test_the_data_th_table_survives_a_substrate_lookup_failure(monkeypatch) -> None:
    # patched where the code LOOKS THE NAME UP: `_DataMixin` lives in its own module since S5.3 (the facade `corridors` re-exports the class)
    monkeypatch.setattr(data_module, "substrate_id_from_name", lambda name: 1)
    monkeypatch.setattr(data_module, "_get_substrate_n_array_spline", _failing)
    result = {"lam_nm": [400.0, 500.0, 600.0], "n_lam": [1.5, 1.49, 1.48], "k_lam": [0.0, 0.0, 0.0], "d_nm": 100.0}

    series = _Window()._prepare_data_th_tab_series(result)

    lam_g, _n, _k, d_g, ns_g, _t, _r = series
    assert lam_g.size == 5
    assert np.all(np.isnan(ns_g))
    assert np.all(d_g == 100.0)


class _Config:
    lam_nm = np.array([400.0, 500.0, 600.0])

    def replace(self, **_changes):
        return self


class _Label:
    def __init__(self, window: _Window) -> None:
        self.window = window

    def setText(self, text: str) -> None:
        self.window.status = text


def test_the_delta_ns_preview_survives_an_rmse_failure(monkeypatch) -> None:
    monkeypatch.setattr(data_module, "_sync_theoretical_tr_from_nk_dict", lambda *a, **k: None)
    monkeypatch.setattr(data_module, "spectral_mse_rmse_masked_from_nk", _failing)
    window = _Window()
    window._last_run_cfg = _Config()
    window._baseline_substrate_n_for_result = lambda seed, lam_override: (lam_override, np.full(lam_override.size, 1.52))
    window._plot_result = lambda result, plot_source: window.plotted.append(plot_source)
    window._refresh_data_table = lambda result_override: None
    window.lbl_status = _Label(window)
    window._format_post_optimization_status = lambda result, preview: "preview"
    window._post_optimization_ready_status = lambda text: text
    seed = {"lam_nm": [400.0, 500.0, 600.0], "n_lam": [1.5, 1.49, 1.48], "k_lam": [0.0, 0.0, 0.0], "d_nm": 100.0,
            "rmse": 0.5}

    assert window._apply_manual_substrate_offset_preview(seed, 0.01) is True

    assert window.plotted == ["manual_delta_ns_preview"]
    assert window._last_result["substrate_n_offset"] == pytest.approx(0.01)
    assert window._last_result["rmse"] == 0.5
