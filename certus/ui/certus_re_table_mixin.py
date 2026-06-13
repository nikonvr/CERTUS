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


class CertusRETableMixin:
    """CertusRETableMixin for CERTUS_RE."""

    def _stack_info_front_table_cols(self) -> tuple[int, int]:
        """Table RE 5 colonnes : Mat=1, QWOT=3."""

        return (_RE_FT_COL_MAT, _RE_FT_COL_QW)

    def _on_l0_changed_refresh_front_table(self, *_args) -> None:

        self._re_refresh_front_table_num_and_n()

    def _on_l0_changed_update_substrate_info(self, *_args) -> None:

        self._update_substrate_info()

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox):
        """RE specific: no extra connections."""

        pass

    def _on_layer_added(self):
        """RE specific: no extra actions."""

        # RE layers are usually loaded from Excel, but manual add is now possible.

        pass

    def _on_layer_deleted(self):
        """RE specific: no extra actions."""

        pass

    def _update_layer_count(self):

        super()._update_layer_count()

        self._re_refresh_front_table_num_and_n()

    def _re_parse_thick_nm_from_table(self, row: int) -> float | None:
        """Read thickness (nm) shown in the Thick column."""

        it = self.front_table.item(row, _RE_FT_COL_THICK)

        if it is None:
            return None

        s = (it.text() or "").strip().replace(",", ".")

        if not s or s.upper() == "N/A":
            return None

        try:
            d = float(s)

        except ValueError:
            return None

        return d if np.isfinite(d) and d > 1e-9 else None

    def _re_n_from_qwot_and_thick(self, qwot: float, d_nm: float, l0: float) -> float | None:
        """n at lambda0 from QWOT = 4 n d / lambda0  =>  n = QWOT*lambda0 / (4d)."""

        if not np.isfinite(qwot) or not np.isfinite(d_nm) or not np.isfinite(l0) or abs(l0) < 1e-9 or d_nm < 1e-9:
            return None

        n_est = (float(qwot) * float(l0)) / (4.0 * float(d_nm))

        return n_est if np.isfinite(n_est) and n_est > 0 else None

    def _re_refresh_front_table_num_and_n(self) -> None:
        """Layer index (1...) and Re(n) at lambda0 (3 decimals) for each row."""

        if not hasattr(self, "front_table") or self.front_table.columnCount() < 5:
            return

        mats = self._get_materials()

        l0 = float(self.l0_spin.value()) if hasattr(self, "l0_spin") else float(getattr(self, "_re_lambda_ref", 500.0))

        wls = np.array([l0], dtype=np.float64)

        for r in range(self.front_table.rowCount()):
            num_it = self.front_table.item(r, _RE_FT_COL_NUM)

            if num_it is None:
                num_it = QTableWidgetItem()

                num_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                num_it.setFlags(num_it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.front_table.setItem(r, _RE_FT_COL_NUM, num_it)

            num_it.setText(str(r + 1))

            n_it = self.front_table.item(r, _RE_FT_COL_N)

            if n_it is None:
                n_it = QTableWidgetItem()

                n_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                n_it.setFlags(n_it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.front_table.setItem(r, _RE_FT_COL_N, n_it)

            mat = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

            nr = float("nan")

            n_src = ""

            if mat and mats and mat in mats:
                try:
                    nk = mats[mat].get_nk(wls)

                    nr = float(np.real(np.asarray(nk, dtype=np.complex128).ravel()[0]))

                    n_src = "Tabulated n(lambda₀)"

                except NUMERICAL_FAULT_EXCEPTIONS :
                    nr = float("nan")

            if not np.isfinite(nr):
                sb = self.front_table.cellWidget(r, _RE_FT_COL_QW)

                qw = float(sb.value()) if sb and hasattr(sb, "value") else float("nan")

                d_nm = self._re_parse_thick_nm_from_table(r)

                if d_nm is not None:
                    n_alt = self._re_n_from_qwot_and_thick(qw, d_nm, l0)

                    if n_alt is not None:
                        nr = float(n_alt)

                        n_src = "QWOT & thickness (n = QWOTlambda₀/(4d))"

            if np.isfinite(nr):
                n_it.setText(f"{nr:.3f}")

            else:
                n_it.setText("")

                n_src = ""

            tip = f"Layer #{r + 1}  lambda₀ = {l0:.1f} nm"

            if mat:
                tip += f"  material {mat}"

            if n_src:
                tip += f"  {n_src}"

            n_it.setToolTip(tip)

    def _merge_adjacent_layers(self):
        """Same logic as base class; Mat / QWOT columns at 1 and 3 (RE 5-column table)."""

        merged = False

        passes = 0

        c_m, c_q = _RE_FT_COL_MAT, _RE_FT_COL_QW

        while passes < 10:
            passes += 1

            found = False

            i = 1

            while i < self.front_table.rowCount():
                m_curr = self._safe_get_combo_text(i, c_m)

                m_prev = self._safe_get_combo_text(i - 1, c_m)

                if m_curr and m_prev and m_curr == m_prev:
                    try:
                        q_curr = self.front_table.cellWidget(i, c_q).value()

                        sp_prev = self.front_table.cellWidget(i - 1, c_q)

                        sp_prev.blockSignals(True)

                        sp_prev.setValue(sp_prev.value() + q_curr)

                        sp_prev.blockSignals(False)

                        self.front_table.removeRow(i)

                        merged = True

                        found = True

                        self.log(f"Merged adjacent layers ({m_curr})", "INFO")

                        continue

                    except (
                        ValueError,
                        TypeError,
                        RuntimeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        FileNotFoundError,
                    ) as e:
                        if hasattr(self, "logger") and self.logger:
                            self.logger.error(f"Merge error: {e}")

                i += 1

            if not found:
                break

        self._update_layer_count()

        if merged:
            self._schedule_eval()

    def _update_thickness_display(self):
        """Physical thickness: column Thick(nm) = index 4 (RE table)."""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        stack = self._get_front_stack()

        if stack and mats:
            ep = init_thickness(stack, l0, mats)

            if ep is not None:
                for r, d in enumerate(ep):
                    it = self.front_table.item(r, _RE_FT_COL_THICK)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_current = ep

                if getattr(self, "_re_loading_workbook", False):
                    # During RE load, keep the exact workbook-derived thickness vector as source of truth.
                    # Do not let later UI refreshes or schedule_eval() overwrite it with a reconstructed copy.
                    loaded_ep = np.asarray(ep, dtype=np.float64).ravel().copy()
                    self._re_loaded_exact_ep = loaded_ep
                    self._use_exact_ep = True
                    self.ep_current = loaded_ep.copy()

                self._on_front_thickness_updated()

        self._re_refresh_front_table_num_and_n()

    def _update_qwot_from_ep(self, ep):
        """QWOT in column 3 (RE table)."""

        self.front_table.blockSignals(True)

        ep = np.asarray(ep, dtype=float).ravel()

        for r in range(min(len(ep), self.front_table.rowCount())):
            mat_name = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

            qw_val = self._ep_nm_to_qwot(ep[r], mat_name)

            sb = self.front_table.cellWidget(r, _RE_FT_COL_QW)

            if sb:
                sb.setValue(qw_val)

        self.front_table.blockSignals(False)

    def _add_front_row(self, mat: str, qwot: float, var: bool, del_checked: bool = False):
        """RE: no Var/Del columns (thicknesses driven by RE file / optimization)."""

        del var, del_checked

        row = self.front_table.rowCount()

        self.front_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._merge_adjacent_layers)

        self.front_table.setCellWidget(row, _RE_FT_COL_MAT, cb)

        sb = self._create_spin(qwot, dec=4)

        sb.valueChanged.connect(self._on_schedule_eval_signal)

        self._on_qwot_changed_connection(sb)

        self.front_table.setCellWidget(row, _RE_FT_COL_QW, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(row, _RE_FT_COL_THICK, it)

        self._update_layer_count()

    def _get_front_stack(self) -> list[Layer]:
        """RE: all front-table layers are active in the model (equivalent to Var=True)."""

        try:
            stack: list[Layer] = []

            for r in range(self.front_table.rowCount()):
                mat = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

                if not mat:
                    continue

                qw = self.front_table.cellWidget(r, _RE_FT_COL_QW).value()

                stack.append(Layer(mat, qw, True))

            return stack

        except (AttributeError, ValueError, IndexError) as e:
            logging.debug(f"Could not get front stack: {e}")

            return []

    def add_target(self):
        """Adds spectral target"""

        r = self.target_table.rowCount()

        self.target_table.insertRow(r)

        col_idx = 0

        # Active Checkbox

        chk = QCheckBox()

        chk.setToolTip("Enable or disable this target.")

        chk.setChecked(True)

        chk.stateChanged.connect(self._schedule_eval)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.target_table.setCellWidget(r, col_idx, cw)

        col_idx += 1

        if self.oblique_mode:
            # Oblique: Ang, Pol, Type, lmin, lmax, Weight (no Val min/max: RE = _re_targets points)

            # Angle

            angle_sb = self._create_spin(0.0, dec=1, minv=0, maxv=90)

            angle_sb.setToolTip("Incident angle (degrees).")

            angle_sb.valueChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, angle_sb)

            col_idx += 1

            # Polarization

            pol_combo = QComboBox()

            pol_combo.setToolTip("Target polarization: s, p, or Avg (unpolarized average).")

            pol_combo.addItems(["s", "p", "Avg"])

            pol_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, pol_combo)

            col_idx += 1

            # Type (R or T)

            type_combo = QComboBox()

            type_combo.setToolTip("Target type: Reflectance (R) or Transmittance (T).")

            type_combo.addItems(["R", "T"])

            type_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, type_combo)

            col_idx += 1

            # lambdamin, lambdamax

            _tl0, _th0 = self._re_default_target_lmin_lmax_nm()

            for val, dec, tt in (
                (_tl0, 1, "Target wavelength range start (nm)."),
                (_th0, 1, "Target wavelength range end (nm)."),
            ):
                sb = self._create_spin(val, dec=dec, minv=200, maxv=20000)

                sb.setToolTip(tt)

                sb.valueChanged.connect(self._schedule_eval)

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

            w_sb = self._create_spin(1.0, dec=1, minv=0, maxv=100)

            w_sb.setToolTip(
                "Weight (manual row without RE file). With an RE file, the fit uses the spectral "
                "points from the workbook, not this column."
            )

            w_sb.valueChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, w_sb)

            col_idx += 1

        else:
            # Normal Mode: lmin, lmax, Tmin, Tmax, Weight

            _nl0, _nh0 = self._re_default_target_lmin_lmax_nm()

            defs = [_nl0, _nh0, 0.0, 0.5, 1.0]

            decs = [1, 1, 3, 3, 1]

            ranges = [(200, 20000), (200, 20000), (0, 1), (0, 1), (0, 100)]

            for i, val in enumerate(defs):
                sb = self._create_spin(val, dec=decs[i], minv=ranges[i][0], maxv=ranges[i][1])

                tts = [
                    "Target wavelength range start (nm).",
                    "Target wavelength range end (nm).",
                    "Minimum target Transmittance (0-1).",
                    "Maximum target Transmittance (0-1).",
                    "Weight multiplier for this target.",
                ]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self._on_schedule_eval_signal)

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

    def _get_materials(self) -> dict:
        """Tabular H/L/substrate materials after loading the RE Excel file only."""

        if not getattr(self, "_re_loaded", False):
            return {}

        try:
            result = {}

            for key, attr in (
                ("H", "_re_tabular_H"),
                ("L", "_re_tabular_L"),
                ("Substrate", "_re_tabular_Sub"),
            ):
                tab = getattr(self, attr, None)

                if tab is not None:
                    result[key] = tab

            return result

        except (AttributeError, KeyError) as e:
            logging.debug(f"Could not get materials: {e}")

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        # RE: files loaded -> measurement targets (even if oblique UI checkbox is off).

        if getattr(self, "_re_loaded", False) and self._re_targets:
            return self._re_filter_targets_by_fit_window([t for t in self._re_targets if t.on])

        if not self.oblique_mode:
            return []  # Else normal mode: _get_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                active = chk.isChecked() if chk else False

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                angle = angle_w.value() if angle_w else 0.0

                # Polarisation

                pol_w = self.target_table.cellWidget(r, 2)

                polarization = pol_w.currentText() if pol_w else "s"

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                target_type = type_w.currentText() if type_w else "T"

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                _dl0, _dh0 = self._re_default_target_lmin_lmax_nm()

                lmin = lmin_w.value() if lmin_w else _dl0

                lmax = lmax_w.value() if lmax_w else _dh0

                weight_w = self.target_table.cellWidget(r, 6)

                weight = weight_w.value() if weight_w else 1.0

                targets.append(
                    ObliqueTarget(
                        angle=angle,
                        pol=polarization,
                        target_type=target_type,
                        lmin=lmin,
                        lmax=lmax,
                        tmin=0.5,
                        tmax=0.5,
                        w=weight,
                        on=active,
                        include_backside=True,
                    )
                )

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug(f"Could not get oblique target row: {e}")

        return targets

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """RE specific plot info mapping."""

        if widget == self.spectrum_plot:
            return "spectrum", "Spectrum (T)"

        elif widget == self.profile_plot:
            return "profile", "Refractive Index Profile"

        elif widget == self.nk_plot:
            return "nk", "Dispersion n(lambda)"

        return None

    def _paste_from_excel(self):
        """Pastes data from Excel into layer table"""

        clipboard = QApplication.clipboard()

        text = clipboard.text()

        if not text:
            return

        try:
            # Excel parse (tabs/cols, newlines/rows)

            lines = text.strip().split("\n")

            rows_data = []

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Split columns (tabs or multiple spaces)

                cols = line.split("\t")

                if len(cols) < 2:  # If no tab, try with multiple spaces
                    cols = [c for c in line.split(" ") if c]

                if len(cols) < 2:
                    continue

                # Parse columns

                # Fmt: Mat, QWOT, [Thick], [Var]

                mat = cols[0].strip()

                qwot_str = cols[1].strip()

                # Check if material is valid

                materials = [m for m in CFG.MATERIALS if m != "Substrate"]

                if mat not in materials:
                    # Try to find match (case insensitive)

                    mat_lower = mat.lower()

                    mat_found = None

                    for m in materials:
                        if m.lower() == mat_lower:
                            mat_found = m

                            break

                    if mat_found:
                        mat = mat_found

                    else:
                        self.log(f"Invalid material ignored: {mat}", "WARNING")

                        continue

                # Parser QWOT

                try:
                    qwot = float(qwot_str.replace(",", "."))

                except ValueError:
                    self.log(f"Invalid QWOT value ignored: {qwot_str}", "WARNING")

                    continue

                rows_data.append((mat, qwot))

            if not rows_data:
                self.log("No valid data to paste", "WARNING")

                return

            # Clear table or append depending on selection

            current_row = self.front_table.currentRow()

            if current_row >= 0:
                # Paste from selected row

                start_row = current_row

            else:
                # Clear table and paste from start

                self.front_table.blockSignals(True)

                self.front_table.setRowCount(0)

                self.front_table.blockSignals(False)

                start_row = 0

            # Add rows

            self.front_table.blockSignals(True)

            for i, (mat, qwot) in enumerate(rows_data):
                row = start_row + i

                if row >= self.front_table.rowCount():
                    self._add_front_row(mat, qwot, True)

                else:
                    cb = self._create_combo(mat)

                    cb.currentIndexChanged.connect(self._merge_adjacent_layers)

                    self.front_table.setCellWidget(row, _RE_FT_COL_MAT, cb)

                    sb = self._create_spin(qwot, dec=4)

                    sb.valueChanged.connect(self._on_schedule_eval_signal)

                    self.front_table.setCellWidget(row, _RE_FT_COL_QW, sb)

                    it = self.front_table.item(row, _RE_FT_COL_THICK)

                    if it is None:
                        it = QTableWidgetItem("N/A")

                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        self.front_table.setItem(row, _RE_FT_COL_THICK, it)

                    else:
                        it.setText("N/A")

            self.front_table.blockSignals(False)

            self._update_layer_count()

            self._schedule_eval()

            self.log(f"{len(rows_data)} row(s) pasted from Excel", "SUCCESS")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Paste error: {str(e)}", "ERROR")

            traceback.print_exc()

    def _reconstruct_lambda_list(self, raw: list) -> list:
        """Reconstruct a wavelength list from raw values, filling None gaps via step.

        Used by _parse_re_index and _parse_re_measurement.  The step is inferred

        from the first two cached (numeric) values found in *raw*.  If only one

        cached value exists the step defaults to 10 nm.

        """

        if not raw:
            return []

        first_val = None

        first_idx = 0

        step = None

        for i, v in enumerate(raw):
            if isinstance(v, (int, float)):
                if first_val is None:
                    first_val = float(v)

                    first_idx = i

                elif step is None:
                    step = float(v) - first_val

                    break

        if first_val is None:
            return []

        if step is None or abs(step) < 1e-9:
            step = 10.0

        result = []

        for i, v in enumerate(raw):
            if isinstance(v, (int, float)):
                result.append(float(v))

            else:
                result.append(first_val + (i - first_idx) * step)

        return result

    def _re_build_target_theory_rows(
        self,
        ep: np.ndarray,
        a_pct: float,
        b_pct: float,
        f_pct: float,
        *,
        spline_dH: np.ndarray | None = None,
        spline_dL: np.ndarray | None = None,
        spline_lam_node2_nm: float | None = None,
        re_envelope_scale: float = 1.0,
    ) -> list[dict[str, Any]]:
        """One row per RE point: target vs computed R/T (phase 2: DeltaRe splines if provided)."""

        stack = self._get_front_stack()

        mats = self._get_materials()

        ep = np.asarray(ep, dtype=np.float64).flatten()

        tgts_all = getattr(self, "_re_targets", [])

        tgts = self._re_filter_targets_by_fit_window([t for t in tgts_all if t.on and t.valid()])

        if not tgts:
            return []

        float_dtype = np.float64

        complex_dtype = np.complex128

        tgt_centers = sorted({(t.lmin + t.lmax) / 2.0 for t in tgts})

        wls = np.array(tgt_centers, dtype=float_dtype)

        mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

        n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

        n_sub = np.ascontiguousarray(mats_nk["Substrate"])

        lambda_ref = float(self.l0_spin.value())

        is_H = np.array([l.mat == "H" for l in stack], dtype=bool)

        is_L = np.array([l.mat == "L" for l in stack], dtype=bool)

        _sct0 = getattr(self, "_re_sub_cauchy_a0", None)

        _sub_bt = None

        if (
            spline_dH is not None
            and spline_dL is not None
            and len(np.asarray(spline_dH).ravel()) == int(RE_SPLINE_N_KNOTS)
            and _sct0 is not None
            and getattr(self, "_re_sub_cauchy_a1", None) is not None
            and getattr(self, "_re_sub_cauchy_a2", None) is not None
        ):
            _sub_bt = (
                float(_sct0),
                float(self._re_sub_cauchy_a1),
                float(self._re_sub_cauchy_a2),
            )

        n_layers_nominal, n_sub = re_apply_re_index_model(
            n_layers_nominal,
            n_sub,
            is_H=is_H,
            is_L=is_L,
            wls_nm=wls,
            lambda_ref_nm=lambda_ref,
            a_pct=a_pct,
            b_pct=b_pct,
            f_pct=f_pct,
            spline_dH=spline_dH,
            spline_dL=spline_dL,
            spline_lam_node2_nm=spline_lam_node2_nm,
            re_envelope_scale=re_envelope_scale,
            sub_cauchy_theta=_sub_bt,
        )

        n_layers_T = np.ascontiguousarray(n_layers_nominal.T)

        from collections import defaultdict

        config_groups = defaultdict(list)

        for tgt in tgts:
            config_groups[(tgt.angle, tgt.pol, tgt.include_backside)].append(tgt)

        out: list[dict[str, Any]] = []

        p4_kw = self._re_p4_display_beam_kwargs()

        for (angle, pol, include_backside), tgt_list in config_groups.items():
            R_c, T_c = _re_calc_spectrum_for_config(wls, n_layers_T, ep, n_sub, angle, pol, include_backside, **p4_kw)

            for tgt in tgt_list:
                wl_c = float((tgt.lmin + tgt.lmax) / 2.0)

                idx = int(np.argmin(np.abs(wls - wl_c)))

                if abs(float(wls[idx]) - wl_c) > 0.05:
                    continue

                tgt_val = float((tgt.tmin + tgt.tmax) / 2.0)

                theo = float(R_c[idx] if tgt.target_type == "R" else T_c[idx])

                out.append(
                    {
                        "lambda_nm": wl_c,
                        "angle_deg": float(tgt.angle),
                        "pol": str(tgt.pol),
                        "target_type": str(tgt.target_type),
                        "include_backside": bool(tgt.include_backside),
                        "weight": float(tgt.w),
                        "target": tgt_val,
                        "theory": theo,
                        "delta": theo - tgt_val,
                    }
                )

        out.sort(key=lambda r: (r["lambda_nm"], r["angle_deg"], r["pol"], r["target_type"]))

        return out

    def _re_format_rmse_value(self, v: float | None) -> str:
        """Format an RMSE value for log output."""
        if v is None:
            return ""
        try:
            vf = float(v)
            return f"{vf:.6f}" if np.isfinite(vf) else ""
        except (TypeError, ValueError):
            return ""
