import time
import traceback
import logging
from pathlib import Path
from threading import Event
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import numpy as np
import pandas as pd
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    HC_EV_NM,
    N_MIN_LIMIT,
    PI,
    SMALL_EPSILON,
    T_SUB_MIN_R_NORM,
    T_SUB_MIN_T_NORM,
    __version__,
    get_resource_path,
    get_safe_worker_count,
)
from certus.core.certus_lazy_imports import lazy_scipy
scipy = lazy_scipy()
from certus.core.certus_index_core import TLU_SOFT_EDGE_MARGIN, TLU_PRIOR_TRANSPARENT_N_MIN_SOFT
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
from certus_physics import (
    PGlobalConfig,
    TLUParameters,
    calculate_single_interface_R,
    calculate_reflection_array,
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    clip_to_bounds,
    compute_mse_vectorized,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_n_frosted_glass_array,
    SplineBasisCache,
)
from certus.utils.certus_index_utils import (
    sellmeier_2poles_eval_nj,
    k_law_8p_eval,
    _deduce_knots_from_k8p,
    _ensure_strictly_increasing,
    _merge_closest_knot_pair,
    fit_sellmeier_global,
    fit_k_global_8p,
    DataType,
    _get_substrate_n_array_index,
    calculate_index_rmse,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitService, IndexFitRequest
from certus.core.certus_index_core import (
    OptimizationConfig,
    OptimizationResults,
    calculate_relative_R_normalization,
    _SAPPHIRE_DATA_FILE,
    _SAPPHIRE_FILE_HAS_K_COLUMN,
    estimate_initial_params,
)
from certus.core.certus_index_objectives import (
    IRGlobalObjective,
    Phase23SplineObjective,
    Phase23Pass2SplineObjective,
    TLUObjective,
)
from certus.core.certus_index_solvers import (
    PGlobalOptimizerINDEX,
    SubsetOptimTask,
)
from certus.workers.certus_index_workers import (
    _compute_RT_from_config,
    _spectrum_visibility_target_traces,
    _index_live_spectrum_visibility,
    IRPGlobalCallback,
    IRSplineCallback,
    IRStage2Callback,
)


class IRGlobalModelStrategy:
    @staticmethod
    def _prepare_ir_phase2_inputs(worker) -> tuple:
        """Prepare full-spectrum inputs and objective for IR Phase 2 global model."""
        c = worker.config
        tlu = worker.tlu_results
        thickness = tlu.optimal_thickness
        l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)
        sub_id = c.substrate_sellmeier_id if c.substrate_sellmeier_id is not None else -1
        n_sub_full = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)
        _k_sub_full = c.k_sub_data
        _D_sub = c.substrate_thickness_nm
        if c.is_frosted_glass:
            T_sub_full = np.ones_like(l_full)
            R_sub_full = calculate_single_interface_R(l_full, n_sub_full)
        elif c.has_absorbing_substrate:
            T_sub_full = calculate_bare_substrate_T_absorbing(l_full, n_sub_full, _k_sub_full, _D_sub)
            R_sub_full = calculate_bare_substrate_R_absorbing(l_full, n_sub_full, _k_sub_full, _D_sub)
        else:
            T_sub_full = calculate_bare_substrate_RT(l_full, n_sub_full)
            R_sub_full = calculate_bare_substrate_R(l_full, n_sub_full)
        target_T = c.target_data["T"].to_numpy(dtype=np.float64) if "T" in c.target_data.columns else None
        target_R = c.target_data["R"].to_numpy(dtype=np.float64) if "R" in c.target_data.columns else None
        df_tlu = tlu.df_results
        n_tlu_ref = np.interp(l_full, df_tlu["lambda"].values, df_tlu["n_calc"].values)
        obj = IRGlobalObjective(l_full, target_T, target_R, n_sub_full, T_sub_full, R_sub_full, thickness, n_tlu_ref, c)
        return (l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness)

    @staticmethod
    def _run_ir_stage0_to_stage2(
        worker,
        c: OptimizationConfig,
        l_full: np.ndarray,
        n_sub_full: np.ndarray,
        df_tlu: pd.DataFrame,
        n_tlu_ref: np.ndarray,
        obj: IRGlobalObjective,
        thickness: float,
    ) -> tuple | None:
        """Run warm start + PGlobal + final L-BFGS-B polish and return best sample + optimizer."""
        flat_bounds = np.array(
            [
                [1.0, 16.0],
                [0.0, 20.0],
                [0.001, 1.0],
                [0.0, 20.0],
                [0.01, 20.0],
                [-40.0, 40.0],
                [-100.0, 80.0],
                [-40.0, 40.0],
                [-100.0, 80.0],
                [1e-10, 0.1],
                [0.5, 12.0],
                [0.005, 5.0],
                [1.0, 8.0],
            ],
            dtype=np.float64,
        )
        log_clues = [0, 1, 2, 3, 4, 9, 10, 11]
        worker.logger.info("-" * 65)
        worker.logger.info("PHASE 2/2: GLOBAL IR MODEL REFINEMENT (PGLOBAL)")
        worker.logger.info("  Sellmeier 2-Poles (5p) + Empirical k (8p) = 13 dimensions")
        worker.logger.info(f"  d fixed = {thickness:.2f} nm | n VIS continuity guard +/-0.20 of TLU")
        worker.logger.info("-" * 65)
        x0_polished = None
        y0_polished = np.inf
        try:
            _, params_sell = fit_sellmeier_global(l_full, n_tlu_ref)
            k_tlu_ref = None
            if "k_calc" in df_tlu.columns:
                k_raw = np.interp(l_full, df_tlu["lambda"].values, df_tlu["k_calc"].values)
                k_tlu_ref = np.clip(k_raw, 1e-09, None)
            params_k8 = None
            if k_tlu_ref is not None:
                _, params_k8 = fit_k_global_8p(l_full, k_tlu_ref)
            if params_sell is not None:
                if params_k8 is None:
                    _k_candidates = [
                        np.array([0.5, -15.0, 0.1, -20.0, 1e-06, 5.0, 1.0, 2.0]),
                        np.array([8.0, -20.0, 0.5, -25.0, 1e-05, 4.0, 0.5, 2.0]),
                        np.array([3.0, -18.0, 0.2, -22.0, 0.0001, 3.5, 0.8, 2.0]),
                        np.array([12.0, -22.0, 1.0, -28.0, 2e-05, 5.0, 1.5, 2.0]),
                        np.array([0.1, -30.0, 0.1, -30.0, 0.0005, 4.5, 0.3, 2.0]),
                    ]
                    _best_k_y = np.inf
                    _best_k_p = None
                    for _kp in _k_candidates:
                        _x_try = np.clip(np.concatenate([params_sell, _kp]), flat_bounds[:, 0], flat_bounds[:, 1])
                        _y_try = float(obj(_x_try))
                        if _y_try < _best_k_y:
                            _best_k_y = _y_try
                            _best_k_p = _kp
                    params_k8 = _best_k_p
                    worker.logger.info(
                        f"  > Warm start: Sellmeier OK | k_8p best candidate RMSE = {np.sqrt(_best_k_y):.6f}"
                    )
                else:
                    worker.logger.info("  > Warm start: Sellmeier OK | k_8p OK")
                x0_raw = np.concatenate([params_sell, params_k8])
                x0_clamped = np.clip(x0_raw, flat_bounds[:, 0], flat_bounds[:, 1])
                worker.logger.info("  > Stage 0: L-BFGS-B polish from Phase 1 warm start...")
                res_s0 = scipy.optimize.minimize(
                    obj,
                    x0_clamped,
                    method="L-BFGS-B",
                    bounds=list(zip(flat_bounds[:, 0], flat_bounds[:, 1])),
                    options={"maxiter": 3000, "ftol": 1e-15, "gtol": 1e-10},
                )
                if np.isfinite(res_s0.fun) and res_s0.fun < 100000000000.0:
                    x0_polished = res_s0.x
                    y0_polished = float(res_s0.fun)
                    worker.logger.info(f"  > Stage 0 done: RMSE = {np.sqrt(y0_polished):.6f} ({res_s0.nit} iters)")
                else:
                    y_raw = float(obj(x0_clamped))
                    if np.isfinite(y_raw) and y_raw < 100000000000.0:
                        x0_polished = x0_clamped
                        y0_polished = y_raw
                        worker.logger.info(
                            f"  > Stage 0 polish rejected, using raw warm start: RMSE = {np.sqrt(y0_polished):.6f}"
                        )
                    else:
                        worker.logger.info("  > Stage 0: warm start lands in rejected region, PGlobal starts cold")
            else:
                worker.logger.info("  > Warm start: Sellmeier fit failed, PGlobal starts cold")
        except NUMERICAL_FAULT_EXCEPTIONS as _e_ws:
            worker.logger.warning(f"  > Warm start exception: {_e_ws}  PGlobal starts cold")
        pg_bounds = flat_bounds.copy()
        if x0_polished is not None and np.isfinite(y0_polished):
            worker.logger.info(f"  > PGlobal: full bounds | warm seed RMSE = {np.sqrt(y0_polished):.6f}")
        else:
            worker.logger.info("  > PGlobal: full bounds | cold start")
        pg_conf = PGlobalConfig.for_dimension(13).with_overrides(
            max_feval=150000, max_time=480.0, max_active_clusters=100, n_samples_per_iter=3000, convergence_tol=1e-10
        )
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))
        overrides = getattr(c, "phase2_pglobal_overrides", None) or {}
        for k, v in overrides.items():
            if hasattr(pg_conf, k):
                pg_conf = pg_conf.with_overrides(**{k: v})
        if getattr(pg_conf, "max_feval", None) != 150000:
            pg_conf = pg_conf.with_overrides(max_feval=150000)
        worker.logger.info(
            f"  > PGlobal: Sobol+Clustering | =0.008 | pop={pg_conf.n_samples_per_iter} | max_feval={pg_conf.max_feval}"
        )
        worker.logger.info("-" * 65)
        optimizer = PGlobalOptimizerINDEX(
            obj, pg_bounds, n_workers=1, config=pg_conf, log_clues=log_clues, stop_event=worker._stop_event
        )
        best_y_so_far = y0_polished if np.isfinite(y0_polished) else float("inf")
        best_x_so_far = x0_polished.copy() if x0_polished is not None else None
        pg_callback = IRPGlobalCallback(
            worker, optimizer, obj, c, l_full, thickness, n_sub_full, "IR Global Search", True
        )
        if np.isfinite(best_y_so_far) and best_x_so_far is not None:
            from certus_physics import Sample as _Sample

            pg_callback(_Sample(x=best_x_so_far, y=best_y_so_far))
        res_pg = optimizer.optimize(callback=pg_callback, x0=x0_polished)
        if res_pg is None or (np.isfinite(y0_polished) and y0_polished < getattr(res_pg, "y", np.inf)):
            if x0_polished is not None and np.isfinite(y0_polished):
                worker.logger.info("  > PGlobal did not improve on Stage 0  keeping Stage 0 result")
                res_pg = _Sample(x=x0_polished, y=y0_polished)
            elif res_pg is None:
                worker.error.emit("IR optimization returned no feasible solution.")
                return None
        try:
            worker.logger.info("  > Stage 2: final L-BFGS-B polish from PGlobal result...")
            _stage2_cb = IRStage2Callback(worker, obj, c, l_full, thickness, n_sub_full)
            res_s2 = scipy.optimize.minimize(
                obj,
                res_pg.x,
                method="L-BFGS-B",
                bounds=list(zip(flat_bounds[:, 0], flat_bounds[:, 1])),
                options={"maxiter": 5000, "ftol": 1e-16, "gtol": 1e-11},
                callback=_stage2_cb,
            )
            if np.isfinite(res_s2.fun) and res_s2.fun < res_pg.y:
                _improv = (1.0 - res_s2.fun / res_pg.y) * 100.0
                worker.logger.info(
                    f"  > Stage 2 polish: {np.sqrt(res_pg.y):.6f} -> {np.sqrt(res_s2.fun):.6f}  ({_improv:.1f} % MSE reduction, {res_s2.nit} iters)"
                )
                res_pg = _Sample(x=res_s2.x, y=float(res_s2.fun))
            else:
                worker.logger.info("  > Stage 2 polish: no improvement (PGlobal already at local min)")
        except NUMERICAL_FAULT_EXCEPTIONS as _e_s2:
            worker.logger.warning(f"  > Stage 2 polish failed: {_e_s2}")
        worker.best_mse = res_pg.y
        return (res_pg, optimizer)

    @staticmethod
    def _run_phase21_refinement(
        worker,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        target_T: np.ndarray | None,
        k_spline_knots_lambda_um: np.ndarray | None,
        k_spline_knots_values: np.ndarray | None,
        p_opt_final: np.ndarray,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """Run final 90%T/10%R refinement when spline-k result is available."""
        if (
            c.is_frosted_glass
            or target_T is None
            or k_spline_knots_lambda_um is None
            or (k_spline_knots_values is None)
        ):
            return (None, None, None)
        w_T_orig = obj.weight_T
        w_R_orig = obj.weight_R
        obj.weight_T = 0.9
        obj.weight_R = 0.1
        obj.invalidate_cache()
        worker.logger.info("PHASE 2.1: 90% T / 10% R refinement from Phase 2.3 result...")
        worker.progress_snapshot.emit(
            build_progress_snapshot(
                message="Phase 2.1 (90% T)",
                display_ratio=0.99,
                progress_ratio=0.99,
                eta_seconds=None,
                confidence=0.25,
                state=StepState.RUNNING,
                module="INDEX",
                phase="IR_PHASE_2_1",
            )
        )
        try:
            n_k = len(k_spline_knots_lambda_um)
            log_k_21 = np.log(np.clip(k_spline_knots_values, 1e-09, obj.k_max_guard))
            x0_21 = np.concatenate([p_opt_final[:5].copy(), log_k_21])
            rel = 0.05
            ps = p_opt_final[:5]
            bounds_sell_21 = [
                (max(1.0, ps[0] * (1 - rel)), min(16.0, ps[0] * (1 + rel))),
                (max(0.0, ps[1] * (1 - rel)), min(20.0, ps[1] * (1 + rel))),
                (max(0.001, ps[2] * (1 - rel)), min(1.0, ps[2] * (1 + rel))),
                (max(0.0, ps[3] * (1 - rel)), min(20.0, ps[3] * (1 + rel))),
                (max(0.01, ps[4] * (1 - rel)), min(20.0, ps[4] * (1 + rel))),
            ]
            log_k_lo = np.log(1e-09)
            log_k_hi = np.log(max(obj.k_max_guard, 1e-09))
            bounds_21 = bounds_sell_21 + [(log_k_lo, log_k_hi)] * n_k
            phase23_T = Phase23SplineObjective(obj, k_spline_knots_lambda_um, obj.k_max_guard)
            _cb_21 = IRSplineCallback(
                worker,
                obj,
                c,
                l_full,
                thickness,
                n_sub_full,
                "Phase 2.1 (90% T)",
                knot_lam=k_spline_knots_lambda_um,
                n_k=n_k,
                lk_lo=log_k_lo,
                lk_hi=log_k_hi,
            )
            r21 = scipy.optimize.minimize(
                phase23_T,
                x0_21,
                method="L-BFGS-B",
                jac=phase23_T.gradient,
                bounds=bounds_21,
                options={"maxiter": 1500, "ftol": 1e-14, "gtol": 1e-09},
                callback=_cb_21,
            )
            if np.isfinite(r21.fun) and r21.fun < 10000000000.0:
                n_T = sellmeier_2poles_eval_nj(r21.x[:5], obj.wl_um)
                B_T = SplineBasisCache.get(k_spline_knots_lambda_um, obj.wl_um)
                k_T = np.exp(np.clip(B_T @ r21.x[5 : 5 + n_k], log_k_lo, log_k_hi))
                p_opt_T = np.concatenate([r21.x[:5], res_pg.x[5:]])
                worker.logger.info(f"  Phase 2.1 done: RMSE_T = {np.sqrt(r21.fun):.6f}")
                return (n_T, k_T, p_opt_T)
            return (None, None, None)
        except NUMERICAL_FAULT_EXCEPTIONS as _e21:
            worker.logger.warning(f"  Phase 2.1 failed: {_e21}")
            return (None, None, None)
        finally:
            obj.weight_T = w_T_orig
            obj.weight_R = w_R_orig
            obj.invalidate_cache()

    @staticmethod
    def _run_phase23_knot_reduction(
        worker,
        *,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
        log_k_lo: float,
        log_k_hi: float,
        lam_min: float,
        lam_max: float,
        min_knot_dist_um: float,
        initial_best_n: int,
        initial_best_mse: float,
        initial_best_knot_lam: np.ndarray,
        initial_best_log_k: np.ndarray,
        initial_best_p_sell: np.ndarray,
        n_final: np.ndarray,
        k_final: np.ndarray,
        p_opt_final: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Reduce spline knot count while constraining RMSE degradation."""
        RMSE_RATIO_MAX = 1.1
        MIN_KNOTS = 4
        best_n = int(initial_best_n)
        best_mse_red = float(initial_best_mse)
        best_knot_lam = initial_best_knot_lam.copy()
        best_log_k = initial_best_log_k.copy()
        best_p_sell = initial_best_p_sell.copy()
        n_out = n_final
        k_out = k_final
        p_out = p_opt_final
        while best_n > MIN_KNOTS:
            knot_lam_try, log_k_try = _merge_closest_knot_pair(best_knot_lam, best_log_k)
            knot_lam_try = _ensure_strictly_increasing(knot_lam_try, min_gap=1e-09)
            n_k_try = len(knot_lam_try)
            rel = 0.1
            ps0 = best_p_sell
            bounds_sell_try = [
                (max(1.0, ps0[0] * (1 - rel)), min(16.0, ps0[0] * (1 + rel))),
                (max(0.0, ps0[1] * (1 - rel)), min(20.0, ps0[1] * (1 + rel))),
                (max(0.001, ps0[2] * (1 - rel)), min(1.0, ps0[2] * (1 + rel))),
                (max(0.0, ps0[3] * (1 - rel)), min(20.0, ps0[3] * (1 + rel))),
                (max(0.01, ps0[4] * (1 - rel)), min(20.0, ps0[4] * (1 + rel))),
            ]
            bounds_log_k_try = [(log_k_lo, log_k_hi)] * n_k_try
            x0_p1_try = np.concatenate([best_p_sell, log_k_try])
            bounds_p1_try = bounds_sell_try + bounds_log_k_try
            phase23_try = Phase23SplineObjective(obj, knot_lam_try, obj.k_max_guard)
            t0_red = time.time()
            best_x_red = x0_p1_try.copy()
            best_fun_red = np.inf
            while True:
                _cb_red_p1 = IRSplineCallback(
                    worker,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    f"Knot reduction {best_n}->{n_k_try}",
                    knot_lam=knot_lam_try,
                    n_k=n_k_try,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                    t0=t0_red,
                )
                r1_try = scipy.optimize.minimize(
                    phase23_try,
                    best_x_red,
                    method="L-BFGS-B",
                    jac=phase23_try.gradient,
                    bounds=bounds_p1_try,
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-09},
                    callback=_cb_red_p1,
                )
                if np.isfinite(r1_try.fun) and r1_try.fun < best_fun_red:
                    best_fun_red = r1_try.fun
                    best_x_red = r1_try.x.copy()
                if time.time() - t0_red >= 2.0:
                    break
            if not np.isfinite(best_fun_red) or best_fun_red > RMSE_RATIO_MAX**2 * best_mse_red:
                worker.logger.info(
                    f"  Knot reduction: {best_n} -> {n_k_try} rejected (loss > 10% RMSE), keeping {best_n} knots"
                )
                break
            bounds_lam_try = [(lam_min + min_knot_dist_um, lam_max - min_knot_dist_um) for _ in range(n_k_try - 2)]
            x0_p2_try = np.concatenate([best_x_red[:5], best_x_red[5 : 5 + n_k_try], knot_lam_try[1:-1]])
            bounds_p2_try = bounds_sell_try + bounds_log_k_try + bounds_lam_try
            phase23_p2_try = Phase23Pass2SplineObjective(
                obj, n_k_try, lam_min, lam_max, obj.k_max_guard, min_knot_dist_um
            )
            _cb_red_p2 = IRSplineCallback(
                worker,
                obj,
                c,
                l_full,
                thickness,
                n_sub_full,
                f"Knot reduction {best_n}->{n_k_try}",
                phase23_obj=phase23_p2_try,
                n_k=n_k_try,
                lk_lo=log_k_lo,
                lk_hi=log_k_hi,
            )
            try:
                r2_try = scipy.optimize.minimize(
                    phase23_p2_try,
                    x0_p2_try,
                    method="L-BFGS-B",
                    jac=phase23_p2_try.gradient,
                    bounds=bounds_p2_try,
                    options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-09},
                    callback=_cb_red_p2,
                )
                if np.isfinite(r2_try.fun) and r2_try.fun <= RMSE_RATIO_MAX**2 * best_mse_red:
                    best_mse_red = r2_try.fun
                    best_n = n_k_try
                    best_knot_lam = phase23_p2_try._knot_lam_from_x(r2_try.x)
                    best_log_k = r2_try.x[5 : 5 + n_k_try].copy()
                    best_p_sell = r2_try.x[:5].copy()
                    worker.best_mse = r2_try.fun
                    n_out = sellmeier_2poles_eval_nj(r2_try.x[:5], obj.wl_um)
                    B_red = SplineBasisCache.get(best_knot_lam, obj.wl_um)
                    k_out = np.exp(np.clip(B_red @ best_log_k, log_k_lo, log_k_hi))
                    p_out = np.concatenate([r2_try.x[:5], res_pg.x[5:]])
                    worker.logger.info(
                        f"  Knot reduction: {best_n + 1} -> {best_n} OK (RMSE {np.sqrt(best_mse_red):.6f}, < 10% loss)"
                    )
                else:
                    worker.logger.info(
                        f"  Knot reduction: {best_n} -> {n_k_try} rejected (loss > 10% RMSE), keeping {best_n} knots"
                    )
                    break
            except NUMERICAL_FAULT_EXCEPTIONS as _ered:
                worker.logger.warning(f"  Knot reduction failed: {_ered}, keeping {best_n} knots")
                break
        return (n_out, k_out, p_out, best_knot_lam, best_log_k, best_mse_red)

    @staticmethod
    def _run_phase23_spline_refinement(
        worker,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
        """Run Phase 2.3 spline refinement and return final n/k/model params and spline knots."""
        n_final = sellmeier_2poles_eval_nj(res_pg.x[:5], obj.wl_um)
        k_final = k_law_8p_eval(obj.wl_um, res_pg.x[5:])
        p_opt_final = res_pg.x
        k_spline_knots_lambda_um = None
        k_spline_knots_values = None
        rmse_before_23 = np.sqrt(res_pg.y)
        try:
            num_knots = 8
            knot_lam_um = _deduce_knots_from_k8p(obj.wl_um, res_pg.x[5:], num_knots=num_knots, min_knot_dist_um=0.05)
            k_at_knots = k_law_8p_eval(knot_lam_um, res_pg.x[5:])
            log_k_lo = np.log(1e-09)
            log_k_hi = np.log(max(obj.k_max_guard, 1e-09))
            log_k_knot0 = np.log(np.clip(k_at_knots, 1e-09, obj.k_max_guard))
            rel = 0.1
            p_sell0 = res_pg.x[:5].copy()
            bounds_sell = [
                (max(1.0, p_sell0[0] * (1 - rel)), min(16.0, p_sell0[0] * (1 + rel))),
                (max(0.0, p_sell0[1] * (1 - rel)), min(20.0, p_sell0[1] * (1 + rel))),
                (max(0.001, p_sell0[2] * (1 - rel)), min(1.0, p_sell0[2] * (1 + rel))),
                (max(0.0, p_sell0[3] * (1 - rel)), min(20.0, p_sell0[3] * (1 + rel))),
                (max(0.01, p_sell0[4] * (1 - rel)), min(20.0, p_sell0[4] * (1 + rel))),
            ]
            bounds_log_k = [(log_k_lo, log_k_hi)] * num_knots
            bounds_23 = bounds_sell + bounds_log_k
            x0_23 = np.concatenate([res_pg.x[:5].copy(), log_k_knot0])
            phase23_obj = Phase23SplineObjective(obj, knot_lam_um, obj.k_max_guard)
            worker.logger.info("PHASE 2.3: spline k (log k) + n variable (tight bounds)...")
            worker.progress_snapshot.emit(
                build_progress_snapshot(
                    message="Phase 2.3 spline k",
                    display_ratio=0.98,
                    progress_ratio=0.98,
                    eta_seconds=None,
                    confidence=0.25,
                    state=StepState.RUNNING,
                    module="INDEX",
                    phase="IR_PHASE_2_3",
                )
            )
            t0_p1 = time.time()
            best_x_23 = x0_23.copy()
            best_fun_23 = np.inf
            while True:
                _cb_p1 = IRSplineCallback(
                    worker,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    "Phase 2.3 spline k",
                    knot_lam=knot_lam_um,
                    n_k=num_knots,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                    t0=t0_p1,
                )
                r23 = scipy.optimize.minimize(
                    phase23_obj,
                    best_x_23,
                    method="L-BFGS-B",
                    jac=phase23_obj.gradient,
                    bounds=bounds_23,
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-09},
                    callback=_cb_p1,
                )
                if np.isfinite(r23.fun) and r23.fun < best_fun_23:
                    best_fun_23 = r23.fun
                    best_x_23 = r23.x.copy()
                elapsed_p1 = time.time() - t0_p1
                if elapsed_p1 >= 2.0:
                    break
            r23 = type("_R23", (), {"fun": best_fun_23, "x": best_x_23})()
            if np.isfinite(r23.fun) and r23.fun < 10000000000.0:
                worker.best_mse = r23.fun
                n_final = sellmeier_2poles_eval_nj(r23.x[:5], obj.wl_um)
                B = SplineBasisCache.get(knot_lam_um, obj.wl_um)
                log_k = B @ r23.x[5 : 5 + num_knots]
                k_final = np.exp(np.clip(log_k, log_k_lo, log_k_hi))
                p_opt_final = np.concatenate([r23.x[:5], res_pg.x[5:]])
                k_spline_knots_lambda_um = knot_lam_um.copy()
                k_spline_knots_values = np.exp(np.clip(r23.x[5 : 5 + num_knots], log_k_lo, log_k_hi))
                worker.logger.info(
                    f"  Phase 2.3 Pass 1 done: RMSE {np.sqrt(r23.fun):.6f} (before: {rmse_before_23:.6f}) [{elapsed_p1:.1f} s]"
                )
                min_knot_dist_um = 0.05
                lam_min = float(obj.wl_um.min())
                lam_max = float(obj.wl_um.max())
                bounds_lambda = [(lam_min + min_knot_dist_um, lam_max - min_knot_dist_um) for _ in range(num_knots - 2)]
                bounds_23_pass2 = bounds_sell + bounds_log_k + bounds_lambda
                lambda_internes0 = knot_lam_um[1:-1].copy()
                x0_pass2 = np.concatenate([r23.x[:5], r23.x[5 : 5 + num_knots], lambda_internes0])
                phase23_pass2 = Phase23Pass2SplineObjective(
                    obj, num_knots, lam_min, lam_max, obj.k_max_guard, min_knot_dist_um
                )
                worker.logger.info("  Phase 2.3 Pass 2: knot positions + values...")
                worker.progress_snapshot.emit(
                    build_progress_snapshot(
                        message="Phase 2.3 Pass 2",
                        display_ratio=0.99,
                        progress_ratio=0.99,
                        eta_seconds=None,
                        confidence=0.25,
                        state=StepState.RUNNING,
                        module="INDEX",
                        phase="IR_PHASE_2_3_P2",
                    )
                )
                _cb_p2 = IRSplineCallback(
                    worker,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    "Phase 2.3 Pass 2",
                    phase23_obj=phase23_pass2,
                    n_k=num_knots,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                )
                try:
                    r23p2 = scipy.optimize.minimize(
                        phase23_pass2,
                        x0_pass2,
                        method="L-BFGS-B",
                        jac=phase23_pass2.gradient,
                        bounds=bounds_23_pass2,
                        options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-09},
                        callback=_cb_p2,
                    )
                    if np.isfinite(r23p2.fun) and r23p2.fun < 10000000000.0 and (r23p2.fun <= r23.fun):
                        worker.best_mse = r23p2.fun
                        knot_lam_p2 = phase23_pass2._knot_lam_from_x(r23p2.x)
                        n_final = sellmeier_2poles_eval_nj(r23p2.x[:5], obj.wl_um)
                        B_p2 = SplineBasisCache.get(knot_lam_p2, obj.wl_um)
                        log_k_p2 = B_p2 @ r23p2.x[5 : 5 + num_knots]
                        k_final = np.exp(np.clip(log_k_p2, log_k_lo, log_k_hi))
                        p_opt_final = np.concatenate([r23p2.x[:5], res_pg.x[5:]])
                        k_spline_knots_lambda_um = knot_lam_p2.copy()
                        k_spline_knots_values = np.exp(np.clip(r23p2.x[5 : 5 + num_knots], log_k_lo, log_k_hi))
                        worker.logger.info(f"  Phase 2.3 Pass 2 done: RMSE {np.sqrt(r23p2.fun):.6f}")
                    else:
                        worker.logger.info("  Phase 2.3 Pass 2: no improvement, keeping Pass 1 result")
                except NUMERICAL_FAULT_EXCEPTIONS as _ep2:
                    worker.logger.warning(f"  Phase 2.3 Pass 2 failed: {_ep2}, keeping Pass 1 result")
                n_final, k_final, p_opt_final, best_knot_lam, best_log_k, _ = worker._run_phase23_knot_reduction(
                    c=c,
                    obj=obj,
                    res_pg=res_pg,
                    l_full=l_full,
                    thickness=thickness,
                    n_sub_full=n_sub_full,
                    log_k_lo=log_k_lo,
                    log_k_hi=log_k_hi,
                    lam_min=lam_min,
                    lam_max=lam_max,
                    min_knot_dist_um=min_knot_dist_um,
                    initial_best_n=num_knots,
                    initial_best_mse=worker.best_mse,
                    initial_best_knot_lam=k_spline_knots_lambda_um,
                    initial_best_log_k=np.log(np.clip(k_spline_knots_values, 1e-09, obj.k_max_guard)),
                    initial_best_p_sell=p_opt_final[:5],
                    n_final=n_final,
                    k_final=k_final,
                    p_opt_final=p_opt_final,
                )
                k_spline_knots_lambda_um = best_knot_lam.copy()
                k_spline_knots_values = np.exp(np.clip(best_log_k, log_k_lo, log_k_hi))
            else:
                worker.logger.warning("  Phase 2.3: no improvement, keeping 8p (k_8p) result")
        except NUMERICAL_FAULT_EXCEPTIONS as _e23:
            worker.logger.warning(f"  Phase 2.3 failed: {_e23}")
        return (n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values)

    @staticmethod
    def _package_results(
        worker,
        n,
        k,
        thickness,
        l_full,
        p_opt,
        n_T=None,
        k_T=None,
        p_T=None,
        k_spline_knots_lambda_um=None,
        k_spline_knots_values=None,
    ) -> Any:
        c = worker.config
        sub_id = c.substrate_sellmeier_id
        if sub_id is None:
            raise ValueError(f"Unknown canonical substrate id for {c.substrate!r}")
        n_sub = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)
        Rc, Tc, Ts = _compute_RT_from_config(c, l_full, n, k, thickness, n_sub)
        with np.errstate(divide="ignore", invalid="ignore"):
            T_s_safe_T = np.where(Ts > T_SUB_MIN_T_NORM, Ts, np.nan)
            T_norm = np.nan_to_num(Tc / T_s_safe_T, nan=0.0)
            T_s_safe_R = np.where(Ts > T_SUB_MIN_R_NORM, Ts, np.nan)
            R_norm = np.nan_to_num(Rc / T_s_safe_R, nan=0.0)
        df = pd.DataFrame(
            {
                "lambda": l_full,
                "n_calc": n,
                "k_calc": k,
                "T_calc (%)": Tc * 100,
                "T_norm_calc (%)": T_norm * 100,
                "R_calc (%)": Rc * 100,
                "R_norm_calc (%)": R_norm * 100,
            }
        )
        if "T" in c.target_data.columns:
            df["T_target"] = c.target_data["T"].to_numpy()
        if "R" in c.target_data.columns:
            df["R_target"] = c.target_data["R"].to_numpy()
        if n_T is not None:
            df["n_fit_T_only"] = n_T
            df["k_fit_T_only"] = k_T
        n_rt = n
        if n_T is not None:
            df["delta_n"] = 2.0 * np.abs(n_rt - n_T)
            df["delta_k"] = 2.0 * np.abs(k - k_T) if k_T is not None else 0.0
        else:
            df["delta_n"] = 0.0
            df["delta_k"] = 0.0
        results = OptimizationResults(
            config=c,
            optimal_thickness=thickness,
            final_mse=worker.best_mse,
            df_results=df,
            tlu_params=None,
            optimization_stats={"method": "PGLOBAL Global Refinement (Sellmeier+k8p)", "final_cost": worker.best_mse},
            execution_time=0.0,
            sellmeier_params=p_opt[:5],
        )
        results.k_8p_params = p_opt[5:]
        results.n_T, results.k_T, results.p_opt_T = (n_T, k_T, p_T)
        results.k_spline_knots_lambda_um = k_spline_knots_lambda_um
        results.k_spline_knots_values = k_spline_knots_values
        return results
