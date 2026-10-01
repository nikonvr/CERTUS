"""Three loops of `IndexTableDialog.__init__` are methods of their own (audit v2, plan S5.2).

The substrate-index dialog plots the raw index of every substrate series with the three laws fitted on it, then fills a table with the same figures. `__init__` was 457 lines
(complexity 64); three loops come out, each pinned here on a namespace in place of the dialog, recorders in place of the plot and the table:

    _plot_the_index_series   the raw points and the three laws of every series, the best law coloured by the quality label the constructor kept for its series
    _fill_the_rmse_row       the RMSE of every law under its column, in the first row: green for the best, grey for the clearly worse ones
    _fill_the_data_rows      one row per wavelength, rows outside the fit window shaded, the wavelength of rows inside it in bold, bad columns greyed
"""

from __future__ import annotations

import inspect
import math
from types import SimpleNamespace

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from certus.core.certus_substrate_index import SUBSTRATE_INDEX_MODELS
from certus.ui import certus_substrate_index_dialog as module
from certus.ui.certus_substrate_index_dialog import IndexTableDialog, _quality_of_a_series
from certus.ui.certus_ui import CertusTheme

pytestmark = pytest.mark.usefixtures("qapp")

LABELS = [label for _key, label in SUBSTRATE_INDEX_MODELS]
CENTER = Qt.AlignmentFlag.AlignCenter.value


def hex_of(color) -> str:
    return QColor(color).name()


# --- _fill_the_rmse_row ------------------------------------------------------------------------------------------------------------------


class Table:
    def __init__(self) -> None:
        self.items: dict[tuple[int, int], object] = {}

    def setItem(self, row, col, item) -> None:
        self.items[(row, col)] = item


def rmse_row_of(series, rmse, orders=None, bases=None):
    font = QFont()
    font.setPointSize(13)
    orders = orders or {bk: list(SUBSTRATE_INDEX_MODELS) for bk in series}
    bases = bases or {bk: 1 + k * (1 + len(LABELS)) for k, bk in enumerate(series)}
    window = SimpleNamespace(n_results_raw={bk: [1.0] for bk in series}, rmse_row=rmse, _models_order_by_bk=orders)
    table = Table()
    IndexTableDialog._fill_the_rmse_row(window, table, font, bases)
    return table, bases


def test_each_series_has_an_empty_centred_cell_in_the_surface_colour_under_its_raw_column():
    table, bases = rmse_row_of(["A"], {"A": dict.fromkeys(LABELS, 0.01)})
    item = table.items[(0, bases["A"])]
    assert item.text() == ""
    assert item.textAlignment() == CENTER
    assert item.font().pointSize() == 13
    assert hex_of(item.background().color()) == hex_of(CertusTheme.SURFACE)


def test_every_law_gets_a_centred_cell_in_the_rmse_font_and_the_surface_colour():
    table, bases = rmse_row_of(["A"], {"A": dict.fromkeys(LABELS, 0.01)})
    for j in range(len(LABELS)):
        cell = table.items[(0, bases["A"] + 1 + j)]
        assert cell.textAlignment() == CENTER
        assert cell.font().pointSize() == 13
        assert hex_of(cell.background().color()) == hex_of(CertusTheme.SURFACE)


def test_only_the_first_row_is_written():
    table, _ = rmse_row_of(["A", "B"], {"A": dict.fromkeys(LABELS, 0.01), "B": dict.fromkeys(LABELS, 0.02)})
    assert {row for row, _col in table.items} == {0}


def test_the_rmse_is_written_with_six_decimals_and_a_missing_one_is_blank():
    rmse = {"A": {LABELS[0]: 0.0123456789, LABELS[1]: float("nan")}}
    table, bases = rmse_row_of(["A"], rmse)
    assert table.items[(0, bases["A"] + 1)].text() == "0.012346"
    assert table.items[(0, bases["A"] + 2)].text() == ""
    assert table.items[(0, bases["A"] + 3)].text() == ""


def test_the_best_law_is_green_the_clearly_worse_grey_and_the_others_dark():
    rmse = {"A": {LABELS[0]: 0.0100, LABELS[1]: 0.0105, LABELS[2]: 0.0200}}  # ratio limit is 1.10
    table, bases = rmse_row_of(["A"], rmse)
    colours = [hex_of(table.items[(0, bases["A"] + 1 + j)].foreground().color()) for j in range(3)]
    assert colours == [hex_of(CertusTheme.SUCCESS), hex_of(CertusTheme.TEXT_MAIN), hex_of(CertusTheme.TEXT_SUB)]


