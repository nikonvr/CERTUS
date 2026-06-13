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
from certus.ui.certus_ui_utils import open_file_explorer
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



class CertusFieldEventsMixin:
    """CertusFieldEventsMixin."""

    def _on_table_item_changed(self, item):
        if self._is_updating_table or self.stack_panel.is_updating_table or item is None:
            return
        col = item.column()
        if col in (0, 1):
            self._update_thicknesses()
        elif col == 2:
            self._update_qwot_from_thickness(item.row())

    def _build_plot_export_frames(self, plot_data: dict) -> dict[str, pd.DataFrame]:
        return FieldExportService.build_plot_export_frames(plot_data)

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
        from certus.ui.certus_ui_utils import open_file_explorer
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
