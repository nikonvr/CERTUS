from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from CERTUS_INDEX_SPLINE import (
    CertusIndexSplineApp,
    _K_PLOT_YMAX,
    _K_PLOT_YMIN,
    _apply_fixed_log_k_axis,
    _interp_series_at_sigma_knots,
)


class _PlotItem:
    def setTitle(self, *_args, **_kwargs) -> None:
        pass

    def setXRange(self, *_args, **_kwargs) -> None:
        pass


class _PlotWidget:
    def __init__(self) -> None:
        self.plotItem = _PlotItem()
        self.cleared = False
        self.auto_ranged = False
        self.added_items: list[tuple[object, object | None]] = []
        self.log_modes: list[tuple[tuple, dict]] = []
        self.y_ranges: list[tuple[float, float, float]] = []

    def clear(self) -> None:
        self.cleared = True

    def autoRange(self) -> None:
        self.auto_ranged = True

    def setLabel(self, *_args, **_kwargs) -> None:
        pass

    def addItem(self, item, ignoreBounds=None) -> None:
        self.added_items.append((item, ignoreBounds))

    def setLogMode(self, *args, **kwargs) -> None:
        self.log_modes.append((args, kwargs))

    def setYRange(self, lo: float, hi: float, padding: float = 0.0) -> None:
        self.y_ranges.append((float(lo), float(hi), float(padding)))


class _FakeTextItem:
    def __init__(self, *args, html: str | None = None, anchor=None, **_kwargs) -> None:
        self.html = html
        self.anchor = anchor
        self.pos = None
        self.z = None

    def setZValue(self, value) -> None:
        self.z = value

    def setPos(self, x, y) -> None:
        self.pos = (x, y)


def test_interp_series_at_sigma_knots_returns_lambda_sorted_points() -> None:
    lam = np.array([400.0, 500.0, 600.0, 700.0], dtype=np.float64)
    y = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    sigma_knots = 1.0 / np.array([700.0, 500.0, 600.0], dtype=np.float64)

    lam_k, y_k = _interp_series_at_sigma_knots(lam, y, sigma_knots)

    assert np.allclose(lam_k, [500.0, 600.0, 700.0])
    assert np.allclose(y_k, [0.2, 0.3, 0.4])


def test_apply_fixed_log_k_axis_forces_requested_bounds() -> None:
    plot_k = _PlotWidget()

    _apply_fixed_log_k_axis(plot_k)

    assert plot_k.log_modes[-1] == ((False, True), {})
    # PyQtGraph utilise l’échelle log en coordonnées log10 sur l’axe Y.
    assert plot_k.y_ranges[-1] == (
        float(np.log10(_K_PLOT_YMIN)),
        float(np.log10(_K_PLOT_YMAX)),
        0.0,
    )


def test_plot_result_adds_large_t_knot_markers(monkeypatch) -> None:
    recorded_scatter: list[dict[str, object]] = []

    def _fake_scatter(plot_w, x, y, *, color, name, symbol_size=5):
        recorded_scatter.append(
            {
                "plot": plot_w,
                "x": np.asarray(x, dtype=np.float64).copy(),
                "y": np.asarray(y, dtype=np.float64).copy(),
                "color": color,
                "name": name,
                "symbol_size": symbol_size,
            }
        )

    monkeypatch.setattr("CERTUS_INDEX_SPLINE._plot_spectrum_raw_scatter", _fake_scatter)
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.pg.TextItem", _FakeTextItem)

    plot_t = _PlotWidget()
    plot_n = _PlotWidget()
    plot_k = _PlotWidget()

    app = SimpleNamespace(
        df=None,
        lbl_status=SimpleNamespace(setText=lambda *_args, **_kwargs: None),
        logger=None,
        plot_T=plot_t,
        plot_n=plot_n,
        plot_k=plot_k,
        _transform_spectrum_x=lambda lam_nm: (np.asarray(lam_nm, dtype=np.float64), "lambda (nm)"),
        _add_curve=lambda *_args, **_kwargs: True,
        _plot_corridor_tab=lambda *_args, **_kwargs: None,
        _plot_corridor_rmse_tab=lambda *_args, **_kwargs: None,
        _plot_nl_tab=lambda *_args, **_kwargs: None,
        _apply_spectrum_x_axis_label=lambda *_args, **_kwargs: None,
        _apply_spectrum_plot_title=lambda *_args, **_kwargs: None,
        _update_rmse_fit_region_overlay=lambda *_args, **_kwargs: None,
        _corridor_rmse_profile_win=None,
    )
    result = {
        "lam_nm": np.array([400.0, 500.0, 600.0, 700.0], dtype=np.float64),
        "t_theo": np.array([0.15, 0.25, 0.35, 0.45], dtype=np.float64),
        "n_lam": np.array([2.0, 2.1, 2.2, 2.3], dtype=np.float64),
        "k_lam": np.array([1e-3, 2e-3, 3e-3, 4e-3], dtype=np.float64),
        "sigma_knots": 1.0 / np.array([700.0, 500.0, 600.0], dtype=np.float64),
        "d_nm": 123.0,
    }

    CertusIndexSplineApp._plot_result(app, result)

    knot_calls = [call for call in recorded_scatter if call["name"] == "T model knots"]
    assert len(knot_calls) == 1
    assert knot_calls[0]["plot"] is plot_t
    assert knot_calls[0]["symbol_size"] == 11
    assert np.allclose(knot_calls[0]["x"], [500.0, 600.0, 700.0])
    assert np.allclose(knot_calls[0]["y"], [0.25, 0.35, 0.45])
    assert len(plot_t.added_items) == 1
    badge, ignore_bounds = plot_t.added_items[0]
    assert ignore_bounds is True
    assert isinstance(badge, _FakeTextItem)
    assert "d = 123.00 nm" in str(badge.html)
    assert plot_k.log_modes[-1] == ((False, True), {})
    # PyQtGraph utilise l’échelle log en coordonnées log10 sur l’axe Y.
    assert plot_k.y_ranges[-1] == (
        float(np.log10(_K_PLOT_YMIN)),
        float(np.log10(_K_PLOT_YMAX)),
        0.0,
    )
