from __future__ import annotations
import logging
import copy
import time
import os
import functools
import multiprocessing
import traceback
from pathlib import Path
import sys
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg

from certus.core.certus_core import certus_timestamp_display, setup_logging, CFG, create_module_environment, NUMERICAL_FAULT_EXCEPTIONS, get_resource_path, certus_timestamp_file

from certus.ui.certus_qt_widgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox,
    QColor, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFont, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QKeySequence, QLabel, QMessageBox,
    QPushButton, QRadioButton, QScrollArea, QShortcut, QSplitter, QStackedWidget,
    QStatusBar, QTableWidgetItem, QTabWidget, QTextEdit, QTimer, Qt, QVBoxLayout,
    QWidget,
)

from certus_physics import Layer, ObliqueTarget, init_thickness, calc_spectrum_front_wrapper, calc_spectrum_full_exact_wrapper

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale, spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display, spectrum_eval_plot_curves,
    spectrum_eval_run_preamble, spectrum_eval_start_worker,
)

from certus.ui.certus_ui import (
    attach_excel_clipboard_context_menu, CertusBaseApp, CertusCard, CertusCollapsible,
    CertusScientificPlot, CertusStatusPill, CertusTheme, CertusThemeToggle,
    enable_file_drop, EnhancedProgressWidget, ExcelTableWidget, FlashyCard,
    get_certus_last_dir, install_standard_shortcuts, safe_ui_action,
    set_certus_last_dir, show_toast, WelcomeGuideWidget, create_flashy_grid,
    create_header_logo_widget, create_styled_button, create_styled_label,
    create_top_actions_bar, init_certus_app, set_certus_window_icon,
    install_skeleton_loader, remove_skeleton_loader, wrap_scientific_plot_with_toolbar,
    open_documentation, confirm_stop_with_timeout,
)

from certus.utils.certus_ux import build_premium_overrides
from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus.workers.certus_re_workers import REWorker
from certus.ui.certus_re_ui import CertusREResultsDialog

