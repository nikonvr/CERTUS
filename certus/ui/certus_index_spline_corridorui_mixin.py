from __future__ import annotations

from threading import Event
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMessageBox, QScrollArea, QVBoxLayout, QWidget

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
from certus.ui.certus_index_spline_common import _worker_corridor_rmse_healer, logger
from certus.ui.certus_index_spline_corridor_rmse_view import _CorridorRmseViewMixin
from certus.ui.certus_index_spline_corridor_run import _CorridorRunMixin
from certus.ui.certus_ui import (
    CertusCard,
    CertusScientificPlot,
    CertusTheme,
    ExcelTableWidget,
    GenericWorker,
    create_styled_button,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_atomic_io import atomic_open


class CertusIndexSplineCorridorUIMixin(_CorridorRunMixin, _CorridorRmseViewMixin):
    """CertusIndexSplineCorridorUIMixin."""

    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None:
        """Starts the gap healing worker after the grid, outside the ``finished`` handler (prevents ``_cleanup_thread``)."""
        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: a worker is already running.")
            return
        cfg = self._last_run_cfg
        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: no optimization config.")
            return
        self._stop_event = Event()
        self._worker = GenericWorker(
            _worker_corridor_rmse_healer,
            cfg,
            tasks,
            self._stop_event,
        )
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "rmse_heal"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_corridor_grid_busy(True)
        self._worker.start()

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

    def _use_robust_corridor_interval(self) -> None:

        if not bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        float(d_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        if not (np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb >= d_lo_rb):
            return

        half = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        half = float(min(max(0.0, half), max_half))

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.setValue(round(half * scale))
            # setValue does not emit valueChanged if unchanged: force visual sync
            # so vertical interval bars always reflect current robust bounds.
            self._on_corridor_manual_slider_changed(self.sl_corridor_manual_half.value())

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
