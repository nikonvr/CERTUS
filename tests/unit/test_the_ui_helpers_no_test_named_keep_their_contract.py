"""Interface helpers that no test named keep their contract (plan S3.7, fourth batch).

`certus_index_ui_utils` is what INDEX says to its user and how it reads a result before plotting it (a toast or a dialog, the file
name on its label, the n/k arrays with the infrared part masked); `certus_substrate_plot_utils` shades the part of a spectrum that a
fit did not use; `certus_qss_icons` paints the tick and the dot that a checked indicator needs (the SVG that was there never
rendered). Their promises are small and visible: what the user reads, which pixels are drawn.

Every assertion was read from the code, then broken once on purpose (the planted errors are in the commit message).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# certus_index_ui_utils


def test_the_detected_data_type_is_named_in_both_the_banner_and_the_summary():
    from certus.ui.certus_index_ui_utils import _detected_data_type_label, _source_type_label
    from certus.utils.certus_index_utils import DataType

    assert _detected_data_type_label(DataType.TRANSMISSION).strip() == "Detected:  TRANSMISSION only"
    assert _detected_data_type_label(DataType.REFLECTION).strip() == "Detected:  REFLECTION only"
    assert _detected_data_type_label(DataType.BOTH).strip() == "Detected: TRANSMISSION + REFLECTION"
    assert [_source_type_label(t) for t in DataType] == ["Transmission", "Reflection", "Transmission + Reflection"]
    assert _source_type_label("something else") == "Unknown"


def test_offscreen_mode_is_read_from_the_environment_whatever_the_case(monkeypatch):
    from certus.ui.certus_index_ui_utils import _is_qt_offscreen_mode

    monkeypatch.setenv("QT_QPA_PLATFORM", "OffScreen")
    assert _is_qt_offscreen_mode() is True
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    assert _is_qt_offscreen_mode() is False
    monkeypatch.delenv("QT_QPA_PLATFORM")
    assert _is_qt_offscreen_mode() is False


@pytest.fixture
def notify(monkeypatch):
    """`_notify_user` with the toast and the three message boxes replaced by recorders, and a window platform."""
    import certus.ui.certus_index_ui_utils as utils

    seen = {"toast": [], "box": []}
    state = {"toast_error": None}

    def toast(parent, text, level, duration_ms):
        if state["toast_error"] is not None:
            raise state["toast_error"]
        seen["toast"].append((parent, text, level, duration_ms))

    monkeypatch.setattr(utils, "show_toast", toast)
    for kind in ("critical", "warning", "information"):
        monkeypatch.setattr(utils.QMessageBox, kind, staticmethod(lambda parent, title, message, _k=kind: seen["box"].append((_k, parent, title, message))))
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    return SimpleNamespace(utils=utils, seen=seen, state=state)


def test_a_non_blocking_message_is_a_toast_with_its_title_in_front(notify):
    notify.utils._notify_user("win", "Load", "file read", level="warning", duration_ms=1500)
    assert notify.seen["toast"] == [("win", "Load: file read", "warning", 1500)]
    assert notify.seen["box"] == []
    notify.utils._notify_user("win", "", "no title")
    assert notify.seen["toast"][-1][1:] == ("no title", "info", 4000)


@pytest.mark.parametrize(("level", "box"), [("error", "critical"), ("critical", "critical"), ("warning", "warning"), ("info", "information"), ("anything", "information")])
def test_a_blocking_message_is_a_dialog_of_the_kind_its_level_says(notify, level, box):
    notify.utils._notify_user("win", "Title", "text", level=level, blocking=True)
    assert notify.seen["toast"] == []
    assert notify.seen["box"] == [(box, "win", "Title", "text")]


def test_a_dialog_without_a_title_gets_a_default_one(notify):
    notify.utils._notify_user("win", "", "text", level="error", blocking=True)
    notify.utils._notify_user("win", "", "text", level="warning", blocking=True)
    notify.utils._notify_user("win", "", "text", blocking=True)
    assert [(k, title) for k, _p, title, _m in notify.seen["box"]] == [("critical", "Error"), ("warning", "Warning"), ("information", "Info")]


def test_a_toast_that_fails_falls_back_to_a_dialog_and_offscreen_to_the_log(notify, monkeypatch, caplog):
    notify.state["toast_error"] = RuntimeError("no toast stack")
    notify.utils._notify_user("win", "Title", "text", level="error")
    assert notify.seen["box"] == [("critical", "win", "Title", "text")]
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    with caplog.at_level(logging.WARNING, logger="CERTUS"):
        notify.utils._notify_user("win", "Title", "text two", level="error")
    assert len(notify.seen["box"]) == 1  # no dialog under the offscreen platform: nobody could answer it
    assert [r.getMessage() for r in caplog.records] == ["Title: text two"]


def test_the_file_label_shows_the_name_of_a_windows_path_and_the_tooltip_the_whole_path():
    from certus.ui.certus_index_ui_utils import _update_loaded_file_label
    from certus.ui.certus_theme import CertusTheme

    label = SimpleNamespace(text="", sheet="", tip="")
    label.setText = lambda s: setattr(label, "text", s)
    label.setStyleSheet = lambda s: setattr(label, "sheet", s)
    label.setToolTip = lambda s: setattr(label, "tip", s)
    name = _update_loaded_file_label(label, "C:\\data\\run 3\\spectrum_A.xlsx")
    assert name == "spectrum_A.xlsx"
    assert label.text == " spectrum_A.xlsx"
    assert label.tip == "C:\\data\\run 3\\spectrum_A.xlsx"
    assert CertusTheme.SUCCESS in label.sheet
    assert "bold" in label.sheet


def test_the_plot_title_is_the_stem_of_the_source():
    from certus.ui.certus_index_ui_utils import _set_spectrum_plot_title

    titles = []
    plot = SimpleNamespace(plotItem=SimpleNamespace(setTitle=titles.append))
    _set_spectrum_plot_title(plot, "D:\\spectra\\BK7_witness.v2.csv")
    assert titles == ["Spectrum      BK7_witness.v2"]


def test_the_detected_type_is_shown_and_logged(caplog):
    from certus.ui.certus_index_ui_utils import _display_detected_data_type
    from certus.utils.certus_index_utils import DataType

    label = SimpleNamespace(text="")
    label.setText = lambda s: setattr(label, "text", s)
    log = logging.getLogger("test-index-type")
    with caplog.at_level(logging.INFO, logger="test-index-type"):
        shown = _display_detected_data_type(label, log, DataType.REFLECTION)
    assert label.text == shown
    assert "REFLECTION only" in shown
    assert f"[INDEX.LOAD] data analysis | type={shown}" in caplog.text


def test_the_spectral_range_of_the_target_data_fills_both_spin_boxes_and_is_logged(caplog):
    from certus.ui.certus_index_ui_utils import _update_lambda_bounds_from_target_data

    boxes = [SimpleNamespace(value=None) for _ in range(2)]
    for box in boxes:
        box.setValue = lambda v, b=box: setattr(b, "value", v)
    log = logging.getLogger("test-index-range")
    with caplog.at_level(logging.INFO, logger="test-index-range"):
        bounds = _update_lambda_bounds_from_target_data(pd.DataFrame({"lambda": [700.0, 400.0, 550.5]}), boxes[0], boxes[1], log)
    assert bounds == (400.0, 700.0)
    assert (boxes[0].value, boxes[1].value) == (400.0, 700.0)
    assert "[INDEX.LOAD] spectral range | min=400.0 nm | max=700.0 nm" in caplog.text


def test_the_loaded_spectrum_is_described_in_the_log_by_path_name_and_size(tmp_path, caplog):
    from certus.ui.certus_index_ui_utils import _log_loaded_spectrum_metadata

    log = logging.getLogger("test-index-meta")
    path = tmp_path / "scan.csv"
    with caplog.at_level(logging.INFO, logger="test-index-meta"):
        _log_loaded_spectrum_metadata(log, str(path), pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))
    text = caplog.text
    assert "[FILE] Spectrum loaded:" in text
    assert "[FILE] Name: scan.csv" in text
    assert "[FILE] Dimensions: 3 rows × 2 columns" in text


def _nk_frame(n, k):
    return pd.DataFrame({"n_calc": n, "k_calc": k})


_TLU_PARAMS = object()  # any value that is not None


def _nk_result(method="Sellmeier", lambda_max_fit=900.0, tlu_params=_TLU_PARAMS):
    return SimpleNamespace(optimization_stats={"method": method}, config=SimpleNamespace(lambda_max_fit=lambda_max_fit), tlu_params=tlu_params)


def test_the_nk_inputs_without_their_columns_are_refused_and_logged(caplog):
    from certus.ui.certus_index_ui_utils import _prepare_nk_plot_inputs

    log = logging.getLogger("test-index-nk")
    with caplog.at_level(logging.ERROR, logger="test-index-nk"):
        assert _prepare_nk_plot_inputs(np.array([500.0]), pd.DataFrame({"n_calc": [1.5]}), _nk_result(), log) is None
    assert "Missing n_calc or k_calc" in caplog.text


def test_all_nan_arrays_are_refused_and_a_single_nan_is_not(caplog):
    from certus.ui.certus_index_ui_utils import _prepare_nk_plot_inputs

    log = logging.getLogger("test-index-nk2")
    wls = np.array([500.0, 600.0])
    with caplog.at_level(logging.ERROR, logger="test-index-nk2"):
        assert _prepare_nk_plot_inputs(wls, _nk_frame([np.nan, np.nan], [0.1, 0.2]), _nk_result(), log) is None
        assert _prepare_nk_plot_inputs(wls, _nk_frame([1.5, 1.6], [np.nan, np.nan]), _nk_result(), log) is None
    assert "all NaN" in caplog.text
    assert _prepare_nk_plot_inputs(wls, _nk_frame([1.5, np.nan], [0.1, 0.2]), _nk_result(), log) is not None


def test_beyond_the_fit_range_the_nk_curves_are_blanked_unless_the_method_is_a_spline_or_has_no_tlu_parameters():
    from certus.ui.certus_index_ui_utils import _prepare_nk_plot_inputs

    wls = np.array([500.0, 900.0, 1000.0, 1200.0])
    frame = _nk_frame([1.5, 1.5, 1.4, 1.4], [0.0, 0.0, 0.01, 0.02])
    log = logging.getLogger("test-index-nk3")
    n, k, method, lambda_max, tlu = _prepare_nk_plot_inputs(wls, frame, _nk_result(), log)
    assert (method, lambda_max, tlu) == ("Sellmeier", 900.0, True)
    assert n.tolist()[:2] == [1.5, 1.5] and np.isnan(n[2:]).all()  # the infrared is blanked, 900 itself is kept
    assert k.tolist()[:2] == [0.0, 0.0] and np.isnan(k[2:]).all()
    assert frame["n_calc"].tolist() == [1.5, 1.5, 1.4, 1.4]  # the frame is not modified
    for result in (_nk_result(method="B-Spline fit"), _nk_result(tlu_params=None), _nk_result(lambda_max_fit=None)):
        n2, _k2, _m, _l, tlu2 = _prepare_nk_plot_inputs(wls, frame, result, log)
        assert tlu2 is False
        assert not np.isnan(n2).any()


def test_the_log_axis_writes_decades_as_plain_decimals():
    from certus.ui.certus_index_ui_utils import KLogAxisItem

    assert KLogAxisItem.tickStrings(None, [-2, -1, 0, 1, 2.5], 1, 1) == ["0.01", "0.1", "1", "10", "316.227766"]
    assert KLogAxisItem.tickStrings(None, [400], 1, 1) == [""]  # 10**400 cannot be written: the tick is blank, not an error


# =============================================================================
# certus_substrate_plot_utils


def _regions(plot_widget):
    import pyqtgraph as pg

    return [item.getRegion() for item in plot_widget.plotItem.items if isinstance(item, pg.LinearRegionItem)]


@pytest.fixture
def plot_widget(qapp):
    import pyqtgraph as pg

    widget = pg.PlotWidget()
    yield widget
    widget.close()


def test_the_part_of_the_data_outside_the_fit_window_is_shaded_on_both_sides(plot_widget):
    from certus.ui.certus_substrate_plot_utils import _add_pg_fit_band_outside_shading

    _add_pg_fit_band_outside_shading(plot_widget, 450.0, 550.0, 400.0, 700.0)
    assert _regions(plot_widget) == [(400.0, 450.0), (550.0, 700.0)]


def test_a_fit_window_given_backwards_or_reaching_past_the_data_is_clipped_to_the_data(plot_widget):
    from certus.ui.certus_substrate_plot_utils import _add_pg_fit_band_outside_shading

    _add_pg_fit_band_outside_shading(plot_widget, 550.0, 450.0, 700.0, 400.0)  # both pairs reversed
    assert _regions(plot_widget) == [(400.0, 450.0), (550.0, 700.0)]
    plot_widget.plotItem.clear()
    _add_pg_fit_band_outside_shading(plot_widget, 100.0, 550.0, 400.0, 700.0)  # starts before the data: nothing on the left
    assert _regions(plot_widget) == [(550.0, 700.0)]
    plot_widget.plotItem.clear()
    _add_pg_fit_band_outside_shading(plot_widget, 800.0, 900.0, 400.0, 700.0)  # starts after the data: all of it is outside
    assert _regions(plot_widget) == [(400.0, 700.0)]


@pytest.mark.parametrize(
    "arguments",
    [(300.0, 800.0, 400.0, 700.0), (450.0, 550.0, 500.0, 500.0), (float("nan"), 550.0, 400.0, 700.0), (450.0, 550.0, 400.0, float("inf"))],
    ids=["window covers the data", "no data range", "nan bound", "infinite bound"],
)
def test_nothing_is_shaded_when_there_is_nothing_to_shade_or_the_bounds_are_not_numbers(plot_widget, arguments):
    from certus.ui.certus_substrate_plot_utils import _add_pg_fit_band_outside_shading

    _add_pg_fit_band_outside_shading(plot_widget, *arguments)
    assert _regions(plot_widget) == []


def test_the_split_puts_nan_outside_the_mask_for_the_gray_curve_and_inside_it_for_the_coloured_one():
    from certus.ui.certus_substrate_plot_utils import _nan_split_band_y

    y = np.array([1.0, 2.0, 3.0, 4.0])
    outside, inside = _nan_split_band_y(y, np.array([False, True, True, False]))
    assert outside.tolist()[0] == 1.0 and np.isnan(outside[1]) and np.isnan(outside[2]) and outside[3] == 4.0
    assert np.isnan(inside[0]) and inside[1:3].tolist() == [2.0, 3.0] and np.isnan(inside[3])
    assert _nan_split_band_y([1, 2], None)[0] is None
    assert _nan_split_band_y([1, 2], None)[1].tolist() == [1.0, 2.0]


class _Recorder:
    def __init__(self):
        self.calls = []

    def plot(self, x, y, **kwargs):
        self.calls.append((np.asarray(x).tolist(), np.asarray(y).tolist(), kwargs))
        return len(self.calls)


def test_a_curve_without_a_mask_is_drawn_once_in_the_inside_pen_and_non_finite_points_are_dropped():
    from certus.ui.certus_substrate_plot_utils import _pg_plot_xy_split_band

    rec = _Recorder()
    handle = _pg_plot_xy_split_band(rec, [400.0, 500.0, np.nan, 700.0], [0.1, np.inf, 0.3, 0.4], None, "in", "out", name="T")
    assert handle == 1
    assert rec.calls == [([400.0, 700.0], [0.1, 0.4], {"pen": "in", "name": "T"})]
    assert _pg_plot_xy_split_band(rec, [np.nan], [np.nan], None, "in", "out") is None


def test_a_curve_with_a_mask_is_drawn_gray_outside_first_then_coloured_inside():
    from certus.ui.certus_substrate_plot_utils import _pg_plot_xy_split_band

    rec = _Recorder()
    handle = _pg_plot_xy_split_band(rec, [400.0, 500.0, 600.0], [0.1, 0.2, 0.3], np.array([False, True, True]), "in", "out", name="T")
    assert handle == 2  # the handle of the second plot, the coloured one
    assert [c[2] for c in rec.calls] == [{"pen": "out"}, {"pen": "in", "name": "T"}]
    outside, inside = rec.calls[0][1], rec.calls[1][1]
    assert outside[0] == 0.1 and np.isnan(outside[1]) and np.isnan(outside[2])
    assert np.isnan(inside[0]) and inside[1:] == [0.2, 0.3]


def test_the_mask_follows_the_points_that_survive_the_finite_filter():
    from certus.ui.certus_substrate_plot_utils import _pg_plot_xy_split_band

    rec = _Recorder()
    _pg_plot_xy_split_band(rec, [400.0, np.nan, 600.0], [0.1, 0.2, 0.3], np.array([True, True, False]), "in", "out")
    assert rec.calls[0][0] == [400.0, 600.0]
    assert rec.calls[1][1][0] == 0.1 and np.isnan(rec.calls[1][1][1])  # 600 is outside the mask


def test_a_scatter_is_drawn_as_symbols_without_a_line_and_outside_points_use_the_outside_symbol_pen():
    from certus.ui.certus_substrate_plot_utils import _pg_plot_scatter_split_band

    rec = _Recorder()
    handle = _pg_plot_scatter_split_band(rec, [400.0, 500.0], [0.1, 0.2], np.array([False, True]), "in", "out", symbol="o", symbol_size=7.0, name="R")
    assert handle == 2
    assert rec.calls[0][2] == {"symbolPen": "out", "pen": None, "symbol": "o", "symbolSize": 7.0}
    assert rec.calls[1][2] == {"symbolPen": "in", "name": "R", "pen": None, "symbol": "o", "symbolSize": 7.0}


def test_a_scatter_with_no_mask_or_a_mask_of_the_wrong_length_is_drawn_once():
    from certus.ui.certus_substrate_plot_utils import _pg_plot_scatter_split_band

    rec = _Recorder()
    _pg_plot_scatter_split_band(rec, [400.0, 500.0, 600.0], [0.1, 0.2, 0.3], None, "in", "out")
    _pg_plot_scatter_split_band(rec, [400.0, 500.0, 600.0], [0.1, 0.2, 0.3], np.array([True, False]), "in", "out")  # two flags for three points
    assert len(rec.calls) == 2
    assert all(call[2]["symbolPen"] == "in" for call in rec.calls)
    assert _pg_plot_scatter_split_band(rec, [np.nan], [1.0], None, "in", "out") is None


# =============================================================================
# certus_qss_icons


@pytest.fixture
def glyphs(qapp, tmp_path, monkeypatch):
    import certus.utils.certus_qss_icons as icons

    monkeypatch.setattr(icons, "CACHE_DIR", tmp_path / "glyphs")
    icons.glyph_path.cache_clear()
    yield icons
    icons.glyph_path.cache_clear()


def _pixels(path):
    from PyQt6.QtGui import QImage

    image = QImage(path)
    assert not image.isNull()
    return image


def test_a_glyph_is_a_png_in_the_cache_named_by_glyph_colour_and_size(glyphs):
    path = glyphs.glyph_path("check", "#AABBCC", 16)
    assert path.endswith("/check_aabbcc_16.png")
    assert "\\" not in path  # QSS reads a backslash as an escape
    assert Path(path).stat().st_size > 0
    assert Path(path).parent == glyphs.CACHE_DIR


def test_a_dot_is_painted_in_the_asked_colour_in_the_middle_and_nothing_at_the_corners(glyphs):
    image = _pixels(glyphs.glyph_path("dot", "#ff0000", 16))
    assert (image.width(), image.height()) == (16, 16)
    centre = image.pixelColor(8, 8)
    assert (centre.red(), centre.green(), centre.blue()) == (255, 0, 0)
    assert centre.alpha() == 255
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(15, 15).alpha() == 0
    assert image.pixelColor(10, 8).alpha() > 128  # radius 3.5 px: the pixel two and a half from the centre is inside
    assert image.pixelColor(14, 8).alpha() < 128  # and the one six and a half away is not


def test_a_check_mark_is_painted_in_the_asked_colour_on_a_transparent_ground(glyphs):
    image = _pixels(glyphs.glyph_path("check", "#00ff00", 16))
    opaque = [(x, y) for x in range(16) for y in range(16) if image.pixelColor(x, y).alpha() > 128]
    assert len(opaque) > 10  # a tick, not a smudge and not nothing
    assert all(image.pixelColor(x, y).green() > 200 and image.pixelColor(x, y).red() < 60 for x, y in opaque)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(7, 11).alpha() > 128  # the bottom of the tick
    assert image.pixelColor(12, 5).alpha() > 128  # the end of its long leg
    assert image.pixelColor(2, 2).alpha() == 0
    assert image.pixelColor(14, 13).alpha() == 0


def test_the_size_is_honoured(glyphs):
    image = _pixels(glyphs.glyph_path("dot", "#336699", 24))
    assert (image.width(), image.height()) == (24, 24)


def test_an_unknown_glyph_is_an_error_naming_the_known_ones(glyphs):
    with pytest.raises(KeyError, match=r"unknown glyph 'star'.*\['check', 'dot'\]"):
        glyphs.glyph_path("star", "#000000")


def test_a_glyph_is_painted_once_and_then_read_from_the_cache(glyphs, monkeypatch):
    first = glyphs.glyph_path("dot", "#123456", 16)
    glyphs.glyph_path.cache_clear()  # force the second call to look at the disk, as a new process would
    monkeypatch.setitem(glyphs._PAINTERS, "dot", lambda *_a: pytest.fail("painted again"))
    assert glyphs.glyph_path("dot", "#123456", 16) == first


def test_when_the_cache_cannot_be_written_the_path_is_empty_so_that_the_caller_omits_the_property(glyphs, tmp_path, monkeypatch):
    blocker = tmp_path / "a_file_where_a_folder_should_be"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(glyphs, "CACHE_DIR", blocker / "glyphs")
    assert glyphs.glyph_path("check", "#445566", 16) == ""


def test_without_an_application_no_pixmap_is_touched_and_the_path_is_empty():
    """QPixmap aborts the process when no QGuiApplication exists: a stylesheet builder may run before the app is up."""
    code = "from certus.utils.certus_qss_icons import glyph_path\nprint(repr(glyph_path('check', '#112233')))"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    assert done.stdout.strip() == "''"
