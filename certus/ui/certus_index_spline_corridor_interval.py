"""CERTUS-INDEX-SPLINE corridors - the thickness interval a corridor is generated from, manual or robust, and its controls: the preset, the slider and its bounds, the preview, the generation from the current grid (methods moved, text unchanged, out of certus_index_spline_settings.py, certus_index_spline_corridorui_mixin.py, certus_index_spline_manualmesh_mixin.py and certus_index_spline_rendering.py)."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QSlider, QVBoxLayout

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_design_tokens import slider_corridor_half_stylesheet
from certus.spline.certus_index_spline_core import logger
from certus.ui.certus_index_spline_corridor_common import (
    _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN,
    _DEFAULT_CORRIDOR_RMSE_DELTA,
    _DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA,
)
from certus.ui.certus_index_spline_corridor_ui import CertusTheme, create_styled_button


class _CorridorIntervalMixin:
    """The manual and robust interval of a corridor, and its controls. A slice of the window: `_CorridorControlMixin` and `CertusIndexSplineCorridorUIMixin` inherit it; what it reads on the window is declared in certus_index_spline_corridor_host.py."""

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
            self.sp_corridor_rmse_delta.setValue(_DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA)

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

        max_steps = max(1, round(max_half * scale))

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

        self.sl_corridor_manual_half.setValue(round(cur_half * scale))

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

    def _use_robust_corridor_interval(self) -> None:

        if not bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        float(d_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        if not (np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb >= d_lo_rb):
            return

        half = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        half = float(min(max(0.0, half), max_half))

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.setValue(round(half * scale))
            # setValue does not emit valueChanged if unchanged: force visual sync
            # so vertical interval bars always reflect current robust bounds.
            self._on_corridor_manual_slider_changed(self.sl_corridor_manual_half.value())

    def _corridor_manual_half_width_nm(self) -> float:

        if not hasattr(self, "sl_corridor_manual_half"):
            return 0.0

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        return float(self.sl_corridor_manual_half.value()) / float(scale)

    def _set_corridor_manual_interval_preview(self, d_best: float, half_width_nm: float) -> None:

        hw = float(max(0.0, half_width_nm))

        self._corridor_rmse_manual_lo = float(d_best - hw)

        self._corridor_rmse_manual_hi = float(d_best + hw)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText(f"+/-{hw:.2f} nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText(
                f"Manual interval: [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
            )

    def _set_corridor_manual_bounds_labels(self, d_min: float, d_best: float, d_max: float) -> None:

        if hasattr(self, "lbl_corridor_manual_dmin"):
            self.lbl_corridor_manual_dmin.setText(f"d_min: {d_min:.2f} nm" if np.isfinite(d_min) else "d_min: -")

        if hasattr(self, "lbl_corridor_manual_dcenter"):
            self.lbl_corridor_manual_dcenter.setText(f"d*: {d_best:.2f} nm" if np.isfinite(d_best) else "d*: -")

        if hasattr(self, "lbl_corridor_manual_dmax"):
            self.lbl_corridor_manual_dmax.setText(f"d_max: {d_max:.2f} nm" if np.isfinite(d_max) else "d_max: -")

    def _corridor_manual_max_half_width_nm(self, d_s: np.ndarray) -> float:

        d_arr = np.asarray(d_s, dtype=np.float64).ravel()

        if d_arr.size == 0:
            return 0.0

        d_span = float(max(np.nanmax(d_arr) - np.nanmin(d_arr), 0.0)) if np.any(np.isfinite(d_arr)) else 0.0

        robust_half = 0.0

        if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
            robust_half = 0.5 * float(max(0.0, self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

        cur_half = self._corridor_manual_half_width_nm()

        step_half = float(np.nanmedian(np.abs(np.diff(d_arr)))) if d_arr.size >= 2 else 0.0

        return float(max(d_span, robust_half, cur_half, step_half, 0.0))

    def _reset_corridor_manual_controls(self) -> None:

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.blockSignals(True)

            self.sl_corridor_manual_half.setRange(0, 1)

            self.sl_corridor_manual_half.setValue(0)

            self.sl_corridor_manual_half.setEnabled(False)

            self.sl_corridor_manual_half.blockSignals(False)

        if hasattr(self, "btn_generate_manual_corridor"):
            self.btn_generate_manual_corridor.setEnabled(False)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(False)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText("+/-0.00 nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText("Manual interval: -")

        self._set_corridor_manual_bounds_labels(float("nan"), float("nan"), float("nan"))

    def _on_corridor_manual_slider_changed(self, _value: int) -> None:

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = float(d_s[i_best])

        self._set_corridor_manual_interval_preview(d_center, self._corridor_manual_half_width_nm())

        src = self._corridor_profile_source_result()

        if src is not None:
            try:
                self._plot_corridor_rmse_tab(src)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Manual corridor slider refresh failed", exc_info=True)

    def _build_corridor_tab_generate(self, lay_generate: QVBoxLayout) -> None:
        lay_generate.setSpacing(6)

        lbl_manual = QLabel("Alternative path: define a manual interval around d* and generate a corridor directly.")
        lbl_manual.setWordWrap(True)
        lbl_manual.setStyleSheet(CertusTheme.get_hint_text_style())
        lay_generate.addWidget(lbl_manual)

        row_manual = QHBoxLayout()
        row_manual.addWidget(QLabel("Manual centered corridor (+/- nm):"))

        self.sl_corridor_manual_half = QSlider(Qt.Orientation.Horizontal)
        self.sl_corridor_manual_half.setRange(0, 1)
        self.sl_corridor_manual_half.setValue(0)
        self.sl_corridor_manual_half.setSingleStep(1)
        self.sl_corridor_manual_half.setPageStep(5)
        self.sl_corridor_manual_half.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sl_corridor_manual_half.setEnabled(False)
        self.sl_corridor_manual_half.setToolTip(
            "<b>Cursor: Manual Width (±Δd)</b><br>"
            "Set the corridor width manually to generate the n, k, and L envelopes.<br>"
            "The generated corridor will be [d* - Δd, d* + Δd]."
        )
        self.sl_corridor_manual_half.setStyleSheet(slider_corridor_half_stylesheet())
        self.sl_corridor_manual_half.valueChanged.connect(self._on_corridor_manual_slider_changed)
        row_manual.addWidget(self.sl_corridor_manual_half, 1)

        self.lbl_corridor_manual_half = QLabel("+/-0.00 nm")
        self.lbl_corridor_manual_half.setMinimumWidth(90)
        row_manual.addWidget(self.lbl_corridor_manual_half)

        self.btn_corridor_manual_robust = create_styled_button("Use robust interval", "secondary", parent=self)
        self.btn_corridor_manual_robust.setEnabled(False)
        self.btn_corridor_manual_robust.setToolTip(
            "<b>Synchronize with Robust Interval</b><br>"
            "Automatically aligns the manual slider to the width calculated by the parabola (purple/orange).<br>"
            "Use this to restart from the smart suggestion before manual fine-tuning."
        )
        self.btn_corridor_manual_robust.clicked.connect(self._use_robust_corridor_interval)
        row_manual.addWidget(self.btn_corridor_manual_robust)

        self.btn_generate_manual_corridor = create_styled_button(
            "Corridor from interval", "primary", parent=self
        )
        self.btn_generate_manual_corridor.setEnabled(False)
        self.btn_generate_manual_corridor.setToolTip(
            "<b>Generate visual n/k/L corridor</b><br>"
            "Reconstruct and display the uncertainty envelopes on the Indices tab "
            "as corridors surrounding the nominal model."
        )
        self.btn_generate_manual_corridor.clicked.connect(self._apply_manual_corridor_selection)
        row_manual.addWidget(self.btn_generate_manual_corridor)

        lay_generate.addLayout(row_manual)

        row_manual_meta = QHBoxLayout()
        self.lbl_corridor_manual_dmin = QLabel("d_min: -")
        self.lbl_corridor_manual_dcenter = QLabel("d*: -")
        self.lbl_corridor_manual_dmax = QLabel("d_max: -")
        self.lbl_corridor_manual_interval = QLabel("Manual interval: -")

        for _lab in (
            self.lbl_corridor_manual_dmin,
            self.lbl_corridor_manual_dcenter,
            self.lbl_corridor_manual_dmax,
            self.lbl_corridor_manual_interval,
        ):
            _lab.setStyleSheet(CertusTheme.get_hint_text_style())

        row_manual_meta.addWidget(self.lbl_corridor_manual_dmin)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dcenter)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dmax)
        row_manual_meta.addStretch(1)
        row_manual_meta.addWidget(self.lbl_corridor_manual_interval)
        lay_generate.addLayout(row_manual_meta)
