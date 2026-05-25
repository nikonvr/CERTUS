"""

CERTUS METAL COMMON

===================

Shared base classes and utilities for CERTUS-METAL and CERTUS-METAL SINGLE.

"""

import functools


import logging

import os
from pathlib import Path

import time

import traceback

from dataclasses import dataclass, field

from typing import Any, Callable


import numpy as np
import pyqtgraph as pg

import scipy.optimize

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot

from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


from certus_data import (
    ReportSection,
    build_standard_report,
    read_data_file_robust,
)
from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
)

from certus_ux import build_premium_overrides, OBJ
from certus_metrology import ValidationStatus
from certus_services import IndexFitRequest, IndexFitService
from certus_plot import CertusScientificPlot
from certus_ui import (
    CertusBaseApp,
    CertusTheme,
    CertusThemeToggle,
    CertusCard,
    CertusActionBar,
    CertusStatusPill,
    create_styled_button,
    DATA_FILES_FILTER_EXTENDED,
    DetachedPlotWindow,
    EnhancedProgressWidget,
    apply_certus_theme,
    confirm_stop_with_timeout,
    format_count_kmg,
    stop_worker_and_thread,
    clone_plot_widget,
    create_header_logo_widget,
    create_log_widget,
    open_data_file_and_read,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    open_documentation,
)

from certus_load_summary import build_summary_plain_text, show_load_summary_dialog



# =============================================================================

# CONSTANTS (Shared Defaults)

# =============================================================================

DEFAULT_EM_MIN = 5

DEFAULT_EM_MAX = 50

DEFAULT_NUM_KNOTS = 5

DEFAULT_NK_MIN = 0.0

DEFAULT_NK_MAX = 10.0

DEFAULT_MIN_KNOT_DISTANCE = 20.0

DEFAULT_EXCEL_FILENAME = "metal_results.xlsx"


DEFAULT_POPSIZE = 15

DEFAULT_MAXITER = 800

DEFAULT_TOL = 0.005

DEFAULT_MUTATION_MIN = 0.5

DEFAULT_MUTATION_MAX = 1.0

DEFAULT_RECOMBINATION = 0.7

DEFAULT_UPDATING = "deferred"

DEFAULT_WORKERS = -1



def normalize_percent_column(values: np.ndarray) -> np.ndarray:
    """Normalize a reflectance/transmittance column to the [0, 1] range.

    Values > 1 are assumed to be percent (0-100) and divided by 100.
    Otherwise the input is returned unchanged. NaN-safe via ``np.nanmax``.

    Used by METAL apps' ``on_file_loaded`` to handle mixed-unit inputs.
    """

    arr = np.asarray(values)
    if arr.size == 0:
        return arr
    try:
        vmax = float(np.nanmax(arr))
    except (TypeError, ValueError):
        return arr
    return arr / 100.0 if vmax > 1.0 else arr


def _format_beam_status(cur: int, tot: int, best: float) -> str:
    """Return the standard METAL beam-analysis status line."""

    rmse = float(np.sqrt(best)) if best >= 0 else 0.0
    return f"Thickness {cur}/{tot} | Best RMSE: {rmse:.2e}"


def setup_beam_analysis_thread(app, worker) -> "QThread":
    """Move a BeamAnalysisWorker onto a fresh QThread and wire standard signals.

    Factors the identical thread wiring used by both METAL apps
    (see ``run_beam_analysis`` in SINGLE/BILAYER). The worker is expected
    to expose ``run``, ``progress(cur, tot, best)``, ``finished(stats)``
    and ``error(str)`` signals, and the app is expected to provide
    ``status_label``, ``on_beam_finished`` and ``_on_beam_error``.

    Returns the created QThread (also stored on ``app.beam_thread``).
    Caller is responsible for ``thread.start()``.
    """

    thread = QThread()
    app.beam_thread = thread
    app.beam_worker = worker
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    worker.progress.connect(lambda cur, tot, best: app.status_label.setText(_format_beam_status(cur, tot, best)))
    worker.finished.connect(app.on_beam_finished)
    worker.error.connect(app._on_beam_error)
    # Proper cleanup to avoid memory leaks
    for signal in (worker.finished, worker.error):
        signal.connect(thread.quit)
        signal.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread


def teardown_beam_thread(app, stats) -> None:
    """Stop the beam-analysis worker thread and reset METAL buttons.

    Shared first block of ``CERTUS_METAL_SINGLE.on_beam_finished`` and
    ``CERTUS_METAL_BILAYER.on_beam_finished``. App-specific plot logic
    must be done separately by the caller.
    """

    thread = getattr(app, "beam_thread", None)
    if thread is not None:
        if thread.isRunning():
            thread.quit()
            if not thread.wait(3000):
                logging.critical(
                    "Beam thread did not stop within 3s in on_beam_finished - skipping terminate() to avoid unsafe thread kill."
                )
        app.beam_thread = None
    if hasattr(app, "btn_run"):
        app.btn_run.setEnabled(True)
    if hasattr(app, "btn_beam"):
        app.btn_beam.setEnabled(True)
    if hasattr(app, "btn_stop"):
        app.btn_stop.setEnabled(False)
    app.beam_stats = stats


def setup_common_metal_plots(app) -> None:
    """Create the common METAL `n & k` tab widgets and wiring."""

    app.clues_plot = CertusScientificPlot(
        app,
        "Optimized Metal Optical Constants (n, k)",
        "Refractive Index (n)",
        "Wavelength (nm)",
    )

    app.p1 = app.clues_plot.getPlotItem()

    app.p2 = pg.ViewBox()

    app.p1.showAxis("right")

    app.p1.scene().addItem(app.p2)

    app.p1.getAxis("right").linkToView(app.p2)

    app.p2.setXLink(app.p1)

    app.p1.getAxis("left").setLabel(
        "Refractive Index (n)",
        color=CertusTheme.CHART_PRIMARY,
    )

    app.p1.getAxis("right").setLabel(
        "Extinction Coefficient (k)",
        color=CertusTheme.CHART_DANGER,
    )

    app.n_curve = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.CHART_PRIMARY, width=2))

    app.k_curve = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2, style=Qt.PenStyle.DashLine))

    app.p1.addItem(app.n_curve)

    app.p2.addItem(app.k_curve)

    def _sync_p2_geometry(*_args) -> None:
        try:
            if app.p1 is None or app.p2 is None or app.p1.vb is None:
                return
            scene_rect = app.p1.vb.sceneBoundingRect()
            if scene_rect.isValid() and scene_rect.width() > 0 and scene_rect.height() > 0:
                app.p2.setGeometry(scene_rect)
        except NUMERICAL_FAULT_EXCEPTIONS:
            return

    app.p1.vb.sigResized.connect(_sync_p2_geometry)

    app.tabs.addTab(app.clues_plot, "n & k")






























