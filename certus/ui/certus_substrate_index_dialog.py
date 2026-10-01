"""CERTUS SUBSTRATE INDEX - the dialog that compares the three refractive-index laws, one table and one plot per law (moved out of certus_substrate_ui.py, S5.3)."""

import functools
import logging

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from certus.core.certus_substrate_index import (
    _MODEL_LABEL_TO_INDEX,
    _N_SUBSTRATE_MODELS,
    SUBSTRATE_INDEX_MODELS,
    IndexCore,
    _bad_model_labels,
    _best_finite_rmse_from_triplet,
    _rms_triplet,
    _rmse_is_bad_vs_best,
    _rmse_is_best_fit,
    _substrate_index_geom_fit_mask,
    _substrate_index_models_ordered_by_rmse,
)
from certus.ui.certus_substrate_plot_utils import (
    _add_pg_fit_band_outside_shading,
    _pg_plot_scatter_split_band,
    _pg_plot_xy_split_band,
)
from certus.ui.certus_ui import (
    CertusScientificPlot,
    CertusTheme,
    ExcelTableWidget,
    attach_excel_clipboard_context_menu,
    create_styled_button,
    create_styled_label,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_ux import Typography


def _quality_of_a_series(rms_by_label: dict[str, float]) -> tuple[float, str]:
    """The best finite RMSE of a series and what it says of the series: good up to 0.02, degraded up to 0.05, poor above; a series without a finite RMSE counts as good."""
    best_v = _best_finite_rmse_from_triplet(_rms_triplet(rms_by_label))
    q_label = "good"
    if np.isfinite(best_v):
        if best_v > 0.02:
            q_label = "degraded"
        if best_v > 0.05:
            q_label = "poor"
    return best_v, q_label


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
            best_v, q_label = _quality_of_a_series(rmse_row.get(bk, {}))
            self._series_quality[bk] = {"best_rmse": float(best_v), "quality_label": q_label}
            summary_rows.append(f"{bk}: best RMSE={best_v:.6g} | quality={q_label}")

        if summary_rows:
            self._series_summary_text = summary_rows
            detail = QLabel(" | ".join(summary_rows))
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: {Typography.BODY}pt;")
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
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

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

        self._plot_the_index_series(
            wl, n_results_raw, n_results_by_model, bad_model, fit_mask_plot, colors, _fit_pen_styles
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

        self._fill_the_rmse_row(table, rmse_font, _col_base_raw)

        self._fill_the_data_rows(wl, bad_column, table, n_data_rows)

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

    def _plot_the_index_series(self, wl, n_results_raw, n_results_by_model, bad_model, fit_mask_plot, colors, _fit_pen_styles):
        """Plot the raw points and the three fitted laws of every substrate series, colouring the best law by the quality of its fit (kept in `_series_quality`)."""
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
            q_label = self._series_quality[key]["quality_label"]

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

    def _fill_the_rmse_row(self, table, rmse_font, _col_base_raw):
        """Write the RMSE of every law under its column in the first row of the table: green for the best, grey for the clearly worse ones."""
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

    def _fill_the_data_rows(self, wl, bad_column, table, n_data_rows):
        """Write one row per wavelength: its index under every series and law, outside-the-fit rows shaded, the wavelength of in-fit rows in bold, bad columns greyed."""
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
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size: {Typography.BODY_LG}pt;'>"
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
