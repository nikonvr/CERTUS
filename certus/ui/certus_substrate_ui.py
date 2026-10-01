#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""


CERTUS Substrate Index - Substrate refractive index determination only


"""


import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    __version__,
)
from certus.core.certus_substrate_index import (
    SELLMEIER_DEFAULT_LOG_L1L2,
    SUBSTRATE_INDEX_MODELS,
    IndexCore,
    _align_xy_lengths,
    _filter_dataframe_bare_substrate_columns,
    _substrate_index_geom_fit_mask,
    _substrate_index_models_ordered_by_rmse,
    logger,
)
from certus.ui.certus_a11y import install_accessible_names
from certus.ui.certus_measurement_excel_ui import open_measurement_excel_interactive
from certus.ui.certus_substrate_index_dialog import (  # noqa: F401 - re-exported: callers import this name from here
    IndexTableDialog,
)
from certus.ui.certus_substrate_plot_utils import _add_pg_fit_band_outside_shading, _pg_plot_xy_split_band
from certus.ui.certus_ui import (
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    EnhancedProgressWidget,
    attach_excel_clipboard_context_menu,
    create_header_logo_widget,
    create_styled_button,
    init_certus_app,
    install_standard_shortcuts,
    open_documentation,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_atomic_io import atomic_open
from certus.utils.certus_qsettings import certus_settings
from certus.utils.certus_ux import Typography


class SubstrateIndexGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        # Model and Presenter initialization
        from certus.ui.certus_substrate_presenter import CertusSubstratePresenter
        self.presenter = CertusSubstratePresenter(self)

        self.df: pd.DataFrame | None = None
        self.last_dir: str | None = None
        self._last_loaded_measurement_path: str = ""
        self._last_quality_summary: str = "n/a"

        # Spectral smoothing filter parameters (Savitzky-Golay)
        self.current_window: int = 15
        self.current_poly: int = 2
        self.current_heavy: bool = False

        self._attach_ui_log_handler()

        self.settings = certus_settings("SFL", "CERTUS_SUBSTRATE_INDEX")
        self.last_dir = self.settings.value("last_dir", "")

        self._setup_ui()
        self.resize(1100, 850)

    @property
    def last_run_manifest(self) -> dict | None:
        """Presenter-backed manifest of the latest Sellmeier fit."""
        return getattr(self.presenter, "last_run_manifest", None)

    @property
    def validation_status(self) -> str:
        """Presenter-backed validation status string."""
        return getattr(self.presenter, "validation_status", "OK")

    # --- View Interface Implementations ---
    def is_cancel_requested(self) -> bool:
        return self._is_cancel_requested()

    def set_busy(self, busy: bool) -> None:
        self._set_busy(busy)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def log_message(self, message: str, level: str = "INFO") -> None:
        self.log(message, level)

    def update_progress(self, current: int, total: int, phase: str, extra_info: str = "") -> None:
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(current, total, phase=phase, extra_info=extra_info)

    def stop_progress(self, message: str) -> None:
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop(message)

    def display_results(self, x, n_results_raw, n_results_by_model, rmse_row, n_fit_meta, wl_min_fit, wl_max_fit, quality_summary) -> None:
        self._last_quality_summary = quality_summary

        self._plot_output_results(x, n_results_raw, n_results_by_model, rmse_row, wl_min_fit, wl_max_fit)
        self.main_tabs.setCurrentIndex(1)

    def export_substrate_datasheet(self) -> None:
        """P1-11: Export versioned substrate datasheet (JSON)."""
        if self.last_run_manifest is None:
            QMessageBox.warning(self, "Export", "No result available. Run a Sellmeier fit first.")
            return

        import json
        from datetime import datetime

        from PyQt6.QtWidgets import QFileDialog

        default_fn = f"Substrate_Datasheet_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export Datasheet", default_fn, "JSON Files (*.json)")
        if not path:
            return

        # Prepare payload from manifest
        payload = {
            "metadata": {
                "instrument": "CERTUS SUBSTRATE INDEX",
                "version": __version__,
                "export_date": datetime.now().isoformat(),
                "status": self.validation_status,
            },
            "substrate": {
                "source_file": self.last_run_manifest.get("source_file"),
                "file_hash": self.last_run_manifest.get("file_hash"),
                "sellmeier_coeffs": self.last_run_manifest.get("sellmeier_coeffs"),
                "fit_rmse": self.last_run_manifest.get("rmse"),
                "lambda_range_nm": self.last_run_manifest.get("lambda_range_nm"),
            },
        }

        try:
            with atomic_open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            self.log(f"Datasheet exported to {Path(path).name}", "SUCCESS")
        except (OSError, TypeError, ValueError) as e:
            self.log(f"Export failed: {e}", "ERROR")
            QMessageBox.critical(self, "Export Error", str(e))

    class _UILogHandler(logging.Handler):
        def __init__(self, append_fn):

            super().__init__(level=logging.INFO)

            self._append_fn = append_fn

            self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))

        def emit(self, record: logging.LogRecord) -> None:

            try:
                self._append_fn(self.format(record))

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

    def _attach_ui_log_handler(self) -> None:

        if not hasattr(self, "log_panel") or self.log_panel is None:
            return

        underlying_logger = getattr(logger, "logger", logger)
        for h in underlying_logger.handlers:
            if isinstance(h, SubstrateIndexGUI._UILogHandler):
                return

        h = SubstrateIndexGUI._UILogHandler(self.log_panel.log_text.append)

        h.setLevel(logging.INFO)

        underlying_logger.addHandler(h)

        self.log("UI log bridge attached (INFO+).", "INFO")

    def log(self, message: str, level: str = "INFO") -> None:

        level_u = str(level).upper().strip()

        _map = {
            "DEBUG": logger.debug,
            "INFO": logger.info,
            "WARNING": logger.warning,
            "ERROR": logger.error,
            "SUCCESS": logger.info,
        }

        _map.get(level_u, logger.info)(message)

    def _set_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_load"):
            self.btn_load.setEnabled(not busy)

        if hasattr(self, "btn_calc_n"):
            self.btn_calc_n.setEnabled((not busy) and (self.df is not None))
        if hasattr(self, "btn_export_datasheet"):
            self.btn_export_datasheet.setEnabled((not busy) and (self.last_run_manifest is not None))

    def _get_fit_range_from_ui(self) -> tuple[float, float]:

        lo = float(self.fit_lmin_spin.value())

        hi = float(self.fit_lmax_spin.value())

        lo, hi = (min(lo, hi), max(lo, hi))

        if self.df is not None and not self.df.empty:
            wl = np.asarray(
                pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values,
                dtype=np.float64,
            )

            m = np.isfinite(wl)

            if int(np.count_nonzero(m)) >= 2:
                wmin = float(np.min(wl[m]))

                wmax = float(np.max(wl[m]))

                lo = max(lo, wmin)

                hi = min(hi, wmax)

        if hi < lo:
            lo, hi = hi, lo

        return lo, hi

    def _on_fit_range_changed(self):

        if self.df is None:
            return

        # Immediately redraws preview to update out-of-fit shading.

        self.preview_plot()

    def _on_fit_range_spin_changed(self, *_args) -> None:

        self._on_fit_range_changed()

    def _apply_full_auto_sellmeier_mode(self) -> None:
        """Full auto mode: hides/disables manual Sellmeier settings."""

        auto_on = bool(self.sell_auto_chk.isChecked()) if hasattr(self, "sell_auto_chk") else True

        controls = [
            getattr(self, "sell_timeout_lbl", None),
            getattr(self, "sell_timeout_spin", None),
            getattr(self, "sell_de_lbl", None),
            getattr(self, "sell_de_iter_spin", None),
            getattr(self, "sell_ls_lbl", None),
            getattr(self, "sell_ls_nfev_spin", None),
        ]

        for w in controls:
            if w is None:
                continue

            w.setVisible(not auto_on)

            w.setEnabled(not auto_on)

    def _on_sell_auto_state_changed(self, *_args) -> None:

        self._apply_full_auto_sellmeier_mode()

    def _setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = create_header_logo_widget(
            "CERTUS SUBSTRATE INDEX",
            "Index from spectral measurements",
            logo_width=200,
            module_name="CERTUS_SUBSTRATE_INDEX",
        )

        layout.addWidget(header)

        content = QWidget()

        c_layout = QVBoxLayout(content)

        c_layout.setContentsMargins(
            CertusTheme.SPACING_XL, CertusTheme.SPACING_XL, CertusTheme.SPACING_XL, CertusTheme.SPACING_XL
        )

        tools = QFrame()

        tools.setStyleSheet(
            f"background-color: {CertusTheme.SURFACE}; border-radius: {CertusTheme.RADIUS_LG}px; border: 1px solid {CertusTheme.BORDER};"
        )

        tools_layout = QVBoxLayout(tools)
        tools_layout.setContentsMargins(
            CertusTheme.SPACING_MD, CertusTheme.SPACING_MD, CertusTheme.SPACING_MD, CertusTheme.SPACING_MD
        )

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        tools_layout.addLayout(row1)
        tools_layout.addLayout(row2)

        self.btn_load = create_styled_button("Load Data (.xlsx/.xls)", variant="primary")
        self.btn_load.clicked.connect(self.load_file)
        self.btn_load.setToolTip("Load a measured transmission or reflection spectrum.")

        self.fit_lmin_spin = QDoubleSpinBox()
        self.fit_lmin_spin.setRange(100.0, 20000.0)
        self.fit_lmin_spin.setDecimals(1)
        self.fit_lmin_spin.setSingleStep(50.0)
        self.fit_lmin_spin.setValue(400.0)
        self.fit_lmin_spin.valueChanged.connect(self._on_fit_range_spin_changed)
        self.fit_lmin_spin.setToolTip(
            "Shortest wavelength used to fit the index, in nm (100 to 20000). "
            "Points outside the range are ignored by the fit."
        )

        self.fit_lmax_spin = QDoubleSpinBox()
        self.fit_lmax_spin.setRange(100.0, 20000.0)
        self.fit_lmax_spin.setDecimals(1)
        self.fit_lmax_spin.setSingleStep(50.0)
        self.fit_lmax_spin.setValue(5000.0)
        self.fit_lmax_spin.valueChanged.connect(self._on_fit_range_spin_changed)
        self.fit_lmax_spin.setToolTip(
            "Longest wavelength used to fit the index, in nm (100 to 20000). "
            "Points outside the range are ignored by the fit."
        )

        self.sell_auto_chk = QCheckBox("Sellmeier full auto")
        self.sell_auto_chk.setChecked(True)
        self.sell_auto_chk.setToolTip("Active: automatic internal Sellmeier parameters.")
        self.sell_auto_chk.stateChanged.connect(self._on_sell_auto_state_changed)

        self.sell_timeout_lbl = QLabel("Sellmeier budget (s):")
        self.sell_timeout_spin = QDoubleSpinBox()
        self.sell_timeout_spin.setRange(0.0, 120.0)
        self.sell_timeout_spin.setDecimals(1)
        self.sell_timeout_spin.setSingleStep(1.0)
        self.sell_timeout_spin.setValue(8.0)
        self.sell_timeout_spin.setToolTip("0 = unlimited. Time limit for Sellmeier global optimization.")

        self.sell_de_lbl = QLabel("Sellmeier DE iters:")
        self.sell_de_iter_spin = QSpinBox()
        self.sell_de_iter_spin.setRange(10, 2000)
        self.sell_de_iter_spin.setSingleStep(25)
        self.sell_de_iter_spin.setValue(300)
        self.sell_de_iter_spin.setToolTip("Max L-BFGS-B iterations (Sellmeier, global phase).")

        self.sell_ls_lbl = QLabel("Sellmeier LS nfev:")
        self.sell_ls_nfev_spin = QSpinBox()
        self.sell_ls_nfev_spin.setRange(100, 50000)
        self.sell_ls_nfev_spin.setSingleStep(100)
        self.sell_ls_nfev_spin.setValue(3000)
        self.sell_ls_nfev_spin.setToolTip("Max evaluations for least_squares (polish after L-BFGS-B, Sellmeier).")

        self.sell_log_l_chk = QCheckBox("Sellmeier L1,L2 en ln (optimization.)")
        self.sell_log_l_chk.setChecked(bool(SELLMEIER_DEFAULT_LOG_L1L2))
        self.sell_log_l_chk.setToolTip(
            "If checked: optimization on ui=ln(Li) then Li=exp(ui) (log bounds). Otherwise: Li directly."
        )

        self.btn_calc_n = create_styled_button("Calc Substrate Index (3 laws)", variant="secondary")
        self.btn_calc_n.clicked.connect(self.calculate_index)
        self.btn_calc_n.setToolTip(
            "Fit the substrate index over the wavelength range above, using the three "
            "dispersion laws, and report which one fits best."
        )
        self.btn_calc_n.setEnabled(False)

        self.btn_export_datasheet = create_styled_button("Export Datasheet (JSON)", variant="outline")
        self.btn_export_datasheet.setToolTip("Export substrate Sellmeier coefficients and metadata to JSON.")
        self.btn_export_datasheet.clicked.connect(self.export_substrate_datasheet)
        self.btn_export_datasheet.setEnabled(False)

        # Row 1 layout
        row1.addWidget(self.btn_load)
        row1.addSpacing(10)
        row1.addWidget(QLabel("λ min fit (nm):"))
        row1.addWidget(self.fit_lmin_spin)
        row1.addSpacing(10)
        row1.addWidget(QLabel("λ max fit (nm):"))
        row1.addWidget(self.fit_lmax_spin)
        row1.addSpacing(15)
        row1.addWidget(self.sell_auto_chk)
        row1.addStretch()
        row1.addWidget(self.btn_calc_n)

        # Row 2 layout
        row2.addWidget(self.sell_timeout_lbl)
        row2.addWidget(self.sell_timeout_spin)
        row2.addSpacing(10)
        row2.addWidget(self.sell_de_lbl)
        row2.addWidget(self.sell_de_iter_spin)
        row2.addSpacing(10)
        row2.addWidget(self.sell_ls_lbl)
        row2.addWidget(self.sell_ls_nfev_spin)
        row2.addSpacing(10)
        row2.addWidget(self.sell_log_l_chk)
        row2.addSpacing(15)
        row2.addWidget(self.btn_export_datasheet)
        row2.addStretch()

        c_layout.addWidget(tools)

        hint = QLabel(
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size: {Typography.BODY_LG}pt;'>"
            "Only spectral columns whose <b>name</b> indicates a <b>bare substrate</b> "
            "(e.g. <i>substrate nu</i>, <i>sbst nu</i>, <i>SNU</i>, <i>BSUB</i>, <i>bare sub</i>, "
            "<i>no-coat</i>, <i>sans_dep</i>, <i>nu</i> isolated...) are loaded; "
            "filter / stack / target / design (including abbreviations) are ignored."
            "</span>"
        )

        hint.setWordWrap(True)

        c_layout.addWidget(hint)

        self.main_tabs = QTabWidget()

        self.plot_widget = CertusScientificPlot(title="Spectra")
        self.plot_widget.addLegend(offset=(10, 10))
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Wavelength (nm)")
        self.plot_widget.setLabel("left", "Amplitude")
        attach_excel_clipboard_context_menu(self.plot_widget)

        spectra_tab = QWidget()
        spectra_layout = QVBoxLayout(spectra_tab)
        spectra_layout.setContentsMargins(0, 0, 0, 0)
        spectra_layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_widget))
        self.main_tabs.addTab(spectra_tab, "Input spectra")

        self.output_plot = CertusScientificPlot(title="Substrate output")
        self.output_plot.addLegend(offset=(10, 10))
        try:
            self.output_plot.legend.setBrush(QBrush(QColor(CertusTheme.SURFACE)))
            self.output_plot.legend.setLabelTextColor(QColor(CertusTheme.TEXT_MAIN))
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        self.output_plot.showGrid(x=True, y=True, alpha=0.25)
        self.output_plot.setLabel("bottom", "Wavelength (nm)")
        self.output_plot.setLabel("left", "Index n")
        self.output_plot.setTitle("Substrate index output (raw vs fitted) — quality-aware")
        attach_excel_clipboard_context_menu(self.output_plot)

        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.output_plot))
        self.main_tabs.addTab(output_tab, "Output")

        self.output_tables = QWidget()
        self.output_tables_layout = QVBoxLayout(self.output_tables)
        self.output_tables_layout.setContentsMargins(0, 0, 0, 0)
        self.output_model_selector = QComboBox()
        self.output_model_selector.setToolTip("Select a single fitted law to highlight in the table.")
        self.output_model_selector.currentIndexChanged.connect(self._refresh_output_tables)
        self.output_tables_layout.addWidget(self.output_model_selector)

        self.output_table_hint = QLabel("Tip: use the model selector to focus on one law, or keep All models to compare the full stack.")
        self.output_table_hint.setWordWrap(True)
        self.output_table_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: {Typography.BODY_LG}pt;")
        self.output_tables_layout.addWidget(self.output_table_hint)
        self.output_tables_area = QWidget()
        self.output_tables_area_layout = QVBoxLayout(self.output_tables_area)
        self.output_tables_area_layout.setContentsMargins(0, 0, 0, 0)
        self.output_tables_layout.addWidget(self.output_tables_area)
        self.main_tabs.addTab(self.output_tables, "Output tables")

        c_layout.addWidget(self.main_tabs)

        self.log_panel = CertusLogPanel(title="LOGS", visible=True, height=170)

        c_layout.addWidget(self.log_panel)

        layout.addWidget(content)

        # `click()`: the export button is greyed out until a run has produced something to export.
        install_standard_shortcuts(
            self,
            save=self.btn_export_datasheet.click,
            load=self.btn_load.click,
            help=lambda: open_documentation("CERTUS_SUBSTRATE_INDEX"),
        )

        self.progress_widget = EnhancedProgressWidget()

        if hasattr(self.progress_widget, "canceled"):
            self.progress_widget.canceled.connect(lambda: self.log("Cancellation requested by user...", "WARNING"))

        self.statusBar().addPermanentWidget(self.progress_widget)

        self._apply_full_auto_sellmeier_mode()

        install_accessible_names(self)  # the two wavelength spin boxes have a tooltip and no label

    def _is_cancel_requested(self) -> bool:

        return bool(
            hasattr(self, "progress_widget")
            and hasattr(self.progress_widget, "is_canceled")
            and self.progress_widget.is_canceled()
        )

    def load_file(self):

        self.progress_widget.start()

        self.progress_widget.set_time_budget(8.0)

        self.progress_widget.update(1, 1, phase="Load workbook")

        self.log("Loading measurement workbook...", "INFO")

        try:
            result = open_measurement_excel_interactive(
                self,
                start_dir=self.last_dir or "",
                caption="Open Data",
                round_wavelength_decimals=None,
            )

            if result is None:
                self.progress_widget.stop("Cancelled")

                return

            raw_df, path, self.last_dir = result
            self._last_loaded_measurement_path = str(path or "")

            self.settings.setValue("last_dir", self.last_dir)

            self.df, kept_spec, dropped_spec = _filter_dataframe_bare_substrate_columns(raw_df)

            if dropped_spec:
                logger.info(
                    "Substrate index: ignored columns (no bare substrate indicator in the name): %s",
                    "; ".join(dropped_spec[:40]) + ("; ..." if len(dropped_spec) > 40 else ""),
                )

            if not kept_spec:
                self.df = None

                self.btn_calc_n.setEnabled(False)

                QMessageBox.warning(
                    self,
                    "Bare substrate: no columns retained",
                    "No spectral column name indicates a **bare substrate** "
                    "(e.g. substrate nu, sbst nu, SNU, BSUB, bare sub, nocoat, sans_dep, "
                    "nu sub, empty sub, isolated word 'nu', etc.).\n\n"
                    "Filter or stack measurements are intentionally ignored.\n\n"
                    f"Columns present but excluded ({len(dropped_spec)}): "
                    + (", ".join(dropped_spec[:12]) + ("..." if len(dropped_spec) > 12 else "")),
                )

                self.progress_widget.stop("Error: No bare-substrate columns")

                return

            self.btn_calc_n.setEnabled(True)

            # Measurement sheet imposes absolute lambda bounds; UI window stays inside these limits.

            wl_all = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

            m_w = np.isfinite(wl_all)

            if int(np.count_nonzero(m_w)) >= 2:
                wmin = float(np.min(wl_all[m_w]))

                wmax = float(np.max(wl_all[m_w]))

                self.fit_lmin_spin.setRange(wmin, wmax)

                self.fit_lmax_spin.setRange(wmin, wmax)

                self.fit_lmin_spin.setValue(wmin)

                self.fit_lmax_spin.setValue(wmax)

            self.log(
                f"Substrate index: {Path(path).name}  "
                f"{len(kept_spec)} bare substrate column(s), {len(dropped_spec)} ignored.",
                "INFO",
            )

            logger.info(
                "Substrate index: loading %s  %d bare substrate column(s), %d ignored.",
                Path(path).name,
                len(kept_spec),
                len(dropped_spec),
            )

            self.progress_widget.update(1, 1, phase="Preview")

            self.preview_plot()

            self.progress_widget.stop("Done")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logger.error("Failed to load measurement sheet: %s", e)

            QMessageBox.critical(self, "Error", f"Failed to load measurement sheet:\n{e}")

            self.log(f"Load error: {e}", "ERROR")

            self.progress_widget.stop("Error: Load failed")

    def _output_table_titles(self, selected_model: str | None = None) -> list[str]:
        titles = ["lambda (nm)"]
        models_by_bk = getattr(self, "_models_order_by_bk", {})
        if getattr(self, "n_results_raw", None):
            for bk in self.n_results_raw.keys():
                titles.append(f"{bk} (Raw)")
                if selected_model:
                    titles.append(f"{bk} ({selected_model})")
                else:
                    for _mk, mlabel in models_by_bk.get(bk, []):
                        titles.append(f"{bk} ({mlabel})")
        return titles

    def _refresh_output_tables(self, *_args) -> None:
        if not hasattr(self, "output_tables_area"):
            return
        while self.output_tables_area_layout.count():
            item = self.output_tables_area_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not hasattr(self, "n_results_raw") or not self.n_results_raw:
            empty = QLabel("No output available yet. Run the substrate fit to populate this view.")
            empty.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; padding: 12px;")
            self.output_tables_area_layout.addWidget(empty)
            return

        selected = self.output_model_selector.currentText().strip() if hasattr(self, "output_model_selector") else ""
        if not selected:
            selected = ""

        table = QTableWidget()
        self.output_table_widget = table
        wl = np.asarray(self.output_table_wl if hasattr(self, "output_table_wl") else [], dtype=np.float64)
        table.setRowCount(len(wl))
        models_known = {ml for _, ml in SUBSTRATE_INDEX_MODELS}
        col_names = self._output_table_titles(selected if selected in models_known else None)
        table.setColumnCount(len(col_names))
        table.setHorizontalHeaderLabels(col_names)
        models_by_bk = getattr(self, "_models_order_by_bk", {})
        for i in range(len(wl)):
            table.setItem(i, 0, QTableWidgetItem(f"{wl[i]:.1f}"))
            c = 1
            for bk in self.n_results_raw.keys():
                table.setItem(i, c, QTableWidgetItem(f"{self.n_results_raw[bk][i]:.4f}"))
                c += 1
                if selected and selected in self.n_results_by_model.get(bk, {}):
                    arr = self.n_results_by_model[bk][selected]
                    table.setItem(i, c, QTableWidgetItem(f"{arr[i]:.4f}"))
                    c += 1
                else:
                    for _mk, mlabel in models_by_bk.get(bk, []):
                        arr = self.n_results_by_model.get(bk, {}).get(mlabel)
                        table.setItem(i, c, QTableWidgetItem(f"{arr[i]:.4f}" if arr is not None else ""))
                        c += 1
        self.output_tables_area_layout.addWidget(table)

    def _plot_output_results(
        self,
        wl: np.ndarray,
        n_results_raw: dict[str, np.ndarray],
        n_results_by_model: dict[str, dict[str, np.ndarray]],
        rmse_row: dict[str, dict[str, float]],
        fit_wl_lo: float,
        fit_wl_hi: float,
    ) -> None:
        """Render the dedicated output tab for raw and fitted index curves."""

        if not hasattr(self, "output_plot"):
            return

        self.output_plot.clear()
        wl = np.asarray(wl, dtype=np.float64)
        if wl.size == 0:
            return
        m_wl = np.isfinite(wl)
        if int(np.count_nonzero(m_wl)) < 2:
            return
        wl = wl[m_wl]
        self.output_plot.setTitle("Substrate index output (raw vs fitted) — quality-aware")

        self.output_table_wl = wl
        self.n_results_raw = n_results_raw
        self.n_results_by_model = n_results_by_model
        self.rmse_row = rmse_row
        self._models_order_by_bk = {
            bk: _substrate_index_models_ordered_by_rmse(rmse_row.get(bk, {})) for bk in n_results_raw.keys()
        }

        if hasattr(self, "output_model_selector"):
            self.output_model_selector.blockSignals(True)
            self.output_model_selector.clear()
            self.output_model_selector.addItem("All models")
            for _mk, mlabel in SUBSTRATE_INDEX_MODELS:
                self.output_model_selector.addItem(mlabel)
            self.output_model_selector.blockSignals(False)

        fit_mask = _substrate_index_geom_fit_mask(wl, fit_wl_lo, fit_wl_hi)
        colors = [CertusTheme.BRAND_DESIGN, CertusTheme.BRAND_INDEX, CertusTheme.SUCCESS, CertusTheme.WARNING]
        valid_points_total = 0

        for i, key in enumerate(n_results_raw.keys()):
            raw_arr = np.asarray(n_results_raw[key], dtype=np.float64)
            valid_points_total += int(np.count_nonzero(np.isfinite(raw_arr) & np.isfinite(wl)))
            c = pg.mkColor(colors[i % len(colors)])
            c_raw = pg.mkColor(c)
            c_raw.setAlpha(130)
            _pg_plot_xy_split_band(
                self.output_plot,
                wl,
                n_results_raw[key],
                fit_mask,
                pg.mkPen(color=c_raw, width=1.8),
                pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.2),
                name=f"{key} (Raw n)",
            )
            bym = n_results_by_model.get(key, {})
            for pi, (_mk, mlabel) in enumerate(SUBSTRATE_INDEX_MODELS):
                arr = bym.get(mlabel)
                if arr is None:
                    continue
                _pg_plot_xy_split_band(
                    self.output_plot,
                    wl,
                    arr,
                    fit_mask,
                    pg.mkPen(color=pg.mkColor(c), width=2.0, style=[Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine][pi % 3]),
                    pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.2),
                    name=f"{key} ({mlabel})",
                )

        self.output_plot.getViewBox().enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
        self.output_plot.autoRange()
        if valid_points_total == 0:
            self.output_plot.setTitle("Substrate index output — no valid points to plot")
        self._refresh_output_tables()

    def preview_plot(self):

        if self.df is None:
            return

        self.plot_widget.clear()

        x = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

        m_x = np.isfinite(x)

        if int(np.count_nonzero(m_x)) < 5:
            logger.warning("Substrate index preview: wavelength column has insufficient finite points.")

            return

        x = x[m_x]

        wmin, wmax = float(np.min(x)), float(np.max(x))

        lo_f, hi_f = self._get_fit_range_from_ui()

        if wmax > wmin:
            _add_pg_fit_band_outside_shading(self.plot_widget, lo_f, hi_f, wmin, wmax)

        fit_mask = _substrate_index_geom_fit_mask(x, lo_f, hi_f)

        y_raw = np.asarray(self.df.loc[m_x, self.df.columns[1:]].values, dtype=np.float64).T
        x, y_raw = _align_xy_lengths(x, y_raw, label="preview")

        y_clean = IndexCore.apply_dynamic_filtering(
            x, y_raw, self.current_window, self.current_poly, self.current_heavy
        )

        y_clean_arr = np.asarray(y_clean, dtype=np.float64)
        if y_clean_arr.ndim == 1:
            y_clean_arr = y_clean_arr.reshape(1, -1)

        for i, col in enumerate(self.df.columns[1:]):
            if i >= y_clean_arr.shape[0]:
                continue
            color = [CertusTheme.BRAND_DESIGN, CertusTheme.BRAND_INDEX, CertusTheme.SUCCESS, CertusTheme.WARNING][i % 4]
            y_series = np.asarray(y_clean_arr[i], dtype=np.float64)
            m_series = np.isfinite(x) & np.isfinite(y_series)
            if int(np.count_nonzero(m_series)) < 2:
                continue

            fit_mask_series = fit_mask[m_series] if fit_mask.size == m_series.size else fit_mask

            _pg_plot_xy_split_band(
                self.plot_widget,
                x[m_series],
                y_series[m_series],
                fit_mask_series,
                pg.mkPen(color=color, width=2),
                pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.6),
                name=str(col),
            )

        self.plot_widget.getViewBox().enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.plot_widget.autoRange()

    def _get_clean_fraction_column(self, x: np.ndarray, col_name) -> np.ndarray:

        y_raw = np.asarray(pd.to_numeric(self.df[col_name], errors="coerce").values, dtype=np.float64)
        x, y_raw = _align_xy_lengths(x, y_raw, label=str(col_name))

        m = np.isfinite(x) & np.isfinite(y_raw)

        if int(np.count_nonzero(m)) < 5:
            raise ValueError(f"Not enough finite points in column: {col_name}")

        if not np.all(m):
            y_raw = np.interp(x, x[m], y_raw[m])

        y_clean = IndexCore.apply_dynamic_filtering(
            x, y_raw, self.current_window, self.current_poly, self.current_heavy
        )

        y_clean = np.asarray(y_clean, dtype=np.float64)
        if y_clean.ndim > 1:
            y_clean = np.squeeze(y_clean)
        y_clean = np.asarray(y_clean, dtype=np.float64).reshape(-1)

        return IndexCore.to_fraction(y_clean)


    def calculate_index(self):
        if self.df is None:
            return

        self.progress_widget.start()
        if hasattr(self.progress_widget, "enable_cancel"):
            self.progress_widget.enable_cancel(True)
        self.progress_widget.set_time_budget(25.0)

        sellmeier_settings = {
            "auto": bool(self.sell_auto_chk.isChecked()),
            "timeout": float(self.sell_timeout_spin.value()),
            "de_iter": int(self.sell_de_iter_spin.value()),
            "ls_nfev": int(self.sell_ls_nfev_spin.value()),
            "log_l1l2": bool(self.sell_log_l_chk.isChecked()) if hasattr(self, "sell_log_l_chk") else False,
        }

        fit_range = self._get_fit_range_from_ui()

        # Delegate the actual calculation and state management to Presenter
        self.presenter.calculate_index(self.df, fit_range, sellmeier_settings)
        
        # After calculation, sync the mutated dataframe back if any
        if self.presenter.df is not None:
            self.df = self.presenter.df

        if hasattr(self.progress_widget, "enable_cancel"):
            self.progress_widget.enable_cancel(False)
        self._set_busy(False)


def main():

    app = init_certus_app("CERTUS_SUBSTRATE_INDEX")

    window = SubstrateIndexGUI()

    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