def test_a_tie_with_the_best_is_green_too_and_a_law_with_no_rmse_is_grey():
    rmse = {"A": {LABELS[0]: 0.0100, LABELS[1]: 0.0100 * (1 + 1e-12), LABELS[2]: float("nan")}}
    table, bases = rmse_row_of(["A"], rmse)
    colours = [hex_of(table.items[(0, bases["A"] + 1 + j)].foreground().color()) for j in range(3)]
    assert colours == [hex_of(CertusTheme.SUCCESS), hex_of(CertusTheme.SUCCESS), hex_of(CertusTheme.TEXT_SUB)]


def test_the_laws_follow_the_order_chosen_for_their_series():
    rmse = {"A": {LABELS[0]: 0.03, LABELS[1]: 0.01, LABELS[2]: 0.02}}
    order = [SUBSTRATE_INDEX_MODELS[1], SUBSTRATE_INDEX_MODELS[2], SUBSTRATE_INDEX_MODELS[0]]
    table, bases = rmse_row_of(["A"], rmse, orders={"A": order})
    texts = [table.items[(0, bases["A"] + 1 + j)].text() for j in range(3)]
    assert texts == ["0.010000", "0.020000", "0.030000"]


def test_every_series_has_its_own_columns_and_its_own_best():
    rmse = {"A": {LABELS[0]: 0.01, LABELS[1]: 0.05, LABELS[2]: 0.05}, "B": {LABELS[0]: 0.05, LABELS[1]: 0.05, LABELS[2]: 0.01}}
    table, bases = rmse_row_of(["A", "B"], rmse)
    green = hex_of(CertusTheme.SUCCESS)
    a = [hex_of(table.items[(0, bases["A"] + 1 + j)].foreground().color()) == green for j in range(3)]
    b = [hex_of(table.items[(0, bases["B"] + 1 + j)].foreground().color()) == green for j in range(3)]
    assert a == [True, False, False]
    assert b == [False, False, True]


def test_a_series_without_rmse_has_blank_grey_cells():
    table, bases = rmse_row_of(["A"], {})
    cells = [table.items[(0, bases["A"] + 1 + j)] for j in range(3)]
    assert [cell.text() for cell in cells] == ["", "", ""]
    assert {hex_of(cell.foreground().color()) for cell in cells} == {hex_of(CertusTheme.TEXT_SUB)}


# --- _fill_the_data_rows -----------------------------------------------------------------------------------------------------------------

WL = np.array([500.0, 600.0, 700.0, 800.0])


def data_rows(*, lo=None, hi=None, raw=None, by_model=None, bad_column=None, wl=WL, orders=None):
    raw = {"A": np.array([1.5, 1.6, 1.7, 1.8])} if raw is None else raw
    by_model = {"A": {LABELS[0]: np.array([1.51, 1.61, 1.71, 1.81]), LABELS[1]: np.array([1.52, 1.62, 1.72, 1.82])}} if by_model is None else by_model
    orders = {bk: list(SUBSTRATE_INDEX_MODELS) for bk in raw} if orders is None else orders
    width = 1 + sum(1 + len(orders[bk]) for bk in raw)
    bad_column = [False] * width if bad_column is None else bad_column
    window = SimpleNamespace(fit_wl_lo=lo, fit_wl_hi=hi, n_results_raw=raw, n_results_by_model=by_model, _models_order_by_bk=orders)
    table = Table()
    IndexTableDialog._fill_the_data_rows(window, wl, bad_column, table, len(wl))
    return table


def test_one_row_per_wavelength_below_the_header_row_with_the_wavelength_then_every_series_and_law():
    table = data_rows()
    assert {row for row, _col in table.items} == {1, 2, 3, 4}
    assert [table.items[(1, col)].text() for col in range(5)] == ["500.0", "1.5000", "1.5100", "1.5200", ""]
    assert [table.items[(4, col)].text() for col in range(5)] == ["800.0", "1.8000", "1.8100", "1.8200", ""]


