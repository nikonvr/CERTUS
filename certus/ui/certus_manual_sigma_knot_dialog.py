from __future__ import annotations

import logging
import numpy as np
import pyqtgraph as pg

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from certus.ui.certus_ui import CertusScientificPlot, CertusTheme
from certus.ui.certus_ui_widgets_progress import EnhancedProgressWidget


_LOG = logging.getLogger("CERTUS")


def _sorted_xy(
    lam_nm: np.ndarray | None,
    values: np.ndarray | None,
    *,
    label: str = "series",
) -> tuple[np.ndarray, np.ndarray]:
    lam = np.asarray(lam_nm if lam_nm is not None else [], dtype=np.float64).ravel()
    val = np.asarray(values if values is not None else [], dtype=np.float64).ravel()
    n = int(min(lam.size, val.size))
    if n <= 0:
        _LOG.warning("Manual knots preview missing %s data (lambda=%d, values=%d)", label, int(lam.size), int(val.size))
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    lam = lam[:n]
    val = val[:n]
    mask = np.isfinite(lam) & np.isfinite(val)
    if not np.any(mask):
        _LOG.warning("Manual knots preview %s data has no finite samples (n=%d)", label, int(n))
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    lam = lam[mask]
    val = val[mask]
    order = np.argsort(lam, kind="mergesort")
    return lam[order], val[order]


class _LambdaKnotRow(QFrame):
    def __init__(
        self,
        lam_min_nm: float,
        lam_max_nm: float,
        initial_nm: float,
        on_remove,
        on_value_changed,
        on_select,
    ) -> None:
        super().__init__()
        self.preview_line: pg.InfiniteLine | None = None
        self.selection_label: pg.TextItem | None = None
        self.origin = "propose"
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_kind = QLabel("", self)
        layout.addWidget(self.lbl_kind)
        layout.addWidget(QLabel("lambda (nm)"))

        self.spin = QDoubleSpinBox(self)
        self.spin.setDecimals(4)
        self.spin.setRange(float(lam_min_nm), float(lam_max_nm))
        self.spin.setSingleStep(max(1.0, 0.01 * (float(lam_max_nm) - float(lam_min_nm))))
        self.spin.setValue(float(np.clip(initial_nm, lam_min_nm, lam_max_nm)))
        self.spin.valueChanged.connect(lambda _value: on_value_changed(self))
        self.spin.lineEdit().selectionChanged.connect(lambda: on_select(self))
        layout.addWidget(self.spin, 1)

        btn_remove = QPushButton("Remove", self)
        btn_remove.clicked.connect(lambda: on_remove(self))
        layout.addWidget(btn_remove)

    def set_kind(self, kind_label: str, *, color: str | None = None) -> None:
        txt = str(kind_label or "").strip()
        self.lbl_kind.setText(txt)
        self.origin = "preexistant" if "pre" in txt.lower() else "propose"
        if color:
            self.lbl_kind.setStyleSheet(f"color: {color}; font-weight: 600;")
        else:
            self.lbl_kind.setStyleSheet("")

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("QFrame { border: 2px solid #ffb347; border-radius: 4px; }")
        else:
            self.setStyleSheet("")


