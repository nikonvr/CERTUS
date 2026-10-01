"""CERTUS-INDEX-SPLINE corridors - the worker mixin: what the window does when a corridor worker is done (moved out of certus_index_spline_corridors.py, S5.3)."""

from __future__ import annotations

import time
from typing import Any
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox

from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_core import log_index_spline_d_trace, _log_index_spline_best_config
from certus.utils.certus_index_utils import (
    log_structured_json_event,
    _safe_int_from_mapping,
    _filter_rmse_peaks_iteratively,
)
from certus.spline.certus_corridor_utils import quick_pwlnk_refit_result_dict
from certus.utils.certus_skeleton import uninstall_skeleton
from certus.spline.certus_index_spline_corridor_ui import GenericWorker, ManualSigmaKnotDialog

# Mixins moved out of this class (S5.3): the methods live there, the names stay importable from here.
from certus.spline.certus_index_spline_corridor_tab import _CorridorTabMixin


class _CorridorWorkerMixin(_CorridorTabMixin):
    """Mixin containing the corridor worker callbacks; the plot tab is in `_CorridorTabMixin`, which this class inherits."""

    def _finish_corridor_rmse_d_grid_worker_done(self, result: object) -> None:
        """End of RMSE(d) grid worker: merge profile_d*, refresh UI, adopt the best global result. Not for solver dicts."""
        self._worker_role = "idle"

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._set_corridor_grid_busy(False)

        self._corridor_rmse_grid_live_t0 = float("nan")
        self._corridor_rmse_live_last_plot_ts = float("nan")

        if not isinstance(result, dict):
            self.lbl_status.setText("RMSE(d) grid: canceled or invalid result.")

            if self.logger:
                self.logger.warning("RMSE(d) grid worker finished without dict result.")

            return

        if self.logger:
            d_dbg = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            r_dbg = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            n_nan_d = int(np.sum(~np.isfinite(d_dbg))) if d_dbg.size else 0
            n_nan_r = int(np.sum(~np.isfinite(r_dbg))) if r_dbg.size else 0
            cov_req = _safe_int_from_mapping(result, "profile_d_manual_grid_requested_base_points", -1)
            cov_ret = _safe_int_from_mapping(result, "profile_d_manual_grid_returned_base_points", -1)
            cov_miss = _safe_int_from_mapping(result, "profile_d_manual_grid_missing_after_emergency", -1)
            cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
            self.logger.info(
                "GUI RMSE(d) regular grid done [order A:result-received] | points=%d | nan(d)=%d | nan(rmse)=%d | coverage requested/returned/missing=%d/%d/%d | complete=%s",
                int(d_dbg.size),
                int(n_nan_d),
                int(n_nan_r),
                int(cov_req),
                int(cov_ret),
                int(cov_miss),
                "yes" if cov_ok else "no",
            )
            if d_dbg.size and r_dbg.size == d_dbg.size:
                fg_c = np.isfinite(d_dbg) & np.isfinite(r_dbg)
                if np.any(fg_c):
                    df = d_dbg[fg_c]
                    rf = r_dbg[fg_c]
                    j_min = int(np.argmin(rf))
                    j_max = int(np.argmax(rf))
                    d0_seed = result.get("profile_d_manual_grid_d0_seed_nm")
                    d_nom_pack = result.get("profile_d_manual_grid_nominal_pack_d_nm")
                    d0_txt = f"{float(d0_seed):.6f}" if d0_seed is not None and np.isfinite(float(d0_seed)) else "n/a"
                    d_nom_txt = (
                        f"{float(d_nom_pack):.6f}"
                        if d_nom_pack is not None and np.isfinite(float(d_nom_pack))
                        else "n/a"
                    )
                    self.logger.info(
                        "GUI RMSE(d) regular grid done [order A-ext:curve-on-receive] | d_nm[min,max]=[%.6f,%.6f] | "
                        "rmse[min,max]=[%.8f,%.8f] | curve_min(d,rmse)=(%.6f,%.8f) | curve_max(d,rmse)=(%.6f,%.8f) | "
                        "visit_first_d_nm=%s | nominal_pack_d_nm=%s",
                        float(np.min(df)),
                        float(np.max(df)),
                        float(np.min(rf)),
                        float(np.max(rf)),
                        float(df[j_min]),
                        float(rf[j_min]),
                        float(df[j_max]),
                        float(rf[j_max]),
                        d0_txt,
                        d_nom_txt,
                    )

        # --- GAP HEALING LOGIC (UX) ---
        # 1. Identify what we have and remove peaks for baseline
        d_raw = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_raw = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        snapshots = result.get("profile_d_full_results", [])

        # Filter peaks iteratively to find the "trustworthy" monotonic baseline
        order = np.argsort(d_raw)
        df, rf = d_raw[order], r_raw[order]
        snap_f = [snapshots[i] for i in order] if len(snapshots) == len(d_raw) else []

        d_mono, r_mono = _filter_rmse_peaks_iteratively(df, rf)
        # Find indices of monotonic points in the sorted list
        mono_indices = []
        if len(snap_f) > 0:
            for dm in d_mono:
                idx = np.where(np.abs(df - dm) < 1e-9)[0]
                if idx.size > 0:
                    mono_indices.append(idx[0])

        # 2. Check for GAPS relative to requested grid
        requested = getattr(self, "_corridor_rmse_requested_grid", np.array([]))
        tasks = []
        if requested.size > 0 and len(snap_f) > 0 and len(mono_indices) > 0:
            for d_req in requested:
                # Is it missing?
                if not np.any(np.abs(d_mono - d_req) < 1e-4):
                    # FIND BEST NEIGHBOR in monotonic set
                    dist = np.abs(d_mono - d_req)
                    # We look for immediate neighbors (left/right)
                    # but actually any nearby monotonic point is a good seed.
                    # As requested: "best among left/right neighbors"
                    side_indices = np.where(dist < 2.1 * (requested[1] - requested[0] if requested.size > 1 else 1.0))[
                        0
                    ]
                    if side_indices.size > 0:
                        # Best among those nearby
                        best_side_sub_idx = side_indices[np.argmin(r_mono[side_indices])]
                        global_idx_in_snap_f = mono_indices[best_side_sub_idx]
                        seed_snap = snap_f[global_idx_in_snap_f]
                        tasks.append((float(d_req), seed_snap))

        if tasks and str(getattr(self, "_worker_role", "") or "") != "rmse_heal":
            if self.logger:
                self.logger.info("GUI RMSE(d) Grid Healing | Launching healer for %d gaps", len(tasks))
            heal_tasks = list(tasks)
            QTimer.singleShot(0, lambda t=heal_tasks: self._launch_corridor_rmse_gap_heal(t))
            return

        # Continuing finalization...
        upd = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        for k, v in result.items():
            if str(k).startswith("profile_d") or str(k).startswith("corridor_"):
                upd[k] = v

        self._last_result = upd

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        try:
            self._plot_corridor_rmse_tab(upd)

        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Corridor RMSE tab refresh after manual grid failed", exc_info=True)

        n_ok = int(np.asarray(upd.get("profile_d_values_nm", [])).size)

        n_tot = int(result.get("profile_d_manual_grid_total_points", n_ok))
        n_base_done = int(result.get("profile_d_manual_grid_base_done_points", min(n_ok, n_tot)) or min(n_ok, n_tot))
        n_extra_done = int(
            result.get("profile_d_manual_grid_extra_done_points", max(0, n_ok - n_tot)) or max(0, n_ok - n_tot)
        )

        self._set_corridor_grid_progress_ui(
            done=n_ok,
            total=n_tot,
            base_done=n_base_done,
            base_total=n_tot,
            extra_done=n_extra_done,
        )

        self._set_corridor_grid_completed_badge()

        n_bp = int(result.get("profile_d_manual_grid_breakpoint_count", 0))

        n_extra = int(result.get("profile_d_manual_grid_extra_points", 0))

        n_glob_runs = int(result.get("profile_d_manual_grid_global_opt_runs", 0))

        n_glob_imp = int(result.get("profile_d_manual_grid_global_opt_improved", 0))

        rmse_glob_best = float(result.get("profile_d_manual_grid_best_global_rmse", float("nan")))

        t_ms = float(result.get("profile_d_manual_grid_elapsed_ms", float("nan")))

        self.lbl_status.setText(
            f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | "
            f"global_opt={n_glob_runs}/{n_glob_imp} | {t_ms:.0f} ms"
            if np.isfinite(t_ms)
            else f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | global_opt={n_glob_runs}/{n_glob_imp}"
        )

        if self.logger:
            self.logger.info(
                "GUI RMSE(d) regular grid done | n_points=%d | breakpoints=%d | extra_points=%d | global_opt_runs=%d | global_opt_improved=%d | best_global_rmse=%s | elapsed_ms=%s",
                n_ok,
                int(n_bp),
                int(n_extra),
                int(n_glob_runs),
                int(n_glob_imp),
                f"{rmse_glob_best:.8f}" if np.isfinite(rmse_glob_best) else "n/a",
                f"{t_ms:.1f}" if np.isfinite(t_ms) else "n/a",
            )

        best_global_result = result.get("profile_d_manual_grid_best_global_result")
        curve_minimum_result = result.get("profile_d_manual_grid_curve_minimum_result")
        curve_beats = bool(result.get("profile_d_manual_grid_curve_beats_nominal", False))
        grid_cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
        delta_curve = float(result.get("profile_d_manual_grid_curve_vs_nominal_delta_rmse", float("nan")))

        rmse_best_global = (
            self._rmse_from_result_dict(best_global_result) if isinstance(best_global_result, dict) else float("nan")
        )
        rmse_curve = (
            self._rmse_from_result_dict(curve_minimum_result)
            if isinstance(curve_minimum_result, dict)
            else float("nan")
        )

        cand_global_ok = bool(
            int(n_glob_imp) > 0 and isinstance(best_global_result, dict) and np.isfinite(rmse_best_global)
        )
        cand_curve_ok = bool(curve_beats and isinstance(curve_minimum_result, dict) and np.isfinite(rmse_curve))

        if int(n_glob_imp) > 0 and (not cand_global_ok) and self.logger:
            self.logger.warning(
                "GUI RMSE(d) regular grid | global_opt_improved=%d but best_global_result missing/invalid rmse.",
                int(n_glob_imp),
            )

        chosen_seed: dict[str, Any] | None = None
        chosen_origin = ""
        chosen_log_tag = ""
        chosen_status = ""
        if cand_global_ok and cand_curve_ok:
            if rmse_curve < rmse_best_global:
                chosen_seed = dict(curve_minimum_result)
                chosen_origin = "corridor-profile-curve-minimum"
                chosen_log_tag = "order C2:corridor-curve-min-promoted-over-global-opt"
                chosen_status = "[INDEX_SPLINE.CORRIDORS] curve minimum promoted | auto-refine in progress"
            else:
                chosen_seed = dict(best_global_result)
                chosen_origin = "corridor-global-optimization-best"
                chosen_log_tag = "order C:corridor-global-opt-best-promoted"
                chosen_status = "[INDEX_SPLINE.CORRIDORS] new corridor minimum found via global optimization | auto-refine in progress"
        elif cand_global_ok:
            chosen_seed = dict(best_global_result)
            chosen_origin = "corridor-global-optimization-best"
            chosen_log_tag = "order C:corridor-global-opt-best-promoted"
            chosen_status = "[INDEX_SPLINE.CORRIDORS] new corridor minimum found via global optimization | auto-refine in progress"
        elif cand_curve_ok:
            chosen_seed = dict(curve_minimum_result)
            chosen_origin = "corridor-profile-curve-minimum"
            chosen_log_tag = "order B2:corridor-curve-min-promoted"
            chosen_status = "[INDEX_SPLINE.CORRIDORS] curve minimum promoted as nominal | auto-refine in progress"

        if isinstance(chosen_seed, dict):
            if not grid_cov_ok:
                if self.logger:
                    self.logger.error(
                        "[INDEX_SPLINE.CORRIDORS] adoption candidate rejected | reason=base-grid coverage incomplete"
                    )
                chosen_seed = None
            if self.logger:
                rmse_prev_upd = self._rmse_from_result_dict(upd)
                d_sel = chosen_seed.get("d_nm") if isinstance(chosen_seed, dict) else None
                d_sel_txt = (
                    f"{float(d_sel):.6f}" if isinstance(d_sel, (int, float)) and np.isfinite(float(d_sel)) else "n/a"
                )
                self.logger.info(
                    "[INDEX_SPLINE.CORRIDORS] adoption decision | candidate_origin=%s | d_selected_nm=%s | "
                    "rmse_before_adoption=%s | rmse_global_opt=%s | rmse_curve=%s | delta_curve_vs_pre_adoption=%s | "
                    "grid_coverage_complete=%s",
                    chosen_origin,
                    d_sel_txt,
                    (f"{rmse_prev_upd:.8f}" if np.isfinite(rmse_prev_upd) else "n/a"),
                    (f"{rmse_best_global:.8f}" if np.isfinite(rmse_best_global) else "n/a"),
                    (f"{rmse_curve:.8f}" if np.isfinite(rmse_curve) else "n/a"),
                    (f"{delta_curve:.3e}" if np.isfinite(delta_curve) else "n/a"),
                    "yes" if grid_cov_ok else "no",
                )

            if isinstance(chosen_seed, dict):
                self._merge_rmse_grid_promotion_into_nominal(
                    dict(chosen_seed),
                    adoption_log_tag=chosen_log_tag,
                )
                if isinstance(self._last_result, dict):
                    self._last_worker_result = dict(self._last_result)

                strict_snapshot = dict(chosen_seed)
                if strict_snapshot.get("x_seg_spline_sigma") is None and strict_snapshot.get("x") is not None:
                    strict_snapshot["x_seg_spline_sigma"] = (
                        np.asarray(strict_snapshot.get("x"), dtype=np.float64).ravel().copy()
                    )
                if strict_snapshot.get("x") is None and strict_snapshot.get("x_seg_spline_sigma") is not None:
                    strict_snapshot["x"] = (
                        np.asarray(strict_snapshot.get("x_seg_spline_sigma"), dtype=np.float64).ravel().copy()
                    )
                chosen_seed["gui_solver_snapshot_for_corridors"] = dict(strict_snapshot)

                self.lbl_status.setText(chosen_status)
                if self._schedule_corridor_auto_refine(
                    chosen_seed,
                    rerun_corridor=True,
                    origin=chosen_origin,
                ):
                    return
                if self.logger:
                    self.logger.warning(
                        "[INDEX_SPLINE.CORRIDORS] auto-refine chain failed to start | chosen_origin=%s",
                        chosen_origin,
                    )

        if self.logger:
            dv = np.asarray(upd.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            rv = np.asarray(upd.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            if dv.size and rv.size == dv.size:
                fg_z = np.isfinite(dv) & np.isfinite(rv)
                if np.any(fg_z):
                    dz = dv[fg_z]
                    rz = rv[fg_z]
                    jz = int(np.argmin(rz))
                    self.logger.info(
                        "[INDEX_SPLINE.CORRIDORS] post-merge curve | points=%d | rmse_min=%.8f | d=%.6f nm | "
                        "nominal_dict_d_nm=%s | nominal_dict_rmse=%s",
                        int(dz.size),
                        float(rz[jz]),
                        float(dz[jz]),
                        (
                            f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                            else "n/a"
                        ),
                        (
                            f"{self._rmse_from_result_dict(self._last_result):.8f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(self._rmse_from_result_dict(self._last_result))
                            else "n/a"
                        ),
                    )

        return

    def _on_worker_done(self, result: object) -> None:

        role = str(getattr(self, "_worker_role", "main") or "main")
        manual_pipeline_roles = (
            "manual_sigma_insert",
            "manual_autoshift",
            "manual_auto_add_one",
            "manual_auto_clean",
            "manual_repartition_log",
            "manual_repartition_sigma",
        )
        worker_obj = getattr(self, "_worker", None)
        worker_func = getattr(worker_obj, "func", None)
        worker_name = str(getattr(worker_func, "__name__", "?") or "?")
        manual_dlg = getattr(self, "_manual_knots_dialog", None)

        uninstall_skeleton(self.tabs_main)
        if role == "curve_min_deep":
            self._finish_curve_minimum_deep_worker_done(result)

            return

        if role == "rmse_heal":
            self._finish_rmse_heal_worker_done(result)
            return

        grid_fin = self._is_rmse_d_grid_worker_finalize_dict(result)

        if grid_fin or role == "rmse_grid":
            if grid_fin and role != "rmse_grid" and self.logger:
                op_id = result.get("op_id") if isinstance(result, dict) else None

                self.logger.warning(
                    "[INDEX_SPLINE.CORRIDORS] worker_done grid result | profile_d_status=%s | worker_role=%r | worker=%s | op_id=%s",
                    (result.get("profile_d_status") if isinstance(result, dict) else None),
                    role,
                    worker_name,
                    str(op_id) if op_id is not None else "n/a",
                )

            self._finish_corridor_rmse_d_grid_worker_done(result)
            return

        if not isinstance(result, dict):
            if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
                manual_dlg.set_runtime_busy(False)
                manual_dlg.append_runtime_log("Re-optimization finished without usable result.")

            self.lbl_status.setText("Canceled or no result (dict)")
            self._worker_role = "idle"
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

            if self.logger:
                if result is None:
                    self.logger.warning(
                        "[INDEX_SPLINE.GUI] worker finished without a result dictionary"
                        "Common causes: Stop button during calculation, thread closure/interruption, "
                        "or silent worker-side exception. Graphs are not updated since this signal."
                    )

                else:
                    self.logger.warning(
                        "[INDEX_SPLINE.GUI] worker returned %s instead of a result dictionary - result ignored",
                        type(result).__name__,
                    )

            self._refresh_post_optimization_option_controls()
            return

        if role not in ("rmse_grid", "corridors"):
            self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_best_idx = -1
            self._corridor_rmse_center_nm = float("nan")
            self._corridor_rmse_robust_lo = float("nan")
            self._corridor_rmse_robust_hi = float("nan")
            self._corridor_rmse_robust_ok = False
            if hasattr(self, "plot_corridor_rmse_d"):
                self.plot_corridor_rmse_d.clear()
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        if self.logger:
            op_id = result.get("op_id")

            role_ctx = role if worker_name == "?" else f"{role}|worker={worker_name}"

            op_id_ctx = str(op_id) if op_id is not None else "n/a"

            _wm = result.get("pipeline_best_rmse_watermark")

            _wms = result.get("pipeline_best_rmse_stage")

            _wm_hint = ""

            if _wm is not None and np.isfinite(float(_wm)):
                _wm_hint = f" | pipeline watermark (best RMSE seen during run): {_wm:.6f} (@ {_wms!s})"

            self.logger.info(
                "[INDEX_SPLINE.GUI] result dictionary received | rmse_current_nk=%.6f | "
                "d = %.4f nm | role = %s | worker = %s | op_id = %s%s",
                float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                float(result.get("d_nm", float("nan"))),
                role,
                worker_name,
                op_id_ctx,
                _wm_hint,
            )

            log_index_spline_d_trace(
                self.logger,
                f"[INDEX_SPLINE.GUI] worker result received | role={role_ctx} | op_id={op_id_ctx}",
                result.get("d_nm"),
                detail=("worker=" + worker_name),
            )

            split_mesh = self._result_uses_split_mesh(result)

            self.logger.info(
                "[INDEX_SPLINE.GUI] worker details | mse=%.6e | split=%s | continuous=%s | adaptive=%s",
                float(result.get("mse", float("nan"))),
                bool(split_mesh),
                bool(result.get("continuous_model")),
                bool(result.get("adaptive_mesh")),
            )

            log_structured_json_event(
                self.logger,
                "AUTO_BEST_JSON",
                "worker_done",
                role=role,
                worker=worker_name,
                op_id=op_id_ctx,
                mse=float(result.get("mse", float("nan"))),
                rmse=float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                rmse_convention="sqrt(max(mse,0))",
                d_nm=float(result.get("d_nm", float("nan"))),
                split=bool(split_mesh),
                continuous=bool(result.get("continuous_model")),
                adaptive=bool(result.get("adaptive_mesh")),
            )

        # Auto-Best: trigger a 2nd local pass (free split n/logk knots) after the 1st warm pass.

        if self._auto_best_two_stage_refine:
            cfg2 = self._build_opt_config()

            if cfg2 is not None:
                self._auto_best_second_stage_pending = {
                    "seed": dict(result),
                    "cfg": cfg2,
                }

                self._auto_best_two_stage_refine = False

                self.log(
                    "Auto-Best: launching local pass 2 (separated sigma knots for n and ln k, then polish).",
                    "INFO",
                )

                self.lbl_status.setText("Auto-Best pass 2: preparing...")

                QTimer.singleShot(0, self._start_auto_best_second_stage)

                return

            self._auto_best_two_stage_refine = False

        self._last_worker_result = dict(result)

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        display = result if role == "corridors" else self._display_result_prefer_best_live(result)

        self._last_result = display

        st = self._format_post_optimization_status(display, result)

        if display.get("adaptive_mesh"):
            st = "Adaptive mesh | " + st

        if display.get("auto_knot_stages") and "sigma_knots" in display:
            kfin = int(np.asarray(display["sigma_knots"], dtype=np.float64).size)

            kbest = display.get("auto_knots_K_best")

            if kbest is not None and int(kbest) != kfin:
                st = f"K retained={int(kbest)} (last K={kfin}) stages={len(display['auto_knot_stages'])} | " + st

            else:
                st = f"K={kfin} stages={len(display['auto_knot_stages'])} | " + st

        if display.get("gui_display_from_best_live"):
            st = "Meilleur RMSE (live) | " + st

        self.lbl_status.setText(st)

        if self.logger:
            self.logger.info("End optimization: %s", st)

            rmse_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )

            _log_index_spline_best_config(self.logger, display, rmse_fin, title="[END OPTIM  display / export]")

        # === SAFE-GUARD: Wrap entire final completion path to prevent silent app termination ===
        try:
            plot_source = f"fin_worker:{role}"
            if worker_name != "?":
                plot_source = f"{plot_source}|{worker_name}"
            self._plot_result(display, plot_source=plot_source)
        except Exception as e:
            import traceback

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _plot_result failed: %s\n%s", type(e).__name__, __import__('traceback').format_exc()
                )
            else:
                print(f"[CRASH GUARD] _plot_result failed: {e}", file=__import__("sys").stderr)

        try:
            self._refresh_data_table()
        except Exception as e:

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_data_table failed: %s\n%s",
                    type(e).__name__,
                    __import__('traceback').format_exc(),
                )

        if role in manual_pipeline_roles and self.logger:
            self.logger.info(
                "PIPELINE [05b/09] Manual pipeline stage completed (%s); proceeding to corridors only afterwards if requested.",
                role,
            )
        if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
            try:
                manual_dlg.set_runtime_busy(False)
                d_fin, rmse_fin = self._runtime_metrics_from_result_dict(display)
                rmse_txt = f"{float(rmse_fin):.6f}" if np.isfinite(rmse_fin) else "n/a"
                self._refresh_manual_dialog_preview(manual_dlg, display)
                # Important: for manual-local flows, keep the exact worker output mesh
                # (result) instead of the display snapshot (which may be overridden by
                # a stale best-live candidate at another K).
                sigma_before = np.asarray(getattr(manual_dlg, "_base_sigma_knots", []), dtype=np.float64).ravel()
                sigma_requested = manual_dlg.selected_sigma_knots()
                sigma_fin = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                if sigma_fin.size == 0:
                    sigma_fin = np.asarray(display.get("sigma_knots", []), dtype=np.float64).ravel()
                requested_summary = self._summarize_manual_mesh_change(sigma_before, sigma_requested)
                applied_summary = self._summarize_manual_mesh_change(sigma_before, sigma_fin)
                manual_dlg.append_runtime_log(
                    self._manual_mesh_change_log_line("Requested mesh", requested_summary)
                )
                same_requested_and_applied = requested_summary["after_sigma_knots"].size == applied_summary[
                    "after_sigma_knots"
                ].size and np.allclose(
                    requested_summary["after_sigma_knots"],
                    applied_summary["after_sigma_knots"],
                    rtol=1e-10,
                    atol=1e-12,
                )
                if not same_requested_and_applied:
                    manual_dlg.append_runtime_log(
                        "Worker returned a different mesh than requested; keeping the applied mesh below."
                    )
                manual_dlg.append_runtime_log(
                    self._manual_mesh_change_log_line("Applied mesh", applied_summary)
                )
                if sigma_fin.size:
                    manual_dlg.adopt_sigma_knots(sigma_fin)
                opt_delta_ns = result.get("substrate_n_offset")
                if opt_delta_ns is None:
                    opt_delta_ns = display.get("substrate_n_offset")
                if opt_delta_ns is not None:
                    manual_dlg.adopt_delta_ns(float(opt_delta_ns))
                manual_dlg.set_runtime_progress(100.0, "Re-optimisation terminee")
                manual_dlg.set_runtime_metrics(d_fin, rmse_fin)
                manual_dlg.append_runtime_log(f"Re-optimisation terminee | RMSE={rmse_txt}")
                if self.logger:
                    self.logger.info(
                        "[INDEX_SPLINE.GUI] manual pipeline applied mesh | role=%s | %s",
                        role,
                        self._manual_mesh_change_log_line("applied", applied_summary),
                    )
                # Stores the absolute best config for the 'Recall best RMSE' button.
                # We use `result` (raw from worker) and not `display`: `display` may be
                # the best live snapshot (e.g. K=14 initial during auto_clean), which
                # would point "Recall best" to an erroneous intermediate state.
                raw_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                raw_rmse = self._rmse_from_result_dict(result)
                if raw_sk.size and np.isfinite(raw_rmse):
                    manual_dlg.update_best_config(result, raw_sk)
            except Exception as e:

                if self.logger:
                    self.logger.exception(
                        "INDEX_SPLINE [CRASH GUARD] manual dialog finalization failed: %s\n%s",
                        type(e).__name__,
                        __import__('traceback').format_exc(),
                    )

        # --- Manual extra-knot dialog (must occur before any deferred corridors) ---
        if (
            role not in ((*manual_pipeline_roles, "corridors"))
            and self._can_offer_manual_extra_knots(result)
            and getattr(self, "_corridor_auto_refine_plan", None) is None
        ):
            if self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot stage available after optimization; this stage runs before deferred corridors."
                )

            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                open_manual_fn = getattr(self, "_open_manual_extra_knots_dialog", None)
                if callable(open_manual_fn):
                    open_manual_fn(result)
                    if self.logger:
                        self.logger.info(
                            "PIPELINE [05b/09] Manual extra-knot stage opened in keep-open mode; user closes dialog explicitly."
                        )
                else:
                    # Fallback for test doubles/legacy call paths without non-blocking dialog helper.
                    lambdas = self._prompt_manual_extra_knots(result)
                    if lambdas:
                        if self.logger:
                            self.logger.info(
                                "Manual extra-knot stage accepted; deferred corridors are postponed until manual insertion completes."
                            )
                        self._start_manual_sigma_insert_worker(result, lambdas)
                        return
            elif self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot dialog already open; keeping current session active."
                )

        self._worker_role = "idle"

        try:
            self._refresh_post_optimization_option_controls()
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_post_optimization_option_controls failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )

        self.lbl_status.setText(self._post_optimization_ready_status(st))

        try:
            self.export_excel(auto_export=True)
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] export_excel(auto_export=True) failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )
            else:
                print(f"[CRASH GUARD] export_excel failed: {e}", file=__import__("sys").stderr)


    def _start_corridor_rmse_grid_recalc(self) -> None:
        """Recalculate RMSE(d) on a regular grid (refit n,L with fixed d) in a thread."""

        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.info("GUI RMSE(d) regular grid | request ignored: worker already running")

            QMessageBox.information(self, "Calculate", "A worker is already running (wait or Stop).")

            return

        cfg = self._last_run_cfg

        if cfg is None:
            cfg = self._build_opt_config(notify=False)

        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no optimization configuration available")

            QMessageBox.warning(self, "Calculate", "No optimization configuration available (run a fit first).")

            return

        base = self._corridor_profile_source_result()

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Fallback: some display snapshots (best-live merge / stripped payloads)
            # can miss solver mesh fields needed by RMSE(d) fixed-d refits.
            base_fallback_src = ""
            for src_name, cand in (
                ("corridor_rmse_base_snapshot", self._corridor_rmse_base_snapshot),
                ("last_worker_result", self._last_worker_result),
                ("last_result", self._last_result),
                ("best_live_result", self._best_live_result),
            ):
                if isinstance(cand, dict) and cand.get("sigma_knots") is not None:
                    base = dict(cand)
                    base_fallback_src = str(src_name)
                    break
            if base_fallback_src and self.logger:
                self.logger.info(
                    "GUI RMSE(d) regular grid | base snapshot fallback selected from %s",
                    base_fallback_src,
                )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Last chance: rebuild a valid solver snapshot on canonical mesh, silently.
            base_seed: dict[str, Any] = {}
            for cand in (self._last_worker_result, self._last_result, self._best_live_result):
                if isinstance(cand, dict):
                    base_seed = dict(cand)
                    break
            try:
                maxfun_recover = int(max(300, min(4000, int(getattr(cfg, "polish_maxfun", 1200) or 1200))))
                rebuilt = quick_pwlnk_refit_result_dict(cfg, base_seed, maxfun=maxfun_recover)
            except (TypeError, ValueError, RuntimeError, AttributeError):
                rebuilt = None
            if isinstance(rebuilt, dict) and rebuilt.get("sigma_knots") is not None:
                base = dict(rebuilt)
                self._corridor_rmse_base_snapshot = dict(rebuilt)
                if self.logger:
                    self.logger.info(
                        "GUI RMSE(d) regular grid | base snapshot auto-rebuilt (maxfun=%d, sigma_knots=%d)",
                        int(maxfun_recover),
                        int(np.asarray(base.get("sigma_knots", []), dtype=np.float64).size),
                    )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no corridor profile base in current result")

            # Keep the UX non-blocking: no popup for missing base, only status feedback.
            self.lbl_status.setText(
                "RMSE(d): base corridor unavailable (auto reconstruction impossible). Run a fit, then retry."
            )

            return

        self._corridor_rmse_base_snapshot = dict(base)

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size > 0 and r_s.size == d_s.size and 0 <= i_best < int(d_s.size):
            d_center = float(d_s[i_best])

        else:
            d_center = float(base.get("d_nm", float("nan")))

        if not np.isfinite(d_center):
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: cannot determine center d*")

            QMessageBox.warning(self, "Calculate", "Cannot determine center thickness d* for the grid.")

            return

        n_pts = int(self.sp_corridor_grid_n_points.value()) if hasattr(self, "sp_corridor_grid_n_points") else 11

        step = float(self.sp_corridor_grid_d_step_nm.value()) if hasattr(self, "sp_corridor_grid_d_step_nm") else 0.5

        break_lookback = (
            int(self.sp_corridor_breakpoint_lookback.value()) if hasattr(self, "sp_corridor_breakpoint_lookback") else 5
        )

        if n_pts < 2 or (not np.isfinite(step)) or step <= 0:
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid | aborted: invalid grid params n_pts=%s step=%s",
                    str(n_pts),
                    str(step),
                )

            QMessageBox.warning(self, "Calculate", "Invalid grid: need ?2 points and Deltad > 0.")

            return

        offs = (np.arange(n_pts, dtype=np.float64) - 0.5 * float(n_pts - 1)) * step

        d_grid = d_center + offs
        self._corridor_rmse_requested_grid = d_grid.copy()

        d_lo_grid = float(np.min(d_grid)) if d_grid.size else float("nan")

        d_hi_grid = float(np.max(d_grid)) if d_grid.size else float("nan")

        self.__class__._prepare_worker_restart(self)

        snap = dict(base)

        from certus.ui.certus_index_spline_ui import _worker_corridor_rmse_regular_grid
        self._worker = GenericWorker(
            _worker_corridor_rmse_regular_grid,
            cfg,
            snap,
            d_grid,
            self._stop_event,
            int(max(2, break_lookback)),
        )

        def _grid_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=m, display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='CORRIDORS', metadata={'pv': pv}))

        self._worker.kwargs["progress_cb"] = _grid_progress

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.kwargs["visit_anchor_nm"] = float(d_center)

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self._worker_role = "rmse_grid"

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._set_corridor_grid_busy(True)

        self._corridor_rmse_grid_live_t0 = float(time.perf_counter())
        self._corridor_rmse_live_last_plot_ts = float("nan")

        self._set_corridor_grid_progress_ui(done=0, total=int(max(1, d_grid.size)))

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText(
            f"RMSE(d) grid: {n_pts} points, Deltad={step:g} nm, break-lookback={int(max(2, break_lookback))} "
            f"(center d*?{d_center:.3f} nm)..."
        )

        if self.logger:
            bd_raw = base.get("d_nm")
            bd_txt = (
                f"{float(bd_raw):.6f}" if isinstance(bd_raw, (int, float)) and np.isfinite(float(bd_raw)) else "n/a"
            )
            br = self._rmse_from_result_dict(base)
            br_txt = f"{br:.8f}" if np.isfinite(br) else "n/a"
            sbv = base.get("spectral_rmse_best_value")
            sbv_txt = f"{float(sbv):.8f}" if sbv is not None and np.isfinite(float(sbv)) else "n/a"
            if (
                d_s.size > 0
                and r_s.size == d_s.size
                and 0 <= i_best < int(d_s.size)
                and np.isfinite(float(r_s[i_best]))
            ):
                center_src = f"rmse_tab_best_idx={i_best}"
                tab_d = f"{float(d_s[i_best]):.6f}"
                tab_r = f"{float(r_s[i_best]):.8f}"
            else:
                center_src = "base_dict_d_nm"
                tab_d = "n/a"
                tab_r = "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | start | center=%.6f nm | n_pts=%d | step=%.6f nm | d_range=[%.6f, %.6f] nm | "
                "base_d_nm=%s | base_rmse_dict=%s | spectral_rmse_best_value=%s | center_src=%s | tab(d,rmse)=(%s,%s)",
                float(d_center),
                int(n_pts),
                float(step),
                float(d_lo_grid),
                float(d_hi_grid),
                bd_txt,
                br_txt,
                sbv_txt,
                center_src,
                tab_d,
                tab_r,
            )

        # Auto-select the Corridor RMSE(d) tab to show live updates
        if hasattr(self, "_idx_tab_corridor_rmse") and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor_rmse))

        self._worker.start()