def test_the_columns_of_several_series_follow_each_other():
    raw = {"A": np.array([1.5, 1.6]), "B": np.array([2.5, 2.6])}
    by_model = {"A": {LABELS[0]: np.array([1.0, 1.1])}, "B": {LABELS[2]: np.array([2.0, 2.1])}}
    table = data_rows(raw=raw, by_model=by_model, wl=np.array([500.0, 600.0]))
    assert [table.items[(1, col)].text() for col in range(9)] == ["500.0", "1.5000", "1.0000", "", "", "2.5000", "", "", "2.0000"]


def test_the_laws_of_a_series_follow_its_own_order():
    order = [SUBSTRATE_INDEX_MODELS[1], SUBSTRATE_INDEX_MODELS[0], SUBSTRATE_INDEX_MODELS[2]]
    table = data_rows(orders={"A": order})
    assert [table.items[(1, col)].text() for col in range(5)] == ["500.0", "1.5000", "1.5200", "1.5100", ""]


def test_every_cell_is_centred():
    table = data_rows()
    assert {item.textAlignment() for item in table.items.values()} == {CENTER}


def test_without_a_fit_window_no_row_is_shaded_or_bold():
    table = data_rows()
    for (row, col), item in table.items.items():
        assert not item.font().bold(), (row, col)
        assert hex_of(item.foreground().color()) != hex_of(CertusTheme.TEXT_SUB) or item.foreground().style() == Qt.BrushStyle.NoBrush


def test_rows_outside_the_fit_window_are_shaded_and_greyed_in_every_column_and_those_inside_have_a_bold_wavelength():
    table = data_rows(lo=550.0, hi=750.0)
    for row in (1, 4):  # 500 and 800 nm
        for col in range(5):
            item = table.items[(row, col)]
            assert hex_of(item.background().color()) == hex_of(CertusTheme.BORDER)
            assert hex_of(item.foreground().color()) == hex_of(CertusTheme.TEXT_SUB)
        assert not table.items[(row, 0)].font().bold()
    for row in (2, 3):
        assert table.items[(row, 0)].font().bold()
        assert not table.items[(row, 1)].font().bold()


def test_the_window_edges_belong_to_the_fit():
    table = data_rows(lo=600.0, hi=700.0)
    assert table.items[(2, 0)].font().bold()
    assert table.items[(3, 0)].font().bold()
    assert not table.items[(1, 0)].font().bold()


def test_a_reversed_window_is_the_same_window():
    first = data_rows(lo=550.0, hi=750.0)
    second = data_rows(lo=750.0, hi=550.0)
    assert [first.items[(row, 0)].font().bold() for row in (1, 2, 3, 4)] == [second.items[(row, 0)].font().bold() for row in (1, 2, 3, 4)]


def test_a_window_with_only_one_end_is_no_window():
    table = data_rows(lo=550.0, hi=None)
    assert not any(item.font().bold() for item in table.items.values())


def test_in_the_fit_the_good_columns_are_on_the_surface_colour_and_the_bad_ones_grey():
    table = data_rows(lo=0.0, hi=1e6, bad_column=[False, False, True, False, False])
    assert hex_of(table.items[(2, 1)].background().color()) == hex_of(CertusTheme.SURFACE)
    assert hex_of(table.items[(2, 3)].background().color()) == hex_of(CertusTheme.SURFACE)
    assert hex_of(table.items[(2, 2)].foreground().color()) == hex_of(CertusTheme.TEXT_SUB)
    assert table.items[(2, 2)].background().style() == Qt.BrushStyle.NoBrush  # a bad column keeps no background of its own


def test_the_wavelength_column_is_never_greyed_as_a_bad_column():
    table = data_rows(bad_column=[True, False, False, False, False])
    assert table.items[(1, 0)].foreground().style() == Qt.BrushStyle.NoBrush
    assert table.items[(1, 0)].background().style() == Qt.BrushStyle.NoBrush


def test_a_row_where_no_series_has_a_finite_index_is_neither_shaded_nor_bold():
    raw = {"A": np.array([1.5, float("nan"), float("nan"), float("nan")])}
    table = data_rows(raw=raw, lo=550.0, hi=750.0, by_model={})
    assert hex_of(table.items[(1, 0)].background().color()) == hex_of(CertusTheme.BORDER)  # 500 nm: outside the window, with data
    assert not table.items[(2, 0)].font().bold()  # 600 nm: in the window but nothing to show
    assert not table.items[(3, 0)].font().bold()  # 700 nm: same
    assert hex_of(table.items[(4, 0)].background().color()) != hex_of(CertusTheme.BORDER)  # 800 nm: outside the window, nothing to shade


