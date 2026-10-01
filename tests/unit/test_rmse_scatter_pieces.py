"""Three pieces of the RMSE(d) scatter are methods of their own (audit v2, plan S5.2).

`_PlotMixin._plot_rmse_data_scatter` draws the RMSE(d) profile of the corridors tab: 383 lines, complexity 72. Three blocks come out of it:

    _plot_the_reversal_and_fallback_points   the points taken after a break and the three kinds of fallback evaluation, one marker series each
    _plot_the_breakpoint_events              the breakpoints of the manual grid, snapped on the nearest plotted d, by what triggered them; how many broke towards each side
    _draw_the_local_parabola                 the local parabolic fit over a window centred on its minimum, its centre line, and the label spec of its curvature

Pinned here without Qt: the plot is a recorder and `pg` is replaced by a namespace that turns every pen, brush and line into a tuple.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtCore import Qt

from certus.spline import certus_index_spline_rendering as module
from certus.spline.certus_index_spline_rendering import _PlotMixin


class Plot:
    """Records `plot(...)` and `addItem(...)`, in the order they come."""

    def __init__(self) -> None:
        self.series: list[tuple[np.ndarray, np.ndarray, dict]] = []
        self.items: list = []
        self.timeline: list[str] = []

    def plot(self, x, y, **kwargs) -> None:
        self.series.append((np.asarray(x), np.asarray(y), kwargs))
        self.timeline.append(kwargs.get("name", "?"))

    def addItem(self, item) -> None:
        self.items.append(item)
        self.timeline.append("item")


@pytest.fixture(autouse=True)
def fake_pyqtgraph(monkeypatch):
    fake = SimpleNamespace(
        mkBrush=lambda *args, **kwargs: ("brush", args, kwargs),
        mkPen=lambda *args, **kwargs: ("pen", args, kwargs),
        InfiniteLine=lambda **kwargs: ("line", kwargs),
    )
    monkeypatch.setattr(module, "pg", fake)


# --- _plot_the_reversal_and_fallback_points --------------------------------------------------------------------------------------------

D_VIS = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
R_VIS = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])


def markers(status, reversed_mask=None):
    plot = Plot()
    mask = np.zeros(D_VIS.size, dtype=bool) if reversed_mask is None else np.asarray(reversed_mask, dtype=bool)
    _PlotMixin._plot_the_reversal_and_fallback_points(SimpleNamespace(plot_corridor_rmse_d=plot), D_VIS, R_VIS, np.asarray(status, dtype=np.int8), mask)
    return plot


def test_without_reversal_nor_fallback_nothing_is_plotted():
    assert markers([0, 0, 0, 0, 0, 0]).series == []


def test_the_reversal_points_are_orange_triangles_at_their_own_coordinates():
    plot = markers([0] * 6, reversed_mask=[0, 1, 0, 0, 1, 0])
    ((x, y, style),) = plot.series
    np.testing.assert_array_equal(x, [20.0, 50.0])
    np.testing.assert_array_equal(y, [0.2, 0.5])
    assert style == {
        "pen": None,
        "symbol": "t",
        "symbolSize": 11,
        "symbolBrush": ("brush", (255, 140, 0, 200), {}),
        "symbolPen": ("pen", (255, 140, 0, 220), {}),
        "name": "RMSE(d) reprise cassure",
    }


@pytest.mark.parametrize(
    ("status", "symbol", "size", "color", "name"),
    [(1, "x", 12, "#ff8c00", "Fallback seed"), (2, "d", 13, "#c2185b", "Fallback objectif"), (3, "s", 14, "#6a1b9a", "Fallback urgence")],
    ids=["seed", "objective", "emergency"],
)
def test_each_fallback_kind_has_its_own_hollow_marker(status, symbol, size, color, name):
    plot = markers([0, status, 0, 0, status, 0])
    ((x, y, style),) = plot.series
    np.testing.assert_array_equal(x, [20.0, 50.0])
    np.testing.assert_array_equal(y, [0.2, 0.5])
    assert style == {
        "pen": None,
        "symbol": symbol,
        "symbolSize": size,
        "symbolBrush": ("brush", (255, 255, 255, 0), {}),
        "symbolPen": ("pen", (color,), {"width": 2}),
        "name": name,
    }


def test_an_unknown_status_is_not_a_fallback():
    assert markers([4, 0, -1, 7, 0, 0]).series == []


def test_every_series_comes_in_the_order_reversal_seed_objective_emergency():
    plot = markers([0, 1, 2, 3, 0, 0], reversed_mask=[1, 0, 0, 0, 0, 0])
    assert plot.timeline == ["RMSE(d) reprise cassure", "Fallback seed", "Fallback objectif", "Fallback urgence"]


def test_a_point_that_is_both_a_reversal_and_a_fallback_is_in_both_series():
    plot = markers([0, 1, 0, 0, 0, 0], reversed_mask=[0, 1, 0, 0, 0, 0])
    assert plot.timeline == ["RMSE(d) reprise cassure", "Fallback seed"]


# --- _plot_the_breakpoint_events -------------------------------------------------------------------------------------------------------

D_PLOT = np.array([100.0, 110.0, 120.0, 130.0])
R_PLOT = np.array([0.4, 0.3, 0.2, 0.1])


def breakpoints(events, d_plot=D_PLOT, r_plot=R_PLOT, key=True):
    plot = Plot()
    src = {"profile_d_manual_grid_breakpoint_events": events} if key else {}
    left, right, got = _PlotMixin._plot_the_breakpoint_events(SimpleNamespace(plot_corridor_rmse_d=plot), src, d_plot, r_plot)
    return plot, left, right, got


def event(d, prev=0.0, parabola=0.0, sign=float("nan")):
    return {"d_break_nm": d, "trigger_prevN": prev, "trigger_parabola": parabola, "branch_dir_sign": sign}


def by_name(plot):
    return {kwargs["name"]: (x, y, kwargs) for x, y, kwargs in plot.series}


def test_without_events_nothing_is_plotted_and_the_events_are_given_back():
    plot, left, right, got = breakpoints([])
    assert plot.series == []
    assert (left, right) == (0, 0)
    assert got == []


def test_a_missing_key_gives_an_empty_list():
    plot, left, right, got = breakpoints(None, key=False)
    assert plot.series == []
    assert got == []
    assert (left, right) == (0, 0)


def test_events_that_are_not_a_list_are_given_back_untouched_and_not_plotted():
    for odd in ("text", {"d_break_nm": 100.0}, (event(100.0),), None):
        plot, left, right, got = breakpoints(odd)
        assert plot.series == []
        assert got is odd
        assert (left, right) == (0, 0)


def test_without_plotted_points_the_events_are_not_read():
    plot, left, right, got = breakpoints([event(100.0, sign=1.0)], d_plot=np.array([]), r_plot=np.array([]))
    assert plot.series == []
    assert (left, right) == (0, 0)
    assert len(got) == 1


def test_an_event_is_snapped_on_the_nearest_plotted_d_and_marked():
    plot, *_ = breakpoints([event(111.0), event(128.0)])
    x, y, style = by_name(plot)["Breakpoints"]
    np.testing.assert_array_equal(x, [110.0, 130.0])
    np.testing.assert_array_equal(y, [0.3, 0.1])
    assert x.dtype == np.float64
    assert style == {
        "pen": None,
        "symbol": "o",
        "symbolSize": 15,
        "symbolBrush": ("brush", (255, 236, 139, 220), {}),
        "symbolPen": ("pen", ("#9b111e",), {"width": 2}),
        "name": "Breakpoints",
    }


def test_events_without_a_finite_d_and_things_that_are_not_events_are_skipped():
    plot, left, right, _got = breakpoints([{"trigger_parabola": 1.0}, event(float("nan"), sign=1.0), event(float("inf"), sign=1.0), "not a dict", None, event(120.0)])
    x, _y, _style = by_name(plot)["Breakpoints"]
    np.testing.assert_array_equal(x, [120.0])
    assert (left, right) == (0, 0)


def test_the_prevN_trigger_marks_a_hollow_diamond():
    plot, *_ = breakpoints([event(100.0, prev=1.0), event(120.0)])
    x, y, style = by_name(plot)["Breakpoint prevN"]
    np.testing.assert_array_equal(x, [100.0])
    np.testing.assert_array_equal(y, [0.4])
    assert style == {
        "pen": None,
        "symbol": "d",
        "symbolSize": 13,
        "symbolBrush": ("brush", (255, 255, 255, 0), {}),
        "symbolPen": ("pen", ("#9b111e",), {"width": 2}),
        "name": "Breakpoint prevN",
    }


def test_the_parabola_trigger_marks_a_hollow_triangle():
    plot, *_ = breakpoints([event(110.0, parabola=1.0), event(120.0)])
    x, y, style = by_name(plot)["Breakpoint parabola"]
    np.testing.assert_array_equal(x, [110.0])
    np.testing.assert_array_equal(y, [0.3])
    assert style == {
        "pen": None,
        "symbol": "t",
        "symbolSize": 14,
        "symbolBrush": ("brush", (255, 255, 255, 0), {}),
        "symbolPen": ("pen", ("#7a3cff",), {"width": 2}),
        "name": "Breakpoint parabola",
    }


def test_the_parabola_trigger_wins_over_the_prevN_one_and_both_need_more_than_a_half():
    plot, *_ = breakpoints([event(100.0, prev=1.0, parabola=1.0), event(110.0, prev=0.5, parabola=0.5), event(120.0, prev=0.6)])
    series = by_name(plot)
    np.testing.assert_array_equal(series["Breakpoints"][0], [100.0, 110.0, 120.0])
    np.testing.assert_array_equal(series["Breakpoint parabola"][0], [100.0])
    np.testing.assert_array_equal(series["Breakpoint prevN"][0], [120.0])


def test_the_triggers_default_to_not_triggered():
    plot, *_ = breakpoints([{"d_break_nm": 100.0}])
    assert list(by_name(plot)) == ["Breakpoints"]


@pytest.mark.parametrize(
    ("signs", "left", "right"),
    [
        ([1.0, 2.5, 1.0], 0, 3),
        ([-1.0, -0.2], 2, 0),
        ([1.0, -1.0, -1.0], 2, 1),
        ([0.0, float("nan"), float("inf"), float("-inf")], 0, 0),
    ],
    ids=["right", "left", "both", "no direction"],
)
def test_the_events_are_counted_by_the_side_they_broke_towards(signs, left, right):
    _plot, got_left, got_right, _events = breakpoints([event(100.0, sign=s) for s in signs])
    assert (got_left, got_right) == (left, right)


def test_an_event_without_a_direction_is_not_counted():
    _plot, left, right, _events = breakpoints([{"d_break_nm": 100.0}])
    assert (left, right) == (0, 0)


def test_the_series_come_in_the_order_breakpoints_prevN_parabola():
    plot, *_ = breakpoints([event(100.0, prev=1.0), event(110.0, parabola=1.0)])
    assert plot.timeline == ["Breakpoints", "Breakpoint prevN", "Breakpoint parabola"]


def test_the_events_come_back_as_they_were_given():
    events = [event(100.0, sign=1.0), "junk"]
    *_head, got = breakpoints(events)
    assert got is events


# --- _draw_the_local_parabola ----------------------------------------------------------------------------------------------------------

PURPLE = "#7a3cff"
UNCHANGED = "the spec it was given"


def fit(**changes):
    base = {"ok": True, "d_center": 100.0, "window_nm": (95.0, 108.0), "coeffs": (2.0, -4.0, 1.0), "anchor_nm": 100.0}
    base.update(changes)
    return base


def draw(parab_fit, d_parab_arr=(90.0, 100.0, 110.0), d_plot=(80.0, 90.0, 100.0, 120.0), d_best=101.0, d_center=100.0, spec=UNCHANGED):
    plot = Plot()
    curves: list = []
    app = SimpleNamespace(plot_corridor_rmse_d=plot, _add_curve=lambda *args, **kwargs: curves.append((args, kwargs)))
    out = _PlotMixin._draw_the_local_parabola(app, np.asarray(d_plot, dtype=np.float64), d_best, spec, np.asarray(d_parab_arr, dtype=np.float64), parab_fit, d_center)
    return out, plot, curves


def drawn_curve(curves):
    ((args, kwargs),) = curves
    return args, kwargs


def test_a_fit_that_is_not_ok_draws_nothing_and_keeps_the_spec():
    for parab_fit in ({"ok": False}, {}, {"ok": 0}):
        out, plot, curves = draw(parab_fit)
        assert out is UNCHANGED
        assert curves == []
        assert plot.items == []


def test_the_curve_is_a_dashed_purple_line_named_after_the_fit():
    _out, plot, curves = draw(fit())
    args, kwargs = drawn_curve(curves)
    assert args[0] is plot
    assert args[3:] == (PURPLE, "Local parabolic fit")
    assert kwargs == {"pen": ("pen", (PURPLE,), {"width": 2, "style": Qt.PenStyle.DashLine})}


def test_the_curve_spans_five_percent_each_side_of_the_centre_with_two_hundred_points():
    _out, _plot, curves = draw(fit(d_center=100.0))
    d_par = drawn_curve(curves)[0][1]
    assert d_par.shape == (200,)
    assert d_par.dtype == np.float64
    assert d_par[0] == pytest.approx(95.0)
    assert d_par[-1] == pytest.approx(105.0)


def test_the_curve_is_the_quadratic_in_the_distance_to_the_anchor():
    _out, _plot, curves = draw(fit(coeffs=(2.0, -4.0, 1.0), anchor_nm=98.0))
    args = drawn_curve(curves)[0]
    d_par, r_par = args[1], args[2]
    x = d_par - 98.0
    np.testing.assert_allclose(r_par, 2.0 * x * x - 4.0 * x + 1.0)


def test_without_an_anchor_the_best_d_is_the_anchor():
    parab_fit = fit()
    parab_fit.pop("anchor_nm")
    _out, _plot, curves = draw(parab_fit, d_best=103.0)
    args = drawn_curve(curves)[0]
    x = args[1] - 103.0
    np.testing.assert_allclose(args[2], 2.0 * x * x - 4.0 * x + 1.0)


def test_the_window_is_centred_on_the_fit_centre_not_on_the_one_that_was_given():
    _out, _plot, curves = draw(fit(d_center=200.0), d_center=100.0)
    d_par = drawn_curve(curves)[0][1]
    assert d_par[0] == pytest.approx(190.0)
    assert d_par[-1] == pytest.approx(210.0)


def test_without_a_centre_in_the_fit_the_given_centre_is_used():
    parab_fit = fit()
    parab_fit.pop("d_center")
    _out, _plot, curves = draw(parab_fit, d_center=300.0)
    d_par = drawn_curve(curves)[0][1]
    assert d_par[0] == pytest.approx(285.0)
    assert d_par[-1] == pytest.approx(315.0)


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        ((-15.0, -5.0), (-15.0, -5.0)),
        ((-10.0, -2.0), (-14.0, -6.0)),
        ((-12.0, -2.0), (-12.0, -8.0)),
        ((-18.0, -8.0), (-12.0, -8.0)),
    ],
    ids=["symmetric", "centre on the left edge: half the window", "the left side is the smaller", "the right side is the smaller"],
)
def test_a_non_positive_centre_gets_a_window_of_one_half_span_each_side(window, expected):
    _out, _plot, curves = draw(fit(d_center=-10.0, window_nm=window), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    assert d_par[0] == pytest.approx(expected[0])
    assert d_par[-1] == pytest.approx(expected[1])


def test_a_centre_of_zero_is_not_a_positive_centre():
    _out, _plot, curves = draw(fit(d_center=0.0, window_nm=(-4.0, 4.0)), d_center=0.0)
    d_par = drawn_curve(curves)[0][1]
    assert (d_par[0], d_par[-1]) == (pytest.approx(-4.0), pytest.approx(4.0))


def test_the_half_span_falls_back_on_half_the_spread_of_the_profile_then_on_a_millinanometre():
    _out, _plot, curves = draw(fit(d_center=-10.0, window_nm=(5.0, 5.0)), d_parab_arr=(90.0, 100.0, 110.0), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    assert (d_par[0], d_par[-1]) == (pytest.approx(-20.0), pytest.approx(0.0))
    _out, _plot, curves = draw(fit(d_center=-10.0, window_nm=(5.0, 5.0)), d_parab_arr=(90.0,), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    assert (d_par[0], d_par[-1]) == (pytest.approx(-10.001), pytest.approx(-9.999))


def test_the_fallback_half_span_is_at_least_a_millionth_of_a_nanometre():
    _out, _plot, curves = draw(fit(d_center=-10.0, window_nm=(5.0, 5.0)), d_parab_arr=(1.0, 1.0 + 1e-10), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    assert d_par[-1] - d_par[0] == pytest.approx(2e-6)


def test_without_a_window_the_profile_extent_is_the_default_window():
    parab_fit = fit(d_center=-10.0)
    parab_fit.pop("window_nm")
    _out, _plot, curves = draw(parab_fit, d_parab_arr=(-30.0, -20.0, -4.0), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    # window (-30, -4): left = 20, right = 6 -> half span 6
    assert (d_par[0], d_par[-1]) == (pytest.approx(-16.0), pytest.approx(-4.0))


def test_without_a_window_nor_a_profile_the_half_span_is_a_millinanometre():
    parab_fit = fit(d_center=-10.0)
    parab_fit.pop("window_nm")
    _out, _plot, curves = draw(parab_fit, d_parab_arr=(), d_plot=(70.0, 90.0, 80.0), d_center=-10.0)
    d_par = drawn_curve(curves)[0][1]
    assert (d_par[0], d_par[-1]) == (pytest.approx(-10.001), pytest.approx(-9.999))


def test_a_centre_that_is_not_finite_takes_the_plotted_extent():
    _out, _plot, curves = draw(fit(d_center=float("nan")), d_plot=(70.0, 90.0, 80.0))
    d_par = drawn_curve(curves)[0][1]
    assert (d_par[0], d_par[-1]) == (70.0, 90.0)


def test_a_centre_that_is_not_finite_and_nothing_plotted_gives_a_nan_axis():
    _out, _plot, curves = draw(fit(d_center=float("nan")), d_plot=())
    assert np.isnan(drawn_curve(curves)[0][1]).all()


def test_the_centre_line_is_dotted_at_the_centre_that_was_given():
    _out, plot, _curves = draw(fit(d_center=200.0), d_center=100.0)
    assert plot.items == [("line", {"pos": 100.0, "angle": 90, "movable": False, "pen": ("pen", (PURPLE,), {"width": 1, "style": Qt.PenStyle.DotLine})})]


def test_the_curve_is_drawn_before_the_centre_line():
    plot = Plot()
    order: list[str] = []
    app = SimpleNamespace(plot_corridor_rmse_d=plot, _add_curve=lambda *args, **kwargs: order.append("curve"))
    plot.addItem = lambda item: order.append("line")
    _PlotMixin._draw_the_local_parabola(app, np.array([1.0]), 1.0, None, np.array([1.0]), fit(), 100.0)
    assert order == ["curve", "line"]


def test_a_convex_fit_gives_the_label_spec_of_its_curvature():
    out, *_ = draw(fit(coeffs=(2.0, -4.0, 1.0), d_center=100.0))
    assert out == (2.0, 100.0, -1.0)  # vertex value: c0 - c1^2 / (4 c2) = 1 - 16 / 8


@pytest.mark.parametrize(
    "coeffs",
    [(0.0, -4.0, 1.0), (-2.0, -4.0, 1.0), (float("nan"), -4.0, 1.0), (2.0, float("nan"), 1.0), (2.0, -4.0, float("nan")), (float("inf"), -4.0, 1.0)],
    ids=["flat", "concave", "nan c2", "nan c1", "nan c0", "inf c2"],
)
def test_a_fit_without_a_finite_minimum_keeps_the_spec(coeffs):
    out, *_ = draw(fit(coeffs=coeffs))
    assert out is UNCHANGED


def test_a_vertex_that_is_not_finite_keeps_the_spec():
    parab_fit = fit()
    parab_fit.pop("d_center")
    out, *_ = draw(parab_fit)
    assert out is UNCHANGED


def test_the_vertex_comes_from_the_fit_centre():
    out, *_ = draw(fit(d_center=140.0), d_center=100.0)
    assert out[1] == 140.0


def test_a_fit_without_coefficients_draws_a_nan_curve_and_keeps_the_spec():
    parab_fit = fit()
    parab_fit.pop("coeffs")
    out, _plot, curves = draw(parab_fit)
    assert out is UNCHANGED
    assert np.isnan(drawn_curve(curves)[0][2]).all()


# --- the scatter hands them their work ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        "self._plot_the_reversal_and_fallback_points(d_vis, r_vis, status_vis, m_rev)",
        "bp_dir_left, bp_dir_right, bp_events = self._plot_the_breakpoint_events(src, d_plot, r_plot)",
        "curvature_label_spec = self._draw_the_local_parabola(d_plot, d_best, curvature_label_spec, d_parab_arr, parab_fit, d_center)",
    ],
)
def test_the_scatter_calls_each_piece_with_the_values_it_computed(call):
    assert call in inspect.getsource(_PlotMixin._plot_rmse_data_scatter)


def test_the_pieces_come_in_the_order_of_the_drawing():
    source = inspect.getsource(_PlotMixin._plot_rmse_data_scatter)
    positions = [source.index(name) for name in ("_plot_the_reversal_and_fallback_points", "_plot_the_breakpoint_events", "_draw_the_local_parabola")]
    assert positions == sorted(positions)