class MetalOptimizationWorker(QObject):
    """Base Optimization Worker for METAL applications"""

    finished = pyqtSignal(dict)

    progress = pyqtSignal(dict)

    error = pyqtSignal(str)

    stats_update = pyqtSignal(str, int)

    def __init__(self, params) -> None:

        super().__init__()

        self.params = params

        self.is_running = True

        self.iteration_count = 0

        self.evaluation_count = 0

        self.best_candidate = {"x": None, "fun": float("inf")}

        self._last_progress_time = 0.0

    @pyqtSlot()
    def stop(self) -> None:
        """Request stop"""

        self.is_running = False


def metal_optimization_worker_run_differential_evolution(
    worker: MetalOptimizationWorker,
    global_objective_function: Callable[..., Any],
    args_for_objective: tuple,
) -> None:
    """
    Run ``scipy.optimize.differential_evolution`` with shared callback
    (progress, best candidate, user stop). Emits ``finished`` or ``error``.
    """

    p = worker.params

    try:
        worker.best_candidate = {"x": None, "fun": float("inf")}

        worker._last_live_emit_time = 0.0

        def callback(xk, _convergence) -> None:

            if not worker.is_running:
                raise StopIteration("User requested stop.")

            worker.iteration_count += 1

            popsize = p.get("popsize", 15)

            worker.evaluation_count += popsize

            worker.stats_update.emit("MCS", popsize)

            current_mse = global_objective_function(xk, *args_for_objective)

            if current_mse < worker.best_candidate["fun"]:
                worker.best_candidate["fun"] = current_mse

                worker.best_candidate["x"] = xk.copy()

            if worker.iteration_count % 5 == 0:
                worker.progress.emit(
                    {
                        "params": xk,
                        "mse": current_mse,
                        "iteration": worker.iteration_count,
                    }
                )

            now = time.time()

            if now - worker._last_live_emit_time >= 2.0 and worker.best_candidate["x"] is not None:
                worker._last_live_emit_time = now

                worker.progress.emit(
                    {
                        "params": worker.best_candidate["x"].copy(),
                        "mse": worker.best_candidate["fun"],
                        "iteration": worker.iteration_count,
                    }
                )

        bounds = p["bounds"]

        max_workers = p.get("workers", 1)

        if max_workers > 1:
            from concurrent.futures import ThreadPoolExecutor

            class ThreadMap:
                def __init__(self, ex) -> None:

                    self.ex = ex

                def __call__(self, func, iterabl) -> list:

                    return list(self.ex.map(func, iterabl))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                result = scipy.optimize.differential_evolution(
                    global_objective_function,
                    bounds,
                    args=args_for_objective,
                    popsize=p["popsize"],
                    maxiter=p["maxiter"],
                    tol=p["tol"],
                    mutation=(p["mutation_min"], p["mutation_max"]),
                    recombination=p["recombination"],
                    updating="deferred",
                    workers=ThreadMap(executor),
                    callback=callback,
                    disp=False,
                )

        else:
            result = scipy.optimize.differential_evolution(
                global_objective_function,
                bounds,
                args=args_for_objective,
                popsize=p["popsize"],
                maxiter=p["maxiter"],
                tol=p["tol"],
                mutation=(p["mutation_min"], p["mutation_max"]),
                recombination=p["recombination"],
                updating=p["updating"],
                workers=1,
                callback=callback,
                disp=False,
            )

        if hasattr(result, "nfev") and result.nfev > 0:
            batches = result.nfev // 100

            if batches > 0:
                worker.stats_update.emit("SP", batches * 100)

            remaining = result.nfev % 100

            if remaining > 0:
                worker.stats_update.emit("SP", remaining)

        worker.finished.emit({"result": result, "params": p})

    except StopIteration as e:
        if worker.best_candidate["x"] is not None:
            from scipy.optimize import OptimizeResult

            dummy_res = OptimizeResult(
                x=worker.best_candidate["x"],
                fun=worker.best_candidate["fun"],
                nfev=worker.evaluation_count,
                message="Stopped by user",
                success=True,
            )

            worker.finished.emit({"result": dummy_res, "params": p})

        else:
            worker.error.emit(str(e))

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logging.error(f"Optimization worker error: {e}", exc_info=True)

        worker.error.emit(f"Error in optimization worker:\n{traceback.format_exc()}")


# BaseBeamAnalysisWorker removed (Dead Code)


@dataclass(frozen=True)
class MetalJobSpec:
    """Declarative description of a METAL job (SINGLE vs BILAYER).

    **P3 scaffold** — the ultimate goal is to fuse the 4 remaining duplicated
    hooks (``on_file_loaded``, ``on_optimization_finished``, ``on_beam_finished``,
    ``export_results``) between :class:`CertusMetalSingleApp` and
    :class:`CertusMetalBilayerApp` by parameterising ``MetalBaseApp`` with a
    :class:`MetalJobSpec` instance. See audit §A1 for the full plan.

    For now this dataclass documents the axis of variation; actual fusion is
    deferred until METAL GUI tests can validate behaviour on real datasets
    (Gaussian bands SINGLE vs DBSCAN multi-valley BILAYER).

    Attributes
    ----------
    variant : str
        ``"single"`` or ``"bilayer"``.
    n_layers : int
        Number of metal layers handled by the worker (1 for SINGLE, 2 for
        BILAYER).
    report_sheets : tuple[str, ...]
        Ordered list of Excel sheet names produced by ``export_results``.
        Used by the future ``build_standard_report`` adoption path.
    beam_analysis_kind : str
        ``"gaussian_bands"`` (SINGLE) or ``"dbscan_multi_valleys"`` (BILAYER).
    extra : dict[str, Any]
        Free-form bag for per-variant extras (bound prep, fit labels, ...).
    """

    variant: str
    n_layers: int
    report_sheets: tuple[str, ...] = ()
    beam_analysis_kind: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# Canonical specs used when P3 fusion lands. Kept here so the two METAL apps
# can import them directly:
#   ``from certus_metal_common import METAL_SINGLE_SPEC, METAL_BILAYER_SPEC``
METAL_SINGLE_SPEC = MetalJobSpec(
    variant="single",
    n_layers=1,
    report_sheets=("Summary", "Fit Parameters", "Reflectance"),
    beam_analysis_kind="gaussian_bands",
)

METAL_BILAYER_SPEC = MetalJobSpec(
    variant="bilayer",
    n_layers=2,
    report_sheets=("Summary", "Fit Parameters", "Reflectance", "Layer Interactions"),
    beam_analysis_kind="dbscan_multi_valleys",
)