def test_a_row_with_data_inside_the_window_is_bold():
    raw = {"A": np.array([1.5, float("nan"), 1.7, float("nan")])}
    table = data_rows(raw=raw, lo=550.0, hi=750.0, by_model={})
    assert table.items[(3, 0)].font().bold()


def test_a_series_with_one_finite_index_is_enough_to_shade_a_row_outside_the_window():
    raw = {"A": np.array([float("nan")] * 4), "B": np.array([float("nan"), 1.6, float("nan"), float("nan")])}
    table = data_rows(raw=raw, lo=650.0, hi=750.0, by_model={})
    assert hex_of(table.items[(2, 0)].background().color()) == hex_of(CertusTheme.BORDER)
    assert hex_of(table.items[(1, 0)].background().color()) != hex_of(CertusTheme.BORDER)


def test_a_bad_column_list_shorter_than_the_row_leaves_the_last_columns_alone():
    table = data_rows(bad_column=[False, True])
    assert hex_of(table.items[(1, 1)].foreground().color()) == hex_of(CertusTheme.TEXT_SUB)
    assert table.items[(1, 4)].foreground().style() == Qt.BrushStyle.NoBrush


# --- _plot_the_index_series --------------------------------------------------------------------------------------------------------------

COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]
PEN_STYLES = [(2.4, Qt.PenStyle.SolidLine), (2.0, Qt.PenStyle.DashLine), (2.0, Qt.PenStyle.DotLine)]
WL_AXIS = np.array([500.0, 600.0, 700.0])
MASK = np.array([False, True, True])


@pytest.fixture(autouse=True)
def curves(monkeypatch):
    seen = SimpleNamespace(scatter=[], lines=[])

    def scatter(plot, wl, y, mask, pen_in, pen_out, *, name=None, **kwargs):
        seen.scatter.append(SimpleNamespace(plot=plot, wl=wl, y=y, mask=mask, pen_in=pen_in, pen_out=pen_out, name=name, kwargs=kwargs))
        return f"raw item of {name}"

    def line(plot, wl, y, mask, pen_in, pen_out, *, name=None, **kwargs):
        seen.lines.append(SimpleNamespace(plot=plot, wl=wl, y=y, mask=mask, pen_in=pen_in, pen_out=pen_out, name=name, kwargs=kwargs))

    monkeypatch.setattr(module, "_pg_plot_scatter_split_band", scatter)
    monkeypatch.setattr(module, "_pg_plot_xy_split_band", line)
    return seen


def plot_series(raw, by_model, quality=None, bad_model=None, colors=COLORS):
    """Run the plot stage; `quality` gives the label the constructor kept for each series (good by default)."""
    plot = object()
    kept = {key: {"best_rmse": 0.001, "quality_label": (quality or {}).get(key, "good")} for key in raw}
    window = SimpleNamespace(plot=plot, raw_items=[], _series_quality=kept)
    IndexTableDialog._plot_the_index_series(window, WL_AXIS, raw, by_model, bad_model or {}, MASK, colors, PEN_STYLES)
    return window, plot


def three_laws(bias=0.0):
    return {label: np.array([1.5, 1.6, 1.7]) + bias + 0.01 * k for k, label in enumerate(LABELS)}


def test_the_raw_points_of_a_series_are_scattered_in_its_colour_with_an_outside_pen_in_grey(curves):
    window, plot = plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()})
    (raw,) = curves.scatter
    assert raw.plot is plot
    assert raw.wl is WL_AXIS
    assert raw.mask is MASK
    assert raw.name == "A (Raw)"
    assert hex_of(raw.pen_in.color()) == "#112233"
    assert raw.pen_in.color().alpha() == 150
    assert raw.pen_in.widthF() == 1.5
    assert hex_of(raw.pen_out.color()) == hex_of(CertusTheme.TEXT_SUB)
    assert raw.pen_out.widthF() == 1.2
    assert window.raw_items == ["raw item of A (Raw)"]


def test_the_colour_of_a_series_cycles_through_the_palette(curves):
    raw = {f"S{k}": np.array([1.5, 1.6, 1.7]) for k in range(5)}
    plot_series(raw, {})
    assert [hex_of(item.pen_in.color()) for item in curves.scatter] == ["#112233", "#445566", "#778899", "#aabbcc", "#112233"]


