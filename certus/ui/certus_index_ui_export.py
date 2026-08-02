import os
import sys
from pathlib import Path
import logging
import traceback
from certus.ui.certus_index_ui_utils import _notify_user
import time
import functools
from datetime import datetime
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtSvgWidgets import QSvgWidget
from certus.core.certus_core import (
    get_resource_path,
    __version__,
    HC_EV_NM,
    N_MIN_LIMIT,
    N_MAX_LIMIT,
    K_MAX_LIMIT,
    SMALL_EPSILON,
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_LIST,
    certus_timestamp_display,
)
from certus.utils.certus_data import generate_html_report
from certus.ui.certus_ui import install_standard_shortcuts
from certus.utils.certus_index_utils import DataType, analyze_loaded_data, normalize_index_config
from certus_physics import (
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
    epsilon_to_nk,
    get_n_substrate_array_by_id,
    get_n_frosted_glass_array,
    calculate_RT_single_layer_backside_array,
    calculate_bare_substrate_RT,
    calculate_single_interface_R,
    calculate_bare_substrate_T_absorbing,
    calculate_bare_substrate_R_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
)
from certus.utils.certus_index_utils import _get_substrate_n_array_index
from certus.core.certus_index_core import (
    OptimizationConfig,
    OptimizationResults,
    substrateMode,
    calculate_relative_R_normalization,
    _optimize_point_kernel,
    _optimize_all_points_batch,
    _SAPPHIRE_DATA_FILE,
    _SAPPHIRE_WLS,
    _SAPPHIRE_K,
    _SAPPHIRE_FILE_HAS_K_COLUMN,
    _SILICON_WLS,
    _SILICON_K,
)
from certus.workers.certus_index_workers import (
    IRGlobalModelWorker,
    OptimizationWorker,
    IndexBeamAnalysisWorker,
    _compute_RT_from_config,
    _index_live_spectrum_visibility,
    _spectrum_visibility_target_traces,
)
from certus.ui.certus_ui import (
    CertusBaseApp,
    CertusCard,
    CertusDashboardCard,
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    CertusThemeToggle,
    DetachedPlotWindow,
    EnhancedProgressWidget,
    ExcelTableWidget,
    FlashyCard,
    apply_certus_theme,
    clone_plot_widget,
    wrap_scientific_plot_with_toolbar,
    create_styled_button,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    stop_worker_and_thread,
    create_header_logo_widget,
    create_top_actions_bar,
    certus_get_open_file_name,
    get_export_config,
    init_certus_app,
    open_documentation,
    get_certus_last_dir,
    set_certus_last_dir,
    setup_gui_exception_handling,
    setup_module_logging,
    setup_pyqtgraph_defaults,
    show_toast,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.ui.certus_svg import SVG_AVAILABLE
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import QObject, QSettings, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

class CertusIndexExportMixin:
    def _make_index_tlu_live_ctx(self, c: OptimizationConfig) -> dict | None:
        """lambda / n_sub grid identical to OptimizationWorker.run (TLU) for live, like Metal Bilayer."""

        try:
            _lmf = getattr(c, "lambda_max_fit", None)

            effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))

            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)

            wls = c.target_data.loc[mask, "lambda"].to_numpy(dtype=np.float64)

            if wls.size == 0:
                return None

            sub_id = c.substrate_sellmeier_id
            if sub_id is None:
                sub_id = -1

            if c.n_sub_data is not None:
                l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

                n_sub = np.interp(
                    wls,
                    l_full,
                    c.n_sub_data,
                    left=c.n_sub_data[0],
                    right=c.n_sub_data[-1],
                ).astype(np.float64)

            else:
                n_sub = _get_substrate_n_array_index(sub_id, wls)

            target_T = None

            target_R = None

            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()

            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()

            valid = np.isfinite(n_sub)

            if target_T is not None:
                valid &= np.isfinite(target_T)

            if target_R is not None:
                valid &= np.isfinite(target_R)

            wls = wls[valid]

            n_sub = n_sub[valid]

            if wls.size == 0:
                return None

            return {
                "config": c,
                "wls": wls,
                "n_sub": n_sub,
                "k_sub": getattr(c, "k_sub_data", None),
                "D_sub": getattr(c, "substrate_thickness_nm", None),
            }

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning("TLU live context build failed: %s", e)

            return None

    def _index_tlu_live_payload_from_params(self, params: np.ndarray) -> dict | None:
        """n,k + R,T from TLU vector (7 param.) - aligned with TLUObjective.__call__."""

        ctx = getattr(self, "_index_tlu_live_ctx", None)

        if ctx is None:
            return None

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size != 7:
            return None

        c = ctx["config"]

        wls = ctx["wls"]

        n_sub = ctx["n_sub"]

        thickness = float(p[0])

        Eg, A, E0, C, Eu, eps_inf = (float(p[i]) for i in range(1, 7))

        if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
            return None

        E_arr = HC_EV_NM / wls

        eps2 = epsilon2_TLU_array(E_arr, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(E_arr, Eg, A, E0, C, Eu)

        n_calc, k_calc, is_valid = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        if not is_valid:
            return None

        # Use shared source of truth for R/T calculation

        R_calc, T_calc, T_sub_ref = _compute_RT_from_config(c, wls, n_calc, k_calc, thickness, n_sub)

        # Apply normalization scaling based on user configuration

        if not c.is_frosted_glass and getattr(c, "use_normalized", False):
            with np.errstate(divide="ignore", invalid="ignore"):
                # Safety for T_sub -> 0

                Ts_safe = np.where(T_sub_ref > SMALL_EPSILON, T_sub_ref, 1.0)

                T_plot = np.where(T_sub_ref > SMALL_EPSILON, T_calc / Ts_safe, np.nan)

                T_plot = np.maximum(T_plot, 0.0)

            R_plot = calculate_relative_R_normalization(R_calc, T_sub_ref)

        else:
            T_plot, R_plot = T_calc, R_calc

        _st, _sr = _index_live_spectrum_visibility(c)

        return {
            "wls": wls,
            "n": n_calc,
            "k": k_calc,
            "R_calc": R_plot,
            "T_calc": T_plot,
            "is_frosted_glass": bool(c.is_frosted_glass),
            "live_show_T": _st,
            "live_show_R": _sr,
            "mse": None,
        }

    def _apply_index_live_plot_payload(self, extra_info: dict) -> None:
        """Live plot n,k + spectrum (same logic as Spline pipeline / progress dict)."""

        wls = extra_info["wls"]

        n_c = extra_info["n"]

        k_c = extra_info["k"]

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

        c_n = self.plot_nk.plot(wls, n_c, pen=pg.mkPen(color="#3b82f6", width=3), name="n (Live)")

        self.plot_nk.add_tracked_curve(c_n, "n (Live)")

        if not hasattr(self, "_vb_k") or self._vb_k is None:
            from certus.ui.certus_index_ui_utils import KLogAxisItem
            pi = self.plot_nk.plotItem

            self._vb_k = pg.ViewBox()

            pi.scene().addItem(self._vb_k)

            ax_k = KLogAxisItem("right")

            ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

            pi.layout.addItem(ax_k, 2, 3)

            ax_k.linkToView(self._vb_k)

            self._vb_k.setXLink(pi)

            pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

        else:
            self._vb_k.clear()

        self._vb_k.setLogMode(False, False)

        self._vb_k.setYRange(-6.5, -2.0, padding=0)

        self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        if self.plot_nk.plotItem.vb.sceneBoundingRect().isValid():
            self._vb_k.setGeometry(self.plot_nk.plotItem.vb.sceneBoundingRect())

        k_plot = np.where(
            np.isfinite(k_c) & (k_c >= 1e-8),
            np.log10(np.maximum(k_c, 1e-7)),
            -7.0,
        )

        c_k = pg.PlotCurveItem(
            wls,
            k_plot,
            pen=pg.mkPen(color="#f59e0b", width=3),
            name="log10(k) (Live)",
        )

        self._vb_k.addItem(c_k)

        self.plot_nk.add_tracked_curve(c_k, "log10(k) (Live)")

        if "R_calc" in extra_info or "T_calc" in extra_info:
            show_t = extra_info.get("live_show_T", True)

            show_r = extra_info.get("live_show_R", True)

            Rc = extra_info.get("R_calc")

            Tc = extra_info.get("T_calc")

            for item in list(self.plot_spectrum.plotItem.items):
                item_name = getattr(item, "name", lambda: "")()

                if item_name in [
                    "R (Live)",
                    "T (Live)",
                    "R Fit",
                    "T Fit",
                    "R (Live Spline)",
                    "T (Live Spline)",
                ]:
                    self.plot_spectrum.plotItem.removeItem(item)

            try:
                self.plot_spectrum.remove_curve("R (Live)")

            except Exception:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            try:
                self.plot_spectrum.remove_curve("T (Live)")

            except Exception:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            if show_r and Rc is not None:
                c_r = pg.PlotCurveItem(
                    wls,
                    np.asarray(Rc) * 100,
                    pen=pg.mkPen(color="#ef4444", width=3),
                    name="R (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_r, "R (Live)")

                self.plot_spectrum.plotItem.addItem(c_r)

            if show_t and Tc is not None:
                c_t = pg.PlotCurveItem(
                    wls,
                    np.asarray(Tc) * 100,
                    pen=pg.mkPen(color="#10b981", width=3),
                    name="T (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_t, "T (Live)")

                self.plot_spectrum.plotItem.addItem(c_t)

        try:
            self.plot_spectrum.getPlotItem().vb.autoRange()

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            self.plot_nk.getPlotItem().vb.autoRange()

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.tabs.setCurrentIndex(0)

    def _update_model_text(self, res: OptimizationResults) -> None:

        # Update data table

        try:
            if hasattr(self, "lbl_final_eq"):
                eq_html = "<h2>Final Analytical Optical Model</h2><br>"

                eq_html += f"<b>Optimal Thickness :</b> {res.optimal_thickness:.7f} nm<br><br>"

                eq_html += "<table width='100%'><tr><td valign='top' width='50%'>"

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    eq_html += "<b>Refractive Index (Sellmeier 2-poles + A)</b><br>"

                    eq_html += (
                        "<i>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2)</i> (lambda in m)<br>"
                    )

                    eq_html += "<ul>"

                    eq_html += f"<li><b>A</b> = {sp[0]:.6f}</li>"

                    eq_html += f"<li><b>B1</b> = {sp[1]:.7e}  <b>C1</b> = {sp[2] ** 2:.7e} m2</li>"

                    eq_html += f"<li><b>B2</b> = {sp[3]:.7e}  <b>C2</b> = {sp[4] ** 2:.7e} m2</li>"

                    eq_html += "</ul>"

                eq_html += "</td><td valign='top' width='50%'>"

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    eq_html += "<b>Extinction Coefficient (Generalized Exp + Gaussian 8-params)</b><br>"

                    eq_html += "<i>k(lambda) = 1e-6 + exp(P1lambda + P2) + exp(P3lambda + P4) + P5exp(-| (lambda-P6)/P7 | ^ P8)</i> (lambda in m)<br>"

                    eq_html += "<ul>"

                    eq_html += "<li><b>P1-P4</b> (Exponentials)</li>"

                    eq_html += f"<li><b>P5</b> (Amp) = {kp[4]:.7e}</li>"

                    eq_html += f"<li><b>P6</b> (Center) = {kp[5]:.7e}</li>"

                    eq_html += f"<li><b>P7</b> (Width) = {kp[6]:.7e}</li>"

                    eq_html += f"<li><b>P8 (Beta Shape)</b> = {kp[7]:.4f}</li>"

                    eq_html += "</ul>"

                    if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                        eq_html += f"<br><i>[INDEX.SPLINE] k refined by spline (log k) | phase=2.3 | knots={len(res.k_spline_knots_lambda_um)}</i>"

                eq_html += "</td></tr></table>"

                self.lbl_final_eq.setText(eq_html)

            # Update independent parameters table (16 parameters list)

            try:
                params_rows = []

                # 1. Sellmeier

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    params_rows.extend(
                        [
                            ("A (Constant)", f"{sp[0]:.6f}"),
                            ("B1", f"{sp[1]:.6f}"),
                            ("C1 (m2)", f"{sp[2] ** 2:.6f}"),
                            ("B2", f"{sp[3]:.6f}"),
                            ("C2 (m2)", f"{sp[4] ** 2:.6f}"),
                        ]
                    )

                # 2. k-law (8 params)

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    names = [
                        "P1 (Slope1)",
                        "P2 (Pos1)",
                        "P3 (Slope2)",
                        "P4 (Pos2)",
                        "P5 (Amp)",
                        "P6 (Center)",
                        "P7 (Width)",
                        "P8 (Beta Exponent)",
                    ]

                    for idx, val in enumerate(kp):
                        p_name = names[idx] if idx < len(names) else f"P{idx + 1}"

                        params_rows.append((p_name, f"{val:.6e}"))

                self.table_params.setRowCount(len(params_rows))

                for i, (p_name, p_val) in enumerate(params_rows):
                    item_name = QTableWidgetItem(p_name)

                    item_name.setBackground(pg.mkColor(CertusTheme.SURFACE))

                    self.table_params.setItem(i, 0, item_name)

                    self.table_params.setItem(i, 1, QTableWidgetItem(p_val))

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error updating params table: {e}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error updating model text: {e}", exc_info=True)

        self.btn_copy_nk.setEnabled(True)

        self.btn_copy_params.setEnabled(True)

    def _update_data_table(self, sub_df, res: OptimizationResults) -> None:

        try:
            self.table_res.setRowCount(len(sub_df))

            has_T_tgt = "T_target" in sub_df.columns

            has_R_tgt = "R_target" in sub_df.columns

            src_name_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_colname = f"n_{src_name_base}_{d_val}"

            k_colname = f"k_{src_name_base}_{d_val}"

            if res.config.is_frosted_glass:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

            else:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("T (%)")

                if "n_fit_T_only" in sub_df.columns:
                    cols.extend(["n (T-only)", "k (T-only)"])

                if has_T_tgt:
                    cols.append("T Exp (%)")

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['T_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_T_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_T_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_T_only']:.6f}"))

                        col_idx += 1

                    if has_T_tgt:
                        val_t = row_data["T_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_t:.2f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

                self.table_res.resizeColumnsToContents()
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error updating data table: {e}", exc_info=True)

    def _display_results(self, res: OptimizationResults) -> None:
        """Update UI graphs and table with results"""

        try:
            df = res.df_results

            if df.empty:
                self.logger.error("df_results is empty!")

                return

            # Verify required columns

            required_cols = ["lambda", "n_calc", "k_calc"]

            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                self.logger.error(f"Missing columns in df_results: {missing_cols}")

                self.logger.error(f"Available columns: {list(df.columns)}")

                return

            mask = (df["lambda"] >= res.config.lambda_min) & (df["lambda"] <= res.config.lambda_max)

            sub_df = df[mask]

            if sub_df.empty:
                self.logger.error(
                    f"sub_df is empty after filtering! lambda_min={res.config.lambda_min}, lambda_max={res.config.lambda_max}"
                )

                return

            wls = sub_df["lambda"].values

            if len(wls) == 0:
                self.logger.error("wls is empty!")

                return

            self._update_spectrum_plot(wls, sub_df, res)

            self._update_nk_plot(wls, sub_df, res)

            self._update_model_text(res)

            self._update_data_table(sub_df, res)

            self.tabs.setCurrentIndex(0)

            try:
                self.plot_spectrum.getPlotItem().vb.autoRange()

                self.plot_nk.getPlotItem().vb.autoRange()

            except NUMERICAL_FAULT_EXCEPTIONS :
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] display failed | component=results | reason=%s", e, exc_info=True)

            self.logger.error(traceback.format_exc())

            _notify_user(
                self,
                "Display Error",
                f"Error displaying results: {e}\n\nCheck logs for details.",
                level="warning",
            )

    def _copy_nk_to_clipboard(self) -> None:
        """Copy the full n,k table (lambda, n, k, ) to the clipboard as tab-separated text."""

        if self.latest_results is None or self.latest_results.df_results is None:
            _notify_user(self, "No Data", "No results available to copy.", level="warning")

            return

        df = self.latest_results.df_results

        required = ["lambda", "n_calc", "k_calc"]

        if not all(c in df.columns for c in required):
            _notify_user(self, "No Data", "Result table does not contain n,k data.", level="warning")

            return

        try:
            res = self.latest_results

            src_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_col = f"n_{src_base}_{d_val}"

            k_col = f"k_{src_base}_{d_val}"

            header = f"lambda (nm)\t{n_col}\t{k_col}"

            if "delta_n" in df.columns:
                header += "\tdelta_n\tdelta_k"

            if "n_fit_T_only" in df.columns:
                header += "\tn (T-only)\tk (T-only)"

            if "n_fit_R_only" in df.columns:
                header += "\tn (R-only)\tk (R-only)"

            lines = [header]

            for _, row in df.iterrows():
                row_str = f"{row['lambda']:.1f}\t{row['n_calc']:.6f}\t{row['k_calc']:.9f}"

                if "delta_n" in df.columns:
                    row_str += f"\t{row['delta_n']:.6f}\t{row['delta_k']:.9f}"

                if "n_fit_T_only" in df.columns:
                    row_str += f"\t{row['n_fit_T_only']:.6f}\t{row['k_fit_T_only']:.9f}"

                if "n_fit_R_only" in df.columns:
                    row_str += f"\t{row['n_fit_R_only']:.6f}\t{row['k_fit_R_only']:.9f}"

                lines.append(row_str)

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("n,k table copied!")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] copy failed | reason=%s", e)

    def _copy_params_to_clipboard(self) -> None:
        """Copy the 16 global model parameters to the clipboard."""

        if self.table_params.rowCount() == 0:
            _notify_user(self, "No Data", "No parameters available to copy.", level="warning")

            return

        try:
            lines = ["Parameter\tValue"]

            for i in range(self.table_params.rowCount()):
                p = self.table_params.item(i, 0).text()

                v = self.table_params.item(i, 1).text()

                lines.append(f"{p}\t{v}")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("Model parameters copied!")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Copy error: {e}")

    def _copy_eq_to_clipboard(self) -> None:
        """Copy the final analytical equations to the clipboard as text."""

        if self.latest_results is None:
            _notify_user(self, "No Data", "No results available to copy.", level="warning")

            return

        try:
            res = self.latest_results

            lines = ["Final Analytical Optical Model", "=" * 40]

            lines.append(f"Optimal Thickness : {res.optimal_thickness:.7f} nm\n")

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                lines.append("Refractive Index (Sellmeier 2-poles + A)")

                lines.append("n^2 = A + (B1*L^2)/(L^2 - C1) + (B2*L^2)/(L^2 - C2)  with L in m")

                lines.append(f"A = {sp[0]:.6f}")

                lines.append(f"B1 = {sp[1]:.7e}")

                lines.append(f"C1 = {sp[2] ** 2:.7e} m^2")

                lines.append(f"B2 = {sp[3]:.7e}")

                lines.append(f"C2 = {sp[4] ** 2:.7e} m^2\n")

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                lines.append("Extinction Coefficient (Generalized Exp + Super-Gauss 8-params)")

                lines.append("k(L) = 1e-6 + exp(P1*L + P2) + exp(P3*L + P4) + P5*exp(-abs((L-P6)/P7)^P8)  with L in m")

                for idx, val in enumerate(kp):
                    lines.append(f"P{idx + 1} = {val:.7e}")

                if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                    lines.append("[INDEX.SPLINE] k refined by spline (log k) | phase=2.3")

                    lines.append(f"Knots (m): {res.k_spline_knots_lambda_um.tolist()}")

                    lines.append(f"k at knots: {res.k_spline_knots_values.tolist()}")

                lines.append("")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText(" Equations copied to clipboard")

            self.logger.info("[INDEX.UI] equations copied to clipboard")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Copy equations failed: {e}", exc_info=True)
            _notify_user(self, "Copy Error", str(e), level="error")

    def _build_uncertainty_content(self, df: pd.DataFrame) -> dict[str, str]:
        """Build uncertainty metrics for HTML export from available delta columns."""

        uncertainty_content: dict[str, str] = {}

        if "delta_n_res" in df.columns:
            dn = df["delta_n_res"].values

            uncertainty_content["Deltan Max (3-way)"] = f"{np.max(dn):.4f}"

            uncertainty_content["Deltan Mean (3-way)"] = f"{np.mean(dn):.4f}"

            uncertainty_content["Deltan Min (3-way)"] = f"{np.min(dn[dn > 0]):.4f}" if np.any(dn > 0) else "0.0000"

        if "delta_k_res" in df.columns:
            dk = df["delta_k_res"].values

            uncertainty_content["Deltak Max (3-way)"] = f"{np.max(dk):.4f}"

            uncertainty_content["Deltak Mean (3-way)"] = f"{np.mean(dk):.4f}"

        if "delta_n" in df.columns and "delta_k" in df.columns:
            uncertainty_content["Deltan Max (50-50 vs 90% T)"] = f"{np.max(df['delta_n'].values):.4f}"

            uncertainty_content["Deltan Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_n'].values):.4f}"

            uncertainty_content["Deltak Max (50-50 vs 90% T)"] = f"{np.max(df['delta_k'].values):.4f}"

            uncertainty_content["Deltak Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_k'].values):.4f}"

        if not uncertainty_content:
            uncertainty_content["Status"] = "Not calculated"

        return uncertainty_content

    def _export_results_html(self, res: OptimizationResults, rmse_val: float, html_path: str) -> None:
        """Export INDEX HTML report; logs errors internally to preserve legacy flow."""

        try:
            # Prepare Dispersion Table

            if res.tlu_params:
                disp_data = [
                    {
                        "Parameter": "Eg",
                        "Value": f"{res.tlu_params.Eg:.4f}",
                        "Unit": "eV",
                    },
                    {
                        "Parameter": "eps_inf",
                        "Value": f"{res.tlu_params.eps_inf:.4f}",
                        "Unit": "-",
                    },
                    {"Parameter": "A", "Value": f"{res.tlu_params.A:.4f}", "Unit": "-"},
                    {"Parameter": "C", "Value": f"{res.tlu_params.C:.4f}", "Unit": "-"},
                    {
                        "Parameter": "E0",
                        "Value": f"{res.tlu_params.E0:.4f}",
                        "Unit": "eV",
                    },
                ]

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                disp_data = [
                    {
                        "Parameter": "Mode",
                        "Value": "IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement",
                        "Unit": "-",
                    },
                    {"Parameter": "Thickness (nm)", "Value": f"{res.optimal_thickness:.4f}", "Unit": "nm"},
                ]

                if not is_phase2_ir:
                    disp_data.append(
                        {
                            "Parameter": "Knots",
                            "Value": f"{res.optimization_stats.get('num_knots', 'N/A')}",
                            "Unit": "-",
                        }
                    )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                disp_data.extend(
                    [
                        {"Parameter": "Sellmeier A (Const)", "Value": f"{sp[0]:.6f}", "Unit": "-"},
                        {"Parameter": "Sellmeier B1", "Value": f"{sp[1]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C1", "Value": f"{sp[2] ** 2:.8e}", "Unit": "m2"},
                        {"Parameter": "Sellmeier B2", "Value": f"{sp[3]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C2", "Value": f"{sp[4] ** 2:.8e}", "Unit": "m2"},
                    ]
                )

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    disp_data.append({"Parameter": name, "Value": f"{val:.8e}", "Unit": "-"})

            # Uncertainty statistics from delta_n_res/delta_k_res (3-way) or delta_n/delta_k (50-50 vs 90% T)
            uncertainty_content = self._build_uncertainty_content(res.df_results)

            sections = [
                {
                    "title": "Optimization Methodology",
                    "type": "kv",
                    "content": {
                        "Algorithm": "Hybrid (PGlobal + L-BFGS-B)",
                        "Gradient Mode": "Analytic (Exact Derivatives)",
                        "Speedup": "~200x vs Finite Difference",
                        "Precision": "Machine Precision (Float64)",
                        "Convergence": "High (Jacobian-Assisted)",
                    },
                },
                {
                    "title": "Algorithm Details",
                    "type": "text",
                    "content": (
                        "The optimization employs a robust three-stage strategy: "
                        "1. <strong>PGlobal (Global Search)</strong>: Uses a stochastic differential evolution approach to find the global minimum region. "
                        "2. <strong>L-BFGS-B (Local Polish)</strong>: Uses the <strong>Analytic Gradient</strong> to refine the solution with high precision. "
                        "3. <strong>Coordinate Descent (Fine Tuning)</strong>: A final local descent step to escape narrow local minima. "
                        "4. <strong>Physical Accuracy</strong>: Rigorously accounts for <strong>Incoherent Backside Reflection</strong> in the substrate for both Transmission and Reflection (T = T_single * T_back / (1 - R_single*R_back)). "
                        "The analytic gradient computes the exact derivatives of the Tauc-Lorentz-Urbach model and Transfer Matrix Method interactions (including backside effects) using the chain rule, "
                        "eliminating numerical noise and providing significant performance improvements over traditional finite-difference methods."
                    ),
                },
                {
                    "title": "Optimization Summary",
                    "type": "kv",
                    "content": {
                        "Date": certus_timestamp_display(),
                        "Source File": Path(res.config.source_file).name,
                        "Final RMSE": f"{rmse_val:.6f}",
                        "Execution Time": f"{res.execution_time:.2f} s",
                        "Model": "IR Global Model (Sellmeier + k 8p)"
                        if (
                            res.tlu_params is None
                            and (
                                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
                            )
                        )
                        else "Tauc-Lorentz-Urbach",
                        "substrate": res.config.substrate,
                    },
                },
                {
                    "title": "Dispersion Parameters",
                    "type": "table",
                    "content": disp_data,
                },
                {
                    "title": "Uncertainty Analysis",
                    "type": "kv",
                    "content": uncertainty_content,
                },
            ]

            # --- 3. Add Beam Analysis Section (if available) ---

            if hasattr(self, "last_beam_results") and self.last_beam_results:
                beam_table = []

                # Sort by MSE

                sorted_beam = sorted(self.last_beam_results, key=lambda x: x["mse"])

                # Take top 20 or all

                for b in sorted_beam[:20]:
                    beam_table.append(
                        {
                            "Thickness (nm)": f"{b['d']:.2f}",
                            "MSE": f"{b['mse']:.2e}",
                            "Status": "Best" if b == sorted_beam[0] else "",
                        }
                    )

                sections.append(
                    {
                        "title": "Beam Analysis (Thickness Scan)",
                        "type": "table",
                        "content": beam_table,
                    }
                )

                # Add explainer

                sections.append(
                    {
                        "title": "Beam Analysis Details",
                        "type": "text",
                        "content": (
                            f"Beam Analysis scanned <strong>{len(self.last_beam_results)}</strong> thickness values. "
                            "The table above shows the best solutions found. "
                            "This technique validates the global minimum by ensuring no better solution exists at other thicknesses."
                        ),
                    }
                )

            # --- 4. Add Physical Model Section ---

            _is_phase2_ir = res.tlu_params is None and (
                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
            )

            if _is_phase2_ir:
                sections.append(
                    {
                        "title": "Physical Model: Sellmeier 2-pole + k 8-parameter",
                        "type": "kv",
                        "content": {
                            "n(lambda)": "Sellmeier 2-pole: n2 = A + B₁lambda2/(lambda2-L₁2) + B₂lambda2/(lambda2-L₂2)",
                            "k(lambda)": "Empirical: exponentials + super-Gaussian peak (soft-saturated)",
                            "Range": "Full spectrum (Phase 2/2 IR Global Model)",
                        },
                    }
                )

            else:
                sections.append(
                    {
                        "title": "Physical Model: Tauc-Lorentz-Urbach",
                        "type": "kv",
                        "content": {
                            "Formula": "2(E) = AE0C(E-Eg)2 / [(E2-E02)2 + C2E2]  (1/E)",
                            "Urbach Tail": "Exponential tail below Eg (extends absorption)",
                            "Eg": "Band Gap Energy (eV)",
                            "eps_inf": "High-frequency dielectric constant",
                            "A": "Amplitude (Strength of oscillator)",
                            "E0": "Peak Energy (eV)",
                            "C": "Broadening (eV)",
                        },
                    }
                )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                _method = (res.optimization_stats or {}).get("method", "")

                _skip_phase5 = "PGLOBAL" in _method or "Sellmeier+k" in _method

                if not _skip_phase5:
                    sections.append(
                        {
                            "title": "Phase 5: Sellmeier Smooth Fit (n)",
                            "type": "text",
                            "content": (
                                "At the end of the optimization, <strong>n</strong> is strictly fitted to a 3-pole <strong>Sellmeier Law</strong> over the entire spectrum "
                                "to guarantee perfectly smooth and physical values: <br/>"
                                "<code>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2) + (B3lambda2) / (lambda2 - C3)</code><br/>"
                                "The extinction coefficient <strong>k</strong> is then re-optimized point-by-point to perfectly match experimental (R,T) targets with the fixed Sellmeier <strong>n</strong>."
                            ),
                        }
                    )

            figures = [self.plot_spectrum, self.plot_nk]

            if hasattr(self, "plot_delta_n"):
                figures.append(self.plot_delta_n)

            if generate_html_report(html_path, "CERTUS-INDEX Report", sections, figures):
                self.logger.info("[INDEX.EXPORT] html saved | path=%s", html_path)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.EXPORT] html export failed | reason=%s", e, exc_info=True)

    def export_results(self) -> None:
        """Standardized Auto-Export (Excel + HTML).

        The export naming must reflect the final fit error used by the report,
        while the material/substrate semantics remain confined to the model and
        config fields.
        """

        if not get_export_config():
            return

        if not self.latest_results:
            return

        res = self.latest_results

        # Final fit error used for report naming and summaries.
        rmse_val = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Generate filenames for the standardized report bundle.

        try:
            reports_dir = get_resource_path("reports")

            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            try:
                src_name = Path(res.config.source_file).stem

                base_filename = f"Report_INDEX_{src_name}_{ts}_RMSE_{rmse_val:.5f}"

            except NUMERICAL_FAULT_EXCEPTIONS:
                base_filename = f"Report_INDEX_{ts}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(reports_dir) / (base_filename + ".xlsx"))

            html_path = str(Path(reports_dir) / (base_filename + ".html"))

            self.lbl_status.setText("Saving Reports...")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Filename generation error: {e}")

            return

        # --- 1. EXCEL EXPORT ---

        try:
            tlu = res.tlu_params

            if tlu:
                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Eg": [f"{tlu.Eg:.4f}"],
                    "eps_inf": [f"{tlu.eps_inf:.4f}"],
                    "A": [f"{tlu.A:.4f}"],
                    "C": [f"{tlu.C:.4f}"],
                    "E0": [f"{tlu.E0:.4f}"],
                }

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Mode": ["IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement"],
                    "Thickness (nm)": [f"{res.optimal_thickness:.4f}"],
                    "Thickness Variation (%)": [f"{getattr(res, 'thickness_variation', 0):+.2f}"],
                }

                if not is_phase2_ir:
                    summary_data["Knots"] = [getattr(res, "num_knots", "N/A")]

            summary_data["Substrate (material)"] = [res.config.substrate]

            if res.config.substrate == "Sapphire (Al2O3)":
                summary_data["Sapphire n(lambda) source"] = ["Sellmeier equation (materials_v1.json, id=3)"]

                summary_data["Sapphire k column in file"] = ["yes" if _SAPPHIRE_FILE_HAS_K_COLUMN else "no"]

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                summary_data["Sellmeier_A"] = [f"{sp[0]:.6f}"]

                summary_data["Sellmeier_B1"] = [f"{sp[1]:.8e}"]

                summary_data["Sellmeier_C1"] = [f"{sp[2] ** 2:.8e}"]

                summary_data["Sellmeier_B2"] = [f"{sp[3]:.8e}"]

                summary_data["Sellmeier_C2"] = [f"{sp[4] ** 2:.8e}"]

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    summary_data[name] = [f"{val:.8e}"]

            df_summary = pd.DataFrame(summary_data)

            df_data = res.df_results.copy()

            from certus.utils.certus_data import ReportSection, build_standard_report

            try:
                if bool(getattr(res.config, "use_normalized", False)):
                    self.set_validation_status("WARNING_DATA_NORMALIZED")
                    self.add_validation_warning("Input data normalized before optimization/export.")
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("INDEX validation status update skipped during export: %s", exc)

            run_manifest = None
            try:
                run_manifest = (res.optimization_stats or {}).get("run_manifest")
            except (TypeError, AttributeError):
                run_manifest = None

            report_result = build_standard_report(
                [
                    ReportSection("Summary", kind="table", content=df_summary, sheet_name="Summary"),
                    ReportSection("Data", kind="table", content=df_data, sheet_name="Data"),
                ],
                excel_path=excel_path,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )
            if report_result.get("excel"):
                self.logger.info("[INDEX.EXPORT] excel saved | path=%s", excel_path)
            else:
                self.logger.error("Excel export blocked/failed: missing or incomplete run manifest.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.EXPORT] excel export failed | reason=%s", e, exc_info=True)

        # --- 2. HTML EXPORT ---
        self._export_results_html(res, rmse_val, html_path)

        self.lbl_status.setText(f" Saved: {base_filename}")

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        copy_app_logs_to_clipboard(self)

        self.lbl_status.setText("Logs copied to clipboard!")

