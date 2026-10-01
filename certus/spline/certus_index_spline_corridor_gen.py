"""CERTUS-INDEX-SPLINE corridors - the generation mixin: corridors from a partial grid, manual selection and the corridor table (moved out of certus_index_spline_corridors.py, S5.3)."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QMessageBox

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_corridor_utils import (
    _expand_corridor_envelope_with_reported_nk,
    enforce_min_k_corridor_half_width,
)
from certus.spline.certus_index_spline_corridor_ui import CertusTheme


class _CorridorGenMixin:
    """Mixin containing corridor generation, application and table refresh methods."""

    def _on_corridor_rmse_grid_live_update(self, payload: object) -> None:
        """Display the RMSE(d) curve live during grid recalculation."""

        worker_role = str(getattr(self, "_worker_role", "") or "")
        if worker_role not in {"rmse_grid", "corridors"}:
            return

        if not isinstance(payload, dict):
            return

        d_live = np.asarray(payload.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        r_live = np.asarray(payload.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

        if d_live.size == 0 or r_live.size != d_live.size:
            return

        cur = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        upd = dict(cur)

        upd["profile_d_values_nm"] = d_live

        upd["profile_d_rmse_values"] = r_live

        k_live = np.asarray(payload.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
        if k_live.size == d_live.size:
            upd["profile_d_manual_grid_point_kind"] = k_live
        st_live = np.asarray(
            payload.get("profile_d_manual_grid_point_status_code", []),
            dtype=np.int32,
        ).ravel()
        if st_live.size == d_live.size:
            upd["profile_d_manual_grid_point_status_code"] = st_live

        upd["profile_d_status"] = str(payload.get("profile_d_status", "manual_grid_live"))

        upd["profile_d_manual_grid_progress"] = float(payload.get("profile_d_manual_grid_progress", float("nan")))

        upd["profile_d_manual_grid_done_points"] = int(payload.get("profile_d_manual_grid_done_points", d_live.size))

        upd["profile_d_manual_grid_total_points"] = int(payload.get("profile_d_manual_grid_total_points", d_live.size))
        upd["profile_d_manual_grid_base_done_points"] = int(
            payload.get("profile_d_manual_grid_base_done_points", upd["profile_d_manual_grid_done_points"])
        )
        upd["profile_d_manual_grid_extra_done_points"] = int(payload.get("profile_d_manual_grid_extra_done_points", 0))

        if "profile_d_manual_grid_breakpoint_events" in payload:
            upd["profile_d_manual_grid_breakpoint_events"] = payload.get("profile_d_manual_grid_breakpoint_events")

        self._last_result = upd

        n_done_payload = int(upd.get("profile_d_manual_grid_done_points", d_live.size))
        n_tot = int(upd.get("profile_d_manual_grid_total_points", d_live.size))
        p_live = float(upd.get("profile_d_manual_grid_progress", float("nan")))
        if np.isfinite(p_live):
            n_done = int(max(0, min(n_tot, round(float(p_live) * float(max(1, n_tot))))))
            n_done = max(n_done, min(1, n_done_payload))
        else:
            n_done = n_done_payload
        n_base_done = int(upd.get("profile_d_manual_grid_base_done_points", n_done))
        n_extra_done = int(upd.get("profile_d_manual_grid_extra_done_points", max(0, n_done - n_tot)))

        d_cur = float(payload.get("profile_d_manual_grid_current_d_nm", float("nan")))

        if worker_role == "rmse_grid":
            self._set_corridor_grid_progress_ui(
                done=n_done,
                total=n_tot,
                base_done=n_base_done,
                base_total=n_tot,
                extra_done=n_extra_done,
                current_d_nm=(d_cur if np.isfinite(d_cur) else None),
            )

        now_ts = float(time.perf_counter())
        last_ts = float(getattr(self, "_corridor_rmse_live_last_plot_ts", float("nan")))
        min_dt = float(getattr(self, "_corridor_rmse_live_plot_min_interval_s", 0.12) or 0.12)
        should_plot = (
            n_done <= 1 or n_done >= n_tot or (not np.isfinite(last_ts)) or ((now_ts - last_ts) >= max(0.02, min_dt))
        )
        if should_plot:
            try:
                self._plot_corridor_rmse_tab(upd)
                # Hard safety net: if live payload has finite points but plot pipeline
                # produced no visible data items, draw a minimal scatter fallback.
                if hasattr(self, "plot_corridor_rmse_d"):
                    plot_item = getattr(self.plot_corridor_rmse_d, "plotItem", None)
                    data_items = []
                    if plot_item is not None and hasattr(plot_item, "listDataItems"):
                        try:
                            data_items = list(plot_item.listDataItems())
                        except (TypeError, ValueError, RuntimeError, AttributeError):
                            data_items = []
                    if len(data_items) == 0:
                        m_live = np.isfinite(d_live) & np.isfinite(r_live)
                        if np.any(m_live):
                            d_fb = np.asarray(d_live[m_live], dtype=np.float64).ravel()
                            r_fb = np.asarray(r_live[m_live], dtype=np.float64).ravel()
                            self.plot_corridor_rmse_d.addItem(
                                pg.ScatterPlotItem(
                                    d_fb,
                                    r_fb,
                                    pen=pg.mkPen(CertusTheme.PRIMARY, width=0),
                                    brush=pg.mkBrush(0, 87, 255, 160),
                                    size=5,
                                    symbol="o",
                                    name="RMSE(d) live",
                                )
                            )
                            self._set_corridor_rmse_view_data_bounds(d_fb, r_fb)
                self._corridor_rmse_live_last_plot_ts = now_ts

            except NUMERICAL_FAULT_EXCEPTIONS:
                self.logger.debug("RMSE(d) live plot update failed", exc_info=True)

        if self.logger and (n_done <= 1 or n_done >= n_tot or (n_done % 5 == 0)):
            r_at_cur = float("nan")
            if np.isfinite(d_cur) and d_live.size and r_live.size == d_live.size:
                fg_l = np.isfinite(d_live) & np.isfinite(r_live)
                if np.any(fg_l):
                    dl = d_live[fg_l]
                    rl = r_live[fg_l]
                    j_nearest = int(np.argmin(np.abs(dl - float(d_cur))))
                    r_at_cur = float(rl[j_nearest])
            r_cur_txt = f"{r_at_cur:.8f}" if np.isfinite(r_at_cur) else "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | live | pts=%d | base %d/%d | extra_done=%d | current_d_nm=%s | rmse_at_nearest_curve_pt=%s",
                int(n_done),
                int(n_base_done),
                int(n_tot),
                int(n_extra_done),
                (f"{float(d_cur):.6f}" if np.isfinite(d_cur) else "n/a"),
                r_cur_txt,
            )

    def _build_manual_corridor_payload(
        self,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo_nm: float,
        d_hi_nm: float,
    ) -> dict[str, Any] | None:

        d_vals = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)

        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)

        if d_vals.size == 0 or n_curves.ndim != 2 or k_curves.ndim != 2:
            return None

        if n_curves.shape[0] != d_vals.size or k_curves.shape[0] != d_vals.size:
            return None

        if n_curves.shape[1] == 0 or k_curves.shape[1] != n_curves.shape[1]:
            return None

        d_lo = float(min(d_lo_nm, d_hi_nm))

        d_hi = float(max(d_lo_nm, d_hi_nm))

        sel = np.isfinite(d_vals) & (d_vals >= d_lo - 1e-12) & (d_vals <= d_hi + 1e-12)

        if not np.any(sel):
            i_near = int(np.argmin(np.abs(d_vals - 0.5 * (d_lo + d_hi))))

            sel = np.zeros_like(d_vals, dtype=bool)

            sel[i_near] = True

        n_pick = np.asarray(n_curves[sel, :], dtype=np.float64)

        k_pick = np.asarray(k_curves[sel, :], dtype=np.float64)

        if n_pick.ndim != 2 or k_pick.ndim != 2 or n_pick.shape[0] == 0:
            return None

        n_lo = np.nanmin(n_pick, axis=0)

        n_hi = np.nanmax(n_pick, axis=0)

        k_lo = np.nanmin(k_pick, axis=0)

        k_hi = np.nanmax(k_pick, axis=0)

        ref_n = np.asarray(source.get("corridor_reference_n_lam", display.get("n_lam", [])), dtype=np.float64).ravel()

        ref_k = np.asarray(source.get("corridor_reference_k_lam", display.get("k_lam", [])), dtype=np.float64).ravel()

        if ref_n.size == n_lo.size and ref_k.size == k_lo.size:
            n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
                n_lo,
                n_hi,
                k_lo,
                k_hi,
                ref_n,
                ref_k,
            )
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(ref_k, dtype=np.float64),
                min_half_width=1e-4,
            )
        else:
            k_ref_eff = 0.5 * (np.asarray(k_lo, dtype=np.float64) + np.asarray(k_hi, dtype=np.float64))
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(k_ref_eff, dtype=np.float64),
                min_half_width=1e-4,
            )

        d_sel = np.asarray(d_vals[sel], dtype=np.float64)

        if int(k_min_changed) > 0 and self.logger:
            self.logger.info(
                "GUI corridor payload | k-min-width enforced | half_width=1.0e-4 | adjusted_points=%d",
                int(k_min_changed),
            )

        return {
            "profile_d_enabled": True,
            "corridor_n_lo": np.asarray(n_lo, dtype=np.float64),
            "corridor_n_hi": np.asarray(n_hi, dtype=np.float64),
            "corridor_k_lo": np.asarray(k_lo, dtype=np.float64),
            "corridor_k_hi": np.asarray(k_hi, dtype=np.float64),
            "corridor_k_min_half_width": 1e-4,
            "corridor_k_min_half_width_enforced_points": int(k_min_changed),
            "corridor_reference_n_lam": np.asarray(ref_n, dtype=np.float64),
            "corridor_reference_k_lam": np.asarray(ref_k, dtype=np.float64),
            "manual_corridor_active": True,
            "manual_corridor_interval_nm": (float(d_lo), float(d_hi)),
            "manual_corridor_selected_d_range_nm": (float(np.nanmin(d_sel)), float(np.nanmax(d_sel))),
            "manual_corridor_selected_count": int(d_sel.size),
        }

    def _apply_corridor_payload_from_interval(
        self,
        *,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo: float,
        d_hi: float,
        status_prefix: str,
    ) -> bool:

        payload = self._build_manual_corridor_payload(source, display, d_lo, d_hi)

        if payload is None:
            if self.logger:
                self.logger.warning(
                    "GUI corridor regenerate | failed payload build | requested_interval=[%.6f, %.6f] nm",
                    float(min(d_lo, d_hi)),
                    float(max(d_lo, d_hi)),
                )

            return False

        updated = dict(display)

        for k, v in source.items():
            if k.startswith("profile_d_") and k not in updated:
                updated[k] = v

        updated.update(payload)

        self._corridor_rmse_manual_active = True

        self._corridor_rmse_manual_lo = float(payload["manual_corridor_interval_nm"][0])

        self._corridor_rmse_manual_hi = float(payload["manual_corridor_interval_nm"][1])

        self._last_result = updated

        self._plot_result(updated, plot_source="corridor_rmse_manual")

        self._refresh_data_table()

        self._update_corridor_rmse_state_bar(updated)

        self.lbl_status.setText(
            f"{status_prefix} [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
        )

        if self.logger:
            self.logger.info(
                "GUI corridor regenerated | status_prefix=%s | requested_interval=[%.6f, %.6f] nm | selected_points=%d | sampled_selected_range=[%.6f, %.6f] nm",
                str(status_prefix),
                float(self._corridor_rmse_manual_lo),
                float(self._corridor_rmse_manual_hi),
                int(payload.get("manual_corridor_selected_count", 0)),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[0]),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[1]),
            )

        return True

    def _generate_corridor_from_partial_grid(self) -> None:
        """Generate n/k corridor from a centered partial RMSE(d) interval."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        r_s = r_s[m]
        if d_s.size == 0 or r_s.size != d_s.size:
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: empty finite RMSE(d) grid")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No valid finite RMSE(d) points are available.",
            )
            return

        d_best = float(d_s[int(np.argmin(r_s))])
        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))
        if not np.isfinite(d_center):
            d_center = d_best

        half = (
            float(self.sp_corridor_partial_delta_nm.value()) if hasattr(self, "sp_corridor_partial_delta_nm") else 2.0
        )
        if (not np.isfinite(half)) or half <= 0.0:
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Invalid Corridor Deltad: please set a positive finite value.",
            )
            return

        d_lo = float(d_center - half)
        d_hi = float(d_center + half)
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))
        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Partial interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(partial-grid) | request | center=%.6f nm | half=%.6f nm | clipped_interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from partial RMSE(d) grid on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Unable to generate n/k corridor from the selected partial grid interval.",
            )

    def _generate_corridor_auto_smart_from_current_grid(self) -> None:
        """Auto-compute and apply smart corridor interval from current RMSE(d) grid."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(auto-smart) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        # Ensure smart/robust interval state is up-to-date with current grid.
        try:
            self._refresh_corridor_rmse_robust_view()
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Auto-smart corridor: robust refresh failed", exc_info=True)

        d_lo = float("nan")
        d_hi = float("nan")
        interval_source = "none"

        smart_int = getattr(self, "_corridor_rmse_smart_interval", None)
        if (
            isinstance(smart_int, (tuple, list))
            and len(smart_int) >= 2
            and np.isfinite(float(smart_int[0]))
            and np.isfinite(float(smart_int[1]))
        ):
            d_lo = float(min(float(smart_int[0]), float(smart_int[1])))
            d_hi = float(max(float(smart_int[0]), float(smart_int[1])))
            interval_source = "smart_code_interval"
        elif bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))
            d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))
            if np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb > d_lo_rb:
                d_lo = float(d_lo_rb)
                d_hi = float(d_hi_rb)
                interval_source = "robust_parabolic_interval"

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        if d_s.size == 0:
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No valid finite RMSE(d) points are available.",
            )
            return
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))

        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval unavailable for current grid (no smart/robust interval found).",
            )
            return

        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(auto-smart) | request | source=%s | interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                str(interval_source),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix=f"auto smart corridor generated ({interval_source}) on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | failed | source=%s | interval=[%.6f, %.6f] nm",
                    str(interval_source),
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Unable to generate n/k corridor from auto smart interval.",
            )
            return

        # Keep interval highlighted explicitly as active manual interval (red lines)
        # in addition to smart/robust guide lines already shown on RMSE(d) chart.
        try:
            self._refresh_corridor_rmse_robust_view()
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Auto-smart corridor: post-apply robust refresh failed", exc_info=True)

    def _apply_manual_corridor_selection(self) -> None:

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: no corridor profile source/display")

            QMessageBox.information(self, "Generate corridor", "No corridor profile is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: invalid RMSE(d) profile or best index")

            QMessageBox.information(self, "Generate corridor", "No valid RMSE(d) profile is available.")

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        half = self._corridor_manual_half_width_nm()

        d_lo = float(d_center - half)

        d_hi = float(d_center + half)

        if self.logger:
            self.logger.info(
                "GUI generate corridor(manual) | request | center=%.6f nm | half=%.6f nm | interval=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="Manual corridor regenerated on",
        )

        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(manual) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )

            QMessageBox.warning(self, "Generate corridor", "Unable to rebuild a manual corridor from this interval.")

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
