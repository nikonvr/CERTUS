from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QFrame, QSplitter, QTextEdit, QAbstractSpinBox, QPushButton,
    QFileDialog, QComboBox, QLineEdit, QTabWidget, QGridLayout, QCheckBox,
    QDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from certus.ui.certus_ui import (
    CertusBaseApp, CertusCard, create_styled_button, 
    create_header_logo_widget, CertusThemeToggle, create_top_actions_bar,
    show_toast, CertusCollapsible, CertusAppLogsMixin, CertusTheme,
    clone_plot_widget, DetachedPlotWindow, EnhancedProgressWidget,
    ExcelTableWidget
)
from certus.ui.certus_icons import certus_icon
from certus.ui.certus_field_plot import CertusFieldPlotWidget, CertusSpectralPlotWidget, CertusIndexProfilePlotWidget
from certus.ui.certus_field_services import FieldExportService, FieldPlotData, FieldStackService
from certus.workers.certus_field_workers_dto import FieldWorkerRequest, FieldParamsDTO
from certus.workers.certus_field_workers import FieldWorkerThread
from certus.core._certus_physics_impl import MaterialDatabase
from certus.workers.certus_strat_workers import _resolve_strat_indices_db_path
from certus.core.certus_core import get_resource_path, SUBSTRATE_CHOICES
from certus.utils.certus_data import generate_html_report, to_excel_robust
# certus_load_summary helpers reserved for future use (not yet wired in FIELD)
from certus.core.certus_field_core import calculate_opt_metrics, get_layer_properties_from_list

import pyqtgraph as pg
import pyqtgraph.exporters
import traceback
import logging
import json
import os
import pandas as pd
import importlib.util
from datetime import datetime
from pathlib import Path
import numpy as np

LIDT_PRESETS = {
    "SiO2": 25.0,
    "MgF2": 20.0,
    "Al2O3": 10.0,
    "HfO2": 5.0,
    "Ta2O5": 3.0,
    "Nb2O5": 2.0,
    "TiO2": 1.0,
    "ZnS": 0.5
}

scipy_installed = importlib.util.find_spec("scipy") is not None

