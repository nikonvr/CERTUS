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
    Phase1Callback,
)


class IndexOptimizationStrategy:
    @staticmethod
    def _run_subset_optim(worker, clues_slice, wls, n_sub, target_T, target_R, exclude_range) -> Any:
        c = worker.config
        wls_sub = wls[clues_slice]
        n_sub_sub = n_sub[clues_slice]
        target_T_sub = target_T[clues_slice] if target_T is not None else None
        target_R_sub = target_R[clues_slice] if target_R is not None else None
        obj_sub = TLUObjective(
            wls_sub,
            target_T_sub,
            target_R_sub,
            n_sub_sub,
            c.data_type,
            (c.thickness_min, c.thickness_max),
            use_normalized=c.use_normalized,
            weight_T=c.weight_T,
            weight_R=c.weight_R,
            exclude_range=exclude_range,
            is_frosted_glass=c.is_frosted_glass,
        )
        res_sub = scipy.optimize.minimize(
            obj_sub,
            worker.best_params,
            method="L-BFGS-B",
            jac=obj_sub.gradient,
            bounds=[(lb, ub) for lb, ub in obj_sub.get_bounds()],
            options={"ftol": SMALL_EPSILON, "gtol": SMALL_EPSILON, "maxiter": 500},
        )
        _bs = obj_sub.get_bounds()
        _lbs = _bs[:, 0]
        _ubs = _bs[:, 1]
        res_polish = scipy.optimize.minimize(
            obj_sub, res_sub.x, method="Nelder-Mead", options={"xatol": 1e-08, "fatol": SMALL_EPSILON, "maxiter": 300}
        )
        x_clip_s = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lbs, _ubs)
        mse_clip_s = float(obj_sub(x_clip_s))
        if float(res_sub.fun) <= mse_clip_s:
            return res_sub.x
        return x_clip_s

    @staticmethod
    def _prepare_run_inputs(
        worker, c: OptimizationConfig
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None, tuple[float, float] | None, TLUObjective]:
        worker.logger.info("=" * 80)
        worker.logger.info("CERTUS INDEX - OPTIMIZATION STARTED")
        worker.logger.info("=" * 80)
        _src = (getattr(c, "source_file", None) or "").strip()
        if _src:
            worker.logger.info("[FILE] Measured Spectrum (input): %s", Path(_src).resolve())
        else:
            worker.logger.warning("[FILE] Measured Spectrum: source path not provided")
        _subn = getattr(c, "substrate", "")
        if _subn == "Sapphire (Al2O3)":
            worker.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) | k file: %s | k column in xlsx: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )
        elif _subn == "Silicon (Si)":
            _clues = get_resource_path("clues.xlsx")
            worker.logger.info("[FILE] Substrate Si (n,k): %s", Path(_clues).resolve())
        if worker.thickness_initial is None:
            worker.thickness_initial = (c.thickness_min + c.thickness_max) / 2.0
        _lmf = getattr(c, "lambda_max_fit", None)
        effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))
        mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)
        wls = c.target_data.loc[mask, "lambda"].to_numpy()
        if len(wls) == 0:
            worker.logger.error(
                "No spectral points in [%.1f, %.1f] nm found in the loaded data. If you are in IR only (lambda_min >= 2200), do not cut at 2200 nm; widen lambda_min towards UV or let the range cover < 2200 nm.",
                c.lambda_min,
                effective_lambda_max,
            )
            raise ValueError("Wavelength window empty for optimization (check min/max lambda or exclusion range).")
        worker.logger.info(
            f"Wavelength range: {c.lambda_min:.1f} - {effective_lambda_max:.1f} nm"
            + (
                f" (TLU fit restricted from {c.lambda_max:.1f} nm)"
                if _lmf is not None and effective_lambda_max < c.lambda_max
                else ""
            )
        )
        worker.logger.info(f"Number of data points: {len(wls)}")
        sub_id = c.substrate_sellmeier_id
        if sub_id is None:
            raise ValueError(f"Unknown canonical substrate id for {c.substrate!r}")
        if c.n_sub_data is not None:
            l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)
            n_sub = np.interp(wls, l_full, c.n_sub_data, left=c.n_sub_data[0], right=c.n_sub_data[-1]).astype(
                np.float64
            )
        else:
            n_sub = _get_substrate_n_array_index(sub_id, wls)
        worker.logger.info(f"substrate: {c.substrate}")
        if c.is_frosted_glass:
            worker.logger.info("Mode: Frosted Glass (Reflection only)")
        else:
            worker.logger.info(f"Data type: {c.data_type.name}")
        target_T = None
        target_R = None
        if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and (not c.is_frosted_glass):
            if "T" in c.target_data.columns:
                target_T = c.target_data.loc[mask, "T"].to_numpy()
        if c.data_type in (DataType.REFLECTION, DataType.BOTH):
            if "R" in c.target_data.columns:
                target_R = c.target_data.loc[mask, "R"].to_numpy()
        valid = np.isfinite(n_sub)
        if target_T is not None:
            valid &= np.isfinite(target_T)
        if target_R is not None:
            valid &= np.isfinite(target_R)
        wls = wls[valid]
        n_sub = n_sub[valid]
        if target_T is not None:
            target_T = target_T[valid]
        if target_R is not None:
            target_R = target_R[valid]
        exclude_range = None
        if c.exclude_min is not None and c.exclude_max is not None:
            exclude_range = (c.exclude_min, c.exclude_max)
        obj = TLUObjective(
            wls,
            target_T,
            target_R,
            n_sub,
            c.data_type,
            (c.thickness_min, c.thickness_max),
            use_normalized=c.use_normalized,
            weight_T=c.weight_T,
            weight_R=c.weight_R,
            exclude_range=exclude_range,
            is_frosted_glass=c.is_frosted_glass,
            has_absorbing_substrate=c.has_absorbing_substrate,
            k_sub_data=c.k_sub_data,
            substrate_thickness_nm=c.substrate_thickness_nm,
        )
        return (wls, n_sub, target_T, target_R, exclude_range, obj)

    @staticmethod
    def _run_phase5_final_optimization(worker, obj: TLUObjective, params_list: list[np.ndarray]) -> None:
        """Run final full-grid refinement and update best solution if improved."""
        worker.progress_snapshot.emit(
            build_progress_snapshot(
                message="Final ultimate optimization...",
                display_ratio=0.92,
                progress_ratio=0.92,
                eta_seconds=None,
                confidence=0.25,
                state=StepState.RUNNING,
                module="INDEX",
                phase="OPT_FINAL",
            )
        )
        worker.logger.info("\n--- PHASE 5: Final Ultimate Optimization (full grid) ---")
        try:
            if len(params_list) == 3:
                avg_params = np.mean(params_list, axis=0)
            else:
                avg_params = worker.best_params
            _bf5 = obj.get_bounds()
            _lb5 = _bf5[:, 0]
            _ub5 = _bf5[:, 1]
            avg_params = clip_to_bounds(np.asarray(avg_params, dtype=np.float64).ravel(), _lb5, _ub5)
            res_final = scipy.optimize.minimize(
                obj,
                avg_params,
                method="L-BFGS-B",
                jac=obj.gradient,
                bounds=[(lb, ub) for lb, ub in obj.get_bounds()],
                options={"ftol": 1e-14, "gtol": 1e-14, "maxiter": 1000},
            )
            res_polish = scipy.optimize.minimize(
                obj, res_final.x, method="Nelder-Mead", options={"xatol": 1e-09, "fatol": 1e-14, "maxiter": 500}
            )
            x_nm_clip = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lb5, _ub5)
            mse_nm_clip = float(obj(x_nm_clip))
            if float(res_final.fun) <= mse_nm_clip:
                final_params, final_mse = (res_final.x, float(res_final.fun))
            else:
                final_params, final_mse = (x_nm_clip, mse_nm_clip)
            if final_mse < worker.best_mse:
                worker.best_mse = final_mse
                worker.best_params = final_params
                worker.logger.info(f" Final optimization improved RMSE: {calculate_index_rmse(final_mse):.6f}")
                worker._emit_live_best_snapshot()
            else:
                worker.logger.info(
                    f" Final optimization complete (RMSE unchanged: {calculate_index_rmse(worker.best_mse):.6f})"
                )
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            worker.logger.warning(f"Final optimization failed: {e}")

    @staticmethod
    def _run_phase1_global_search(
        worker,
        c: OptimizationConfig,
        obj: TLUObjective,
        wls: np.ndarray,
        target_T: np.ndarray | None,
        n_sub: np.ndarray,
    ) -> bool:
        """Run Phase 1 (PGLOBAL) and initialize best_params/best_mse.

        Returns True when execution should stop early (stop requested and finalized).
        """
        if c.high_precision:
            max_evals = 80000
            worker.logger.info("High Precision Mode Enabled (80k evals)")
        else:
            max_evals = 20000
            worker.logger.info("Standard Precision Mode (20k evals)")
        max_time = 240.0
        worker.logger.info("\n--- PHASE 1: PGLOBAL Global Search ---")
        worker.logger.info(f"Thickness range: {c.thickness_min:.1f} - {c.thickness_max:.1f} nm")
        worker.logger.info(f"Max evaluations: {max_evals}")
        worker.progress_snapshot.emit(
            build_progress_snapshot(
                message="Global Search...",
                display_ratio=0.05,
                progress_ratio=0.05,
                eta_seconds=None,
                confidence=0.25,
                state=StepState.RUNNING,
                module="INDEX",
                phase="OPT_GLOBAL",
            )
        )
        pg_conf = PGlobalConfig.for_index(max_feval=max_evals, max_time=max_time)
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))
        pg_conf = pg_conf.with_overrides(local_search_budget=1500)
        worker._optimizer = PGlobalOptimizerINDEX(
            obj, obj.get_bounds(), n_workers=1, config=pg_conf, log_clues=[2, 5], stop_event=worker._stop_event
        )
        phase1_cb = Phase1Callback(worker, max_evals)
        worker._phase1_obj = obj
        smart_x0 = estimate_initial_params(wls, target_T, n_sub)
        smart_x0[0] = float(worker.thickness_initial)
        _bnds = obj.get_bounds()
        for _i in range(7):
            smart_x0[_i] = float(np.clip(smart_x0[_i], _bnds[_i, 0], _bnds[_i, 1]))
        worker.logger.info(
            "TLU warm start | d=%.1f nm  Eg=%.3f eV  A=%.2f  E0=%.3f  C=%.3f  Eu=%.3f  eps_inf=%.3f",
            smart_x0[0],
            smart_x0[1],
            smart_x0[2],
            smart_x0[3],
            smart_x0[4],
            smart_x0[5],
            smart_x0[6],
        )
        try:
            worker.logger.info("TLU diag [warm start] | %s", obj.format_diag_line(smart_x0))
        except NUMERICAL_FAULT_EXCEPTIONS as _e_d0:
            worker.logger.debug("TLU diag warm skip: %s", _e_d0)
        try:
            worker.logger.info("TLU k [warm start / Phase1] | %s", obj.format_k_line(smart_x0))
        except NUMERICAL_FAULT_EXCEPTIONS as _e_k0:
            worker.logger.debug("TLU k warm skip: %s", _e_k0)
        try:
            _y_ws = float(obj(smart_x0))
            if np.isfinite(_y_ws):
                worker.best_mse = _y_ws
                worker.best_params = smart_x0.copy()
                worker.logger.info(
                    "TLU warm-start preview | RMSE = %.6f (traces avant 1er lot PGlobal)",
                    float(np.sqrt(max(0.0, _y_ws))),
                )
                worker._emit_live_best_snapshot()
        except NUMERICAL_FAULT_EXCEPTIONS as _e_ws:
            worker.logger.debug("TLU warm-start preview skipped: %s", _e_ws)
        best = worker._optimizer.optimize(max_iter=30, callback=phase1_cb)
        if best:
            rmse_best = np.sqrt(best.y)
            worker.logger.info(
                f" PGLOBAL Pass 1 complete | Final RMSE: {rmse_best:.6f} | Total evals: {worker._optimizer.n_evals}"
            )
        else:
            worker.logger.warning(" PGLOBAL Pass 1 did not find a solution")
        if worker._finalize_if_stopped():
            return True
        if best:
            worker.best_params = best.x
            worker.best_mse = best.y
            worker._emit_live_best_snapshot()
        elif worker.best_params is not None and np.isfinite(worker.best_mse):
            worker.logger.info(
                f"Using callback-captured best params as fallback (RMSE={calculate_index_rmse(worker.best_mse):.6f}, d={worker.best_params[0]:.2f} nm)"
            )
            worker._emit_live_best_snapshot()
        else:
            worker.logger.info("Using Smart Initialization for fallback parameters...")
            smart_init = estimate_initial_params(wls, target_T, n_sub)
            smart_init[0] = (c.thickness_min + c.thickness_max) / 2
            worker.best_params = smart_init
            worker._emit_live_best_snapshot()
        return False

    @staticmethod
    def _package_results(
        worker, thickness: float, tlu_params: TLUParameters, params_list: list | None = None
    ) -> OptimizationResults:
        """Package optimization results. params_list contains 3 param arrays for uncertainty."""
        c = worker.config
        l_full = c.target_data["lambda"].to_numpy()
        E_full = HC_EV_NM / l_full
        if c.is_frosted_glass:
            n_sub = get_n_frosted_glass_array(l_full)
        else:
            sub_id = c.substrate_sellmeier_id if c.substrate_sellmeier_id is not None else -1
            n_sub = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)
        eps2 = epsilon2_TLU_array(E_full, tlu_params.Eg, tlu_params.A, tlu_params.E0, tlu_params.C, tlu_params.Eu)
        eps1 = epsilon1_TL_analytic(
            E_full, tlu_params.Eg, tlu_params.A, tlu_params.E0, tlu_params.C, tlu_params.eps_inf
        )
        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)
        R_calc, T_calc, T_sub = _compute_RT_from_config(c, l_full, n_calc, k_calc, thickness, n_sub)
        with np.errstate(divide="ignore", invalid="ignore"):
            T_sub_safe = np.where(T_sub > T_SUB_MIN_T_NORM, T_sub, np.nan)
            T_norm_calc = np.nan_to_num(T_calc / T_sub_safe, nan=0.0)
            if c.is_frosted_glass:
                R_norm_calc = R_calc.copy()
            else:
                R_norm_calc = calculate_relative_R_normalization(R_calc, T_sub)
        delta_n_res = np.zeros_like(l_full)
        delta_k_res = np.zeros_like(l_full)
        if params_list and len(params_list) >= 2:
            n_arrays = []
            k_arrays = []
            for p in params_list:
                tlu_sub = TLUParameters.from_array(p[1:7])
                e2_s = epsilon2_TLU_array(E_full, tlu_sub.Eg, tlu_sub.A, tlu_sub.E0, tlu_sub.C, tlu_sub.Eu)
                e1_s = epsilon1_TL_analytic(E_full, tlu_sub.Eg, tlu_sub.A, tlu_sub.E0, tlu_sub.C, tlu_sub.eps_inf)
                n_s, k_s, _ = epsilon_to_nk(e1_s, e2_s, 0.5, 15.0, 15.0)
                n_arrays.append(n_s)
                k_arrays.append(k_s)
            for i in range(len(n_arrays)):
                for j in range(i + 1, len(n_arrays)):
                    delta_n_res = np.maximum(delta_n_res, np.abs(n_arrays[i] - n_arrays[j]))
                    delta_k_res = np.maximum(delta_k_res, np.abs(k_arrays[i] - k_arrays[j]))
        df_data = {
            "lambda": l_full,
            "n_calc": n_calc,
            "k_calc": k_calc,
            "delta_n_res": delta_n_res,
            "delta_k_res": delta_k_res,
            "alpha_cm-1": 4.0 * PI * k_calc / (l_full * 1e-07),
            "T_calc (%)": T_calc * 100,
            "T_norm_calc (%)": T_norm_calc * 100,
            "R_calc (%)": R_calc * 100,
            "R_norm_calc (%)": R_norm_calc * 100,
        }
        if "T" in c.target_data.columns:
            df_data["T_target"] = c.target_data["T"].to_numpy()
        if "R" in c.target_data.columns:
            df_data["R_target"] = c.target_data["R"].to_numpy()
        df = pd.DataFrame(df_data)
        weights_recalc = np.ones_like(l_full, dtype=np.float64)
        out_of_range = (l_full < c.lambda_min) | (l_full > c.lambda_max)
        weights_recalc[out_of_range] = 0.0
        if c.exclude_min is not None and c.exclude_max is not None:
            exc_mask = (l_full >= c.exclude_min) & (l_full <= c.exclude_max)
            weights_recalc[exc_mask] = 0.0
        lambda_max_fit = getattr(c, "lambda_max_fit", None)
        if lambda_max_fit is not None:
            weights_recalc[l_full > lambda_max_fit] = 0.0
        total_mse_recalc = 0.0
        total_weight_recalc = 0.0
        if "T" in c.target_data.columns and (not c.is_frosted_glass):
            target_T = c.target_data["T"].to_numpy()
            val_T = T_norm_calc if c.use_normalized else T_calc
            mse_t, n_t = compute_mse_vectorized(val_T, target_T, weights_recalc)
            if n_t >= 5:
                total_mse_recalc += mse_t * c.weight_T
                total_weight_recalc += c.weight_T
        if "R" in c.target_data.columns:
            target_R = c.target_data["R"].to_numpy()
            val_R = R_norm_calc if c.use_normalized else R_calc
            mse_r, n_r = compute_mse_vectorized(val_R, target_R, weights_recalc)
            if n_r >= 5:
                total_mse_recalc += mse_r * c.weight_R
                total_weight_recalc += c.weight_R
        final_mse_recalc = worker.best_mse
        if total_weight_recalc > 1e-09:
            final_mse_recalc = total_mse_recalc / total_weight_recalc
        if np.isfinite(worker.best_mse) and float(worker.best_mse) < 1e99:
            final_mse_canonical = float(worker.best_mse)
        else:
            final_mse_canonical = float(final_mse_recalc)
        stats = {
            "method": "PGLOBAL + L-BFGS-B + DeepRefine",
            "data_type": c.data_type.name,
            "substrate_mode": c.substrate_mode.name,
            "thickness_variation_pct": getattr(worker, "thickness_variation", 0.0),
            "mse_uniform_grid_recalc": float(final_mse_recalc),
        }
        return OptimizationResults(
            config=c,
            optimal_thickness=thickness,
            final_mse=final_mse_canonical,
            df_results=df,
            tlu_params=tlu_params,
            optimization_stats=stats,
            execution_time=getattr(worker, "execution_time", 0.0),
        )