from certus.utils.certus_re_helpers import (
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG, RE_GUI_DEFAULT_RE_QWOT_ALPHA, RE_HL_DELTA_RE_REG_SQRT_W,
    RE_OPTIM_POINTS_PER_TARGET, RE_PHASE2_FD_MAX_WORKERS, RE_PHASE2_FD_PARALLEL,
    RE_PHASE2_ONESIDED_SPLINE_FD, RE_PHASE4_APERTURE_SCAN_POINTS, RE_P4_BEAM_AP_BOUNDS_DEG,
    RE_P4_BEAM_N_KNOTS, RE_PHASE4_TRF_MAX_NFEV, re_qwot_penalty_weight_from_preset,
    RE_RE_DEADZONE_DELTA_RE_ABS, RE_RE_DEADZONE_QWOT_ABS, RE_SPEED_PRESETS,
    RE_SPLINE_NODE2_DEFAULT_NM, RE_SPLINE_N_KNOTS, RE_SUB_CAUCHY_TUBE_DELTA,
    RE_THICKNESS_SEARCH_RADIUS_PCT, _RE_CANONICAL_SHEETS, _RE_FT_COL_MAT, _RE_FT_COL_N,
    _RE_FT_COL_NUM, _RE_FT_COL_QW, _RE_FT_COL_THICK, _parse_re_rmse_combined_from_progress_message,
    _re_calc_spectrum_for_config, _re_cell_str, _re_find_measurement_wavelength_column,
    _re_header_is_wavelength_label, _re_header_looks_like_spectrum_title, _re_index_column_map,
    _re_index_split_header_and_data, _re_measurement_values_are_percent, _re_p4_ap_staircase_polyline,
    _re_p4_kwargs_from_opt_result, _re_p4_sort_knot_pairs, _re_parse_design_metadata_row,
    _re_parse_design_qwot_rows, _re_qwot_rmse_abs_delta_at_l0, _re_resolve_re_workbook_sheets,
    _re_rmse_combined_spectral_qwot, _re_rmse_oblique_weighted, _re_sort_results_best_for_table_and_apply,
    format_re_drift_log_triplet_pct, format_re_spline_knots_log, parse_re_column_header,
    re_apply_re_index_model, re_delta_qwot_per_layer, re_drift_result_log_suffix,
    re_interp_delta_knots_clamped, re_knots_wavelengths, re_n_corr_at_lambda_ref,
    re_substrate_cauchy_n_re_from_theta, TabularMaterial, ParsedREColumn
)
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class CertusREPlotMixin:
    """CertusREPlotMixin for CERTUS_RE."""

    def _on_update_spectrum_y_scale_signal(self, *_args) -> None:

        self._update_spectrum_y_scale()

    def _plot_profile(
        self,
        ep: np.ndarray,
        stack: list[Layer],
    ):
        """Update n,k display in spectrum widget."""

        # ... logic ...

        """Refractive index profile (front side only  RE without rear coating)."""

        for plot_widget in self._get_plot_targets("profile", self.profile_plot):
            plot_widget.plotItem.clear()

            mats = self._get_materials()

            if "Substrate" not in mats:
                continue

            ns = mats["Substrate"].n4

            x, y = [0.0, 0.0], [ns, mats[stack[0].mat].n4] if stack else [ns, 1.0]

            if ep is not None and len(ep) > 0:
                cs = np.cumsum(ep)

                n_vals = [mats[l.mat].n4 for l in stack]

                # Protection against index out of bounds (oblique mode may have more thicknesses than layers)

                n_layers = min(len(ep) - 1, len(n_vals) - 1)

                for i in range(n_layers):
                    x.extend([cs[i], cs[i]])

                    y.extend([n_vals[i], n_vals[i + 1]])

                if n_vals:
                    x.extend([cs[-1], cs[-1], cs[-1] + max(50.0, 0.1 * cs[-1])])

                    y.extend([n_vals[-1], 1.0, 1.0])

            else:
                x, y = [0.0, 50.0], [ns, 1.0]

            plot_widget.plot(
                x,
                y,
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                fillLevel=0,
                brush=(30, 58, 138, 30),
            )

    def _plot_nk(self):
        """n(lambda) curves. If RE loaded: extended range; dashed = corrected Re (DeltaRe splines or drift %)."""

        mats = self._get_materials()

        cols = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ACCENT,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.ERROR,
        ]

        re_loaded = getattr(self, "_re_loaded", False)

        re_busy = getattr(self, "_re_mode_active", False)

        if re_loaded and getattr(self, "_re_tabular_H", None) is not None:
            wf = np.asarray(self._re_tabular_H.wls_nm, dtype=np.float64)

            if wf.size >= 2:
                w_dense = np.linspace(float(wf[0]), float(wf[-1]), max(400, int(wf.size) * 4))

                w = np.unique(np.concatenate([wf, w_dense]))

            elif wf.size == 1:
                w = np.linspace(max(200.0, wf[0] - 200), wf[0] + 2000.0, 300)

            else:
                w = np.linspace(380.0, 5500.0, 600)

        elif re_loaded:
            w = np.linspace(380.0, 5500.0, 600)

        else:
            w = np.linspace(380.0, 1000.0, 400)

        a_gui = float(getattr(self, "_re_opt_a_pct", 0.0)) if re_loaded else 0.0

        b_gui = float(getattr(self, "_re_opt_b_pct", 0.0)) if re_loaded else 0.0

        _nksp = RE_SPLINE_N_KNOTS

        if re_busy:
            dH_st = getattr(self, "_re_nk_preview_dH", None)

            dL_st = getattr(self, "_re_nk_preview_dL", None)

            _lam2_pv = getattr(self, "_re_nk_preview_lam2", None)

            sub012_pv = getattr(self, "_re_nk_preview_sub012", None)

        else:
            dH_st = getattr(self, "_re_spline_dH", None)

            dL_st = getattr(self, "_re_spline_dL", None)

            _lam2_pv = getattr(self, "_re_spline_lam2_nm", None)

            sub012_pv = None

        use_sp = (
            re_loaded
            and dH_st is not None
            and dL_st is not None
            and len(np.asarray(dH_st).ravel()) == _nksp
            and len(np.asarray(dL_st).ravel()) == _nksp
        )

        if use_sp:
            dh_arr = np.asarray(dH_st, dtype=np.float64).ravel()

            dl_arr = np.asarray(dL_st, dtype=np.float64).ravel()

            show_renk_corr = re_loaded and (
                np.max(np.abs(dh_arr)) > 1e-12
                or np.max(np.abs(dl_arr)) > 1e-12
                or (sub012_pv is not None and len(sub012_pv) == 3 and max(abs(float(x)) for x in sub012_pv) > 1e-12)
            )

        else:
            show_renk_corr = re_loaded and (abs(a_gui) > 1e-12 or abs(b_gui) > 1e-12)

        for plot_widget in self._get_plot_targets("nk", self.nk_plot):
            plot_widget.plotItem.clear()

            for i, (k, m) in enumerate(mats.items()):
                n_nominal = m.get_nk(w).real

                plot_widget.plot(
                    w,
                    n_nominal,
                    pen=pg.mkPen(cols[i % len(cols)], width=2),
                    name=k,
                )

            if show_renk_corr:
                if use_sp:
                    _lam2_pl = float(_lam2_pv) if _lam2_pv is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

                    _kw_pl = re_knots_wavelengths(_lam2_pl)

                    _es_nk = self._re_envelope_scale_from_gui()

                    dHv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dH_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    dLv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dL_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            n_corr = m.get_nk(w).real + dHv

                        elif k == "L":
                            n_corr = m.get_nk(w).real + dLv

                        elif k == "Substrate":
                            lr = float(self.l0_spin.value())

                            if sub012_pv is not None and len(sub012_pv) == 3:
                                ths = np.asarray(sub012_pv, dtype=np.float64)

                            else:
                                _sa = getattr(self, "_re_sub_cauchy_a0", None)

                                _s1 = getattr(self, "_re_sub_cauchy_a1", None)

                                _s2 = getattr(self, "_re_sub_cauchy_a2", None)

                                if _sa is None or _s1 is None or _s2 is None:
                                    continue

                                ths = np.array(
                                    [float(_sa), float(_s1), float(_s2)],
                                    dtype=np.float64,
                                )

                            n_corr = re_substrate_cauchy_n_re_from_theta(w, lr, ths)

                        else:
                            continue

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

                else:
                    a_pct = a_gui

                    b_pct = b_gui

                    lambda_ref = float(self.l0_spin.value())

                    wls_drift_denom = max(5200.0 - lambda_ref, 1.0)

                    t = np.clip((w - lambda_ref) / wls_drift_denom, 0.0, None)

                    drift_factor = t**3

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            mult = 1.0 + (a_pct / 100.0) * drift_factor

                        elif k == "L":
                            mult = 1.0 + (b_pct / 100.0) * drift_factor

                        else:
                            continue

                        n_corr = m.get_nk(w).real * mult

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

    def _re_clear_re_nk_preview(self) -> None:
        """Reset n(lambda) preview synchronized with the RE worker."""

        self._re_nk_preview_dH = None

        self._re_nk_preview_dL = None

        self._re_nk_preview_lam2 = None

        self._re_nk_preview_sub012 = None

    def _re_init_plot_factors(self, wls, spline_dH, spline_dL):

        mats = self._get_materials()

        lam_ref = float(self.l0_spin.value())

        drift_factor = np.clip((wls - lam_ref) / max(5200.0 - lam_ref, 1.0), 0.0, None) ** 3

        use_sp = (
            spline_dH is not None
            and spline_dL is not None
            and len(np.asarray(spline_dH).ravel()) == int(RE_SPLINE_N_KNOTS)
            and len(np.asarray(spline_dL).ravel()) == int(RE_SPLINE_N_KNOTS)
        )

        return mats, drift_factor, use_sp

    def _update_re_spectrum_title(self, rmse=None, suffix=""):
        """Update spectrum plot title with RE RMSE."""

        n_layers = self.front_table.rowCount()

        title = f"RE Spectrum ({n_layers} layers)"

        if rmse is not None and np.isfinite(rmse):
            title += f"  RMSE: {rmse:.6f}"

        if suffix:
            title += f" {suffix}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

    def _re_spline_lam2_nm_from_result(self, r: dict) -> float:

        _kw = r.get("re_knots_nm")

        if _kw is not None and len(_kw) > 1:
            return float(np.asarray(_kw, dtype=np.float64).ravel()[1])

        _lv = r.get("re_spline_lam_node2_nm")

        if _lv is not None:
            return float(_lv)

        return float(RE_SPLINE_NODE2_DEFAULT_NM)
