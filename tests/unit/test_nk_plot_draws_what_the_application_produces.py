"""The n & k plot draws the columns the application produces, and nothing else (decision D62, audit v2 plan S5.2).

`CertusIndexPlotMixin._update_nk_plot` also carried branches for columns that no code of `certus/` ever puts in `df_results`: tolerance sweeps (`n_calc_005`...), a corridor around a
centre curve (`n_center`, `n_hi`, `n_lo`, `n_raw`...) and a reflection-only fit (`n_fit_R_only`...). The owner decided to delete them (383 lines became 143, complexity 36 became 9).
What the optimizers really give is `lambda`, `n_calc`, `k_calc` and, from the IR strategy, the transmission-only fit `n_fit_T_only` / `k_fit_T_only`. This file pins what is drawn from them,
with a real plot widget, and that the retired columns are ignored.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyqtgraph as pg
import pytest
from PyQt6.QtCore import Qt

from certus.ui import certus_index_ui_plot as module
from certus.ui.certus_index_ui_plot import CertusIndexPlotMixin
from certus.ui.certus_ui import CertusScientificPlot, CertusTheme

pytestmark = pytest.mark.usefixtures("qapp")

WL = np.array([500.0, 800.0, 1100.0, 1400.0, 1700.0, 2000.0])
N_CALC = np.array([1.50, 1.51, 1.52, 1.53, 1.54, 1.55])
K_CALC = np.array([0.0, 1e-9, 2e-8, 1e-6, 1e-3, 0.5])
K_PLOTTED = np.array([-7.0, -7.0, -7.0, -6.0, -3.0, np.log10(0.5)])  # below 1e-8 the floor, then log10 with a floor of 1e-7


class Recorder(logging.Logger):
    def __init__(self) -> None:
        super().__init__("recorder")
        self.errors: list[str] = []

    def error(self, msg, *args, **kwargs) -> None:  # type: ignore[override]
        self.errors.append(str(msg) % args if args else str(msg))


def frame(**columns) -> pd.DataFrame:
    data = {"lambda": WL, "n_calc": N_CALC.copy(), "k_calc": K_CALC.copy()}
    data.update(columns)
    return pd.DataFrame(data)


def result(*, source="C:/data/sample_A.xlsx", method="PGLOBAL + L-BFGS-B", lambda_max_fit=None, tlu=None):
    config = SimpleNamespace(source_file=source, lambda_max_fit=lambda_max_fit)
    return SimpleNamespace(config=config, optimal_thickness=1234.5678, optimization_stats={"method": method}, tlu_params=tlu)


def window():
    return SimpleNamespace(plot_nk=CertusScientificPlot(title="nk"), logger=Recorder())


def draw(df, res=None, win=None):
    win = win or window()
    CertusIndexPlotMixin._update_nk_plot(win, df["lambda"].values, df, res or result())
    return win


def n_curves(win) -> dict:
    return {item.opts.get("name"): item for item in win.plot_nk.plotItem.items if isinstance(item, pg.PlotDataItem)}


def k_curves(win) -> dict:
    return {item.opts.get("name"): item for item in win._vb_k.addedItems if isinstance(item, pg.PlotCurveItem)}


def pen_of(item):
    pen = pg.mkPen(item.opts["pen"])
    return pen.color().name(), pen.widthF(), pen.style()


def hex_of(color) -> str:
    return pg.mkColor(color).name()


def y_of(item) -> np.ndarray:
    return np.asarray(item.yData, dtype=float)


# --- the title and the n axis ---------------------------------------------------------------------------------------------------------------


def test_the_title_names_the_source_file_and_the_thickness():
    win = draw(frame())
    assert win.plot_nk.plotItem.titleLabel.text == "Optical Constants      sample_A      thickness = 1234.57 nm"


def test_when_the_source_file_cannot_be_read_the_title_keeps_the_thickness_only():
    class Broken:
        @property
        def source_file(self):
            raise ValueError("no such file name")

    res = result()
    res.config = Broken()
    win = draw(frame(), res)
    assert win.plot_nk.plotItem.titleLabel.text == "Optical Constants      thickness = 1234.57 nm"


def test_the_left_axis_is_the_index_n_in_the_primary_colour():
    win = draw(frame())
    axis = win.plot_nk.plotItem.getAxis("left")
    assert axis.labelText == "n"
    assert hex_of(axis.labelStyle["color"]) == hex_of(CertusTheme.PRIMARY)


# --- the curves --------------------------------------------------------------------------------------------------------------------------


def test_the_index_n_is_a_primary_line_of_width_three_named_after_the_measurement():
    win = draw(frame())
    curve = n_curves(win)["n (R+T)"]
    np.testing.assert_allclose(y_of(curve), N_CALC)
    np.testing.assert_allclose(np.asarray(curve.xData), WL)
    assert pen_of(curve) == (hex_of(CertusTheme.PRIMARY), 3.0, Qt.PenStyle.SolidLine)


def test_the_extinction_k_is_drawn_in_log10_on_the_right_axis_with_a_floor_below_1e_8():
    win = draw(frame())
    curve = k_curves(win)["k (R+T)"]
    np.testing.assert_allclose(y_of(curve), K_PLOTTED)
    assert pen_of(curve) == (hex_of(CertusTheme.WARNING), 3.0, Qt.PenStyle.SolidLine)


def test_the_curves_are_tracked_for_the_crosshair_in_this_order():
    win = draw(frame())
    assert [entry["name"] for entry in win.plot_nk._tracked_curves] == ["n (R+T)", "log10(k)"]


def test_the_transmission_only_fits_are_green_dashed_lines_tracked_too():
    win = draw(frame(n_fit_T_only=N_CALC + 0.01, k_fit_T_only=K_CALC.copy()))
    n_t = n_curves(win)["n (90% T)"]
    k_t = k_curves(win)["k (90% T)"]
    np.testing.assert_allclose(y_of(n_t), N_CALC + 0.01)
    np.testing.assert_allclose(y_of(k_t), K_PLOTTED)
    assert pen_of(n_t) == (hex_of("#10b981"), 2.0, Qt.PenStyle.DashLine)
    assert pen_of(k_t) == (hex_of("#10b981"), 2.0, Qt.PenStyle.DashLine)
    assert [entry["name"] for entry in win.plot_nk._tracked_curves] == ["n (R+T)", "n (90% T)", "log10(k)", "log10(k) (90% T)"]


def test_without_the_transmission_only_columns_there_is_no_such_curve():
    win = draw(frame())
    assert set(n_curves(win)) == {"n (R+T)"}
    assert set(k_curves(win)) == {"k (R+T)"}


LEGACY = {
    "n_calc_005": N_CALC,
    "n_calc_0025": N_CALC,
    "n_calc_001": N_CALC,
    "k_calc_005": K_CALC,
    "k_calc_0025": K_CALC,
    "k_calc_001": K_CALC,
    "n_center": N_CALC,
    "n_hi": N_CALC + 0.01,
    "n_lo": N_CALC - 0.01,
    "n_raw": N_CALC,
    "n_hi_2": N_CALC + 0.02,
    "n_lo_2": N_CALC - 0.02,
    "k_center": K_CALC,
    "k_hi": K_CALC + 1e-4,
    "k_lo": K_CALC,
    "k_raw": K_CALC,
    "k_hi_2": K_CALC + 2e-4,
    "k_lo_2": K_CALC,
    "n_fit_R_only": N_CALC,
    "k_fit_R_only": K_CALC,
}


@pytest.mark.parametrize("column", list(LEGACY))
def test_a_retired_column_adds_nothing_to_the_plot(column):
    win = draw(frame(**{column: LEGACY[column]}))
    assert set(n_curves(win)) == {"n (R+T)"}
    assert set(k_curves(win)) == {"k (R+T)"}
    assert len(win.plot_nk.plotItem.items) == len(draw(frame()).plot_nk.plotItem.items)
    assert win.logger.errors == []


def test_all_the_retired_columns_together_still_draw_the_plain_curves():
    win = draw(frame(**LEGACY))
    assert set(n_curves(win)) == {"n (R+T)"}
    assert set(k_curves(win)) == {"k (R+T)"}
    assert [entry["name"] for entry in win.plot_nk._tracked_curves] == ["n (R+T)", "log10(k)"]
    assert not [item for item in win.plot_nk.plotItem.items if isinstance(item, pg.ErrorBarItem)]
    assert not [item for item in win._vb_k.addedItems if isinstance(item, pg.ErrorBarItem)]


# --- the infrared mask of the TLU model ---------------------------------------------------------------------------------------------------


def test_with_a_tlu_model_the_points_beyond_the_fit_are_blanked_before_drawing():
    res = result(method="TLU", lambda_max_fit=1500.0, tlu=object())
    win = draw(frame(), res)
    n_y = y_of(n_curves(win)["n (R+T)"])
    k_y = y_of(k_curves(win)["k (R+T)"])
    assert np.isnan(n_y[WL > 1500.0]).all()
    np.testing.assert_allclose(n_y[WL <= 1500.0], N_CALC[WL <= 1500.0])
    np.testing.assert_allclose(k_y[WL > 1500.0], -7.0)  # blanked k is the floor of the log axis
    np.testing.assert_allclose(k_y[WL <= 1500.0], K_PLOTTED[WL <= 1500.0])


def test_a_spline_method_is_not_masked_even_with_a_fit_limit():
    res = result(method="Spline", lambda_max_fit=1500.0, tlu=object())
    win = draw(frame(), res)
    np.testing.assert_allclose(y_of(n_curves(win)["n (R+T)"]), N_CALC)


# --- the log axis for k ---------------------------------------------------------------------------------------------------------------------


def test_the_right_axis_is_a_linear_view_of_log10_k_fixed_between_minus_six_and_a_half_and_minus_two():
    win = draw(frame())
    (_x_range, y_range) = win._vb_k.viewRange()
    assert y_range == pytest.approx([-6.5, -2.0])
    assert win._vb_k.state["autoRange"][1] is False
    assert win._vb_k.state["logMode"] == [False, False]


def test_the_right_axis_is_labelled_k_in_log_scale():
    win = draw(frame())
    assert win._ax_k.labelText == "k (log scale)"


def test_a_second_drawing_reuses_the_secondary_view_and_does_not_pile_curves_up():
    win = draw(frame(n_fit_T_only=N_CALC, k_fit_T_only=K_CALC))
    first_view = win._vb_k
    draw(frame(n_fit_T_only=N_CALC, k_fit_T_only=K_CALC), win=win)
    assert win._vb_k is first_view
    assert len(k_curves(win)) == 2
    assert len([i for i in win._vb_k.addedItems if isinstance(i, pg.PlotCurveItem)]) == 2
    assert len([i for i in win.plot_nk.plotItem.items if isinstance(i, pg.PlotDataItem)]) == 2
    assert len(win.plot_nk._tracked_curves) == 4


# --- the legends --------------------------------------------------------------------------------------------------------------------------


def legends(win):
    return [c for c in win.plot_nk.plotItem.childItems() if isinstance(c, pg.LegendItem)]


def labels(legend):
    return [label.text for _sample, label in legend.items]


def test_there_is_a_legend_for_the_left_axis_and_one_for_the_k_curve():
    # the left legend is created after the n curves are plotted: pyqtgraph lists only the curves added after it, so it is filled from the second drawing on
    win = draw(frame())
    assert win.plot_nk.plotItem.legend is not None
    extra = [leg for leg in legends(win) if leg is not win.plot_nk.plotItem.legend]
    assert [labels(leg) for leg in extra] == [["k (R+T)"]]


def test_the_k_legend_lists_the_transmission_only_curve_too():
    win = draw(frame(n_fit_T_only=N_CALC, k_fit_T_only=K_CALC))
    extra = [leg for leg in legends(win) if leg is not win.plot_nk.plotItem.legend]
    assert [labels(leg) for leg in extra] == [["k (R+T)", "k (90% T)"]]


# --- when there is nothing to draw -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["n_calc", "k_calc"])
def test_a_result_without_n_or_k_draws_only_the_title_and_logs_why(missing):
    df = frame().drop(columns=[missing])
    win = draw(df)
    assert win.plot_nk.plotItem.titleLabel.text.startswith("Optical Constants")
    assert n_curves(win) == {}
    assert not hasattr(win, "_vb_k")
    assert any("Missing n_calc or k_calc" in message for message in win.logger.errors)


def test_a_result_whose_index_is_all_nan_draws_only_the_title():
    df = frame()
    df["n_calc"] = np.nan
    win = draw(df)
    assert n_curves(win) == {}
    assert not hasattr(win, "_vb_k")


def test_a_numerical_fault_while_drawing_is_logged_twice_and_does_not_escape(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("the legend broke")

    monkeypatch.setattr(pg, "LegendItem", broken)
    win = draw(frame())
    assert len(win.logger.errors) == 2
    assert "display failed | component=nk | reason=the legend broke" in win.logger.errors[0]
    assert "ValueError" in win.logger.errors[1]


def test_a_new_drawing_starts_from_a_clean_plot_and_clean_tracking():
    win = draw(frame())
    draw(frame(), win=win)
    assert len(n_curves(win)) == 1
    assert [entry["name"] for entry in win.plot_nk._tracked_curves] == ["n (R+T)", "log10(k)"]


def test_the_module_still_uses_the_logger_of_the_window():
    assert module.CertusIndexPlotMixin._update_nk_plot is CertusIndexPlotMixin._update_nk_plot


def test_the_n_legend_lists_its_curves_from_the_first_plot_of_a_window():
    """D66: the legend was created after the n curves, and pyqtgraph lists only the curves added after it: empty at the
    first plot of a window, filled at the next ones. It is created first now."""
    win = draw(frame(n_fit_T_only=N_CALC + 0.01, k_fit_T_only=K_CALC))

    names = [label.text for _sample, label in win.plot_nk.plotItem.legend.items]
    assert names == ["n (R+T)", "n (90% T)"]