class ManualSigmaKnotDialog(QDialog):
    """Dialog for manual placement of extra knots on the lambda axis."""

    local_apply_requested = pyqtSignal(list, float)
    delta_preview_requested = pyqtSignal(float)
    auto_shift_requested = pyqtSignal()
    auto_repartition_log_requested = pyqtSignal()
    auto_repartition_sigma_requested = pyqtSignal()
    auto_clean_requested = pyqtSignal(float)
    force_clean_requested = pyqtSignal()
    auto_add_one_requested = pyqtSignal()
    recall_best_requested = pyqtSignal()
    recall_best_for_k_requested = pyqtSignal(int)
    stop_requested = pyqtSignal()

    def __init__(
        self,
        *,
        sigma_knots: np.ndarray,
        lam_model_nm: np.ndarray | None,
        y_model: np.ndarray | None,
        lam_measurement_nm: np.ndarray | None,
        y_measurement: np.ndarray | None,
        y_label: str,
        initial_delta_ns: float = 0.0,
        keep_open_on_local_apply: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Additional manual knots")
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(940, screen.width() - 40)
        h = min(700, screen.height() - 60)
        self.resize(w, h)

        self._base_sigma_knots = np.asarray(sigma_knots, dtype=np.float64).ravel().copy()
        self._base_lambda_knots_nm = np.sort(1.0 / np.maximum(self._base_sigma_knots, 1e-30))
        _LOG.info(
            "Manual knots dialog init | base_sigma=%d | lam_model=%d | y_model=%d | lam_meas=%d | y_meas=%d | keep_open=%s",
            int(self._base_sigma_knots.size),
            int(np.asarray(lam_model_nm if lam_model_nm is not None else [], dtype=np.float64).size),
            int(np.asarray(y_model if y_model is not None else [], dtype=np.float64).size),
            int(np.asarray(lam_measurement_nm if lam_measurement_nm is not None else [], dtype=np.float64).size),
            int(np.asarray(y_measurement if y_measurement is not None else [], dtype=np.float64).size),
            bool(keep_open_on_local_apply),
        )
        lam_candidates = [
            np.asarray(lam_model_nm if lam_model_nm is not None else [], dtype=np.float64).ravel(),
            np.asarray(lam_measurement_nm if lam_measurement_nm is not None else [], dtype=np.float64).ravel(),
            self._base_lambda_knots_nm,
        ]
        lam_non_empty = [arr[np.isfinite(arr)] for arr in lam_candidates if arr.size > 0]
        if lam_non_empty:
            self._lam_min_nm = float(min(np.min(arr) for arr in lam_non_empty))
            self._lam_max_nm = float(max(np.max(arr) for arr in lam_non_empty))
        else:
            self._lam_min_nm = 400.0
            self._lam_max_nm = 5000.0

        self._row_widgets: list[_LambdaKnotRow] = []
        self._syncing_preview = False
        self._selected_row: _LambdaKnotRow | None = None
        self._keep_open_on_local_apply = bool(keep_open_on_local_apply)
        self._runtime_d_nm = float("nan")
        self._runtime_rmse = float("nan")
        self._session_best_rmse = float("inf")  # track best RMSE across all operations in this dialog session
        # Per-K best tracking: stores {K: (result_dict, sigma_knots, rmse)} for each knot count.
        # This lets the user recall the best configuration for any K they explored.
        self._best_per_k: dict[int, tuple[dict, np.ndarray, float]] = {}
        self._runtime_busy = False

        main_layout = QVBoxLayout(self)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.main_splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.main_splitter)

        top_widget = QWidget(self)
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        bottom_widget = QWidget(self)
        layout = QVBoxLayout(bottom_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.main_splitter.addWidget(top_widget)
        self.main_splitter.addWidget(bottom_widget)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        intro = QLabel(
            "Add one or more extra knots on the lambda axis, then click 'Local Re-optimize' to run the local polish. "
            "Left click the graph to select the nearest knot (or add one if none is near), "
            "drag the lines to move them, right click near a line to remove it, "
            "and use the list below for fine numerical adjustments. Delete key = remove selected knot. "
            "All active knots are listed below (including pre-existing ones)."
        )
        intro.setWordWrap(True)
        top_layout.addWidget(intro)

        self.lbl_summary = QLabel("")
        top_layout.addWidget(self.lbl_summary)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-style: italic;")
        top_layout.addWidget(self.lbl_feedback)

        self.lbl_preview_log = QLabel("Preview log: init")
        self.lbl_preview_log.setWordWrap(True)
        self.lbl_preview_log.setStyleSheet(
            f"background-color: #141414; color: #d6f0ff; padding: 5px 7px; border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; border: 1px solid {CertusTheme.BORDER};"
        )
        top_layout.addWidget(self.lbl_preview_log)

        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Spectral preview (detached window):"))
        self.btn_preview_popup = QPushButton("Show / focus popup", self)
        self.btn_preview_popup.setToolTip("Open the comparison plot in a dedicated popup window.")
        preview_header.addWidget(self.btn_preview_popup)
        preview_header.addStretch(1)
        top_layout.addLayout(preview_header)

        self.plot = CertusScientificPlot(title="Additional manual knots", x_label="lambda (nm)", y_label=y_label)
        self.plot.setMinimumHeight(80)
        self.plot.showGrid(x=True, y=True, alpha=0.35)
        self.plot.addLegend()
        self._preview_axis = "lambda"
        self._preview_axis_button = None
        self.plot.installEventFilter(self)
        self._axis_toggle_style = (
            "QToolButton { background: rgba(30,30,30,180); color: white; border: 1px solid #666; border-radius: 4px; padding: 3px 8px; }"
            "QToolButton:hover { background: rgba(55,55,55,200); }"
            "QToolButton:pressed { background: rgba(90,90,90,220); }"
        )

        self._preview_popup = QDialog(self)
        self._preview_popup.setWindowTitle("Manual knots spectral preview")
        self._preview_popup.resize(980, 540)
        self._preview_popup.setWindowFlag(Qt.WindowType.Window, True)
        popup_layout = QVBoxLayout(self._preview_popup)
        popup_layout.setContentsMargins(6, 6, 6, 6)
        popup_layout.addWidget(self.plot, 1)
        self.btn_preview_popup.clicked.connect(self._show_preview_popup)
        self._preview_popup.finished.connect(self._on_preview_popup_closed)
        self._show_preview_popup()

        hint_popup = QLabel("The spectral comparison graph is displayed in a separate popup window.")
        hint_popup.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-style: italic;")
        top_layout.addWidget(hint_popup)

        metrics_row = QHBoxLayout()
        self.lbl_runtime_metrics = QLabel("d: - nm   |   RMSE: -")
        self.lbl_runtime_metrics.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_runtime_metrics.setStyleSheet(
            f"background-color: #1e1e1e; color: #a5d6ff; padding: 6px; border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; font-weight: bold; border: 1px solid {CertusTheme.BORDER};"
        )
        metrics_row.addWidget(self.lbl_runtime_metrics, 1)
        layout.addLayout(metrics_row)

        # --- Action Panels ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # 1. Substrate Tuning
        group_sub = QGroupBox("Substrate tuning")
        group_sub.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; margin-top: 6px; font-weight: 600; }} QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {CertusTheme.TEXT_SUB}; }}"
        )
        lay_sub = QHBoxLayout(group_sub)
        lay_sub.setContentsMargins(6, 12, 6, 6)
        lay_sub.setSpacing(6)

        lbl_ns = QLabel("Δns:")
        lbl_ns.setToolTip("Reference: theoretical ns without offset")
        lay_sub.addWidget(lbl_ns)
        self.spin_delta_ns = QDoubleSpinBox(self)
        self.spin_delta_ns.setDecimals(6)
        self.spin_delta_ns.setRange(-1.0, 1.0)
        self.spin_delta_ns.setSingleStep(0.001)
        self.spin_delta_ns.setValue(float(initial_delta_ns))
        self.spin_delta_ns.setToolTip(
            "Offset applied to the theoretical reference ns. Each time you return to this step, the reference remains the theoretical ns without offset."
        )
        self.spin_delta_ns.valueChanged.connect(self._on_delta_spin_changed)
        lay_sub.addWidget(self.spin_delta_ns)

        self.btn_apply_delta = QPushButton("Apply (Polish)", self)
        self.btn_apply_delta.setToolTip("Applies delta ns and runs a deep polish (d, n, k free) to lower the RMSE.")
        self.btn_apply_delta.clicked.connect(self._on_apply_keep_open)
        lay_sub.addWidget(self.btn_apply_delta)

        self.btn_autoshift = QPushButton("Autoshift Δn", self)
        self.btn_autoshift.setToolTip(
            "Automatically searches for the optimal shift in [-0.002, 0.002] via multiple deep polishes."
        )
        self.btn_autoshift.clicked.connect(self._on_autoshift_clicked)
        lay_sub.addWidget(self.btn_autoshift)

        actions_layout.addWidget(group_sub)

        # 2. Mesh Automation
        group_mesh = QGroupBox("Mesh automation")
        group_mesh.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; margin-top: 6px; font-weight: 600; }} QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {CertusTheme.TEXT_SUB}; }}"
        )
        lay_mesh = QHBoxLayout(group_mesh)
        lay_mesh.setContentsMargins(6, 12, 6, 6)
        lay_mesh.setSpacing(6)

        self.btn_auto_add_one = QPushButton("Auto Add One", self)
        self.btn_auto_add_one.setToolTip(
            "Try one knot insertion at every mid-gap, evaluate all candidates, and keep the best RMSE result."
        )
        self.btn_auto_add_one.clicked.connect(self._on_auto_add_one_clicked)
        lay_mesh.addWidget(self.btn_auto_add_one)

        self.btn_auto_clean = QPushButton("Advanced Clean", self)
        self.btn_auto_clean.setToolTip("Iteratively removes the least sensitive knots by re-optimizing.")
        self.btn_auto_clean.clicked.connect(self._on_auto_clean_clicked)
        lay_mesh.addWidget(self.btn_auto_clean)

        self.btn_force_clean = QPushButton("Force Drop Node", self)
        self.btn_force_clean.setToolTip("Removes exactly one knot (the least sensitive/penalizing one) unconditionally.")
        self.btn_force_clean.clicked.connect(self._on_force_clean_clicked)
        lay_mesh.addWidget(self.btn_force_clean)

        self.btn_auto_repartition_log = QPushButton("Repart. Log", self)
        self.btn_auto_repartition_log.setToolTip(
            "Redistributes all active knots with uniform spacing in log(sigma), then relaunches a local polish."
        )
        self.btn_auto_repartition_log.clicked.connect(self._on_auto_repartition_log_clicked)
        lay_mesh.addWidget(self.btn_auto_repartition_log)

        self.btn_auto_repartition_sigma = QPushButton("Repart. Sigma", self)
        self.btn_auto_repartition_sigma.setToolTip(
            "Redistributes all active knots with uniform spacing in sigma, then relaunches a local polish."
        )
        self.btn_auto_repartition_sigma.clicked.connect(self._on_auto_repartition_sigma_clicked)
        lay_mesh.addWidget(self.btn_auto_repartition_sigma)

        actions_layout.addWidget(group_mesh)

        # 3. Session / History
        group_hist = QGroupBox("History")
        group_hist.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; margin-top: 6px; font-weight: 600; }} QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {CertusTheme.TEXT_SUB}; }}"
        )
        lay_hist = QHBoxLayout(group_hist)
        lay_hist.setContentsMargins(6, 12, 6, 6)
        lay_hist.setSpacing(6)

        self.btn_recall_best = QToolButton(self)
        self.btn_recall_best.setText("Recall Best RMSE ▾")
        self.btn_recall_best.setToolTip(
            "Reloads the best configuration seen in this session.\nClick the arrow to choose a specific knot count K."
        )
        self.btn_recall_best.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_recall_best.setEnabled(False)
        self.btn_recall_best.clicked.connect(self._on_recall_best_clicked)
        self._recall_menu = QMenu(self)
        self.btn_recall_best.setMenu(self._recall_menu)
        lay_hist.addWidget(self.btn_recall_best)

        actions_layout.addWidget(group_hist)
        actions_layout.addStretch(1)

        layout.addLayout(actions_layout)

        self.progress_runtime = EnhancedProgressWidget(main_label="Node Processing")
        layout.addWidget(self.progress_runtime)

        runtime_actions = QHBoxLayout()
        runtime_actions.addStretch(1)
        self.btn_stop_runtime = QPushButton("Cancel optimization", self)
        self.btn_stop_runtime.setToolTip("Cancel the current re-optimization and keep the best result found so far.")
        self.btn_stop_runtime.setEnabled(False)
        self.btn_stop_runtime.clicked.connect(self._on_stop_clicked)
        runtime_actions.addWidget(self.btn_stop_runtime)
        layout.addLayout(runtime_actions)

        self.lbl_runtime_log = QLabel("Re-optimization log")
        self.txt_runtime_log = QPlainTextEdit(self)
        self.txt_runtime_log.setReadOnly(True)
        self.txt_runtime_log.setMinimumHeight(30)
        self.txt_runtime_log.setStyleSheet(
            f"background-color: #121212; color: #00ff00; font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; padding: 4px;"
        )
        self.txt_runtime_log.setPlaceholderText("Re-optimization progress messages appear here.")

        runtime_log_panel = QWidget(self)
        runtime_log_layout = QVBoxLayout(runtime_log_panel)
        runtime_log_layout.setContentsMargins(0, 0, 0, 0)
        runtime_log_layout.setSpacing(6)
        runtime_log_layout.addWidget(self.lbl_runtime_log)
        runtime_log_layout.addWidget(self.txt_runtime_log)

        lam_meas_s, y_meas_s = _sorted_xy(lam_measurement_nm, y_measurement, label="measurement")
        self._lam_measurement_preview_nm = lam_meas_s
        self._y_measurement_preview = y_meas_s
        _LOG.info(
            "Manual knots dialog preview state | measurement_in=(lam=%s,val=%s) | measurement_out=%d | model_in=(lam=%s,val=%s)",
            int(np.asarray(lam_measurement_nm if lam_measurement_nm is not None else [], dtype=np.float64).size),
            int(np.asarray(y_measurement if y_measurement is not None else [], dtype=np.float64).size),
            int(lam_meas_s.size),
            int(np.asarray(lam_model_nm if lam_model_nm is not None else [], dtype=np.float64).size),
            int(np.asarray(y_model if y_model is not None else [], dtype=np.float64).size),
        )
        self._measurement_curve = None
        if lam_meas_s.size:
            _LOG.info(
                "Manual knots dialog measurement preview ready | n=%d | x=[%.3f, %.3f] | y=[%.6g, %.6g]",
                int(lam_meas_s.size),
                float(np.min(lam_meas_s)),
                float(np.max(lam_meas_s)),
                float(np.min(y_meas_s)),
                float(np.max(y_meas_s)),
            )
            self._measurement_curve = self.plot.plot(
                lam_meas_s,
                y_meas_s,
                pen=None,
                symbol="o",
                symbolSize=4,
                symbolBrush=pg.mkBrush(CertusTheme.TEXT_SUB),
                name="Measurement",
            )
        else:
            _LOG.warning(
                "Manual knots dialog: measurement preview not displayed | reason=empty_or_invalid | "
                "lam_measurement_nm=%s | y_measurement=%s",
                type(lam_measurement_nm).__name__ if lam_measurement_nm is not None else "None",
                type(y_measurement).__name__ if y_measurement is not None else "None",
            )

        lam_model_s, y_model_s = _sorted_xy(lam_model_nm, y_model, label="theoretical model")
        self._lam_model_preview_nm = lam_model_s
        self._y_model_preview = y_model_s
        if lam_model_s.size:
            self._model_curve = self.plot.plot(
                lam_model_s,
                y_model_s,
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2.0),
                name="Current model",
            )
        else:
            self._model_curve = self.plot.plot(
                [],
                [],
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2.0),
                name="Current model",
            )
            _LOG.warning(
                "Manual knots dialog: model preview not displayed | reason=empty_or_invalid | "
                "lam_model_nm=%s | y_model=%s",
                type(lam_model_nm).__name__ if lam_model_nm is not None else "None",
                type(y_model).__name__ if y_model is not None else "None",
            )
        self._relabel_preview_axis()
        self._add_graph_axis_toggle()
        self._proposed_markers = self.plot.plot(
            [],
            [],
            pen=None,
            symbol="d",
            symbolSize=10,
            symbolBrush=pg.mkBrush("#c97800"),
            name="Proposed knots",
        )

        scene = self.plot.plotItem.scene()
        if scene is not None:
            scene.sigMouseClicked.connect(self._on_plot_clicked)

        row_controls = QHBoxLayout()
        self.btn_add = QPushButton("Add a knot")
        self.btn_add.clicked.connect(self._add_default_row)
        self.btn_add.setToolTip("Adds a knot at the default position.")
        row_controls.addWidget(self.btn_add)
        self.btn_remove_selected = QPushButton("Remove selected knot")
        self.btn_remove_selected.setEnabled(False)
        self.btn_remove_selected.clicked.connect(self._remove_selected_row)
        self.btn_remove_selected.setToolTip("Removes the currently selected knot (shortcut: Delete).")
        row_controls.addWidget(self.btn_remove_selected)
        self.btn_remove_last = QPushButton("Remove last")
        self.btn_remove_last.clicked.connect(self._remove_last_row)
        self.btn_remove_last.setToolTip("Removes the last row of the list.")
        row_controls.addWidget(self.btn_remove_last)
        row_controls.addStretch(1)
        self.lbl_selection_hint = QLabel(
            "Tip: left-click to select, right-click to remove, Delete to remove selection."
        )
        self.lbl_selection_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")

        rows_toolbar = QWidget(self)
        rows_toolbar_layout = QVBoxLayout(rows_toolbar)
        rows_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        rows_toolbar_layout.setSpacing(6)
        rows_toolbar_layout.addLayout(row_controls)
        rows_toolbar_layout.addWidget(self.lbl_selection_hint)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.rows_host = QWidget(scroll)
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        self.rows_layout.addStretch(1)
        scroll.setWidget(self.rows_host)

        rows_panel = QWidget(self)
        rows_panel_layout = QVBoxLayout(rows_panel)
        rows_panel_layout.setContentsMargins(0, 0, 0, 0)
        rows_panel_layout.setSpacing(6)
        rows_panel_layout.addWidget(rows_toolbar)
        rows_panel_layout.addWidget(scroll, 1)
        rows_toolbar.setMinimumHeight(15)
        scroll.setMinimumHeight(30)

        # Vertical splitter: horizontal handle that actually resizes log vs knot list.
        self.rows_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.rows_splitter.setChildrenCollapsible(False)
        self.rows_splitter.setHandleWidth(10)
        self.rows_splitter.addWidget(runtime_log_panel)
        self.rows_splitter.addWidget(rows_panel)
        runtime_log_panel.setMinimumHeight(30)
        rows_panel.setMinimumHeight(30)
        self.rows_splitter.setStretchFactor(0, 0)
        self.rows_splitter.setStretchFactor(1, 1)
        self.rows_splitter.setSizes([130, 260])
        self.rows_splitter.setStyleSheet(
            """
            QSplitter::handle:vertical {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #d9dde3,
                    stop: 0.5 #aeb7c2,
                    stop: 1 #d9dde3
                );
                border-top: 1px solid #8e99a6;
                border-bottom: 1px solid #8e99a6;
                margin: 2px 0;
            }
            QSplitter::handle:vertical:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffd58a,
                    stop: 0.5 #ffb347,
                    stop: 1 #ffd58a
                );
                border-top: 1px solid #d8901c;
                border-bottom: 1px solid #d8901c;
            }
            """
        )
        self.rows_splitter.handle(1).setCursor(Qt.CursorShape.SizeVerCursor)
        layout.addWidget(self.rows_splitter, 1)

        self.button_box = QDialogButtonBox(self)
        self.btn_go = self.button_box.addButton("Local re-optimization", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_skip = self.button_box.addButton("Keep current result", QDialogButtonBox.ButtonRole.RejectRole)

        if self._keep_open_on_local_apply:
            self.btn_go.clicked.connect(self._on_apply_keep_open)
        else:
            self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        for lam_k in self._base_lambda_knots_nm:
            self.add_lambda_knot(float(lam_k), origin="preexistant")
        self._sync_summary_and_preview()
        self._refresh_runtime_titles()

    def _show_preview_popup(self) -> None:
        try:
            if hasattr(self, "_preview_popup") and self._preview_popup is not None:
                self._preview_popup.show()
                self._preview_popup.raise_()
                self._preview_popup.activateWindow()
                self._refresh_preview_bounds()
                _LOG.info("Manual knots dialog preview popup shown/focused (axis=%s)", self._preview_axis)
                self.set_feedback_message("Preview popup open")
                if hasattr(self, "lbl_preview_log"):
                    self.lbl_preview_log.setText(f"Preview log: popup shown/focused (axis={self._preview_axis})")
        except Exception:
            _LOG.exception("Manual knots dialog failed to show preview popup")
            self.set_feedback_message("Preview popup failed to open")
            if hasattr(self, "lbl_preview_log"):
                self.lbl_preview_log.setText("Preview log: popup failed to open")

    def _on_preview_popup_closed(self, _code: int) -> None:
        _LOG.info("Manual knots dialog preview popup closed")
        self.set_feedback_message("Preview popup closed")
        if hasattr(self, "lbl_preview_log"):
            self.lbl_preview_log.setText(f"Preview log: popup closed (code={_code})")

    def _refresh_runtime_titles(self) -> None:
        k_before = int(self._base_sigma_knots.size)
        k_after = int(len(self._row_widgets))
        d_txt = f"{float(self._runtime_d_nm):.1f}" if np.isfinite(float(self._runtime_d_nm)) else "-"
        rmse_txt = f"{float(self._runtime_rmse):.6f}" if np.isfinite(float(self._runtime_rmse)) else "-"
        title_plain = f"K {k_before}->{k_after} | d {d_txt} nm | RMSE {rmse_txt} | axis {self._preview_axis}"
        self.setWindowTitle(title_plain)
        if hasattr(self, "_preview_popup") and self._preview_popup is not None:
            self._preview_popup.setWindowTitle(title_plain)
        if hasattr(self, "lbl_preview_log"):
            self.lbl_preview_log.setText(f"Preview log: axis={self._preview_axis} | K={k_after}")

    def _preview_x_from_lambda(self, lambda_nm: float) -> float:
        lam = float(lambda_nm)
        if self._preview_axis == "sigma":
            return float(1e7 / max(lam, 1e-30))
        return lam

    def _lambda_from_preview_x(self, x_value: float) -> float:
        x = float(x_value)
        if self._preview_axis == "sigma":
            return float(1e7 / max(x, 1e-30))
        return x

    def _default_lambda_value(self) -> float:
        if self._row_widgets:
            return float(self._row_widgets[-1].spin.value())
        return 0.5 * (self._lam_min_nm + self._lam_max_nm)

    def _add_default_row(self) -> None:
        self.add_lambda_knot(self._default_lambda_value())

    def _clip_lambda_value(self, lambda_nm: float) -> float:
        return float(np.clip(float(lambda_nm), self._lam_min_nm, self._lam_max_nm))

    def _create_preview_line(self, row: _LambdaKnotRow) -> pg.InfiniteLine:
        is_preexisting = str(getattr(row, "origin", "propose")).strip().lower() == "preexistant"
        base_color = "#ff9f1a" if is_preexisting else "#c97800"
        base_width = 2.5 if is_preexisting else 2.0
        pos_x = self._preview_x_from_lambda(row.spin.value())
        line = pg.InfiniteLine(
            pos=float(pos_x),
            angle=90,
            movable=True,
            pen=pg.mkPen(base_color, width=base_width),
            hoverPen=pg.mkPen(CertusTheme.WARNING, width=3),
        )
        try:
            if self._preview_axis == "sigma":
                line.setBounds((1e7 / max(self._lam_max_nm, 1e-30), 1e7 / max(self._lam_min_nm, 1e-30)))
            else:
                line.setBounds((self._lam_min_nm, self._lam_max_nm))
        except AttributeError:
            pass
        line.sigPositionChanged.connect(lambda _line: self._on_line_position_changed(row))
        return line

    def _update_selection_label(self, row: _LambdaKnotRow) -> None:
        if row.preview_line is None:
            if row.selection_label is not None:
                self.plot.removeItem(row.selection_label)
                row.selection_label = None
            return
        is_sel = row is self._selected_row
        if not is_sel:
            if row.selection_label is not None:
                self.plot.removeItem(row.selection_label)
                row.selection_label = None
            return
        x_pos = self._preview_x_from_lambda(float(row.preview_line.value()))
        y_anchor = float(np.nanmax(self._y_model_preview)) if self._y_model_preview.size else 1.0
        y_pos = y_anchor + 0.02 * max(abs(y_anchor), 1.0)
        if row.selection_label is None:
            lbl = pg.TextItem(
                html='<div style="background-color:#ffb347;color:#1b1b1b;padding:2px 5px;border-radius:3px;"><b>Selection</b></div>',
                anchor=(0.5, 1.0),
            )
            row.selection_label = lbl
            self.plot.addItem(lbl)
        row.selection_label.setPos(x_pos, y_pos)

    def _update_line_style(self, row: _LambdaKnotRow) -> None:
        if row.preview_line is None:
            return
        is_preexisting = str(getattr(row, "origin", "propose")).strip().lower() == "preexistant"
        base_color = "#ff9f1a" if is_preexisting else "#c97800"
        base_width = 2.5 if is_preexisting else 2.0
        is_sel = row is self._selected_row
        if is_sel:
            row.preview_line.setPen(pg.mkPen(CertusTheme.WARNING, width=3))
            row.preview_line.setHoverPen(pg.mkPen(CertusTheme.WARNING, width=4))
            row.preview_line.setZValue(20)
            row.set_selected(True)
        else:
            row.preview_line.setPen(pg.mkPen(base_color, width=base_width))
            row.preview_line.setHoverPen(pg.mkPen(CertusTheme.WARNING, width=3))
            row.preview_line.setZValue(12)
            row.set_selected(False)
        self._update_selection_label(row)

    def _set_selected_row(self, row: _LambdaKnotRow | None) -> None:
        if row is not None and row not in self._row_widgets:
            row = None
        self._selected_row = row
        for rw in self._row_widgets:
            self._update_line_style(rw)
        self.btn_remove_selected.setEnabled(self._selected_row is not None)

    def _remove_selected_row(self) -> None:
        if self._selected_row is None:
            return
        self._remove_row(self._selected_row)

    def _remove_last_row(self) -> None:
        if not self._row_widgets:
            return
        self._remove_row(self._row_widgets[-1])

    def _on_row_value_changed(self, row: _LambdaKnotRow) -> None:
        if self._syncing_preview:
            return
        value_nm = self._clip_lambda_value(row.spin.value())
        self._syncing_preview = True
        try:
            row.spin.blockSignals(True)
            row.spin.setValue(value_nm)
            row.spin.blockSignals(False)
            if row.preview_line is not None:
                target_x = self._preview_x_from_lambda(value_nm)
                if abs(float(row.preview_line.value()) - target_x) > 1e-9:
                    row.preview_line.blockSignals(True)
                    row.preview_line.setValue(float(target_x))
                    row.preview_line.blockSignals(False)
        finally:
            row.spin.blockSignals(False)
            self._syncing_preview = False
        self._sort_rows_by_lambda()
        self._set_selected_row(row)
        self._sync_summary_and_preview()

    def _on_line_position_changed(self, row: _LambdaKnotRow) -> None:
        if self._syncing_preview or row.preview_line is None:
            return
        value_nm = self._lambda_from_preview_x(row.preview_line.value())
        value_nm = self._clip_lambda_value(value_nm)
        self._syncing_preview = True
        try:
            target_x = self._preview_x_from_lambda(value_nm)
            if abs(float(row.preview_line.value()) - float(target_x)) > 1e-9:
                row.preview_line.blockSignals(True)
                row.preview_line.setValue(float(target_x))
                row.preview_line.blockSignals(False)
            row.spin.blockSignals(True)
            row.spin.setValue(value_nm)
            row.spin.blockSignals(False)
        finally:
            row.spin.blockSignals(False)
            self._syncing_preview = False
        self._sort_rows_by_lambda()
        self._set_selected_row(row)
        self._sync_summary_and_preview()

    def _sort_rows_by_lambda(self) -> None:
        if len(self._row_widgets) < 2:
            return
        self._row_widgets.sort(key=lambda row: float(row.spin.value()))
        for row in self._row_widgets:
            self.rows_layout.removeWidget(row)
        for idx, row in enumerate(self._row_widgets):
            self.rows_layout.insertWidget(idx, row)

    def _x_tolerance_nm_from_pixels(self, px: float = 24.0) -> float:
        vb = getattr(self.plot.plotItem, "vb", None)
        scene = getattr(self.plot.plotItem, "scene", None)
        if vb is None or scene is None:
            if self._preview_axis == "sigma":
                sig_min = 1e7 / max(self._lam_max_nm, 1e-30)
                sig_max = 1e7 / max(self._lam_min_nm, 1e-30)
                return max(5.0, 0.02 * (sig_max - sig_min))
            return max(5.0, 0.02 * (self._lam_max_nm - self._lam_min_nm))
        if self._preview_axis == "sigma":
            sig_min = 1e7 / max(self._lam_max_nm, 1e-30)
            sig_max = 1e7 / max(self._lam_min_nm, 1e-30)
            plot_center_x = 0.5 * (sig_min + sig_max)
        else:
            plot_center_x = 0.5 * (self._lam_min_nm + self._lam_max_nm)
        center = vb.mapViewToScene(pg.Point(plot_center_x, 0.0))
        p0 = vb.mapSceneToView(pg.Point(float(center.x() - px), float(center.y())))
        p1 = vb.mapSceneToView(pg.Point(float(center.x() + px), float(center.y())))
        tol = abs(float(p1.x()) - float(p0.x()))
        return max(2.0, tol)

    def _nearest_row_to_x(self, x_value: float) -> tuple[_LambdaKnotRow | None, float]:
        if not self._row_widgets or not np.isfinite(float(x_value)):
            return None, float("inf")
        best_row = None
        best_dist = float("inf")
        for row in self._row_widgets:
            row_x = self._preview_x_from_lambda(float(row.spin.value()))
            dist = abs(row_x - float(x_value))
            if dist < best_dist:
                best_dist = dist
                best_row = row
        return best_row, best_dist

    def _add_lambda_from_plot_x(self, x_value: float) -> bool:
        if not np.isfinite(float(x_value)):
            return False
        lambda_val = self._lambda_from_preview_x(x_value)
        self.add_lambda_knot(self._clip_lambda_value(lambda_val))
        return True

    def _remove_nearest_lambda_knot(self, x_value: float, tolerance_nm: float | None = None) -> bool:
        if not self._row_widgets or not np.isfinite(float(x_value)):
            return False
        tol = float(tolerance_nm) if tolerance_nm is not None else self._x_tolerance_nm_from_pixels(24.0)
        best_row, best_dist = self._nearest_row_to_x(float(x_value))
        if best_row is None or best_dist > tol:
            return False
        self._remove_row(best_row)
        return True

    def _select_nearest_lambda_knot(self, x_value: float, tolerance_nm: float | None = None) -> bool:
        if not self._row_widgets or not np.isfinite(float(x_value)):
            return False
        tol = float(tolerance_nm) if tolerance_nm is not None else self._x_tolerance_nm_from_pixels(20.0)
        best_row, best_dist = self._nearest_row_to_x(float(x_value))
        if best_row is None or best_dist > tol:
            return False
        self._set_selected_row(best_row)
        return True

    def _on_plot_clicked(self, event) -> None:
        if event is None:
            return
        vb = getattr(self.plot.plotItem, "vb", None)
        if vb is None:
            return
        scene_pos = event.scenePos()
        if not vb.sceneBoundingRect().contains(scene_pos):
            return
        x_value = float(vb.mapSceneToView(scene_pos).x())
        handled = False
        if event.button() == Qt.MouseButton.LeftButton:
            # First try selection for dense regions; fallback to add.
            handled = self._select_nearest_lambda_knot(x_value)
            if not handled:
                handled = self._add_lambda_from_plot_x(x_value)
        elif event.button() == Qt.MouseButton.RightButton:
            handled = self._remove_nearest_lambda_knot(x_value)
        if handled and hasattr(event, "accept"):
            event.accept()

    def keyPressEvent(self, event) -> None:
        if event is not None and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_row is not None:
                self._remove_selected_row()
                event.accept()
                return
        super().keyPressEvent(event)

    def done(self, result: int) -> None:
        try:
            if hasattr(self, "_preview_popup") and self._preview_popup is not None:
                self._preview_popup.close()
        except Exception:
            pass
        super().done(result)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_preview_bounds()

    def add_lambda_knot(self, lambda_nm: float, *, origin: str = "propose") -> None:
        row = _LambdaKnotRow(
            self._lam_min_nm,
            self._lam_max_nm,
            lambda_nm,
            on_remove=self._remove_row,
            on_value_changed=self._on_row_value_changed,
            on_select=self._set_selected_row,
        )
        if str(origin).strip().lower() == "preexistant":
            row.set_kind("Pre-existing", color="#d4a100")
        else:
            row.set_kind("Proposed", color="#c97800")
        row.preview_line = self._create_preview_line(row)
        self._row_widgets.append(row)
        self.plot.addItem(row.preview_line)
        if len(self._row_widgets) == 1:
            self.rows_layout.insertWidget(max(0, self.rows_layout.count() - 1), row)
        else:
            self._sort_rows_by_lambda()
        self._set_selected_row(row)
        self._sync_summary_and_preview()

    def _remove_row(self, row: _LambdaKnotRow) -> None:
        if row in self._row_widgets:
            self._row_widgets.remove(row)
        if row.preview_line is not None:
            self.plot.removeItem(row.preview_line)
            row.preview_line = None
        if row.selection_label is not None:
            self.plot.removeItem(row.selection_label)
            row.selection_label = None
        row.setParent(None)
        row.deleteLater()
        if self._selected_row is row:
            self._selected_row = None
        self._set_selected_row(self._row_widgets[-1] if self._row_widgets else None)
        self._sync_summary_and_preview()

    def selected_lambda_knots(self) -> list[float]:
        "Returns active lambda knots sorted, with automatic deletion of duplicates."
        vals = sorted([float(row.spin.value()) for row in self._row_widgets])
        if not vals:
            return []

        # Automatic removal of duplicates (relative tolerance 1e-6)
        unique_vals = [vals[0]]
        for v in vals[1:]:
            if (v - unique_vals[-1]) > (1e-6 * v):
                unique_vals.append(v)
        return unique_vals

    def selected_sigma_knots(self) -> np.ndarray:
        lam = np.asarray(self.selected_lambda_knots(), dtype=np.float64)
        if lam.size == 0:
            return np.empty(0, dtype=np.float64)
        return np.sort(1.0 / np.maximum(lam, 1e-30))

    def adopt_sigma_knots(self, sigma_knots: np.ndarray | None) -> None:
        sk = np.asarray(sigma_knots if sigma_knots is not None else [], dtype=np.float64).ravel()
        if sk.size == 0:
            return
        self._base_sigma_knots = sk.copy()
        self._base_lambda_knots_nm = np.sort(1.0 / np.maximum(self._base_sigma_knots, 1e-30))
        # Reset the active rows so the accepted mesh becomes the new baseline.
        for row in list(self._row_widgets):
            self._remove_row(row)
        self._row_widgets = []
        self._selected_row = None
        for lam_k in self._base_lambda_knots_nm:
            self.add_lambda_knot(float(lam_k), origin="preexistant")
        self._set_selected_row(None)
        self._sync_summary_and_preview()
        self._refresh_preview_bounds()

    def update_model_preview(self, lam_model_nm: np.ndarray | None, y_model: np.ndarray | None) -> None:
        lam_model_s, y_model_s = _sorted_xy(lam_model_nm, y_model, label="theoretical model")
        _LOG.info(
            "Manual knots dialog update_model_preview | axis=%s | input_sizes=(lam=%d, values=%d) | filtered_size=%d",
            self._preview_axis,
            int(np.asarray(lam_model_nm if lam_model_nm is not None else [], dtype=np.float64).size),
            int(np.asarray(y_model if y_model is not None else [], dtype=np.float64).size),
            int(lam_model_s.size),
        )
        self._lam_model_preview_nm = lam_model_s
        self._y_model_preview = y_model_s
        if getattr(self, "_model_curve", None) is not None:
            self._model_curve.setData(lam_model_s, y_model_s)
        else:
            _LOG.warning("Manual knots dialog update_model_preview called before _model_curve initialization")
        if lam_model_s.size == 0:
            _LOG.warning("Manual knots dialog: update_model_preview received no usable model data")
        if hasattr(self, "lbl_preview_log"):
            self.lbl_preview_log.setText(f"Preview log: model updated with {int(lam_model_s.size)} sample(s) | axis={self._preview_axis}")
        self._sync_summary_and_preview()
        self._refresh_preview_bounds()

    def _preview_sigma_curve(self, lam_nm: np.ndarray, y_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lam = np.asarray(lam_nm, dtype=np.float64).ravel()
        y = np.asarray(y_values, dtype=np.float64).ravel()
        n = int(min(lam.size, y.size))
        if n <= 0:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        lam = lam[:n]
        y = y[:n]
        with np.errstate(divide="ignore", invalid="ignore"):
            sigma_cm = 1e7 / np.maximum(lam, 1e-30)
        mask = np.isfinite(sigma_cm) & np.isfinite(y)
        if not np.any(mask):
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        sigma_cm = sigma_cm[mask]
        y = y[mask]
        order = np.argsort(sigma_cm, kind="mergesort")
        return sigma_cm[order], y[order]

    def _refresh_preview_bounds(self) -> None:
        try:
            vb = self.plot.getViewBox()
            if vb is not None:
                vb.autoRange()
                vb.updateAutoRange()
                self.plot.getPlotItem().setDownsampling(auto=True, mode="peak")
                self.plot.getPlotItem().setClipToView(True)
                self.plot.repaint()
        except Exception:
            _LOG.exception("Manual knots dialog failed to refresh preview bounds")

    def substrate_delta_ns(self) -> float:
        return float(self.spin_delta_ns.value())

    def adopt_delta_ns(self, delta_ns: float) -> None:
        """Update the delta_ns spinbox to reflect a new optimal offset."""
        self.spin_delta_ns.blockSignals(True)
        self.spin_delta_ns.setValue(float(delta_ns))
        self.spin_delta_ns.blockSignals(False)

    def _sync_summary_and_preview(self) -> None:
        row_lambda_knots = [float(row.spin.value()) for row in self._row_widgets]
        preview_lambda_knots = sorted(row_lambda_knots)
        for row, lam_k in zip(self._row_widgets, row_lambda_knots):
            if row.preview_line is not None:
                target_x = self._preview_x_from_lambda(float(lam_k))
                if abs(float(row.preview_line.value()) - float(target_x)) > 1e-9:
                    row.preview_line.blockSignals(True)
                    row.preview_line.setValue(float(target_x))
                    row.preview_line.blockSignals(False)

        if self._lam_model_preview_nm.size and preview_lambda_knots:
            y_preview = np.interp(
                np.asarray(preview_lambda_knots, dtype=np.float64),
                self._lam_model_preview_nm,
                self._y_model_preview,
            )
            x_preview = np.asarray([self._preview_x_from_lambda(v) for v in preview_lambda_knots], dtype=np.float64)
            self._proposed_markers.setData(x_preview, y_preview)
        else:
            self._proposed_markers.setData([], [])

        if self._preview_axis == "sigma":
            sigma_x, sigma_y = self._preview_sigma_curve(self._lam_model_preview_nm, self._y_model_preview)
            if getattr(self, "_model_curve", None) is not None:
                self._model_curve.setData(sigma_x, sigma_y)
        else:
            if getattr(self, "_model_curve", None) is not None:
                self._model_curve.setData(self._lam_model_preview_nm, self._y_model_preview)
        self._relabel_preview_axis()

        k_before = int(self._base_sigma_knots.size)
        k_after = len(self._row_widgets)
        delta_k = int(k_after - k_before)
        valid = self._is_selection_valid() if self._row_widgets else False
        warning = "" if valid or not self._row_widgets else "    Adjust overlapping positions before re-optimizing."
        self.lbl_summary.setText(
            f"Initial K: {k_before}    Active K: {k_after} (Delta {delta_k:+d})    Left-click to add, drag orange lines to move, right-click near a line to remove.{warning}"
        )
        enable_actions = not self._runtime_busy
        self.btn_go.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_apply_delta.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_autoshift.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_auto_repartition_log.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_auto_repartition_sigma.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_auto_add_one.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_remove_last.setEnabled(enable_actions and bool(self._row_widgets))
        self.btn_add.setEnabled(enable_actions)
        self.btn_remove_selected.setEnabled(enable_actions and self._selected_row is not None)
        self.btn_auto_clean.setEnabled(enable_actions and bool(self._row_widgets) and valid)
        self.btn_recall_best.setEnabled(enable_actions and bool(self._best_per_k))
        self.btn_skip.setEnabled(not self._runtime_busy)
        self.btn_stop_runtime.setEnabled(self._runtime_busy)
        self.spin_delta_ns.setEnabled(enable_actions)
        for row in self._row_widgets:
            row.spin.setEnabled(enable_actions)
        self._refresh_runtime_titles()

    def _is_selection_valid(self) -> bool:
        """Validates node selection: finite values, no duplicates, and >= 2 nodes."""
        if not self._row_widgets:
            return True

        vals = np.asarray([float(row.spin.value()) for row in self._row_widgets], dtype=np.float64)
        if vals.size == 0 or not np.all(np.isfinite(vals)):
            return False
        if vals.size < 2:
            return False

        vals.sort()

        def _tol(v: float) -> float:
            return max(1e-9, 1e-6 * max(abs(float(v)), 1.0))

        # Reject duplicates among proposed lambda knots.
        if vals.size > 1:
            d = np.diff(vals)
            for i, dv in enumerate(d):
                if float(dv) <= _tol(vals[i + 1]):
                    return False

        return True

    def _on_accept(self) -> None:
        self.accept()

    def _on_apply_keep_open(self) -> None:
        if not self._is_selection_valid() or not self._row_widgets:
            QMessageBox.warning(
                self,
                "Manual knots",
                "Invalid selection. Adjust knots before re-optimizing.",
            )
            return
        self.local_apply_requested.emit(self.selected_lambda_knots(), self.substrate_delta_ns())

    def _on_autoshift_clicked(self) -> None:
        self.auto_shift_requested.emit()

    def _on_auto_repartition_log_clicked(self) -> None:
        self.auto_repartition_log_requested.emit()

    def _on_auto_repartition_sigma_clicked(self) -> None:
        self.auto_repartition_sigma_requested.emit()

    def _on_stop_clicked(self) -> None:
        self.append_runtime_log("Stop requested by user...")
        self.stop_requested.emit()

    def _on_apply_delta_preview(self) -> None:
        self.delta_preview_requested.emit(self.substrate_delta_ns())

    def _on_delta_spin_changed(self, _value: float) -> None:
        self.delta_preview_requested.emit(self.substrate_delta_ns())

    def clear_runtime_log(self) -> None:
        self.txt_runtime_log.clear()

    def set_feedback_message(self, message: str) -> None:
        self.lbl_feedback.setText(str(message or "").strip())

    def _relabel_preview_axis(self) -> None:
        self.plot.setLabel("bottom", "sigma (cm^-1)" if self._preview_axis == "sigma" else "lambda (nm)")
        if hasattr(self, "_preview_popup") and self._preview_popup is not None:
            self._preview_popup.setWindowTitle(f"Manual knots spectral preview | axis {self._preview_axis}")

    def _add_graph_axis_toggle(self) -> None:
        try:
            if getattr(self, "_preview_axis_button", None) is None:
                btn = QToolButton(self.plot)
                btn.setText("lambda")
                btn.setCheckable(True)
                btn.setChecked(False)
                btn.setToolTip("Toggle preview axis between lambda and sigma")
                btn.clicked.connect(self._toggle_preview_axis)
                btn.setStyleSheet(self._axis_toggle_style)
                btn.setParent(self.plot)
                btn.raise_()
                self._preview_axis_button = btn
            btn = self._preview_axis_button
            if btn is not None:
                btn.adjustSize()
                btn.move(10, 10)
                btn.show()
        except Exception:
            _LOG.exception("Manual knots dialog failed to attach graph axis toggle")

    def _toggle_preview_axis(self) -> None:
        self._preview_axis = "sigma" if self._preview_axis == "lambda" else "lambda"
        if self._preview_axis_button is not None:
            self._preview_axis_button.setText(self._preview_axis)
            self._preview_axis_button.setChecked(self._preview_axis == "sigma")
        self._relabel_preview_axis()
        self._rescale_preview_curves()
        self._sync_summary_and_preview()
        _LOG.info("Manual knots dialog preview axis toggled to %s", self._preview_axis)
        if hasattr(self, "lbl_preview_log"):
            self.lbl_preview_log.setText(f"Preview log: axis toggled to {self._preview_axis}")

    def _rescale_preview_curves(self) -> None:
        if getattr(self, "_model_curve", None) is None:
            return
        try:
            model_x = self._lam_model_preview_nm
            model_y = self._y_model_preview
            if self._preview_axis == "sigma":
                model_x, model_y = self._preview_sigma_curve(model_x, model_y)
            self._model_curve.setData(model_x, model_y)

            if getattr(self, "_measurement_curve", None) is not None and self._measurement_curve is not None:
                meas_x = self._lam_measurement_preview_nm
                meas_y = self._y_measurement_preview
                if self._preview_axis == "sigma":
                    meas_x, meas_y = self._preview_sigma_curve(meas_x, meas_y)
                self._measurement_curve.setData(meas_x, meas_y)

            preview_lambda_knots = sorted([float(r.spin.value()) for r in self._row_widgets])
            if preview_lambda_knots and self._lam_model_preview_nm.size and self._y_model_preview.size:
                y_preview = np.interp(np.asarray(preview_lambda_knots, dtype=np.float64), self._lam_model_preview_nm, self._y_model_preview)
                x_preview = np.asarray([self._preview_x_from_lambda(v) for v in preview_lambda_knots], dtype=np.float64)
                self._proposed_markers.setData(x_preview, y_preview)
            else:
                self._proposed_markers.setData([], [])

            # Also update all vertical knot lines
            was_syncing = getattr(self, "_syncing_preview", False)
            self._syncing_preview = True
            try:
                for row in self._row_widgets:
                    if row.preview_line is not None:
                        try:
                            if self._preview_axis == "sigma":
                                row.preview_line.setBounds((1e7 / max(self._lam_max_nm, 1e-30), 1e7 / max(self._lam_min_nm, 1e-30)))
                            else:
                                row.preview_line.setBounds((self._lam_min_nm, self._lam_max_nm))
                        except AttributeError:
                            pass
                        
                        target_x = self._preview_x_from_lambda(float(row.spin.value()))
                        row.preview_line.blockSignals(True)
                        row.preview_line.setValue(float(target_x))
                        row.preview_line.blockSignals(False)
                        self._update_selection_label(row)
            finally:
                self._syncing_preview = was_syncing

            self._refresh_preview_bounds()
        except Exception:
            _LOG.exception("Manual knots dialog failed to rescale preview curves for axis=%s", self._preview_axis)

    def append_runtime_log(self, message: str) -> None:
        msg = str(message or "").strip()
        if not msg:
            return
        self.txt_runtime_log.appendPlainText(msg)
        sb = self.txt_runtime_log.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def set_runtime_progress(self, percent: float, message: str | None = None) -> None:
        p = int(round(float(np.clip(percent, 0.0, 100.0)) * 100.0))
        self.progress_runtime.update(iteration=p, max_iter=10000, phase="Optimizing...", progress_pct=int(p/100))
        if message:
            self.progress_runtime.setToolTip(str(message))

    def set_runtime_busy(self, busy: bool) -> None:
        self._runtime_busy = bool(busy)
        self._sync_summary_and_preview()

    def set_runtime_metrics(self, d_nm: float | None, rmse: float | None) -> None:
        self._runtime_d_nm = float(d_nm) if d_nm is not None else float("nan")
        self._runtime_rmse = float(rmse) if rmse is not None else float("nan")
        # Track best RMSE across the entire dialog session
        if np.isfinite(self._runtime_rmse) and self._runtime_rmse < self._session_best_rmse:
            self._session_best_rmse = float(self._runtime_rmse)
        d_txt = f"{float(self._runtime_d_nm):.1f}" if np.isfinite(float(self._runtime_d_nm)) else "-"
        rmse_txt = f"{float(self._runtime_rmse):.6f}" if np.isfinite(float(self._runtime_rmse)) else "-"
        best_txt = f"{float(self._session_best_rmse):.6f}" if np.isfinite(self._session_best_rmse) else "-"
        # Display current and best RMSE
        self.lbl_runtime_metrics.setText(f"d: {d_txt} nm   |   RMSE: {rmse_txt}   |   Best: {best_txt}")

    def update_best_config(self, result: dict, sigma_knots: np.ndarray) -> None:
        """Stores the best config per knot count K (called by GUI after each result).

        The per-K dictionary allows the user to recall the best configuration
        for any knot count they explored during the session, not just the
        absolute best RMSE.
        """
        rmse = float(result.get("rmse", float("inf")))
        if not np.isfinite(rmse):
            _LOG.debug("MANUAL_DIALOG best snapshot ignored: non-finite RMSE in result payload")
            return
        sk = np.asarray(sigma_knots, dtype=np.float64).ravel().copy()
        K = int(sk.size)
        existing = self._best_per_k.get(K)
        if existing is None or rmse < existing[2]:
            prev_rmse = existing[2] if existing is not None else float("inf")
            self._best_per_k[K] = (dict(result), sk, rmse)
            self._session_best_rmse = min(self._session_best_rmse, rmse)
            _LOG.info(
                "MANUAL_DIALOG best snapshot updated for K=%d | RMSE=%.8f (prev=%s) | d=%.4f nm | delta_ns=%+.6f",
                K,
                rmse,
                f"{prev_rmse:.8f}" if np.isfinite(prev_rmse) else "n/a",
                float(result.get("d_nm", float("nan"))),
                float(result.get("substrate_n_offset", 0.0)),
            )
            self._refresh_recall_menu()
        else:
            _LOG.debug(
                "MANUAL_DIALOG best snapshot unchanged for K=%d | candidate RMSE=%.8f >= best=%.8f",
                K,
                rmse,
                existing[2],
            )

    def _refresh_recall_menu(self) -> None:
        """Rebuild the recall menu with one entry per K, sorted by K."""
        self._recall_menu.clear()
        if not self._best_per_k:
            self.btn_recall_best.setEnabled(False)
            return
        self.btn_recall_best.setEnabled(True)
        # Find absolute best for the button label
        abs_best_k = min(self._best_per_k, key=lambda k: self._best_per_k[k][2])
        abs_best_rmse = self._best_per_k[abs_best_k][2]
        self.btn_recall_best.setToolTip(
            f"Click: recall absolute best (K={abs_best_k}, RMSE={abs_best_rmse:.8f})\n"
            f"Arrow: choose a specific knot count K"
        )
        for K in sorted(self._best_per_k.keys()):
            _, sk, rmse = self._best_per_k[K]
            marker = " ★" if K == abs_best_k else ""
            action = self._recall_menu.addAction(f"K={K}  |  RMSE={rmse:.6f}{marker}")
            action.setData(K)
            action.triggered.connect(lambda checked, k=K: self._on_recall_for_k(k))

    def _on_recall_for_k(self, k: int) -> None:
        """Emit recall signal for a specific knot count."""
        _LOG.info("MANUAL_DIALOG user requested recall of best RMSE for K=%d", k)
        self.recall_best_for_k_requested.emit(k)

    def get_best_config(self) -> tuple[dict, np.ndarray] | None:
        """Returns (result, sigma_knots) of the absolute best config across all K, or None."""
        if not self._best_per_k:
            _LOG.debug("MANUAL_DIALOG best snapshot requested but unavailable")
            return None
        best_k = min(self._best_per_k, key=lambda k: self._best_per_k[k][2])
        result, sk, rmse = self._best_per_k[best_k]
        _LOG.debug(
            "MANUAL_DIALOG returning absolute best snapshot | RMSE=%.8f | K=%d",
            rmse,
            best_k,
        )
        return dict(result), sk.copy()

    def get_best_config_for_k(self, k: int) -> tuple[dict, np.ndarray] | None:
        """Returns (result, sigma_knots) of the best config for a specific K, or None."""
        entry = self._best_per_k.get(k)
        if entry is None:
            _LOG.debug("MANUAL_DIALOG best snapshot for K=%d not available", k)
            return None
        result, sk, rmse = entry
        _LOG.debug(
            "MANUAL_DIALOG returning best snapshot for K=%d | RMSE=%.8f",
            k,
            rmse,
        )
        return dict(result), sk.copy()

    def _on_recall_best_clicked(self) -> None:
        _LOG.info("MANUAL_DIALOG user requested recall of absolute best RMSE snapshot")
        self.recall_best_requested.emit()

    def _on_auto_clean_clicked(self) -> None:
        _LOG.info(
            "MANUAL_DIALOG user requested advanced auto-clean | tolerance=+%.5f | current_rmse=%s | session_best=%s",
            0.00005,
            f"{float(self._runtime_rmse):.8f}" if np.isfinite(float(self._runtime_rmse)) else "n/a",
            f"{float(self._session_best_rmse):.8f}" if np.isfinite(float(self._session_best_rmse)) else "n/a",
        )
        # Tolerance is now read from the main GUI via the listener;
        # 5e-5 remains the default on the CERTUS_INDEX_SPLINE._on_auto_clean side.
        self.auto_clean_requested.emit(float("nan"))
        self._refresh_runtime_titles()

    def _on_force_clean_clicked(self) -> None:
        _LOG.info(
            "MANUAL_DIALOG user requested force-clean | current_rmse=%s | session_best=%s",
            f"{float(self._runtime_rmse):.8f}" if np.isfinite(float(self._runtime_rmse)) else "n/a",
            f"{float(self._session_best_rmse):.8f}" if np.isfinite(float(self._session_best_rmse)) else "n/a",
        )
        self.force_clean_requested.emit()
        self._refresh_runtime_titles()

    def _on_auto_add_one_clicked(self) -> None:
        _LOG.info(
            "MANUAL_DIALOG user requested auto add one | current_rmse=%s | session_best=%s",
            f"{float(self._runtime_rmse):.8f}" if np.isfinite(float(self._runtime_rmse)) else "n/a",
            f"{float(self._session_best_rmse):.8f}" if np.isfinite(float(self._session_best_rmse)) else "n/a",
        )
        self.auto_add_one_requested.emit()
        self._refresh_runtime_titles()
