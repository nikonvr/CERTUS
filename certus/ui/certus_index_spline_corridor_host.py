"""CERTUS-INDEX-SPLINE corridors - what the corridor mixins read on the window that hosts them, written down.

A corridor mixin is not a class on its own: its methods read attributes and call methods that the window, or another
mixin of the window, provides. Nothing said which ones. This module says it, and it is a declaration only: nothing imports
it at run time but the test that holds the code to it
(tests/unit/test_the_corridor_mixins_declare_what_they_read_on_the_window.py).

- `CONTRACTS` gives, for each corridor mixin, the names it reads on `self` and does not define: exactly those, so that a
  new coupling, or one that went away, has to be written here.
- The protocols give these names a type. The signatures are those of the methods as the window defines them, and the
  types of the widgets are the classes that build them; `Any` stands where the code builds a value in more than one way.
  A mixin never inherits from a protocol (the window is a QMainWindow: the metaclasses would clash): annotate `self` with
  `CorridorHost` where a type checker should see the contract.

The host is a QMainWindow: what QMainWindow itself provides is not repeated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import logging
    from threading import Event

    import numpy as np
    import pandas as pd
    import pyqtgraph as pg
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QLabel,
        QPushButton,
        QSpinBox,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    from certus.spline.certus_index_spline_core import SplineOptConfig
    from certus.ui.certus_index_spline_corridor_ui import ManualSigmaKnotDialog
    from certus.ui.certus_ui import (
        CertusScientificPlot,
        CertusStatusPill,
        CertusStepper,
        EnhancedProgressWidget,
    )


class IndexSplineRunHost(Protocol):
    """What the rest of the window lends to the corridor code: the worker life cycle, the data, and the methods of the other mixins."""

    _best_live_result: dict | None
    _last_result: dict | None
    _last_run_cfg: SplineOptConfig | None
    _last_worker_result: dict | None
    _manual_knots_dialog: Any
    _stop_event: Event
    df: pd.DataFrame | None
    logger: logging.Logger | None

    def _add_context_page(self, widget: QWidget) -> QWidget: ...
    def _add_curve(self, widget: pg.PlotWidget, x: np.ndarray, y: np.ndarray, color: str, name: str, is_scatter: bool = ..., *, crosshair_primary: bool = ..., pen: Any | None = ...) -> bool: ...
    def _apply_cell_style(self, item: QTableWidgetItem, val: float) -> None: ...
    def _apply_corridor_payload_from_interval(self, *, source: dict[str, Any], display: dict[str, Any], d_lo: float, d_hi: float, status_prefix: str) -> bool: ...
    def _apply_corridor_preset_auto_robust(self) -> None: ...
    def _apply_manual_corridor_selection(self) -> None: ...
    def _build_corridor_tab_generate(self, lay_generate: QVBoxLayout) -> None: ...
    def _build_corridor_tab_rmse_controls(self, lay_rmse: QVBoxLayout) -> None: ...
    def _build_opt_config(self, *, notify: bool = ...) -> SplineOptConfig | None: ...
    def _can_offer_manual_extra_knots(self, result: dict) -> bool: ...
    @staticmethod
    def _cfg_with_result_substrate(cfg_base: SplineOptConfig, result: dict) -> SplineOptConfig: ...
    def _cleanup_thread(self) -> None: ...
    def _corridor_manual_half_width_nm(self) -> float: ...
    def _corridor_profile_source_result(self) -> dict[str, Any] | None: ...
    def _create_empty_context_widget(self, message: str) -> QWidget: ...
    def _display_result_prefer_best_live(self, result: dict) -> dict: ...
    def _ensure_complete_manifest_for_secondary_export(self) -> bool: ...
    def _export_corridor_rmse_envelope_nk_excel(self) -> None: ...
    def _export_corridor_rmse_profile_clipboard(self) -> None: ...
    def _finish_corridor_rmse_d_grid_worker_done(self, result: object) -> None: ...
    def _finish_curve_minimum_deep_worker_done(self, result: object) -> None: ...
    def _finish_rmse_heal_worker_done(self, healed_list: object) -> None: ...
    @staticmethod
    def _fmt_k_data_tab(kv: float) -> str: ...
    @staticmethod
    def _fmt_n_data_tab(nv: float) -> str: ...
    @staticmethod
    def _format_post_optimization_status(display: dict, fallback_result: dict | None = ...) -> str: ...
    def _generate_corridor_auto_smart_from_current_grid(self) -> None: ...
    def _generate_corridor_from_current_grid(self) -> None: ...
    def _generate_corridor_from_partial_grid(self) -> None: ...
    @staticmethod
    def _is_rmse_d_grid_worker_finalize_dict(r: object) -> bool: ...
    @staticmethod
    def _lam_piecewise_report_grid_nm(lo: float, hi: float) -> np.ndarray: ...
    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None: ...
    @staticmethod
    def _manual_mesh_change_log_line(label: str, summary: dict[str, Any]) -> str: ...
    def _manual_postprocess_seed_result(self) -> dict | None: ...
    def _merge_rmse_grid_promotion_into_nominal(self, promoted: dict, *, adoption_log_tag: str) -> None: ...
    def _on_corr_mode_changed(self, _idx: int = ...) -> None: ...
    def _on_corridor_rmse_grid_live_update(self, payload: object) -> None: ...
    def _on_corridor_rmse_lock_scale_toggled(self, _checked: bool) -> None: ...
    def _on_progress(self, v: int, msg: str) -> None: ...
    def _on_worker_done(self, result: object) -> None: ...
    def _on_worker_err(self, msg: str) -> None: ...
    def _open_manual_extra_knots_dialog(self, result: dict) -> None: ...
    def _plot_corridor_rmse_tab(self, src: dict) -> None: ...
    def _plot_result(self, r: dict, *, plot_source: str = ...) -> None: ...
    @staticmethod
    def _post_optimization_ready_status(base_status: str) -> str: ...
    def _prepare_nk_data_tab_series(self, r: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None: ...
    def _prepare_worker_restart(self) -> None: ...
    def _prog_reset_bar(self) -> None: ...
    def _prompt_manual_extra_knots(self, result: dict) -> tuple[list[float], float] | None: ...
    def _refresh_corridor_rmse_robust_view(self) -> None: ...
    def _refresh_corridors_gui_state_labels(self) -> None: ...
    def _refresh_data_table(self, result_override: dict | None = ...) -> None: ...
    def _refresh_manual_dialog_preview(self, dialog: ManualSigmaKnotDialog | None, preview_result: dict | None) -> None: ...
    def _refresh_post_optimization_option_controls(self, *_args) -> None: ...
    @staticmethod
    def _result_uses_split_mesh(result: dict | None) -> bool: ...
    @staticmethod
    def _rmse_from_result_dict(d: dict) -> float: ...
    @staticmethod
    def _robust_interval_from_local_quadratic(d_s: np.ndarray, r_s: np.ndarray, i_best: int, delta_rmse: float, half_window_pts: int) -> tuple[bool, float, float, float, float]: ...
    @staticmethod
    def _runtime_metrics_from_result_dict(d: dict | None) -> tuple[float, float]: ...
    def _schedule_corridor_auto_refine(self, seed: dict, *, rerun_corridor: bool, origin: str) -> bool: ...
    def _set_corridor_grid_busy(self, busy: bool) -> None: ...
    def _set_corridor_grid_completed_badge(self) -> None: ...
    def _set_corridor_grid_progress_ui(self, *, done: int, total: int, base_done: int | None = ..., base_total: int | None = ..., extra_done: int | None = ..., current_d_nm: float | None = ...) -> None: ...
    def _set_corridor_rmse_view_data_bounds(self, d_vals: np.ndarray, r_vals: np.ndarray) -> None: ...
    def _start_auto_best_second_stage(self) -> None: ...
    def _start_corridor_rmse_grid_recalc(self) -> None: ...
    def _start_curve_minimum_deep_refit(self, seed: dict) -> bool: ...
    def _start_manual_sigma_insert_worker(self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float = ...) -> None: ...
    @staticmethod
    def _summarize_manual_mesh_change(before_sigma_knots: Any, after_sigma_knots: Any) -> dict[str, Any]: ...
    def _sync_corridor_manual_controls(self, d_s: np.ndarray, i_best: int) -> None: ...
    def _update_corridor_rmse_state_bar(self, src: dict[str, Any] | None = ...) -> None: ...
    def export_excel(self, auto_export: bool = ...) -> None: ...
    def log(self, msg: str, lvl: str = ...) -> None: ...


class IndexSplineViewHost(Protocol):
    """The widgets of the window, outside the corridor tabs, that the corridor code reads or drives."""

    _stepper: CertusStepper
    btn_run: QPushButton
    btn_stop: QPushButton
    lbl_status: CertusStatusPill
    progress_widget: EnhancedProgressWidget
    tabs_main: QTabWidget


class CorridorStateHost(Protocol):
    """The corridor state kept on the window: one attribute per entry of CORRIDOR_STATE."""

    _corridor_auto_refine_plan: dict[str, Any] | None
    _corridor_k_crosshair_hi: np.ndarray | list
    _corridor_k_crosshair_lam: np.ndarray | list
    _corridor_k_crosshair_lo: np.ndarray | list
    _corridor_k_crosshair_nom: np.ndarray | list
    _corridor_rmse_base_snapshot: dict | None
    _corridor_rmse_best_idx: int | None
    _corridor_rmse_center_nm: float
    _corridor_rmse_curvature_label: Any
    _corridor_rmse_d_vals: np.ndarray
    _corridor_rmse_grid_live_t0: float
    _corridor_rmse_live_last_plot_ts: float
    _corridor_rmse_live_plot_min_interval_s: float
    _corridor_rmse_manual_active: bool
    _corridor_rmse_manual_hi: float
    _corridor_rmse_manual_lo: float
    _corridor_rmse_manual_slider_scale: int
    _corridor_rmse_parab_export: dict | None
    _corridor_rmse_requested_grid: np.ndarray
    _corridor_rmse_robust_export: dict | None
    _corridor_rmse_robust_hi: float
    _corridor_rmse_robust_lo: float
    _corridor_rmse_robust_ok: bool
    _corridor_rmse_smart_interval: tuple[float, float] | None
    _corridor_rmse_vals: np.ndarray


class CorridorWidgetsHost(Protocol):
    """The widgets and the graphic objects of the corridor tabs."""

    _corridor_rmse_best_marker: pg.InfiniteLine
    _corridor_rmse_curve: pg.PlotDataItem
    _idx_tab_corridor: Any
    _idx_tab_corridor_rmse: Any
    btn_corridor_generate_auto_smart_grid: Any
    btn_corridor_generate_from_grid: Any
    btn_corridor_generate_from_partial_grid: Any
    btn_corridor_rmse_export_data: Any
    btn_corridor_rmse_export_envelope_nk: Any
    btn_corridor_rmse_grid_calc: Any
    cb_corr_mode: QComboBox
    chk_corr_scientific_nominal: QCheckBox
    chk_corridor_rmse_envelope_only: QCheckBox
    chk_corridor_rmse_live_parabola: QCheckBox
    chk_corridor_rmse_lock_scale: QCheckBox
    lbl_corr_alpha: QLabel
    lbl_corr_rmse_delta: QLabel
    lbl_corridor_rmse_grid_progress: QLabel
    lbl_corridor_rmse_robust_compact: QLabel
    lbl_corridor_rmse_summary: QLabel
    lbl_corridors_run_state: QLabel
    lbl_corridors_state_adv: QLabel
    lbl_corridors_tab_state: QLabel
    pb_corridor_rmse_grid: EnhancedProgressWidget
    plot_corridor_rmse_d: CertusScientificPlot
    plot_k_corridor: CertusScientificPlot
    plot_n_corridor: CertusScientificPlot
    sp_corr_alpha: QDoubleSpinBox
    sp_corr_rmse_delta: QDoubleSpinBox
    sp_corridor_breakpoint_lookback: QSpinBox
    sp_corridor_grid_d_step_nm: QDoubleSpinBox
    sp_corridor_grid_n_points: QSpinBox
    sp_corridor_partial_delta_nm: QDoubleSpinBox
    sp_corridor_rmse_delta: QDoubleSpinBox
    sp_corridor_rmse_win: QSpinBox


class CorridorHost(IndexSplineRunHost, IndexSplineViewHost, CorridorStateHost, CorridorWidgetsHost, Protocol):
    """Everything a corridor mixin may read on the window."""



#: Corridor mixin -> the names it reads on the window and does not define itself, sorted.
CONTRACTS: dict[str, tuple[str, ...]] = {
    "_CorridorControlMixin": (),
    "_CorridorGenMixin": (
        "_corridor_manual_half_width_nm", "_corridor_profile_source_result", "_corridor_rmse_best_idx",
        "_corridor_rmse_center_nm", "_corridor_rmse_manual_hi", "_corridor_rmse_manual_lo",
        "_corridor_rmse_robust_hi", "_corridor_rmse_robust_lo", "_corridor_rmse_robust_ok",
        "_corridor_rmse_smart_interval", "_plot_result", "_refresh_corridor_rmse_robust_view",
        "_refresh_data_table", "_update_corridor_rmse_state_bar", "lbl_status", "logger",
        "sp_corridor_partial_delta_nm",
    ),
    "_CorridorExportMixin": (
        "_corridor_profile_source_result", "_corridor_rmse_d_vals", "_corridor_rmse_manual_active",
        "_corridor_rmse_manual_hi", "_corridor_rmse_manual_lo", "_corridor_rmse_parab_export",
        "_corridor_rmse_robust_export", "_corridor_rmse_vals", "_fmt_k_data_tab", "_fmt_n_data_tab",
        "_last_result", "_prepare_nk_data_tab_series", "lbl_status", "logger", "sp_corridor_grid_d_step_nm",
    ),
    "_CorridorWorkerMixin": (
        "_best_live_result", "_build_opt_config", "_can_offer_manual_extra_knots", "_cleanup_thread",
        "_corridor_auto_refine_plan", "_corridor_profile_source_result", "_corridor_rmse_base_snapshot",
        "_corridor_rmse_best_idx", "_corridor_rmse_d_vals", "_corridor_rmse_requested_grid",
        "_corridor_rmse_vals", "_display_result_prefer_best_live", "_finish_curve_minimum_deep_worker_done",
        "_finish_rmse_heal_worker_done", "_format_post_optimization_status", "_idx_tab_corridor_rmse",
        "_is_rmse_d_grid_worker_finalize_dict", "_last_run_cfg", "_launch_corridor_rmse_gap_heal",
        "_manual_knots_dialog", "_manual_mesh_change_log_line", "_merge_rmse_grid_promotion_into_nominal",
        "_on_corridor_rmse_grid_live_update", "_on_progress", "_on_worker_err",
        "_open_manual_extra_knots_dialog", "_plot_corridor_rmse_tab", "_plot_result",
        "_post_optimization_ready_status", "_prepare_worker_restart", "_prog_reset_bar",
        "_prompt_manual_extra_knots", "_refresh_data_table", "_refresh_manual_dialog_preview",
        "_refresh_post_optimization_option_controls", "_result_uses_split_mesh", "_rmse_from_result_dict",
        "_runtime_metrics_from_result_dict", "_schedule_corridor_auto_refine", "_set_corridor_grid_busy",
        "_set_corridor_grid_completed_badge", "_set_corridor_grid_progress_ui", "_start_auto_best_second_stage",
        "_start_manual_sigma_insert_worker", "_stop_event", "_summarize_manual_mesh_change", "btn_run",
        "btn_stop", "export_excel", "lbl_corridor_rmse_robust_compact", "lbl_corridor_rmse_summary",
        "lbl_status", "log", "logger", "plot_corridor_rmse_d", "tabs_main",
    ),
    "_CorridorTabMixin": (
        "_add_curve", "_export_corridor_rmse_envelope_nk_excel", "_export_corridor_rmse_profile_clipboard",
        "_generate_corridor_auto_smart_from_current_grid", "_generate_corridor_from_current_grid",
        "_generate_corridor_from_partial_grid", "_idx_tab_corridor", "_on_corridor_rmse_lock_scale_toggled",
        "_refresh_corridor_rmse_robust_view", "_start_corridor_rmse_grid_recalc", "logger", "plot_k_corridor",
        "plot_n_corridor", "tabs_main",
    ),
    "CertusIndexSplineCorridorUIMixin": (
        "_cleanup_thread", "_last_run_cfg", "_on_worker_done", "_on_worker_err", "btn_run", "btn_stop",
        "logger",
    ),
    "_CorridorRunMixin": (
        "_build_opt_config", "_cfg_with_result_substrate", "_cleanup_thread", "_corridor_auto_refine_plan",
        "_corridor_rmse_d_vals", "_corridor_rmse_grid_live_t0", "_corridor_rmse_live_last_plot_ts",
        "_corridor_rmse_live_plot_min_interval_s", "_display_result_prefer_best_live",
        "_finish_corridor_rmse_d_grid_worker_done", "_format_post_optimization_status", "_last_run_cfg",
        "_manual_postprocess_seed_result", "_on_progress", "_on_worker_done", "_on_worker_err",
        "_plot_corridor_rmse_tab", "_plot_result", "_post_optimization_ready_status", "_prepare_worker_restart",
        "_prog_reset_bar", "_refresh_data_table", "_refresh_post_optimization_option_controls",
        "_rmse_from_result_dict", "_set_corridor_rmse_view_data_bounds", "_start_curve_minimum_deep_refit",
        "_stepper", "_stop_event", "btn_corridor_generate_auto_smart_grid", "btn_corridor_generate_from_grid",
        "btn_corridor_generate_from_partial_grid", "btn_corridor_rmse_export_data",
        "btn_corridor_rmse_export_envelope_nk", "btn_corridor_rmse_grid_calc", "btn_run", "btn_stop",
        "cb_corr_mode", "chk_corr_scientific_nominal", "chk_corridor_rmse_envelope_only", "df", "export_excel",
        "lbl_corr_alpha", "lbl_corr_rmse_delta", "lbl_corridor_rmse_grid_progress", "lbl_corridors_run_state",
        "lbl_corridors_state_adv", "lbl_corridors_tab_state", "lbl_status", "logger", "pb_corridor_rmse_grid",
        "plot_corridor_rmse_d", "progress_widget", "sp_corr_alpha", "sp_corr_rmse_delta",
        "sp_corridor_breakpoint_lookback", "sp_corridor_grid_d_step_nm", "sp_corridor_grid_n_points",
        "sp_corridor_partial_delta_nm",
    ),
    "_CorridorRmseViewMixin": (
        "_add_context_page", "_apply_corridor_preset_auto_robust", "_build_corridor_tab_generate",
        "_build_corridor_tab_rmse_controls", "_corridor_rmse_best_idx", "_corridor_rmse_d_vals",
        "_corridor_rmse_robust_hi", "_corridor_rmse_robust_lo", "_corridor_rmse_robust_ok",
        "_corridor_rmse_vals", "_last_result", "_last_worker_result", "_plot_corridor_rmse_tab",
        "sp_corridor_rmse_delta", "sp_corridor_rmse_win",
    ),
    "_CorridorIntervalMixin": (
        "_apply_corridor_payload_from_interval", "_apply_manual_corridor_selection",
        "_corridor_profile_source_result", "_corridor_rmse_best_idx", "_corridor_rmse_center_nm",
        "_corridor_rmse_d_vals", "_corridor_rmse_manual_active", "_corridor_rmse_manual_hi",
        "_corridor_rmse_manual_lo", "_corridor_rmse_manual_slider_scale", "_corridor_rmse_robust_hi",
        "_corridor_rmse_robust_lo", "_corridor_rmse_robust_ok", "_last_result", "_on_corr_mode_changed",
        "_plot_corridor_rmse_tab", "_refresh_corridor_rmse_robust_view", "_refresh_corridors_gui_state_labels",
        "cb_corr_mode", "chk_corr_scientific_nominal", "logger", "sp_corr_rmse_delta", "sp_corridor_rmse_delta",
        "sp_corridor_rmse_win",
    ),
    "_CorridorNkMixin": (
        "_add_context_page", "_apply_cell_style", "_corridor_k_crosshair_hi", "_corridor_k_crosshair_lam",
        "_corridor_k_crosshair_lo", "_corridor_k_crosshair_nom", "_create_empty_context_widget",
        "_ensure_complete_manifest_for_secondary_export", "_lam_piecewise_report_grid_nm",
    ),
    "_CorridorRmsePlotMixin": (
        "_add_curve", "_corridor_rmse_best_marker", "_corridor_rmse_curvature_label", "_corridor_rmse_curve",
        "_corridor_rmse_manual_active", "_corridor_rmse_manual_hi", "_corridor_rmse_manual_lo",
        "_corridor_rmse_smart_interval", "_robust_interval_from_local_quadratic",
        "_sync_corridor_manual_controls", "_update_corridor_rmse_state_bar", "chk_corridor_rmse_live_parabola",
        "chk_corridor_rmse_lock_scale", "lbl_corridor_rmse_robust_compact", "lbl_corridor_rmse_summary",
        "plot_corridor_rmse_d", "sp_corridor_rmse_delta", "sp_corridor_rmse_win",
    ),
}