def test_every_law_present_is_drawn_after_the_raw_points_with_its_own_pen_style(curves):
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()})
    assert [line.name for line in curves.lines] == [f"A ({label})" for label in LABELS]
    assert [line.pen_in.widthF() for line in curves.lines] == [2.4, 2.0, 2.0]
    assert [line.pen_in.style() for line in curves.lines] == [Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine]
    assert [line.pen_out.widthF() for line in curves.lines] == [pytest.approx(1.9), pytest.approx(1.5), pytest.approx(1.5)]
    assert [line.pen_out.style() for line in curves.lines] == [Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine]
    assert {hex_of(line.pen_out.color()) for line in curves.lines} == {hex_of(CertusTheme.TEXT_SUB)}
    assert all(line.mask is MASK and line.wl is WL_AXIS for line in curves.lines)


def test_a_law_without_values_is_skipped_and_the_others_keep_their_pen_style(curves):
    laws = three_laws()
    laws.pop(LABELS[0])
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": laws})
    assert [line.name for line in curves.lines] == [f"A ({LABELS[1]})", f"A ({LABELS[2]})"]
    assert [line.pen_in.style() for line in curves.lines] == [Qt.PenStyle.DashLine, Qt.PenStyle.DotLine]


def test_the_values_of_a_law_are_plotted_as_given(curves):
    laws = three_laws()
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": laws})
    assert curves.lines[1].y is laws[LABELS[1]]


@pytest.mark.parametrize(
    ("label", "token", "alpha"),
    [("good", "SUCCESS", 230), ("degraded", "WARNING", 230), ("poor", "ERROR", 220)],
)
def test_the_first_law_is_coloured_by_the_quality_label_kept_for_its_series(curves, label, token, alpha):
    # the token is read when the test runs, not when it is collected: another test may have switched the theme in between
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()}, quality={"A": label})
    first = curves.lines[0].pen_in.color()
    assert hex_of(first) == hex_of(getattr(CertusTheme, token))
    assert first.alpha() == alpha


def test_every_series_is_coloured_by_its_own_label(curves):
    raw = {"A": np.array([1.5, 1.6, 1.7]), "B": np.array([1.5, 1.6, 1.7])}
    plot_series(raw, {"A": three_laws(), "B": three_laws()}, quality={"A": "good", "B": "poor"})
    firsts = [line for line in curves.lines if line.name.endswith(f"({LABELS[0]})")]
    assert [hex_of(line.pen_in.color()) for line in firsts] == [hex_of(CertusTheme.SUCCESS), hex_of(CertusTheme.ERROR)]


def test_the_other_laws_take_the_colour_of_the_series_and_the_bad_ones_a_grey(curves):
    bad = {"A": {LABELS[2]}}
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()}, bad_model=bad)
    second, third = curves.lines[1].pen_in.color(), curves.lines[2].pen_in.color()
    assert (hex_of(second), second.alpha()) == ("#112233", 220)
    assert (hex_of(third), third.alpha()) == (hex_of(CertusTheme.TEXT_SUB), 160)


def test_the_first_law_keeps_its_quality_colour_even_when_it_is_a_bad_one(curves):
    bad = {"A": {LABELS[0]}}
    plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()}, bad_model=bad)
    assert hex_of(curves.lines[0].pen_in.color()) == hex_of(CertusTheme.SUCCESS)


def test_the_plot_stage_only_reads_the_quality_of_the_series():
    window, _plot = plot_series({"A": np.array([1.5, 1.6, 1.7])}, {"A": three_laws()}, quality={"A": "degraded"})
    assert window._series_quality == {"A": {"best_rmse": 0.001, "quality_label": "degraded"}}


# --- _quality_of_a_series ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("best", "label"),
    [(0.005, "good"), (0.02, "good"), (0.0201, "degraded"), (0.05, "degraded"), (0.0501, "poor"), (0.5, "poor")],
    ids=["good", "good at the limit", "degraded", "degraded at the limit", "poor", "far worse"],
)
def test_the_quality_label_follows_the_best_rmse_of_the_series(best, label):
    best_v, got = _quality_of_a_series({LABELS[0]: best, LABELS[1]: 1.0, LABELS[2]: float("nan")})
    assert (best_v, got) == (best, label)


def test_the_best_rmse_is_the_smallest_finite_one():
    assert _quality_of_a_series({LABELS[0]: 0.3, LABELS[1]: 0.01, LABELS[2]: float("nan")})[0] == 0.01