class MetalBaseApp(CertusBaseApp):
    """Base Class for Metal Characterization Apps (Single & Bilayer).

    Provides shared UI layout, file loading, and export logic."""

    # Module ID for help (override in subclass)

    MODULE_ID = "METAL"

    def _uninstall_all_skeletons(self) -> None:
        """Uninstall all skeleton overlays from plots."""
        try:
            from certus_ui import remove_skeleton_loader
            for plot_attr in ["mse_plot", "reflectance_plot", "diel_plot"]:
                p = getattr(self, plot_attr, None)
                if p:
                    remove_skeleton_loader(p)
        except Exception as e:
            logging.getLogger("CERTUS").debug("Failsafe removing skeleton loaders: %s", e)

    def __init__(self, app_name="CERTUS-METAL", app_title="Metal Characterization") -> None:

        super().__init__()

        self.APP_NAME = app_name

        self.APP_TITLE = app_title

        # Shared State

        self.target_data = None

        self.mse_data = {"iterations": [], "errors": []}

        self.rmse_history = []

        self._last_target_file = None

        # Setup Logger

        self._setup_logger(self.APP_NAME)

        # Apply Theme (Shared styles)

        self._apply_theme()

        # Build UI

        self.setup_ui()

        # Finalize

        self._finalize_init()

        # Initialize detached plots tracking

        self.detached_plot_windows = {}

    def _load_defaults(self) -> None:
        """Load default values for METAL applications"""

        # Reset file selection

        self.target_data = None

        self._last_target_file = None

        # Reset optimization data

        self.mse_data = {"iterations": [], "errors": []}

        self.rmse_history = []

        self.beam_stats = None

        # Reset UI elements

        if hasattr(self, "btn_load"):
            # Reset file selection display

            pass  # File button doesn't show filename

        # Reset parameter fields to defaults

        if hasattr(self, "widgets"):
            # Common metal defaults

            default_params = {"eM_min": "5.0", "eM_max": "50.0", "eL_nominal": "100.0", "eL_variation": "20.0"}

            for param, default_value in default_params.items():
                if param in self.widgets:
                    self.widgets[param].setText(default_value)

    def _create_labeled_input(self, label_text, widget, tooltip_text=None) -> Any:
        """Creates a horizontal layout with Label [Info] Widget (Shared)"""

        layout = QHBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(5)

        lbl = QLabel(label_text)

        if tooltip_text:
            lbl.setToolTip(tooltip_text)

            widget.setToolTip(tooltip_text)

        layout.addWidget(lbl)

        if tooltip_text:
            # Simple info icon

            info_btn = QPushButton("?")

            info_btn.setFixedSize(16, 16)

            info_btn.setToolTip(tooltip_text)

            info_btn.setStyleSheet(
                f"border-radius: 8px; background: {CertusTheme.SECONDARY}; color: white; font-weight: bold; border: none;"
            )

            layout.addWidget(info_btn)

        layout.addStretch()

        layout.addWidget(widget)

        return layout

    def update_lambda_filters(self) -> None:
        """Updates wavelength filters (Shared)"""

        if self.target_data is not None:
            # handle both dict (SINGLE) and array (BILAYER potentially)

            # MetalBaseApp.load_target_file stores numpy array in self.target_data usually?

            # Wait, SINGLE stores dict {'lambda':..., 'R':...}

            # BILAYER stores numpy array via on_file_loaded hook?

            # Let's verify SINGLE vs BILAYER storage.

            # SINGLE: self.target_data = {'lambda': wls, 'R': ...}

            # BILAYER: self.target_data is stored as numpy array in base, but maybe overwritten?

            # Let's check BILAYER again.

            # BILAYER on_file_loaded: (data) -> assigns to self.target_data['lambda']? No.

            # Standardization required.

            # SINGLE uses dict. BILAYER uses?

            # Logic needs to handle both or standardize.

            # For now, safe check:

            l_data = None

            if isinstance(self.target_data, dict) and "lambda" in self.target_data:
                l_data = self.target_data["lambda"]

            elif isinstance(self.target_data, np.ndarray) and len(self.target_data.shape) > 1:
                l_data = self.target_data[:, 0]

            if l_data is not None:
                min_l = l_data.min()

                max_l = l_data.max()

                if "lmin_filter" in self.widgets:
                    self.widgets["lmin_filter"].setText(f"{min_l:.1f}")

                if "lmax_filter" in self.widgets:
                    self.widgets["lmax_filter"].setText(f"{max_l:.1f}")

    def _get_param_bounds(self, name) -> tuple:
        """Gets parameter bounds (Shared)"""

        # Assumes self.widgets[name_min] and self.widgets[name_max] exist

        p_min = float(self.widgets[f"{name}_min"].text())

        p_max = float(self.widgets[f"{name}_max"].text())

        if p_min == p_max:
            p_max += 1e-9

        return (p_min, p_max)

    def detach_current_plot(self) -> None:
        """Detaches current plot (Shared)"""

        current_widget = self.tabs.currentWidget()

        if current_widget is None:
            return

        current_index = self.tabs.currentIndex()

        plot_name = f"plot_{current_index}"

        plot_title = self.tabs.tabText(current_index)

        if plot_name in self.detached_plot_windows:
            if self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

        try:
            # Shared helper for cloning

            detached_plot_copy = clone_plot_widget(current_widget, title_override=plot_title)

            if detached_plot_copy is None:
                return  # Or log error

            detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

            detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = detached_window

            detached_window.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error creating detached window: {e}", exc_info=True)

    def reattach_plot(self, plot_name: str) -> None:
        """Reattaches detached plot (Shared)"""

        if plot_name in self.detached_plot_windows:
            detached_window = self.detached_plot_windows[plot_name]

            detached_window.deleteLater()

            del self.detached_plot_windows[plot_name]

    def _apply_theme(self) -> None:
        """Applies Certus theme with shared overrides"""

        plots = [
            getattr(self, "reflectance_plot", None),
            getattr(self, "mse_plot", None),
            getattr(self, "diel_plot", None),
            getattr(self, "clues_plot", None),
        ]

        # Filter None

        plots = [p for p in plots if p is not None]

        apply_certus_theme(
            self,
            plots=plots,
            overrides=f"""
            {build_premium_overrides()}

                /* METAL Shared Styles */

                QPushButton {{

                    border-radius: 4px;

                    padding: 4px 10px;

                    font-size: 13px;

                }}

                QPushButton:hover {{

                    border-color: {CertusTheme.SECONDARY};

                }}

            """,
        )

        # Update extra widgets if they exist

        if hasattr(self, "progress_widget"):
            self.progress_widget.style().unpolish(self.progress_widget)

            self.progress_widget.style().polish(self.progress_widget)

    def setup_ui(self) -> None:
        """Builds standard METAL layout (Splitter: Control | Results)"""

        # Main Splitter

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_split = self.main_splitter

        self.setCentralWidget(self.main_splitter)

        # === LEFT PANEL ===

        left_panel_widget = QWidget()

        left_panel_widget.setMinimumWidth(280)

        left_panel_outer = QVBoxLayout(left_panel_widget)

        left_panel_outer.setContentsMargins(0, 0, 0, 0)

        left_panel_outer.setSpacing(0)

        # Header (Pinned outside scroll)

        self._create_header(left_panel_outer)

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel_outer.addWidget(scroll_area)

        left_panel = QWidget()

        scroll_area.setWidget(left_panel)

        left_layout = QVBoxLayout(left_panel)

        left_layout.setContentsMargins(0, 0, 4, 0)

        left_layout.setSpacing(8)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Load measurement  2 Configure metal model  3 Run optimization  4 Inspect plots")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        workflow_card.body.addWidget(workflow_hint)

        left_layout.addWidget(workflow_card)

        self.params_widget = QWidget()

        self.params_layout = QGridLayout(self.params_widget)

        self.params_layout.setSpacing(6)

        self.params_layout.setContentsMargins(0, 0, 0, 0)

        self._setup_parameter_grid(self.params_layout)

        params_card = CertusCard("Parameters")

        params_card.body.setContentsMargins(10, 8, 10, 10)

        params_card.body.addWidget(self.params_widget)

        left_layout.addWidget(params_card)

        self._create_action_buttons(left_layout)

        left_layout.addStretch()

        self.main_splitter.addWidget(left_panel_widget)

        # === RIGHT PANEL (Plots) ===

        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabs Container

        plot_container = QWidget()

        plot_layout = QVBoxLayout(plot_container)

        plot_layout.setContentsMargins(0, 0, 0, 0)

        # Plot Header (Detach)

        plot_header = QWidget()

        plot_header.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        ph_layout = QHBoxLayout(plot_header)

        ph_layout.setContentsMargins(6, 2, 6, 2)

        detach_btn = create_styled_button("⬡  Detach Plot", "secondary")

        detach_btn.setFixedHeight(24)

        detach_btn.setToolTip("Detach the current plot tab into a separate floating window.")

        detach_btn.clicked.connect(self.detach_current_plot)

        ph_layout.addWidget(detach_btn)

        ph_layout.addStretch()

        plot_layout.addWidget(plot_header)

        # Tabs

        self.tabs = QTabWidget()

        self._setup_plots()  # Subclass defines plots

        plot_layout.addWidget(self.tabs)

        self.right_splitter.addWidget(plot_container)

        # Logs

        self.log_container = QWidget()

        self.log_container.setVisible(False)

        log_layout = QVBoxLayout(self.log_container)

        log_layout.setContentsMargins(0, 0, 0, 0)

        self.log_text = create_log_widget(visible=True)

        log_layout.addWidget(self.log_text)

        self.right_splitter.addWidget(self.log_container)

        self.right_splitter.setSizes([800, 0])

        self.right_splitter.setCollapsible(0, False)

        self.main_splitter.addWidget(self.right_splitter)

        self.main_splitter.setSizes([380, 1020])

        self._create_status_bar()

        install_standard_shortcuts(
            self,
            run=getattr(self, "start_optimization", None),
            stop=getattr(self, "stop_optimization", None),
            help=lambda: open_documentation(getattr(self, "MODULE_ID", "CERTUS_METAL")),
            toggle_logs=lambda: self.btn_details.setChecked(not self.btn_details.isChecked()),
        )

        def _on_data_drop(paths) -> None:
            if paths and hasattr(self, "load_target_file"):
                self.load_target_file(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_data_drop, extensions=("csv", "xlsx", "xls", "txt"))

    def _get_log_widget(self) -> Any:
        """Override to return the log text widget."""

        return getattr(self, "log_text", None)

    def _create_header(self, layout) -> None:
        """Shared header with Logo & Help using standardized widget"""

        # Pass self.APP_TITLE as subtitle if desired, or a generic one

        header = create_header_logo_widget(
            title_text=self.APP_NAME.replace("CERTUS_", "").replace("_", " "),
            subtitle_text=self.APP_TITLE,
            module_name=self.MODULE_ID,
        )

        self.btn_theme = CertusThemeToggle(header)

        header.layout().addWidget(self.btn_theme)

        layout.addWidget(header)

    def _setup_parameter_grid(self, layout) -> None:
        """Override to add param groups"""

        pass

    def _setup_plots(self) -> None:
        """Override to add tabs"""

        pass

    def _create_action_buttons(self, layout) -> None:
        """Start/Stop/Details"""

        container = QVBoxLayout()

        r1 = QHBoxLayout()

        self.btn_run = QPushButton("▶  Start")
        self.btn_run.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_run.setFixedHeight(36)

        self.btn_run.setToolTip("Start the differential evolution optimization to extract metal optical constants.")

        self.btn_run.clicked.connect(self.start_optimization)  # Subclass must implement start_optimization

        r1.addWidget(self.btn_run)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName(OBJ.DANGER_BUTTON)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_stop.setFixedHeight(36)

        self.btn_stop.setEnabled(False)

        self.btn_stop.setToolTip("Stop the running optimization and keep the best result found so far.")

        self.btn_stop.clicked.connect(self.stop_optimization)

        r1.addWidget(self.btn_stop)

        container.addLayout(r1)

        # Beam Analysis Button (Subclasses enable it)

        try:
            self.btn_beam = QPushButton("Beam Analysis")

            beam_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)

            self.btn_beam.setIcon(beam_icon)

        except (ImportError, AttributeError):
            self.btn_beam = QPushButton("Beam Analysis")

        self.btn_beam.setFixedHeight(30)

        self.btn_beam.setEnabled(False)  # Disabled until optimization finishes

        self.btn_beam.setToolTip(
            "Run Beam Analysis: scan thickness (eM) around the optimum to map the\n"
            "MSE valley and assess solution uniqueness."
        )

        self.btn_beam.setStyleSheet(
            f"background: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN}; border: 1px solid {CertusTheme.BORDER}; border-radius: 4px;"
        )

        # Connect to hypothetical handler (subclass must implement or crash/noop)

        def _start_beam_analysis_if_available(*_args) -> None:
            getattr(self, "start_beam_analysis", lambda: None)()

        self.btn_beam.clicked.connect(_start_beam_analysis_if_available)

        action_bar = CertusActionBar()

        action_bar.add_widget(self.btn_beam)

        self.btn_details = QPushButton("Show Details")

        self.btn_details.setCheckable(True)

        self.btn_details.setToolTip("Show or hide the computation log panel.")

        self.btn_details.clicked.connect(self.on_toggle_details)

        action_bar.add_widget(self.btn_details)

        from certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)

        action_bar.add_widget(self.clear_btn)

        action_bar.add_stretch()

        container.addWidget(action_bar)

        layout.addLayout(container)

    def on_toggle_details(self, checked) -> None:

        self.log_container.setVisible(checked)

        h = self.right_splitter.height()

        if checked:
            self.right_splitter.setSizes([int(h * 0.8), int(h * 0.2)])

        else:
            self.right_splitter.setSizes([h, 0])

    # === SHARED UI COMPONENT FACTORIES ===

    def _create_group_box(self, title) -> tuple:

        c = CertusCard(title)

        l = c.body

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        return c, l

    def _create_input_group(self) -> Any:

        c, l = self._create_group_box("Input Data")

        self.btn_load = QPushButton(" Load File...")

        self.btn_load.setToolTip(
            "Load a data file (CSV or Excel) containing columns:\n"
            "lambda (nm), R, [T], [Rback]  percentage or 01 scale accepted."
        )

        self.btn_load.clicked.connect(self.load_target_file)

        l.addWidget(self.btn_load)

        self.lbl_file = QLabel("No file loaded")

        self.lbl_file.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        l.addWidget(self.lbl_file)

        fl = QGridLayout()

        fl.addWidget(QLabel("lambda min:"), 0, 0)

        self.widgets["lmin_filter"] = QLineEdit()

        self.widgets["lmin_filter"].setToolTip(
            "Minimum wavelength (nm) used for fitting. Rows below this value are excluded."
        )

        fl.addWidget(self.widgets["lmin_filter"], 0, 1)

        fl.addWidget(QLabel("lambda max:"), 1, 0)

        self.widgets["lmax_filter"] = QLineEdit()

        self.widgets["lmax_filter"].setToolTip(
            "Maximum wavelength (nm) used for fitting. Rows above this value are excluded."
        )

        fl.addWidget(self.widgets["lmax_filter"], 1, 1)

        l.addLayout(fl)

        return c

    def _create_output_group(self) -> Any:

        c = CertusCard("Output")

        l = QGridLayout()

        l.setContentsMargins(8, 12, 8, 8)

        c.body.addLayout(l)

        self.widgets["excel_filename"] = QLineEdit(DEFAULT_EXCEL_FILENAME)

        self.widgets["excel_filename"].setToolTip("Name of the Excel output file. Written to the reports/ directory.")

        l.addWidget(QLabel("File:"), 0, 0)

        l.addWidget(self.widgets["excel_filename"], 0, 1)

        return c

    def _create_physical_params_group(self, show_el: bool = False, el_defaults: tuple = ("900", "20")) -> CertusCard:
        """

        Creates standardized Physical Parameters group.

        Args:

            show_el: If True, includes eL (dielectric layer) parameters

            el_defaults: Default values for (eL_nominal, eL_variation)

        Returns:

            CertusCard with configured inputs stored in self.widgets

        """

        c, l = self._create_group_box("Physical Parameters")

        # eM (Metal thickness)

        self.widgets["eM_min"] = QLineEdit(str(DEFAULT_EM_MIN))

        self.widgets["eM_max"] = QLineEdit(str(DEFAULT_EM_MAX))

        row = QHBoxLayout()

        row.addWidget(QLabel("eM min (nm):"))

        row.addWidget(self.widgets["eM_min"])

        row.addWidget(QLabel("max:"))

        row.addWidget(self.widgets["eM_max"])

        l.addLayout(row)

        # Optional eL (Dielectric layer - for BILAYER)

        if show_el:
            self.widgets["eL_nominal"] = QLineEdit(el_defaults[0])

            self.widgets["eL_variation"] = QLineEdit(el_defaults[1])

            row2 = QHBoxLayout()

            row2.addWidget(QLabel("eL Nominal (nm):"))

            row2.addWidget(self.widgets["eL_nominal"])

            row2.addWidget(QLabel("+/-"))

            row2.addWidget(self.widgets["eL_variation"])

            l.addLayout(row2)

        return c

    def _create_material_params_group(
        self, show_diel_model: bool = False, substrate_options: list = None
    ) -> CertusCard:
        """

        Creates standardized Material Parameters group (Spline knots).

        Args:

            show_diel_model: If True, includes dielectric model inputs (n_inf, A)

            substrate_options: List of substrate names for combo box

        Returns:

            CertusCard with configured inputs stored in self.widgets

        """

        c, l = self._create_group_box("Material Parameters")

        # Spline Knots

        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Knots:"))

        self.widgets["num_knots"] = QLineEdit(str(DEFAULT_NUM_KNOTS))

        self.widgets["num_knots"].setFixedWidth(50)

        row1.addWidget(self.widgets["num_knots"])

        row1.addWidget(QLabel("n/k range:"))

        self.widgets["nk_min"] = QLineEdit(str(DEFAULT_NK_MIN))

        self.widgets["nk_min"].setFixedWidth(40)

        row1.addWidget(self.widgets["nk_min"])

        row1.addWidget(QLabel("-"))

        self.widgets["nk_max"] = QLineEdit(str(DEFAULT_NK_MAX))

        self.widgets["nk_max"].setFixedWidth(40)

        row1.addWidget(self.widgets["nk_max"])

        l.addLayout(row1)

        # Min knot distance

        row2 = QHBoxLayout()

        row2.addWidget(QLabel("Min knot distance (nm):"))

        self.widgets["min_knot_dist"] = QLineEdit(str(DEFAULT_MIN_KNOT_DISTANCE))

        self.widgets["min_knot_dist"].setFixedWidth(60)

        row2.addWidget(self.widgets["min_knot_dist"])

        row2.addStretch()

        l.addLayout(row2)

        # Optional Dielectric model (for BILAYER)

        if show_diel_model:
            row3 = QHBoxLayout()

            row3.addWidget(QLabel("n∞:"))

            self.widgets["n_inf"] = QLineEdit("1.46")

            self.widgets["n_inf"].setFixedWidth(50)

            row3.addWidget(self.widgets["n_inf"])

            row3.addWidget(QLabel("A (nm2):"))

            self.widgets["A_coeff"] = QLineEdit("3500")

            self.widgets["A_coeff"].setFixedWidth(60)

            row3.addWidget(self.widgets["A_coeff"])

            row3.addStretch()

            l.addLayout(row3)

        # Optional substrate selector

        if substrate_options:
            row4 = QHBoxLayout()

            row4.addWidget(QLabel("substrate:"))

            self.widgets["substrate"] = QComboBox()

            self.widgets["substrate"].addItems(substrate_options)

            row4.addWidget(self.widgets["substrate"])

            row4.addStretch()

            l.addLayout(row4)

        return c

    def _create_live_params_group(self) -> CertusCard:
        """

        Creates standardized Live Parameters display group (updated during optimization).

        Returns:

            CertusCard with QLabel widgets stored in self.widgets

        """

        c, l = self._create_group_box("Live Parameters")

        # eM display

        row1 = QHBoxLayout()

        row1.addWidget(QLabel("eM:"))

        self.widgets["live_eM"] = QLabel("--")

        self.widgets["live_eM"].setStyleSheet(f"font-weight: bold; color: {CertusTheme.PRIMARY};")

        row1.addWidget(self.widgets["live_eM"])

        row1.addWidget(QLabel("nm"))

        row1.addStretch()

        l.addLayout(row1)

        # MSE display

        row2 = QHBoxLayout()

        row2.addWidget(QLabel("MSE:"))

        self.widgets["live_MSE"] = QLabel("--")

        self.widgets["live_MSE"].setStyleSheet(f"font-weight: bold; color: {CertusTheme.SUCCESS};")

        row2.addWidget(self.widgets["live_MSE"])

        row2.addStretch()

        l.addLayout(row2)

        # Iterations display

        row3 = QHBoxLayout()

        row3.addWidget(QLabel("Iterations:"))

        self.widgets["live_iter"] = QLabel("--")

        row3.addWidget(self.widgets["live_iter"])

        row3.addStretch()

        l.addLayout(row3)

        return c

    def _create_status_bar(self) -> None:

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.status_label = CertusStatusPill("Ready", "ready")

        self.status_bar.addWidget(self.status_label, 1)

        self.stat_counters = {"MS": 0, "MCS": 0, "SP": 0}

        self.stats_label = QLabel(" 0  |  0  |   0")

        self.stats_label.setToolTip(
            " Objective function evaluations  |   Monte Carlo / iterations  |   Spectral points processed"
        )

        self.status_bar.addPermanentWidget(self.stats_label)

        self.progress_widget = EnhancedProgressWidget()

        self.status_bar.addPermanentWidget(self.progress_widget)

        self.btn_theme = CertusThemeToggle(self)

        self.status_bar.addPermanentWidget(self.btn_theme)

    def load_target_file(self, filepath=None) -> None:
        """robust loading logic (Shared)"""

        if filepath is None or isinstance(filepath, bool):
            filepath, df = open_data_file_and_read(
                self,
                "Open Reflectance File",
                DATA_FILES_FILTER_EXTENDED,
            )

            if filepath is None:
                return

        else:
            df = read_data_file_robust(filepath)

        if not filepath:
            return

        try:
            # Basic validation

            if len(df.columns) < 2:
                raise ValueError("Files needs >= 2 cols")

            # Store raw data (subclass processes it)

            self._last_target_file = filepath

            self.lbl_file.setText(Path(filepath).name)

            # Common processing: wavelengths

            data = df.to_numpy()

            data = data[data[:, 0].argsort()]  # Sort lambda

            self.target_data = data  # Store raw

            self.logger.info(f"Loaded {filepath}: {len(data)} points")

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                n_rows = int(data.shape[0]) if isinstance(data, np.ndarray) else 0

                lmin = float(np.nanmin(data[:, 0])) if n_rows > 0 else float("nan")

                lmax = float(np.nanmax(data[:, 0])) if n_rows > 0 else float("nan")

                _sub_w = self.widgets.get("substrate")
                substrate_txt = (_sub_w.currentText() if _sub_w is not None else "(unknown)").upper()

                _ncols = int(data.shape[1]) if isinstance(data, np.ndarray) and data.ndim == 2 else 0
                faces_txt = f"{_ncols - 1} column(s)" if _ncols > 1 else "(unknown)"

                summary = build_summary_plain_text(
                    "CERTUS METAL - Load Summary",
                    [
                        f"File: {Path(filepath).resolve(strict=False)}",
                        "",
                        "General",
                        f"SUBSTRATE: {substrate_txt}",
                        f"FACES: {faces_txt}",
                        (f"Rows: {n_rows}", n_rows <= 0),
                        "",
                        "Data",
                        (
                            f"Columns: {int(data.shape[1]) if isinstance(data, np.ndarray) and data.ndim == 2 else 0}",
                            False,
                        ),
                        (
                            f"Wavelength range: [{lmin:.1f}, {lmax:.1f}] nm",
                            not (np.isfinite(lmin) and np.isfinite(lmax) and lmax > lmin),
                        ),
                    ],
                )

                show_load_summary_dialog(self, "METAL Load Summary", summary)

            # Subclass hook

            if hasattr(self, "on_file_loaded"):
                self.on_file_loaded(data)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def update_stats_display(self) -> None:

        self.stats_label.setText(
            f" {format_count_kmg(self.stat_counters['MS'])}  |  {format_count_kmg(self.stat_counters['MCS'])}  |   {format_count_kmg(self.stat_counters['SP'])}"
        )

    def on_stats_update(self, ctype, inc) -> None:

        if ctype in self.stat_counters:
            self.stat_counters[ctype] += inc

            self.update_stats_display()

    def on_optimization_error(self, error_message) -> None:
        """Handles optimization error"""
        self._uninstall_all_skeletons()
        self.progress_widget.stop("Error")
        QMessageBox.critical(self, "Optimization Error", error_message)
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_beam_error(self, error_message) -> None:
        """Handles beam analysis error"""
        self._uninstall_all_skeletons()
        self.progress_widget.stop("Beam Error")
        QMessageBox.critical(self, "Beam Analysis Error", error_message)
        self.btn_run.setEnabled(True)
        self.btn_beam.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def closeEvent(self, event) -> None:
        """Clean up all worker threads on close."""

        for attr in ("worker", "beam_worker"):
            w = getattr(self, attr, None)

            if w and hasattr(w, "stop"):
                w.stop()

        for attr in ("optimization_thread", "beam_thread"):
            t = getattr(self, attr, None)

            if t is not None:
                try:
                    if t.isRunning():
                        t.quit()

                        if not t.wait(2000):
                            logging.critical(
                                f"{attr} did not stop within 2s in closeEvent - skipping terminate() to avoid unsafe thread kill."
                            )

                except RuntimeError:
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        super().closeEvent(event)

    # --- Config hooks (unified contract) ---
    #
    # ``_collect_config`` / ``_apply_config`` are the names used by
    # :class:`CertusBaseApp` (``certus_ui.py``). METAL historically used
    # ``_get_config_dict`` / ``_apply_config_dict``; both names are
    # supported so existing subclasses (METAL_SINGLE / METAL_BILAYER) that
    # override the legacy names keep working while new code can rely on the
    # unified contract.

    def _get_config_dict(self) -> dict:
        """Legacy alias for :meth:`_collect_config` (kept for METAL subclasses)."""

        return {}

    def _apply_config_dict(self, config) -> None:
        """Legacy alias for :meth:`_apply_config` (kept for METAL subclasses)."""

        pass

    def _collect_config(self) -> Any:
        """Unified config collector. Defaults to :meth:`_get_config_dict` so

        subclasses overriding the legacy hook keep working transparently."""

        config = self._get_config_dict()

        if getattr(self, "target_data", None) is not None:
            config["target_file"] = getattr(self, "_last_target_file", "")

        if hasattr(self, "final_results") and self.final_results is not None:
            result = self.final_results["result"]

            config["optimization_result"] = {
                "mse": float(result.fun),
                "params": result.x.tolist(),
                "nfev": int(result.nfev) if hasattr(result, "nfev") else 0,
            }

        return config

    def _apply_config(self, config) -> None:
        """Unified config applier. Defaults to :meth:`_apply_config_dict` so

        subclasses overriding the legacy hook keep working transparently."""

        if "physical_params" not in config:
            raise ValueError("Invalid configuration file format.")

        if "excel_filename" in self.widgets:
            self.widgets["excel_filename"].setText(config.get("excel_filename", DEFAULT_EXCEL_FILENAME))

        self._apply_config_dict(config)

        filt = config.get("filters", {})

        if "lmin_filter" in self.widgets:
            self.widgets["lmin_filter"].setText(str(filt.get("lmin_filter", 400)))

        if "lmax_filter" in self.widgets:
            self.widgets["lmax_filter"].setText(str(filt.get("lmax_filter", 1000)))

        self.update_lambda_filters()

        target_file = config.get("target_file", "")

        if target_file and Path(target_file).exists():
            self.load_target_file(target_file)

        elif target_file:
            self.logger.warning(f"Target file from config not found: {target_file}")

    def _post_save_config(self, filename: str) -> None:

        QMessageBox.information(self, "Save Successful", f"Configuration saved to\n{filename}")

    def _post_load_config(self, filename: str, config: dict) -> None:

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            p = config.get("physical_params", {}) if isinstance(config, dict) else {}

            _sub_w = self.widgets.get("substrate")
            substrate_txt = (_sub_w.currentText() if _sub_w is not None else "(unknown)").upper()

            target_file = config.get("target_file", "")

            summary = build_summary_plain_text(
                "CERTUS METAL - Config Summary",
                [
                    f"File: {Path(filename).resolve(strict=False)}",
                    "",
                    "General",
                    f"SUBSTRATE: {substrate_txt}",
                    f"Target file from config: {target_file or '(none)'}",
                    (
                        f"Target file exists: {'yes' if (target_file and Path(target_file).exists()) else 'no'}",
                        bool(target_file) and not Path(target_file).exists(),
                    ),
                    "",
                    "Compatibility checks",
                    f"Physical params keys: {len(p)}",
                    (
                        f"Optimization params present: {'yes' if 'optimization_params' in config else 'no'}",
                        "optimization_params" not in config,
                    ),
                    (f"Filter params present: {'yes' if 'filters' in config else 'no'}", "filters" not in config),
                ],
            )

            show_load_summary_dialog(self, "METAL Config Summary", summary)

        QMessageBox.information(self, "Load Successful", f"Configuration loaded from\n{filename}")

    # Abstract methods

    def start_optimization(self) -> None:

        raise NotImplementedError

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""
        from certus_ui import copy_app_logs_to_clipboard
        if copy_app_logs_to_clipboard(self) and hasattr(self, "status_label"):
            self.status_label.setText("Logs copied to clipboard!")

    def _metal_start_optimization(
        self,
        worker_class: type[QObject],
        build_bounds_fn: Callable[[dict, np.ndarray], np.ndarray],
        build_params_fn: Optional[Callable[[dict], None]] = None,
        before_run_fn: Optional[Callable[[dict], bool]] = None,
    ) -> None:
        """Shared logic for starting metal optimization."""
        if getattr(self, "optimization_thread", None) is not None:
            try:
                if self.optimization_thread.isRunning():
                    if getattr(self, "worker", None):
                        self.worker.stop()
                    self.optimization_thread.quit()
                    if not self.optimization_thread.wait(2000):
                        logging.critical(
                            "Optimization thread did not stop within 2s - skipping terminate() to avoid unsafe thread kill."
                        )
            except RuntimeError:
                pass
            self.optimization_thread = None
            self.worker = None

        if not self.target_data:
            from certus_errors import show_error
            show_error(self, "optim_no_data")
            return

        try:
            p = {k: v.text() for k, v in self.widgets.items() if isinstance(v, QLineEdit)}
            params = {k: float(v) for k, v in p.items() if k not in ["excel_filename"]}
            
            params.update(
                {
                    "excel_filename": self.widgets["excel_filename"].text(),
                    "popsize": DEFAULT_POPSIZE,
                    "maxiter": DEFAULT_MAXITER,
                    "tol": DEFAULT_TOL,
                    "mutation_min": DEFAULT_MUTATION_MIN,
                    "mutation_max": DEFAULT_MUTATION_MAX,
                    "recombination": DEFAULT_RECOMBINATION,
                    "updating": DEFAULT_UPDATING,
                    "workers": DEFAULT_WORKERS,
                }
            )

            if build_params_fn:
                build_params_fn(params)

            mask = (self.target_data["lambda"] >= params["lmin_filter"]) & (
                self.target_data["lambda"] <= params["lmax_filter"]
            )
            target_lambda_filtered = self.target_data["lambda"][mask]
            
            params["target_lambda"] = target_lambda_filtered
            params["target_r"] = self.target_data["R"][mask]
            
            if "T" in self.target_data:
                params["target_t"] = self.target_data["T"][mask]
            if "Rback" in self.target_data:
                params["target_rb"] = self.target_data["Rback"][mask]

            if before_run_fn and not before_run_fn(params):
                return

            bounds = build_bounds_fn(params, target_lambda_filtered)
            params["bounds"] = bounds

        except (ValueError, KeyError) as e:
            QMessageBox.critical(self, "Parameter Error", f"Invalid value: {e}")
            return

        self.mse_data = {"iterations": [], "errors": []}
        self.mse_curve.setData([], [])
        if hasattr(self, "diel_curve"):
            self.diel_curve.setData([], [])

        for label in [
            "live_eM", "live_MSE", "live_eM_label", "live_eL_label",
            "live_n_infini_label", "live_A_diel_label", "live_mse_label"
        ]:
            if label in self.widgets:
                self.widgets[label].setText("...")

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self._last_worker_params = params.copy()
        self.optimization_thread = QThread()
        self.worker = worker_class(params)
        self.worker.moveToThread(self.optimization_thread)

        self.optimization_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_optimization_finished)
        self.worker.progress.connect(self.update_plots)
        self.worker.progress.connect(self._on_optim_progress)
        self.worker.error.connect(self.on_optimization_error)
        self.worker.stats_update.connect(self.on_stats_update)

        self.worker.finished.connect(self.optimization_thread.quit)
        self.worker.error.connect(self.optimization_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.optimization_thread.finished.connect(self.optimization_thread.deleteLater)

        self._optim_max_iter = params.get("maxiter", DEFAULT_MAXITER)
        self.progress_widget.start()
        self.optimization_thread.start()

        try:
            from certus_ui import install_skeleton_loader
            if hasattr(self, "mse_plot") and self.mse_plot:
                install_skeleton_loader(self.mse_plot, "chart")
            if hasattr(self, "reflectance_plot") and self.reflectance_plot:
                install_skeleton_loader(self.reflectance_plot, "chart")
            if hasattr(self, "diel_plot") and self.diel_plot:
                install_skeleton_loader(self.diel_plot, "chart")
        except Exception as e:
            logging.getLogger("CERTUS").debug("Failsafe installing skeleton loaders: %s", e)

        self.stat_counters = {"MS": 0, "MCS": 0, "SP": 0}
        self.update_stats_display()

    def stop_optimization(self) -> None:
        """Confirm-then-stop for optimization and beam analysis workers.

        Shared implementation used by both METAL_SINGLE and METAL_BILAYER.
        Subclasses can override ``_extra_stop_cleanup`` for app-specific
        post-stop logic.
        """

        self._uninstall_all_skeletons()

        if not confirm_stop_with_timeout(self):
            return

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped")

        logger = getattr(self, "logger", None)

        stop_worker_and_thread(
            getattr(self, "worker", None),
            getattr(self, "optimization_thread", None),
            timeout_ms=3000,
            logger=logger,
            label="Optimization thread",
        )
        stop_worker_and_thread(
            getattr(self, "beam_worker", None),
            getattr(self, "beam_thread", None),
            timeout_ms=3000,
            logger=logger,
            label="Beam analysis thread",
        )

        if hasattr(self, "btn_run"):
            self.btn_run.setEnabled(True)
        if hasattr(self, "btn_beam"):
            self.btn_beam.setEnabled(True)
        if hasattr(self, "btn_stop"):
            self.btn_stop.setEnabled(False)

        extra = getattr(self, "_extra_stop_cleanup", None)
        if callable(extra):
            extra()

    # --- Standard report adoption (P6, opt-in) -----------------------------
    #
    # ``export_via_builder`` lets METAL subclasses produce an Excel + HTML
    # report through the unified :func:`certus_data.build_standard_report`
    # instead of hand-rolling their own Excel writer + HTML generator. The
    # existing ``export_results`` implementations are preserved; new code or
    # migrations can call this helper directly.

    def export_via_builder(
        self,
        sections: list[ReportSection],
        *,
        excel_path: str | None = None,
        html_path: str | None = None,
        html_title: str | None = None,
    ) -> dict[str, bool]:
        """Build a standard report (Excel + HTML) from ``sections``."""

        title = html_title or f"{getattr(self, 'APP_TITLE', 'CERTUS')} — Report"
        try:
            self.set_validation_status("OK")
        except (RuntimeError, AttributeError, TypeError, ValueError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        run_manifest = None
        try:
            seed_val = None
            for _seed_candidate in (
                getattr(self, "run_seed", None),
                getattr(self, "random_seed", None),
                getattr(self, "ensemble_seed", None),
                getattr(self, "_loaded_config", {}).get("seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
                getattr(self, "_loaded_config", {}).get("random_seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
                getattr(self, "_loaded_config", {}).get("ensemble_seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
            ):
                if _seed_candidate is None:
                    continue
                try:
                    seed_val = int(_seed_candidate)
                    break
                except (TypeError, ValueError):
                    continue

            status_txt = str(getattr(self, "validation_status", "OK") or "OK")
            try:
                status_val = ValidationStatus(status_txt)
            except ValueError:
                status_val = ValidationStatus.OK
            svc = IndexFitService(runner=lambda _cfg: getattr(self, "_last_result", {}) or {})
            req = IndexFitRequest(
                config={
                    "module": str(getattr(self, "MODULE_ID", "CERTUS_METAL")),
                    "app_title": str(getattr(self, "APP_TITLE", "CERTUS METAL")),
                },
                source_paths=[
                    p
                    for p in (
                        str(getattr(self, "filename", "") or "").strip(),
                        str(getattr(self, "_last_config_file", "") or "").strip(),
                    )
                    if p
                ],
                seed=seed_val,
                app_id=str(getattr(self, "MODULE_ID", "CERTUS_METAL")),
                app_version=str(getattr(self, "MODULE_VERSION", "unknown")),
                warnings=list(getattr(self, "validation_warnings", []) or []),
                status=status_val,
            )
            run_manifest = svc.fit(req).manifest
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.warning("METAL manifest generation failed: %s", exc)
            run_manifest = None
        result = build_standard_report(
            sections,
            excel_path=excel_path,
            html_path=html_path,
            html_title=title,
            run_manifest=run_manifest,
            require_complete_manifest=True,
        )
        logger = getattr(self, "logger", None)
        if logger is not None:
            for kind, ok in result.items():
                target = excel_path if kind == "excel" else html_path
                if ok:
                    logger.info(f"Standard report {kind} written: {target}")
                else:
                    logger.warning(f"Standard report {kind} failed: {target}")
        return result

    @staticmethod
    def widget_to_b64(widget) -> str:
        """Capture a QWidget as a base64-encoded PNG string for HTML reports.

        Returns an empty string if the widget is None or does not support
        ``grab()`` (e.g. during headless / offscreen testing).
        """
        if widget is None:
            return ""
        try:
            from PyQt6.QtCore import QBuffer, QIODevice
            import base64

            img = widget.grab().toImage()
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            return base64.b64encode(buf.data()).decode()
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):  # noqa: BLE001 — QBuffer / grab may fail headless
            return ""