class DetachedStackWindow(QMainWindow):
    closed_signal = pyqtSignal()

    def __init__(self, stack_panel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🥞 Stack Structure - Floating Panel")
        self.resize(400, 600)
        self.setMinimumSize(360, 400)
        
        self.stack_panel = stack_panel
        
        c = QWidget()
        self.setCentralWidget(c)
        l = QVBoxLayout(c)
        l.setContentsMargins(8, 8, 8, 8)
        l.setSpacing(0)
        l.addWidget(self.stack_panel)
        
        from certus.ui.certus_ui import apply_certus_theme, set_certus_window_icon
        apply_certus_theme(self)
        set_certus_window_icon(self)

    def closeEvent(self, event):
        self.closed_signal.emit()
        super().closeEvent(event)

class OpticsPanelWidget(QWidget):
    """Standalone UI component for optical parameters."""
    mat_h_changed = pyqtSignal(str)
    mat_l_changed = pyqtSignal(str)
    thickness_update_requested = pyqtSignal()

    def __init__(self, material_list, parent=None):
        super().__init__(parent)
        self.material_list = material_list
        self._build_ui()

    def _create_spin(self, val: float, min_val: float = 0.0, max_val: float = 10000.0, step: float = 0.01, dec: int = 2, suffix: str = "") -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setDecimals(dec)
        spin.setSingleStep(step)
        spin.setValue(val)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        if suffix:
            spin.setSuffix(suffix)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        spin.setMaximumWidth(120)
        return spin

    def _create_combo(self, default_val: str, allow_air: bool = True, items_list: list[str] | tuple[str, ...] = None) -> QComboBox:
        combo = QComboBox()
        if allow_air:
            combo.addItem("Air")
        items = items_list if items_list is not None else self.material_list
        for mat in items:
            combo.addItem(mat)
        idx = combo.findText(default_val)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setMaximumWidth(160)
        return combo

    def _build_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        
        self.combo_mat_H = self._create_combo("H800-Nb2O5", allow_air=False)
        self.combo_mat_L = self._create_combo("H800-SiO2", allow_air=False)
        self.combo_mat_Sub = self._create_combo("SiO2", allow_air=False, items_list=SUBSTRATE_CHOICES)
        self.combo_mat_Sup = self._create_combo("Air", allow_air=True)
        self.edit_l0 = self._create_spin(1064.0, dec=1, suffix=" nm")
        self.edit_lcalc = QLineEdit("1064.0")
        self.edit_lcalc.setMaximumWidth(120)
        
        self.combo_mat_H.setToolTip("High index material (H)")
        self.combo_mat_L.setToolTip("Low index material (L)")
        self.combo_mat_Sub.setToolTip("Substrate material index lookup")
        self.combo_mat_Sup.setToolTip("Superstrate medium (incident medium, e.g. Air)")
        self.edit_l0.setToolTip("Reference center wavelength")
        self.edit_lcalc.setToolTip("Field evaluation wavelength. Multiple values can be specified, separated by commas or semicolons (e.g. 1064, 532, 355).")

        self.edit_angle = self._create_spin(0.0, max_val=89.9, step=1.0, dec=1, suffix=" °")
        self.edit_angle.setToolTip("Angle of incidence (degrees)")
        
        self.combo_pol = QComboBox()
        self.combo_pol.setMaximumWidth(160)
        self.combo_pol.setToolTip("Polarization state of the incident field")
        self.combo_pol.addItems(["S (TE)", "P (TM)", "Average (Unpolarized)"])

        # Row 0
        grid.addWidget(QLabel("High Index Mat (H):"), 0, 0)
        grid.addWidget(self.combo_mat_H, 0, 1)
        grid.addWidget(QLabel("Center λ:"), 0, 2)
        grid.addWidget(self.edit_l0, 0, 3)

        # Row 1
        grid.addWidget(QLabel("Low Index Mat (L):"), 1, 0)
        grid.addWidget(self.combo_mat_L, 1, 1)
        grid.addWidget(QLabel("Evaluation λ:"), 1, 2)
        grid.addWidget(self.edit_lcalc, 1, 3)

        # Row 2
        grid.addWidget(QLabel("Substrate:"), 2, 0)
        grid.addWidget(self.combo_mat_Sub, 2, 1)
        grid.addWidget(QLabel("Angle of Incidence:"), 2, 2)
        grid.addWidget(self.edit_angle, 2, 3)

        # Row 3
        grid.addWidget(QLabel("Superstrate:"), 3, 0)
        grid.addWidget(self.combo_mat_Sup, 3, 1)
        grid.addWidget(QLabel("Polarization:"), 3, 2)
        grid.addWidget(self.combo_pol, 3, 3)

        # Add column stretches to keep it compact on the left
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 0)
        grid.setColumnStretch(4, 1)
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        grid.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 0, 4)

        # Connect signals
        self.combo_mat_H.currentTextChanged.connect(self.mat_h_changed.emit)
        self.combo_mat_L.currentTextChanged.connect(self.mat_l_changed.emit)
        self.combo_mat_H.currentTextChanged.connect(lambda _: self.thickness_update_requested.emit())
        self.combo_mat_L.currentTextChanged.connect(lambda _: self.thickness_update_requested.emit())
        self.edit_l0.valueChanged.connect(lambda _: self.thickness_update_requested.emit())


