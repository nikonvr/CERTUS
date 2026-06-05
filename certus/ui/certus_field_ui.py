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
from certus.ui.certus_ui import open_file_explorer
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


class CertusFieldApp(CertusBaseApp, CertusAppLogsMixin):
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
        self._finalize_init()

        # Connect additional signals for auto-calculation
        self.optics_panel.edit_lcalc.textChanged.connect(self.trigger_auto_calc)
        self.optics_panel.edit_angle.valueChanged.connect(self.trigger_auto_calc)
        self.optics_panel.combo_pol.currentIndexChanged.connect(self.trigger_auto_calc)
        self.optics_panel.combo_mat_Sub.currentIndexChanged.connect(self.trigger_auto_calc)
        self.optics_panel.combo_mat_Sup.currentIndexChanged.connect(self.trigger_auto_calc)

        self._update_thicknesses()
        if hasattr(self, 'toggle_details_btn'):
            self.toggle_details_btn.setChecked(True)

    def _get_default_splitter_sizes(self) -> list[int]:
        return [380, 1000]

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
        
    def _create_combo(self, default_val: str, allow_air: bool = True) -> QComboBox:
        combo = QComboBox()
        if allow_air:
            combo.addItem("Air")
        for mat in self.material_list:
            combo.addItem(mat)
        
        idx = combo.findText(default_val)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

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

    def _on_table_item_changed(self, item):
        if self._is_updating_table or self.stack_panel.is_updating_table or item is None:
            return
        col = item.column()
        if col in (0, 1):
            self._update_thicknesses()
        elif col == 2:
            self._update_qwot_from_thickness(item.row())

    def on_cleanup(self):
        removed = self.smart_cleanup(self.table_layers)
        if removed > 0:
            show_toast(self, f"Cleaned up {removed} layer(s).", variant="success")
        else:
            show_toast(self, "Stack is already clean.", variant="info")

    def on_needle(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self._initial_field_data = getattr(self, "_last_plot_data", None)
        self._initial_spectral_data = getattr(self, "_last_spectral_data", None)

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="needle", params=params))

    def _normalize_layer_material(self, row: int) -> str:
        mat_item = self.table_layers.item(row, 0)
        if mat_item is None:
            mat_item = QTableWidgetItem("H")
            mat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_layers.setItem(row, 0, mat_item)
        mat_str = mat_item.text().strip().upper()
        normalized = "H" if mat_str not in {"H", "L"} else mat_str
        if normalized != mat_item.text().strip().upper():
            mat_item.setText(normalized)
        return normalized

    def _safe_float_from_item(self, item: QTableWidgetItem | None, default: float = 0.0) -> float:
        if item is None:
            return default
        try:
            return float(item.text().strip().replace(",", "."))
        except (AttributeError, ValueError):
            return default

    def _parse_lambda_calcs(self) -> list[float]:
        raw = self.edit_lcalc.text().replace(';', ',')
        values = []
        for chunk in raw.split(','):
            token = chunk.strip()
            if not token:
                continue
            try:
                value = float(token)
            except ValueError as exc:
                raise ValueError(f"Invalid wavelength: {token}") from exc
            if value <= 0:
                raise ValueError(f"Wavelength must be positive: {value}")
            values.append(value)
        if not values:
            raise ValueError("Please enter at least one calculation wavelength.")
        return values

    def _get_n_for_material(self, mat_name: str, wl: float) -> float:
        if mat_name == "Air":
            return 1.0
        if self.materials_db and hasattr(self.materials_db, "_db"):
            try:
                db_ref = self.materials_db._db
                name_norm = mat_name.strip().lower()
                if name_norm in db_ref.SUBSTRATE_NAMES:
                    return float(db_ref.get_substrate_index(mat_name, wl).real)
                else:
                    return float(db_ref.get_material_index(mat_name, wl).real)
            except Exception:
                pass
        # Fallbacks to avoid crashes if DB is empty or fails
        if "Ta2O5" in mat_name: return 2.10
        if "Nb" in mat_name: return 2.20
        if "SiO2" in mat_name: return 1.46
        if "BK7" in mat_name: return 1.52
        return 1.5

    def _update_thicknesses(self):
        if self._is_updating_table:
            return
        self._is_updating_table = True
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)

            for row in range(self.table_layers.rowCount()):
                qwot_item = self.table_layers.item(row, 1)
                thick_item = self.table_layers.item(row, 2)
                if not (qwot_item and thick_item):
                    continue

                qwot_val = self._safe_float_from_item(qwot_item, 0.0)
                mat_str = self._normalize_layer_material(row)
                n = n1 if mat_str == "H" else n2

                thickness_nm = FieldStackService.calculate_thickness_nm(qwot_val, n, l0)

                self.stack_panel.is_updating_table = True
                thick_item.setText(f"{thickness_nm:.2f}")
                self.stack_panel.is_updating_table = False
        finally:
            self._is_updating_table = False
        
        self._update_index_profile_plot()
        self._update_spectral_response()
        self.trigger_auto_calc()

    def _update_qwot_from_thickness(self, row: int):
        if self._is_updating_table or row < 0 or row >= self.table_layers.rowCount():
            return
        self._is_updating_table = True
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)

            qwot_item = self.table_layers.item(row, 1)
            thick_item = self.table_layers.item(row, 2)
            if not (qwot_item and thick_item):
                return

            thick_val = self._safe_float_from_item(thick_item, 0.0)
            mat_str = self._normalize_layer_material(row)
            n = n1 if mat_str == "H" else n2

            qwot_val = FieldStackService.calculate_qwot(thick_val, n, l0)

            self.stack_panel.is_updating_table = True
            qwot_item.setText(f"{qwot_val:.4f}")
            self.stack_panel.is_updating_table = False
        finally:
            self._is_updating_table = False

        self._update_index_profile_plot()
        self._update_spectral_response()

    def _get_layer_material_read_only(self, row: int) -> str:
        mat_item = self.table_layers.item(row, 0)
        if mat_item is None:
            return "H" if row % 2 == 0 else "L"
        mat_str = mat_item.text().strip().upper()
        return mat_str if mat_str in {"H", "L"} else ("H" if row % 2 == 0 else "L")

    def _update_index_profile_plot(self):
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)
            n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), l0)
            n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), l0)

            thicknesses = []
            n_vals = []
            for row in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(row, 2)
                thick_val = self._safe_float_from_item(thick_item, 0.0)
                mat_str = self._get_layer_material_read_only(row)
                n = n1 if mat_str == "H" else n2

                if thick_val <= 0:
                    qwot_item = self.table_layers.item(row, 1)
                    qwot_val = self._safe_float_from_item(qwot_item, 0.0)
                    thick_val = FieldStackService.calculate_thickness_nm(qwot_val, n, l0)
                
                thicknesses.append(thick_val)
                n_vals.append(n)

            # Do NOT reverse them for index profile plotting. In CERTUS RE/STRAT, 
            # Substrate is at z=0 (left) and Superstrate is at z > 0 (right).
            if not thicknesses:
                z_coords = [0.0, 50.0]
                n_coords = [n_sub, n_sup]
            else:
                z_coords = [0.0, 0.0]
                n_coords = [n_sub, n_vals[0]]
                current_z = 0.0
                for i in range(len(thicknesses)):
                    current_z += thicknesses[i]
                    z_coords.extend([current_z, current_z])
                    if i < len(thicknesses) - 1:
                        n_coords.extend([n_vals[i], n_vals[i+1]])
                    else:
                        n_coords.extend([n_vals[i], n_sup])
                z_coords.extend([current_z + max(50.0, 0.1 * current_z)])
                n_coords.extend([n_sup])

            if hasattr(self, "profile_plot_widget"):
                for target in self._get_plot_targets("index_profile", self.profile_plot_widget):
                    target.plot_profile(z_coords, n_coords)
        except Exception as e:
            self.logger.debug(f"Error updating index profile plot: {e}")

    def _update_spectral_response(self):
        try:
            params = self._get_params()
            l0 = params.l0
            emp_factors = params.emp_factors
            layer_types = params.layer_types
            theta_inc = params.theta_inc
            pol_flag = params.pol_flag

            wls = np.linspace(max(350.0, 0.5 * l0), 1.5 * l0, 200)
            R_values = []
            for wl in wls:
                n1 = self._get_n_for_material(self.combo_mat_H.currentText(), wl)
                n2 = self._get_n_for_material(self.combo_mat_L.currentText(), wl)
                n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), wl)
                n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), wl)

                metrics = calculate_opt_metrics(
                    n1_r=n1,
                    n2_r=n2,
                    nSub_r=n_sub,
                    l0=l0,
                    emp_factors_list=emp_factors,
                    layer_types=layer_types,
                    n_super=n_sup,
                    theta_inc=theta_inc,
                    pol_flag=pol_flag,
                    lambda_calc=wl
                )
                R_values.append(metrics['R'])

            self._last_spectral_data = {
                'wavelengths': list(wls),
                'R_values': R_values
            }

            if hasattr(self, "spectral_plot_widget"):
                for target in self._get_plot_targets("spectral_response", self.spectral_plot_widget):
                    target.plot_spectral_response(list(wls), R_values, initial_data=self._initial_spectral_data)

            if hasattr(self, "table_spectral_res"):
                spec_headers = ["Wavelength (nm)", "Reflectance (R)"]
                spec_data = [[f"{wl:.2f}", f"{r:.6f}"] for wl, r in zip(wls, R_values)]
                self.table_spectral_res.set_data(spec_headers, spec_data)
        except Exception as e:
            self.logger.debug(f"Error updating spectral response: {e}")

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

    def detach_current_plot(self) -> None:
        """Clones the active plot tab into a detached floating window.

        Tab order (must match addTab call order in _build_right_panel):
          0 = Overview  (composite — not detachable individually)
          1 = Field           → field_profile
          2 = Spectrum         → spectral_response
          3 = Index          → index_profile
        """
        idx = self.tab_widget.currentIndex()
        if idx == 0:
            # Overview is composite; nothing to detach as a single plot
            show_toast(self, "Overview cannot be detached. Select an individual tab.", "info")
            return
        elif idx == 1:
            plot_name = "field_profile"
            plot_widget = self.plot_widget
            plot_title = "🔭 Electric Field Profile"
        elif idx == 2:
            plot_name = "spectral_response"
            plot_widget = self.spectral_plot_widget
            plot_title = "🌈 Spectral Response"
        elif idx == 3:
            plot_name = "index_profile"
            plot_widget = self.profile_plot_widget
            plot_title = "📊 Index Profile"
        else:
            return

        if plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            if win.isVisible():
                win.raise_()
                win.activateWindow()
                return

        import functools
        clone = clone_plot_widget(plot_widget, title_override=plot_title)
        if clone is not None:
            win = DetachedPlotWindow(clone, parent=self, title=plot_title)
            win.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))
            self.detached_plot_windows[plot_name] = win
            win.show()

    def reattach_plot(self, plot_name: str) -> None:
        """Safely close and clean up a detached plot window."""
        if plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            win.deleteLater()
            del self.detached_plot_windows[plot_name]

    def toggle_detach_stack(self) -> None:
        """Toggle the detachment of the stack panel into a separate window securely."""
        try:
            if self.detached_stack_window is None:
                self.detached_stack_window = DetachedStackWindow(self.stack_panel, parent=self)
                self.detached_stack_window.closed_signal.connect(self.reattach_stack)
                self.detached_plot_windows["stack_structure"] = self.detached_stack_window
                self.stack_panel.set_controls_visible(True)
                self.detached_stack_window.show()
                self.btn_detach_stack.setText("⬡ Reattach Stack")
            else:
                self.detached_stack_window.close()
        except Exception as e:
            logging.error(f"Error toggling detach stack: {e}")

    def reattach_stack(self) -> None:
        """Securely reattach the stack panel to the main interface."""
        try:
            if self.detached_stack_window is not None:
                self.card_stack.body.insertWidget(0, self.stack_panel)
                self.stack_panel.show()
                self.stack_panel.set_controls_visible(False)
                self.btn_detach_stack.setText("⬡ Detach Stack")
                
                try:
                    self.detached_stack_window.closed_signal.disconnect()
                except Exception:
                    pass
                
                if "stack_structure" in self.detached_plot_windows:
                    del self.detached_plot_windows["stack_structure"]
                self.detached_stack_window = None
        except Exception as e:
            logging.error(f"Error reattaching stack: {e}")

    def _apply_theme(self) -> None:
        plots_to_theme = []
        if hasattr(self, "plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("field_profile", self.plot_widget))
        if hasattr(self, "spectral_plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("spectral_response", self.spectral_plot_widget))
        if hasattr(self, "profile_plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("index_profile", self.profile_plot_widget))
            
        if plots_to_theme:
            self._apply_certus_compact_theme(plots=plots_to_theme)
        
        if hasattr(self, "log_text"):
            self.log_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {CertusTheme.SURFACE};
                    color: {CertusTheme.TEXT_MAIN};
                    border: 1px solid {CertusTheme.BORDER};
                    border-radius: 4px;
                }}
            """)

    def _setup_shortcuts(self) -> None:
        pass # Managed partly by base class

    def _get_plot_targets(self, plot_name: str, primary_widget) -> list:
        targets = []
        if plot_name == "field_profile":
            if hasattr(self, "plot_widget"):
                targets.append(self.plot_widget)
            if hasattr(self, "plot_widget_ov"):
                targets.append(self.plot_widget_ov)
        elif plot_name == "spectral_response":
            if hasattr(self, "spectral_plot_widget"):
                targets.append(self.spectral_plot_widget)
            if hasattr(self, "spectral_plot_widget_ov"):
                targets.append(self.spectral_plot_widget_ov)
        elif plot_name == "index_profile":
            if hasattr(self, "profile_plot_widget"):
                targets.append(self.profile_plot_widget)
            if hasattr(self, "profile_plot_widget_ov"):
                targets.append(self.profile_plot_widget_ov)
        else:
            targets.append(primary_widget)

        if hasattr(self, "detached_plot_windows") and plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            if win.isVisible() and hasattr(win, "plot_widget"):
                targets.append(win.plot_widget)
        return targets

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

    def _set_last_plot_data(self, plot_data):
        self._last_plot_data = FieldPlotData.from_any(plot_data).to_dict()

    def _refresh_result_views(self, plot_data: FieldPlotData, *, clear_first: bool = True) -> None:
        payload = plot_data.to_dict()
        
        # Extract layer types from the stack table
        layer_types = []
        for row in range(self.table_layers.rowCount()):
            layer_types.append(0 if self._normalize_layer_material(row) == "H" else 1)
        payload["layer_types"] = layer_types
        payload["sub_name"] = self.combo_mat_Sub.currentText()
        payload["sup_name"] = self.combo_mat_Sup.currentText()
        
        # Update field profile plots
        for target in self._get_plot_targets("field_profile", self.plot_widget):
            target.update_nominal_plot(payload, clear_first=clear_first, initial_data=self._initial_field_data)
            
        # Update index profile and spectral plots
        self._update_index_profile_plot()
        self._update_spectral_response()
        self._update_metrics_labels(plot_data)
        
        # Populate Field Result table
        if hasattr(self, "table_field_res") and plot_data.z_coords:
            headers = ["z (nm)"] + [f"|E|^2 (λ = {wl:g} nm)" for wl in plot_data.lambda_calcs]
            data = []
            for k in range(len(plot_data.z_coords)):
                row = [f"{plot_data.z_coords[k]:.2f}"]
                for w in range(len(plot_data.lambda_calcs)):
                    row.append(f"{plot_data.E2_values_list[w][k]:.6f}")
                data.append(row)
            self.table_field_res.set_data(headers, data)

        # Populate Design Result table
        if hasattr(self, "table_design_res"):
            params = self._get_params()
            n_H = self._get_n_for_material(self.combo_mat_H.currentText(), params.l0)
            n_L = self._get_n_for_material(self.combo_mat_L.currentText(), params.l0)
            design_headers = ["Layer", "Material", "Thickness (QWOT)", "Physical Thickness (nm)", f"Refractive Index (at {params.l0:g} nm)"]
            design_data = []
            # Add Superstrate row
            n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), params.l0)
            design_data.append(["0 (Superstrate)", self.combo_mat_Sup.currentText(), "-", "-", f"{n_sup:.4f}"])
            # Add Stack layers
            for r in range(self.table_layers.rowCount()):
                mat = self.table_layers.item(r, 0).text() if self.table_layers.item(r, 0) else ""
                qwot = self.table_layers.item(r, 1).text() if self.table_layers.item(r, 1) else ""
                thick = self.table_layers.item(r, 2).text() if self.table_layers.item(r, 2) else ""
                idx_val = n_H if mat == "H" else n_L
                design_data.append([
                    str(r + 1),
                    mat,
                    qwot,
                    thick,
                    f"{idx_val:.4f}"
                ])
            # Add Substrate row
            n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), params.l0)
            design_data.append([f"{self.table_layers.rowCount() + 1} (Substrate)", self.combo_mat_Sub.currentText(), "-", "-", f"{n_sub:.4f}"])
            self.table_design_res.set_data(design_headers, design_data)

        self._set_last_plot_data(payload)
        self.tab_widget.setCurrentIndex(0)

    def _copy_table_to_clipboard(self, table: ExcelTableWidget) -> None:
        lines = []
        cols = table.columnCount()
        hdr = [table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else "" for c in range(cols)]
        lines.append("\t".join(hdr))
        for r in range(table.rowCount()):
            row = [table.item(r, c).text() if table.item(r, c) else "" for c in range(cols)]
            lines.append("\t".join(row))
        QApplication.clipboard().setText("\n".join(lines))

    def _copy_field_res_to_clipboard(self) -> None:
        if hasattr(self, "table_field_res"):
            self._copy_table_to_clipboard(self.table_field_res)
            show_toast(self, "Field data copied to clipboard!", "success")

    def _copy_spectral_res_to_clipboard(self) -> None:
        if hasattr(self, "table_spectral_res"):
            self._copy_table_to_clipboard(self.table_spectral_res)
            show_toast(self, "Spectral data copied to clipboard!", "success")

    def _copy_design_res_to_clipboard(self) -> None:
        if hasattr(self, "table_design_res"):
            self._copy_table_to_clipboard(self.table_design_res)
            show_toast(self, "Design data copied to clipboard!", "success")

    def _load_stack(self, emp_factors: list[float], layer_types: list[int] | None = None):
        normalized_layer_types = FieldStackService.normalize_layer_types(layer_types, len(emp_factors))
        FieldStackService.load_stack(self.stack_panel.table_layers, emp_factors, normalized_layer_types)

    def reset_to_defaults(self):
        from certus.utils.certus_reset_framework import reset_app_to_defaults
        return reset_app_to_defaults(self)

    def _load_defaults(self):
        self._skip_auto_calc = True
        try:
            # Restore OpticsPanel defaults
            self.combo_mat_H.setCurrentText("H800-Nb2O5")
            self.combo_mat_L.setCurrentText("H800-SiO2")
            self.combo_mat_Sub.setCurrentText("SiO2")
            self.combo_mat_Sup.setCurrentText("Air")
            self.edit_l0.setValue(1064.0)
            self.edit_lcalc.setText("1064.0")
            self.edit_angle.setValue(0.0)
            self.combo_pol.setCurrentIndex(0) # S (TE)

            # Restore OptimizationPanel defaults
            self.edit_seuil1.setValue(3.0)
            self.edit_seuil2.setValue(25.0)
            self.edit_alpha.setValue(10.0)
            self.edit_mc_error.setValue(2.0)
            self.edit_mc_iter.setValue(50.0)
            self.edit_rmin.setValue(1.0)
            self.edit_rmax.setValue(1.0)
            self.chk_min_field.setChecked(False)
            self.chk_global_opt.setChecked(False)
            self.chk_allow_growth.setChecked(False)
            self.opt_panel.edit_dmin.setValue(5.0)

            # Restore StackPanel table defaults
            self.stack_panel.is_updating_table = True
            self.table_layers.setRowCount(9)
            for i in range(9):
                self.stack_panel.add_row_to_table(i, 1.0)
            self.stack_panel.is_updating_table = False

            # Reset status and labels
            self.lbl_max_e2.setText("Peak |E|² : N/A")
            self.lbl_r.setText("R : N/A")
            
            # Reset internal data
            self.current_result = None
            self._last_plot_data = None
            self._initial_field_data = None
            self._initial_spectral_data = None
            self.pareto_history.clear()
            
            # Reset plot widgets
            self.plot_widget.clear()
            self.plot_widget_ov.clear()
            self.spectral_plot_widget.clear()
            self.spectral_plot_widget_ov.clear()
            self.profile_plot_widget.clear()
            self.profile_plot_widget_ov.clear()
        finally:
            self._skip_auto_calc = False
            self._update_thicknesses()

    def save_config(self):
        try:
            params = self._get_params()
        except Exception:
            show_toast(self, "Invalid configuration", "error")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Save Configuration", "", "JSON Files (*.json)")
        if not filename:
            return

        data = {
            "mat_H": self.combo_mat_H.currentText(),
            "mat_L": self.combo_mat_L.currentText(),
            "mat_Sub": self.combo_mat_Sub.currentText(),
            "mat_Sup": self.combo_mat_Sup.currentText(),
            "l0": params.l0,
            "lcalc": self.edit_lcalc.text(),
            "emp_factors": params.emp_factors,
            "layer_types": params.layer_types,
            "seuil1": params.seuil_int_1,
            "seuil2": params.seuil_int_2,
            "alpha": params.alpha,
            "theta_inc_deg": self.edit_angle.value(),
            "pol_idx": self.combo_pol.currentIndex(),
            "mc_error": self.edit_mc_error.value(),
            "mc_iter": int(self.edit_mc_iter.value()),
            "rmin": params.rmin,
            "rmax": params.rmax,
            "min_field_active": bool(params.min_field_active),
            "global_opt": bool(params.global_opt),
            "allow_growth": bool(self.chk_allow_growth.isChecked())
        }

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            show_toast(self, "Configuration saved successfully.", "success")
        except Exception as e:
            show_toast(self, f"Error saving: {e}", "error")

    def load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Configuration", "", "JSON Files (*.json)")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            def set_combo(combo: QComboBox, text: str):
                idx = combo.findText(text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    
            set_combo(self.combo_mat_H, data.get("mat_H", "H800-Nb2O5"))
            set_combo(self.combo_mat_L, data.get("mat_L", "H800-SiO2"))
            set_combo(self.combo_mat_Sub, data.get("mat_Sub", "SiO2"))
            set_combo(self.combo_mat_Sup, data.get("mat_Sup", "Air"))
            
            self.edit_l0.setValue(data.get("l0", 1064.0))
            self.edit_lcalc.setText(str(data.get("lcalc", "1064.0")))
            self.edit_seuil1.setValue(data.get("seuil1", 0.5))
            self.edit_seuil2.setValue(data.get("seuil2", 0.5))
            self.edit_alpha.setValue(data.get("alpha", 10.0))
            
            self.edit_angle.setValue(data.get("theta_inc_deg", 0.0))
            self.combo_pol.setCurrentIndex(data.get("pol_idx", 0))
            self.edit_mc_error.setValue(data.get("mc_error", 2.0))
            self.edit_mc_iter.setValue(data.get("mc_iter", 50))
            self.edit_rmin.setValue(data.get("rmin", 1.0))
            self.edit_rmax.setValue(data.get("rmax", 1.0))
            self.chk_min_field.setChecked(bool(data.get("min_field_active", False)))
            self.chk_global_opt.setChecked(bool(data.get("global_opt", False)))
            self.chk_allow_growth.setChecked(bool(data.get("allow_growth", False)))
            
            emp = data.get("emp_factors", [])
            layer_types = data.get("layer_types", [])

            self._is_updating_table = True
            try:
                self._load_stack(emp, layer_types)
            finally:
                self._is_updating_table = False
            self._update_thicknesses()
            
            show_toast(self, "Configuration loaded.", "success")
        except Exception as e:
            show_toast(self, f"Error loading: {e}", "error")

    def export_data(self):
        if not self._last_plot_data:
            show_toast(self, "No data to export. Run a calculation first.", "warning")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = get_resource_path("reports")
            os.makedirs(report_dir, exist_ok=True)

            base_name = f"Report_FIELD_{timestamp}"
            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")
            html_path = str(Path(report_dir) / f"{base_name}.html")

            params = self._get_params()
            sheets = {"Summary": self._build_summary_frame(params)}
            sheets.update(self._build_plot_export_frames(self._last_plot_data))
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

            if self._export_results_html(html_path):
                show_toast(self, "Excel and HTML reports generated successfully.", "success")
                self.logger.info(f"Reports generated in: {report_dir}")
            else:
                show_toast(self, "HTML error, Excel generated.", "warning")

        except Exception as e:
            show_toast(self, f"Export error: {e}", "error")
            self.logger.error(f"Export Error: {e}\n{traceback.format_exc()}")

    def export_png(self):
        if not self._last_plot_data:
            show_toast(self, "No plot to capture.", "warning")
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = get_resource_path("reports")
            os.makedirs(report_dir, exist_ok=True)
            png_path = str(Path(report_dir) / f"Capture_FIELD_{timestamp}.png")
            
            exporter = pyqtgraph.exporters.ImageExporter(self.plot_widget.plotItem)
            # High quality parameters
            exporter.parameters()['width'] = 1920
            exporter.export(png_path)
            show_toast(self, f"Screenshot saved: {png_path}", "success")
        except Exception as e:
            show_toast(self, f"Screenshot error: {e}", "error")

    def open_help(self):
        show_toast(self, "CERTUS Electric Field Optimization module.", "info")

    def _on_mat_h_changed(self, mat_name: str):
        for key, val in LIDT_PRESETS.items():
            if key in mat_name:
                self.edit_seuil1.setValue(val)
                break

    def _on_mat_l_changed(self, mat_name: str):
        for key, val in LIDT_PRESETS.items():
            if key in mat_name:
                self.edit_seuil2.setValue(val)
                break

    def _get_params(self) -> FieldParamsDTO:
        emp_factors = []
        layer_types = []
        for row in range(self.table_layers.rowCount()):
            qwot_item = self.table_layers.item(row, 1)
            if qwot_item is None:
                continue

            qwot_value = self._safe_float_from_item(qwot_item, default=np.nan)
            if not np.isfinite(qwot_value) or qwot_value <= 0:
                raise ValueError(f"Invalid QWOT at row {row + 1}.")

            emp_factors.append(qwot_value)
            layer_types.append(0 if self._normalize_layer_material(row) == "H" else 1)

        if not emp_factors:
            raise ValueError("Stack is empty.")

        lambda_calcs = self._parse_lambda_calcs()
        l0 = self.edit_l0.value()
        if l0 <= 0:
            raise ValueError("Center wavelength must be positive.")

        n1_rs = [self._get_n_for_material(self.combo_mat_H.currentText(), wavelength) for wavelength in lambda_calcs]
        n2_rs = [self._get_n_for_material(self.combo_mat_L.currentText(), wavelength) for wavelength in lambda_calcs]
        nSub_rs = [self._get_n_for_material(self.combo_mat_Sub.currentText(), wavelength) for wavelength in lambda_calcs]
        nSup_rs = [self._get_n_for_material(self.combo_mat_Sup.currentText(), wavelength) for wavelength in lambda_calcs]

        return FieldParamsDTO(
            n1_rs=n1_rs,
            n2_rs=n2_rs,
            nSub_rs=nSub_rs,
            n_supers=nSup_rs,
            l0=l0,
            lambda_calcs=lambda_calcs,
            emp_factors=emp_factors,
            layer_types=layer_types,
            seuil_int_1=self.edit_seuil1.value(),
            seuil_int_2=self.edit_seuil2.value(),
            alpha=self.edit_alpha.value(),
            maxiter=1000,
            theta_inc=np.radians(self.edit_angle.value()),
            pol_flag=self.combo_pol.currentIndex(),
            tolerate_error=self.edit_mc_error.value() / 100.0,
            mc_iterations=int(self.edit_mc_iter.value()),
            rmin=self.edit_rmin.value(),
            rmax=self.edit_rmax.value(),
            min_field_active=self.chk_min_field.isChecked(),
            global_opt=self.chk_global_opt.isChecked(),
            dmin=self.opt_panel.edit_dmin.value(),
        )

    def on_calc_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="calculate", params=params))

    def on_opt_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self._initial_field_data = getattr(self, "_last_plot_data", None)
        self._initial_spectral_data = getattr(self, "_last_spectral_data", None)

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)

        if self.chk_allow_growth.isChecked():
            self._synthesis_active = True
            self._synthesis_best_cost = float('inf')
            self._synthesis_stagnation_count = 0
            self._synthesis_checkpoint = {
                "emp_factors": list(params.emp_factors),
                "layer_types": list(params.layer_types),
                "cost": float('inf')
            }
            self.logger.info("Starting hidden Needle Synthesis loop (Authorize change of number layer mode)...")
            params.synthesis_mode = True
        else:
            self._synthesis_active = False

        self._start_worker(FieldWorkerRequest(action="optimize", params=params))

    def on_mc_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="tolerate", params=params))

    def on_import_design(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Design", "", "JSON Files (*.json)")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            # If the design file contains materials and center wavelength config, load them
            for key, combo in [("mat_H", self.combo_mat_H), ("mat_L", self.combo_mat_L), ("mat_Sub", self.combo_mat_Sub), ("mat_Sup", self.combo_mat_Sup)]:
                if key in data:
                    idx = combo.findText(data[key])
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
            if "l0" in data:
                try:
                    self.edit_l0.setValue(float(data["l0"]))
                except (ValueError, TypeError):
                    pass
            if "rmin" in data:
                try:
                    self.edit_rmin.setValue(float(data["rmin"]))
                except (ValueError, TypeError):
                    pass
            if "rmax" in data:
                try:
                    self.edit_rmax.setValue(float(data["rmax"]))
                except (ValueError, TypeError):
                    pass

            self._is_updating_table = True
            try:
                if "emp_factors" in data:
                    layer_types = data.get("layer_types", [])
                    self.table_layers.setRowCount(0)
                    for i, f_val in enumerate(data["emp_factors"]):
                        self.table_layers.insertRow(i)
                        material = None
                        if layer_types and i < len(layer_types):
                            material = "H" if layer_types[i] == 0 else "L"
                        self.stack_panel.add_row_to_table(i, float(f_val), mat_str=material)
                elif "layers" in data:
                    self.table_layers.setRowCount(0)
                    for i, layer in enumerate(data["layers"]):
                        material_name = str(layer.get("material", "H"))
                        thickness_nm = float(layer.get("physical_thickness_nm", 0.0))
                        self.table_layers.insertRow(i)
                        material = "H" if "H" in material_name.upper() else "L"
                        self.stack_panel.add_row_to_table(i, 1.0, mat_str=material)
                        self.table_layers.item(i, 2).setText(f"{thickness_nm:.2f}")
                else:
                    raise ValueError("Unrecognized file format.")
            finally:
                self._is_updating_table = False

            if "layers" in data:
                for i in range(self.table_layers.rowCount()):
                    self._update_qwot_from_thickness(i)
            else:
                self._update_thicknesses()
            
            show_toast(self, "Design imported successfully.", "success")

            # Build and show load summary popup
            sub_label = data.get("mat_Sub") or data.get("substrate_choice") or self.combo_mat_Sub.currentText()
            summary_lines = [
                f"SUBSTRATE: {sub_label}",
                "FACES: ONE FACE (NO BACKSIDE)",
                "",
                f"File: {Path(filename).resolve()}",
                "",
                "Design Parameters:",
                f"  High Index Material (H): {data.get('mat_H') or self.combo_mat_H.currentText()}",
                f"  Low Index Material (L): {data.get('mat_L') or self.combo_mat_L.currentText()}",
                f"  Superstrate: {data.get('mat_Sup') or self.combo_mat_Sup.currentText()}",
                f"  Center Wavelength (l0): {data.get('l0', self.edit_l0.value())} nm",
                "",
                "Structure Details:",
                f"  Total Layers: {self.table_layers.rowCount()}",
            ]
            total_thick = 0.0
            for r in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(r, 2)
                if thick_item:
                    try:
                        total_thick += float(thick_item.text().strip())
                    except ValueError:
                        pass
            summary_lines.append(f"  Total Physical Thickness: {total_thick:.2f} nm")

            # Create a vertical list popup mimicking CERTUS STRAT results
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout
            from PyQt6.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle("FIELD Load Summary")
            dlg.resize(450, 600)
            lay = QVBoxLayout(dlg)

            info = QLabel("\n".join(summary_lines))
            info.setWordWrap(True)
            lay.addWidget(info)

            tbl = QTableWidget()
            tbl.setColumnCount(3)
            tbl.setHorizontalHeaderLabels(["Mat", "QWOT", "Physical (nm)"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tbl.setRowCount(self.table_layers.rowCount())
            
            for row in range(self.table_layers.rowCount()):
                for col in range(3):
                    item = self.table_layers.item(row, col)
                    if item:
                        new_item = QTableWidgetItem(item.text())
                        new_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        new_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                        tbl.setItem(row, col, new_item)

            lay.addWidget(tbl)

            row_btn = QHBoxLayout()
            row_btn.addStretch()
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(dlg.close)
            row_btn.addWidget(btn_close)
            lay.addLayout(row_btn)

            dlg.exec()

        except Exception as e:
            self.logger.error(f"Import error: {str(e)}")
            show_toast(self, f"Error: {str(e)}", "error")


    def on_worker_plot(self, plot_data: dict, msg: str):
        """Intermediate plot callback during optimization — updates all field targets.

        Uses _get_plot_targets so that the overview widget (plot_widget_ov)
        and any detached window are also refreshed, not just the dedicated tab.
        """
        if hasattr(self, "status_label"):
            self.status_label.setText(msg)
        # _get_plot_targets covers: plot_widget, plot_widget_ov, detached window
        for target in self._get_plot_targets("field_profile", self.plot_widget):
            target.update_nominal_plot(plot_data, initial_data=self._initial_field_data)
        self._set_last_plot_data(plot_data)

    def _get_cleanup_dmin_nm(self) -> float:
        """Return the minimum thickness threshold used for post-optimization cleanup."""
        try:
            if hasattr(self, "opt_panel") and hasattr(self.opt_panel, "edit_dmin"):
                return max(0.0, float(self.opt_panel.edit_dmin.value()))
        except Exception:
            pass
        return 5.0

    def _stack_has_layers_below_dmin(self, dmin_nm: float) -> bool:
        if self.table_layers.rowCount() <= 0:
            return False
        for row in range(self.table_layers.rowCount()):
            thick_item = self.table_layers.item(row, 2)
            if thick_item is None:
                continue
            try:
                if float(thick_item.text()) < dmin_nm:
                    return True
            except Exception:
                continue
        return False

    def _remove_thin_layers_strict(self, dmin_nm: float) -> int:
        """Remove every layer thinner than ``dmin_nm`` and merge adjacent identical layers.

        Returns the number of rows removed. This is intentionally deterministic and
        conservative: it never deletes the whole stack and keeps at least one layer.
        """
        if self.table_layers.rowCount() <= 1:
            return 0

        removed_total = 0
        while self.table_layers.rowCount() > 1:
            rows_to_remove: list[int] = []
            for row in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(row, 2)
                if thick_item is None:
                    continue
                try:
                    thickness = float(thick_item.text())
                except Exception:
                    continue
                if thickness < dmin_nm:
                    rows_to_remove.append(row)

            # Keep at least one layer
            if len(rows_to_remove) >= self.table_layers.rowCount():
                rows_to_remove = rows_to_remove[:-1]

            if not rows_to_remove:
                break

            for row in reversed(rows_to_remove):
                self.table_layers.removeRow(row)
                removed_total += 1

            if self.table_layers.rowCount() > 1:
                self.rebuild_material_pattern()
                self.smart_cleanup(self.table_layers)
            if not self._stack_has_layers_below_dmin(dmin_nm):
                break

        return removed_total

    def _cleanup_thin_layers_and_reoptimize(self, *, source: str = "optimization") -> bool:
        """Remove layers thinner than dmin and relaunch a local optimization once."""
        dmin_nm = self._get_cleanup_dmin_nm()
        if self.table_layers.rowCount() <= 0 or not self._stack_has_layers_below_dmin(dmin_nm):
            return False

        self.logger.info("[FIELD] Post-%s cleanup triggered (dmin=%.2f nm).", source, dmin_nm)
        self._skip_auto_calc = True
        self._is_updating_table = True
        try:
            removed = self._remove_thin_layers_strict(dmin_nm)
        finally:
            self._is_updating_table = False

        if removed > 0:
            self.logger.info("[FIELD] strict cleanup removed %d thin layer(s).", removed)

        try:
            params = self._get_params()
        except ValueError as e:
            self.logger.warning("[FIELD] cleanup completed but local re-optimization could not start: %s", e)
            self._skip_auto_calc = False
            return True

        params.global_opt = False
        params.synthesis_mode = False
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="optimize", params=params))
        QTimer.singleShot(250, lambda: setattr(self, "_skip_auto_calc", False))
        return True

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

        if not result.success:
            if hasattr(self, "progress_widget"):
                self.progress_widget.stop(f"Failed: {result.message}")

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
                    self.progress_widget.stop(result.message)
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
                                self.progress_widget.stop("Max layers reached")
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
                                    self.progress_widget.stop("Failed to get parameters")
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
                            self.progress_widget.stop("Stagnation: reverted to checkpoint")
                        
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
                                self.progress_widget.stop("Failed to get parameters")
                    else:
                        self.logger.info("[Synthesis] Needle did not find any beneficial insertion. Reverting and finishing.")
                        self._revert_to_synthesis_checkpoint()
                        self._synthesis_active = False
                        self._is_running = False
                        self.btn_calc.setEnabled(True)
                        self.btn_opt.setEnabled(True)
                        self.btn_mc.setEnabled(True)
                        if hasattr(self, "progress_widget"):
                            self.progress_widget.stop("No needle insertion found: reverted to checkpoint")
        else:
            if hasattr(self, "status_label"):
                self.status_label.setText(f"Failed: {result.message}")
            show_toast(self, f"Failed: {result.message}", "error")

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
        if hasattr(self, "status_label"):
            self.status_label.setText(f"Error: {exc_val}")
        show_toast(self, f"Fatal error: {exc_val}", "error")
        if self.logger:
            self.logger.error(f"Worker Error: {exc_val}\n{''.join(traceback.format_exception(exc_type, exc_val, exc_trace))}")

    def _compute_cost(self, emp_factors: list[float], layer_types: list[int]) -> float:
        try:
            params = self._get_params()
        except ValueError:
            return float('inf')
        
        from certus.workers.certus_field_workers import top_level_objective_function
        return top_level_objective_function(
            emp_factors,
            params.n1_rs,
            params.n2_rs,
            params.nSub_rs,
            params.l0,
            params.seuil_int_1,
            params.seuil_int_2,
            params.alpha,
            params.integral_points,
            params.n_supers,
            params.theta_inc,
            params.pol_flag,
            params.lambda_calcs,
            layer_types,
            rmin=params.rmin,
            rmax=params.rmax,
            min_field_active=params.min_field_active
        )

    def _revert_to_synthesis_checkpoint(self):
        """Restore the best synthesis checkpoint and re-enable auto-calc.

        Mirrors the pattern of _restore_pareto_champion: _skip_auto_calc is
        reset AFTER the table is populated to avoid spurious intermediate
        auto-calc firings, then immediately unlocked so the UI stays reactive.
        """
        if hasattr(self, "_synthesis_checkpoint") and self._synthesis_checkpoint is not None:
            chk = self._synthesis_checkpoint
            # GUARD: block auto-calc noise during table reload
            self._skip_auto_calc = True
            self._is_updating_table = True
            try:
                FieldStackService.load_stack(self.table_layers, chk["emp_factors"], chk["layer_types"])
            finally:
                self._is_updating_table = False
            self._update_thicknesses()
            # CRITICAL: re-enable auto-calc so the UI stays reactive after revert
            self._skip_auto_calc = False
            self.logger.info(f"Reverted to best synthesis checkpoint (Cost={chk['cost']:.6f})")

    def on_load_json_clicked(self):
        self.on_import_design()

    def on_export_csv_clicked(self):
        """Export current field data to Excel (xlsx).

        Uses _last_plot_data (set after every successful calculation)
        instead of current_result which is never assigned.
        FieldExportService.build_plot_export_frames returns dict[str, DataFrame].
        """
        if not self._last_plot_data:
            show_toast(self, "No result to export. Run a calculation first.", "warning")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "", "Excel Files (*.xlsx)")
        if not filename:
            return

        try:
            sheets = FieldExportService.build_plot_export_frames(self._last_plot_data)
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            self.logger.info(f"Exported field data to {filename}")
            show_toast(self, "Data exported successfully.", "success")
        except Exception as e:
            self.logger.error(f"Export error: {str(e)}")
            show_toast(self, f"Export failed: {str(e)}", "error")

    def _export_results_html(self, html_path: str) -> bool:
        """Generate a professional standalone HTML report for field optimization."""
        try:
            params = self._get_params()
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare stack table rows
            rows = ""
            for r in range(self.table_layers.rowCount()):
                mat = self._normalize_layer_material(r)
                thick = self.table_layers.item(r, 2).text() if self.table_layers.item(r, 2) else "0.0"
                rows += f"<tr><td>{r+1}</td><td>{mat}</td><td>{thick} nm</td></tr>"

            html = f"""
            <html><head>
            <style>
                body {{ font-family: sans-serif; margin: 40px; color: #333; }}
                h1 {{ color: #2563eb; border-bottom: 2px solid #2563eb; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f8fafc; }}
                .meta {{ background: #f1f5f9; padding: 15px; border-radius: 8px; }}
            </style>
            </head><body>
                <h1>CERTUS-FIELD Report</h1>
                <div class="meta"><p>Generated: {now}</p><p>Objective: {params.l0}nm center λ</p></div>
                <h2>Layer Structure</h2>
                <table><tr><th>#</th><th>Material</th><th>Thickness</th></tr>{rows}</table>
            </body></html>"""
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            return True
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return False


        sections = [
            {
                "title": "Optical Configuration",
                "type": "kv",
                "content": {
                    "H Material": self.combo_mat_H.currentText(),
                    "L Material": self.combo_mat_L.currentText(),
                    "Substrate": self.combo_mat_Sub.currentText(),
                    "Superstrate": self.combo_mat_Sup.currentText(),
                    "Center λ (nm)": f"{params.l0:.1f}",
                    "Evaluation λ (nm)": lambda_calcs_str,
                    "Total Layers": str(self.table_layers.rowCount()),
                    "Total Thickness": f"{total_thickness_nm:.2f} nm",
                },
            },
            {
                "title": "Layer Structure",
                "type": "table",
                "content": stack_data
            },
            {
                "title": "Electric Field Details",
                "type": "text",
                "content": "This report contains the spatial distribution of the electric field intensity inside the thin film stack.",
            },
        ]

        all_sections = methodology_sections + sections

        figures = [self.plot_widget]
        if hasattr(self, "spectral_plot_widget"):
            figures.append(self.spectral_plot_widget)
        if hasattr(self, "profile_plot_widget"):
            figures.append(self.profile_plot_widget)

        return generate_html_report(html_path, "CERTUS-FIELD Report", all_sections, figures)

    def on_export_html_clicked(self):
        """Export a full HTML report.

        Guards on _last_plot_data instead of current_result
        (current_result is never assigned — _export_results_html
        reads the stack table and plot widgets directly).
        """
        if not self._last_plot_data:
            show_toast(self, "No result to export. Run a calculation first.", "warning")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "HTML Report", "", "HTML Files (*.html)")
        if not filename:
            return

        try:
            if self._export_results_html(filename):
                self.logger.info(f"Report generated at {filename}")
                show_toast(self, "Report generated.", "success")
            else:
                show_toast(self, "HTML Report generation failed.", "error")
        except Exception as e:
            self.logger.error(f"Report generation error: {str(e)}")
            show_toast(self, f"Report generation failed: {str(e)}", "error")

    def on_open_reports_clicked(self):
        report_dir = os.path.join(get_resource_path("."), "reports")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir, exist_ok=True)
        open_file_explorer(report_dir)

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
        self.worker.start()
        if hasattr(self, "progress_widget"):
            self.progress_widget.start()

    @pyqtSlot(int, str)
    def on_worker_progress(self, progress, message):
        self.logger.info(f"[{progress}%] {message}")
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(progress, 100, phase=message)

    def copy_logs_to_clipboard(self) -> None:
        from certus.ui.certus_ui import copy_app_logs_to_clipboard
        if copy_app_logs_to_clipboard(self):
            show_toast(self, "Logs copied to clipboard!", "success")
            if hasattr(self, "status_label"):
                self.status_label.setText("Logs copied to clipboard!")
        else:
            show_toast(self, "No logs to copy.", "warning")

    def trigger_auto_calc(self):
        if getattr(self, "_skip_auto_calc", False):
            return
        if hasattr(self, 'auto_calc_timer'):
            self.auto_calc_timer.start(300)

    def run_auto_calc(self):
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            if getattr(self.worker, 'request', None) and self.worker.request.action == "calculate":
                self.worker.stop()
                self.auto_calc_timer.start(100)
            return

        try:
            params = self._get_params()
        except ValueError:
            return

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="calculate", params=params))

    def _update_metrics_labels(self, plot_data: FieldPlotData):
        try:
            flat_e2 = [val for sublist in plot_data.E2_values_list for val in sublist]
            peak_e2 = max(flat_e2) if flat_e2 else 0.0
            self.lbl_max_e2.setText(f"Peak |E|² : {peak_e2:.4f}")
            
            # Now calculate R for each evaluation wavelength
            params = self._get_params()
            r_strs = []
            for i, wl in enumerate(params.lambda_calcs):
                metrics = calculate_opt_metrics(
                    n1_r=params.n1_rs[i],
                    n2_r=params.n2_rs[i],
                    nSub_r=params.nSub_rs[i],
                    l0=params.l0,
                    emp_factors_list=params.emp_factors,
                    layer_types=params.layer_types,
                    n_super=params.n_supers[i],
                    theta_inc=params.theta_inc,
                    pol_flag=params.pol_flag,
                    lambda_calc=wl
                )
                r_strs.append(f"R({wl:g}nm) = {metrics['R']:.4f}")
            
            self.lbl_r.setText(" | ".join(r_strs))
        except Exception as e:
            self.logger.debug(f"Error updating metrics labels: {e}")

    def _ensure_pareto_ui(self) -> bool:
        """Create Pareto window/table lazily and only when Qt is ready."""
        if self.pareto_window is not None:
            return True

        self.pareto_window = QDialog(self)
        self.pareto_window.setWindowTitle("Pareto Front Explorer - CERTUS-FIELD")
        self.pareto_window.setMinimumSize(850, 400)

        p_lay = QVBoxLayout(self.pareto_window)

        lbl = QLabel(
            "Double-click col 1-2 = load Best Cost | "
            "Double-click col 3-4 = load Best MC | "
            "Double-click col 5-6 = load Best Fab (>=5nm)"
        )
        lbl.setStyleSheet("font-size: 12px; margin-bottom: 5px; color: #475569;")
        p_lay.addWidget(lbl)

        self.pareto_table = QTableWidget(0, 8)
        self.pareto_table.setHorizontalHeaderLabels([
            "N Layers", "Best Cost", "d_min Cost",
            "Best MC", "d_min MC", "Best Fab", "d_min Fab",
            "Cost/N"
        ])
        self.pareto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pareto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pareto_table.verticalHeader().setVisible(False)
        self.pareto_table.setAlternatingRowColors(True)
        
        for i in range(8):
            self.pareto_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self.pareto_table.cellDoubleClicked.connect(self._load_pareto_design)
        p_lay.addWidget(self.pareto_table)

        f_p_btns = QHBoxLayout()

        clr_btn = QPushButton("Clear Pareto")
        clr_btn.setToolTip("Clear the Pareto front table.")
        clr_btn.clicked.connect(self._clear_pareto)

        exp_btn = QPushButton("Export HTML Report")
        exp_btn.setToolTip("Export Pareto front to an HTML report.")
        exp_btn.clicked.connect(self._export_pareto_report)

        f_p_btns.addWidget(clr_btn)
        f_p_btns.addStretch()
        f_p_btns.addWidget(exp_btn)
        p_lay.addLayout(f_p_btns)

        clr_btn.setStyleSheet("padding: 6px 12px; background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px;")
        exp_btn.setStyleSheet(f"padding: 6px 12px; background-color: {CertusTheme.PRIMARY}; color: white; border: none; border-radius: 4px;")

        self._refresh_pareto_table()
        return True

    def _show_pareto_window(self) -> None:
        """Display the Pareto table in a detachable window."""
        if not self._ensure_pareto_ui():
            return
        self._refresh_pareto_table()
        self.pareto_window.show()
        self.pareto_window.raise_()
        self.pareto_window.activateWindow()
        if getattr(self, "_pareto_cleanup_pending", False):
            self._pareto_cleanup_pending = False
            QTimer.singleShot(250, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))

    def _clear_pareto(self) -> None:
        self.pareto_history = {}
        self._refresh_pareto_table()

    def _refresh_pareto_table(self) -> None:
        if getattr(self, "pareto_table", None) is None:
            return
        self.pareto_table.setRowCount(0)
        for d, N in enumerate(sorted(self.pareto_history.keys())):
            self.pareto_table.insertRow(d)
            rec = self.pareto_history[N]
            self._populate_pareto_table_row(d, N, rec)

    def _populate_pareto_table_row(self, row_index: int, n_layers: int, rec: dict) -> None:
        i_layers = QTableWidgetItem(str(n_layers))
        i_layers.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        best_cost = rec.get("best_cost", float("inf"))
        i_cost = QTableWidgetItem(f"{best_cost:.5f}")
        i_cost.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        dmin_r = rec.get("dmin_rmse", 0.0)
        i_dmin_r = QTableWidgetItem(f"{dmin_r:.1f}")
        i_dmin_r.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_r < 5.0:
            i_dmin_r.setForeground(Qt.GlobalColor.red)

        best_mc = rec.get("best_mc", float("inf"))
        i_mc = QTableWidgetItem(f"{best_mc:.5f}")
        i_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        dmin_m = rec.get("dmin_mc", 0.0)
        i_dmin_m = QTableWidgetItem(f"{dmin_m:.1f}")
        i_dmin_m.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_m < 5.0:
            i_dmin_m.setForeground(Qt.GlobalColor.red)

        best_fab = rec.get("best_fab", float("inf"))
        i_fab = QTableWidgetItem(f"{best_fab:.5f}" if best_fab < float("inf") else "-")
        i_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if best_fab < float("inf"):
            i_fab.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_fab.setForeground(Qt.GlobalColor.gray)

        dmin_f = rec.get("dmin_fab", 0.0)
        i_dmin_f = QTableWidgetItem(f"{dmin_f:.1f}" if dmin_f > 0 else "-")
        i_dmin_f.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_f >= 5.0:
            i_dmin_f.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_dmin_f.setForeground(Qt.GlobalColor.gray)

        cost_per_n = best_cost / n_layers if n_layers > 0 and best_cost < float("inf") else float("inf")
        i_eff = QTableWidgetItem(f"{cost_per_n * 1000:.4f}" if cost_per_n < float("inf") else "-")
        i_eff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pareto_table.setItem(row_index, 0, i_layers)
        self.pareto_table.setItem(row_index, 1, i_cost)
        self.pareto_table.setItem(row_index, 2, i_dmin_r)
        self.pareto_table.setItem(row_index, 3, i_mc)
        self.pareto_table.setItem(row_index, 4, i_dmin_m)
        self.pareto_table.setItem(row_index, 5, i_fab)
        self.pareto_table.setItem(row_index, 6, i_dmin_f)
        self.pareto_table.setItem(row_index, 7, i_eff)

    def _update_pareto_record(self, emp_factors: list[float] | None = None, cost_val: float | None = None) -> None:
        """Records current configuration in Pareto history if better."""
        if emp_factors is None:
            emp_factors = []
            layer_types = []
            for r in range(self.table_layers.rowCount()):
                qwot_item = self.table_layers.item(r, 1)
                if qwot_item is not None:
                    emp_factors.append(self._safe_float_from_item(qwot_item, 0.0))
                    layer_types.append(0 if self._normalize_layer_material(r) == "H" else 1)
        else:
            try:
                params = self._get_params()
                layer_types = params.layer_types
                if len(layer_types) != len(emp_factors):
                    layer_types = [i % 2 for i in range(len(emp_factors))]
            except Exception:
                layer_types = [i % 2 for i in range(len(emp_factors))]

        if not emp_factors:
            return

        if cost_val is None:
            cost_val = self._compute_cost(emp_factors, layer_types)

        if not np.isfinite(cost_val) or cost_val < 0.0 or cost_val > 1e10:
            return

        N = len(emp_factors)

        try:
            params = self._get_params()
            _, ep_physical = get_layer_properties_from_list(
                params.n1_rs[0], params.n2_rs[0], emp_factors, layer_types, params.l0
            )
            dmin = float(np.min(ep_physical)) if len(ep_physical) > 0 else 0.0
        except Exception:
            dmin = 0.0
            ep_physical = np.array([])

        mc_cost = cost_val
        rng = np.random.default_rng(42)
        evals = []
        for _ in range(5):
            noise = rng.normal(0, 0.02, size=len(emp_factors))
            noisy_emp = np.maximum(np.array(emp_factors) + noise, 0.01).tolist()
            try:
                c = self._compute_cost(noisy_emp, layer_types)
                if c is not None and np.isfinite(c) and c < 1e20:
                    evals.append(c)
            except Exception:
                pass
        if evals:
            mc_cost = float(np.mean(evals))

        rec = self.pareto_history.setdefault(
            N,
            {
                "best_cost": float("inf"),
                "emp_rmse": None,
                "type_rmse": None,
                "dmin_rmse": 0.0,
                
                "best_mc": float("inf"),
                "emp_mc": None,
                "type_mc": None,
                "dmin_mc": 0.0,
                
                "best_fab": float("inf"),
                "emp_fab": None,
                "type_fab": None,
                "dmin_fab": 0.0,
            }
        )

        updated = False

        if cost_val < rec["best_cost"] - 1e-6:
            rec["best_cost"] = cost_val
            rec["emp_rmse"] = list(emp_factors)
            rec["type_rmse"] = list(layer_types)
            rec["dmin_rmse"] = dmin
            updated = True

        if mc_cost < rec["best_mc"] - 1e-6:
            rec["best_mc"] = mc_cost
            rec["emp_mc"] = list(emp_factors)
            rec["type_mc"] = list(layer_types)
            rec["dmin_mc"] = dmin
            updated = True

        is_fabricable = len(ep_physical) > 0 and np.all(ep_physical >= 5.0)
        if is_fabricable and cost_val < rec["best_fab"] - 1e-6:
            rec["best_fab"] = cost_val
            rec["emp_fab"] = list(emp_factors)
            rec["type_fab"] = list(layer_types)
            rec["dmin_fab"] = dmin
            updated = True

        if updated:
            self._refresh_pareto_table()

    def _load_pareto_design(self, row: int, col: int) -> None:
        try:
            N = int(self.pareto_table.item(row, 0).text())
            rec = self.pareto_history[N]

            load_mc = 3 <= col <= 4
            load_fab = 5 <= col <= 6

            if load_fab and rec.get("emp_fab") is not None:
                self._restore_pareto_champion(rec["emp_fab"], rec["type_fab"])
                self.logger.info(f"Loaded FAB champion for N={N} (Cost={rec['best_fab']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
            elif load_mc and rec.get("emp_mc") is not None:
                self._restore_pareto_champion(rec["emp_mc"], rec["type_mc"])
                self.logger.info(f"Loaded MC champion for N={N} (Cost={rec['best_mc']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
            elif rec.get("emp_rmse") is not None:
                self._restore_pareto_champion(rec["emp_rmse"], rec["type_rmse"])
                self.logger.info(f"Loaded Cost champion for N={N} (Cost={rec['best_cost']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
        except Exception as e:
            self.logger.error(f"Failed to load Pareto design: {e}")

    def _restore_pareto_champion(self, emp_factors: list[float], layer_types: list[int]) -> None:
        """Restore a Pareto champion into the layer table and trigger a fresh calculation."""
        self._skip_auto_calc = True
        self._is_updating_table = True
        try:
            FieldStackService.load_stack(self.table_layers, emp_factors, layer_types)
        finally:
            self._is_updating_table = False

        self._update_thicknesses()

        def _run_calc():
            self._skip_auto_calc = False
            self.on_calc_clicked()

        QTimer.singleShot(200, _run_calc)

    def _export_pareto_report(self) -> None:
        """Export a grouped HTML report summarizing the full Pareto front for Field."""
        if not self.pareto_history:
            show_toast(self, "Pareto history is empty.", "warning")
            return

        report_dir = os.path.join(get_resource_path("."), "reports")
        os.makedirs(report_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(report_dir, f"Pareto_Field_Summary_{ts}.html")

        rows_html = []
        for N in sorted(self.pareto_history.keys()):
            rec = self.pareto_history[N]
            best_cost = rec.get("best_cost", float("inf"))
            best_mc = rec.get("best_mc", float("inf"))
            best_fab = rec.get("best_fab", float("inf"))
            dmin_r = rec.get("dmin_rmse", 0.0)
            dmin_m = rec.get("dmin_mc", 0.0)
            dmin_f = rec.get("dmin_fab", 0.0)
            
            eff = best_cost / N if N > 0 and best_cost < float("inf") else 0.0
            
            rows_html.append(f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 12px; text-align: center; font-weight: bold; color: #1e293b;">{N}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #2563eb;">{best_cost:.5f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: {'#dc2626' if dmin_r < 5.0 else '#1e293b'};">{dmin_r:.1f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #d97706;">{best_mc:.5f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: {'#dc2626' if dmin_m < 5.0 else '#1e293b'};">{dmin_m:.1f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #16a34a;">{f"{best_fab:.5f}" if best_fab < float('inf') else '-'}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #16a34a;">{f"{dmin_f:.1f}" if dmin_f > 0 else '-'}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #64748b;">{eff * 1000:.4f}</td>
                </tr>
            """)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <title>CERTUS-FIELD - Pareto Front Summary</title>
    <style>
        body {{ background: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 40px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 32px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
        h1 {{ font-size: 28px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
        p {{ color: #64748b; font-size: 14px; margin-bottom: 24px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th {{ background: #f1f5f9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; padding: 12px; border-bottom: 2px solid #e2e8f0; }}
        tr:hover {{ background: #f8fafc; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏆 Pareto Front Summary</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Module: CERTUS-FIELD</p>
        <table>
            <thead>
                <tr>
                    <th>N Layers</th>
                    <th>Best Cost</th>
                    <th>d_min Cost (nm)</th>
                    <th>Best MC Cost</th>
                    <th>d_min MC (nm)</th>
                    <th>Best Fab Cost</th>
                    <th>d_min Fab (nm)</th>
                    <th>Cost/N &times;1000</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_template)
            self.logger.info(f"Pareto HTML report generated at {filename}")
            show_toast(self, "Pareto report generated successfully.", "success")
        except Exception as e:
            self.logger.error(f"Failed to generate Pareto report: {e}")
            show_toast(self, f"Generation failed: {str(e)}", "error")
