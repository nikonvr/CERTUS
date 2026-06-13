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



class CertusFieldLayoutMixin:
    """CertusFieldLayoutMixin."""

    def _build_left_panel(self) -> QWidget:
        left_panel = QWidget()
        left_panel.setMinimumWidth(360)
        # left_panel.setMaximumWidth(420)  # Removed to free the splitter
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. Header (Logo)
        header_widget = create_header_logo_widget(
            "FIELD",
            self.APP_TITLE,
            logo_width=160,
            module_name="CERTUS_FIELD"
        )
        self.btn_theme = CertusThemeToggle(header_widget)
        header_widget.layout().addWidget(self.btn_theme)
        left_layout.addWidget(header_widget)

        # 2. Action Bar with log toggle
        self.toggle_details_btn = QPushButton("Show Details")
        self.toggle_details_btn.setCheckable(True)
        self.toggle_details_btn.setToolTip("Toggle the visibility of the application logs panel")
        self.toggle_details_btn.toggled.connect(self.on_toggle_details)
        
        self.btn_screenshot = create_styled_button("📸 Capture", variant="secondary")
        self.btn_screenshot.setToolTip("Save a screenshot of the electric field profile (PNG)")
        self.btn_screenshot.clicked.connect(self.export_png)

        self.btn_copy_log = create_styled_button("Copy Log", variant="secondary", icon=certus_icon("copy"))
        self.btn_copy_log.setToolTip("Copy the application logs to the clipboard")
        self.btn_copy_log.clicked.connect(self.copy_logs_to_clipboard)
        
        action_bar = create_top_actions_bar(self, self.save_config, self.load_config, self.export_data, self.open_help)
        action_bar.layout().addWidget(self.btn_screenshot)
        action_bar.layout().addWidget(self.toggle_details_btn)
        action_bar.layout().addWidget(self.btn_copy_log)
        
        left_layout.addWidget(action_bar)

        from certus.utils.certus_reset_framework import create_reset_button
        self.clear_btn = create_reset_button(self, use_app_reset=True)
        left_layout.addWidget(self.clear_btn)

        # 3. Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 8, 4, 0)
        scroll_layout.setSpacing(8)

        # -- Card: Optics
        card_optics = CertusCard("🔭 Optical Parameters", "Materials & Wavelengths")
        self.optics_panel = OpticsPanelWidget(self.material_list)
        
        # Connect to main app
        self.optics_panel.thickness_update_requested.connect(self._update_thicknesses)
        self.optics_panel.mat_h_changed.connect(self._on_mat_h_changed)
        self.optics_panel.mat_l_changed.connect(self._on_mat_l_changed)
        
        # Aliases for convenience during refactoring
        self.combo_mat_H = self.optics_panel.combo_mat_H
        self.combo_mat_L = self.optics_panel.combo_mat_L
        self.combo_mat_Sub = self.optics_panel.combo_mat_Sub
        self.combo_mat_Sup = self.optics_panel.combo_mat_Sup
        self.edit_l0 = self.optics_panel.edit_l0
        self.edit_lcalc = self.optics_panel.edit_lcalc
        self.edit_angle = self.optics_panel.edit_angle
        self.combo_pol = self.optics_panel.combo_pol
        
        card_optics.body.addWidget(self.optics_panel)
        scroll_layout.addWidget(CertusCollapsible("1  Materials Config", card_optics, expanded=True))

        # -- Card: Structure
        self.card_stack = CertusCard("🥞 Stack Structure", "Layers & Thicknesses")
        self.stack_panel = StackPanelWidget()
        
        self.stack_panel.table_item_changed.connect(self._on_table_item_changed)
        self.stack_panel.structure_changed.connect(self._update_thicknesses)
        self.stack_panel.import_requested.connect(self.on_import_design)
        self.stack_panel.pareto_requested.connect(self._show_pareto_window)
        
        btn_load_layout = QHBoxLayout()
        self.btn_detach_stack = create_styled_button("⬡ Detach Stack", variant="secondary")
        self.btn_detach_stack.setToolTip("Open the stack editor in a floating panel")
        self.btn_detach_stack.clicked.connect(self.toggle_detach_stack)
        btn_load_layout.addWidget(self.btn_detach_stack)
        
        self.table_layers = self.stack_panel.table_layers
        
        self.card_stack.body.addWidget(self.stack_panel)
        self.card_stack.body.addLayout(btn_load_layout)
        scroll_layout.addWidget(CertusCollapsible("2  Stack", self.card_stack, expanded=True))

        # -- Card: Optimisation
        card_opt = CertusCard("⚡ Optimization", "Weights & Controls")
        self.opt_panel = OptimizationPanelWidget()
        
        self.opt_panel.calc_requested.connect(self.on_calc_clicked)
        self.opt_panel.opt_requested.connect(self.on_opt_clicked)
        self.opt_panel.mc_requested.connect(self.on_mc_clicked)
        
        self.edit_seuil1 = self.opt_panel.edit_seuil1
        self.edit_seuil2 = self.opt_panel.edit_seuil2
        self.edit_alpha = self.opt_panel.edit_alpha
        self.edit_mc_error = self.opt_panel.edit_mc_error
        self.edit_mc_iter = self.opt_panel.edit_mc_iter
        self.edit_rmin = self.opt_panel.edit_rmin
        self.edit_rmax = self.opt_panel.edit_rmax
        self.chk_min_field = self.opt_panel.chk_min_field
        self.chk_global_opt = self.opt_panel.chk_global_opt
        self.chk_allow_growth = self.opt_panel.chk_allow_growth
        self.btn_calc = self.opt_panel.btn_calc
        self.btn_opt = self.opt_panel.btn_opt
        self.btn_mc = self.opt_panel.btn_mc
        
        card_opt.body.addWidget(self.opt_panel)
        scroll_layout.addWidget(CertusCollapsible("3  Action", card_opt, expanded=True))

        # -- Card: Metrics
        self.card_metrics = CertusCard("📊 Analytical Metrics", "Latest calculation results")
        metrics_layout_w = QWidget()
        metrics_layout = QVBoxLayout(metrics_layout_w)
        self.lbl_max_e2 = QLabel("Peak |E|² : N/A")
        self.lbl_r = QLabel("R : N/A")
        self.lbl_max_e2.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {CertusTheme.SUCCESS};")
        metrics_layout.addWidget(self.lbl_max_e2)
        metrics_layout.addWidget(self.lbl_r)
        self.card_metrics.body.addWidget(metrics_layout_w)
        scroll_layout.addWidget(self.card_metrics)

        # -- Card: Reports & Data
        card_reports = CertusCard("📁 Reports & Data", "Export history")
        rep_layout_w = QWidget()
        rep_layout = QVBoxLayout(rep_layout_w)
        self.btn_open_reports = create_styled_button("📂 Open Reports Folder", variant="secondary")
        self.btn_open_reports.setToolTip("Open the folder containing exported reports in File Explorer")
        self.btn_open_reports.clicked.connect(self.on_open_reports_clicked)
        rep_layout.addWidget(self.btn_open_reports)
        
        card_reports.body.addWidget(rep_layout_w)
        scroll_layout.addWidget(card_reports)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        return left_panel

    def _build_right_panel(self) -> QWidget:
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)

        # Tab 1: Overview (field + spectral + index simultaneously)
        overview_container = QWidget()
        overview_layout = QVBoxLayout(overview_container)
        overview_layout.setContentsMargins(4, 4, 4, 4)
        overview_layout.setSpacing(6)

        overview_hint = QLabel("Overview — field, spectral response and index profile visible together")
        overview_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        overview_layout.addWidget(overview_hint)

        overview_grid = QGridLayout()
        overview_grid.setHorizontalSpacing(8)
        overview_grid.setVerticalSpacing(8)

        field_panel = QWidget()
        field_layout = QVBoxLayout(field_panel)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_title = QLabel("Electric field")
        field_title.setStyleSheet("font-weight: 600;")
        field_layout.addWidget(field_title)
        self.plot_widget_ov = CertusFieldPlotWidget()
        field_layout.addWidget(self.plot_widget_ov)

        spectral_panel = QWidget()
        spectral_layout = QVBoxLayout(spectral_panel)
        spectral_layout.setContentsMargins(0, 0, 0, 0)
        spectral_layout.setSpacing(4)
        spectral_title = QLabel("Spectral response")
        spectral_title.setStyleSheet("font-weight: 600;")
        spectral_layout.addWidget(spectral_title)
        self.spectral_plot_widget_ov = CertusSpectralPlotWidget()
        spectral_layout.addWidget(self.spectral_plot_widget_ov)

        profile_panel = QWidget()
        profile_layout = QVBoxLayout(profile_panel)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(4)
        profile_title = QLabel("Index profile")
        profile_title.setStyleSheet("font-weight: 600;")
        profile_layout.addWidget(profile_title)
        self.profile_plot_widget_ov = CertusIndexProfilePlotWidget()
        profile_layout.addWidget(self.profile_plot_widget_ov)

        overview_grid.addWidget(field_panel, 0, 0)
        overview_grid.addWidget(spectral_panel, 0, 1)
        overview_grid.addWidget(profile_panel, 1, 0, 1, 2)
        overview_layout.addLayout(overview_grid)
        self.tab_widget.addTab(overview_container, "Overview")

        # Focus tabs for dedicated inspection
        field_container = QWidget()
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(4, 4, 4, 4)
        self.plot_widget = CertusFieldPlotWidget()
        field_layout.addWidget(self.plot_widget)
        self.tab_widget.addTab(field_container, "Field")

        spectral_container = QWidget()
        spectral_layout = QVBoxLayout(spectral_container)
        spectral_layout.setContentsMargins(4, 4, 4, 4)
        self.spectral_plot_widget = CertusSpectralPlotWidget()
        spectral_layout.addWidget(self.spectral_plot_widget)
        self.tab_widget.addTab(spectral_container, "Spectrum")

        profile_container = QWidget()
        profile_layout = QVBoxLayout(profile_container)
        profile_layout.setContentsMargins(4, 4, 4, 4)
        self.profile_plot_widget = CertusIndexProfilePlotWidget()
        profile_layout.addWidget(self.profile_plot_widget)
        self.tab_widget.addTab(profile_container, "Index")

        # Field Result Tab
        field_res_container = QWidget()
        field_res_layout = QVBoxLayout(field_res_container)
        field_res_layout.setContentsMargins(4, 4, 4, 4)
        field_res_tb = QHBoxLayout()
        self.btn_copy_field_res = create_styled_button("Copy Field Data", "secondary")
        self.btn_copy_field_res.clicked.connect(self._copy_field_res_to_clipboard)
        field_res_tb.addWidget(self.btn_copy_field_res)
        field_res_tb.addStretch(1)
        field_res_layout.addLayout(field_res_tb)
        self.table_field_res = ExcelTableWidget()
        self.table_field_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        field_res_layout.addWidget(self.table_field_res, 1)
        self.tab_widget.addTab(field_res_container, "Field Result")

        # Spectral Result Tab
        spectral_res_container = QWidget()
        spectral_res_layout = QVBoxLayout(spectral_res_container)
        spectral_res_layout.setContentsMargins(4, 4, 4, 4)
        spectral_res_tb = QHBoxLayout()
        self.btn_copy_spectral_res = create_styled_button("Copy Spectral Data", "secondary")
        self.btn_copy_spectral_res.clicked.connect(self._copy_spectral_res_to_clipboard)
        spectral_res_tb.addWidget(self.btn_copy_spectral_res)
        spectral_res_tb.addStretch(1)
        spectral_res_layout.addLayout(spectral_res_tb)
        self.table_spectral_res = ExcelTableWidget()
        self.table_spectral_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        spectral_res_layout.addWidget(self.table_spectral_res, 1)
        self.tab_widget.addTab(spectral_res_container, "Spectral Result")

        # Design Result Tab
        design_res_container = QWidget()
        design_res_layout = QVBoxLayout(design_res_container)
        design_res_layout.setContentsMargins(4, 4, 4, 4)
        design_res_tb = QHBoxLayout()
        self.btn_copy_design_res = create_styled_button("Copy Design Data", "secondary")
        self.btn_copy_design_res.clicked.connect(self._copy_design_res_to_clipboard)
        design_res_tb.addWidget(self.btn_copy_design_res)
        design_res_tb.addStretch(1)
        design_res_layout.addLayout(design_res_tb)
        self.table_design_res = ExcelTableWidget()
        self.table_design_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        design_res_layout.addWidget(self.table_design_res, 1)
        self.tab_widget.addTab(design_res_container, "Design Result")

        right_top_widget = QWidget()
        right_top_layout = QVBoxLayout(right_top_widget)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 0)
        header_label = QLabel("Results")
        header_label.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.btn_detach = create_styled_button("⬡ Detach active tab", "secondary")
        self.btn_detach.setFixedHeight(24)
        self.btn_detach.setToolTip("Open the current tab in a separate window.")
        self.btn_detach.clicked.connect(self.detach_current_plot)
        header_layout.addWidget(self.btn_detach)

        right_top_layout.addLayout(header_layout)
        right_top_layout.addWidget(self.tab_widget)

        self.right_splitter.addWidget(right_top_widget)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setVisible(False)
        self.right_splitter.addWidget(self.log_text)

        self.right_splitter.setSizes([1000, 0])
        self.tab_widget.setCurrentIndex(0)
        return self.right_splitter

    def _build_plot_export_frames(self, plot_data: dict) -> dict[str, pd.DataFrame]:
        return FieldExportService.build_plot_export_frames(plot_data)

    def _build_summary_frame(self, params: FieldParamsDTO) -> pd.DataFrame:
        return FieldExportService.build_summary_frame(
            params,
            self.combo_mat_H,
            self.combo_mat_L,
            self.combo_mat_Sub,
            self.combo_mat_Sup,
            self.edit_angle,
            self.combo_pol,
        )

    def _build_plot_data(self, result) -> FieldPlotData:
        return FieldPlotData.from_any(result)
