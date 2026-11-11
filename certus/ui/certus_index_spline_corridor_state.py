"""CERTUS-INDEX-SPLINE corridors - the state the corridor code keeps on the window, declared in one place.

The corridor code keeps its state as plain attributes of the window (`self._corridor_...`). They are written from nine
modules, and they are born in three kinds of places: the constructor of the window, the function that builds the RMSE(d)
tab, and, for the rest, whichever function first computes them. A reader that may run before that birth goes through
`getattr(self, name, fallback)`.

This table declares each of them: its type, the value it has before any corridor was computed, the function where the
corridor code first sets it, whether `_load_defaults` puts it back, and the fallback expressions the code passes to
`getattr` today. The constructor of the window reads it, first thing, to give every attribute that value
(`initial_corridor_state`): no reader depends any more on which function ran before it, and a fallback of `getattr` is
only what a fake host of the tests gets. tests/unit/test_the_corridor_mixins_declare_what_they_read_on_the_window.py
holds the code to the table, so that a new attribute, a new fallback or a moved birth place has to be written down here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

import numpy as np

from certus.ui.certus_index_spline_corridor_common import _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN


class CorridorStateEntry(NamedTuple):
    """One attribute of the window that belongs to the corridor code."""

    annotation: str  #: its type, as an annotation
    default: Callable[[], Any]  #: makes the value it has before any corridor was computed
    born_in: str  #: `module:Class.function` (module without the `certus_index_spline_` prefix) where it is first set
    reset: bool  #: True when `CertusIndexSplineStateMixin._load_defaults` sets it back
    fallbacks: tuple[str, ...]  #: the defaults passed to `getattr(self, name, ...)`, as `ast.unparse` writes them


def _nan() -> float:
    return float("nan")


def _no_points() -> np.ndarray:
    return np.array([], dtype=np.float64)


def _nothing() -> None:
    return None


def _empty_list() -> list:
    return []


_INIT = "ui:CertusIndexSplineApp.__init__"
_RMSE_TAB = "corridor_rmse_view:_CorridorRmseViewMixin._build_tab_corridor_rmse"
_PRESET = "corridor_interval:_CorridorIntervalMixin._apply_corridor_preset_auto_robust"
_K_TAB = "corridor_tab:_CorridorTabMixin._plot_corridor_tab"
_RMSE_PLOT = "corridor_rmse_plot:_CorridorRmsePlotMixin._plot_corridor_rmse_tab"
_NAN = ("float('nan')",)

CORRIDOR_STATE: dict[str, CorridorStateEntry] = {
    # The run: what the grid worker was asked, and what is planned after it.
    "_corridor_rmse_base_snapshot": CorridorStateEntry("dict | None", _nothing, _INIT, True, ()),
    "_corridor_auto_refine_plan": CorridorStateEntry("dict[str, Any] | None", _nothing, _INIT, True, ("None",)),
    "_corridor_rmse_requested_grid": CorridorStateEntry(
        "np.ndarray", lambda: np.array([]), "corridor_worker:_CorridorWorkerMixin._start_corridor_rmse_grid_recalc", False,
        ("np.array([])",),
    ),
    "_corridor_rmse_grid_live_t0": CorridorStateEntry("float", _nan, _RMSE_TAB, False, _NAN),
    "_corridor_rmse_live_last_plot_ts": CorridorStateEntry("float", _nan, _RMSE_TAB, False, _NAN),
    "_corridor_rmse_live_plot_min_interval_s": CorridorStateEntry("float", lambda: 0.12, _RMSE_TAB, False, ("0.12",)),
    # The RMSE(d) curve and what was read on it.
    "_corridor_rmse_d_vals": CorridorStateEntry("np.ndarray", _no_points, _RMSE_TAB, True, ("[]",)),
    "_corridor_rmse_vals": CorridorStateEntry("np.ndarray", _no_points, _RMSE_TAB, True, ("[]",)),
    "_corridor_rmse_best_idx": CorridorStateEntry("int", lambda: -1, _RMSE_TAB, True, ("-1",)),
    "_corridor_rmse_center_nm": CorridorStateEntry("float", _nan, _RMSE_TAB, True, _NAN),
    "_corridor_rmse_robust_lo": CorridorStateEntry("float", _nan, _RMSE_TAB, True, _NAN),
    "_corridor_rmse_robust_hi": CorridorStateEntry("float", _nan, _RMSE_TAB, True, _NAN),
    "_corridor_rmse_robust_ok": CorridorStateEntry("bool", lambda: False, _RMSE_TAB, True, ("False",)),
    "_corridor_rmse_smart_interval": CorridorStateEntry("tuple[float, float] | None", _nothing, _RMSE_PLOT, False, ("None",)),
    "_corridor_rmse_parab_export": CorridorStateEntry("dict | None", _nothing, _RMSE_PLOT, False, ("None",)),
    "_corridor_rmse_robust_export": CorridorStateEntry("dict | None", _nothing, _RMSE_PLOT, False, ("None",)),
    "_corridor_rmse_curvature_label": CorridorStateEntry(
        "Any", _nothing, "corridor_rmse_plot:_CorridorRmsePlotMixin._draw_corridor_curvature_label", False, ("None",)
    ),
    # The interval chosen by hand.
    "_corridor_rmse_manual_active": CorridorStateEntry("bool", lambda: False, _INIT, True, ("False",)),
    "_corridor_rmse_manual_lo": CorridorStateEntry("float", _nan, _INIT, True, _NAN),
    "_corridor_rmse_manual_hi": CorridorStateEntry("float", _nan, _INIT, True, _NAN),
    "_corridor_rmse_manual_slider_scale": CorridorStateEntry("int", lambda: 100, _INIT, False, ("100",)),
    # The settings of the robust preset.
    "_corridor_parabola_half_window_pts": CorridorStateEntry("int", lambda: 4, _PRESET, False, ("4",)),
    "_corridor_symmetric_center_mode": CorridorStateEntry("str", lambda: "parabola", _PRESET, False, ("'parabola'",)),
    "_corridor_adaptive_rmse_ref_half_width_nm": CorridorStateEntry("float", lambda: 1.5, _PRESET, False, ("1.5",)),
    "_corridor_adaptive_rmse_probe_steps_each_side": CorridorStateEntry("int", lambda: 3, _PRESET, False, ("3",)),
    "_corridor_adaptive_rmse_noise_factor": CorridorStateEntry("float", lambda: 3.0, _PRESET, False, ("3.0",)),
    "_corridor_adaptive_rmse_min": CorridorStateEntry(
        "float", lambda: float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN), _PRESET, False, ("_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN",)
    ),
    # The crosshair of the k corridor: nothing sets these before the first plot, and their readers get an empty list.
    "_corridor_k_crosshair_lam": CorridorStateEntry("np.ndarray | list", _empty_list, _K_TAB, False, ("[]",)),
    "_corridor_k_crosshair_nom": CorridorStateEntry("np.ndarray | list", _empty_list, _K_TAB, False, ("[]",)),
    "_corridor_k_crosshair_lo": CorridorStateEntry("np.ndarray | list", _empty_list, _K_TAB, False, ("[]",)),
    "_corridor_k_crosshair_hi": CorridorStateEntry("np.ndarray | list", _empty_list, _K_TAB, False, ("[]",)),
}

def initial_corridor_state() -> dict[str, Any]:
    """A fresh value for every attribute of the table: what a window holds before any corridor was computed."""
    return {name: entry.default() for name, entry in CORRIDOR_STATE.items()}


#: Graphic objects of the RMSE(d) tab: their readers check `hasattr`, they have no value before the tab is built.
GRAPHIC_OBJECTS: tuple[str, ...] = ("_corridor_rmse_curve", "_corridor_rmse_best_marker")

#: Read through `getattr(self, name, None)` and set by nothing: the branch that reads it never runs.
NEVER_ASSIGNED: tuple[str, ...] = ("_corridor_rmse_profile_win",)
