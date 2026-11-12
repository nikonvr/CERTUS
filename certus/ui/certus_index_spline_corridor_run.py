"""CERTUS-INDEX-SPLINE corridors - the life cycle of a corridor run: the toggle, the deferred worker, the busy state and the progress of the RMSE(d) grid, the heal and the deep refit, the auto-refine chain (methods moved, text unchanged, out of certus_index_spline_settings.py, certus_index_spline_corridorui_mixin.py, certus_index_spline_eventsextras_mixin.py and certus_index_spline_corridor_gen.py)."""

from __future__ import annotations

import time

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QMessageBox

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_core import (
    _log_index_spline_best_config,
    ensure_lam_nm_array,
    log_index_spline_d_trace,
    logger,
)
from certus.spline.spline_pipeline import worker_run_corridor_profile_after_nl_choice
from certus.ui.certus_index_spline_corridor_jobs import _worker_curve_minimum_deep_refit
from certus.ui.certus_index_spline_corridor_ui import CertusTheme, GenericWorker
from certus.ui.certus_index_spline_lazy_app import CertusIndexSplineApp
from certus.utils.certus_progress_tracker import StepState, build_progress_snapshot


class _CorridorRunMixin:
    """The life cycle of a corridor run. A slice of the window: `_CorridorControlMixin` and `CertusIndexSplineCorridorUIMixin` inherit it; what it reads on the window is declared in certus_index_spline_corridor_host.py."""

    def _start_deferred_corridor_worker(self, result: dict) -> bool:

        cfg_base = self._last_run_cfg

        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)

        if cfg_base is None:
            return False

        self.__class__._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        cfg_corr = self._cfg_with_result_substrate(cfg_base, result).replace()

        cfg_corr.gui_defer_corridor_profile_after_nl = False
        # Manual "Corridors" action must execute profiling now, regardless of the main run checkbox state.
        cfg_corr.corridor_profile_d_enabled = True

        # --- Resync solver snapshot if manual dialog changed the mesh (K) ---
        _snap = result.get("gui_solver_snapshot_for_corridors")
        _snap_k = 0
        if isinstance(_snap, dict):
            _snap_sk = np.asarray(_snap.get("sigma_knots", []), dtype=np.float64).ravel()
            _snap_k = int(_snap_sk.size)
        _cur_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        _cur_k = int(_cur_sk.size)
        if _cur_k >= 2 and _cur_k != _snap_k:
            fresh_snap = dict(result)
            for _key in ("x", "x_seg_spline_sigma", "n_nodes_physical", "L_nodes",
                         "sigma_knots", "d_nm", "n_lam", "k_lam", "rmse", "mse"):
                if _key in result:
                    val = result[_key]
                    if isinstance(val, np.ndarray):
                        fresh_snap[_key] = val.copy()
                    else:
                        fresh_snap[_key] = val
            result["gui_solver_snapshot_for_corridors"] = fresh_snap
            if self.logger:
                self.logger.info(
                    "[INDEX_SPLINE.CORRIDORS] solver snapshot resynced to current mesh | k_snap=%d -> k_current=%d",
                    _snap_k, _cur_k,
                )


        self._worker = GenericWorker(
            worker_run_corridor_profile_after_nl_choice, cfg_corr, dict(result), self._stop_event
        )

        def _corr_progress(p: float | int, m: str) -> None:

            pv = round(float(p) * 100.0)

            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=m, display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='SETTINGS', metadata={'pv': pv}))

        self._worker.kwargs["progress_cb"] = _corr_progress
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        source_stage = str(getattr(self, "_worker_role", "main") or "main")

        self._worker_role = "corridors"

        if hasattr(self, "_stepper"):
            self._stepper.set_step(6)

        if self.logger:
            rd = result.get("d_nm")
            rd_txt = f"{float(rd):.6f}" if isinstance(rd, (int, float)) and np.isfinite(float(rd)) else "n/a"
            rr = self._rmse_from_result_dict(result)
            rr_txt = f"{rr:.8f}" if np.isfinite(rr) else "n/a"
            self.logger.info(
                "[INDEX_SPLINE.CORRIDORS] launching deferred corridor worker | after_stage=%s | seed_d_nm=%s | seed_rmse_dict=%s",
                source_stage,
                rd_txt,
                rr_txt,
            )
            log_index_spline_d_trace(
                self.logger,
                "[INDEX_SPLINE.CORRIDORS] deferred corridor launch trace | seed=last_result",
                result.get("d_nm"),
                detail=f"after_stage={source_stage} rmse_dict={rr_txt}",
            )

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText("Corridors: calculation in progress...")

        self._worker.start()

        return True

    def _finish_curve_minimum_deep_worker_done(self, result: object) -> None:
        """End of deep polish from minimum RMSE(d): return to post-optimization state without auto-launch."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not isinstance(result, dict):
            self.lbl_status.setText("Deep polish (grid minimum): cancelled or failed.")
            if self.logger:
                self.logger.warning(
                    "GUI curve-min deep refit | finished without dict (type=%s)",
                    type(result).__name__,
                )
            QMessageBox.warning(
                self,
                "Polish profond",
                "L-BFGS-B polish from grid minimum did not return a valid result "
                "(interruption or numerical failure). The nominal was not modified.",
            )
            self._refresh_post_optimization_option_controls()
            return
        for _rk in list(result.keys()):
            if str(_rk).startswith("profile_d"):
                del result[_rk]

        # Restore corridor and profile_d keys from the preceding corridor worker output.
        # The deep polish (L-BFGS-B on d+nodes) does not recompute corridor envelopes;
        # they were computed by the corridor worker and are stored in _last_result.
        # Safety: _display_result_prefer_best_live (called below) will NOT strip them
        # because _best_live_result is None during deep polish (no live callbacks).
        prev = self._last_result if isinstance(self._last_result, dict) else {}
        _lam_result = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_prev = np.asarray(prev.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_ok = _lam_result.size > 0 and _lam_result.size == _lam_prev.size
        _n_restored = 0
        if _lam_ok:
            for _pk in list(prev.keys()):
                if (
                    str(_pk).startswith("corridor_")
                    or str(_pk).startswith("profile_d_")
                    or _pk == "profile_d_enabled"
                ) and _pk not in result:
                    val = prev[_pk]
                    result[_pk] = val.copy() if isinstance(val, np.ndarray) else val
                    _n_restored += 1
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | corridor data restoration from _last_result | "
                "lam_ok=%s (result=%d, prev=%d) | keys_restored=%d",
                "yes" if _lam_ok else "NO",
                int(_lam_result.size),
                int(_lam_prev.size),
                int(_n_restored),
            )

        self._last_worker_result = dict(result)
        self._corridor_rmse_manual_active = False
        self._corridor_rmse_manual_lo = float("nan")
        self._corridor_rmse_manual_hi = float("nan")

        display = self._display_result_prefer_best_live(result)
        self._last_result = display

        st = self._format_post_optimization_status(display, result)
        status_text = "After the grid minimum (deep polish) | " + st
        self.lbl_status.setText(status_text)

        if self.logger:
            rm_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )
            self.logger.info(
                "GUI curve-min deep refit | done | rmse=%.8f | d_nm=%.6f",
                rm_fin,
                float(display.get("d_nm", float("nan"))),
            )
            if np.isfinite(rm_fin):
                _log_index_spline_best_config(self.logger, display, rm_fin, title="[FIN polish min grille]")

        self._plot_result(display, plot_source="polish_grille_profond")
        self._refresh_data_table()

        _cont_after_deep = getattr(self, "_continue_corridor_auto_refine_after_deep", None)
        if callable(_cont_after_deep) and bool(_cont_after_deep()):
            return

        self._refresh_post_optimization_option_controls()
        self.lbl_status.setText(self._post_optimization_ready_status(status_text))
        self.export_excel(auto_export=True)

    def _finish_rmse_heal_worker_done(self, healed_list: object) -> None:
        """Merge healed points into the main result and refresh."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_corridor_grid_busy(False)

        if not isinstance(healed_list, list) or not healed_list:
            dr = self._last_result if isinstance(self._last_result, dict) else {}
            self._finish_corridor_rmse_d_grid_worker_done(dr)
            return

        # Get baseline from last result
        base = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        d_main = list(np.asarray(base.get("profile_d_values_nm", []), dtype=np.float64).ravel())
        r_main = list(np.asarray(base.get("profile_d_rmse_values", []), dtype=np.float64).ravel())
        s_main = list(base.get("profile_d_full_results", []))

        added = 0
        for item in healed_list:
            if not isinstance(item, dict):
                continue
            dv = item.get("profile_d_val_nm")
            if dv is None:
                continue

            # Replace or add
            match = -1
            for i, d_ex in enumerate(d_main):
                if np.abs(d_ex - dv) < 1e-4:
                    match = i
                    break

            rm = float(np.sqrt(max(float(item.get("mse", 0.0)), 0.0)))
            if match >= 0:
                # Only replace if better!
                if rm < r_main[match] - 1e-15:
                    r_main[match] = rm
                    s_main[match] = item
                    added += 1
            else:
                d_main.append(dv)
                r_main.append(rm)
                s_main.append(item)
                added += 1

        if self.logger:
            self.logger.info("GUI RMSE(d) Grid Healing | Integrated %d improved/healed points", added)

        base["profile_d_values_nm"] = np.array(d_main, dtype=np.float64)
        base["profile_d_rmse_values"] = np.array(r_main, dtype=np.float64)
        base["profile_d_full_results"] = s_main
        base["profile_d_manual_grid_coverage_complete"] = True  # We healed!

        # Finally trigger the standard finalization
        self._finish_corridor_rmse_d_grid_worker_done(base)

    def _set_corridor_grid_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_corridor_rmse_grid_calc"):
            self.btn_corridor_rmse_grid_calc.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_d_step_nm"):
            self.sp_corridor_grid_d_step_nm.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_n_points"):
            self.sp_corridor_grid_n_points.setEnabled(not busy)

        if hasattr(self, "sp_corridor_breakpoint_lookback"):
            self.sp_corridor_breakpoint_lookback.setEnabled(not busy)

        if hasattr(self, "chk_corridor_rmse_envelope_only"):
            self.chk_corridor_rmse_envelope_only.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_data"):
            self.btn_corridor_rmse_export_data.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_envelope_nk"):
            self.btn_corridor_rmse_export_envelope_nk.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "sp_corridor_partial_delta_nm"):
            self.sp_corridor_partial_delta_nm.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_partial_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_auto_smart_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "pb_corridor_rmse_grid"):
            if busy:
                self.pb_corridor_rmse_grid.start()
            else:
                self.pb_corridor_rmse_grid.stop(final_message="Idle")

    def _set_corridor_grid_progress_ui(
        self,
        *,
        done: int,
        total: int,
        base_done: int | None = None,
        base_total: int | None = None,
        extra_done: int | None = None,
        current_d_nm: float | None = None,
    ) -> None:

        tot = max(1, int(total))
        dn = int(max(0, min(done, tot)))
        frac = float(dn) / float(tot)

        # UX-8: Sub-progress injection
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                iteration=self._prog_ui_last,
                max_iter=10000,
                evals=0,
                phase=f"RMSE(d) Grid: {dn}/{tot}",
                extra_info="",
                sub_iteration=dn,
                max_sub_iter=tot,
            )

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.update(iteration=dn, max_iter=tot, phase=f"Scanning grid... {dn}/{tot}", progress_pct=round(100.0 * frac))

        t0 = float(getattr(self, "_corridor_rmse_grid_live_t0", float("nan")))

        eta_txt = ""

        if np.isfinite(t0) and dn > 0:
            dt = max(0.0, time.perf_counter() - t0)

            avg = dt / float(dn)

            eta = max(0.0, float(tot - dn) * avg)

            eta_txt = f" | avg {avg:.2f}s/pt | ETA {eta:.1f}s"

        d_txt = ""

        if current_d_nm is not None and np.isfinite(float(current_d_nm)):
            d_txt = f" | d={float(current_d_nm):.3f} nm"

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            if base_done is not None and base_total is not None:
                btot = max(1, int(base_total))
                bdn = int(max(0, min(int(base_done), btot)))
                xdn = int(max(0, int(extra_done or 0)))
                bfrac = 100.0 * float(bdn) / float(btot)
                self.lbl_corridor_rmse_grid_progress.setText(
                    f"Grid {bdn}/{btot} ({bfrac:.1f}%) + extra {xdn}{d_txt}{eta_txt}"
                )
            else:
                self.lbl_corridor_rmse_grid_progress.setText(f"Grid {dn}/{tot} ({100.0 * frac:.1f}%){d_txt}{eta_txt}")

    def _schedule_corridor_auto_refine(
        self,
        seed: dict,
        *,
        rerun_corridor: bool,
        origin: str,
    ) -> bool:
        """Schedule a strict refinement chain after corridor improvement."""
        if not isinstance(seed, dict):
            return False
        self._corridor_auto_refine_plan = {
            "stage": "deep",
            "rerun_corridor": bool(rerun_corridor),
            "origin": str(origin or "corridor"),
        }
        if self.logger:
            self.logger.info(
                "AUTO-REFINE [%s] scheduled | chain=deep-polish -> [conditional-corridor-rerun] | rerun_corridor=%s",
                str(origin or "corridor"),
                "yes" if bool(rerun_corridor) else "no",
            )
        if self._start_curve_minimum_deep_refit(dict(seed)):
            return True
        self._corridor_auto_refine_plan = None
        return False

    def _continue_corridor_auto_refine_after_deep(self) -> bool:
        """Continue refinement chain when deep polish is done."""
        plan = self._corridor_auto_refine_plan
        if not isinstance(plan, dict) or str(plan.get("stage", "")) != "deep":
            return False
        seed_now = self._manual_postprocess_seed_result()
        if not isinstance(seed_now, dict):
            self._corridor_auto_refine_plan = None
            return False
        if bool(plan.get("rerun_corridor", False)):
            if self.logger:
                self.logger.info(
                    "AUTO-REFINE [%s] deep-polish done | rerunning corridor profiling.",
                    plan.get("origin", "corridor"),
                )
            self._corridor_auto_refine_plan = None
            return bool(self._start_deferred_corridor_worker(dict(seed_now)))
        self._corridor_auto_refine_plan = None
        return False

    def _set_corridor_grid_completed_badge(self) -> None:

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.stop(final_message="Done")

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            base = str(self.lbl_corridor_rmse_grid_progress.text() or "").strip()

            if "Final fit updated" not in base:
                self.lbl_corridor_rmse_grid_progress.setText(f"{base} | Final fit updated")

    def _refresh_corridors_gui_state_labels(self) -> None:
        """Refresh corridor state badges for the post-optimization controls."""

        role = str(getattr(self, "_worker_role", "idle") or "idle")
        unlocked = isinstance(getattr(self, "_last_result", None), dict)

        if role == "rmse_grid":
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>calculation in progress...</b></span>'
        elif not unlocked:
            rich = (
                f'Corridors: <span style="color:{CertusTheme.TEXT_SUB};"><b>available after optimization</b></span>'
            )

        elif bool(
            self._last_result.get("profile_d_enabled", False)
            or self._last_result.get("profile_d_values_nm") is not None
        ):
            rich = f'Corridors: <span style="color:{CertusTheme.SUCCESS};"><b>already computed</b></span>'

        else:
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>ready to launch</b></span>'

        if hasattr(self, "lbl_corridors_run_state"):
            self.lbl_corridors_run_state.setText(rich)

        if hasattr(self, "lbl_corridors_state_adv"):
            self.lbl_corridors_state_adv.setText(rich)

        if hasattr(self, "lbl_corridors_tab_state"):
            self.lbl_corridors_tab_state.setText(rich)

    def _on_btn_corridor_clicked(self) -> None:

        seed = self._manual_postprocess_seed_result()
        if not isinstance(seed, dict):
            QMessageBox.information(
                self,
                "Corridors",
                "Run an optimization first to have a base result.",
            )
            return
        if self.logger:
            self.logger.info(
                "Corridors manual trigger | base=%s",
                "standard",
            )
        if not self._start_deferred_corridor_worker(seed):
            QMessageBox.warning(
                self,
                "Corridors",
                "Unable to start manual corridor calculation from the current result.",
            )

    def _on_corridor_chk_state_changed(self, *_args) -> None:

        self._refresh_corridors_gui_state_labels()

    @staticmethod
    def _is_rmse_d_grid_worker_finalize_dict(r: object) -> bool:
        """True if ``r`` is the final dict from the RMSE(d) grid worker (not a full solver result)."""
        if not isinstance(r, dict):
            return False
        st = str(r.get("profile_d_status", ""))
        return st in {"manual_grid", "manual_grid_empty"}

    def _merge_rmse_grid_promotion_into_nominal(self, promoted: dict, *, adoption_log_tag: str) -> None:
        """Merges a promoted dict (global-opt or grid minimum) into ``_last_result`` and refreshes the UI."""
        prev_nominal = dict(self._last_result) if isinstance(self._last_result, dict) else {}
        merged_nominal = dict(prev_nominal)
        merged_nominal.update(promoted)
        if merged_nominal.get("lam_nm") is None:
            lam_prev = prev_nominal.get("lam_nm")
            if lam_prev is not None:
                merged_nominal["lam_nm"] = np.asarray(lam_prev, dtype=np.float64).ravel().copy()
            elif self.df is not None and "lambda" in self.df.columns:
                merged_nominal["lam_nm"] = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid [%s] | promoted result missing lam_nm; fallback applied.",
                    adoption_log_tag,
                )
        self._last_result = merged_nominal
        if self.logger:
            rmse_after_replace = self._rmse_from_result_dict(self._last_result)
            self.logger.info(
                "GUI RMSE(d) regular grid [%s] | nominal merged | rmse_after_replace=%s | d_nm=%s",
                adoption_log_tag,
                (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a"),
                (
                    f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                    if np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                    else "n/a"
                ),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: adoption grille RMSE(d) → nominal _last_result",
                self._last_result.get("d_nm"),
                detail=(
                    "tag="
                    + str(adoption_log_tag)
                    + " rmse="
                    + (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a")
                ),
            )
        try:
            self._plot_result(self._last_result, plot_source="promotion_grille_rmse")
            self._refresh_data_table()
        except (ValueError, TypeError, AttributeError, RuntimeError):
            logger.debug("Failed to refresh plot after RMSE grid promotion", exc_info=True)

    def _on_corr_mode_changed(self, _idx: int = 0) -> None:
        """Show alpha vs Delta RMSE spinboxes according to corridor mode (LR hides both thresholds)."""

        if not hasattr(self, "cb_corr_mode"):
            return

        m = str(self.cb_corr_mode.currentData() or "abs_delta_adaptive")

        show_alpha = m == "alpha"

        show_delta = m in ("abs_delta", "abs_delta_adaptive")

        if hasattr(self, "sp_corr_alpha"):
            self.sp_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "lbl_corr_alpha"):
            self.lbl_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "lbl_corr_rmse_delta"):
            self.lbl_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setVisible(show_delta)

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

    def _start_curve_minimum_deep_refit(self, seed: dict) -> bool:
        """Launches ``quick_pwlnk_refit_result_dict`` (L-BFGS-B on d + nodes) from the grid minimum seed."""
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Optimization", "A calculation is already in progress.")
            return False
        cfg = self._last_run_cfg
        if cfg is None:
            cfg = self._build_opt_config(notify=False)
        if cfg is None:
            QMessageBox.warning(
                self,
                "Optimization",
                "No optimization configuration available (run a fit first).",
            )
            return False
        cfg = self._cfg_with_result_substrate(cfg, seed)
        polish = int(getattr(cfg, "polish_maxfun", 10000) or 10000)
        deep_maxfun = int(max(4000, min(24000, round(1.5 * float(polish)))))
        CertusIndexSplineApp._prepare_worker_restart(self)
        self._worker = GenericWorker(
            _worker_curve_minimum_deep_refit,
            cfg,
            dict(seed),
            self._stop_event,
            deep_maxfun=deep_maxfun,
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "curve_min_deep"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._prog_ui_last = 0
        self._prog_reset_bar()
        sd = float(seed.get("d_nm", float("nan")))
        self.lbl_status.setText(
            f"Grid minimum? Deep L-BFGS-B polish (d+nodes, maxfun={deep_maxfun}) from d={sd:.3f} nm"
        )
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | start | deep_maxfun=%d | seed_d_nm=%s",
                deep_maxfun,
                (f"{sd:.6f}" if np.isfinite(sd) else "n/a"),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: deep polish from the RMSE(d) grid minimum",
                seed.get("d_nm"),
                detail=f"deep_maxfun={deep_maxfun}",
            )
        self._worker.start()
        return True
