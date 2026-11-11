"""The corridor code of the INDEX SPLINE window is cut in slices, one per feature, and each slice keeps what it was given.

The corridor methods were spread over the classes of the window by the history of the files, not by what they do: the
life cycle of a corridor run sat in four classes of four modules. Each slice is a mixin of its own module that holds the
methods of one feature, moved there with their text unchanged (scripts/refactor_guard.py proved the bytecode). The classes
that held them, `_CorridorControlMixin` and `CertusIndexSplineCorridorUIMixin`, inherit the slices, so the window is built
from the same list of bases as before.

`SLICES` is the table of what moved where. What this file pins:

* the window resolves each method to the slice, and to nothing above it;
* a slice is a plain mixin: no constructor, no base but `object` (the window is a QMainWindow);
* a class that inherits several slices names them in one order, the order of `SLICES`;
* a slice module imports nothing of the window at module level: not the modules above the group, and the interface
  layer through the gateway only. Otherwise the module that defines the window would import itself.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

ROOT = Path(__file__).resolve().parents[2]
UI = "certus.ui.certus_index_spline_"

#: Module of the slice -> (its class, the methods it holds). The order of the slices is the order of the bases.
SLICES = {
    "corridor_run": (
        "_CorridorRunMixin",
        (
            "_start_deferred_corridor_worker",
            "_finish_curve_minimum_deep_worker_done",
            "_finish_rmse_heal_worker_done",
            "_set_corridor_grid_busy",
            "_set_corridor_grid_progress_ui",
            "_schedule_corridor_auto_refine",
            "_continue_corridor_auto_refine_after_deep",
            "_set_corridor_grid_completed_badge",
            "_refresh_corridors_gui_state_labels",
            "_on_btn_corridor_clicked",
            "_on_corridor_chk_state_changed",
            "_is_rmse_d_grid_worker_finalize_dict",
            "_merge_rmse_grid_promotion_into_nominal",
            "_on_corr_mode_changed",
            "_on_corridor_rmse_grid_live_update",
        ),
    ),
    "corridor_rmse_view": (
        "_CorridorRmseViewMixin",
        (
            "_build_tab_corridor_rmse",
            "_refresh_corridor_rmse_robust_view",
            "_update_corridor_rmse_state_bar",
            "_corridor_profile_source_result",
            "_set_corridor_rmse_view_data_bounds",
            "_on_corridor_rmse_lock_scale_toggled",
            "_on_corridor_rmse_plot_clicked",
            "_robust_interval_from_local_quadratic",
            "_build_corridor_labels",
        ),
    ),
    "corridor_interval": (
        "_CorridorIntervalMixin",
        (
            "_apply_corridor_preset_auto_robust",
            "_sync_corridor_manual_controls",
            "_generate_corridor_from_current_grid",
            "_use_robust_corridor_interval",
            "_corridor_manual_half_width_nm",
            "_set_corridor_manual_interval_preview",
            "_set_corridor_manual_bounds_labels",
            "_corridor_manual_max_half_width_nm",
            "_reset_corridor_manual_controls",
            "_on_corridor_manual_slider_changed",
            "_build_corridor_tab_generate",
        ),
    ),
    "corridor_nk": (
        "_CorridorNkMixin",
        (
            "_interp_corridor_value",
            "_k_corridor_crosshair_formatter",
            "_build_tab_data_corridor",
            "_copy_corridor_to_clipboard",
            "_export_corridor_csv",
            "_refresh_corridor_table",
            "_build_tab_corridor",
        ),
    ),
    "corridor_rmse_plot": (
        "_CorridorRmsePlotMixin",
        (
            "_plot_rmse_data_scatter",
            "_plot_the_reversal_and_fallback_points",
            "_plot_the_breakpoint_events",
            "_draw_the_local_parabola",
            "_corridor_profile_arrays",
            "_prep_rmse_plot_data",
            "_draw_corridor_curvature_label",
            "_plot_corridor_rmse_tab",
            "_manual_grid_note",
            "_write_the_rmse_summary",
        ),
    ),
}
#: The classes that inherit the slices, and the slices each one takes.
COMPOSITES = {
    "settings:_CorridorControlMixin": ("_CorridorRunMixin", "_CorridorRmseViewMixin", "_CorridorIntervalMixin"),
    "corridorui_mixin:CertusIndexSplineCorridorUIMixin": (
        "_CorridorRunMixin",
        "_CorridorRmseViewMixin",
        "_CorridorIntervalMixin",
        "_CorridorNkMixin",
    ),
    "rendering:_PlotMixin": ("_CorridorRmsePlotMixin",),
}
#: The modules above the corridor group: a slice that imported one at module level would close an import cycle.
ABOVE = ("common", "ui", "settings", "execution", "rendering", "mixins_ui")
GATEWAY = f"{UI}corridor_ui"


def slice_class(stem: str) -> type:
    return getattr(importlib.import_module(UI + stem), SLICES[stem][0])


@pytest.mark.parametrize("stem", sorted(SLICES))
def test_the_window_takes_each_method_from_its_slice(stem) -> None:
    klass = slice_class(stem)
    for name in SLICES[stem][1]:
        assert name in vars(klass), f"{klass.__name__} does not define {name}"
        assert inspect.getattr_static(CertusIndexSplineApp, name) is vars(klass)[name], f"{name} is not the one of {klass.__name__}"


@pytest.mark.parametrize("stem", sorted(SLICES))
def test_a_slice_holds_what_the_table_says_and_nothing_else(stem) -> None:
    klass = slice_class(stem)
    defined = {name for name, value in vars(klass).items() if callable(getattr(value, "__func__", value))}
    assert defined == set(SLICES[stem][1])


@pytest.mark.parametrize("stem", sorted(SLICES))
def test_a_slice_is_a_plain_mixin(stem) -> None:
    klass = slice_class(stem)
    assert klass.__bases__ == (object,)
    assert "__init__" not in vars(klass)
    assert "Mixin" in klass.__name__


@pytest.mark.parametrize("composite", sorted(COMPOSITES))
def test_a_class_that_inherits_slices_names_them_in_the_order_of_the_table(composite) -> None:
    stem, _, name = composite.partition(":")
    klass = getattr(importlib.import_module(UI + stem), name)
    canonical = [SLICES[s][0] for s in SLICES]
    bases = [base.__name__ for base in klass.__bases__]
    assert bases == [n for n in canonical if n in COMPOSITES[composite]]
    assert klass in CertusIndexSplineApp.__mro__


@pytest.mark.parametrize("stem", sorted(SLICES))
def test_a_slice_module_imports_nothing_of_the_window_at_module_level(stem) -> None:
    tree = ast.parse((ROOT / f"{(UI + stem).replace('.', '/')}.py").read_text(encoding="utf-8-sig"))
    imported = [node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)]
    imported += [alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names]
    above = [m for m in imported if m in {UI + s for s in ABOVE} or (m.startswith(UI) and m.endswith("_mixin"))]
    assert above == [], f"{stem} imports a module that is above the corridor group"
    interface = [m for m in imported if m.startswith("certus.ui.") and not m.startswith(f"{UI}corridor")]
    assert interface == [], f"{stem} imports the interface layer itself: take the name from {GATEWAY}"