class StackPanelWidget(QWidget):
    """Standalone UI component for the stack structure."""
    table_item_changed = pyqtSignal(object)
    import_requested = pyqtSignal()
    structure_changed = pyqtSignal()
    pareto_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_updating_table = False
        self._build_ui()

    def _build_ui(self):
        stack_layout = QVBoxLayout(self)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_layers = QTableWidget(9, 3)
        self.table_layers.setHorizontalHeaderLabels(["Mat.", "QWOT", "Thickness (nm)"])
        self.table_layers.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_layers.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_layers.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_layers.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_layers.setAlternatingRowColors(True)
        self.table_layers.verticalHeader().setDefaultSectionSize(28)
        
        self.table_layers.setDragEnabled(True)
        self.table_layers.setAcceptDrops(True)
        self.table_layers.viewport().setAcceptDrops(True)
        self.table_layers.setDragDropOverwriteMode(False)
        self.table_layers.setDropIndicatorShown(True)
        self.table_layers.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        self.table_layers.itemChanged.connect(self.table_item_changed.emit)
        
        # Populate table
        self.is_updating_table = True
        for i in range(9):
            self.add_row_to_table(i, 1.0)
        self.is_updating_table = False
            
        self.btn_container = QWidget()
        grid = QGridLayout(self.btn_container)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setSpacing(4)
        
        self.btn_add_h = create_styled_button("+ H", variant="secondary", icon=certus_icon("plus"))
        self.btn_add_l = create_styled_button("+ L", variant="secondary", icon=certus_icon("plus"))
        self.btn_del_last = create_styled_button("- Last", variant="secondary", icon=certus_icon("minus"))
        self.btn_clear = create_styled_button("Clear", variant="secondary", icon=certus_icon("trash-2"))
        
        self.btn_add_h.setToolTip("Add a High index layer (H) at the end of the stack")
        self.btn_add_l.setToolTip("Add a Low index layer (L) at the end of the stack")
        self.btn_del_last.setToolTip("Remove the last layer or the currently selected layer")
        self.btn_clear.setToolTip("Clear all layers from the stack")
        
        def safe_add_layer(mat_str: str) -> None:
            try:
                row = self.table_layers.rowCount()
                self.table_layers.insertRow(row)
                self.is_updating_table = True
                self.add_row_to_table(row, 1.0, mat_str)
                self.is_updating_table = False
                self.structure_changed.emit()
            except Exception as e:
                logging.error(f"Failed to add layer {mat_str}: {e}")
                self.is_updating_table = False
                
        def safe_clear() -> None:
            try:
                self.is_updating_table = True
                self.table_layers.setRowCount(0)
                self.is_updating_table = False
                self.structure_changed.emit()
            except Exception as e:
                logging.error(f"Failed to clear table: {e}")
                
        def safe_import() -> None:
            try:
                self.import_requested.emit()
            except Exception as e:
                logging.error(f"Failed to emit import request: {e}")
                
        def safe_pareto() -> None:
            try:
                self.pareto_requested.emit()
            except Exception as e:
                logging.error(f"Failed to emit pareto request: {e}")
        
        self.btn_add_h.clicked.connect(lambda: safe_add_layer("H"))
        self.btn_add_l.clicked.connect(lambda: safe_add_layer("L"))
        self.btn_del_last.clicked.connect(self.on_del_layer)
        self.btn_clear.clicked.connect(safe_clear)
        
        grid.addWidget(self.btn_add_h, 0, 0)
        grid.addWidget(self.btn_add_l, 0, 1)
        grid.addWidget(self.btn_del_last, 0, 2)
        grid.addWidget(self.btn_clear, 0, 3)
        
        self.btn_load_json = create_styled_button("Load JSON", variant="secondary", icon=certus_icon("folder-open"))
        self.btn_load_json.setToolTip("Load stack structure from a JSON design file")
        self.btn_load_json.clicked.connect(safe_import)
        
        self.btn_pareto = create_styled_button("🏆 Open Pareto Front", variant="primary")
        self.btn_pareto.setToolTip("Open the Pareto Front explorer window to analyze design trade-offs")
        self.btn_pareto.clicked.connect(safe_pareto)
        
        grid.addWidget(self.btn_load_json, 1, 0, 1, 2)
        grid.addWidget(self.btn_pareto, 1, 2, 1, 2)
        
        stack_layout.addWidget(self.table_layers)
        stack_layout.addWidget(self.btn_container)
        
        self.btn_container.setVisible(False)

    def set_controls_visible(self, visible: bool) -> None:
        if hasattr(self, "btn_container"):
            self.btn_container.setVisible(visible)

    def add_row_to_table(self, row: int, qwot: float, mat_str: str = None) -> None:
        """Adds or updates a row in the layers table securely."""
        try:
            if mat_str is None:
                mat_str = "H" if row % 2 == 0 else "L"
            
            # Guardrail: ensure the row exists
            if row >= self.table_layers.rowCount():
                return
                
            item_mat = QTableWidgetItem(mat_str)
            item_mat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_qwot = QTableWidgetItem(f"{qwot:.4f}")
            item_qwot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_thick = QTableWidgetItem("0.0")
            item_thick.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.table_layers.setItem(row, 0, item_mat)
            self.table_layers.setItem(row, 1, item_qwot)
            self.table_layers.setItem(row, 2, item_thick)
        except Exception as e:
            logging.error(f"Error in add_row_to_table: {e}")

    def on_add_layer(self) -> None:
        try:
            row = self.table_layers.rowCount()
            self.table_layers.insertRow(row)
            self.is_updating_table = True
            self.add_row_to_table(row, 1.0)
            self.is_updating_table = False
            self.structure_changed.emit()
        except Exception as e:
            logging.error(f"Error in on_add_layer: {e}")
            self.is_updating_table = False

    def on_del_layer(self) -> None:
        """Safely removes a layer with UI protections."""
        try:
            if self.table_layers.rowCount() == 0:
                return
                
            row = self.table_layers.currentRow()
            if row >= 0:
                self.table_layers.removeRow(row)
            else:
                row = self.table_layers.rowCount() - 1
                if row >= 0:
                    self.table_layers.removeRow(row)
            
            self.is_updating_table = True
        except Exception as e:
            logging.error(f"Error deleting layer: {e}")
            self.is_updating_table = False
            return
            
        try:
            self.rebuild_material_pattern()
        finally:
            self.is_updating_table = False
        self.structure_changed.emit()

    def rebuild_material_pattern(self):
        for row in range(self.table_layers.rowCount()):
            mat_item = self.table_layers.item(row, 0)
            if mat_item is None:
                mat_item = QTableWidgetItem()
                mat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_layers.setItem(row, 0, mat_item)
            mat_item.setText("H" if row % 2 == 0 else "L")


