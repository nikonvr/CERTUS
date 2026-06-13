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

class CertusIndexWorkerMixin:
    def _warmup_numba(self) -> None:
        """JIT precompilation via background thread"""
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        import threading
        self.lbl_status.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _warmup_numba_thread_runner(self) -> None:
        try:
            from certus.core.certus_index_objectives import warmup_index_objectives
            warmup_index_objectives(silent=True)

            wls = np.array([500.0, 600.0], dtype=np.float64)

            get_n_substrate_array_by_id(0, wls)

            get_n_frosted_glass_array(wls)

            n_test = np.array([1.5, 1.5])

            k_test = np.array([0.0, 0.0])


            calculate_RT_single_layer_backside_array(wls, n_test, k_test, 100.0, n_test)

            calculate_bare_substrate_RT(wls, n_test)

            calculate_single_interface_R(wls, n_test)

            # Absorbing substrate kernels (sapphire / user k_sub)

            k_sub_test = np.array([1e-4, 1e-4])

            calculate_bare_substrate_T_absorbing(wls, n_test, k_sub_test, 1.0e6)

            calculate_bare_substrate_R_absorbing(wls, n_test, k_sub_test, 1.0e6)

            calculate_RT_single_layer_absorbing_substrate_array(wls, n_test, k_test, 100.0, n_test, k_sub_test, 1.0e6)

            # Warmup per-lambda kernels (scalar + batch)

            _optimize_point_kernel(
                1.5,
                0.0,
                500.0,
                0.9,
                0.1,
                1.0,
                1.0,
                1.5,
                0.92,
                0.08,
                100.0,
                True,
                True,
                True,
                False,
            )

            _optimize_all_points_batch(
                np.array([1.5, 1.5]),
                np.array([0.0, 0.0]),
                wls,
                np.array([0.9, 0.9]),
                np.array([0.1, 0.1]),
                1.0,
                1.0,
                n_test,
                np.array([0.92, 0.92]),
                np.array([0.08, 0.08]),
                100.0,
                True,
                True,
                True,
                False,
                np.array([False, False]),
            )

            self.sig_numba_ready.emit()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f" Numba warmup failed: {e}", exc_info=True)
            self.sig_numba_error.emit()

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:
        self.lbl_status.setText("Ready (JIT Compiled)")
        self._on_numba_ready()  # Mark as ready
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        self.lbl_status.setText("JIT Init Error")

    def _configure_and_start_optimization_worker(self, config: OptimizationConfig) -> None:
        """Instantiate/connect the optimization worker and start the thread."""

        self._thread = QThread()

        # Two-stage TLU (lambda<=2200) + IR spline only if the user window contains lambda < 2200 nm.
        # Otherwise (e.g., fit only 3500-5200 nm): a single stage over the entire range avoids 0 points.
        use_two_stage = config.lambda_max > 2500.0 and config.lambda_min < 2200.0

        if use_two_stage:
            self.logger.info(
                "[INDEX.LOAD] pipeline selected | mode=two-stage | reason=wl_max>2500nm | tlu_band_max=2200nm"
            )
            config.lambda_max_fit = 2200.0
        elif config.lambda_max > 2500.0:
            self.logger.info(
                "[INDEX.LOAD] pipeline selected | mode=single-stage | reason=wl_max>2500nm and lambda_min>=2200nm"
            )
        else:
            self.logger.info("[INDEX.LOAD] pipeline selected | mode=standard | reason=wl_max<=2500nm")

        self._index_tlu_live_ctx = self._make_index_tlu_live_ctx(config)
        self._worker = OptimizationWorker(config, logger=self.logger)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.evals_update.connect(self._on_evals_update)
        self._worker.curve_update.connect(self._on_curve_update)
        self._worker.error.connect(self._on_error)

        if use_two_stage:
            # Connect to custom handler for Phase 2
            self._worker.finished.connect(self._on_tlu_constrained_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
        else:
            self._worker.finished.connect(self._on_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    def _abort_run_optimization(self, title: str, message: str, *, critical: bool = False) -> None:
        """Abort run setup with a user-visible message and reset primary buttons."""
        _notify_user(
            self,
            title,
            message,
            level="error" if critical else "warning",
            blocking=critical,
        )
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _resolve_substrate_absorption_inputs(
        self,
        *,
        substrate_name: str,
        wls_target: np.ndarray,
    ) -> tuple[np.ndarray | None, float | None, np.ndarray | None] | None:
        """Resolve (k_sub, substrate_thickness_nm, n_sub_data) for the selected substrate mode.

        Returns ``None`` when setup must be aborted (message already shown to the user).
        """
        k_sub_interp: np.ndarray | None = None
        sub_thickness_nm: float | None = None
        n_sub_data: np.ndarray | None = None

        is_silicon = substrate_name == "Silicon (Si)"

        if is_silicon:
            if _SILICON_WLS is not None:
                n_sub_data = _get_silicon_n_on_grid(wls_target)
                thickness_mm = self.sb_sub_thickness_mm.value()
                if thickness_mm > 0:
                    k_sub_interp = _get_silicon_k_on_grid(wls_target)
                    sub_thickness_nm = thickness_mm * 1e6
                    self.logger.info(
                        f"[SILICON] Self-absorbent substrate: thickness={thickness_mm:.3f} mm "
                        f"| k_sub(max)={k_sub_interp.max():.4g}"
                    )
                else:
                    self.logger.info("[SILICON] Thickness = 0 -> transparent substrate (k=0 everywhere).")
            else:
                self.logger.warning(
                    "[INDEX.LOAD] silicon substrate fallback | reason=clues.xlsx substrate data unavailable | mode=transparent"
                )
            return k_sub_interp, sub_thickness_nm, n_sub_data

        # For all other substrates, they are transparent (k=0)
        self.logger.info(
            "[INDEX.LOAD] substrate forced transparent | substrate=%s | k=0 everywhere",
            substrate_name,
        )
        return None, None, None

    def run_optimization(self) -> None:
        """

        Run the index optimization process.

        This method initiates the optimization workflow including:

        - Data validation and mode checking

        - Parameter configuration and setup

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusIndex instance

        Returns:

            None

        Notes:

            - Requires loaded target spectrum data

            - Supports both normal and frosted glass modes

            - Validates data requirements for selected mode

            - Emits progress signals during optimization

        """

        if self.target_data is None:
            _notify_user(self, "No Data", "Please load a spectrum first.", level="warning")

            return

        # Check for frosted glass mode

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        if is_frosted_glass:
            # Frosted glass requires reflection data

            if "R" not in self.target_data.columns:
                _notify_user(
                    self,
                    "Data Error",
                    "Frosted Glass mode requires reflection (R) data.\n"
                    "Please load a file with reflection measurements.",
                    level="warning",
                )

                return

            # Force data_type to REFLECTION for frosted glass

            effective_data_type = DataType.REFLECTION

        else:
            effective_data_type = self.data_type

        self._cleanup_worker()

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        self.lbl_status.setText(" Optimization running...")

        self.recap_widget.setVisible(False)

        self.tabs.setCurrentIndex(0)

        # substrate - always use selected material (with bounds check)

        sub_idx = self.cb_sub.currentIndex()

        if sub_idx < 0 or sub_idx >= len(SUBSTRATE_LIST):
            self.logger.error(f"Invalid substrate index: {sub_idx}")
            _notify_user(self, "Error", "Invalid substrate selection.", level="error")

            self.btn_run.setEnabled(True)

            self.btn_stop.setEnabled(False)

            return

        full_sub_name = SUBSTRATE_LIST[sub_idx]

        substrate_name = full_sub_name

        substrate_mode = substrateMode.FROSTED_GLASS if is_frosted_glass else substrateMode.STANDARD

        ex_min, ex_max = None, None

        if self.chk_exclude.isChecked():
            ex_min = self.sb_ex_min.value()

            ex_max = self.sb_ex_max.value()

            if ex_min >= ex_max:
                _notify_user(self, "Warning", "Invalid exclusion range. Ignored.", level="warning")

                ex_min, ex_max = None, None

        # Absorbing substrate inputs (Sapphire/Si/manual k_sub)
        wls_target = self.target_data["lambda"].to_numpy(dtype=np.float64)
        substrate_inputs = self._resolve_substrate_absorption_inputs(
            substrate_name=substrate_name,
            wls_target=wls_target,
        )
        if substrate_inputs is None:
            return
        k_sub_interp, sub_thickness_nm, n_sub_data = substrate_inputs

        _d_fft_seed = getattr(self, "_estimated_thickness_nm", None)

        _fixed_thickness_seed = None

        if _d_fft_seed is not None:
            _d_lo = float(min(self.sb_dmin.value(), self.sb_dmax.value()))

            _d_hi = float(max(self.sb_dmin.value(), self.sb_dmax.value()))

            _fixed_thickness_seed = float(np.clip(float(_d_fft_seed), _d_lo, _d_hi))

        config = OptimizationConfig(
            target_data=self.target_data,
            data_type=effective_data_type,
            substrate=substrate_name,
            substrate_mode=substrate_mode,
            thickness_min=self.sb_dmin.value(),
            thickness_max=self.sb_dmax.value(),
            lambda_min=self.sb_lmin.value(),
            lambda_max=self.sb_lmax.value(),
            exclude_min=ex_min,
            exclude_max=ex_max,
            source_file=self.source_file_path,
            use_normalized=self.chk_normalized.isChecked(),
            weight_T=self.sb_weight_T.value() if not is_frosted_glass else 0.0,
            weight_R=self.sb_weight_R.value(),
            high_precision=self.chk_high_precision.isChecked(),
            fixed_thickness=_fixed_thickness_seed,
            k_sub_data=k_sub_interp,
            substrate_thickness_nm=sub_thickness_nm,
            n_sub_data=n_sub_data,
        )

        # Start progress widget timing

        self.logger.info("=" * 60)

        self.logger.info("[INDEX.STATE] optimization started")

        if self.source_file_path:
            self.logger.info(
                "[FILE] Measured Spectrum: %s",
                Path(self.source_file_path).resolve(),
            )

        else:
            self.logger.warning("[FILE] Measured Spectrum: path not specified")

        if substrate_name == "Sapphire (Al2O3)":
            self.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) "
                "| k file: %s | k column: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )

        elif substrate_name == "Silicon (Si)":
            self.logger.info(
                "[FILE] Substrate Si (clues.xlsx): %s",
                Path(get_resource_path("clues.xlsx")).resolve(),
            )

        self.logger.info("=" * 60)

        self.logger.info(f"substrate: {substrate_name} (Mode: {substrate_mode.name})")

        self.logger.info(
            "[INDEX.LOAD] thickness range | min=%.1f nm | max=%.1f nm",
            config.thickness_min,
            config.thickness_max,
        )

        self.logger.info(
            "[INDEX.LOAD] wavelength range | min=%.1f nm | max=%.1f nm",
            config.lambda_min,
            config.lambda_max,
        )

        if config.exclude_min and config.exclude_max:
            self.logger.info(f"Excluded Region: {config.exclude_min} - {config.exclude_max} nm")

        self.logger.info("=" * 50)

        self._reset_optimization_progress_state(config)
        self._configure_and_start_optimization_worker(config)

    def stop_optimization(self) -> None:
        """Stop optimization - best solution will be saved by the worker"""

        # confirm_stop_with_timeout is imported from certus.ui.certus_ui

        if not confirm_stop_with_timeout(self):
            return

        # Ensure UI reflects stopped state immediately

        self.lbl_status.setText(" Stopping...")
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped")

        self.btn_stop.setEnabled(False)

        ok_main = stop_worker_and_thread(
            self._worker,
            self._thread,
            timeout_ms=3000,
            logger=self.logger,
            label="Thread",
        )
        if not ok_main:
            self.lbl_status.setText(" Stop timeout (thread may still finish)")

        stop_worker_and_thread(
            getattr(self, "_worker2", None),
            getattr(self, "_thread2", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Thread2",
        )

        # Also stop beam analysis worker if running

        stop_worker_and_thread(
            getattr(self, "_beam_worker", None),
            getattr(self, "_beam_thread", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Beam thread",
        )

        self.lbl_status.setText(" Stopping...")

    def _cleanup_worker(self) -> None:

        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    if self._worker:
                        self._worker.stop()

                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                # Qt object has already been deleted

                pass

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    if hasattr(self, "_worker2") and self._worker2:
                        self._worker2.stop()

                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                self._core_logger.debug("Silenced exception in %s", __name__, exc_info=True)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_thread_finished(self) -> None:

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_evals_update(self, n_evals: int) -> None:
        """Update evaluation count for progress widget ETA."""

        self._current_n_evals = n_evals

        self.lbl_dice.setText(f" {n_evals:,}")

    def _on_progress(self, step: int, phase: str, extra_info=None) -> None:

        # Throttle UI updates (plots, labels, tables) to avoid GUI flooding

        now = time.time()

        # Always update if phase changes, otherwise check 2.0s interval

        phase_changed = self._last_phase_name != phase

        self._last_phase_name = phase

        if not phase_changed and (now - self._last_progress_ui_update < 2.0):
            return

        self._last_progress_ui_update = now

        rmse_val = 0.0

        rmse_str = ""

        is_numeric_msg = False

        if isinstance(extra_info, dict) and "n" in extra_info and "k" in extra_info and "wls" in extra_info:
            try:
                self._apply_index_live_plot_payload(extra_info)

                wls = extra_info["wls"]

                n_c = extra_info["n"]

                k_c = extra_info["k"]

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error plotting live progress: {e}", exc_info=True)

                wls = extra_info.get("wls", np.array([]))

                n_c = extra_info.get("n", np.array([]))

                k_c = extra_info.get("k", np.array([]))

            # Live Update of Data Tab & Clipboard Support

            try:
                if getattr(self, "latest_results", None) is not None:
                    # Update background DataFrame so Copy works

                    live_df = pd.DataFrame({"lambda": wls, "n_calc": n_c, "k_calc": k_c})

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        live_df["R_calc (%)"] = extra_info["R_calc"] * 100

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        live_df["T_calc (%)"] = extra_info["T_calc"] * 100

                    self.latest_results.df_results = live_df

                    self.table_res.setRowCount(len(wls))

                    src_name_base = Path(self.latest_results.config.source_file).stem

                    d_val = (
                        int(round(self.latest_results.thickness))
                        if hasattr(self.latest_results, "thickness") and self.latest_results.thickness
                        else 0
                    )

                    n_colname = f"n_{src_name_base}_{d_val}"

                    k_colname = f"k_{src_name_base}_{d_val}"

                    cols = ["lambda (nm)", n_colname, k_colname]

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        cols.append("T (%)")

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        cols.append("R (%)")

                    self.table_res.setColumnCount(len(cols))

                    self.table_res.setHorizontalHeaderLabels(cols)

                    for i in range(len(wls)):
                        self.table_res.setItem(i, 0, QTableWidgetItem(f"{wls[i]:.1f}"))

                        self.table_res.setItem(i, 1, QTableWidgetItem(f"{n_c[i]:.4f}"))

                        self.table_res.setItem(i, 2, QTableWidgetItem(f"{k_c[i]:.6f}"))

                        col_idx = 3

                        if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['T_calc'][i] * 100:.2f}"))

                            col_idx += 1

                        if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['R_calc'][i] * 100:.2f}"))

                            col_idx += 1

                    self.table_res.resizeColumnsToContents()
            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Live data table update error: {e}", exc_info=True)

            if isinstance(extra_info, dict) and "mse" in extra_info:
                val = extra_info["mse"]

                if val is not None:
                    rmse_val = np.sqrt(val)

                    if rmse_val < self._best_rmse_display:
                        self._best_rmse_display = rmse_val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                else:
                    self.lbl_status.setText(f"{phase}")

            else:
                self.lbl_status.setText(f"{phase}")

            # Still update the progress bar even with dict data

            n_evals = getattr(self, "_current_n_evals", 0)

            self.progress_widget.update(step, 100, n_evals, phase, "")

            return

        elif isinstance(extra_info, float):
            # It's a numerical MSE

            rmse_val = np.sqrt(extra_info)

            if rmse_val < self._best_rmse_display:
                self._best_rmse_display = rmse_val

            rmse_str = f"RMSE: {rmse_val:.5f}"

            self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

            is_numeric_msg = True

        elif isinstance(extra_info, str):
            # Try to parse string message if it contains numerical info

            if "Total Data RMSE" in extra_info:
                try:
                    val_str = extra_info.split()[-1]

                    val = float(val_str)

                    if val < self._best_rmse_display:
                        self._best_rmse_display = val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                    rmse_val = val

                    rmse_str = f"RMSE: {val:.5f}"

                    is_numeric_msg = True

                except ValueError:
                    self.lbl_status.setText(f"{phase} | {extra_info}")

                    rmse_str = extra_info

            else:
                self.lbl_status.setText(f"{phase} | {extra_info}")

                rmse_str = extra_info

        else:
            self.lbl_status.setText(f"{phase}")

            rmse_str = str(extra_info) if extra_info else ""

        if is_numeric_msg and rmse_val > 0:
            self._total_iterations += 1

            # --- UX-3: update convergence chart ---
            if hasattr(self, "_conv_iterations"):
                self._conv_iterations.append(self._total_iterations)
                self._conv_rmse_current.append(rmse_val)
                self._conv_rmse_best.append(self._best_rmse_display)
                xs = self._conv_iterations
                self._conv_curve_current.setData(xs, self._conv_rmse_current)
                self._conv_curve_best.setData(xs, self._conv_rmse_best)

        n_evals = getattr(self, "_current_n_evals", 0)

        self.progress_widget.update(
            iteration=step,
            max_iter=100,
            evals=n_evals,
            phase=phase,
            extra_info=rmse_str,
        )

    def _on_error(self, error_msg: str) -> None:

        self.lbl_status.setText(" Error")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Error")

        # Quit orphaned thread (error signal does NOT trigger thread.quit)

        if hasattr(self, "_thread") and self._thread is not None:
            try:
                if self._thread.isRunning():
                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread cleanup warning: {e}")

            finally:
                self._thread = None

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread2 cleanup warning: {e}")

            finally:
                self._thread2 = None

        self._worker = None

        self._worker2 = None

        self._thread = None

        self._thread2 = None

        self.optimization_running = False

        self.logger.error(f"Worker Error: {error_msg}")

    def _on_curve_update(self, params) -> None:
        """Live TLU : equivalent Metal Bilayer ``progress`` -> ``update_plots`` (best parameter set)."""

        try:
            p = np.asarray(params, dtype=np.float64).ravel()

            if p.size != 7:
                return

            payload = self._index_tlu_live_payload_from_params(p)

            if payload is None:
                return

            self._apply_index_live_plot_payload(payload)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.debug("curve_update: %s", e, exc_info=True)

    def _on_finished(self, res: OptimizationResults) -> None:

        # Stop progress widget and show completion

        mode_str = "Frosted Glass" if res.config.is_frosted_glass else res.config.data_type.name

        self.progress_widget.stop(f"Done ({mode_str})")

        # Status message adapted to mode

        self.lbl_status.setText(f" Done ({mode_str})")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        # Enable Copy n,k

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(True)

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(True)

        # Button states are now entirely automated based on wavelength, no Refine buttons.

        # Save results for export

        self.latest_results = res

        # PHASE 5: Sellmeier refit + k reopt. Skip when result already from Phase 2 global model.

        try:
            method = (res.optimization_stats or {}).get("method", "")

            skip_phase5_overwrite = "PGLOBAL" in method or "Sellmeier+k" in method

            if skip_phase5_overwrite:
                self.logger.info("[INDEX.SPLINE] phase5 skipped | reason=global Sellmeier+k | action=keep_nk")

            else:
                self.lbl_status.setText(" Phase 5: Global Sellmeier fit for n & k re-optimization...")

                df = res.df_results

                if "lambda" in df.columns and "n_calc" in df.columns and "k_calc" in df.columns:
                    wls = df["lambda"].values

                    n_exp = df["n_calc"].values

                    k_cal = df["k_calc"].values

                    # 1. Global Sellmeier 2-poles fit on calculated n

                    n_spline = n_exp.copy()

                    n_target = n_exp.copy()

                    # Blend TLU with Spline for wls < 2500 nm to find the ideal compromise

                    if res.tlu_params is not None:
                        try:
                            from certus_physics import epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk

                            tlu = res.tlu_params

                            E_wls = HC_EV_NM / wls

                            e2_w = epsilon2_TLU_array(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.Eu)

                            e1_w = epsilon1_TL_analytic(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf)

                            n_tlu, _, _ = epsilon_to_nk(e1_w, e2_w, 0.5, 15.0, 15.0)

                            mask_2500 = wls < 2500.0

                            n_target[mask_2500] = (n_spline[mask_2500] + n_tlu[mask_2500]) / 2.0

                        except NUMERICAL_FAULT_EXCEPTIONS as e:
                            self.logger.warning(f"Could not compute TLU compromise: {e}")

                    # Mask out the exclude range if it exists

                    valid_mask = np.ones_like(wls, dtype=bool)

                    ex_min = res.config.exclude_min

                    ex_max = res.config.exclude_max

                    if ex_min is not None and ex_max is not None and ex_min > 0 and ex_max > ex_min:
                        valid_mask &= ~((wls >= ex_min) & (wls <= ex_max))

                    n_fit_global, params_n = fit_sellmeier_global(
                        wls, n_exp, material=res.config.substrate, valid_mask=valid_mask
                    )

                    if params_n is not None:
                        # 2. Re-optimize / smooth k using the 8-parameter empirical law

                        k_smooth, params_k = fit_k_global_8p(wls, k_cal, valid_mask=valid_mask)

                        if params_k is not None:
                            setattr(res, "k_8p_params", params_k)

                        # 3. Update dataframe with perfectly smooth n & newly re-optimized k

                        df["n_calc"] = n_fit_global

                        if params_k is not None:
                            df["k_calc"] = k_smooth

                        # Save Sellmeier parameters to res object to export them

                        setattr(res, "sellmeier_params", params_n)

                        self.logger.info("[INDEX.SPLINE] phase5 complete | status=success")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Phase 5 failed (n Sellmeier / k reopt) : {e}", exc_info=True)

            # Safe Fallback: Original res is unchanged and will be exported normally.

        # =====================================================================

        # Convert final_mse to RMSE

        final_rmse = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Update summary (safe for Spline where tlu_params is None)

        eg_val = res.tlu_params.Eg if res.tlu_params else 0.0

        eps_val = res.tlu_params.eps_inf if res.tlu_params else 0.0

        self.recap_widget.update_results(res.optimal_thickness, final_rmse, eg_val, eps_val)

        # Update graphs (target + fit according to use_normalized) BEFORE HTML export:

        # generate_html_report performs a grab() of the widget; if the export precedes this plot,

        # the Visual Analysis section shows an obsolete state (e.g., live curves only, old T/Tsub mode).

        self._display_results(res)

        # AUTO EXPORT (Excel + HTML ; the PNG capture must reflect the spectrum above)

        self.export_results()

    def _on_tlu_constrained_finished(self, tlu_res: OptimizationResults) -> None:

        # Check if user requested stop during Phase 1

        if self._worker is not None and self._worker.is_stopped:
            self._on_finished(tlu_res)

            return

        # Show the TLU curve and results before asking the question

        final_rmse_tlu = np.sqrt(tlu_res.final_mse) if tlu_res.final_mse >= 0 else 0.0

        eg_val = tlu_res.tlu_params.Eg if tlu_res.tlu_params else 0.0

        eps_val = tlu_res.tlu_params.eps_inf if tlu_res.tlu_params else 0.0

        self.recap_widget.update_results(tlu_res.optimal_thickness, final_rmse_tlu, eg_val, eps_val)

        self._display_results(tlu_res)

        # Force Qt to redraw the GUI immediately before crashing with popup

        # Request validation before launching the IR phase which is cumbersome

        msg_box = QMessageBox(self)

        msg_box.setIcon(QMessageBox.Icon.Question)

        msg_box.setWindowTitle("Phase 1 Completed (TLU)")

        msg_box.setText(
            f"Phase 1 (UV-VIS) completed successfully.\n"
            f"Fixed thickness: {tlu_res.optimal_thickness:.2f} nm.\n\n"
            f"All properties (n, k, thickness) below 2500 nm are now strictly FIXED.\n"
            f"Do you want to launch the Global IR Model extension (> 2500 nm)?"
        )

        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)

        msg_box.setDefaultButton(yes_btn)

        QTimer.singleShot(5000, yes_btn.click)

        reply = msg_box.exec()

        if reply == int(QMessageBox.StandardButton.No) or reply == QMessageBox.StandardButton.No:
            self.logger.info("[INDEX.SPLINE] phase2/ir extension canceled by user | action=keep_full_TLU")

            self._on_finished(tlu_res)

            return

        self.lbl_status.setText(" Phase 2/2: Global Model Refinement IR (> 2500 nm)...")

        # Restore full wavelength range (TLU was fitted on <= 2200 nm only)

        tlu_res.config.lambda_max_fit = None

        if self.target_data is not None:
            tlu_res.config.target_data = self.target_data.copy()

            tlu_res.config.lambda_min = float(self.target_data["lambda"].min())

            tlu_res.config.lambda_max = float(self.target_data["lambda"].max())

            self.logger.info(
                f"  Phase 2: full-range data "
                f"[{tlu_res.config.lambda_min:.0f}, {tlu_res.config.lambda_max:.0f}] nm "
                f"({len(self.target_data)} pts)"
            )

        self._best_rmse_display = 1e12

        self._total_iterations = 0

        self._worker2 = IRGlobalModelWorker(tlu_res.config, tlu_res, logger=self.logger)

        # Removed live visualization logic

        # Re-connect to standard UI handlers

        self._worker2.finished.connect(self._on_finished)

        self._worker2.error.connect(self._on_error)

        self._worker2.progress.connect(self._on_progress)

        self._worker2.evals_update.connect(self._on_evals_update)

        self._worker2.curve_update.connect(self._on_curve_update)

        self._thread2 = QThread()

        self._worker2.moveToThread(self._thread2)

        self._thread2.started.connect(self._worker2.run)

        self._worker2.finished.connect(self._thread2.quit)

        self._worker2.finished.connect(self._worker2.deleteLater)

        self._thread2.finished.connect(self._thread2.deleteLater)

        self._thread2.finished.connect(self._on_thread_finished)

        self._thread2.start()

