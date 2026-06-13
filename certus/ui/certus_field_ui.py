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

from certus.ui.certus_ui_widgets_cards import CertusCard
from certus.ui.certus_base_app import CertusBaseApp, CertusAppLogsMixin
from certus.ui.certus_ui_widgets_factory import create_styled_button, create_header_logo_widget, create_top_actions_bar
from certus.ui.certus_ui_widgets_utils import CertusThemeToggle, DetachedPlotWindow, ExcelTableWidget
from certus.ui.certus_ui_widgets_layout import CertusCollapsible
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_utils import show_toast, open_file_explorer
from certus.ui.certus_ui_widgets_progress import EnhancedProgressWidget
from certus.ui.certus_plot import clone_plot_widget

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



from certus.ui.certus_field_layout_mixin import CertusFieldLayoutMixin
from certus.ui.certus_field_plot_mixin import CertusFieldPlotMixin
from certus.ui.certus_field_events_mixin import CertusFieldEventsMixin
from certus.ui.certus_field_workers_mixin import CertusFieldWorkersMixin
from certus.ui.certus_field_state_mixin import CertusFieldStateMixin


class CertusFieldApp(
    CertusBaseApp,
    CertusAppLogsMixin,
    CertusFieldLayoutMixin,
    CertusFieldPlotMixin,
    CertusFieldEventsMixin,
    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):
    APP_NAME = "CERTUS-FIELD"
    APP_TITLE = "Electric Field Optimization"
    APP_VERSION = "1.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_logger(self.APP_NAME)
        self.worker = None
        self.current_result = None
        self.detached_plot_windows = {}
        self.detached_stack_window = None
        self._is_updating_table = False
        self._skip_auto_calc = False
        self._initial_field_data = None
        self._initial_spectral_data = None
        self.pareto_history = {}
        self.pareto_window = None
        self._pareto_initialized = False
        self._pareto_cleanup_pending = False
        self._last_plot_data = None  # Initialized here to prevent AttributeError before first calculation

        # Auto-calculation timer setup
        self.auto_calc_timer = QTimer(self)
        self.auto_calc_timer.setSingleShot(True)
        self.auto_calc_timer.timeout.connect(self.run_auto_calc)

        # Init Material Database
        try:
            self.materials_db = MaterialDatabase(_resolve_strat_indices_db_path())
            self.material_list = self.materials_db.get_material_list()
        except Exception as e:
            self.logger.error(f"Error loading material database: {e}")
            self.materials_db = None
            self.material_list = []

        self._build_ui()
        self.progress_widget = EnhancedProgressWidget()
        self.status_bar.addPermanentWidget(self.progress_widget)
        self.field_opt_status = QLabel("Ready")
        self.field_opt_status.setObjectName("fieldOptStatus")
        self.field_opt_status.setStyleSheet("font-weight: 600; padding: 0 8px;")
        self.status_bar.addPermanentWidget(self.field_opt_status)
        self._finalize_init()

        # Connect additional signals for auto-calculation
        self.optics_panel.edit_lcalc.textChanged.connect(self.trigger_auto_calc)
        self.optics_panel.edit_angle.valueChanged.connect(self.trigger_auto_calc)


def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusFieldApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
