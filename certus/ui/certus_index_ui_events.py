import os
import sys
from pathlib import Path
import logging
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
    OH_BAND_MIN,
    OH_BAND_MAX,
)
from certus.ui.certus_ui_shared import apply_app_zoom
from certus.ui.certus_index_ui_utils import (
    _notify_user,
    _update_loaded_file_label,
    _set_spectrum_plot_title,
    _log_loaded_spectrum_metadata,
    _display_detected_data_type,
    _update_lambda_bounds_from_target_data,
    _is_qt_offscreen_mode,
    _source_type_label,
    KLogAxisItem,
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


class CertusIndexEventsMixin:
    def _setup_shortcuts(self) -> None:
        """Install premium cross-window shortcuts."""
        try:
            install_standard_shortcuts(
                self,
                # F5 / Esc were missing entirely: INDEX declared no QShortcut at
                # all, so the operator had no keyboard way to start or abort a run.
                run=getattr(self, "run_optimization", None),
                stop=getattr(self, "stop_optimization", None),
                save=getattr(self, "save_config", None),
                load=getattr(self, "load_config", None),
                zoom_in=getattr(self, "zoom_in_ui", None),
                zoom_out=getattr(self, "zoom_out_ui", None),
                reset_zoom=getattr(self, "reset_ui_zoom", None),
            )
        except RuntimeError, AttributeError, TypeError, ValueError:
            self._core_logger.debug("Shortcut installation failed", exc_info=True)

    def _update_zoom_status(self, factor: float | None = None) -> None:
        if factor is None:
            factor = getattr(self, "_zoom_factor", 1.0)
        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.setText(f"Zoom {int(round(factor * 100))}%")

    def _apply_ui_zoom(self, factor: float) -> None:
        apply_app_zoom(
            self,
            factor,
            label_attr="lbl_zoom",
            stylesheet_fn=CertusTheme.get_standard_stylesheet,
            toast_fn=show_toast,
            base_font_size=getattr(CertusTheme, "FONT_SIZE_BASE", 10),
        )

    def _on_substrate_mode_changed(self) -> None:
        """Handle substrate mode change"""

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        # Show/hide info label

        self.lbl_frosted_info.setVisible(is_frosted_glass)

        # Frosted: disable norm, force reflection only

        if is_frosted_glass:
            # Uncheck and disable normalization

            self.chk_normalized.setChecked(False)

            self.chk_normalized.setEnabled(False)

            # Force reflection weights

            self.sb_weight_T.setValue(0.0)

            self.sb_weight_T.setEnabled(False)

            self.sb_weight_R.setValue(1.0)

        else:
            # Re-enable normalization

            self.chk_normalized.setEnabled(True)

            self.chk_normalized.setChecked(True)

            # Re-enable T weight

            self.sb_weight_T.setEnabled(True)

            self.sb_weight_T.setValue(1.0)

        self._persist_index_weight_settings()

    def _on_substrate_changed(self, index: int) -> None:
        """When Al2O3 or Si is selected: auto-configure absorbing mode (locked) if k(lambda) is available.

        Sapphire without k column in xlsx: transparent substrate only (no absorption).

        For any other substrate: restore manual mode."""

        sub_name = SUBSTRATE_LIST[index] if 0 <= index < len(SUBSTRATE_LIST) else ""

        is_sapphire = sub_name == "Sapphire (Al2O3)"

        is_silicon = sub_name == "Silicon (Si)"

        if is_sapphire:
            if _SAPPHIRE_WLS is not None:
                self._absorbing_sub_widget.setVisible(True)

                self.btn_import_ksub.setEnabled(False)

                self._ksub_raw_wls = _SAPPHIRE_WLS

                self._ksub_raw_k = _SAPPHIRE_K

                if _SAPPHIRE_FILE_HAS_K_COLUMN:
                    self.chk_absorbing_sub.setChecked(True)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(1.0)

                    self.sb_sub_thickness_mm.setEnabled(True)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx (auto, colonne k)")

                else:
                    self.chk_absorbing_sub.setChecked(False)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(0.0)

                    self.sb_sub_thickness_mm.setEnabled(False)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx  no k column: transparent only")

            else:
                # File not found  warn but don't block

                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx NOT FOUND")

        elif is_silicon:
            if _SILICON_WLS is not None:
                # Auto-activate and lock absorbing mode

                self.chk_absorbing_sub.setChecked(True)

                self.chk_absorbing_sub.setEnabled(False)

                self._absorbing_sub_widget.setVisible(True)

                self.sb_sub_thickness_mm.setValue(0.5)

                self.sb_sub_thickness_mm.setEnabled(True)

                # Show info; disable manual CSV import (data is built-in from clues.xlsx)

                self.lbl_ksub_file.setText("clues.xlsx -> Si-substrate (auto)")

                self.btn_import_ksub.setEnabled(False)

                # Store silicon k internally (will be interpolated to target grid in _on_run)

                self._ksub_raw_wls = _SILICON_WLS

                self._ksub_raw_k = _SILICON_K

            else:
                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("clues.xlsx Si-substrate NOT FOUND")

        else:
            # Other substrates: restore manual control

            self.chk_absorbing_sub.setChecked(False)

            self.chk_absorbing_sub.setEnabled(True)

            self._absorbing_sub_widget.setVisible(False)

            self.sb_sub_thickness_mm.setValue(1.0)

            self.sb_sub_thickness_mm.setEnabled(True)

            self.btn_import_ksub.setEnabled(True)

            if self._ksub_raw_wls is _SAPPHIRE_WLS or self._ksub_raw_wls is _SILICON_WLS:
                # Clear built-in data so other substrates start clean

                self._ksub_raw_wls = None

                self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(no files)")

    def _on_absorbing_sub_toggled(self, checked: bool) -> None:

        self._absorbing_sub_widget.setVisible(checked)

    def _on_import_ksub(self) -> None:

        path = certus_get_open_file_name(self, "Import k_sub substrate", "CSV (*.csv);;All (*)")

        if not path:
            return

        set_certus_last_dir(path)

        try:
            df_k = pd.read_csv(path, comment="#")

            # Accept first two numeric columns regardless of header names

            cols = df_k.select_dtypes(include=[np.number]).columns

            if len(cols) < 2:
                raise ValueError("The CSV must contain at least 2 numeric columns (lambda, k).")

            self._ksub_raw_wls = df_k[cols[0]].to_numpy(dtype=np.float64)

            self._ksub_raw_k = df_k[cols[1]].to_numpy(dtype=np.float64)

            self.lbl_ksub_file.setText(Path(path).name)

            self.logger.info(
                "[FILE] k_sub imported: %s (%d points)",
                Path(path).resolve(),
                len(self._ksub_raw_wls),
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            _notify_user(self, "k_sub Error", str(e), level="warning")

            self._ksub_raw_wls = None

            self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(error)")

    def _auto_detect_from_file(self, filepath: str) -> None:
        """Auto-detect substrate from filename and pre-estimate thickness

        from the spectrum (oscillation counting). Updates GUI widgets accordingly."""

        fname = Path(filepath).name.lower()

        #  1. substrate detection from filename

        SUBSTRATE_KEYWORDS = {
            "SiO2": [
                "fusedsilica",
                "fused_silica",
                "silica_glass",
            ],
            "N-BK7": [
                "bk7",
                "nbk7",
                "n-bk7",
                "borosilicate",
                "glass",
                "bk",
                "pyrex",
            ],
            "D263T": ["d263", "d263t", "schott", "d263teco"],
            "Al2O3": [
                "sapphire",
                "saphir",
                "al2o3",
                "alumina",
                "alumine",
                "corundum",
                "ruby",
            ],
            "B270i": ["b270", "b270i", "soda", "sodalime"],
            "Si": [
                "silicon",
                "silicium",
                "si_sub",
                "wafer",
            ],
        }

        detected_substrate = None

        for sub_name, keywords in SUBSTRATE_KEYWORDS.items():
            for kw in keywords:
                if kw in fname:
                    detected_substrate = sub_name

                    break

            if detected_substrate:
                break

        if detected_substrate:
            idx = self.cb_sub.findText(detected_substrate)

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

                self.logger.info("[INDEX.LOAD] auto-detected substrate | substrate=%s", detected_substrate)

        #  2. Pre-estimate thickness from spectrum

        self._estimated_thickness_nm = None

        if not hasattr(self, "target_data") or self.target_data is None:
            return

        try:
            from scipy.signal import find_peaks

            wls = self.target_data["lambda"].to_numpy()

            # Use T if available, otherwise R

            if "T" in self.target_data.columns:
                signal = self.target_data["T"].to_numpy()

            elif "R" in self.target_data.columns:
                signal = self.target_data["R"].to_numpy()

            else:
                return

            valid = np.isfinite(signal) & np.isfinite(wls) & (wls > 0)

            wls = wls[valid]

            signal = signal[valid]

            if len(wls) < 16:
                return

            lmin, lmax = wls.min(), wls.max()

            # Approx n from detected substrate

            n_approx = 2.0

            sub_text = self.cb_sub.currentText() if hasattr(self, "cb_sub") else ""

            if "SiO2" in sub_text or "fused" in sub_text.lower():
                n_approx = 1.5

            elif "Al2O3" in sub_text or "sapphire" in sub_text.lower():
                n_approx = 2.1

            elif "Si" in sub_text and "SiO2" not in sub_text:
                n_approx = 3.5

            #  Method 1: FFT on uniformly sampled 1/lambda axis

            d_fft = None

            try:
                # Resample signal on uniform 1/lambda grid (Fabry-Perot fringes are periodic in 1/lambda)

                inv_wls = 1.0 / wls  # nm^-1, but wls in nm -> values ~1e-3

                inv_sorted_idx = np.argsort(inv_wls)

                inv_wls_s = inv_wls[inv_sorted_idx]

                sig_s = signal[inv_sorted_idx]

                N_fft = 4096

                inv_uniform = np.linspace(inv_wls_s[0], inv_wls_s[-1], N_fft)

                sig_uniform = np.interp(inv_uniform, inv_wls_s, sig_s)

                # Detrend

                sig_uniform -= np.polyval(np.polyfit(inv_uniform, sig_uniform, 3), inv_uniform)

                fft_amp = np.abs(np.fft.rfft(sig_uniform))

                freqs = np.fft.rfftfreq(N_fft, d=(inv_uniform[1] - inv_uniform[0]))  # in nm

                # Ignore DC and very low freqs (below 200 nm optical path)

                freq_mask = freqs > (1.0 / (2.0 * n_approx * lmax) * 0.5)

                if freq_mask.sum() > 2:
                    dominant_freq_idx = np.argmax(fft_amp[freq_mask])

                    dominant_freqs = freqs[freq_mask]

                    dominant_freq = dominant_freqs[dominant_freq_idx]  # in nm (= 2*n*d)

                    if dominant_freq > 0:
                        d_fft = dominant_freq / (2.0 * n_approx)

            except NUMERICAL_FAULT_EXCEPTIONS as e_fft:
                self.logger.debug(f"FFT thickness estimate failed: {e_fft}")

            #  Method 2: Peak/valley counting (robust to low-contrast fringes)

            d_peaks = None

            try:
                # Detrend signal with a polynomial fit to remove baseline drift

                poly_coef = np.polyfit(wls, signal, 3)

                sig_detrended = signal - np.polyval(poly_coef, wls)

                # Adaptive prominence: 10% of signal range

                sig_range = np.nanmax(sig_detrended) - np.nanmin(sig_detrended)

                prominence = max(sig_range * 0.10, 1e-4)

                min_dist_pts = max(3, len(wls) // 50)

                peaks, _ = find_peaks(sig_detrended, prominence=prominence, distance=min_dist_pts)

                valleys, _ = find_peaks(-sig_detrended, prominence=prominence, distance=min_dist_pts)

                n_extrema = len(peaks) + len(valleys)

                if n_extrema >= 2:
                    # Each fringe = 1 peak + 1 valley -> n_oscillations = n_extrema / 2

                    n_osc = n_extrema / 2.0

                    inv_range = 1.0 / lmin - 1.0 / lmax

                    if inv_range > 0:
                        d_peaks = n_osc / (2.0 * n_approx * inv_range)

            except NUMERICAL_FAULT_EXCEPTIONS as e_pk:
                self.logger.debug(f"Peak-count thickness estimate failed: {e_pk}")

            # -- Choose best estimate: FFT is primary (robust to noise & low contrast)

            d_estimate = None

            method_str = ""

            if d_fft is not None:
                d_estimate = d_fft

                if d_peaks is not None:
                    method_str = f"FFT, n\u2248{n_approx} (peaks check: {d_peaks:.0f} nm)"

                else:
                    method_str = f"FFT, n\u2248{n_approx}"

            elif d_peaks is not None:
                d_estimate = d_peaks

                method_str = f"peaks ({len(peaks)}up+{len(valleys)}dn), n\u2248{n_approx}"

            if d_estimate is not None and d_estimate > 5.0:
                d_estimate = max(10.0, d_estimate)

                self._estimated_thickness_nm = float(d_estimate)

                # Margins: -50% / +100%

                d_min = max(3.0, d_estimate * 0.50)

                d_max = d_estimate * 2.0

                # Round to clean values

                step = 50.0 if d_estimate > 500 else 10.0

                d_min = round(d_min / step) * step

                d_max = round(d_max / step) * step

                d_max = max(d_max, d_min + step * 2)

                # Clamp to physical spinbox ranges

                d_min = max(3.0, min(d_min, 49000.0))

                d_max = max(d_min + 10.0, min(d_max, 50000.0))

                self.sb_dmin.setValue(d_min)

                self.sb_dmax.setValue(d_max)

                self.logger.info(
                    "[INDEX.LOAD] estimated thickness | value=~%.0f nm | method=%s | range=[%.0f, %.0f] nm",
                    d_estimate,
                    method_str,
                    d_min,
                    d_max,
                )

            else:
                self.logger.info("[INDEX.LOAD] thickness not estimated | reason=no oscillations detected")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.debug(f"Auto-detect thickness failed:{e}")

    def _toggle_exclude(self, checked) -> None:

        self.sb_ex_min.setEnabled(checked and not self.chk_oh_band.isChecked())

        self.sb_ex_max.setEnabled(checked and not self.chk_oh_band.isChecked())

        # If exclude is unchecked, also uncheck OH band for coherence

        if not checked and self.chk_oh_band.isChecked():
            self.chk_oh_band.blockSignals(True)

            self.chk_oh_band.setChecked(False)

            self.chk_oh_band.blockSignals(False)

        self._update_plot_exclusion()

    def _update_plot_exclusion(self) -> None:

        if self.exclude_region is not None:
            try:
                self.plot_spectrum.removeItem(self.exclude_region)

            except (AttributeError, RuntimeError) as e:
                # Non-critical: exclude_region may not exist or already removed

                self.logger.debug("[INDEX.UI] exclude region removal skipped: %s", e)

                pass

            self.exclude_region = None

        if self.chk_exclude.isChecked():
            min_v = self.sb_ex_min.value()

            max_v = self.sb_ex_max.value()

            if max_v > min_v:
                self.exclude_region = pg.LinearRegionItem(
                    [min_v, max_v], brush=pg.mkBrush(255, 0, 0, 50), movable=False
                )

                self.plot_spectrum.addItem(self.exclude_region)

    def _toggle_oh_band(self, checked) -> None:
        """Toggle OH- band exclusion (1360-1460 nm E-band)."""

        if checked:
            # Set the exclude region to OH- band

            self.chk_exclude.setChecked(True)

            self.sb_ex_min.setValue(OH_BAND_MIN)

            self.sb_ex_max.setValue(OH_BAND_MAX)

            self.sb_ex_min.setEnabled(False)

            self.sb_ex_max.setEnabled(False)

        else:
            # Re-enable manual control

            self.sb_ex_min.setEnabled(self.chk_exclude.isChecked())

            self.sb_ex_max.setEnabled(self.chk_exclude.isChecked())

    def load_file(self, filepath=None) -> None:

        if filepath is None or isinstance(filepath, bool):
            from certus.ui.certus_ui import certus_get_open_file_name, DATA_FILE_FILTER

            filepath = certus_get_open_file_name(self, "Open", DATA_FILE_FILTER)

            if not filepath:
                return

        if not filepath:
            return

        try:
            from certus.utils.certus_data import load_spectrum_columns

            # Use the unified standard to load and clean (sort, normalize %, nm, etc.)

            res = load_spectrum_columns(filepath, column_roles={})

            df = res.dataframe

            # Automatic data type analysis (uses original headers preserved by column_roles={})

            self.data_type, parsed_data = analyze_loaded_data(df)

            # Rebuild DataFrame with standard named columns

            self.target_data = pd.DataFrame({"lambda": parsed_data["lambda"]})

            if parsed_data["T"] is not None:
                self.target_data["T"] = parsed_data["T"]

            if parsed_data["R"] is not None:
                self.target_data["R"] = parsed_data["R"]

            # Display filename and detected type

            fname = _update_loaded_file_label(self.lbl_file, filepath)

            self.source_file_path = filepath

            # FIX: Update Plot Title immediately on load

            _set_spectrum_plot_title(self.plot_spectrum, fname)

            # Log file loading details (absolute path for traceability)
            _log_loaded_spectrum_metadata(self.logger, filepath, df)

            # Display detected data type
            _display_detected_data_type(
                self.lbl_data_type,
                self.logger,
                self.data_type,
            )

            # Update lambda bounds
            lmin, lmax = _update_lambda_bounds_from_target_data(
                self.target_data,
                self.sb_lmin,
                self.sb_lmax,
                self.logger,
            )

            if not _is_qt_offscreen_mode():
                src_type = _source_type_label(self.data_type)

                n_rows = int(len(self.target_data))

                has_t = "T" in self.target_data.columns

                has_r = "R" in self.target_data.columns

                summary = build_summary_plain_text(
                    "CERTUS INDEX - Load Summary",
                    [
                        f"File: {Path(filepath).resolve()}",
                        "",
                        "General",
                        (f"Rows: {n_rows}", n_rows <= 0),
                        (f"Detected type: {src_type}", src_type == "Unknown"),
                        "",
                        "Data",
                        (f"Wavelength range: [{float(lmin):.1f}, {float(lmax):.1f}] nm", (float(lmax) <= float(lmin))),
                        f"Columns kept: {', '.join(self.target_data.columns.astype(str).tolist())}",
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if has_t else 'no'}",
                            not has_t and self.data_type != DataType.REFLECTION,
                        ),
                        (
                            f"Reflection column present: {'yes' if has_r else 'no'}",
                            not has_r and self.data_type != DataType.TRANSMISSION,
                        ),
                        (
                            "Potential unit conversion applied (% -> fraction): "
                            f"{'yes' if ((parsed_data['T'] is not None and np.size(parsed_data['T']) > 0 and np.nanmax(parsed_data['T']) > 1.5) or (parsed_data['R'] is not None and np.size(parsed_data['R']) > 0 and np.nanmax(parsed_data['R']) > 1.5)) else 'no'}",
                            False,
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX Load Summary", summary)

            # Display preview - clear() deletes everything

            # Force cleanup of internal structures

            self.plot_spectrum.plotItem.clear()

            try:
                # Clean internal structures

                self.plot_spectrum._tracked_curves = []

                self.plot_spectrum.curve_points = {}

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                # Ignore errors after clear()

                self.logger.warning(f"cleanup after clear() failed: {e}")

            wls = self.target_data["lambda"].values

            _is_frost = self.rb_frosted_glass.isChecked()

            _preview_t, _preview_r = _spectrum_visibility_target_traces(self.data_type, _is_frost)

            if _preview_t and "T" in self.target_data.columns:
                c_t = self.plot_spectrum.plot(
                    wls,
                    self.target_data["T"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=3,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_t, "T", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    self.logger.debug("[INDEX.UI] add tracked curve for T skipped: %s", e)

                    pass

            if _preview_r and "R" in self.target_data.columns:
                c_r = self.plot_spectrum.plot(
                    wls,
                    self.target_data["R"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=3,
                    symbolBrush=CertusTheme.DANGER,
                    name="R data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_r, "R", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    self.logger.debug("[INDEX.UI] add tracked curve for R skipped: %s", e)

                    pass

            self.tabs.setCurrentIndex(0)

            # --- DYNAMIC SMOOTHING WITH AUTO-CLOSING DIALOG ---
            self._apply_dynamic_ir_smoothing(
                wls=wls,
                preview_t=_preview_t,
                preview_r=_preview_r,
            )
            # --- END DYNAMIC SMOOTHING ---

            # Auto-detect substrate and pre-estimate thickness

            self._auto_detect_from_file(filepath)

            # Reset results

            self.latest_results = None

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            # Do not show error for tracking issues (non-critical)

            error_msg = str(e)

            if "add_tracked_curve" in error_msg.lower() or "tracking" in error_msg.lower():
                # Non-critical tracking error - log only

                self.logger.debug(f"Non-critical tracking error during file load: {e}")

            else:
                # Critical error - show user
                _notify_user(self, "Load Error", error_msg, level="error")

                self.logger.error("File load error", exc_info=True)

    def _apply_dynamic_ir_smoothing(
        self,
        *,
        wls: np.ndarray,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Apply optional IR denoising and let user keep raw vs smoothed traces."""
        try:
            from scipy.signal import savgol_filter

            raw_data = self.target_data.copy()
            smoothed_data = self.target_data.copy()
            smoothed_any = False
            cols_ir_smooth: list[str] = []

            if "T" in self.target_data.columns and preview_t:
                cols_ir_smooth.append("T")
            if "R" in self.target_data.columns and preview_r:
                cols_ir_smooth.append("R")

            for col in cols_ir_smooth:
                y = self.target_data[col].values
                y_smooth1 = savgol_filter(y, window_length=11, polyorder=2)
                y_smooth2 = savgol_filter(y, window_length=51, polyorder=2)
                y_final = np.copy(y)
                mask_transition = (wls >= 4000) & (wls <= 5200)
                mask_heavy = wls > 5200
                if np.any(mask_transition) or np.any(mask_heavy):
                    smoothed_any = True
                    if np.any(mask_transition):
                        weights = (wls[mask_transition] - 4000) / (5200 - 4000)
                        y_final[mask_transition] = (1 - weights) * y_smooth1[mask_transition] + weights * y_smooth2[
                            mask_transition
                        ]
                    if np.any(mask_heavy):
                        y_final[mask_heavy] = y_smooth2[mask_heavy]
                    smoothed_data[col] = y_final

            if not smoothed_any:
                return

            self._plot_raw_and_smoothed_preview(
                wls=wls,
                raw_data=raw_data,
                smoothed_data=smoothed_data,
                preview_t=preview_t,
                preview_r=preview_r,
            )
            keep_raw = self._ask_keep_raw_or_smoothed()
            self.target_data = raw_data if keep_raw else smoothed_data
            self._redraw_target_preview(wls, preview_t, preview_r)
        except ImportError:
            self.logger.warning("[INDEX.LOAD] smoothing skipped: scipy.signal unavailable")
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning("[INDEX.LOAD] smoothing failed: %s", e)

    def _ask_keep_raw_or_smoothed(self) -> bool:
        """Return True when user explicitly keeps raw traces."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Noise Filtering")
        msg_box.setText(
            "IR Noise detected in 4000-5200nm band.\n"
            "Do you want to keep the smoothed response or the raw response?\n\n"
            "If no selection is made, the smoothed response will be kept after 5 seconds."
        )
        btn_smooth = msg_box.addButton(
            "Keep Smoothed",
            QMessageBox.ButtonRole.AcceptRole,
        )
        btn_raw = msg_box.addButton("Keep Raw", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_smooth)

        timer = QTimer(msg_box)
        timer.timeout.connect(msg_box.accept)
        timer.start(5000)
        msg_box.exec()
        timer.stop()
        return msg_box.clickedButton() == btn_raw

    def detach_current_plot(self) -> None:
        """Detach current plot or data table in a separate window"""

        current_widget = self.tabs.currentWidget()

        if current_widget is None:
            return

        current_index = self.tabs.currentIndex()

        # 1. OPTION : TAB SPECTRUM (Index 0)

        if current_index == 0:
            plot_name = "spectrum"

            plot_title = "Transmission / Reflection Spectrum"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            detached_plot_copy = clone_plot_widget(self.plot_spectrum)

            if detached_plot_copy:
                detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

                detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

                self.detached_plot_windows[plot_name] = detached_window

                detached_window.show()

        # 2. OPTION : TAB N_K (Index 1) -> Split into two windows!

        elif current_index == 1:
            screen = QApplication.primaryScreen().availableGeometry()

            win_w = screen.width() // 2 - 10

            win_h = screen.height() - 100

            # Detach N (Left Axis)

            if "nk_n" not in self.detached_plot_windows or not self.detached_plot_windows["nk_n"].isVisible():
                n_clone = clone_plot_widget(self.plot_nk, title_override="Refractive Index n")

                win_n = DetachedPlotWindow(n_clone, parent=self, title="Refractive Index n")

                win_n.closed_signal.connect(functools.partial(self.reattach_plot, "nk_n"))

                self.detached_plot_windows["nk_n"] = win_n

                win_n.setGeometry(screen.x(), screen.y() + 40, win_w, win_h)

                win_n.show()

                n_clone.setLabel("left", "Refractive Index n", color=CertusTheme.PRIMARY)

            else:
                self.detached_plot_windows["nk_n"].raise_()

            # Detach K (Right Axis)

            if "nk_k" not in self.detached_plot_windows or not self.detached_plot_windows["nk_k"].isVisible():
                k_clone = CertusScientificPlot(
                    None,
                    title="Extinction Coefficient k",
                    y_label="k",
                    x_label="lambda (nm)",
                    axisItems={"left": KLogAxisItem(orientation="left")},
                )

                if hasattr(self, "_vb_k"):
                    for item in self._vb_k.addedItems:
                        if isinstance(item, pg.PlotCurveItem):
                            x, y = item.getData()

                            if x is not None and y is not None:
                                pen = item.opts.get("pen", pg.mkPen("y"))

                                k_clone.plot(x, y, pen=pen, name=item.name())

                win_k = DetachedPlotWindow(k_clone, parent=self, title="Extinction Coefficient k")

                win_k.closed_signal.connect(functools.partial(self.reattach_plot, "nk_k"))

                self.detached_plot_windows["nk_k"] = win_k

                win_k.setGeometry(screen.x() + win_w + 20, screen.y() + 40, win_w, win_h)

                win_k.show()

                k_clone.setYRange(-6.0, -2.0, padding=0)

            else:
                self.detached_plot_windows["nk_k"].raise_()

        # 3. OPTION : TAB DATA (Index 3)

        elif current_index == 3 or self.tabs.tabText(current_index) == "Data":
            plot_name = "data_table"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            # Create a detached table (Excel-like with copy support)

            table_copy = ExcelTableWidget()

            table_copy.setColumnCount(self.table_res.columnCount())

            table_copy.setRowCount(self.table_res.rowCount())

            # Copy headers

            labels = []

            for i in range(self.table_res.columnCount()):
                item = self.table_res.horizontalHeaderItem(i)

                labels.append(item.text() if item else f"C{i}")

            table_copy.setHorizontalHeaderLabels(labels)

            # Copy content

            try:
                for r in range(self.table_res.rowCount()):
                    for c in range(self.table_res.columnCount()):
                        item = self.table_res.item(r, c)

                        if item:
                            table_copy.setItem(r, c, QTableWidgetItem(item.text()))

            except NUMERICAL_FAULT_EXCEPTIONS:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            win_data = DetachedPlotWindow(table_copy, parent=self, title="Result Data Table")

            # Apply some extra styling to the detached table to make it fit

            table_copy.setStyleSheet(f"background: {CertusTheme.SURFACE}; border: none;")

            win_data.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = win_data

            win_data.resize(900, 700)

            win_data.show()

    def on_toggle_details(self, checked) -> None:
        """Show/Hide log"""

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

        if hasattr(self, "right_splitter"):
            if checked:
                self.right_splitter.setSizes([600, 200])

            else:
                self.right_splitter.setSizes([1000, 0])

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""

        # Shutdown ThreadPoolExecutor if exists

        if hasattr(self, "_executor") and self._executor is not None:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                if hasattr(self, "logger") and self.logger:
                    self.logger.warning(f"Error shutting down executor: {e}")

            finally:
                self._executor = None

        # Cleanup optimization worker and thread

        self._cleanup_worker()

        # Cleanup beam worker and thread

        if getattr(self, "_beam_worker", None):
            self._beam_worker.stop()

        beam_thread = getattr(self, "_beam_thread", None)

        if beam_thread is not None and beam_thread.isRunning():
            beam_thread.quit()

            if not beam_thread.wait(2000):
                self.logger.critical(
                    "Beam thread did not stop within 2s in closeEvent - skipping terminate() to avoid unsafe thread kill."
                )

        try:
            self.killTimer(self._log_timer_id)

        except AttributeError, TypeError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.logger.info("[INDEX.STATE] application closed")

        super().closeEvent(event)