class OptimizationPanelWidget(QWidget):
    """Standalone UI component for optimization parameters."""
    calc_requested = pyqtSignal()
    opt_requested = pyqtSignal()
    mc_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _create_spin(self, val: float, min_val: float = 0.0, max_val: float = 10000.0, step: float = 0.01, dec: int = 2, suffix: str = "") -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setDecimals(dec)
        spin.setSingleStep(step)
        spin.setValue(val)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        if suffix:
            spin.setSuffix(suffix)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        spin.setMaximumWidth(120)
        return spin

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        form_opt_w = QWidget()
        grid = QGridLayout(form_opt_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        
        self.edit_seuil1 = self._create_spin(3.0, max_val=1000.0, dec=2)
        self.edit_seuil2 = self._create_spin(25.0, max_val=1000.0, dec=2)
        self.edit_alpha = self._create_spin(10.0, max_val=1000.0, dec=1)
        self.edit_mc_error = self._create_spin(2.0, max_val=20.0, step=0.1, dec=1, suffix=" %")
        self.edit_mc_iter = self._create_spin(50, max_val=1000, step=1, dec=0)
        self.edit_rmin = self._create_spin(1.0, min_val=0.0, max_val=1.0, step=0.01, dec=2)
        self.edit_rmax = self._create_spin(1.0, min_val=0.0, max_val=1.0, step=0.01, dec=2)
        
        self.chk_min_field = QCheckBox("Active Field Minimization")
        self.chk_global_opt = QCheckBox("Global Optimization")
        self.chk_allow_growth = QCheckBox("Authorize change of number layer")
        
        self.edit_seuil1.setToolTip("Laser Induced Damage Threshold (LIDT) for High index layer material (J/cm²)")
        self.edit_seuil2.setToolTip("Laser Induced Damage Threshold (LIDT) for Low index layer material (J/cm²)")
        self.edit_alpha.setToolTip("Penalty weight alpha for damage threshold violations in the cost function")
        self.edit_mc_error.setToolTip("Monte-Carlo normal thickness perturbation standard deviation percentage")
        self.edit_mc_iter.setToolTip("Number of Monte-Carlo runs for sensitivity and tolerancing analysis")
        self.edit_rmin.setToolTip("Minimum Reflectance constraint applied on all evaluation wavelengths (0.0 to 1.0)")
        self.edit_rmax.setToolTip("Maximum Reflectance constraint applied on all evaluation wavelengths (0.0 to 1.0)")
        self.chk_min_field.setToolTip("Enable continuous field minimization weighted by LIDT, instead of a simple threshold barrier.")
        self.chk_global_opt.setToolTip("Use Differential Evolution (global search) instead of Multi-Start L-BFGS-B (local search).")
        self.chk_allow_growth.setToolTip("Authorize automatic layer insertion and deletion during optimization (Needle synthesis loop).")

        # Row 0: Threshold H vs Rmin
        grid.addWidget(QLabel("LIDT H (J/cm²):"), 0, 0)
        grid.addWidget(self.edit_seuil1, 0, 1)
        grid.addWidget(QLabel("Rmin:"), 0, 2)
        grid.addWidget(self.edit_rmin, 0, 3)

        # Row 1: Threshold L vs Rmax
        grid.addWidget(QLabel("LIDT L (J/cm²):"), 1, 0)
        grid.addWidget(self.edit_seuil2, 1, 1)
        grid.addWidget(QLabel("Rmax:"), 1, 2)
        grid.addWidget(self.edit_rmax, 1, 3)

        # Row 2: Weight vs MC Error
        grid.addWidget(QLabel("Weight (α):"), 2, 0)
        grid.addWidget(self.edit_alpha, 2, 1)
        grid.addWidget(QLabel("MC Error:"), 2, 2)
        grid.addWidget(self.edit_mc_error, 2, 3)

        # Row 3: MC Iterations & Active Minimization
        grid.addWidget(self.chk_min_field, 3, 0, 1, 2)
        grid.addWidget(QLabel("MC Iterations:"), 3, 2)
        grid.addWidget(self.edit_mc_iter, 3, 3)
        
        self.edit_dmin = self._create_spin(5.0, min_val=0.0, max_val=100.0, step=0.5, dec=1, suffix=" nm")
        self.edit_dmin.setToolTip("Minimum thickness to keep a layer during final cleaning step")
        
        # Row 4: Global Optimization & Allow Growth
        grid.addWidget(self.chk_global_opt, 4, 0, 1, 2)
        grid.addWidget(self.chk_allow_growth, 4, 2, 1, 2)
        
        # Row 5: dmin
        grid.addWidget(QLabel("Min Thickness:"), 5, 0)
        grid.addWidget(self.edit_dmin, 5, 1)

        # Add column stretches to keep it compact on the left
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 0)
        grid.setColumnStretch(4, 1)
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        grid.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 0, 4)
        
        btn_actions_layout_w = QWidget()
        btn_actions_layout = QHBoxLayout(btn_actions_layout_w)
        btn_actions_layout.setContentsMargins(0, 8, 0, 0)
        btn_actions_layout.setSpacing(8)
        
        self.btn_calc = create_styled_button("Calculate Field", variant="primary", icon=certus_icon("activity", color="#FFFFFF"))
        self.btn_calc.setToolTip("Compute and plot the electric field profile for the current design")
        self.btn_opt = create_styled_button("Run Optimization", variant="success", icon=certus_icon("sparkles", color="#FFFFFF"))
        self.btn_opt.setToolTip("Run thickness optimization to minimize electric field intensity")
        self.btn_mc = create_styled_button("Sensitivity Analysis (MC)", variant="secondary", icon=certus_icon("sliders"))
        self.btn_mc.setToolTip("Run Monte-Carlo sensitivity analysis on layer thicknesses")
        
        if not scipy_installed:
            self.btn_opt.setEnabled(False)
            self.btn_opt.setToolTip("SciPy required for optimization")
            self.btn_opt.setText("Optimization (SciPy not installed)")

        self.btn_calc.clicked.connect(self.calc_requested.emit)
        self.btn_opt.clicked.connect(self.opt_requested.emit)
        self.btn_mc.clicked.connect(self.mc_requested.emit)
        
        btn_actions_layout.addWidget(self.btn_calc)
        btn_actions_layout.addWidget(self.btn_opt)
        btn_actions_layout.addWidget(self.btn_mc)
        
        layout.addWidget(form_opt_w)
        layout.addWidget(btn_actions_layout_w)



