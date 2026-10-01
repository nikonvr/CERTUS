"""CERTUS-INDEX-SPLINE corridors - the data mixin: the n / k and thickness tables and their previews (moved out of certus_index_spline_corridors.py, S5.3)."""

from __future__ import annotations

from typing import Any
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QTableWidgetItem

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_core import (
    SplineOptConfig,
    ensure_lam_nm_array,
    substrate_id_from_name,
)
from certus.utils.certus_index_utils import _get_substrate_n_array_spline
from certus.spline.spline_objective import spectral_mse_rmse_masked_from_nk
from certus.spline.spline_pipeline import _sync_theoretical_tr_from_nk_dict
from certus.spline.certus_corridor_utils import enforce_min_k_corridor_half_width
from certus.spline.certus_index_spline_corridor_ui import CertusScientificPlot, ManualSigmaKnotDialog


class _DataMixin:
    """Mixin containing data table and nk data preparation methods."""

    def _prepare_nk_data_tab_series(
        self, r: dict[str, Any]
    ) -> (
        tuple[
            np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
        ]
        | None
    ):
        """n/k series (and NL, envelopes) interpolated on piecewise lambda grid."""

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data tab n/k: missing lam_nm in result; fallback to experimental lambda grid.")
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()

        n_ = np.asarray(r["n_lam"], dtype=np.float64).ravel()

        k_ = np.asarray(r["k_lam"], dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_.size, k_.size))

        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")

        ls = lam[:m0][order]

        ns = n_[:m0][order]

        ks = k_[:m0][order]

        fg = np.isfinite(ls)

        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))

        hi = float(np.nanmax(ls[fg]))

        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)

        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, ns, left=np.nan, right=np.nan)

        k_g = np.interp(lam_g, ls, ks, left=np.nan, right=np.nan)

        m = m0

        lam_full = lam[:m0]

        n_lo_g = np.full_like(lam_g, np.nan)

        n_hi_g = np.full_like(lam_g, np.nan)

        k_lo_g = np.full_like(lam_g, np.nan)

        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(r.get("profile_d_enabled", False)) or bool(r.get("manual_corridor_active", False)):
            cn_lo = np.asarray(r.get("corridor_n_lo", []), dtype=np.float64).ravel()

            cn_hi = np.asarray(r.get("corridor_n_hi", []), dtype=np.float64).ravel()

            ck_lo = np.asarray(r.get("corridor_k_lo", []), dtype=np.float64).ravel()

            ck_hi = np.asarray(r.get("corridor_k_hi", []), dtype=np.float64).ravel()

            lsz = lam_full.size

            if cn_lo.size == lsz and cn_hi.size == lsz and ck_lo.size == lsz and ck_hi.size == lsz:
                n_lo_g = np.interp(lam_g, ls, cn_lo[:m][order], left=np.nan, right=np.nan)

                n_hi_g = np.interp(lam_g, ls, cn_hi[:m][order], left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, ls, ck_lo[:m][order], left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, ls, ck_hi[:m][order], left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots and Detailed Corridor Tab
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        return (lam_g, n_g, k_g, n_lo_g, n_hi_g, k_lo_g, k_hi_g)

    def _prepare_data_th_tab_series(
        self, r: dict[str, Any]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data TH: missing lam_nm in result; fallback to experimental lambda grid.")

        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        n_src = np.asarray(r.get("n_lam", []), dtype=np.float64).ravel()
        k_src = np.asarray(r.get("k_lam", []), dtype=np.float64).ravel()
        t_src = np.asarray(r.get("t_theo", []), dtype=np.float64).ravel()
        r_src = np.asarray(r.get("r_theo", []), dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_src.size, k_src.size))
        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")
        ls = lam[:m0][order]
        n_s = n_src[:m0][order]
        k_s = k_src[:m0][order]

        fg = np.isfinite(ls)
        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))
        hi = float(np.nanmax(ls[fg]))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, n_s, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, ls, k_s, left=np.nan, right=np.nan)

        t_g = np.full_like(lam_g, np.nan)
        if t_src.size >= m0:
            t_s = t_src[:m0][order]
            t_g = np.interp(lam_g, ls, t_s, left=np.nan, right=np.nan)

        r_g = np.full_like(lam_g, np.nan)
        if r_src.size >= m0:
            r_s = r_src[:m0][order]
            r_g = np.interp(lam_g, ls, r_s, left=np.nan, right=np.nan)

        ns_g = np.full_like(lam_g, np.nan)
        ns_src = np.asarray(r.get("n_sub_effective", []), dtype=np.float64).ravel()
        if ns_src.size >= m0:
            ns_s = ns_src[:m0][order]
            ns_g = np.interp(lam_g, ls, ns_s, left=np.nan, right=np.nan)
        else:
            try:
                sub_name = str(
                    r.get("substrate_name")
                    or getattr(self, "sub_name", "")
                    or (
                        self.cb_sub.currentData()
                        if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                        else ""
                    )
                )
                sid = substrate_id_from_name(sub_name)
                ns_raw = np.asarray(_get_substrate_n_array_spline(sid, lam_g), dtype=np.float64).ravel()
                if ns_raw.size == lam_g.size:
                    ns_g = ns_raw
            except NUMERICAL_FAULT_EXCEPTIONS:
                if self.logger:
                    self.logger.debug("Data TH substrate ns build failed", exc_info=True)
            except (TypeError, ValueError):
                if self.logger:
                    self.logger.debug("Data TH substrate lookup failed", exc_info=True)

        d_nm = float(r.get("d_nm", float("nan")))
        d_g = np.full_like(lam_g, d_nm, dtype=np.float64)

        return (lam_g, n_g, k_g, d_g, ns_g, t_g, r_g)

    def _baseline_substrate_n_for_result(
        self,
        result: dict,
        *,
        lam_override: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray] | None:

        lam_src = lam_override if lam_override is not None else result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        if lam.size == 0:
            return None

        sub_name = str(
            result.get("substrate_name")
            or getattr(self, "sub_name", "")
            or (
                self.cb_sub.currentData()
                if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                else ""
            )
        )
        sid = substrate_id_from_name(sub_name)
        n_sub = np.asarray(_get_substrate_n_array_spline(sid, lam), dtype=np.float64).ravel()
        if n_sub.size != lam.size:
            return None
        return lam.copy(), n_sub.copy()

    @staticmethod
    def _decorate_result_with_substrate_offset(
        result: dict,
        *,
        n_sub_base: np.ndarray,
        delta_ns: float,
    ) -> dict:

        out = dict(result)
        base = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()
        out["n_sub_base"] = base
        out["substrate_n_offset"] = float(delta_ns)
        out["n_sub_effective"] = base + float(delta_ns)
        return out

    @staticmethod
    def _cfg_with_result_substrate(cfg_base: SplineOptConfig, result: dict) -> SplineOptConfig:

        n_eff = np.asarray(result.get("n_sub_effective", []), dtype=np.float64).ravel()
        lam_cfg = np.asarray(getattr(cfg_base, "lam_nm", []), dtype=np.float64).ravel()
        if lam_cfg.size and n_eff.size == lam_cfg.size:
            n_base = np.asarray(result.get("n_sub_base", []), dtype=np.float64).ravel()
            if n_base.size != lam_cfg.size:
                n_base = n_eff.copy()
            return cfg_base.replace(
                n_sub=n_eff.copy(),
                substrate_n_base=n_base.copy(),
                substrate_n_offset=float(result.get("substrate_n_offset", 0.0)),
            )
        return cfg_base

    def _apply_manual_substrate_offset_preview(self, seed_result: dict, delta_ns: float) -> bool:

        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return False

        lam_preview = np.asarray(seed_result.get("lam_nm", getattr(cfg_base, "lam_nm", [])), dtype=np.float64).ravel()
        baseline_payload = self._baseline_substrate_n_for_result(seed_result, lam_override=lam_preview)
        if baseline_payload is None:
            return False
        _, n_sub_base = baseline_payload

        preview = self._decorate_result_with_substrate_offset(
            seed_result,
            n_sub_base=n_sub_base,
            delta_ns=float(delta_ns),
        )
        cfg_preview = cfg_base.replace(
            n_sub=np.asarray(preview["n_sub_effective"], dtype=np.float64).ravel().copy(),
            substrate_n_base=np.asarray(preview["n_sub_base"], dtype=np.float64).ravel().copy(),
            substrate_n_offset=float(delta_ns),
        )
        _sync_theoretical_tr_from_nk_dict(
            cfg_preview,
            preview,
            log=self.logger,
            reason="manual_delta_ns_preview",
        )
        try:
            mse_preview, rmse_preview = spectral_mse_rmse_masked_from_nk(
                cfg_preview,
                preview,
                np.asarray(preview.get("lam_nm", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("n_lam", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("k_lam", []), dtype=np.float64).ravel(),
                float(preview.get("d_nm", float("nan"))),
            )
            if np.isfinite(mse_preview):
                preview["mse"] = float(mse_preview)
            if np.isfinite(rmse_preview):
                preview["rmse"] = float(rmse_preview)
        except (TypeError, ValueError, RuntimeError):
            if self.logger:
                self.logger.debug("Manual delta-ns preview RMSE recompute failed", exc_info=True)

        self._last_worker_result = dict(preview)
        self._last_result = dict(preview)
        self._plot_result(preview, plot_source="manual_delta_ns_preview")
        self._refresh_data_table(result_override=preview)
        self.lbl_status.setText(
            self._post_optimization_ready_status(
                self._format_post_optimization_status(preview, preview)
            )
        )
        return True

    def _refresh_manual_dialog_preview(self, dialog: ManualSigmaKnotDialog | None, preview_result: dict | None) -> None:

        if not isinstance(dialog, ManualSigmaKnotDialog) or not isinstance(preview_result, dict):
            return
        lam_preview = np.asarray(preview_result.get("lam_nm", []), dtype=np.float64).ravel()
        y_preview = np.empty(0, dtype=np.float64)
        t_val = preview_result.get("t_theo")
        if t_val is not None:
            y_preview = np.asarray(t_val, dtype=np.float64).ravel()
        if y_preview.size == 0:
            r_val = preview_result.get("r_theo")
            if r_val is not None:
                y_preview = np.asarray(r_val, dtype=np.float64).ravel()
        dialog.update_model_preview(lam_preview, y_preview)
        d_preview, rmse_preview = self._runtime_metrics_from_result_dict(preview_result)
        dialog.set_runtime_metrics(d_preview, rmse_preview)

    def _copy_nk_to_clipboard(self) -> None:

        if self._last_result is None:
            QMessageBox.information(self, "Clipboard", "Run an optimization first.")

            return

        r = self._last_result

        ser = self._prepare_nk_data_tab_series(r)

        if ser is None:
            QMessageBox.information(self, "Clipboard", "Empty grid.")

            return

        (
            lam_g,
            n_g,
            k_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        hdr = "lambda_nm\tn\tn_envelope_min\tn_envelope_max\tk\tk_envelope_min\tk_envelope_max"

        lines = [hdr]

        m = int(lam_g.size)

        for i in range(m):
            row = f"{float(lam_g[i]):.4f}\t"

            row += self._fmt_n_data_tab(float(n_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_lo_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_hi_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_lo_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_hi_g[i]))

            lines.append(row)

        cb = QApplication.clipboard()

        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")

            return

        cb.setText("\n".join(lines))

        self.lbl_status.setText("Data table copied (TSV).")

        self.btn_copy_nk.setText(" Copied!")

        QTimer.singleShot(1800, lambda: self.btn_copy_nk.setText("Copy full table (TSV)"))

    def _copy_data_th_to_clipboard(self) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        if t.rowCount() <= 0 or t.columnCount() <= 0:
            QMessageBox.information(self, "Clipboard", "Data TH empty.")
            return

        headers = [
            t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(t.columnCount())
        ]
        lines = ["\t".join(headers)]

        for r in range(t.rowCount()):
            row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())]
            lines.append("\t".join(row))

        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText("\n".join(lines))
        self.lbl_status.setText("Data TH copied (TSV).")

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setText(" Copied!")
            QTimer.singleShot(
                1800,
                lambda: self.btn_copy_data_th.setText("Copy Data TH table (TSV)"),
            )

    def _on_data_preview_plot_mouse_moved(
        self,
        src: CertusScientificPlot,
        pos: Any,
        x: float,
        y: float,
        y_show: Any,
    ) -> None:
        """Synchronizes both previews (lambda) and tooltip with all interpolated n and k."""

        del pos, y_show

        s = getattr(self, "_data_preview_series", None)

        if not isinstance(s, dict):
            return

        pn = self.plot_data_preview_n

        pk = self.plot_data_preview_k

        lam = s.get("lam")

        if lam is None:
            return

        lam_a = np.asarray(lam, dtype=np.float64).ravel()

        def _fmt_nq(v: float) -> str:

            return self._fmt_n_data_tab(v) if np.isfinite(v) else "-"

        def _fmt_kq(v: float) -> str:

            if not np.isfinite(v) or v < 0:
                return "-"

            return self._fmt_k_data_tab(float(v))

        n_at = self._interp_preview_axis(lam_a, s["n"], x)

        nlo_at = self._interp_preview_axis(lam_a, s["n_lo"], x)

        nhi_at = self._interp_preview_axis(lam_a, s["n_hi"], x)

        k_at = self._interp_preview_axis(lam_a, s["k"], x)

        klo_at = self._interp_preview_axis(lam_a, s["k_lo"], x)

        khi_at = self._interp_preview_axis(lam_a, s["k_hi"], x)

        lam_txt = float(x)

        txt = (
            f"lambda = {lam_txt:.2f} nm\n"
            f"n={_fmt_nq(n_at)}  n_min={_fmt_nq(nlo_at)}  n_max={_fmt_nq(nhi_at)}\n"
            f"k={_fmt_kq(k_at)}  k_min={_fmt_kq(klo_at)}  k_max={_fmt_kq(khi_at)}"
        )

        k_floor = float(s.get("k_floor", 1e-30))

        if not (np.isfinite(k_floor) and k_floor > 0.0):
            k_floor = 1e-30

        pn.vLine.setPos(x)

        pk.vLine.setPos(x)

        pn.hLine.setVisible(False)

        pk.hLine.setVisible(False)

        for w in (pn, pk):
            try:
                xr = w.plotItem.vb.viewRange()[0]

                x_lo, x_hi = float(xr[0]), float(xr[1])

                span = x_hi - x_lo

                if span > 0 and x > x_lo + 0.78 * span:
                    w.info_label.setAnchor((1, 1))

                else:
                    w.info_label.setAnchor((0, 1))

            except NUMERICAL_FAULT_EXCEPTIONS:
                w.info_label.setAnchor((0, 1))

        pn.info_label.setText(txt)

        pk.info_label.setText(txt)

        if src is pn:
            pn_y = float(y)

            if np.isfinite(k_at) and float(k_at) > 0.0:
                pk_y = float(k_at)

            elif np.isfinite(k_at) and float(k_at) == 0.0:
                pk_y = k_floor

            else:
                pk_y = self._vb_mid_y_plot(pk)

        else:
            pk_y = float(y)

            pn_y = float(n_at) if np.isfinite(n_at) else self._vb_mid_y_plot(pn)

        pn.info_label.setPos(x, pn_y)

        pk.info_label.setPos(x, pk_y)

    def _refresh_data_table(self, result_override: dict | None = None) -> None:

        if not hasattr(self, "table_nk"):
            return

        t = self.table_nk

        t.setRowCount(0)

        result_eff = result_override if isinstance(result_override, dict) else self._last_result

        if result_eff is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=None)

            return

        ser = self._prepare_nk_data_tab_series(result_eff)

        if ser is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=result_eff)

            return

        (
            lam_g,
            n_g,
            k_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        t.setColumnCount(7)

        t.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n env min",
                "n env max",
                "k",
                "k env min",
                "k env max",
            ]
        )

        t.setRowCount(m)

        n_valid = 0

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))

            if np.isfinite(n_g[i]) and np.isfinite(k_g[i]) and float(k_g[i]) >= 0.0:
                n_valid += 1

            t.setItem(i, 1, _cell_n(float(n_g[i])))

            t.setItem(i, 2, _cell_n(float(n_lo_g[i])))

            t.setItem(i, 3, _cell_n(float(n_hi_g[i])))

            t.setItem(i, 4, _cell_k(float(k_g[i])))

            t.setItem(i, 5, _cell_k(float(k_lo_g[i])))

            t.setItem(i, 6, _cell_k(float(k_hi_g[i])))

        self.btn_copy_nk.setEnabled(m > 0 and n_valid > 0)

        self.btn_export_nk.setEnabled(m > 0 and n_valid > 0)

        self._refresh_data_preview_plots(ser=ser)
        self._refresh_data_th_table(result_eff=result_eff)
        self._refresh_corridor_table(result_eff)

    def _refresh_data_th_table(self, result_eff: dict | None) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        t.setRowCount(0)

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(False)

        if not isinstance(result_eff, dict):
            return

        ser = self._prepare_data_th_tab_series(result_eff)
        if ser is None:
            return

        lam_g, n_g, k_g, d_g, ns_g, t_g, r_g = ser

        m = int(lam_g.size)
        t.setColumnCount(7)
        t.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
        t.setRowCount(m)

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        def _cell_lin(x: float, fmt: str = ".6f") -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(f"{float(x):{fmt}}")

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))
            t.setItem(i, 1, _cell_n(float(n_g[i])))
            t.setItem(i, 2, _cell_k(float(k_g[i])))
            t.setItem(i, 3, _cell_lin(float(d_g[i]), ".4f"))
            t.setItem(i, 4, _cell_n(float(ns_g[i])))
            t.setItem(i, 5, _cell_lin(float(t_g[i])))
            t.setItem(i, 6, _cell_lin(float(r_g[i])))

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(m > 0)
