import logging
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import Qt

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
)
from certus.core.certus_index_core import (
    OptimizationResults,
)
from certus.ui.certus_index_ui_utils import (
    KLogAxisItem,
    _prepare_nk_plot_inputs,
)
from certus.ui.certus_ui import (
    CertusTheme,
)
from certus.utils.certus_index_utils import DataType


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
            from certus.ui.certus_index_ui_utils import _set_spectrum_plot_title
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
        n_values, k_values, *_ = prepared

        try:
            # k curve refs for legend

            c_kt = None

            # --- Primary axis (left): n ---

            # Label left axis explicitly

            self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

            c_n = self.plot_nk.plot(wls, n_values, pen=pg.mkPen(CertusTheme.PRIMARY, width=3), name="n (R+T)")

            self.plot_nk.add_tracked_curve(c_n, "n (R+T)")

            # --- EXTRA FITS: Visualization ---

            if "n_fit_T_only" in sub_df.columns:
                c_nt = self.plot_nk.plot(
                    wls,
                    sub_df["n_fit_T_only"].values,
                    pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine),
                    name="n (90% T)",
                )

                self.plot_nk.add_tracked_curve(c_nt, "n (90% T)")

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

            k_plot = np.where(
                np.isfinite(k_values) & (k_values >= 1e-8), np.log10(np.maximum(k_values, 1e-7)), -7.0
            )

            c_k = pg.PlotCurveItem(wls, k_plot, pen=pg.mkPen(CertusTheme.WARNING, width=3), name="k (R+T)")

            self._vb_k.addItem(c_k)

            self.plot_nk.add_tracked_curve(c_k, "log10(k)")

            c_k_main = c_k

            # --- EXTRA FITS: k Visualization ---

            if "k_fit_T_only" in sub_df.columns:
                kt = sub_df["k_fit_T_only"].values

                kt_p = np.where(np.isfinite(kt) & (kt >= 1e-8), np.log10(np.maximum(kt, 1e-7)), -7.0)

                c_kt = pg.PlotCurveItem(
                    wls, kt_p, pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine), name="k (90% T)"
                )

                self._vb_k.addItem(c_kt)

                self.plot_nk.add_tracked_curve(c_kt, "log10(k) (90% T)")

            # Legend k (right axis)

            leg_k = pg.LegendItem(offset=(10, 120), labelTextSize="9pt")

            leg_k.setParentItem(self.plot_nk.plotItem)

            leg_k.addItem(c_k_main, "k (R+T)")

            if c_kt is not None:
                leg_k.addItem(c_kt, "k (90% T)")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] display failed | component=nk | reason=%s", e, exc_info=True)

            self.logger.error(traceback.format_exc())

