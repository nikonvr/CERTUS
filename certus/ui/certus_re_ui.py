# -*- coding: utf-8 -*-
"""
certus_re_ui.py - Extract of CertusREResultsDialog from CERTUS_RE.py
"""

from __future__ import annotations

import numpy as np
from typing import Any

from certus.ui.certus_qt_widgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QTableWidgetItem,
    QColor,
    Qt,
    QHeaderView,
    QAbstractItemView,
    QApplication,
    QTimer,
)

from certus.ui.certus_ui import (
    ExcelTableWidget,
    set_certus_window_icon,
)

from certus.utils.certus_re_helpers import (
    RE_SPLINE_N_KNOTS,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_RANKING_ALPHA_REF,
    _re_sort_results_best_for_table_and_apply,
    re_drift_result_log_suffix,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    re_delta_qwot_per_layer,
)

class CertusREResultsDialog(QDialog):
    def __init__(
        self,
        main_app,
        results: list,
        ep0: np.ndarray,
        *,
        re_rmse_initial: float | None = None,
        re_rmse_phase1: float | None = None,
        re_rmse_final: float | None = None,
        initial_stack: list | None = None,
        announce_in_log: bool = True,
    ):
        from certus.ui.certus_qt_widgets import QWidget
        parent_widget = main_app if isinstance(main_app, QWidget) else None
        super().__init__(parent_widget)

        self.main_app = main_app
        self.results = results
        self.ep0 = ep0
        _re_sort_results_best_for_table_and_apply(results)

        ep0 = np.asarray(ep0, dtype=np.float64).ravel()

        if ep0.size == 0 and results:
            ep0 = np.asarray(results[0].get("ep"), dtype=np.float64).ravel()

        if initial_stack is not None:
            initial_stack = list(initial_stack)

        else:
            initial_stack = getattr(main_app, "_re_initial_stack", [])
        self.initial_stack = initial_stack

        n = int(ep0.size)

        n_runs = len(results)

        l0_ref = float(self.main_app.l0_spin.value())

        self.setWindowTitle(f"RE Results (QWOT @ lambda₀={l0_ref:.0f} nm)")

        set_certus_window_icon(self)

        _n_rmse_rows = 0

        if re_rmse_initial is not None and re_rmse_phase1 is not None and re_rmse_final is not None:
            _n_rmse_rows = 3

        _n_spline_param_rows = 2 * RE_SPLINE_N_KNOTS

        _n_rank_row = 1 if results and results[0].get("re_ranking_score") is not None else 0

        self.resize(
            200 + n_runs * 180,
            min(
                100 + (n + _n_spline_param_rows + _n_rmse_rows + _n_rank_row) * 28 + 120,
                980,
            ),
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(10, 10, 10, 10)

        layout.setSpacing(6)

        if _n_rmse_rows:
            _ri, _r1, _rf = re_rmse_initial, re_rmse_phase1, re_rmse_final

            layout.addWidget(
                QLabel(
                    "<b>RMSE (Deltaln(lambda) trapezoidal weighting, same as RE TRF / least-squares objective)</b><br>"
                    f"Initial (start thicknesses, nominal n): {_ri:.6f}<br>"
                    f"After thickness optimization (nominal n): {_r1:.6f}<br>"
                    f"Final (thicknesses + DeltaRe H/L splines, nominal substrate): {_rf:.6f}<br>"
                    "<i> = run with the lowest spectral RMSE (RMSE column of the summary below) ; "
                    "tie-break -> lowest RMSE. Solution applied at run end = same row.</i>"
                )
            )

        if results and results[0].get("re_ranking_score") is not None:
            _ar0 = float(results[0].get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

            layout.addWidget(
                QLabel(
                    "<b>RMSE (inter-run ranking)</b> = √(RMSE_sp2 + _refRMS(DeltaQ)2) "
                    f" <b>raw</b> QWOT (no dead band), _ref=<b>{_ar0:g}</b>. "
                    "At fixed _ref, lower = better sp / optical thickness trade-off."
                )
            )

        # Summary header

        summary_parts = []

        for i, r in enumerate(results):
            star = " " if i == 0 else ""

            _rk = r.get("re_ranking_score")

            _rk_s = f" &nbsp;|&nbsp; RMSE={float(_rk):.6f}" if _rk is not None else ""

            summary_parts.append(
                f"<b>{r['label']}</b>: RMSE={r['rmse']:.6f}{_rk_s}  "
                f"{re_drift_result_log_suffix(r)}  "
                f"({r['nfev']} evals){star}"
            )

        layout.addWidget(QLabel("<br>".join(summary_parts)))

        layout.addWidget(
            QLabel(
                "<i>QWOT / DeltaQWOT: 4n*ep/lambda₀ at lambda₀; initial tabulated n; "
                "final tabulated n + run DeltaRe splines H/L (aligned with TRF objective QWOT).</i>"
            )
        )

        # Table: Layer | Mat | Initial QWOT | Run1 Final | Run1 DeltaQ | ...

        self.n_cols = 3 + 2 * n_runs

        self.headers = ["#", "Mat", f"Initial QWOT@{l0_ref:.0f}nm"]

        for r in results:
            star = " " if r is results[0] else ""

            self.headers.append(f"{r['label']}{star} QWOT")

            self.headers.append("DeltaQWOT")

        n_total_rows = n + _n_spline_param_rows + _n_rmse_rows + _n_rank_row

        self.tbl = ExcelTableWidget()

        self.tbl.setRowCount(n_total_rows)

        self.tbl.setColumnCount(self.n_cols)

        self.tbl.setHorizontalHeaderLabels(self.headers)

        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.tbl.setAlternatingRowColors(True)

        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        _mats_tbl = self.main_app._get_materials()

        _lref_tbl = np.array([float(l0_ref)], dtype=np.float64)

        _esc_tbl = float(self.main_app._re_envelope_scale_from_gui())

        _kq_tbl = 4.0 / max(float(l0_ref), 1e-9)

        _nref_tbl = np.array(
            [
                float(
                    np.real(
                        np.asarray(
                            _mats_tbl[initial_stack[i].mat].get_nk(_lref_tbl),
                            dtype=np.complex128,
                        )[0]
                    )
                )
                for i in range(n)
            ],
            dtype=np.float64,
        )

        _is_h_tbl = np.array([initial_stack[i].mat == "H" for i in range(n)], dtype=bool)

        _is_l_tbl = np.array([initial_stack[i].mat == "L" for i in range(n)], dtype=bool)

        _run_n_corr_dq: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

        for r in results:
            _ep_r = np.asarray(r["ep"], dtype=np.float64).ravel()

            _lam2_r = self._re_spline_lam2_nm_from_result(r)

            _dh_r = r.get("re_dH_knots")

            _dl_r = r.get("re_dL_knots")

            _nc = re_n_corr_at_lambda_ref(
                _nref_tbl,
                _is_h_tbl,
                _is_l_tbl,
                _lref_tbl,
                _esc_tbl,
                spline_dH=_dh_r,
                spline_dL=_dl_r,
                spline_lam2_nm=_lam2_r,
            )

            _dq = re_delta_qwot_per_layer(
                _ep_r,
                ep0,
                _nref_tbl,
                _is_h_tbl,
                _is_l_tbl,
                float(l0_ref),
                _esc_tbl,
                _lref_tbl,
                spline_dH=_dh_r,
                spline_dL=_dl_r,
                spline_lam2_nm=_lam2_r,
            )

            _run_n_corr_dq.append((_nc, _dq, _ep_r))

        for i in range(n):
            ep_init = float(ep0[i])

            mat_name = initial_stack[i].mat if i < len(initial_stack) else "?"

            qw_init = _kq_tbl * float(_nref_tbl[i]) * ep_init

            self.tbl.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            self.tbl.setItem(i, 1, QTableWidgetItem(mat_name))

            self.tbl.setItem(i, 2, QTableWidgetItem(f"{qw_init:.4f}"))

            for j, r in enumerate(results):
                _nc_j, _dq_j, _ep_j = _run_n_corr_dq[j]

                ep_fin = float(_ep_j[i]) if i < _ep_j.size else float(r["ep"][i])

                qw_fin = _kq_tbl * float(_nc_j[i]) * ep_fin

                delta_q = float(_dq_j[i]) if i < _dq_j.size else (qw_fin - qw_init)

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                self.tbl.setItem(i, col_fin, QTableWidgetItem(f"{qw_fin:.4f}"))

                delta_item = QTableWidgetItem(f"{delta_q:+.4f}")

                if abs(delta_q) < 0.02:
                    delta_item.setForeground(QColor("#22c55e"))

                elif abs(delta_q) < 0.08:
                    delta_item.setForeground(QColor("#f59e0b"))

                else:
                    delta_item.setForeground(QColor("#ef4444"))

                self.tbl.setItem(i, col_d, delta_item)

            for col in range(self.n_cols):
                item = self.tbl.item(i, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        _knot_default = re_knots_wavelengths(RE_SPLINE_NODE2_DEFAULT_NM)

        _knot_display = np.asarray(results[0].get("re_knots_nm", _knot_default), dtype=float)

        _nk = RE_SPLINE_N_KNOTS

        for k in range(_nk):
            row_idx = n + k

            wl_k = float(_knot_display[k]) if k < len(_knot_display) else float(_knot_default[k])

            self.tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            label_item = QTableWidgetItem(f"DeltaRe(H) @ {wl_k:.0f} nm")

            label_item.setForeground(QColor("#60a5fa"))

            self.tbl.setItem(row_idx, 1, label_item)

            self.tbl.setItem(row_idx, 2, QTableWidgetItem("0"))

            for j, r in enumerate(results):
                dh = r.get("re_dH_knots", [0.0] * _nk)

                val = float(dh[k]) if k < len(dh) else 0.0

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                val_item = QTableWidgetItem(f"{val:+.5f}")

                val_item.setForeground(QColor("#60a5fa"))

                self.tbl.setItem(row_idx, col_fin, val_item)

                self.tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(self.n_cols):
                item = self.tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for k in range(_nk):
            row_idx = n + _nk + k

            wl_k = float(_knot_display[k]) if k < len(_knot_display) else float(_knot_default[k])

            self.tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            label_item = QTableWidgetItem(f"DeltaRe(L) @ {wl_k:.0f} nm")

            label_item.setForeground(QColor("#34d399"))

            self.tbl.setItem(row_idx, 1, label_item)

            self.tbl.setItem(row_idx, 2, QTableWidgetItem("0"))

            for j, r in enumerate(results):
                dl = r.get("re_dL_knots", [0.0] * _nk)

                val = float(dl[k]) if k < len(dl) else 0.0

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                val_item = QTableWidgetItem(f"{val:+.5f}")

                val_item.setForeground(QColor("#34d399"))

                self.tbl.setItem(row_idx, col_fin, val_item)

                self.tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(self.n_cols):
                item = self.tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if _n_rmse_rows:

            def _fmt_rmse_cell(v: float) -> str:

                return f"{float(v):.6f}" if np.isfinite(v) else ""

            for kr, (rmse_lbl, rmse_v) in enumerate(
                [
                    ("RMSE initial (spectral Deltaln(lambda) trap + ×QWOT)  start thicknesses", re_rmse_initial),
                    ("RMSE after phase 1 (same definition)", re_rmse_phase1),
                    ("RMSE final (spectral + ×QWOT)  thicknesses + Re H/L splines", re_rmse_final),
                ]
            ):
                row_idx = n + _n_spline_param_rows + kr

                self.tbl.setItem(row_idx, 0, QTableWidgetItem(""))

                li = QTableWidgetItem(rmse_lbl)

                li.setForeground(QColor("#a78bfa"))

                self.tbl.setItem(row_idx, 1, li)

                self.tbl.setItem(row_idx, 2, QTableWidgetItem(""))

                rv = QTableWidgetItem(_fmt_rmse_cell(rmse_v))

                rv.setForeground(QColor("#a78bfa"))

                self.tbl.setItem(row_idx, 3, rv)

                self.tbl.setItem(row_idx, 4, QTableWidgetItem(""))

                for j in range(1, n_runs):
                    self.tbl.setItem(row_idx, 3 + 2 * j, QTableWidgetItem(""))

                    self.tbl.setItem(row_idx, 4 + 2 * j, QTableWidgetItem(""))

                for col in range(self.n_cols):
                    item = self.tbl.item(row_idx, col)

                    if item:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if _n_rank_row:
            row_idx = n + _n_spline_param_rows + _n_rmse_rows

            self.tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            _ar_tbl = float(results[0].get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

            li = QTableWidgetItem(f"Ranking RMSE (√(sp2+_refQWOT_raw2), _ref={_ar_tbl:g})")

            li.setForeground(QColor("#f472b6"))

            self.tbl.setItem(row_idx, 1, li)

            self.tbl.setItem(row_idx, 2, QTableWidgetItem(""))

            for j, r in enumerate(results):
                rs = r.get("re_ranking_score")

                qrw = r.get("re_rmse_qwot_raw")

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                if rs is not None:
                    rv = QTableWidgetItem(f"{float(rs):.6f}")

                    rv.setForeground(QColor("#f472b6"))

                    rv.setToolTip(
                        f"RMSE_sp={float(r['rmse']):.6f}\n"
                        f"QWOT_raw (RMS |DeltaQ|)={float(qrw) if qrw is not None else 0.0:.6f}"
                    )

                    self.tbl.setItem(row_idx, col_fin, rv)

                else:
                    self.tbl.setItem(row_idx, col_fin, QTableWidgetItem(""))

                self.tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(self.n_cols):
                item = self.tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.tbl)

        # Buttons

        btn_row = QHBoxLayout()

        export_tgt_btn = QPushButton(" Export cibles vs calcul (Excel)")

        export_tgt_btn.setToolTip(
            "One sheet per measurement point: target (RE file) vs computed R or T "
            "(thicknesses + DeltaRe H/L splines of the  solution)."
        )

        export_tgt_btn.clicked.connect(self.export_tgt_calc)

        idx_drift_btn = QPushButton(" Re indices (before / after correction)")

        idx_drift_btn.setToolTip("Tabulated Re vs after DeltaRe splines (H/L)  substrate unchanged.")

        idx_drift_btn.clicked.connect(self.open_idx)

        overlay_plot_btn = QPushButton(" Overlay plot (targets vs theory)")

        overlay_plot_btn.setToolTip("Plot theoretical spectra overlaid on RE targets.")

        overlay_plot_btn.clicked.connect(self.show_plot_overlay)

        overlay_indices_btn = QPushButton(" Index plot (before/after)")

        overlay_indices_btn.setToolTip("Plot indices before and after RE correction.")

        overlay_indices_btn.clicked.connect(self.show_indices_plot)

        delta_qwot_btn = QPushButton(" Plot DeltaQWOT")

        delta_qwot_btn.setToolTip(
            "DeltaQWOT per layer: (4/lambda₀)(n_fin*ep_fin - n_init*ep_init) with n_fin = n_tab + run DeltaRe splines."
        )

        delta_qwot_btn.clicked.connect(self.show_delta_qwot_plot)

        beam_ap_plot_btn = QPushButton(" Beam ap(lambda)")

        beam_ap_plot_btn.setToolTip(
            "ap(lambda) in constant steps between lambda nodes (staircase steps), "
            "one curve per run (= best). The step ap values are not constrained to be monotonic."
        )

        beam_ap_plot_btn.clicked.connect(self.plot_beam_aperture)

        self.copy_btn = QPushButton(" Copy to Clipboard")

        self.copy_btn.clicked.connect(self.copy_to_clipboard)

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(self.close)

        btn_row.addWidget(export_tgt_btn)

        btn_row.addWidget(idx_drift_btn)

        btn_row.addWidget(overlay_plot_btn)

        btn_row.addWidget(overlay_indices_btn)

        btn_row.addWidget(delta_qwot_btn)

        btn_row.addWidget(beam_ap_plot_btn)

        btn_row.addWidget(self.copy_btn)

        btn_row.addStretch()

        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.setMinimumSize(640, 420)

        if announce_in_log:
            self.main_app.log(
                "RE: results display; modal opening of 'RE Results' window "
                "(QWOT table, DeltaQWOT, DeltaRe splines, RMSE milestones, exports).",
                "INFO",
            )

        self.show()

        self.raise_()

        self.activateWindow()

        self.exec()

    def _re_spline_lam2_nm_from_result(self, r: dict) -> float:
        return self.main_app._re_spline_lam2_nm_from_result(r)

    def export_tgt_calc(self):

            best_r = self.results[0]

            ep_b = np.asarray(best_r["ep"], dtype=np.float64).flatten()

            a_b = float(best_r.get("a", 0.0))

            b_b = float(best_r.get("b", 0.0))

            f_b = float(best_r.get("f", 0.0))

            lbl = str(best_r.get("label", "best")).replace("/", "-").replace("\\", "-")[:48]

            sdh, sdl = best_r.get("re_dH_knots"), best_r.get("re_dL_knots")

            self.main_app.export_re_targets_vs_theory(
                ep_b,
                a_b,
                b_b,
                f_b,
                spline_dH=sdh,
                spline_dL=sdl,
                run_label=lbl,
            )

    def open_idx(self):

            best_r = self.results[0]

            if best_r.get("re_dH_knots") is not None and best_r.get("re_dL_knots") is not None:
                _rkw = best_r.get("re_knots_nm")

                _lam_d = (
                    float(np.asarray(_rkw, dtype=float)[1])
                    if _rkw is not None and len(_rkw) > 1
                    else best_r.get("re_spline_lam_node2_nm")
                )

                self.main_app._show_re_drifted_indices_window(
                    spline_dH=np.asarray(best_r["re_dH_knots"], dtype=np.float64),
                    spline_dL=np.asarray(best_r["re_dL_knots"], dtype=np.float64),
                    spline_lam_node2_nm=_lam_d,
                    re_envelope_scale=self.main_app._re_envelope_scale_from_gui(),
                    cauchy_a0=best_r.get("re_sub_cauchy_a0"),
                    cauchy_a1=best_r.get("re_sub_cauchy_a1"),
                    cauchy_a2=best_r.get("re_sub_cauchy_a2"),
                    parent=self,
                )

            else:
                self.main_app._show_re_drifted_indices_window(
                    float(best_r.get("a", 0.0)),
                    float(best_r.get("b", 0.0)),
                    float(best_r.get("f", 0.0)),
                    parent=self,
                )

    def show_plot_overlay(self):

            best_r = self.results[0]

            self.main_app._show_re_target_plot_overlay(best_r, parent=self)

    def show_indices_plot(self):

            self.main_app._show_re_indices_plot_overlay(self.results[0], parent=self)

    def show_delta_qwot_plot(self):

            self.main_app._show_re_delta_qwot_plot(self.results[0], self.initial_stack, self.ep0, parent=self)

    def plot_beam_aperture(self):

            self.main_app._show_re_p4_beam_aperture_plot(self.results, parent=self)

    def copy_to_clipboard(self):

            lines = ["\t".join(self.headers)]

            for i in range(self.tbl.rowCount()):
                row_vals = [self.tbl.item(i, c).text() if self.tbl.item(i, c) else "" for c in range(self.n_cols)]

                lines.append("\t".join(row_vals))

            QApplication.clipboard().setText("\n".join(lines))

            self.copy_btn.setText(" Copied!")

            QTimer.singleShot(1500, lambda: self.copy_btn.setText(" Copy to Clipboard"))