@pytest.mark.parametrize("rms", [{}, {LABELS[0]: float("nan")}, dict.fromkeys(LABELS, float("nan"))], ids=["empty", "one nan", "all nan"])
def test_a_series_without_a_finite_rmse_counts_as_good_with_a_nan_best(rms):
    best_v, label = _quality_of_a_series(rms)
    assert math.isnan(best_v)
    assert label == "good"


def test_the_two_thresholds_are_written_once_in_the_module():
    source = inspect.getsource(module)
    assert source.count("best_v > 0.02") == 1
    assert source.count("best_v > 0.05") == 1


# --- the constructor ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        "self._plot_the_index_series(",
        "self._fill_the_rmse_row(table, rmse_font, _col_base_raw)",
        "self._fill_the_data_rows(wl, bad_column, table, n_data_rows)",
    ],
)
def test_the_constructor_hands_each_loop_to_its_method(call):
    assert call in inspect.getsource(IndexTableDialog.__init__)


def test_the_plot_comes_before_the_table_and_the_header_row_before_the_data_rows():
    source = inspect.getsource(IndexTableDialog.__init__)
    order = [source.index(name) for name in ("self._plot_the_index_series(", "self._fill_the_rmse_row(", "self._fill_the_data_rows(")]
    assert order == sorted(order)


def test_pg_is_the_module_pyqtgraph():
    assert module.pg is pg


def test_the_real_dialog_classifies_each_series_once_and_says_so_on_top_and_in_the_quality_line(monkeypatch):
    # undo the autouse recorder: here the real plot helpers run on a real plot
    monkeypatch.undo()
    wl = np.array([500.0, 600.0, 700.0])
    raw = {key: np.array([1.50, 1.51, 1.52]) + k for k, key in enumerate("ABC")}
    by_model = {key: {label: arr + 0.001 * k for k, label in enumerate(LABELS)} for key, arr in raw.items()}
    rmse = {"A": dict.fromkeys(LABELS, 0.02), "B": dict.fromkeys(LABELS, 0.0300001234), "C": dict.fromkeys(LABELS, 0.0501)}
    dialog = IndexTableDialog(wl, raw, by_model, rmse)
    try:
        assert [dialog._series_quality[key]["quality_label"] for key in "ABC"] == ["good", "degraded", "poor"]
        assert dialog._series_summary_text == [
            "A: best RMSE=0.02 | quality=good",
            "B: best RMSE=0.0300001 | quality=degraded",
            "C: best RMSE=0.0501 | quality=poor",
        ]
        assert dialog._last_quality_summary == " | ".join(dialog._series_summary_text)
        assert dialog.summary_label.text().endswith(" | Series status: 1 good, 1 degraded, 1 poor")
    finally:
        dialog.deleteLater()


def test_the_real_dialog_runs_its_three_pieces(monkeypatch):
    # undo the autouse recorder: here the real plot helpers run on a real plot
    monkeypatch.undo()
    wl = np.array([500.0, 600.0, 700.0])
    raw = {"A": np.array([1.50, 1.51, 1.52]), "B": np.array([1.60, 1.61, 1.62])}
    by_model = {key: {label: raw[key] + 0.001 * k for k, label in enumerate(LABELS)} for key in raw}
    rmse = {"A": {LABELS[0]: 0.001, LABELS[1]: 0.002, LABELS[2]: 0.003}, "B": {LABELS[0]: 0.06, LABELS[1]: 0.07, LABELS[2]: 0.08}}
    dialog = IndexTableDialog(wl, raw, by_model, rmse, fit_wl_lo=550.0, fit_wl_hi=750.0)
    try:
        assert dialog.table.rowCount() == 1 + 3
        assert dialog.table.item(0, 0).text() == "RMSE (fit window)"
        assert dialog.table.item(1, 0).text() == "500.0"
        assert dialog.table.item(2, 0).font().bold()
        assert not dialog.table.item(1, 0).font().bold()
        assert dialog.table.item(0, 2).text() == "0.001000"
        assert dialog._series_quality == {"A": {"best_rmse": 0.001, "quality_label": "good"}, "B": {"best_rmse": 0.06, "quality_label": "poor"}}
        assert dialog._last_quality_summary == "A: best RMSE=0.001 | quality=good | B: best RMSE=0.06 | quality=poor"
        assert len(dialog.raw_items) == 2
        assert len(dialog.plot.listDataItems()) >= 2 * (1 + len(LABELS))
    finally:
        dialog.deleteLater()
