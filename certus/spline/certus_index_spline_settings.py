# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Settings and Corridor UI Controls Mixins.
Contains _SettingsMixin and _CorridorControlMixin.
"""

from __future__ import annotations
import logging
import os
import time
from typing import Any
from pathlib import Path

import numpy as np
from certus.spline.certus_index_spline_core import _log_index_spline_best_config
import pyqtgraph as pg

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import (
    QDialog, QMessageBox, QVBoxLayout, QWidget, QLabel,
    QPushButton, QCheckBox, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QGridLayout, QScrollArea
)


from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_ui import (
    CertusTheme,
    safe_ui_action,
    GenericWorker,
)
from certus.spline.certus_index_spline_core import (
    log_index_spline_d_trace,
    _QS_SPLINE_ORG,
    _QS_SPLINE_APP,
    _QS_SPECTRUM_FIT_R,
    _QS_SPECTRUM_FIT_TREL,
    _QS_SPECTRUM_FIT_T,
    _QS_SPECTRUM_WR,
    _QS_SPECTRUM_WT,
    _QS_SPLINE_UNCERTAINTY_DEFAULTS_REV,
    _QS_MAIN_SPLITTER_LAYOUT_REV,
    _QS_MAIN_SPLITTER_STATE,
    _QS_RIGHT_SPLITTER_STATE,
    _MAIN_SPLITTER_LAYOUT_REV,
    _UNCERTAINTY_DEFAULTS_REV,
)

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_data import read_data_file_robust
from certus.spline.certus_index_spline_core import normalize_spectrum_dataframe
from certus.spline.spline_pipeline import worker_run_corridor_profile_after_nl_choice

_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4
_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5
_CORRIDOR_K_TAB_MIN_HALF_WIDTH: float = 1e-4

logger = logging.getLogger("CERTUS_INDEX_SPLINE")


class _SettingsMixin:
    """Mixin containing defaults reset, loading and uncertainty settings methods."""

    def _apply_default_square_plot_split(self) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            return

        total = int(max(0, sizes[0]) + max(0, sizes[1]))
        if total <= 0:
            total = int(max(0, spl.width()))
        if total <= 0:
            return

        panel_h = int(max(0, spl.height()))
        if panel_h <= 0:
            panel_h = int(round(0.58 * float(total)))

        # Keep the right panel width near the visible height so the active plot
        # starts close to a square aspect by default.
        target_right = int(round(0.88 * float(panel_h)))
        target_right = int(
            min(
                max(target_right, int(round(0.20 * float(total)))),
                int(round(0.95 * float(total))),
            )
        )
        target_left = int(max(1, total - target_right))

        self._main_splitter_clamp_guard = True
        try:
            spl.setSizes([target_left, target_right])
        finally:
            self._main_splitter_clamp_guard = False

        self._enforce_main_splitter_ratio_bounds(persist=False)

    def _on_main_splitter_moved(self, *_args) -> None:

        self._enforce_main_splitter_ratio_bounds(persist=True)

    def _enforce_main_splitter_ratio_bounds(self, *, persist: bool = True) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            if persist:
                self._persist_splitter_states()
            return

        if bool(getattr(self, "_main_splitter_clamp_guard", False)):
            if persist:
                self._persist_splitter_states()
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            if persist:
                self._persist_splitter_states()
            return

        left = int(max(0, sizes[0]))
        right = int(max(0, sizes[1]))
        total = int(left + right)
        if total <= 0:
            if persist:
                self._persist_splitter_states()
            return

        min_left = max(1, int(round(0.05 * total)))
        max_left = max(min_left, int(round(0.95 * total)))
        clamped_left = int(min(max(left, min_left), max_left))

        if clamped_left != left:
            self._main_splitter_clamp_guard = True
            try:
                spl.moveSplitter(int(clamped_left), 0)
            finally:
                self._main_splitter_clamp_guard = False

        if persist:
            self._persist_splitter_states()

    def _restore_splitter_states(self) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            v_rev_raw = s.value(_QS_MAIN_SPLITTER_LAYOUT_REV, 0)
            v_rev = int(v_rev_raw or 0)
        except (TypeError, ValueError):
            v_rev = 0

        try:
            if hasattr(self, "main_split") and v_rev == int(_MAIN_SPLITTER_LAYOUT_REV):
                v_main = s.value(_QS_MAIN_SPLITTER_STATE)
                if v_main is not None:
                    self.main_split.restoreState(v_main)
                else:
                    QTimer.singleShot(0, self._apply_default_square_plot_split)
                self._enforce_main_splitter_ratio_bounds(persist=False)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            v_right = s.value(_QS_RIGHT_SPLITTER_STATE)
            if v_right is not None and hasattr(self, "info_split"):
                self.info_split.restoreState(v_right)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _persist_splitter_states(self, *_args) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        if hasattr(self, "main_split"):
            s.setValue(_QS_MAIN_SPLITTER_STATE, self.main_split.saveState())
            s.setValue(_QS_MAIN_SPLITTER_LAYOUT_REV, int(_MAIN_SPLITTER_LAYOUT_REV))

        if hasattr(self, "info_split"):
            s.setValue(_QS_RIGHT_SPLITTER_STATE, self.info_split.saveState())

    def _maybe_apply_uncertainty_defaults_migrated(self) -> None:
        """Applies automatic uncertainty defaults once (migration / new install)."""

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            rev = int(s.value(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, 0) or 0)

        except (TypeError, ValueError):
            rev = 0

        if rev < _UNCERTAINTY_DEFAULTS_REV:
            if rev < 5:
                self._apply_recommended_uncertainty_and_perf_defaults()

                self._apply_sio2_default_fit_parameters()

                if hasattr(self, "chk_trel"):
                    self.chk_trel.setChecked(True)

            if rev < 9 and hasattr(self, "cb_corr_mode"):
                self.cb_corr_mode.blockSignals(True)

                try:
                    iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                    if iq >= 0:
                        self.cb_corr_mode.setCurrentIndex(int(iq))

                finally:
                    self.cb_corr_mode.blockSignals(False)

                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._on_corr_mode_changed()

            if rev < 11 and hasattr(self, "cb_corr_mode"):
                self._apply_corridor_preset_auto_robust()

            if rev < 12:
                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

                if hasattr(self, "_on_corr_mode_changed"):
                    self._on_corr_mode_changed()

                if hasattr(self, "_refresh_corridors_gui_state_labels"):
                    self._refresh_corridors_gui_state_labels()

            s.setValue(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, int(_UNCERTAINTY_DEFAULTS_REV))

    def _apply_recommended_uncertainty_and_perf_defaults(self) -> None:
        """Speed-oriented defaults: Fast profile, n/k corridors enabled (accelerated refits); optional bootstrap / reg. scan."""

        if not hasattr(self, "cb_profilee"):
            return

        self.cb_profilee.blockSignals(True)

        try:
            iq = self.cb_profilee.findData("fast")

            if iq >= 0:
                self.cb_profilee.setCurrentIndex(int(iq))

        finally:
            self.cb_profilee.blockSignals(False)

        self._on_profilee_changed()

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.setChecked(True)

        if hasattr(self, "cb_corr_mode"):
            ia = self.cb_corr_mode.findData("abs_delta_adaptive")

            if ia >= 0:
                self.cb_corr_mode.setCurrentIndex(int(ia))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "chk_corr_sigma_hetero"):
            self.chk_corr_sigma_hetero.setChecked(False)

        if hasattr(self, "sp_corr_hetero_scale"):
            self.sp_corr_hetero_scale.setValue(1.0)

        if hasattr(self, "sp_corr_sigma"):
            self.sp_corr_sigma.setValue(0.0)

        if hasattr(self, "sp_corr_starts"):
            self.sp_corr_starts.setValue(1)

        if hasattr(self, "chk_corr_reg_sens"):
            self.chk_corr_reg_sens.setChecked(False)

        if hasattr(self, "chk_corr_boot"):
            self.chk_corr_boot.setChecked(False)

        if hasattr(self, "sp_corr_boot_n"):
            self.sp_corr_boot_n.setValue(40)

        self._refresh_corridors_gui_state_labels()

        if hasattr(self, "sp_corr_boot_p"):
            self.sp_corr_boot_p.setValue(0.95)

        if hasattr(self, "chk_corr_boot_refit"):
            self.chk_corr_boot_refit.setChecked(False)

        if hasattr(self, "sp_corr_boot_maxfun"):
            self.sp_corr_boot_maxfun.setValue(4000)

        if hasattr(self, "sp_corr_boot_workers"):
            self.sp_corr_boot_workers.setValue(1)

        if hasattr(self, "sp_corr_span"):
            self.sp_corr_span.setValue(15.0)

        if hasattr(self, "sp_corr_prof_maxfun"):
            self.sp_corr_prof_maxfun.setValue(2500)

        if hasattr(self, "cb_corr_boot_mode"):
            ip = self.cb_corr_boot_mode.findData("parametric")

            if ip >= 0:
                self.cb_corr_boot_mode.setCurrentIndex(int(ip))

        if hasattr(self, "cb_corr_mode"):
            self._apply_corridor_preset_auto_robust()

    def reset_to_defaults(self) -> None:
        """Reinitialisation complete (bouton Clear / Reset CERTUS)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        reset_app_to_defaults(self)

    @safe_ui_action
    def _on_load(self, path: str | None = None) -> None:

        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Spectrum",
                self._spectrum_open_dialog_start_path(),
                "Data (*.csv *.xlsx *.xls);;All (*.*)",
            )

        if not path:
            return

        try:
            raw = read_data_file_robust(path)

            self.df = normalize_spectrum_dataframe(raw)

            if self.df is None or "lambda" not in self.df.columns:
                raise ValueError("Invalid wavelength or spectrum column after normalization.")

            self._persist_last_spectrum_path(path)

            self.lbl_file.setText(path)

            if hasattr(self, "tabs_main"):
                self.tabs_main.setCurrentIndex(0)

            self._sync_rmse_lambda_bounds_from_file()

            self._plot_data_raw()

            self.lbl_status.setText(f"Loaded: {len(self.df)} points")

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                lam = np.asarray(self.df.get("lambda", []), dtype=np.float64).ravel()

                lam_f = lam[np.isfinite(lam)]

                lmin = float(np.min(lam_f)) if lam_f.size else float("nan")

                lmax = float(np.max(lam_f)) if lam_f.size else float("nan")

                cols = [str(c) for c in self.df.columns]

                summary = build_summary_plain_text(
                    "CERTUS INDEX SPLINE - Load Summary",
                    [
                        f"File: {Path(path).resolve(strict=False)}",
                        "",
                        "General",
                        (f"Rows: {int(len(self.df))}", int(len(self.df)) <= 0),
                        "",
                        "Data",
                        f"Columns: {', '.join(cols)}",
                        (
                            f"Wavelength range: [{lmin:.1f}, {lmax:.1f}] nm",
                            not (np.isfinite(lmin) and np.isfinite(lmax) and lmax > lmin),
                        ),
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if any(c.lower().startswith('t') for c in cols) else 'no'}",
                            not any(c.lower().startswith("t") for c in cols),
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX SPLINE Load Summary", summary)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            QMessageBox.critical(self, "Loading", str(e))

            logger.exception("load")

    def _update_rmse_fit_region_overlay(self) -> None:

        self._remove_rmse_fit_region_overlay()

        if not getattr(self, "_rmse_fit_lambda_enabled", False):
            return

        span = self._spectrum_plot_lambda_span_nm()

        if span is None:
            return

        lam_file_lo, lam_file_hi = span

        if not (np.isfinite(lam_file_lo) and np.isfinite(lam_file_hi)):
            return

        if lam_file_lo > lam_file_hi:
            lam_file_lo, lam_file_hi = lam_file_hi, lam_file_lo

        wlo = float(self._rmse_fit_lambda_lo)

        whi = float(self._rmse_fit_lambda_hi)

        if not (np.isfinite(wlo) and np.isfinite(whi)):
            return

        lam_win_lo, lam_win_hi = min(wlo, whi), max(wlo, whi)

        def _x_span_lam(la: float, lb: float) -> tuple[float, float] | None:

            if not (np.isfinite(la) and np.isfinite(lb)):
                return None

            if la > lb:
                la, lb = lb, la

            if lb - la <= 0.0:
                return None

            try:
                xv, _ = self._transform_spectrum_x(np.array([la, lb], dtype=np.float64))

            except (TypeError, ValueError, RuntimeError):
                return None

            return float(np.min(xv)), float(np.max(xv))

        eps_lam = max(1e-6, 1e-9 * max(abs(lam_file_hi), 1.0))

        eps_x = max(1e-12, 1e-15 * max(abs(lam_file_lo), abs(lam_file_hi), 1.0))

        def _add_region(xa: float, xb: float, *, brush, z: float) -> None:

            lo_x, hi_x = (xa, xb) if xa <= xb else (xb, xa)

            if hi_x - lo_x <= eps_x:
                return

            reg = pg.LinearRegionItem(values=(lo_x, hi_x), movable=False, brush=brush)

            reg.setZValue(z)

            self.plot_T.addItem(reg)

            self._rmse_fit_overlay_items.append(reg)

        gray_brush = pg.mkBrush(120, 120, 120, 85)

        # Excludes lambda < window (within file envelope) - correct if sigma/sigma^2 (nonlinear in lambda on axis)

        if lam_win_lo > lam_file_lo + eps_lam:
            la, lb = lam_file_lo, min(lam_file_hi, lam_win_lo)

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        # Exclude lambda > window

        if lam_win_hi < lam_file_hi - eps_lam:
            la, lb = max(lam_file_lo, lam_win_hi), lam_file_hi

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        x_active = _x_span_lam(lam_win_lo, lam_win_hi)

        if x_active is not None:
            xa, xb = x_active

            if xb - xa > eps_x:
                reg_active = pg.LinearRegionItem(
                    values=(xa, xb),
                    movable=False,
                    brush=pg.mkBrush(0, 120, 215, 40),
                )

                reg_active.setZValue(-5.0)

                self.plot_T.addItem(reg_active)

                self._rmse_fit_overlay_items.append(reg_active)

    def _on_rmse_fit_window_dialog(self) -> None:

        dlg = QDialog(self)

        dlg.setWindowTitle("Spectral RMSE Window")

        lay = QVBoxLayout(dlg)

        chk = QCheckBox("Limit optimization MSE/RMSE to a lambda band (nm)")

        chk.setChecked(self._rmse_fit_lambda_enabled)

        chk.setToolTip(
            "If checked: only experimental points in [lambda_min, lambda_max] enter the spectral loss. "
            "Plots always use the full loaded file."
        )

        lay.addWidget(chk)

        g = QGridLayout()

        lb_lo = QLabel("lambda_min (nm)")

        lb_hi = QLabel("lambda_max (nm)")

        sp_lo = QDoubleSpinBox()

        sp_hi = QDoubleSpinBox()

        for sp in (sp_lo, sp_hi):
            sp.setRange(200.0, 20000.0)

            sp.setDecimals(4)

            sp.setSingleStep(1.0)

        sp_lo.setValue(float(self._rmse_fit_lambda_lo))

        sp_hi.setValue(float(self._rmse_fit_lambda_hi))

        sp_lo.setToolTip("Lower bound (nm) of the RMSE band.")

        sp_hi.setToolTip("Upper bound (nm) of the RMSE band.")

        g.addWidget(lb_lo, 0, 0)

        g.addWidget(sp_lo, 0, 1)

        g.addWidget(lb_hi, 1, 0)

        g.addWidget(sp_hi, 1, 1)

        lay.addLayout(g)

        btn_reset = QPushButton("Reset")

        btn_reset.setToolTip("Reset lambda_min / lambda_max to [min file, max file] of the loaded spectrum.")

        lay.addWidget(btn_reset)

        def _apply_enable(en: bool) -> None:

            sp_lo.setEnabled(en)

            sp_hi.setEnabled(en)

            btn_reset.setEnabled(en)

        def _do_reset() -> None:

            sp_lo.setValue(float(self._rmse_fit_lambda_lo_default))

            sp_hi.setValue(float(self._rmse_fit_lambda_hi_default))

        chk.toggled.connect(_apply_enable)

        _apply_enable(chk.isChecked())

        btn_reset.clicked.connect(_do_reset)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._rmse_fit_lambda_enabled = chk.isChecked()

        self._rmse_fit_lambda_lo = float(sp_lo.value())

        self._rmse_fit_lambda_hi = float(sp_hi.value())

        if self._last_result is not None:
            self._plot_result(self._last_result, plot_source="fenetre_rmse_fit_lambda")

        elif self.df is not None:
            self._plot_data_raw()

        else:
            self._update_rmse_fit_region_overlay()

    def _restore_spectrum_fit_settings(self) -> None:
        """Reads step 3 from QSettings (T, T/Tsub ratio, R, wT, wR)."""

        if not hasattr(self, "chk_t"):
            return

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        widgets = (
            self.chk_t,
            self.chk_trel,
            self.chk_r,
            self.w_t,
            self.w_r,
        )

        for w in widgets:
            w.blockSignals(True)

        try:
            vt = s.value(_QS_SPECTRUM_FIT_T)

            if vt is not None:
                self.chk_t.setChecked(bool(vt))

            vrel = s.value(_QS_SPECTRUM_FIT_TREL)

            if vrel is not None:
                self.chk_trel.setChecked(bool(vrel))

            vr = s.value(_QS_SPECTRUM_FIT_R)

            if vr is not None:
                self.chk_r.setChecked(bool(vr))

            wtv = s.value(_QS_SPECTRUM_WT)

            if wtv is not None:
                self.w_t.setValue(float(wtv))

            wrv = s.value(_QS_SPECTRUM_WR)

            if wrv is not None:
                self.w_r.setValue(float(wrv))

        finally:
            for w in widgets:
                w.blockSignals(False)

    def _open_advanced_settings_dialog(self) -> None:

        lay_page = getattr(self, "_box4_full_adv_layout", None)

        if not hasattr(self, "_w_full_adv") or lay_page is None:
            return

        dlg = QDialog(self)

        dlg.setWindowTitle("Advanced settings - INDEX-SPLINE")

        dlg.resize(560, 620)

        outer = QVBoxLayout(dlg)

        chk = QCheckBox("Simplified Basic panel (recommended): hide advanced budgets and uncertainty details")

        chk.setChecked(bool(getattr(self, "_simple_auto_uncertainty", True)))

        chk.setToolTip(
            "Unchecked: after OK, controls stay visible in step 4. "
            "Checked: summary only in the panel; settings remain available here."
        )

        outer.addWidget(chk)

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        host = QWidget()

        host_lay = QVBoxLayout(host)

        host_lay.setContentsMargins(0, 0, 0, 0)

        lay_page.removeWidget(self._w_full_adv)

        host_lay.addWidget(self._w_full_adv)

        scroll.setWidget(host)

        outer.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        outer.addWidget(bb)

        code = dlg.exec()

        host_lay.removeWidget(self._w_full_adv)

        lay_page.addWidget(self._w_full_adv)

        self._w_full_adv.show()

        if code == QDialog.DialogCode.Accepted:
            self._simple_auto_uncertainty = chk.isChecked()

            self._persist_simple_auto_uncertainty_pref()

        self._update_epured_visibility()

class _CorridorControlMixin:
    """Mixin containing corridor RMSE grid control, display and worker management."""

    def _start_deferred_corridor_worker(self, result: dict) -> bool:

        cfg_base = self._last_run_cfg

        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)

        if cfg_base is None:
            return False

        self.__class__._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        cfg_corr = self._cfg_with_result_substrate(cfg_base, result).replace()

        setattr(cfg_corr, "gui_defer_corridor_profile_after_nl", False)
        # Manual "Corridors" action must execute profiling now, regardless of the main run checkbox state.
        setattr(cfg_corr, "corridor_profile_d_enabled", True)

        # --- Resync solver snapshot if manual dialog changed the mesh (K) ---
        _snap = result.get("gui_solver_snapshot_for_corridors")
        _snap_k = 0
        if isinstance(_snap, dict):
            _snap_sk = np.asarray(_snap.get("sigma_knots", []), dtype=np.float64).ravel()
            _snap_k = int(_snap_sk.size)
        _cur_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        _cur_k = int(_cur_sk.size)
        if _cur_k >= 2 and _cur_k != _snap_k:
            fresh_snap = dict(result)
            for _key in ("x", "x_seg_spline_sigma", "n_nodes_physical", "L_nodes",
                         "sigma_knots", "d_nm", "n_lam", "k_lam", "rmse", "mse"):
                if _key in result:
                    val = result[_key]
                    if isinstance(val, np.ndarray):
                        fresh_snap[_key] = val.copy()
                    else:
                        fresh_snap[_key] = val
            result["gui_solver_snapshot_for_corridors"] = fresh_snap
            if self.logger:
                self.logger.info(
                    "[INDEX_SPLINE.CORRIDORS] solver snapshot resynced to current mesh | k_snap=%d -> k_current=%d",
                    _snap_k, _cur_k,
                )


        self._worker = GenericWorker(
            worker_run_corridor_profile_after_nl_choice, cfg_corr, dict(result), self._stop_event
        )

        def _corr_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _corr_progress
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        source_stage = str(getattr(self, "_worker_role", "main") or "main")

        self._worker_role = "corridors"

        if hasattr(self, "_stepper"):
            self._stepper.set_step(6)

        if self.logger:
            rd = result.get("d_nm")
            rd_txt = f"{float(rd):.6f}" if isinstance(rd, (int, float)) and np.isfinite(float(rd)) else "n/a"
            rr = self._rmse_from_result_dict(result)
            rr_txt = f"{rr:.8f}" if np.isfinite(rr) else "n/a"
            self.logger.info(
                "[INDEX_SPLINE.CORRIDORS] launching deferred corridor worker | after_stage=%s | seed_d_nm=%s | seed_rmse_dict=%s",
                source_stage,
                rd_txt,
                rr_txt,
            )
            log_index_spline_d_trace(
                self.logger,
                "[INDEX_SPLINE.CORRIDORS] deferred corridor launch trace | seed=last_result",
                result.get("d_nm"),
                detail=f"after_stage={source_stage} rmse_dict={rr_txt}",
            )

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText("Corridors: calculation in progress...")

        self._worker.start()

        return True

    def _finish_curve_minimum_deep_worker_done(self, result: object) -> None:
        """End of deep polish from minimum RMSE(d): return to post-optimization state without auto-launch."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not isinstance(result, dict):
            self.lbl_status.setText("Polish profond (minimum grille) : annule ou echec.")
            if self.logger:
                self.logger.warning(
                    "GUI curve-min deep refit | finished without dict (type=%s)",
                    type(result).__name__,
                )
            QMessageBox.warning(
                self,
                "Polish profond",
                "L-BFGS-B polish from grid minimum did not return a valid result "
                "(interruption or numerical failure). The nominal was not modified.",
            )
            self._refresh_post_optimization_option_controls()
            return
        for _rk in list(result.keys()):
            if str(_rk).startswith("profile_d"):
                del result[_rk]

        # Restore corridor and profile_d keys from the preceding corridor worker output.
        # The deep polish (L-BFGS-B on d+nodes) does not recompute corridor envelopes;
        # they were computed by the corridor worker and are stored in _last_result.
        # Safety: _display_result_prefer_best_live (called below) will NOT strip them
        # because _best_live_result is None during deep polish (no live callbacks).
        prev = self._last_result if isinstance(self._last_result, dict) else {}
        _lam_result = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_prev = np.asarray(prev.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_ok = _lam_result.size > 0 and _lam_result.size == _lam_prev.size
        _n_restored = 0
        if _lam_ok:
            for _pk in list(prev.keys()):
                if (
                    str(_pk).startswith("corridor_")
                    or str(_pk).startswith("profile_d_")
                    or _pk == "profile_d_enabled"
                ) and _pk not in result:
                    val = prev[_pk]
                    result[_pk] = val.copy() if isinstance(val, np.ndarray) else val
                    _n_restored += 1
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | corridor data restoration from _last_result | "
                "lam_ok=%s (result=%d, prev=%d) | keys_restored=%d",
                "yes" if _lam_ok else "NO",
                int(_lam_result.size),
                int(_lam_prev.size),
                int(_n_restored),
            )

        self._last_worker_result = dict(result)
        self._corridor_rmse_manual_active = False
        self._corridor_rmse_manual_lo = float("nan")
        self._corridor_rmse_manual_hi = float("nan")

        display = self._display_result_prefer_best_live(result)
        self._last_result = display

        st = self._format_post_optimization_status(display, result)
        status_text = "Apres minimum grille (polish profond) | " + st
        self.lbl_status.setText(status_text)

        if self.logger:
            rm_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )
            self.logger.info(
                "GUI curve-min deep refit | done | rmse=%.8f | d_nm=%.6f",
                rm_fin,
                float(display.get("d_nm", float("nan"))),
            )
            if np.isfinite(rm_fin):
                _log_index_spline_best_config(self.logger, display, rm_fin, title="[FIN polish min grille]")

        self._plot_result(display, plot_source="polish_grille_profond")
        self._refresh_data_table()

        _cont_after_deep = getattr(self, "_continue_corridor_auto_refine_after_deep", None)
        if callable(_cont_after_deep) and bool(_cont_after_deep()):
            return

        self._refresh_post_optimization_option_controls()
        self.lbl_status.setText(self._post_optimization_ready_status(status_text))
        self.export_excel(auto_export=True)

    def _finish_rmse_heal_worker_done(self, healed_list: object) -> None:
        """Merge healed points into the main result and refresh."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_corridor_grid_busy(False)

        if not isinstance(healed_list, list) or not healed_list:
            dr = self._last_result if isinstance(self._last_result, dict) else {}
            self._finish_corridor_rmse_d_grid_worker_done(dr)
            return

        # Get baseline from last result
        base = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        d_main = list(np.asarray(base.get("profile_d_values_nm", []), dtype=np.float64).ravel())
        r_main = list(np.asarray(base.get("profile_d_rmse_values", []), dtype=np.float64).ravel())
        s_main = list(base.get("profile_d_full_results", []))

        added = 0
        for item in healed_list:
            if not isinstance(item, dict):
                continue
            dv = item.get("profile_d_val_nm")
            if dv is None:
                continue

            # Replace or add
            match = -1
            for i, d_ex in enumerate(d_main):
                if np.abs(d_ex - dv) < 1e-4:
                    match = i
                    break

            rm = float(np.sqrt(max(float(item.get("mse", 0.0)), 0.0)))
            if match >= 0:
                # Only replace if better!
                if rm < r_main[match] - 1e-15:
                    r_main[match] = rm
                    s_main[match] = item
                    added += 1
            else:
                d_main.append(dv)
                r_main.append(rm)
                s_main.append(item)
                added += 1

        if self.logger:
            self.logger.info("GUI RMSE(d) Grid Healing | Integrated %d improved/healed points", added)

        base["profile_d_values_nm"] = np.array(d_main, dtype=np.float64)
        base["profile_d_rmse_values"] = np.array(r_main, dtype=np.float64)
        base["profile_d_full_results"] = s_main
        base["profile_d_manual_grid_coverage_complete"] = True  # We healed!

        # Finally trigger the standard finalization
        self._finish_corridor_rmse_d_grid_worker_done(base)

    def _apply_corridor_preset_auto_robust(self) -> None:
        """Preset 'Auto robust corridor': local adaptive Delta, symmetry on parabola, stable parameters."""

        if hasattr(self, "cb_corr_mode"):
            self.cb_corr_mode.blockSignals(True)

            try:
                iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                if iq >= 0:
                    self.cb_corr_mode.setCurrentIndex(int(iq))

            finally:
                self.cb_corr_mode.blockSignals(False)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "sp_corridor_rmse_win"):
            self.sp_corridor_rmse_win.setValue(4)

        if hasattr(self, "sp_corridor_rmse_delta"):
            self.sp_corridor_rmse_delta.setValue(2e-4)

        self._corridor_parabola_half_window_pts = 4

        self._corridor_symmetric_center_mode = "parabola"

        self._corridor_adaptive_rmse_ref_half_width_nm = 1.5

        self._corridor_adaptive_rmse_probe_steps_each_side = 3

        self._corridor_adaptive_rmse_noise_factor = 3.0

        self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

        if hasattr(self, "_on_corr_mode_changed"):
            self._on_corr_mode_changed()

        if hasattr(self, "_refresh_corridor_rmse_robust_view"):
            try:
                self._refresh_corridor_rmse_robust_view()

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Corridor RMSE robust refresh after preset failed", exc_info=True)

        if hasattr(self, "_refresh_corridors_gui_state_labels"):
            self._refresh_corridors_gui_state_labels()

    def _set_corridor_grid_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_corridor_rmse_grid_calc"):
            self.btn_corridor_rmse_grid_calc.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_d_step_nm"):
            self.sp_corridor_grid_d_step_nm.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_n_points"):
            self.sp_corridor_grid_n_points.setEnabled(not busy)

        if hasattr(self, "sp_corridor_breakpoint_lookback"):
            self.sp_corridor_breakpoint_lookback.setEnabled(not busy)

        if hasattr(self, "chk_corridor_rmse_envelope_only"):
            self.chk_corridor_rmse_envelope_only.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_data"):
            self.btn_corridor_rmse_export_data.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_envelope_nk"):
            self.btn_corridor_rmse_export_envelope_nk.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "sp_corridor_partial_delta_nm"):
            self.sp_corridor_partial_delta_nm.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_partial_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_auto_smart_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setEnabled(bool(busy))

            if busy:
                self.pb_corridor_rmse_grid.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {CertusTheme.PRIMARY}; }}"
                )
            else:
                self.pb_corridor_rmse_grid.setStyleSheet("")

    def _set_corridor_grid_progress_ui(
        self,
        *,
        done: int,
        total: int,
        base_done: int | None = None,
        base_total: int | None = None,
        extra_done: int | None = None,
        current_d_nm: float | None = None,
    ) -> None:

        tot = max(1, int(total))
        dn = int(max(0, min(done, tot)))
        frac = float(dn) / float(tot)

        # UX-8: Sub-progress injection
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                iteration=self._prog_ui_last,
                max_iter=10000,
                evals=0,
                phase=f"RMSE(d) Grid: {dn}/{tot}",
                extra_info="",
                sub_iteration=dn,
                max_sub_iter=tot,
            )

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setValue(int(round(1000.0 * frac)))

        t0 = float(getattr(self, "_corridor_rmse_grid_live_t0", float("nan")))

        eta_txt = ""

        if np.isfinite(t0) and dn > 0:
            dt = max(0.0, time.perf_counter() - t0)

            avg = dt / float(dn)

            eta = max(0.0, float(tot - dn) * avg)

            eta_txt = f" | avg {avg:.2f}s/pt | ETA {eta:.1f}s"

        d_txt = ""

        if current_d_nm is not None and np.isfinite(float(current_d_nm)):
            d_txt = f" | d={float(current_d_nm):.3f} nm"

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            if base_done is not None and base_total is not None:
                btot = max(1, int(base_total))
                bdn = int(max(0, min(int(base_done), btot)))
                xdn = int(max(0, int(extra_done or 0)))
                bfrac = 100.0 * float(bdn) / float(btot)
                self.lbl_corridor_rmse_grid_progress.setText(
                    f"Grid {bdn}/{btot} ({bfrac:.1f}%) + extra {xdn}{d_txt}{eta_txt}"
                )
            else:
                self.lbl_corridor_rmse_grid_progress.setText(f"Grid {dn}/{tot} ({100.0 * frac:.1f}%){d_txt}{eta_txt}")

    def _sync_corridor_manual_controls(self, d_s: np.ndarray, i_best: int) -> None:

        if (
            not hasattr(self, "sl_corridor_manual_half")
            or not hasattr(self, "btn_generate_manual_corridor")
            or d_s.size == 0
            or i_best < 0
            or i_best >= int(d_s.size)
        ):
            self._reset_corridor_manual_controls()

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        man_active = bool(getattr(self, "_corridor_rmse_manual_active", False))
        man_lo = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))
        man_hi = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))
        has_manual_interval = man_active and np.isfinite(man_lo) and np.isfinite(man_hi) and man_hi >= man_lo
        if has_manual_interval:
            # Preserve the effective manual interval currently applied/generated,
            # instead of recomputing preview solely from the previous slider state.
            d_center = 0.5 * float(man_lo + man_hi)

        self._set_corridor_manual_bounds_labels(float(d_s[0]), d_best, float(d_s[-1]))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_steps = max(1, int(round(max_half * scale)))

        cur_half = self._corridor_manual_half_width_nm()
        if has_manual_interval:
            cur_half = 0.5 * float(max(0.0, man_hi - man_lo))

        if not np.isfinite(cur_half) or cur_half <= 0.0:
            if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
                cur_half = 0.5 * max(0.0, float(self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

            elif d_s.size >= 2:
                cur_half = max(float(np.nanmedian(np.abs(np.diff(d_s)))), 0.0)

            else:
                cur_half = 0.0

        cur_half = float(min(max(cur_half, 0.0), max_half))

        self.sl_corridor_manual_half.blockSignals(True)

        self.sl_corridor_manual_half.setRange(0, max_steps)

        self.sl_corridor_manual_half.setTickInterval(max(1, max_steps // 8))

        self.sl_corridor_manual_half.setValue(int(round(cur_half * scale)))

        self.sl_corridor_manual_half.setEnabled(max_steps > 0)

        self.sl_corridor_manual_half.blockSignals(False)

        self.btn_generate_manual_corridor.setEnabled(True)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(bool(self._corridor_rmse_robust_ok))

        self._set_corridor_manual_interval_preview(d_center, cur_half)

    def _generate_corridor_from_current_grid(self) -> None:
        """Generate n/k corridor from all currently available RMSE(d) grid points."""

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: no RMSE(d) grid in memory")

            QMessageBox.information(self, "Generate corridor (grid)", "No RMSE(d) grid is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        if d_s.size == 0:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: RMSE(d) grid empty")

            QMessageBox.information(self, "Generate corridor (grid)", "No valid RMSE(d) points are available.")

            return

        # Guard against partial live updates: d-values can be present while
        # n/k profile curves are still being filled by the worker.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_s.size
            and k_curves.shape[0] == d_s.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_s.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_lo = float(np.nanmin(d_s))

        d_hi = float(np.nanmax(d_s))

        if self.logger:
            self.logger.info(
                "GUI generate corridor(grid) | request | grid_points=%d | d_range=[%.6f, %.6f] nm",
                int(d_s.size),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from RMSE(d) grid on",
        )

        if not ok:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | failed for current RMSE(d) grid")

            QMessageBox.warning(
                self,
                "Generate corridor (grid)",
                "Unable to generate n/k corridor from the current RMSE(d) grid.",
            )

    def _on_corridor_rmse_plot_clicked(self, ev: Any) -> None:

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        if d_s.size == 0 or r_s.size != d_s.size:
            return

        try:
            vb = self.plot_corridor_rmse_d.plotItem.vb

            p = vb.mapSceneToView(ev.scenePos())

            x = float(p.x())

        except NUMERICAL_FAULT_EXCEPTIONS:
            return

        if not np.isfinite(x):
            return

        i_sel = int(np.argmin(np.abs(d_s - x)))

        d_sel = float(d_s[i_sel])

        r_sel = float(r_s[i_sel])

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if i_best < 0 or i_best >= d_s.size:
            i_best = int(np.argmin(r_s))

        d_best = float(d_s[i_best])

        r_best = float(r_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        rb_ok = bool(getattr(self, "_corridor_rmse_robust_ok", False))

        if hasattr(self, "lbl_corridor_rmse_summary"):
            tail = (
                f" | robust interval ? [{d_lo_rb:.3f}, {d_hi_rb:.3f}] nm"
                if rb_ok and np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb)
                else ""
            )

            self.lbl_corridor_rmse_summary.setText(
                f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {r_best:.6f} | "
                f"selected: d = {d_sel:.3f} nm, RMSE = {r_sel:.6f}, DeltaRMSE = {r_sel - r_best:+.6e}{tail}"
            )