class CertusFieldWorkersMixin:
    """CertusFieldWorkersMixin."""

    def on_worker_plot(self, plot_data: dict, msg: str):
        """Intermediate plot callback during optimization — updates all field targets.

        Uses _get_plot_targets so that the overview widget (plot_widget_ov)
        and any detached window are also refreshed, not just the dedicated tab.
        Throttles redraws to keep the UI responsive during PGlobal.
        """
        if hasattr(self, "status_label"):
            self.status_label.setText(msg)

        now = __import__("time").monotonic()
        last_ts = getattr(self, "_last_field_plot_refresh_ts", 0.0)
        if now - last_ts < 0.12:
            self._pending_field_plot_data = plot_data
            self._pending_field_plot_msg = msg
            return
        self._last_field_plot_refresh_ts = now
        self._pending_field_plot_data = None
        self._pending_field_plot_msg = None

        # _get_plot_targets covers: plot_widget, plot_widget_ov, detached window
        for target in self._get_plot_targets("field_profile", self.plot_widget):
            target.update_nominal_plot(plot_data, initial_data=self._initial_field_data)
        self._set_last_plot_data(plot_data)

    def on_worker_finished(self, result):
        action = getattr(self.worker, "request", None) and self.worker.request.action
        synthesis_was_active = getattr(self, "_synthesis_active", False)

        # If standard execution (not synthesis) or worker failed, we reset running and enable buttons
        if not getattr(self, "_synthesis_active", False) or not result.success:
            self._is_running = False
            self.btn_calc.setEnabled(True)
            self.btn_opt.setEnabled(True)
            self.btn_mc.setEnabled(True)
            self._synthesis_active = False
            self._last_field_plot_refresh_ts = 0.0
            self._pending_field_plot_data = None
            self._pending_field_plot_msg = None
            self._field_opt_started_ts = None
            if hasattr(self, "field_opt_status"):
                self.field_opt_status.setText("Ready")
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

        if not result.success:
            if hasattr(self, "progress_widget"):
                self.progress_widget.stop(f"Error: {result.message}")

        if result.success:
            if hasattr(self, "status_label"):
                self.status_label.setText(result.message)

            if result.pareto_solutions and len(result.pareto_solutions) > 1:
                self.logger.info("--- Top Solutions (Pareto Multi-Start) ---")
                for i, s in enumerate(result.pareto_solutions):
                    self.logger.info(f"Solution {i+1}: Cost = {s['cost']:.4f}, QWOT Sum = {s['qwot_sum']:.4f}")

            plot_data = self._build_plot_data(result)
            if getattr(result, 'z_coords_mc', None) and getattr(result, 'E2_mc_runs', None):
                for target in self._get_plot_targets("field_profile", self.plot_widget):
                    target.update_mc_plot(result.z_coords_mc, result.E2_mc_runs, result.lambda_calcs)
                if plot_data.z_coords and plot_data.E2_values_list:
                    self._refresh_result_views(plot_data, clear_first=False)
            elif plot_data.z_coords and plot_data.E2_values_list:
                self._refresh_result_views(plot_data)

            if result.opt_emp_factors:
                self._skip_auto_calc = True
                self._is_updating_table = True
                try:
                    opt_types = getattr(result, "opt_layer_types", None)
                    if opt_types is not None or len(result.opt_emp_factors) != self.table_layers.rowCount():
                        FieldStackService.load_stack(self.table_layers, result.opt_emp_factors, opt_types)
                    else:
                        for r, q in enumerate(result.opt_emp_factors):
                            if self.table_layers.item(r, 1) is not None:
                                self.table_layers.item(r, 1).setText(f"{q:.4f}")
                finally:
                    self._is_updating_table = False
                self._update_thicknesses()
                
                # Record to Pareto history
                opt_t = opt_types if opt_types is not None else [i % 2 for i in range(len(result.opt_emp_factors))]
                cost_v = self._compute_cost(result.opt_emp_factors, opt_t)
                self._update_pareto_record(result.opt_emp_factors, cost_v)

                if hasattr(self, 'auto_calc_timer'):
                    self.auto_calc_timer.stop()
                QTimer.singleShot(500, lambda: setattr(self, "_skip_auto_calc", False))

            if not self._synthesis_active:
                if hasattr(self, "progress_widget"):
                    self.progress_widget.stop("Done" if result.success else f"Error: {result.message}")
                if action == "optimize" and result.pareto_solutions and len(result.pareto_solutions) > 1:
                    self._show_pareto_window()
                    self._pareto_cleanup_pending = True

                if action == "optimize":
                    if self._cleanup_thin_layers_and_reoptimize(source="optimization"):
                        return

            # Synthesis state machine
            if getattr(self, "_synthesis_active", False):
                if action == "optimize":
                    # Step A: Cleanup
                    removed = self.smart_cleanup(self.table_layers)
                    if removed > 0:
                        self.logger.info(f"[Synthesis] Smart cleanup removed {removed} layer(s).")
                    
                    # Read current stack from table
                    emp_factors = []
                    layer_types = []
                    for r in range(self.table_layers.rowCount()):
                        qwot_item = self.table_layers.item(r, 1)
                        if qwot_item is not None:
                            emp_factors.append(self._safe_float_from_item(qwot_item, 0.0))
                            layer_types.append(0 if self._normalize_layer_material(r) == "H" else 1)
                    
                    cost = self._compute_cost(emp_factors, layer_types)
                    self._update_pareto_record(emp_factors, cost)
                    self.logger.info(f"[Synthesis] Optimized cost after cleanup: {cost:.6f} (best seen: {self._synthesis_best_cost:.6f})")
                    
                    if cost < self._synthesis_best_cost - 1e-5:
                        # Improved! Update checkpoint
                        self._synthesis_best_cost = cost
                        self._synthesis_checkpoint = {
                            "emp_factors": emp_factors,
                            "layer_types": layer_types,
                            "cost": cost
                        }
                        
                        if len(emp_factors) >= 100:
                            self.logger.info(f"[Synthesis] Max layer count (100) reached. Stopping synthesis.")
                            self._synthesis_active = False
                            self._is_running = False
                            self.btn_calc.setEnabled(True)
                            self.btn_opt.setEnabled(True)
                            self.btn_mc.setEnabled(True)
                            if hasattr(self, "progress_widget"):
                                self.progress_widget.stop("Error: Max layers reached")
                        else:
                            # Start needle search
                            self.btn_calc.setEnabled(False)
                            self.btn_opt.setEnabled(False)
                            self.btn_mc.setEnabled(False)
                            try:
                                params = self._get_params()
                                self._start_worker(FieldWorkerRequest(action="needle", params=params))
                            except ValueError as e:
                                self._revert_to_synthesis_checkpoint()
                                self._synthesis_active = False
                                self._is_running = False
                                self.btn_calc.setEnabled(True)
                                self.btn_opt.setEnabled(True)
                                self.btn_mc.setEnabled(True)
                                if hasattr(self, "progress_widget"):
                                    self.progress_widget.stop("Error: Failed to get parameters")
                    else:
                        # Did not improve significantly
                        self.logger.info("[Synthesis] Cost did not improve significantly. Reverting to last best checkpoint and finishing.")
                        self._revert_to_synthesis_checkpoint()
                        self._synthesis_active = False
                        self._is_running = False
                        self.btn_calc.setEnabled(True)
                        self.btn_opt.setEnabled(True)
                        self.btn_mc.setEnabled(True)
                        if hasattr(self, "progress_widget"):
                            self.progress_widget.stop("Error: Stagnation")
                        
                elif action == "needle":
                    # Step B: Evaluate needle results
                    inserted = len(result.opt_emp_factors or []) > len(self._synthesis_checkpoint.get("emp_factors", []))
                    if inserted:
                        self.logger.info(f"[Synthesis] Needle found insertion. Growth to {len(result.opt_emp_factors)} layers. Running optimization...")
                        self.btn_calc.setEnabled(False)
                        self.btn_opt.setEnabled(False)
                        self.btn_mc.setEnabled(False)
                        try:
                            params = self._get_params()
                            params.global_opt = False  # Local refinement after needle split
                            params.synthesis_mode = True
                            self._start_worker(FieldWorkerRequest(action="optimize", params=params))
                        except ValueError as e:
                            self._revert_to_synthesis_checkpoint()
                            self._synthesis_active = False
                            self._is_running = False
                            self.btn_calc.setEnabled(True)
                            self.btn_opt.setEnabled(True)
                            self.btn_mc.setEnabled(True)
                            if hasattr(self, "progress_widget"):
                                self.progress_widget.stop("Error: Failed to get parameters")
                    else:
                        self.logger.info("[Synthesis] Needle did not find any beneficial insertion. Reverting and finishing.")
                        self._revert_to_synthesis_checkpoint()
                        self._synthesis_active = False
                        self._is_running = False
                        self.btn_calc.setEnabled(True)
                        self.btn_opt.setEnabled(True)
                        self.btn_mc.setEnabled(True)
                        if hasattr(self, "progress_widget"):
                            self.progress_widget.stop("Error: No needle insertion found")
        else:
            if hasattr(self, "field_opt_status"):
                self.field_opt_status.setText("Failed")
            show_toast(self, f"Failed: {result.message}", "error")
            self._last_field_plot_refresh_ts = 0.0
            self._pending_field_plot_data = None
            self._pending_field_plot_msg = None
            self._field_opt_started_ts = None
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

        if result.success and synthesis_was_active and not self._synthesis_active:
            if len(self.pareto_history) > 1:
                self._show_pareto_window()

    @pyqtSlot(tuple)
    def on_worker_error(self, err_tuple):
        exc_type, exc_val, exc_trace = err_tuple
        if getattr(self, "_synthesis_active", False):
            self._revert_to_synthesis_checkpoint()
            self._synthesis_active = False
        self._is_running = False
        self.btn_calc.setEnabled(True)
        self.btn_opt.setEnabled(True)
        self.btn_mc.setEnabled(True)
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop(f"Error: {exc_val}")
        if hasattr(self, "field_opt_status"):
            self.field_opt_status.setText("Error")
        show_toast(self, f"Fatal error: {exc_val}", "error")
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        if self.logger:
            self.logger.error(f"Worker Error: {exc_val}\n{''.join(traceback.format_exception(exc_type, exc_val, exc_trace))}")

    def _start_worker(self, request: FieldWorkerRequest):
        if request.action != "optimize":
            self._initial_field_data = None
            self._initial_spectral_data = None

        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            return

        self.worker = FieldWorkerThread(request)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.progress.connect(self.on_worker_progress)
        self.worker.signals.plot.connect(self.on_worker_plot)

        self._last_field_plot_refresh_ts = 0.0
        self._pending_field_plot_data = None
        self._pending_field_plot_msg = None
        self._field_opt_started_ts = __import__("time").monotonic()

        if hasattr(self, "progress_widget"):
            self.progress_widget.start()
        if hasattr(self, "field_opt_status"):
            mode = "PGLOBAL" if getattr(request.params, "global_opt", False) else "LOCAL"
            self.field_opt_status.setText(f"{mode} optimization running…  Gen —  Best —  Eval —  Time 0s")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        self.worker.start()

    @pyqtSlot(int, str)
    def on_worker_progress(self, progress, message):
        self.logger.info(f"[{progress}%] {message}")
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(progress, 100, phase=message)
        if hasattr(self, "field_opt_status"):
            elapsed = 0
            if hasattr(self, "_field_opt_started_ts"):
                elapsed = int(max(0.0, __import__("time").monotonic() - float(self._field_opt_started_ts)))
            self.field_opt_status.setText(f"{message} | Time {elapsed}s")
