import os
import sys
from pathlib import Path
import logging
import traceback
from certus.ui.certus_index_ui import (
    _prepare_nk_plot_inputs,
    KLogAxisItem,
)
import time
import functools
from datetime import datetime
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
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

class CertusIndexPlotMixin:
    def _plot_raw_and_smoothed_preview(
        self,
        *,
        wls: np.ndarray,
        raw_data: pd.DataFrame,
        smoothed_data: pd.DataFrame,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Draw temporary raw+smoothed overlay before user selection."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()

        if preview_t and "T" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["T"].values * 100,
                pen=pg.mkPen(color=(40, 167, 69, 100), width=1),
                symbol="o",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(40, 167, 69, 100)),
                name="T data (Raw)",
            )
        if preview_r and "R" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["R"].values * 100,
                pen=pg.mkPen(color=(220, 53, 69, 100), width=1),
                symbol="s",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(220, 53, 69, 100)),
                name="R data (Raw)",
            )
        if preview_t and "T" in smoothed_data.columns:
            c_t_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["T"].values * 100,
                pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                name="T data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_t_sm, "T")
        if preview_r and "R" in smoothed_data.columns:
            c_r_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["R"].values * 100,
                pen=pg.mkPen(CertusTheme.DANGER, width=3),
                name="R data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_r_sm, "R")

    def _redraw_target_preview(self, wls: np.ndarray, preview_t: bool, preview_r: bool) -> None:
        """Redraw target traces from current `self.target_data`."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()
        if preview_t and "T" in self.target_data.columns:
            c_t = self.plot_spectrum.plot(
                wls,
                self.target_data["T"].values * 100,
                pen=None,
                symbol="o",
                symbolSize=3,
                symbolBrush=CertusTheme.SUCCESS,
                name="T data",
            )
            self._try_add_spectrum_tracked_curve(c_t, "T")
        if preview_r and "R" in self.target_data.columns:
            c_r = self.plot_spectrum.plot(
                wls,
                self.target_data["R"].values * 100,
                pen=None,
                symbol="s",
                symbolSize=3,
                symbolBrush=CertusTheme.DANGER,
                name="R data",
            )
            self._try_add_spectrum_tracked_curve(c_r, "R")

    def _try_add_spectrum_tracked_curve(self, curve, key: str) -> None:
        """Best-effort tracked-curve registration for spectrum traces."""
        try:
            self.plot_spectrum.add_tracked_curve(curve, key, "%")
        except NUMERICAL_FAULT_EXCEPTIONS:
            self.logger.debug("[INDEX.UI] tracked-curve registration skipped in %s", __name__, exc_info=True)

    def _clear_plot_tracking_state(self) -> None:
        """Best-effort cleanup of internal plot tracking structures."""
        try:
            self.plot_spectrum._tracked_curves = []
            self.plot_spectrum.curve_points = {}
        except NUMERICAL_FAULT_EXCEPTIONS:
            self.logger.debug("[INDEX.UI] plot tracking state reset skipped in %s", __name__, exc_info=True)

    def _update_spectrum_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the T/R spectrum plot (data + fit)."""

        self.plot_spectrum.clear()

        self.plot_spectrum.clear_tracking()

        self._update_plot_exclusion()

        try:
            from certus.ui.certus_index_ui import _set_spectrum_plot_title
            _set_spectrum_plot_title(self.plot_spectrum, res.config.source_file)

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # Display target data

        if "T_target" in sub_df.columns and not res.config.is_frosted_glass:
            try:
                c_tgt_t = self.plot_spectrum.plot(
                    wls,
                    sub_df["T_target"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=4,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_t, "T Target", "%")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error("[INDEX.UI] display failed | component=T_target | reason=%s", e, exc_info=True)

        if "R_target" in sub_df.columns:
            try:
                c_tgt_r = self.plot_spectrum.plot(
                    wls,
                    sub_df["R_target"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=4,
                    symbolBrush=CertusTheme.DANGER,
                    name="R Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_r, "R Target", "%")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error("[INDEX.UI] display failed | component=R_target | reason=%s", e, exc_info=True)

        # Display fits

        use_normalized = res.config.use_normalized

        # Transmission (not for frosted glass)

        if not res.config.is_frosted_glass and res.config.data_type in (
            DataType.TRANSMISSION,
            DataType.BOTH,
        ):
            col_T = "T_norm_calc (%)" if use_normalized else "T_calc (%)"

            if col_T in sub_df.columns:
                try:
                    c_fit_t = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_T].values,
                        pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                        name="T Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_t, "T Fit", "%")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.error(f"Error displaying T fit: {e}", exc_info=True)

        # Reflection

        if res.config.data_type in (DataType.REFLECTION, DataType.BOTH) or res.config.is_frosted_glass:
            col_R = "R_norm_calc (%)" if use_normalized else "R_calc (%)"

            if col_R in sub_df.columns:
                try:
                    c_fit_r = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_R].values,
                        pen=pg.mkPen(CertusTheme.DANGER, width=3),
                        name="R Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_r, "R Fit", "%")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.error(f"Error displaying R fit: {e}", exc_info=True)

    def _update_nk_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the n & k plot (left axis n, right axis log k)."""

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        try:
            src_name = Path(res.config.source_file).stem

            title_text = f"Optical Constants      {src_name}      thickness = {res.optimal_thickness:.2f} nm"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title_text = f"Optical Constants      thickness = {res.optimal_thickness:.2f} nm"

        self.plot_nk.plotItem.setTitle(title_text)

        prepared = _prepare_nk_plot_inputs(wls, sub_df, res, self.logger)
        if prepared is None:
            return
        n_values, k_values, method_str, lambda_max_fit, tlu_mode = prepared

        try:
            # k curve refs for legend

            c_k_main = None

            c_kt = None

            c_kr = None

            # --- Primary axis (left): n ---

            # Label left axis explicitly

            self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

            if "n_calc_005" in sub_df.columns:
                n1 = sub_df["n_calc_005"].values.copy()

                n2 = sub_df["n_calc_0025"].values.copy()

                n3 = sub_df["n_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    n1[ir_mask_ui] = np.nan

                    n2[ir_mask_ui] = np.nan

                    n3[ir_mask_ui] = np.nan

                self.plot_nk.plot(wls, n1, pen=pg.mkPen(color="#93c5fd", width=2), name="n (tol=0.005)")

                self.plot_nk.plot(wls, n2, pen=pg.mkPen(color="#3b82f6", width=2), name="n (tol=0.0025)")

                c_n3 = self.plot_nk.plot(wls, n3, pen=pg.mkPen(color="#1e3a8a", width=3), name="n (tol=0.001)")

                self.plot_nk.add_tracked_curve(c_n3, "n")

                self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            else:
                c_n = self.plot_nk.plot(wls, n_values, pen=pg.mkPen(CertusTheme.PRIMARY, width=3), name="n (R+T)")

                self.plot_nk.add_tracked_curve(c_n, "n (R+T)")

                if "n_center" in sub_df.columns and "n_hi" in sub_df.columns and "n_lo" in sub_df.columns:
                    n_cen = sub_df["n_center"].values.copy()

                    if tlu_mode:
                        n_cen[ir_mask_ui] = np.nan

                    c_nc = self.plot_nk.plot(
                        wls,
                        n_cen,
                        pen=pg.mkPen(color=CertusTheme.SUCCESS, width=2, style=Qt.PenStyle.DashLine),
                        name="n (center)",
                    )

                    self.plot_nk.add_tracked_curve(c_nc, "n (center)")

                    n_err_center = sub_df["n_raw"].values if "n_raw" in sub_df.columns else n_values

                    top_n = sub_df["n_hi"].values - n_err_center

                    bot_n = n_err_center - sub_df["n_lo"].values

                    top_n = np.where(np.isfinite(top_n), top_n, 0)

                    bot_n = np.where(np.isfinite(bot_n), bot_n, 0)

                    if "n_hi_2" in sub_df.columns and "n_lo_2" in sub_df.columns:
                        top_n2 = sub_df["n_hi_2"].values - n_err_center

                        bot_n2 = n_err_center - sub_df["n_lo_2"].values

                        top_n2 = np.where(np.isfinite(top_n2), top_n2, 0)

                        bot_n2 = np.where(np.isfinite(bot_n2), bot_n2, 0)

                        err_n2 = pg.ErrorBarItem(
                            x=wls,
                            y=n_err_center,
                            top=top_n2,
                            bottom=bot_n2,
                            beam=0.5,
                            pen=pg.mkPen(color=(30, 136, 229, 80), width=3),
                        )

                        self.plot_nk.plotItem.addItem(err_n2)

                    err_n = pg.ErrorBarItem(
                        x=wls,
                        y=n_err_center,
                        top=top_n,
                        bottom=bot_n,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.PRIMARY, width=1),
                    )

                    self.plot_nk.plotItem.addItem(err_n)

                    if "n_raw" in sub_df.columns:
                        # Plot the raw bisection cloud as a translucent scattered layer underneath the clean Line

                        c_raw = self.plot_nk.plot(
                            wls,
                            n_err_center,
                            pen=pg.mkPen(color=(30, 136, 229, 120), width=1, style=Qt.PenStyle.DotLine),
                            name="n (Raw point-by-point)",
                        )

                        self.plot_nk.add_tracked_curve(c_raw, "n (Raw)")

                # --- EXTRA FITS: Visualization ---

                if "n_fit_T_only" in sub_df.columns:
                    c_nt = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_T_only"].values,
                        pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% T)",
                    )

                    self.plot_nk.add_tracked_curve(c_nt, "n (90% T)")

                if "n_fit_R_only" in sub_df.columns:
                    c_nr = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_R_only"].values,
                        pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% R)",
                    )

                    self.plot_nk.add_tracked_curve(c_nr, "n (90% R)")

            # Legend n (left axis)

            self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            # --- Secondary axis (right, log scale): k ---

            pi = self.plot_nk.plotItem

            # Create or reuse secondary ViewBox

            if not hasattr(self, "_vb_k") or self._vb_k is None:
                self._vb_k = pg.ViewBox()

                pi.scene().addItem(self._vb_k)

                ax_k = KLogAxisItem("right")

                ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

                pi.layout.addItem(ax_k, 2, 3)

                ax_k.linkToView(self._vb_k)

                self._vb_k.setXLink(pi)

                self._ax_k = ax_k

                # Geometry sync on resize (connected once only)

                pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

            else:
                self._vb_k.clear()

            # Do NOT use pyqtgraph's internal setLogMode, it silently drops curves if any single point causes a math domain error during rendering.

            # Instead, we will feed it raw log10() values into a linear ViewBox.

            self._vb_k.setLogMode(False, False)

            self._vb_k.setYRange(-6.5, -2.0, padding=0)

            self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

            self._vb_k.setGeometry(pi.vb.sceneBoundingRect())

            # Plot k  use a tiny floor so k0 regions (VIS) stay connected on log scale

            # pyqtgraph's ViewBox with setLogMode(Y=True) applies log10 internally,

            # so we must NOT pass NaN for k=0; instead we floor at 1e-7.

            if "k_calc_005" in sub_df.columns:
                k1 = sub_df["k_calc_005"].values.copy()

                k2 = sub_df["k_calc_0025"].values.copy()

                k3 = sub_df["k_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    k1[ir_mask_ui] = np.nan

                    k2[ir_mask_ui] = np.nan

                    k3[ir_mask_ui] = np.nan

                k1_p = np.where(np.isfinite(k1) & (k1 >= 1e-8), np.log10(np.maximum(k1, 1e-7)), -7.0)

                k2_p = np.where(np.isfinite(k2) & (k2 >= 1e-8), np.log10(np.maximum(k2, 1e-7)), -7.0)

                k3_p = np.where(np.isfinite(k3) & (k3 >= 1e-8), np.log10(np.maximum(k3, 1e-7)), -7.0)

                c_k1 = pg.PlotCurveItem(wls, k1_p, pen=pg.mkPen(color="#fcd34d", width=2), name="log10(k) (tol=0.005)")

                c_k2 = pg.PlotCurveItem(wls, k2_p, pen=pg.mkPen(color="#f59e0b", width=2), name="log10(k) (tol=0.0025)")

                c_k3 = pg.PlotCurveItem(wls, k3_p, pen=pg.mkPen(color="#b45309", width=3), name="log10(k) (tol=0.001)")

                self._vb_k.addItem(c_k1)

                self._vb_k.addItem(c_k2)

                self._vb_k.addItem(c_k3)

                self.plot_nk.add_tracked_curve(c_k3, "log10(k)")

            else:
                k_plot = np.where(
                    np.isfinite(k_values) & (k_values >= 1e-8), np.log10(np.maximum(k_values, 1e-7)), -7.0
                )

                c_k = pg.PlotCurveItem(wls, k_plot, pen=pg.mkPen(CertusTheme.WARNING, width=3), name="k (R+T)")

                self._vb_k.addItem(c_k)

                self.plot_nk.add_tracked_curve(c_k, "log10(k)")

                c_k_main = c_k

                if "k_center" in sub_df.columns and "k_hi" in sub_df.columns and "k_lo" in sub_df.columns:
                    kc = sub_df["k_center"].values.copy()

                    if tlu_mode:
                        kc[ir_mask_ui] = np.nan

                    kc_plot = np.where(np.isfinite(kc) & (kc >= 0), np.maximum(kc, 1e-7), np.nan)

                    c_kc = pg.PlotCurveItem(
                        wls,
                        kc_plot,
                        pen=pg.mkPen(color=CertusTheme.WARNING, width=2, style=Qt.PenStyle.DashLine),
                        name="k (center)",
                    )

                    self._vb_k.addItem(c_kc)

                    self.plot_nk.add_tracked_curve(c_kc, "log10(k) (center)")

                    k_err_center = sub_df["k_raw"].values if "k_raw" in sub_df.columns else k_plot

                    k_err_center_plot = np.where(
                        np.isfinite(k_err_center) & (k_err_center >= 0), np.maximum(k_err_center, 1e-7), np.nan
                    )

                    top_k = sub_df["k_hi"].values - k_err_center_plot

                    bot_k = k_err_center_plot - sub_df["k_lo"].values

                    top_k = np.where(np.isfinite(top_k), top_k, 0)

                    bot_k = np.where(np.isfinite(bot_k), bot_k, 0)

                    if "k_hi_2" in sub_df.columns and "k_lo_2" in sub_df.columns:
                        top_k2 = sub_df["k_hi_2"].values - k_err_center_plot

                        bot_k2 = k_err_center_plot - sub_df["k_lo_2"].values

                        top_k2 = np.where(np.isfinite(top_k2), top_k2, 0)

                        bot_k2 = np.where(np.isfinite(bot_k2), bot_k2, 0)

                        err_k2 = pg.ErrorBarItem(
                            x=wls,
                            y=k_err_center_plot,
                            top=top_k2,
                            bottom=bot_k2,
                            beam=0.5,
                            pen=pg.mkPen(color=(255, 179, 0, 80), width=3),
                        )

                        self._vb_k.addItem(err_k2)

                    err_k = pg.ErrorBarItem(
                        x=wls,
                        y=k_err_center_plot,
                        top=top_k,
                        bottom=bot_k,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.WARNING, width=1),
                    )

                    self._vb_k.addItem(err_k)

            # --- EXTRA FITS: k Visualization ---

            if "k_fit_T_only" in sub_df.columns:
                kt = sub_df["k_fit_T_only"].values

                kt_p = np.where(np.isfinite(kt) & (kt >= 1e-8), np.log10(np.maximum(kt, 1e-7)), -7.0)

                c_kt = pg.PlotCurveItem(
                    wls, kt_p, pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine), name="k (90% T)"
                )

                self._vb_k.addItem(c_kt)

                self.plot_nk.add_tracked_curve(c_kt, "log10(k) (90% T)")

            if "k_fit_R_only" in sub_df.columns:
                kr = sub_df["k_fit_R_only"].values

                kr_p = np.where(np.isfinite(kr) & (kr >= 1e-8), np.log10(np.maximum(kr, 1e-7)), -7.0)

                c_kr = pg.PlotCurveItem(
                    wls, kr_p, pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine), name="k (90% R)"
                )

                self._vb_k.addItem(c_kr)

                self.plot_nk.add_tracked_curve(c_kr, "log10(k) (90% R)")

            if "k_raw" in sub_df.columns:
                c_k_raw = pg.PlotCurveItem(
                    wls,
                    k_err_center_plot,
                    pen=pg.mkPen(color=(255, 179, 0, 120), width=1, style=Qt.PenStyle.DotLine),
                    name="k (Raw point-by-point)",
                )

                self._vb_k.addItem(c_k_raw)

                self.plot_nk.add_tracked_curve(c_k_raw, "log10(k) (Raw)")

            # Legend k (right axis)

            if c_k_main is not None or c_kt is not None or c_kr is not None:
                leg_k = pg.LegendItem(offset=(10, 120), labelTextSize="9pt")

                leg_k.setParentItem(self.plot_nk.plotItem)

                if c_k_main is not None:
                    leg_k.addItem(c_k_main, "k (R+T)")

                if c_kt is not None:
                    leg_k.addItem(c_kt, "k (90% T)")

                if c_kr is not None:
                    leg_k.addItem(c_kr, "k (90% R)")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] display failed | component=nk | reason=%s", e, exc_info=True)

            self.logger.error(traceback.format_exc())

