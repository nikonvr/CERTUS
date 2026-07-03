#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS Substrate Index - Substrate refractive index determination only


"""


import functools
from pathlib import Path
from typing import Any
import re
import sys


import logging


import numpy as np


import pandas as pd


import pyqtgraph as pg


from PyQt6.QtCore import Qt, QSettings


from PyQt6.QtGui import QFont, QColor, QBrush


from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QFrame,
    QMessageBox,
    QCheckBox,
    QDialog,
    QTableWidgetItem,
    QHeaderView,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QTabWidget,
    QComboBox,
    QTableWidget,
    QAbstractItemView,
)


from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    setup_module_logging,
    __version__,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATES,
    CANONICAL_SUBSTRATE_LABELS,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
)
from certus.core.certus_substrate_helpers import filter_bare_substrate_columns, is_bare_substrate_column, norm_header, expand_substrate_abbrevs, unglue_substrate_nu
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import SubstrateIndexRequest, SubstrateIndexService


from certus.ui.certus_measurement_excel_ui import open_measurement_excel_interactive


from certus.utils.certus_spectral_preproc import dynamic_savgol_blend


from certus.ui.certus_ui import (
    CertusTheme,
    CertusLogPanel,
    EnhancedProgressWidget,
    attach_excel_clipboard_context_menu,
    CertusScientificPlot,
    wrap_scientific_plot_with_toolbar,
    init_certus_app,
    create_styled_button,
    create_styled_label,
    set_certus_window_icon,
    create_header_logo_widget,
    ExcelTableWidget,
)



from certus.core.certus_substrate_index import (
    IndexCore,
    SELLMEIER_DEFAULT_LOG_L1L2,
    SUBSTRATE_INDEX_MODELS,
    _MODEL_LABEL_TO_INDEX,
    logger,
)

from certus.ui.certus_substrate_plot_utils import (
    _add_pg_fit_band_outside_shading,
    _nan_split_band_y,
    _pg_plot_xy_split_band,
    _pg_plot_scatter_split_band,
)
from certus.core.certus_substrate_index import _fit_summary_line
from certus.core.certus_substrate_index import (
    _N_SUBSTRATE_MODELS,
    _filter_dataframe_bare_substrate_columns,
    _bad_model_labels,
    _best_finite_rmse_from_triplet,
    _rms_triplet,
    _rmse_is_bad_vs_best,
    _rmse_is_best_fit,
    _substrate_index_geom_fit_mask,
    _substrate_index_models_ordered_by_rmse,
    _model_selection_score,
    _rank_models_by_selection_score,
    _align_xy_lengths,
)

class IndexTableDialog(QDialog):
    def __init__(
        self,
        wl,
        n_results_raw,
        n_results_by_model: dict[str, dict[str, np.ndarray]],
        rmse_row: dict[str, dict[str, float]],
        *,
        fit_meta_by_key: dict[str, dict[str, dict]] | None = None,
        fit_wl_lo: float | None = None,
        fit_wl_hi: float | None = None,
        spectral_wl_lo: float | None = None,
        spectral_wl_hi: float | None = None,
    ):

        super().__init__()

        self.setWindowTitle("Substrate Refractive Index (n)")

        self.resize(1100, 820)

        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};")

        layout = QVBoxLayout(self)

        layout.addWidget(
            create_styled_label(
                "Refractive index: 3 laws compared (best RMSE first; columns sorted by increasing RMSE inside each series)",
                style="subtitle",
            )
        )

        fit_span_txt = ""
        if fit_wl_lo is not None and fit_wl_hi is not None:
            _lo_d = float(min(fit_wl_lo, fit_wl_hi))
            _hi_d = float(max(fit_wl_lo, fit_wl_hi))
            fit_span_txt = f"Fit window: [{_lo_d:.1f}, {_hi_d:.1f}] nm"

        self.chk_only_cauchy = QCheckBox("Hide raw points")
        self.chk_only_cauchy.setToolTip("Toggle visibility of the raw measured points while keeping fitted curves.")

        self.chk_only_cauchy.setChecked(False)

        self.chk_only_cauchy.stateChanged.connect(self.toggle_raw_plots)

        layout.addWidget(self.chk_only_cauchy)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            f"background-color: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; "
            f"border-radius: 8px; padding: 10px; color: {CertusTheme.TEXT_MAIN};"
        )

        self.raw_items = []
        self._series_quality: dict[str, dict[str, float | str]] = {}
        self._series_order = list(n_results_raw.keys())
        self._last_table_summary = []
        self._series_summary_text = []

        summary_parts = ["Table summary: 3 candidate laws per substrate series."]
        if fit_span_txt:
            summary_parts.append(fit_span_txt)
        summary_parts.append("Best RMSE is highlighted in green; weaker fits are muted.")
        self.summary_label.setText(" ".join(summary_parts))
        layout.addWidget(self.summary_label)
        self.summary_label.setAccessibleName("Substrate index summary")
        self.summary_label.setToolTip("Executive summary of the fit quality and window of validity.")

        bad_model: dict[str, set[str]] = {bk: _bad_model_labels(rmse_row.get(bk, {})) for bk in n_results_raw.keys()}

        summary_rows: list[str] = []
        for bk in self._series_order:
            rms = rmse_row.get(bk, {})
            best_v = _best_finite_rmse_from_triplet(_rms_triplet(rms))
            q_label = "good"
            if np.isfinite(best_v):
                if best_v > 0.02:
                    q_label = "degraded"
                if best_v > 0.05:
                    q_label = "poor"
            self._series_quality[bk] = {"best_rmse": float(best_v), "quality_label": q_label}
            summary_rows.append(f"{bk}: best RMSE={best_v:.6g} | quality={q_label}")

        if summary_rows:
            self._series_summary_text = summary_rows
            detail = QLabel(" | ".join(summary_rows))
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")
            layout.addWidget(detail)
            self.summary_label.setText(self.summary_label.text() + f" | Series status: {len([s for s in self._series_quality.values() if s.get('quality_label') == 'good'])} good, {len([s for s in self._series_quality.values() if s.get('quality_label') == 'degraded'])} degraded, {len([s for s in self._series_quality.values() if s.get('quality_label') == 'poor'])} poor")
            self.summary_label.setToolTip("Executive summary of fit quality across substrate series.")

        self.plot = CertusScientificPlot(title="Refractive index vs Wavelength")

        self.plot.setMinimumHeight(400)

        self.plot.addLegend(offset=(10, 10))
        try:
            self.plot.legend.setBrush(QBrush(QColor(CertusTheme.SURFACE)))
            self.plot.legend.setLabelTextColor(QColor(CertusTheme.TEXT_MAIN))
        except Exception:
            pass

        self.plot.showGrid(x=True, y=True, alpha=0.3)

        self.plot.setLabel("bottom", "Wavelength (nm)")

        self.plot.setLabel("left", "Index n")

        self.plot.setTitle("Substrate refractive index curves — best fit highlighted")

        wl_plot = np.asarray(wl, dtype=np.float64)

        fit_mask_plot = None

        if fit_wl_lo is not None and fit_wl_hi is not None:
            fit_mask_plot = _substrate_index_geom_fit_mask(wl_plot, float(fit_wl_lo), float(fit_wl_hi))

        colors = [CertusTheme.BRAND_DESIGN, CertusTheme.WARNING, "#9b59b6", "#34495e"]

        _fit_pen_styles = [
            (2.4, Qt.PenStyle.SolidLine),
            (2.0, Qt.PenStyle.DashLine),
            (2.0, Qt.PenStyle.DotLine),
        ]

        summary_rows: list[str] = []

        for i, key in enumerate(n_results_raw.keys()):
            y_raw = n_results_raw[key]

            c = pg.mkColor(colors[i % len(colors)])

            c_raw = pg.mkColor(c)

            c_raw.setAlpha(150)

            raw_item = _pg_plot_scatter_split_band(
                self.plot,
                wl,
                y_raw,
                fit_mask_plot,
                pg.mkPen(color=c_raw, width=1.5),
                pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.2),
                name=f"{key} (Raw)",
            )

            self.raw_items.append(raw_item)

            bym = n_results_by_model.get(key, {})
            rms = rmse_row.get(key, {})
            best_v = _best_finite_rmse_from_triplet(_rms_triplet(rms))
            q_label = "good"
            if np.isfinite(best_v):
                if best_v > 0.02:
                    q_label = "degraded"
                if best_v > 0.05:
                    q_label = "poor"
            self._series_quality[key] = {"best_rmse": float(best_v), "quality_label": q_label}
            summary_rows.append(f"{key}: best RMSE={best_v:.6g} | quality={q_label}")

            for pi, (_mk, mlabel) in enumerate(SUBSTRATE_INDEX_MODELS):
                arr = bym.get(mlabel)

                if arr is None:
                    continue

                if mlabel in bad_model.get(key, set()):
                    pc = pg.mkColor(CertusTheme.TEXT_SUB)

                    pc.setAlpha(160)

                else:
                    pc = pg.mkColor(c)

                    pc.setAlpha(220)

                if pi == 0:
                    pc.setAlpha(245)
                    if q_label == "good":
                        pc = pg.mkColor(CertusTheme.SUCCESS)
                        pc.setAlpha(230)
                    elif q_label == "degraded":
                        pc = pg.mkColor(CertusTheme.WARNING)
                        pc.setAlpha(230)
                    elif q_label == "poor":
                        pc = pg.mkColor(CertusTheme.ERROR)
                        pc.setAlpha(220)

                pw, pst = _fit_pen_styles[pi % 3]

                _pg_plot_xy_split_band(
                    self.plot,
                    wl,
                    arr,
                    fit_mask_plot,
                    pg.mkPen(color=pc, width=pw, style=pst),
                    pg.mkPen(
                        color=CertusTheme.TEXT_SUB,
                        width=max(1.2, pw - 0.5),
                        style=pst,
                    ),
                    name=f"{key} ({mlabel})",
                )

        if fit_wl_lo is not None and fit_wl_hi is not None and wl_plot.size:
            _wmn = float(np.nanmin(wl_plot))

            _wmx = float(np.nanmax(wl_plot))

            if np.isfinite(_wmn) and np.isfinite(_wmx) and _wmx > _wmn:
                _add_pg_fit_band_outside_shading(self.plot, float(fit_wl_lo), float(fit_wl_hi), _wmn, _wmx)

        vb = self.plot.getViewBox()

        vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.plot.autoRange()

        attach_excel_clipboard_context_menu(self.plot)

        layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot))

        self.wl = wl

        self.n_results_by_model = n_results_by_model

        self.n_results_raw = n_results_raw

        self.rmse_row = rmse_row

        self.fit_meta_by_key = fit_meta_by_key if fit_meta_by_key is not None else {}

        self.fit_wl_lo = fit_wl_lo

        self.fit_wl_hi = fit_wl_hi

        self.spectral_wl_lo = spectral_wl_lo

        self.spectral_wl_hi = spectral_wl_hi

        self._models_order_by_bk: dict[str, list[tuple[str, str]]] = {
            bk: _substrate_index_models_ordered_by_rmse(rmse_row.get(bk, {})) for bk in n_results_raw.keys()
        }

        col_names = ["lambda (nm)"]

        for bk in self.n_results_raw.keys():
            col_names.append(f"{bk} (Raw)")

            for _mk, mlabel in self._models_order_by_bk[bk]:
                col_names.append(f"{bk} ({mlabel})")

        bad_column = [False] * len(col_names)

        _ci = 1

        for _bk in self.n_results_raw.keys():
            bad_column[_ci] = False

            _ci += 1

            rms_b = self.rmse_row.get(_bk, {})

            _mv = _rms_triplet(rms_b)

            _best = _best_finite_rmse_from_triplet(_mv)

            for _mk, mlabel in self._models_order_by_bk[_bk]:
                _j = _MODEL_LABEL_TO_INDEX[mlabel]

                bad_column[_ci] = _rmse_is_bad_vs_best(_mv[_j], _best)

                _ci += 1

        table = ExcelTableWidget()

        n_data_rows = len(wl)

        table.setRowCount(1 + n_data_rows)

        table.setColumnCount(len(col_names))

        table.setHorizontalHeaderLabels(col_names)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)

        _hh = table.horizontalHeader()

        for _c in range(len(col_names)):
            _hh.setSectionResizeMode(_c, QHeaderView.ResizeMode.Interactive)

        _hh.setMinimumSectionSize(72)

        _hh.setStretchLastSection(False)

        self.table = table

        rmse_font = QFont()

        rmse_font.setBold(True)

        rmse_font.setPointSize(max(rmse_font.pointSize(), 11))

        _col_base_raw: dict[str, int] = {}

        _ix_hdr = 1

        for _bk in self.n_results_raw.keys():
            _col_base_raw[_bk] = _ix_hdr

            _ix_hdr += 1 + _N_SUBSTRATE_MODELS

        it0 = QTableWidgetItem("RMSE (fit window)")

        it0.setFont(rmse_font)

        it0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        it0.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

        table.setItem(0, 0, it0)

        for bk in self.n_results_raw.keys():
            base = _col_base_raw[bk]

            rms = self.rmse_row.get(bk, {})

            model_vals = _rms_triplet(rms)

            best_v = _best_finite_rmse_from_triplet(model_vals)

            ir = QTableWidgetItem("")

            ir.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            ir.setFont(rmse_font)

            ir.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

            table.setItem(0, base, ir)

            for j, (_mk, mlabel) in enumerate(self._models_order_by_bk[bk]):
                v = float(rms.get(mlabel, float("nan")))

                txt = f"{v:.6f}" if np.isfinite(v) else ""

                cell = QTableWidgetItem(txt)

                cell.setFont(rmse_font)

                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                cell.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

                if _rmse_is_best_fit(v, best_v):
                    cell.setForeground(QBrush(QColor(CertusTheme.SUCCESS)))

                elif _rmse_is_bad_vs_best(v, best_v):
                    cell.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                else:
                    cell.setForeground(QBrush(QColor(CertusTheme.TEXT_MAIN)))

                table.setItem(0, base + 1 + j, cell)

        wl_arr = np.asarray(wl, dtype=np.float64)

        row_outside_fit_brush = QBrush(QColor(CertusTheme.BORDER))

        if self.fit_wl_lo is not None and self.fit_wl_hi is not None:
            m_band_geom = _substrate_index_geom_fit_mask(wl_arr, float(self.fit_wl_lo), float(self.fit_wl_hi))

            finite_n_any = np.zeros(len(wl_arr), dtype=bool)

            for arr in self.n_results_raw.values():
                finite_n_any |= np.isfinite(np.asarray(arr, dtype=np.float64))

            bold_wl_row = m_band_geom & np.isfinite(wl_arr) & finite_n_any

            outside_fit_row = (~m_band_geom) & np.isfinite(wl_arr) & finite_n_any

        else:
            bold_wl_row = np.zeros(len(wl), dtype=bool)

            outside_fit_row = np.zeros(len(wl), dtype=bool)

        for i in range(n_data_rows):
            r = 1 + i

            row_vals = [f"{wl[i]:.1f}"]

            for bk in self.n_results_raw.keys():
                row_vals.append(f"{self.n_results_raw[bk][i]:.4f}")

                bym = self.n_results_by_model.get(bk, {})

                for _mk, mlabel in self._models_order_by_bk[bk]:
                    arr = bym.get(mlabel)

                    row_vals.append(f"{arr[i]:.4f}" if arr is not None else "")

            for j, txt in enumerate(row_vals):
                it = QTableWidgetItem(txt)

                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if bool(outside_fit_row[i]):
                    it.setBackground(row_outside_fit_brush)

                    it.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                elif j > 0 and j < len(bad_column) and bad_column[j]:
                    it.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                if j == 0 and bool(bold_wl_row[i]):
                    fnt = QFont(it.font())

                    fnt.setBold(True)

                    it.setFont(fnt)

                if j > 0 and j < len(bad_column) and not bool(bad_column[j]) and not bool(outside_fit_row[i]):
                    it.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

                table.setItem(r, j, it)

        layout.addWidget(table)

        btn_row = QHBoxLayout()

        btn_params = create_styled_button("Law parameters (Poly., Sellmeier, Spline)", variant="secondary")

        btn_params.clicked.connect(self.show_model_params_dialog)

        btn_copy = create_styled_button(" Copy to Clipboard", variant="primary")

        btn_copy.clicked.connect(functools.partial(self.copy_to_clipboard, col_names))

        btn_export = create_styled_button("Export summary", variant="outline")
        btn_export.setToolTip("Copy a concise summary of the current fit status to the clipboard.")
        btn_export.clicked.connect(self.copy_summary_to_clipboard)

        btn_row.addWidget(btn_params)
        btn_row.addWidget(btn_export)

        btn_row.addStretch()

        btn_row.addWidget(btn_copy)

        layout.addLayout(btn_row)

        self._last_table_summary = summary_parts
        self._last_quality_summary = " | ".join(summary_rows)

    def toggle_raw_plots(self, state):

        visible = state == Qt.CheckState.Unchecked.value

        for item in self.raw_items:
            item.setVisible(visible)

    def copy_summary_to_clipboard(self):
        lines = [
            "CERTUS Substrate Index summary",
            self.summary_label.text() if hasattr(self, "summary_label") else "",
            "",
        ]
        if hasattr(self, "_last_table_summary") and self._last_table_summary:
            lines.extend(self._last_table_summary)
        if hasattr(self, "fit_wl_lo") and self.fit_wl_lo is not None and self.fit_wl_hi is not None:
            lines.append(f"Fit window: [{float(self.fit_wl_lo):.1f}, {float(self.fit_wl_hi):.1f}] nm")
        QApplication.clipboard().setText("\n".join([x for x in lines if x]).strip() + "\n")
        QMessageBox.information(self, "Copied", "Summary copied to clipboard.")

    def copy_to_clipboard(self, col_names):

        header_lines: list[str] = [
            "CERTUS Substrate Index: 3 laws comparison (Polynomial, Sellmeier 3-poles, Spline n B-spline LSQ).",
            "RMSE (unweighted) calculated on fit window, vs raw n.",
        ]

        if hasattr(self, "summary_label") and self.summary_label.text():
            header_lines.append(self.summary_label.text())
            header_lines.append(f"Quality: {getattr(self, '_last_quality_summary', 'n/a')}")

        if self.fit_wl_lo is not None and self.fit_wl_hi is not None:
            header_lines.append(
                f"Fit zone (data): \u03bb = [{float(self.fit_wl_lo):.1f}, {float(self.fit_wl_hi):.1f}] nm"
            )

        if self.spectral_wl_lo is not None and self.spectral_wl_hi is not None:
            header_lines.append(
                f"n(\u03bb) evaluated on full measured band: \u03bb = [{float(self.spectral_wl_lo):.1f}, {float(self.spectral_wl_hi):.1f}] nm"
            )

        header_lines.append("")

        for bk in self.n_results_raw.keys():
            header_lines.append(f"=== {bk} ===")

            rms = self.rmse_row.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                v = rms.get(mlabel, float("nan"))

                header_lines.append(f"RMSE {mlabel}: {v:.6g}" if np.isfinite(v) else f"RMSE {mlabel}: ")

            meta_block = self.fit_meta_by_key.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                meta = meta_block.get(mlabel, {})

                src = str(meta.get("source", "unknown"))

                header_lines.append(f"--- {mlabel} ---")

                header_lines.append(IndexCore._clipboard_law_line_from_source(src, _mk))

                header_lines.append(IndexCore._clipboard_coeffs_line_from_source(src, meta.get("coeffs"), meta=meta))

                header_lines.append(f"internal source: {src}")

            header_lines.append("")

        header_lines.append("=== Table (TSV) ===")

        text = "\n".join(header_lines) + "\n"

        text += "\t".join(col_names) + "\n"

        row0 = [col_names[0]]

        for bk in self.n_results_raw.keys():
            row0.append("")

            rms = self.rmse_row.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                v = rms.get(mlabel, float("nan"))

                row0.append(f"{v:.6f}" if np.isfinite(v) else "")

        text += "\t".join(row0) + "\n"

        for i in range(len(self.wl)):
            row = [f"{self.wl[i]:.1f}"]

            for bk in self.n_results_raw.keys():
                row.append(f"{self.n_results_raw[bk][i]:.4f}")

                bym = self.n_results_by_model.get(bk, {})

                for _mk, mlabel in self._models_order_by_bk[bk]:
                    arr = bym.get(mlabel)

                    row.append(f"{arr[i]:.4f}" if arr is not None else "")

            text += "\t".join(row) + "\n"

        QApplication.clipboard().setText(text)

        QMessageBox.information(self, "Copied", "Table + RMSE + laws/coefficients copied to clipboard.")

    def show_model_params_dialog(self):

        lines: list[str] = [
            "CERTUS Substrate Index: analytical law parameters",
            "",
        ]

        def _bk_best_rmse_sort_key(bk: str) -> tuple:

            best = _best_finite_rmse_from_triplet(_rms_triplet(self.rmse_row.get(bk, {})))

            if not np.isfinite(best):
                return (1, float("inf"), str(bk))

            return (0, best, str(bk))

        bks_dialog_order = sorted(self.n_results_raw.keys(), key=_bk_best_rmse_sort_key)

        for bk in bks_dialog_order:
            lines.append(f"=== {bk} ===")

            meta_block = self.fit_meta_by_key.get(bk, {})

            rms_b = self.rmse_row.get(bk, {})

            for rank, (_mk, mlabel) in enumerate(self._models_order_by_bk[bk]):
                meta = meta_block.get(mlabel, {})

                src = str(meta.get("source", "unknown"))

                coeffs = meta.get("coeffs")

                req_mk = str(meta.get("requested_model_kind", _mk))

                rmse_v = rms_b.get(mlabel, float("nan"))

                best_tag = "  best RMSE (this series)" if rank == 0 and np.isfinite(rmse_v) else ""

                lines.append(f"[{mlabel}]{best_tag}")

                lines.append(
                    f"RMSE (fit vs raw n, fit window): {float(rmse_v):.6g}"
                    if np.isfinite(rmse_v)
                    else "RMSE (fit vs raw n, fit window): "
                )

                lines.append(IndexCore._clipboard_law_line_from_source(src, req_mk))

                lines.append(f"internal source: {src}")

                lines.append(IndexCore._clipboard_coeffs_line_from_source(src, coeffs, meta=meta))

                lines.append("")

            lines.append("")

        text = "\n".join(lines).strip() + "\n"

        dlg = QDialog(self)

        dlg.setWindowTitle("Law parameters")

        dlg.resize(980, 620)

        dlg.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};")

        layout = QVBoxLayout(dlg)

        info = QLabel(
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size:11px;'>"
            "RMSE (unweighted, vs raw n on fit window), description and coefficients. "
            "Series (blocks === ... ===): from minimal best RMSE to worst, top of window. "
            "In each series: laws from best to worst RMSE (like table columns). "
            "Copy output now includes the summary banner and fit-window context. "
            "Use the summary button for a compact executive view.</span>"
        )

        info.setWordWrap(True)

        layout.addWidget(info)

        txt = QTextEdit()

        txt.setReadOnly(True)

        txt.setText(text)

        layout.addWidget(txt)

        brow = QHBoxLayout()

        btn_copy = create_styled_button(" Copy", variant="secondary")

        btn_copy.clicked.connect(functools.partial(QApplication.clipboard().setText, text))

        btn_close = create_styled_button("Close", variant="primary")

        btn_close.clicked.connect(dlg.accept)

        brow.addWidget(btn_copy)

        brow.addStretch()

        brow.addWidget(btn_close)

        layout.addLayout(brow)

        dlg.exec()


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

        self._attach_ui_log_handler()

        self.settings = QSettings("SFL", "CERTUS_SUBSTRATE_INDEX")
        self.last_dir = self.settings.value("last_dir", "")

        self._setup_ui()
        self.resize(1100, 850)

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
        
        spec_lo = float(np.nanmin(x)) if x.size else float("nan")
        spec_hi = float(np.nanmax(x)) if x.size else float("nan")

        dialog = IndexTableDialog(
            x,
            n_results_raw,
            n_results_by_model,
            rmse_row,
            fit_meta_by_key=n_fit_meta,
            fit_wl_lo=float(wl_min_fit),
            fit_wl_hi=float(wl_max_fit),
            spectral_wl_lo=spec_lo,
            spectral_wl_hi=spec_hi,
        )

        self._plot_output_results(x, n_results_raw, n_results_by_model, rmse_row, wl_min_fit, wl_max_fit)
        self.main_tabs.setCurrentIndex(1)

    def export_substrate_datasheet(self) -> None:
        """P1-11: Export versioned substrate datasheet (JSON)."""
        if self.last_run_manifest is None:
            QMessageBox.warning(self, "Export", "No result available. Run a Sellmeier fit first.")
            return

        from PyQt6.QtWidgets import QFileDialog
        import json
        from datetime import datetime

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
            with open(path, "w", encoding="utf-8") as f:
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

        self.fit_lmin_spin = QDoubleSpinBox()
        self.fit_lmin_spin.setRange(100.0, 20000.0)
        self.fit_lmin_spin.setDecimals(1)
        self.fit_lmin_spin.setSingleStep(50.0)
        self.fit_lmin_spin.setValue(400.0)
        self.fit_lmin_spin.valueChanged.connect(self._on_fit_range_spin_changed)

        self.fit_lmax_spin = QDoubleSpinBox()
        self.fit_lmax_spin.setRange(100.0, 20000.0)
        self.fit_lmax_spin.setDecimals(1)
        self.fit_lmax_spin.setSingleStep(50.0)
        self.fit_lmax_spin.setValue(5000.0)
        self.fit_lmax_spin.valueChanged.connect(self._on_fit_range_spin_changed)

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
        self.btn_calc_n.setEnabled(False)

        self.btn_export_datasheet = create_styled_button("Export Datasheet (JSON)", variant="outline")
        self.btn_export_datasheet.setToolTip("Export substrate Sellmeier coefficients and metadata to JSON.")
        self.btn_export_datasheet.clicked.connect(self.export_substrate_datasheet)
        self.btn_export_datasheet.setEnabled(False)

        # Row 1 layout
        row1.addWidget(self.btn_load)
        row1.addSpacing(10)
        row1.addWidget(QLabel("lambda min fit (nm):"))
        row1.addWidget(self.fit_lmin_spin)
        row1.addSpacing(10)
        row1.addWidget(QLabel("lambda max fit (nm):"))
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
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size:11px;'>"
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
            pass
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
        self.output_table_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
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

        self.progress_widget = EnhancedProgressWidget()

        if hasattr(self.progress_widget, "canceled"):
            self.progress_widget.canceled.connect(lambda: self.log("Cancellation requested by user...", "WARNING"))

        self.statusBar().addPermanentWidget(self.progress_widget)

        self._apply_full_auto_sellmeier_mode()

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
