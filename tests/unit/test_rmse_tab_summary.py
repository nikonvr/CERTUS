"""The summary line of the RMSE(d) tab is written by two methods of their own (audit v2, plan S5.2).

`_PlotMixin._plot_corridor_rmse_tab` draws the RMSE(d) tab of the corridors and writes the sentence above it: 290 lines, complexity 68. The sentence comes out in two pieces, pinned here on a
namespace with a label recorder (no window, no plot):

    _manual_grid_note        the part about the manual d grid: breakpoints, extra points, what triggered them and towards which side they broke
    _write_the_rmse_summary  the whole sentence: best thickness and RMSE, plot / grid / Deltad notes, robust interval, parabola, manual interval, live-preview warning
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.spline.certus_index_spline_rendering import _PlotMixin

# --- _manual_grid_note -------------------------------------------------------------------------------------------------------------------


def note(src, events=None, left=0, right=0):
    return _PlotMixin._manual_grid_note(SimpleNamespace(), src, [] if events is None else events, left, right)


def test_a_d_grid_that_is_not_the_manual_one_has_no_note():
    assert note({}) == ""
    assert note({"profile_d_status": "auto", "profile_d_manual_grid_breakpoint_count": 4}) == ""
    assert note({"profile_d_status": 123}) == ""


def test_the_manual_grid_says_so():
    assert note({"profile_d_status": "manual_grid"}) == " | manual grid (re-run)"


@pytest.mark.parametrize(
    ("breakpoints", "extra", "said"),
    [(0, 0, False), (2, 0, True), (0, 5, True), (3, 7, True)],
    ids=["none", "breakpoints only", "extra points only", "both"],
)
def test_the_breakpoints_and_the_extra_points_are_counted_when_there_are_any(breakpoints, extra, said):
    src = {"profile_d_status": "manual_grid", "profile_d_manual_grid_breakpoint_count": breakpoints, "profile_d_manual_grid_extra_points": extra}
    expected = " | manual grid (re-run)" + (f" | breakpoints detected={breakpoints} | points extra={extra}" if said else "")
    assert note(src) == expected


def test_the_counts_are_read_as_integers():
    src = {"profile_d_status": "manual_grid", "profile_d_manual_grid_breakpoint_count": "3", "profile_d_manual_grid_extra_points": 4.0}
    assert note(src) == " | manual grid (re-run) | breakpoints detected=3 | points extra=4"


def test_what_triggered_the_breakpoints_and_where_they_broke_is_added_when_there_are_events():
    events = [
        {"trigger_prevN": 1.0},
        {"trigger_prevN": 0.5, "trigger_parabola": 1.0},
        {"trigger_parabola": 0.6},
        "junk",
        {},
    ]
    src = {"profile_d_status": "manual_grid"}
    assert note(src, events, left=2, right=1) == " | manual grid (re-run) | causes(prevN=1, parabola=2) | direction(chosen left=2, right=1)"


def test_a_threshold_of_exactly_a_half_does_not_count_as_a_cause():
    events = [{"trigger_prevN": 0.5, "trigger_parabola": 0.5}]
    assert "causes(prevN=0, parabola=0)" in note({"profile_d_status": "manual_grid"}, events)


@pytest.mark.parametrize("events", [[], None, (), {"trigger_prevN": 1.0}], ids=["empty", "none", "tuple", "dict"])
def test_without_a_list_of_events_there_is_no_cause_nor_direction(events):
    assert note({"profile_d_status": "manual_grid"}, events) == " | manual grid (re-run)"


def test_the_events_are_ignored_outside_the_manual_grid():
    assert note({"profile_d_status": "auto"}, [{"trigger_prevN": 1.0}], left=1, right=1) == ""


def test_the_counts_come_before_the_causes():
    src = {"profile_d_status": "manual_grid", "profile_d_manual_grid_breakpoint_count": 1}
    text = note(src, [{"trigger_prevN": 1.0}], left=1)
    assert text.index("breakpoints detected") < text.index("causes(") < text.index("direction(")


# --- _write_the_rmse_summary -------------------------------------------------------------------------------------------------------------


class Label:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def setText(self, text) -> None:
        self.texts.append(text)


def summary(**changes):
    values = dict(
        src={},
        d_plot=np.arange(5.0),
        d_vis=np.arange(3.0),
        parab_fit={"ok": True},
        envelope_display=False,
        is_live_grid=False,
        live_parab=True,
        d_best=100.0,
        rmse_best=0.001234567,
        delta_rb=0.0002,
        rb_ok=True,
        d_lo_rb=99.0,
        d_hi_rb=101.0,
        slope_b=1.5e-5,
        d_center=100.2,
        d_lo_man=float("nan"),
        d_hi_man=float("nan"),
        _grid_note="",
    )
    attributes = changes.pop("attributes", {})
    values.update(changes)
    label = Label()
    window = SimpleNamespace(lbl_corridor_rmse_summary=label, **attributes)
    _PlotMixin._write_the_rmse_summary(window, *values.values())
    return label.texts


def one(**changes) -> str:
    (text,) = summary(**changes)
    return text


BASE = (
    "Best computed thickness: d* = 100.000 nm | RMSE(d*) = 0.001235 | samples = 5"
    " | robust Delta=0.000200 -> interval ? [99.000, 101.000] nm | slope@d*?+1.50e-05 /nm | parabola center?100.200 nm"
)


def test_the_summary_is_written_once_and_says_the_best_thickness_the_rmse_the_samples_the_robust_interval_and_the_parabola():
    assert summary() == [BASE]


def test_the_plot_note_counts_the_points_of_the_envelope_when_it_is_displayed():
    text = one(envelope_display=True)
    assert text.startswith("Best computed thickness: d* = 100.000 nm | RMSE(d*) = 0.001235 | samples = 5 | plot: lower envelope (3/5 pts)")


def test_without_the_envelope_there_is_no_plot_note():
    assert "plot: lower envelope" not in one()


def test_the_grid_note_is_added_right_after_the_samples_and_the_plot_note():
    text = one(envelope_display=True, _grid_note=" | manual grid (re-run)")
    assert " | plot: lower envelope (3/5 pts) | manual grid (re-run) | robust Delta" in text


def test_the_smart_interval_is_added_after_the_grid_note_when_the_window_has_one():
    text = one(_grid_note=" | G", attributes={"_corridor_rmse_smart_interval": (98.5, 101.25)})
    assert " | G | Deltad code ? [98.500, 101.250] nm | robust Delta" in text


def test_without_a_smart_interval_there_is_no_deltad_note():
    assert "Deltad code" not in one(attributes={"_corridor_rmse_smart_interval": None})
    assert "Deltad code" not in one()


def test_the_samples_are_counted_on_all_the_points_not_on_the_visible_ones():
    assert "samples = 7" in one(d_plot=np.arange(7.0))


def test_a_robust_interval_that_could_not_be_found_says_so_and_drops_the_parabola():
    text = one(rb_ok=False)
    assert text.endswith("samples = 5 | robust interval unavailable (insufficient local convex fit)")
    assert "parabola center" not in text


def test_the_parabola_centre_is_given_only_when_the_fit_is_ok():
    assert "parabola center" not in one(parab_fit={"ok": False})
    assert "parabola center" not in one(parab_fit={})


def test_the_robust_interval_and_the_slope_are_written_with_their_formats():
    text = one(delta_rb=0.00031234567, d_lo_rb=98.76543, d_hi_rb=101.23456, slope_b=-2.5e-4)
    assert "robust Delta=0.000312 -> interval ? [98.765, 101.235] nm | slope@d*?-2.50e-04 /nm" in text


def test_a_manual_interval_is_a_preview_until_it_is_active():
    text = one(d_lo_man=99.5, d_hi_man=100.5)
    assert text.endswith(" | manual preview ? [99.500, 100.500] nm")
    active = one(d_lo_man=99.5, d_hi_man=100.5, attributes={"_corridor_rmse_manual_active": True})
    assert active.endswith(" | manual active ? [99.500, 100.500] nm")


def test_an_interval_with_one_bound_missing_is_not_a_manual_interval():
    assert "manual" not in one(d_lo_man=99.5)
    assert "manual" not in one(d_hi_man=100.5)


def test_a_manual_corridor_adds_how_many_profiled_points_it_selected_and_their_range():
    src = {"manual_corridor_active": True, "manual_corridor_selected_count": 12.0, "manual_corridor_selected_d_range_nm": (99.6, 100.4)}
    text = one(src=src, d_lo_man=99.5, d_hi_man=100.5)
    assert text.endswith(" | manual preview ? [99.500, 100.500] nm (12 profiled points) | sampled in [99.600, 100.400] nm")


def test_the_manual_corridor_range_needs_two_finite_bounds():
    for odd in ((99.6,), (99.6, float("nan")), "no", None, (float("inf"), 100.4)):
        src = {"manual_corridor_active": True, "manual_corridor_selected_d_range_nm": odd}
        text = one(src=src, d_lo_man=99.5, d_hi_man=100.5)
        assert "(0 profiled points)" in text
        assert "sampled in" not in text


def test_a_corridor_that_is_not_active_adds_nothing():
    src = {"manual_corridor_active": False, "manual_corridor_selected_count": 12}
    assert "profiled points" not in one(src=src, d_lo_man=99.5, d_hi_man=100.5)


def test_a_live_preview_without_the_parabola_says_the_fits_are_paused():
    assert one(is_live_grid=True, live_parab=False).endswith(" | live preview: points only (parabola/robust fit paused)")
    assert "live preview" not in one(is_live_grid=True, live_parab=True)
    assert "live preview" not in one(is_live_grid=False, live_parab=False)


def test_the_live_preview_warning_comes_last():
    text = one(is_live_grid=True, live_parab=False, d_lo_man=99.5, d_hi_man=100.5)
    assert text.index("manual preview") < text.index("live preview")


# --- the tab hands them their work -------------------------------------------------------------------------------------------------------


def test_the_tab_writes_its_summary_only_when_it_has_the_label_and_hands_the_grid_note_over():
    source = inspect.getsource(_PlotMixin._plot_corridor_rmse_tab)
    assert 'if hasattr(self, "lbl_corridor_rmse_summary"):' in source
    assert "_grid_note = self._manual_grid_note(src, bp_events, bp_dir_left, bp_dir_right)" in source
    assert source.index("_grid_note = self._manual_grid_note(") < source.index("self._write_the_rmse_summary(")
    assert source.index('if hasattr(self, "lbl_corridor_rmse_summary"):') < source.index("_grid_note = self._manual_grid_note(")
