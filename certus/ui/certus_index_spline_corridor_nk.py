"""CERTUS-INDEX-SPLINE corridors - the n/k envelope tab and its data table: how they are built, the crosshair of the k plot, the table refreshed from a result, its copy to the clipboard and its CSV export (methods moved, text unchanged, out of certus_index_spline_corridorui_mixin.py, certus_index_spline_corridor_gen.py and certus_index_spline_rendering.py)."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from certus.spline.certus_corridor_utils import enforce_min_k_corridor_half_width
from certus.ui.certus_index_spline_corridor_common import _apply_fixed_log_k_axis
from certus.ui.certus_index_spline_corridor_ui import (
    CertusScientificPlot,
    CertusTheme,
    ExcelTableWidget,
    create_styled_button,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_atomic_io import atomic_open
from certus.utils.certus_ux import Typography


class _CorridorNkMixin:
    """The n/k envelope tab and its data table. A slice of the window: `CertusIndexSplineCorridorUIMixin` inherits it; what it reads on the window is declared in certus_index_spline_corridor_host.py."""

    @staticmethod
    def _interp_corridor_value(x: float, x_arr: np.ndarray, y_arr: np.ndarray) -> float:
        xa = np.asarray(x_arr, dtype=np.float64).ravel()
        ya = np.asarray(y_arr, dtype=np.float64).ravel()
        m = np.isfinite(xa) & np.isfinite(ya)
        if int(np.count_nonzero(m)) < 2:
            return float("nan")
        xs = xa[m]
        ys = ya[m]
        o = np.argsort(xs, kind="mergesort")
        xs = xs[o]
        ys = ys[o]
        return float(np.interp(float(x), xs, ys, left=np.nan, right=np.nan))

    def _k_corridor_crosshair_formatter(self, x: float, y_on_curve: float | None, y_mouse: float) -> str:
        lam = np.asarray(getattr(self, "_corridor_k_crosshair_lam", []), dtype=np.float64).ravel()
        k_nom = np.asarray(getattr(self, "_corridor_k_crosshair_nom", []), dtype=np.float64).ravel()
        k_min = np.asarray(getattr(self, "_corridor_k_crosshair_lo", []), dtype=np.float64).ravel()
        k_max = np.asarray(getattr(self, "_corridor_k_crosshair_hi", []), dtype=np.float64).ravel()
        kn = self._interp_corridor_value(x, lam, k_nom) if k_nom.size == lam.size else float("nan")
        k0 = self._interp_corridor_value(x, lam, k_min) if k_min.size == lam.size else float("nan")
        k1 = self._interp_corridor_value(x, lam, k_max) if k_max.size == lam.size else float("nan")
        if np.isfinite(k0) and np.isfinite(k1) and k1 < k0:
            k0, k1 = k1, k0
        kn_txt = f"{kn:.3e}" if np.isfinite(kn) and kn > 0.0 else "n/a"
        k0_txt = f"{k0:.3e}" if np.isfinite(k0) and k0 > 0.0 else "n/a"
        k1_txt = f"{k1:.3e}" if np.isfinite(k1) and k1 > 0.0 else "n/a"
        return f"lambda = {x:.2f} nm | k_min = {k0_txt} | k_nom = {kn_txt} | k_max = {k1_txt}"

    def _build_tab_data_corridor(self) -> QWidget:
        """Tab dedicated to detailed corridor uncertainty data."""
        # Sync context stack
        self._add_context_page(
            self._create_empty_context_widget(
                "Detailed corridor uncertainty table.\nIncludes nominal, center, and min/max bounds."
            )
        )

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()
        self.btn_copy_corridor = create_styled_button("Copier tableau Corridors", "secondary")
        self.btn_copy_corridor.setEnabled(False)
        self.btn_copy_corridor.clicked.connect(self._copy_corridor_to_clipboard)
        tb.addWidget(self.btn_copy_corridor)

        self.btn_export_corridor = create_styled_button("Export CSV Corridors...", "primary")
        self.btn_export_corridor.setEnabled(False)
        self.btn_export_corridor.clicked.connect(self._export_corridor_csv)
        tb.addWidget(self.btn_export_corridor)

        tb.addStretch(1)
        lay.addLayout(tb)

        self.table_corridor = ExcelTableWidget()
        self.table_corridor.setColumnCount(9)
        self.table_corridor.setHorizontalHeaderLabels(
            ["lambda (nm)", "n nominal", "k nominal", "n center", "k center", "n min", "n max", "k min", "k max"]
        )
        self.table_corridor.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table_corridor, 1)

        return panel

    def _copy_corridor_to_clipboard(self) -> None:
        if hasattr(self, "table_corridor"):
            t = self.table_corridor
            lines = []
            cols = t.columnCount()
            hdr = [t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(cols)]
            lines.append("\t".join(hdr))
            for r in range(t.rowCount()):
                row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(cols)]
                lines.append("\t".join(row))
            QApplication.clipboard().setText("\n".join(lines))

    def _export_corridor_csv(self) -> None:
        if not self._ensure_complete_manifest_for_secondary_export():
            return
        if not hasattr(self, "table_corridor"):
            return
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Export Corridor CSV", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            import csv

            with atomic_open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [
                    self.table_corridor.horizontalHeaderItem(i).text() for i in range(self.table_corridor.columnCount())
                ]
                writer.writerow(headers)
                for r in range(self.table_corridor.rowCount()):
                    writer.writerow(
                        [
                            self.table_corridor.item(r, c).text() if self.table_corridor.item(r, c) else ""
                            for c in range(self.table_corridor.columnCount())
                        ]
                    )

    def _refresh_corridor_table(self, result: dict) -> None:
        """Populates the detailed data corridor table with smart interpolation."""
        if not hasattr(self, "table_corridor"):
            return

        t = self.table_corridor
        t.setRowCount(0)

        lam_src = result.get("lam_nm")
        n_src = result.get("n_lam")
        k_src = result.get("k_lam")

        if lam_src is None or n_src is None or k_src is None:
            self.btn_copy_corridor.setEnabled(False)
            self.btn_export_corridor.setEnabled(False)
            return

        lam = np.asarray(lam_src, dtype=np.float64).ravel()
        n_nom = np.asarray(n_src, dtype=np.float64).ravel()
        k_nom = np.asarray(k_src, dtype=np.float64).ravel()

        if not lam.size:
            return

        # Smart grid generation
        lo, hi = float(np.nanmin(lam)), float(np.nanmax(lam))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if not lam_g.size:
            return

        # Nominal interpolation
        n_g = np.interp(lam_g, lam, n_nom, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, lam, k_nom, left=np.nan, right=np.nan)

        # Corridor interpolation
        n_lo_g = np.full_like(lam_g, np.nan)
        n_hi_g = np.full_like(lam_g, np.nan)
        k_lo_g = np.full_like(lam_g, np.nan)
        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(result.get("profile_d_enabled", False)) or bool(result.get("manual_corridor_active", False)):
            cn_lo = np.asarray(result.get("corridor_n_lo", []), dtype=np.float64).ravel()
            cn_hi = np.asarray(result.get("corridor_n_hi", []), dtype=np.float64).ravel()
            ck_lo = np.asarray(result.get("corridor_k_lo", []), dtype=np.float64).ravel()
            ck_hi = np.asarray(result.get("corridor_k_hi", []), dtype=np.float64).ravel()

            if cn_lo.size == lam.size:
                n_lo_g = np.interp(lam_g, lam, cn_lo, left=np.nan, right=np.nan)
                n_hi_g = np.interp(lam_g, lam, cn_hi, left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, lam, ck_lo, left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, lam, ck_hi, left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        # Center of corridor (midpoint)
        n_ctr_g = 0.5 * (n_lo_g + n_hi_g)
        k_ctr_g = 0.5 * (k_lo_g + k_hi_g)

        m = int(lam_g.size)
        t.setRowCount(m)

        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidgetItem

        def _cell(val: float, fmt: str = ".4f") -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):{fmt}}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        def _cell_sci(val: float) -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):.2e}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        for i in range(m):
            t.setItem(i, 0, _cell(float(lam_g[i]), ".1f"))
            t.setItem(i, 1, _cell(float(n_g[i])))
            t.setItem(i, 2, _cell_sci(float(k_g[i])))
            t.setItem(i, 3, _cell(float(n_ctr_g[i])))
            t.setItem(i, 4, _cell_sci(float(k_ctr_g[i])))
            t.setItem(i, 5, _cell(float(n_lo_g[i])))
            t.setItem(i, 6, _cell(float(n_hi_g[i])))
            t.setItem(i, 7, _cell_sci(float(k_lo_g[i])))
            t.setItem(i, 8, _cell_sci(float(k_hi_g[i])))

        self.btn_copy_corridor.setEnabled(True)
        self.btn_export_corridor.setEnabled(True)

    def _build_tab_corridor(self) -> QWidget:
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        hint = QLabel(
            "<b>Acceptance envelope (profiling in d)</b> - n(λ) and k(λ) bands after optimization. "
            "Calculation starts from the <b>best polished spectral RMSE</b> ('best RMSE' + RMSE_ref+Delta default): "
            "the displayed reference curve is the scientific nominal, and the envelope groups models whose "
            "masked RMSE remains <= RMSE<sub>best</sub> + Delta. This is not a Bayesian confidence interval."
            "<br><br>"
            "<b>Automatic</b> execution at the end of the run if 'Corridors n/k -> Enable' is checked. "
            "Opened by itself when corridors or bootstrap are available."
            "<br><br>"
            "<b>log10 k:</b> the <b>bold</b> orange curve follows the main optimization result ('n &amp; log10 k' tab). "
            "Shaded area = min/max of linear <i>k</i> from refits accepted at various <i>d</i> "
            "(without corrective widening in scientific mode). The <b>dashed</b> orange curve appears only if a central refit "
            "differs significantly from the bold curve. <b>Crosshair:</b> the value follows the bold curve at the cursor λ."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(CertusTheme.get_hint_text_style())
        ctx_lay.addWidget(hint)

        self.lbl_corridors_tab_state = QLabel()
        self.lbl_corridors_tab_state.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_corridors_tab_state.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: {Typography.BODY_LG}pt;")
        self.lbl_corridors_tab_state.setToolTip("Corridor option state in the UI for the next optimization run.")
        ctx_lay.addWidget(self.lbl_corridors_tab_state)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_n_corridor = CertusScientificPlot(title="n(lambda) + corridors", y_label="n", x_label="lambda (nm)")
        self.plot_n_corridor.showGrid(x=True, y=True, alpha=0.25)

        self.plot_k_corridor = CertusScientificPlot(title="k(lambda) + corridors", y_label="k", x_label="lambda (nm)")
        self.plot_k_corridor.showGrid(x=True, y=True, alpha=0.25)
        _apply_fixed_log_k_axis(self.plot_k_corridor)
        self.plot_k_corridor._certus_crosshair_label_fn = self._k_corridor_crosshair_formatter
        self.plot_k_corridor._certus_crosshair_vertical_only = True

        spl = QSplitter(Qt.Orientation.Vertical)
        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_n_corridor))
        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_k_corridor))
        spl.setStretchFactor(0, 1)
        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        return panel
