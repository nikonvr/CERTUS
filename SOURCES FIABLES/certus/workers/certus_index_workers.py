import time
import traceback
import logging
from pathlib import Path
from threading import Event
from typing import Any
import scipy
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
from certus.core.certus_index_core import TLU_SOFT_EDGE_MARGIN, TLU_PRIOR_TRANSPARENT_N_MIN_SOFT
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
    IRGlobalObjective,
    Phase23SplineObjective,
    Phase23Pass2SplineObjective,
    TLUObjective,
    OptimizationConfig,
    OptimizationResults,
    PGlobalOptimizerINDEX,
    SubsetOptimTask,
    calculate_relative_R_normalization,
    _SAPPHIRE_DATA_FILE,
    _SAPPHIRE_FILE_HAS_K_COLUMN,
    estimate_initial_params,
)

class IRPGlobalCallback:
    def __init__(
        self, worker, opt_instance, obj, c, l_full, thickness, n_sub_full, title="IR Global Search", emit_plot=True
    ) -> None:

        self.worker = worker

        self.opt_instance = opt_instance

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self.title = title

        self.emit_plot = emit_plot

        self.state = [float("inf"), None, 0.0, float("inf"), 0.0, float("inf")]

    def __call__(self, sample) -> None:

        if sample.y < self.state[0]:
            self.state[0], self.state[1] = sample.y, sample.x

        now = time.time()

        if now - self.state[2] < 2.0:
            return

        self.state[2] = now

        self.worker.evals_update.emit(self.opt_instance.n_evals)

        if not self.emit_plot:
            self.worker.progress.emit(90, self.title, self.state[0])

            return

        self.worker.best_params = self.state[1]

        self.worker.best_mse = self.state[0]

        rmse = np.sqrt(self.state[0])

        improved_for_plot = rmse < (self.state[5] * 0.998)

        heartbeat_plot = (now - self.state[4]) >= 10.0

        if not improved_for_plot and not heartbeat_plot:
            self.worker.progress.emit(90, self.title, self.state[0])

            return

        n = sellmeier_2poles_eval_nj(self.state[1][:5], self.obj.wl_um)

        k = k_law_8p_eval(self.obj.wl_um, self.state[1][5:])

        Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

        T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

        # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE :

        # In relative mode (use_normalized), relative R (R_v) = R_calc / T_substrat_nu.

        # Do not correct this formula, it corresponds to the physical calibration of the local spectrometer.

        R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

        T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

        if self.c.is_frosted_glass:
            T_v = np.full_like(self.l_full, np.nan)

        _st, _sr = _index_live_spectrum_visibility(self.c)

        plot_data = {
            "n": n,
            "k": k,
            "wls": self.l_full,
            "R_calc": R_v,
            "T_calc": T_v,
            "is_frosted_glass": self.c.is_frosted_glass,
            "live_show_T": _st,
            "live_show_R": _sr,
            "mse": self.state[0],
        }

        self.state[5] = min(self.state[5], rmse)

        if rmse < self.state[3] or (now - self.state[4]) >= 10.0:
            if rmse < self.state[3]:
                self.state[3] = rmse

            self.state[4] = now

            self.worker.logger.info(f"  [PGLOBAL] Evals: {self.opt_instance.n_evals:6d} | RMSE: {rmse:.6f}")

        self.worker.progress.emit(int(self.opt_instance.n_evals / 300), self.title, plot_data)

class IRStage2Callback:
    def __init__(self, worker, obj, c, l_full, thickness, n_sub_full) -> None:

        self.worker = worker

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self._last_plot = 0.0

    def __call__(self, xk) -> None:

        if time.time() - self._last_plot < 1.5:
            return

        self._last_plot = time.time()

        try:
            n = sellmeier_2poles_eval_nj(xk[:5], self.obj.wl_um)

            k = k_law_8p_eval(self.obj.wl_um, xk[5:])

            Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

            T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

            # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE : R_v = R_calc / T_substrat_nu

            R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

            T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

            if self.c.is_frosted_glass:
                T_v = np.full_like(self.l_full, np.nan)

            _st, _sr = _index_live_spectrum_visibility(self.c)

            self.worker.progress.emit(
                91,
                "Stage 2 polish",
                {
                    "n": n,
                    "k": k,
                    "wls": self.l_full,
                    "R_calc": R_v,
                    "T_calc": T_v,
                    "is_frosted_glass": self.c.is_frosted_glass,
                    "live_show_T": _st,
                    "live_show_R": _sr,
                    "mse": None,
                },
            )

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

class IRSplineCallback:
    def __init__(
        self,
        worker,
        obj,
        c,
        l_full,
        thickness,
        n_sub_full,
        title,
        phase23_obj=None,
        knot_lam=None,
        n_k=None,
        lk_lo=None,
        lk_hi=None,
        t0=None,
    ) -> None:

        self.worker = worker

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self.title = title

        self.phase23_obj = phase23_obj

        self.knot_lam = knot_lam

        self.n_k = n_k

        self.lk_lo = lk_lo

        self.lk_hi = lk_hi

        self.t0 = t0

        self._last_plot = 0.0

    def get_plot_data(self, xk) -> dict | None:

        try:
            knot_lam_local = self.knot_lam

            if self.phase23_obj:
                knot_lam_local = self.phase23_obj._knot_lam_from_x(xk)

            n = sellmeier_2poles_eval_nj(xk[:5], self.obj.wl_um)

            B = SplineBasisCache.get(knot_lam_local, self.obj.wl_um)

            k = np.exp(np.clip(B @ xk[5 : 5 + self.n_k], self.lk_lo, self.lk_hi))

            Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

            T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

            # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE : R_v = R_calc / T_substrat_nu

            R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

            T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

            if self.c.is_frosted_glass:
                T_v = np.full_like(self.l_full, np.nan)

            _st, _sr = _index_live_spectrum_visibility(self.c)

            return {
                "n": n,
                "k": k,
                "wls": self.l_full,
                "R_calc": R_v,
                "T_calc": T_v,
                "is_frosted_glass": self.c.is_frosted_glass,
                "live_show_T": _st,
                "live_show_R": _sr,
                "mse": None,
            }

        except NUMERICAL_FAULT_EXCEPTIONS :
            return None

    def __call__(self, xk) -> bool:

        if time.time() - self._last_plot >= 1.5:
            self._last_plot = time.time()

            pd = self.get_plot_data(xk)

            if pd is not None:
                self.worker.progress.emit(99, self.title, pd)

        if self.t0 is not None:
            return (time.time() - self.t0) >= 10.0

class IRGlobalModelWorker(QObject):
    """

    Refined IR extension pipeline (>2500nm) using PGLOBAL with Sellmeier+EmpiricalK models.

    Replaces the legacy Spline-based approach.

    """

    finished = pyqtSignal(object)

    error = pyqtSignal(str)

    progress = pyqtSignal(int, str, object)

    evals_update = pyqtSignal(int)

    curve_update = pyqtSignal(object)  # best-so-far params (aligned with OptimizationWorker)

    def __init__(self, config: OptimizationConfig, tlu_results: OptimizationResults, logger=None) -> None:

        super().__init__()

        self.config = config

        self.tlu_results = tlu_results

        self.logger = logger or logging.getLogger("CertusIndex")

        self._stop_event = Event()

        self.best_mse = np.inf

        self.best_params = None

    def stop(self) -> None:

        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:

        return self._stop_event.is_set()

    def _prepare_ir_phase2_inputs(self) -> tuple:
        """Prepare full-spectrum inputs and objective for IR Phase 2 global model."""

        c = self.config

        tlu = self.tlu_results

        thickness = tlu.optimal_thickness

        l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

        sub_id = c.substrate_sellmeier_id if c.substrate_sellmeier_id is not None else -1

        n_sub_full = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)

        # Absorbing substrate: Al2O3 or user-provided k_sub.
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

        obj = IRGlobalObjective(
            l_full,
            target_T,
            target_R,
            n_sub_full,
            T_sub_full,
            R_sub_full,
            thickness,
            n_tlu_ref,
            c,
        )

        return l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness

    def _run_ir_stage0_to_stage2(
        self,
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

        self.logger.info("-" * 65)

        self.logger.info("PHASE 2/2: GLOBAL IR MODEL REFINEMENT (PGLOBAL)")

        self.logger.info("  Sellmeier 2-Poles (5p) + Empirical k (8p) = 13 dimensions")

        self.logger.info(f"  d fixed = {thickness:.2f} nm | n VIS continuity guard +/-0.20 of TLU")

        self.logger.info("-" * 65)

        x0_polished = None

        y0_polished = np.inf

        try:
            _, params_sell = fit_sellmeier_global(l_full, n_tlu_ref)

            k_tlu_ref = None

            if "k_calc" in df_tlu.columns:
                k_raw = np.interp(l_full, df_tlu["lambda"].values, df_tlu["k_calc"].values)

                k_tlu_ref = np.clip(k_raw, 1e-9, None)

            params_k8 = None

            if k_tlu_ref is not None:
                _, params_k8 = fit_k_global_8p(l_full, k_tlu_ref)

            if params_sell is not None:
                if params_k8 is None:
                    _k_candidates = [
                        np.array([0.5, -15.0, 0.1, -20.0, 1e-6, 5.0, 1.0, 2.0]),
                        np.array([8.0, -20.0, 0.5, -25.0, 1e-5, 4.0, 0.5, 2.0]),
                        np.array([3.0, -18.0, 0.2, -22.0, 1e-4, 3.5, 0.8, 2.0]),
                        np.array([12.0, -22.0, 1.0, -28.0, 2e-5, 5.0, 1.5, 2.0]),
                        np.array([0.1, -30.0, 0.1, -30.0, 5e-4, 4.5, 0.3, 2.0]),
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

                    self.logger.info(
                        f"  > Warm start: Sellmeier OK | k_8p best candidate RMSE = {np.sqrt(_best_k_y):.6f}"
                    )

                else:
                    self.logger.info("  > Warm start: Sellmeier OK | k_8p OK")

                x0_raw = np.concatenate([params_sell, params_k8])

                x0_clamped = np.clip(x0_raw, flat_bounds[:, 0], flat_bounds[:, 1])

                self.logger.info("  > Stage 0: L-BFGS-B polish from Phase 1 warm start...")

                res_s0 = scipy.optimize.minimize(
                    obj,
                    x0_clamped,
                    method="L-BFGS-B",
                    bounds=list(zip(flat_bounds[:, 0], flat_bounds[:, 1])),
                    options={"maxiter": 3000, "ftol": 1e-15, "gtol": 1e-10},
                )

                if np.isfinite(res_s0.fun) and res_s0.fun < 1e11:
                    x0_polished = res_s0.x

                    y0_polished = float(res_s0.fun)

                    self.logger.info(f"  > Stage 0 done: RMSE = {np.sqrt(y0_polished):.6f} ({res_s0.nit} iters)")

                else:
                    y_raw = float(obj(x0_clamped))

                    if np.isfinite(y_raw) and y_raw < 1e11:
                        x0_polished = x0_clamped

                        y0_polished = y_raw

                        self.logger.info(
                            f"  > Stage 0 polish rejected, using raw warm start: RMSE = {np.sqrt(y0_polished):.6f}"
                        )

                    else:
                        self.logger.info("  > Stage 0: warm start lands in rejected region, PGlobal starts cold")

            else:
                self.logger.info("  > Warm start: Sellmeier fit failed, PGlobal starts cold")

        except NUMERICAL_FAULT_EXCEPTIONS as _e_ws:
            self.logger.warning(f"  > Warm start exception: {_e_ws}  PGlobal starts cold")

        pg_bounds = flat_bounds.copy()

        if x0_polished is not None and np.isfinite(y0_polished):
            self.logger.info(f"  > PGlobal: full bounds | warm seed RMSE = {np.sqrt(y0_polished):.6f}")

        else:
            self.logger.info("  > PGlobal: full bounds | cold start")

        pg_conf = PGlobalConfig.for_dimension(13).with_overrides(
            max_feval=150000,
            max_time=480.0,
            max_active_clusters=100,
            n_samples_per_iter=3000,
            convergence_tol=1e-10,
        )
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))

        overrides = getattr(c, "phase2_pglobal_overrides", None) or {}

        for k, v in overrides.items():
            if hasattr(pg_conf, k):
                pg_conf = pg_conf.with_overrides(**{k: v})

        # Keep the runtime budget aligned with the explicit Phase 2 default used above.
        # This avoids stale or indirect config overrides surfacing as misleading log values.
        if getattr(pg_conf, "max_feval", None) != 150000:
            pg_conf = pg_conf.with_overrides(max_feval=150000)

        self.logger.info(
            f"  > PGlobal: Sobol+Clustering | =0.008 | pop={pg_conf.n_samples_per_iter} | max_feval={pg_conf.max_feval}"
        )

        self.logger.info("-" * 65)

        optimizer = PGlobalOptimizerINDEX(
            obj, pg_bounds, n_workers=1, config=pg_conf, log_clues=log_clues, stop_event=self._stop_event
        )

        best_y_so_far = y0_polished if np.isfinite(y0_polished) else float("inf")

        best_x_so_far = x0_polished.copy() if x0_polished is not None else None

        pg_callback = IRPGlobalCallback(
            self, optimizer, obj, c, l_full, thickness, n_sub_full, "IR Global Search", True
        )

        if np.isfinite(best_y_so_far) and best_x_so_far is not None:
            from certus_physics import Sample as _Sample

            pg_callback(_Sample(x=best_x_so_far, y=best_y_so_far))

        res_pg = optimizer.optimize(callback=pg_callback, x0=x0_polished)

        if res_pg is None or (np.isfinite(y0_polished) and y0_polished < getattr(res_pg, "y", np.inf)):
            if x0_polished is not None and np.isfinite(y0_polished):
                self.logger.info("  > PGlobal did not improve on Stage 0  keeping Stage 0 result")

                res_pg = _Sample(x=x0_polished, y=y0_polished)

            elif res_pg is None:
                self.error.emit("IR optimization returned no feasible solution.")

                return None

        try:
            self.logger.info("  > Stage 2: final L-BFGS-B polish from PGlobal result...")

            _stage2_cb = IRStage2Callback(self, obj, c, l_full, thickness, n_sub_full)

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

                self.logger.info(
                    f"  > Stage 2 polish: {np.sqrt(res_pg.y):.6f} -> {np.sqrt(res_s2.fun):.6f}"
                    f"  ({_improv:.1f} % MSE reduction, {res_s2.nit} iters)"
                )

                res_pg = _Sample(x=res_s2.x, y=float(res_s2.fun))

            else:
                self.logger.info("  > Stage 2 polish: no improvement (PGlobal already at local min)")

        except NUMERICAL_FAULT_EXCEPTIONS as _e_s2:
            self.logger.warning(f"  > Stage 2 polish failed: {_e_s2}")

        self.best_mse = res_pg.y

        return res_pg, optimizer

    def _run_phase21_refinement(
        self,
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

        if c.is_frosted_glass or target_T is None or k_spline_knots_lambda_um is None or k_spline_knots_values is None:
            return None, None, None

        w_T_orig = obj.weight_T

        w_R_orig = obj.weight_R

        obj.weight_T = 0.9

        obj.weight_R = 0.1

        obj.invalidate_cache()

        self.logger.info("PHASE 2.1: 90% T / 10% R refinement from Phase 2.3 result...")

        self.progress.emit(99, "Phase 2.1 (90% T)", None)

        try:
            n_k = len(k_spline_knots_lambda_um)

            log_k_21 = np.log(np.clip(k_spline_knots_values, 1e-9, obj.k_max_guard))

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

            log_k_lo = np.log(1e-9)

            log_k_hi = np.log(max(obj.k_max_guard, 1e-9))

            bounds_21 = bounds_sell_21 + [(log_k_lo, log_k_hi)] * n_k

            phase23_T = Phase23SplineObjective(obj, k_spline_knots_lambda_um, obj.k_max_guard)

            _cb_21 = IRSplineCallback(
                self,
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
                options={"maxiter": 1500, "ftol": 1e-14, "gtol": 1e-9},
                callback=_cb_21,
            )

            if np.isfinite(r21.fun) and r21.fun < 1e10:
                n_T = sellmeier_2poles_eval_nj(r21.x[:5], obj.wl_um)

                B_T = SplineBasisCache.get(k_spline_knots_lambda_um, obj.wl_um)

                k_T = np.exp(np.clip(B_T @ r21.x[5 : 5 + n_k], log_k_lo, log_k_hi))

                p_opt_T = np.concatenate([r21.x[:5], res_pg.x[5:]])

                self.logger.info(f"  Phase 2.1 done: RMSE_T = {np.sqrt(r21.fun):.6f}")

                return n_T, k_T, p_opt_T

            return None, None, None

        except NUMERICAL_FAULT_EXCEPTIONS as _e21:
            self.logger.warning(f"  Phase 2.1 failed: {_e21}")

            return None, None, None

        finally:
            obj.weight_T = w_T_orig

            obj.weight_R = w_R_orig

            obj.invalidate_cache()

    def _run_phase23_knot_reduction(
        self,
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

        RMSE_RATIO_MAX = 1.10

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

            knot_lam_try = _ensure_strictly_increasing(knot_lam_try, min_gap=1e-9)

            n_k_try = len(knot_lam_try)

            rel = 0.10

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
                    self,
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
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_red_p1,
                )

                if np.isfinite(r1_try.fun) and r1_try.fun < best_fun_red:
                    best_fun_red = r1_try.fun

                    best_x_red = r1_try.x.copy()

                if time.time() - t0_red >= 2.0:
                    break

            if not np.isfinite(best_fun_red) or best_fun_red > RMSE_RATIO_MAX**2 * best_mse_red:
                self.logger.info(
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
                self,
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
                    options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_red_p2,
                )

                if np.isfinite(r2_try.fun) and r2_try.fun <= RMSE_RATIO_MAX**2 * best_mse_red:
                    best_mse_red = r2_try.fun

                    best_n = n_k_try

                    best_knot_lam = phase23_p2_try._knot_lam_from_x(r2_try.x)

                    best_log_k = r2_try.x[5 : 5 + n_k_try].copy()

                    best_p_sell = r2_try.x[:5].copy()

                    self.best_mse = r2_try.fun

                    n_out = sellmeier_2poles_eval_nj(r2_try.x[:5], obj.wl_um)

                    B_red = SplineBasisCache.get(best_knot_lam, obj.wl_um)

                    k_out = np.exp(np.clip(B_red @ best_log_k, log_k_lo, log_k_hi))

                    p_out = np.concatenate([r2_try.x[:5], res_pg.x[5:]])

                    self.logger.info(
                        f"  Knot reduction: {best_n + 1} -> {best_n} OK (RMSE {np.sqrt(best_mse_red):.6f}, < 10% loss)"
                    )

                else:
                    self.logger.info(
                        f"  Knot reduction: {best_n} -> {n_k_try} rejected (loss > 10% RMSE), keeping {best_n} knots"
                    )

                    break

            except NUMERICAL_FAULT_EXCEPTIONS as _ered:
                self.logger.warning(f"  Knot reduction failed: {_ered}, keeping {best_n} knots")

                break

        return n_out, k_out, p_out, best_knot_lam, best_log_k, best_mse_red

    def _run_phase23_spline_refinement(
        self,
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

            log_k_lo = np.log(1e-9)

            log_k_hi = np.log(max(obj.k_max_guard, 1e-9))

            log_k_knot0 = np.log(np.clip(k_at_knots, 1e-9, obj.k_max_guard))

            rel = 0.10

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

            self.logger.info("PHASE 2.3: spline k (log k) + n variable (tight bounds)...")

            self.progress.emit(98, "Phase 2.3 spline k", None)

            t0_p1 = time.time()

            best_x_23 = x0_23.copy()

            best_fun_23 = np.inf

            while True:
                _cb_p1 = IRSplineCallback(
                    self,
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
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_p1,
                )

                if np.isfinite(r23.fun) and r23.fun < best_fun_23:
                    best_fun_23 = r23.fun

                    best_x_23 = r23.x.copy()

                elapsed_p1 = time.time() - t0_p1

                if elapsed_p1 >= 2.0:
                    break

            r23 = type("_R23", (), {"fun": best_fun_23, "x": best_x_23})()

            if np.isfinite(r23.fun) and r23.fun < 1e10:
                self.best_mse = r23.fun

                n_final = sellmeier_2poles_eval_nj(r23.x[:5], obj.wl_um)

                B = SplineBasisCache.get(knot_lam_um, obj.wl_um)

                log_k = B @ r23.x[5 : 5 + num_knots]

                k_final = np.exp(np.clip(log_k, log_k_lo, log_k_hi))

                p_opt_final = np.concatenate([r23.x[:5], res_pg.x[5:]])

                k_spline_knots_lambda_um = knot_lam_um.copy()

                k_spline_knots_values = np.exp(np.clip(r23.x[5 : 5 + num_knots], log_k_lo, log_k_hi))

                self.logger.info(
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

                self.logger.info("  Phase 2.3 Pass 2: knot positions + values...")

                self.progress.emit(99, "Phase 2.3 Pass 2", None)

                _cb_p2 = IRSplineCallback(
                    self,
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
                        options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-9},
                        callback=_cb_p2,
                    )

                    if np.isfinite(r23p2.fun) and r23p2.fun < 1e10 and r23p2.fun <= r23.fun:
                        self.best_mse = r23p2.fun

                        knot_lam_p2 = phase23_pass2._knot_lam_from_x(r23p2.x)

                        n_final = sellmeier_2poles_eval_nj(r23p2.x[:5], obj.wl_um)

                        B_p2 = SplineBasisCache.get(knot_lam_p2, obj.wl_um)

                        log_k_p2 = B_p2 @ r23p2.x[5 : 5 + num_knots]

                        k_final = np.exp(np.clip(log_k_p2, log_k_lo, log_k_hi))

                        p_opt_final = np.concatenate([r23p2.x[:5], res_pg.x[5:]])

                        k_spline_knots_lambda_um = knot_lam_p2.copy()

                        k_spline_knots_values = np.exp(np.clip(r23p2.x[5 : 5 + num_knots], log_k_lo, log_k_hi))

                        self.logger.info(f"  Phase 2.3 Pass 2 done: RMSE {np.sqrt(r23p2.fun):.6f}")

                    else:
                        self.logger.info("  Phase 2.3 Pass 2: no improvement, keeping Pass 1 result")

                except NUMERICAL_FAULT_EXCEPTIONS as _ep2:
                    self.logger.warning(f"  Phase 2.3 Pass 2 failed: {_ep2}, keeping Pass 1 result")

                n_final, k_final, p_opt_final, best_knot_lam, best_log_k, _ = self._run_phase23_knot_reduction(
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
                    initial_best_mse=self.best_mse,
                    initial_best_knot_lam=k_spline_knots_lambda_um,
                    initial_best_log_k=np.log(np.clip(k_spline_knots_values, 1e-9, obj.k_max_guard)),
                    initial_best_p_sell=p_opt_final[:5],
                    n_final=n_final,
                    k_final=k_final,
                    p_opt_final=p_opt_final,
                )
                k_spline_knots_lambda_um = best_knot_lam.copy()
                k_spline_knots_values = np.exp(np.clip(best_log_k, log_k_lo, log_k_hi))

            else:
                self.logger.warning("  Phase 2.3: no improvement, keeping 8p (k_8p) result")

        except NUMERICAL_FAULT_EXCEPTIONS as _e23:
            self.logger.warning(f"  Phase 2.3 failed: {_e23}")

        return n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values

    def run(self) -> None:

        try:

            start_time = time.time()

            c = self.config

            l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness = self._prepare_ir_phase2_inputs()

            stage02 = self._run_ir_stage0_to_stage2(
                c,
                l_full,
                n_sub_full,
                df_tlu,
                n_tlu_ref,
                obj,
                thickness,
            )
            if stage02 is None:
                return
            res_pg, optimizer = stage02

            duration = time.time() - start_time

            rmse_final = np.sqrt(res_pg.y)

            self.logger.info("-" * 65)

            self.logger.info(f"PHASE 2 SUCCESSFUL ({duration:.1f} s)")

            self.logger.info(f"  > Final IR RMSE: {rmse_final:.6f}")

            self.logger.info(f"  > Total Evals: {optimizer.n_evals}")

            self.logger.info("-" * 65)

            # ---------- Phase 2 flow ----------

            # Stage 0: warm start (Sellmeier + k_8p from Phase 1) + L-BFGS-B polish

            # Stage 1: PGlobal global search (13 params: Sellmeier 5p + k 8p)

            # Stage 2: L-BFGS-B polish from PGlobal result

            # Phase 2.3: replace k_8p by spline in log(k); n stays Sellmeier with tight bounds

            #   Pass 1: optimize p_sell + log_k at fixed knot positions (210 s)

            #   Pass 2: optimize knot positions + values

            #   Knot reduction: try N-1, N-2, ... knots while RMSE loss < 10%

            # Phase 2.1 (last): 90% T / 10% R refinement from Phase 2.3 result (spline + Sellmeier)

            # ----------

            n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values = (
                self._run_phase23_spline_refinement(
                    c,
                    obj,
                    res_pg,
                    l_full,
                    thickness,
                    n_sub_full,
                )
            )

            n_T, k_T, p_opt_T = self._run_phase21_refinement(
                c,
                obj,
                target_T,
                k_spline_knots_lambda_um,
                k_spline_knots_values,
                p_opt_final,
                res_pg,
                l_full,
                thickness,
                n_sub_full,
            )

            # Package results; delta_n / delta_k = gap between 50-50 and 90% T curves

            results = self._package_results(
                n_final,
                k_final,
                thickness,
                l_full,
                p_opt_final,
                n_T,
                k_T,
                p_opt_T,
                k_spline_knots_lambda_um=k_spline_knots_lambda_um,
                k_spline_knots_values=k_spline_knots_values,
            )

            results.execution_time = duration  # Phase 2 total duration

            try:
                status_val = (
                    ValidationStatus.WARNING_DATA_NORMALIZED
                    if bool(getattr(c, "use_normalized", False))
                    else ValidationStatus.OK
                )
                warnings_list = (
                    ["Input data normalized before optimization."] if bool(getattr(c, "use_normalized", False)) else []
                )
                svc = IndexFitService(runner=lambda _cfg: results)
                svc_resp = svc.fit(
                    IndexFitRequest(
                        config=c,
                        source_paths=[str(getattr(c, "source_file", "") or "")],
                        seed=getattr(c, "random_seed", None),
                        app_id="CERTUS_INDEX",
                        app_version=__version__,
                        warnings=warnings_list,
                        status=status_val,
                    )
                )
                stats = dict(getattr(results, "optimization_stats", {}) or {})
                stats["run_manifest"] = svc_resp.manifest.to_dict()
                results.optimization_stats = stats
            except NUMERICAL_FAULT_EXCEPTIONS as _e_manifest:
                self.logger.debug("IndexFitService manifest wiring skipped: %s", _e_manifest)

            self.progress.emit(100, "Done (IR Refined)", None)

            self.finished.emit(results)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"IR Global optimization error: {e}", exc_info=True)

            self.error.emit(str(e))

    def _package_results(
        self,
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

        c = self.config

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

        # delta_n = 2 * |n_50 - n_T|, delta_k = 2 * |k_50 - k_T| (gap between 50-50 and 90% T curves)

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
            final_mse=self.best_mse,
            df_results=df,
            tlu_params=None,
            optimization_stats={"method": "PGLOBAL Global Refinement (Sellmeier+k8p)", "final_cost": self.best_mse},
            execution_time=0.0,
            sellmeier_params=p_opt[:5],
        )

        results.k_8p_params = p_opt[5:]

        results.n_T, results.k_T, results.p_opt_T = n_T, k_T, p_T

        results.k_spline_knots_lambda_um = k_spline_knots_lambda_um

        results.k_spline_knots_values = k_spline_knots_values

        return results

def _compute_RT_from_config(c, l_full, n, k, thickness, n_sub) -> tuple:
    """

    Single source of truth for R/T calculation.

    Returns (Rc, Tc, Ts) where:

      - Rc, Tc: physical (absolute) reflection and transmission.

      - Ts: substrate transmission (for normalized form T/Ts, R/Ts when use_normalized).

    Branches: frosted_glass | absorbing_substrate | standard.

    """

    _k_sub = getattr(c, "k_sub_data", None)

    _D_sub = getattr(c, "substrate_thickness_nm", None)

    nan_arr = np.full_like(l_full, np.nan)

    if c.is_frosted_glass:
        Rc = calculate_reflection_array(l_full, n, k, thickness, n_sub)

        return Rc, nan_arr, nan_arr

    elif getattr(c, "has_absorbing_substrate", False):
        Rc, Tc = calculate_RT_single_layer_absorbing_substrate_array(l_full, n, k, thickness, n_sub, _k_sub, _D_sub)

        Ts = calculate_bare_substrate_T_absorbing(l_full, n_sub, _k_sub, _D_sub)

        return Rc, Tc, Ts

    else:
        Rc, Tc = calculate_RT_single_layer_backside_array(l_full, n, k, thickness, n_sub)

        Ts = calculate_bare_substrate_RT(l_full, n_sub)

        return Rc, Tc, Ts

def _spectrum_visibility_target_traces(data_type: DataType, is_frosted_glass: bool) -> tuple[bool, bool]:
    """

    Indicates which T and R curves to display, aligned with TLUObjective

    and _update_spectrum_plot : T only if TRANSMISSION or BOTH (not frosted) ;

    R if REFLECTION, BOTH, or frosted substrate (R only).

    """

    show_t = (not is_frosted_glass) and data_type in (DataType.TRANSMISSION, DataType.BOTH)

    show_r = is_frosted_glass or data_type in (DataType.REFLECTION, DataType.BOTH)

    return show_t, show_r

def _index_live_spectrum_visibility(c: OptimizationConfig) -> tuple[bool, bool]:
    """Live visibility INDEX (TLU / IR) : same logic as targets used in the cost."""

    return _spectrum_visibility_target_traces(c.data_type, c.is_frosted_glass)

class Phase1Callback:
    def __init__(self, worker, max_evals) -> None:

        self.worker = worker

        self.max_evals = max_evals

        self._last_status_emit = 0.0

    def __call__(self, s) -> None:

        if self.worker.is_stopped:
            return

        if not np.isfinite(s.y):
            return

        improved = (not np.isfinite(self.worker.best_mse)) or (s.y < self.worker.best_mse)

        if improved:
            self.worker._update_phase1_best(s)
            self.worker._try_active_update(s.x, s.y, force=True)

        now = time.time()

        if improved or (now - self._last_status_emit >= 2.0):
            self._last_status_emit = now

            progress = min(60, int(60 * self.worker._optimizer.n_evals / self.max_evals))

            self.worker.progress.emit(progress, "Global Search...", self.worker.best_mse)

class Phase2PolishCallback:
    def __init__(self, worker) -> None:

        self.worker = worker

        self.polish_iters = 0

    def __call__(self, xk) -> None:

        self.polish_iters += 1

        if self.worker.is_stopped:
            raise StopIteration

        prog_polish = min(75, 60 + int(15 * self.polish_iters / 200))

        self.worker.progress.emit(prog_polish, f"Polish {self.polish_iters}", None)

        self.worker._try_active_update(xk, self.worker.best_mse, force=False)
class OptimizationWorker(QObject):
    """Worker thread for optimization to keep UI responsive"""

    # Progress: (percentage, status_text)

    # Plus an optional trailing extra_info parameter for passing RMSE or live curves

    progress = pyqtSignal(int, str, object)

    finished = pyqtSignal(object)

    error = pyqtSignal(str)

    evals_update = pyqtSignal(int)

    curve_update = pyqtSignal(object)  # Best-so-far params for live plot

    def __init__(self, config: OptimizationConfig, logger=None) -> None:

        super().__init__()

        self.config = config

        self.best_mse = np.inf

        self.best_params = None

        self._stop_event = Event()

        self._optimizer: PGlobalOptimizerINDEX | None = None

        self.logger = logger or logging.getLogger("CertusIndex")

        self.last_plot_update_time = 0.0

        self.last_status_update_time = 0.0

        self.min_plot_interval = 1.0  # Max 1 FPS (User request)

        self.thickness_initial = config.fixed_thickness  # Seed if available

        self._last_best_rmse_log_time = 0.0

        self._last_best_rmse_logged = float("inf")

    def _should_emit_active_update(self, now: float, force: bool) -> bool:
        """Return True when live plot refresh should be emitted."""
        if force:
            return (now - self.last_plot_update_time) > self.min_plot_interval
        return (now - self.last_plot_update_time) > 5.0

    def _update_best_live_params(self, params, mse) -> None:
        """Update best-so-far state if the new sample is strictly better."""
        if mse < self.best_mse:
            self.best_mse = mse
            self.best_params = np.asarray(params, dtype=np.float64).copy()

    def _update_phase1_best(self, sample) -> None:
        """Update phase-1 best state and log diagnostics."""
        self.best_mse = sample.y
        self.best_params = sample.x.copy()
        rmse = np.sqrt(sample.y)

        _tlu_ex = ""
        _o1 = getattr(self, "_phase1_obj", None)
        if _o1 is None:
            _opt = getattr(self, "_optimizer", None)
            if _opt is not None:
                _o1 = getattr(_opt, "objective", None)

        if _o1 is not None:
            try:
                _tlu_ex = " | " + _o1.format_diag_line(sample.x)
            except NUMERICAL_FAULT_EXCEPTIONS as _e_tlu:
                _tlu_ex = f" | diag_tlu_err={_e_tlu}"

        _k_inline = ""
        if _o1 is not None:
            try:
                _k_inline = " | " + _o1.format_k_line(sample.x)
            except NUMERICAL_FAULT_EXCEPTIONS:
                _k_inline = ""

        # Throttle logging to avoid spamming the log during fast local search iterations
        now = time.time()
        significant_improvement = (rmse < self._last_best_rmse_logged * 0.995)
        time_elapsed = (now - self._last_best_rmse_log_time >= 2.0)

        if significant_improvement or time_elapsed:
            self._last_best_rmse_log_time = now
            self._last_best_rmse_logged = rmse
            n_ev = self._optimizer.n_evals if self._optimizer is not None else 0
            self.logger.info(
                f"  Best RMSE: {rmse:.6f} | Evaluations: {n_ev} | Thickness: {sample.x[0]:.2f} nm{_tlu_ex}{_k_inline}"
            )

        if _o1 is None and not getattr(self, "_warned_phase1_missing_obj", False):
            self.logger.warning(
                "Phase1 TLU diag/k unavailable (neither _phase1_obj nor _optimizer.objective) - "
                "run an up-to-date CERTUS_INDEX.py (e.g. folder 1904)."
            )
            self._warned_phase1_missing_obj = True

    def _try_active_update(self, params, mse, force=False) -> None:
        """

        Live trace refresh (throttle).

        Always emit the **best** known parameter set (`best_params`), not the current iteration:

        e.g. during L-BFGS-B polish, ``params`` might be a sub-optimal xk while ``mse`` is capped

        at the global best - the live plot must stay on the best-so-far.

        """

        now = time.time()

        if not self._should_emit_active_update(now, force):
            return

        if mse <= self.best_mse:
            self._update_best_live_params(params, mse)

            if self.best_params is not None:
                self.curve_update.emit(np.asarray(self.best_params, dtype=np.float64).copy())
                self.last_plot_update_time = now

    def _emit_live_best_snapshot(self) -> None:
        """

        Push live trace on current ``best_params`` **without throttle**.

        Essential after L-BFGS-B / Nelder : the last polish ``callback`` might be from

        before the last iteration; otherwise the UI stays on the old best (e.g. PGLOBAL)

        while the log already shows the polish RMSE.

        """

        if self.best_params is not None:
            self.curve_update.emit(np.asarray(self.best_params, dtype=np.float64).copy())



    def _run_subset_optim(self, clues_slice, wls, n_sub, target_T, target_R, exclude_range) -> Any:


        c = self.config

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
            self.best_params,
            method="L-BFGS-B",
            jac=obj_sub.gradient,
            bounds=[(lb, ub) for lb, ub in obj_sub.get_bounds()],
            options={"ftol": SMALL_EPSILON, "gtol": SMALL_EPSILON, "maxiter": 500},
        )

        _bs = obj_sub.get_bounds()

        _lbs = _bs[:, 0]

        _ubs = _bs[:, 1]

        res_polish = scipy.optimize.minimize(
            obj_sub,
            res_sub.x,
            method="Nelder-Mead",
            options={"xatol": 1e-8, "fatol": SMALL_EPSILON, "maxiter": 300},
        )

        x_clip_s = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lbs, _ubs)

        mse_clip_s = float(obj_sub(x_clip_s))

        if float(res_sub.fun) <= mse_clip_s:
            return res_sub.x

        return x_clip_s

    def stop(self) -> None:

        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:

        return self._stop_event.is_set()

    def _finalize_if_stopped(self, params_list: list | None = None) -> bool:
        """Emit partial results and cleanup when stop was requested."""

        if not self.is_stopped:
            return False

        if self.best_params is not None:
            thickness = self.best_params[0]

            tlu_params = TLUParameters.from_array(self.best_params[1:7])

            results = self._package_results(thickness, tlu_params, params_list=params_list)

            self.finished.emit(results)

        self._cleanup()

        return True

    def _prepare_run_inputs(
        self,
        c: OptimizationConfig,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray | None,
        np.ndarray | None,
        tuple[float, float] | None,
        TLUObjective,
    ]:

        self.logger.info("=" * 80)

        self.logger.info("CERTUS INDEX - OPTIMIZATION STARTED")

        self.logger.info("=" * 80)

        _src = (getattr(c, "source_file", None) or "").strip()

        if _src:
            self.logger.info("[FILE] Measured Spectrum (input): %s", Path(_src).resolve())

        else:
            self.logger.warning("[FILE] Measured Spectrum: source path not provided")

        _subn = getattr(c, "substrate", "")

        if _subn == "Sapphire (Al2O3)":
            self.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) "
                "| k file: %s | k column in xlsx: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )

        elif _subn == "Silicon (Si)":
            _clues = get_resource_path("clues.xlsx")

            self.logger.info("[FILE] Substrate Si (n,k): %s", Path(_clues).resolve())

        if self.thickness_initial is None:
            self.thickness_initial = (c.thickness_min + c.thickness_max) / 2.0

        # Filter data - use lambda_max_fit if set (two-stage pipeline restricts TLU to UV-VIS)

        _lmf = getattr(c, "lambda_max_fit", None)

        effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))

        mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)

        wls = c.target_data.loc[mask, "lambda"].to_numpy()

        if len(wls) == 0:
            self.logger.error(
                "No spectral points in [%.1f, %.1f] nm found in the loaded data. "
                "If you are in IR only (lambda_min >= 2200), do not cut at 2200 nm; "
                "widen lambda_min towards UV or let the range cover < 2200 nm.",
                c.lambda_min,
                effective_lambda_max,
            )

            raise ValueError("Wavelength window empty for optimization (check min/max lambda or exclusion range).")

        self.logger.info(
            f"Wavelength range: {c.lambda_min:.1f} - {effective_lambda_max:.1f} nm"
            + (
                f" (TLU fit restricted from {c.lambda_max:.1f} nm)"
                if _lmf is not None and effective_lambda_max < c.lambda_max
                else ""
            )
        )

        self.logger.info(f"Number of data points: {len(wls)}")

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

        self.logger.info(f"substrate: {c.substrate}")

        if c.is_frosted_glass:
            self.logger.info("Mode: Frosted Glass (Reflection only)")

        else:
            self.logger.info(f"Data type: {c.data_type.name}")

        target_T = None

        target_R = None

        if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
            if "T" in c.target_data.columns:
                target_T = c.target_data.loc[mask, "T"].to_numpy()

        if c.data_type in (DataType.REFLECTION, DataType.BOTH):
            if "R" in c.target_data.columns:
                target_R = c.target_data.loc[mask, "R"].to_numpy()

        # Filter valid values

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

        return wls, n_sub, target_T, target_R, exclude_range, obj

    def _run_phase5_final_optimization(self, obj: TLUObjective, params_list: list[np.ndarray]) -> None:
        """Run final full-grid refinement and update best solution if improved."""

        self.progress.emit(92, "Final ultimate optimization...", None)

        self.logger.info("\n--- PHASE 5: Final Ultimate Optimization (full grid) ---")

        try:
            if len(params_list) == 3:
                avg_params = np.mean(params_list, axis=0)

            else:
                avg_params = self.best_params

            _bf5 = obj.get_bounds()

            _lb5 = _bf5[:, 0]

            _ub5 = _bf5[:, 1]

            avg_params = clip_to_bounds(np.asarray(avg_params, dtype=np.float64).ravel(), _lb5, _ub5)

            # Phase 5a: L-BFGS-B with extreme precision

            res_final = scipy.optimize.minimize(
                obj,
                avg_params,
                method="L-BFGS-B",
                jac=obj.gradient,
                bounds=[(lb, ub) for lb, ub in obj.get_bounds()],
                options={"ftol": 1e-14, "gtol": 1e-14, "maxiter": 1000},
            )

            # Phase 5b: Nelder-Mead (no SciPy bounds) -> mandatory projection into the box.

            res_polish = scipy.optimize.minimize(
                obj,
                res_final.x,
                method="Nelder-Mead",
                options={"xatol": 1e-9, "fatol": 1e-14, "maxiter": 500},
            )

            x_nm_clip = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lb5, _ub5)

            mse_nm_clip = float(obj(x_nm_clip))

            if float(res_final.fun) <= mse_nm_clip:
                final_params, final_mse = res_final.x, float(res_final.fun)

            else:
                final_params, final_mse = x_nm_clip, mse_nm_clip

            if final_mse < self.best_mse:
                self.best_mse = final_mse

                self.best_params = final_params

                self.logger.info(f" Final optimization improved RMSE: {calculate_index_rmse(final_mse):.6f}")

                self._emit_live_best_snapshot()

            else:
                self.logger.info(f" Final optimization complete (RMSE unchanged: {calculate_index_rmse(self.best_mse):.6f})")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning(f"Final optimization failed: {e}")

    def _run_phase1_global_search(
        self,
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

            self.logger.info("High Precision Mode Enabled (80k evals)")

        else:
            max_evals = 20000

            self.logger.info("Standard Precision Mode (20k evals)")

        max_time = 240.0

        self.logger.info("\n--- PHASE 1: PGLOBAL Global Search ---")

        self.logger.info(f"Thickness range: {c.thickness_min:.1f} - {c.thickness_max:.1f} nm")

        self.logger.info(f"Max evaluations: {max_evals}")

        self.progress.emit(5, "Global Search...", None)

        pg_conf = PGlobalConfig.for_index(max_feval=max_evals, max_time=max_time)
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))

        # Constrain local search (limit evals). PGlobalConfig is frozen.
        pg_conf = pg_conf.with_overrides(local_search_budget=1500)

        self._optimizer = PGlobalOptimizerINDEX(
            obj,
            obj.get_bounds(),
            n_workers=1,
            config=pg_conf,
            log_clues=[2, 5],
            stop_event=self._stop_event,
        )

        phase1_cb = Phase1Callback(self, max_evals)

        self._phase1_obj = obj

        smart_x0 = estimate_initial_params(wls, target_T, n_sub)

        smart_x0[0] = float(self.thickness_initial)

        _bnds = obj.get_bounds()

        for _i in range(7):
            smart_x0[_i] = float(np.clip(smart_x0[_i], _bnds[_i, 0], _bnds[_i, 1]))

        self.logger.info(
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
            self.logger.info("TLU diag [warm start] | %s", obj.format_diag_line(smart_x0))

        except NUMERICAL_FAULT_EXCEPTIONS as _e_d0:
            self.logger.debug("TLU diag warm skip: %s", _e_d0)

        try:
            self.logger.info("TLU k [warm start / Phase1] | %s", obj.format_k_line(smart_x0))

        except NUMERICAL_FAULT_EXCEPTIONS as _e_k0:
            self.logger.debug("TLU k warm skip: %s", _e_k0)

        try:
            _y_ws = float(obj(smart_x0))

            if np.isfinite(_y_ws):
                self.best_mse = _y_ws

                self.best_params = smart_x0.copy()

                self.logger.info(
                    "TLU warm-start preview | RMSE = %.6f (traces avant 1er lot PGlobal)",
                    float(np.sqrt(max(0.0, _y_ws))),
                )

                self._emit_live_best_snapshot()

        except NUMERICAL_FAULT_EXCEPTIONS as _e_ws:
            self.logger.debug("TLU warm-start preview skipped: %s", _e_ws)

        # No x0 injected into PGLOBAL; warm start remains diagnostics + UI baseline.
        best = self._optimizer.optimize(max_iter=30, callback=phase1_cb)

        if best:
            rmse_best = np.sqrt(best.y)

            self.logger.info(
                f" PGLOBAL Pass 1 complete | Final RMSE: {rmse_best:.6f} | Total evals: {self._optimizer.n_evals}"
            )

        else:
            self.logger.warning(" PGLOBAL Pass 1 did not find a solution")

        if self._finalize_if_stopped():
            return True

        if best:
            self.best_params = best.x

            self.best_mse = best.y

            self._emit_live_best_snapshot()

        else:
            # Prefer best_params captured by callback over mid-range smart init fallback.
            if self.best_params is not None and np.isfinite(self.best_mse):
                self.logger.info(
                    f"Using callback-captured best params as fallback "
                    f"(RMSE={calculate_index_rmse(self.best_mse):.6f}, d={self.best_params[0]:.2f} nm)"
                )

                self._emit_live_best_snapshot()

            else:
                self.logger.info("Using Smart Initialization for fallback parameters...")

                smart_init = estimate_initial_params(wls, target_T, n_sub)

                smart_init[0] = (c.thickness_min + c.thickness_max) / 2

                self.best_params = smart_init

                self._emit_live_best_snapshot()

        return False

    def run(self) -> None:

        try:

            start_time = time.time()

            c = self.config

            wls, n_sub, target_T, target_R, exclude_range, obj = self._prepare_run_inputs(c)

            _setup_n_lo = float(N_MIN_LIMIT) + float(TLU_SOFT_EDGE_MARGIN)

            if getattr(obj, "_prior_transparent_low_k", False):
                _setup_n_lo = max(_setup_n_lo, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

            self.logger.info(
                "TLU setup Phase1 | Eg_min(bounds)=%.4f eV | k_soft_ceiling=%.5g | prior_lame_claire(T)=%s | "
                "budget_logs_k_pen=%d | hν_max=%.4f eV | n_lo_soft=%.3f",
                float(obj.param_bounds[0, 0]),
                float(getattr(obj, "_k_soft_ceiling", float("nan"))),
                getattr(obj, "_prior_transparent_low_k", False),
                int(getattr(obj, "_tlu_explode_logs_left", 0)),
                float(np.max(HC_EV_NM / np.maximum(wls, 1.0))),
                _setup_n_lo,
            )

            # === Phase 1: PGLOBAL ===

            if self._run_phase1_global_search(c, obj, wls, target_T, n_sub):
                return

            # === Phase 2: L-BFGS-B Polish ===

            self.logger.info("\n--- PHASE 2: L-BFGS-B Local Polish ---")

            self.progress.emit(60, "Polish...", None)

            # Callback to update display during Polish

            phase2_cb = Phase2PolishCallback(self)

            res = scipy.optimize.minimize(
                obj,
                self.best_params,
                method="L-BFGS-B",
                jac=obj.gradient,
                bounds=[(lb, ub) for lb, ub in obj.get_bounds()],
                callback=phase2_cb,
                options={"ftol": SMALL_EPSILON, "gtol": SMALL_EPSILON, "maxiter": 2000},
            )

            self.evals_update.emit(obj.n_evals)

            if res.fun < self.best_mse:
                self.best_mse = res.fun

                self.best_params = res.x

                rmse_polish = calculate_index_rmse(res.fun)

                self.logger.info(f" Polish complete | RMSE: {rmse_polish:.6f} | Evals: {obj.n_evals}")

                self._emit_live_best_snapshot()

            else:
                rmse_current = calculate_index_rmse(self.best_mse)

                self.logger.info(f" Polish complete | RMSE: {rmse_current:.6f} (unchanged)")

            # === Phase 3: L-BFGS-B Local Polish (remplace Coordinate Descent) ===

            if not self.is_stopped:
                self.logger.info("\n--- PHASE 3: L-BFGS-B Local Polish ---")

                self.progress.emit(75, "Fine tuning...", None)

                try:
                    exclude_range_p3 = (c.exclude_min, c.exclude_max) if c.exclude_min is not None else None

                    obj_p3 = TLUObjective(
                        wls,
                        target_T,
                        target_R,
                        n_sub,
                        c.data_type,
                        (c.thickness_min, c.thickness_max),
                        use_normalized=c.use_normalized,
                        weight_T=c.weight_T,
                        weight_R=c.weight_R,
                        exclude_range=exclude_range_p3,
                        is_frosted_glass=c.is_frosted_glass,
                    )

                    x0_p3 = self.best_params.copy()

                    # Bounds +/-5% around current solution, intersected with TLU global bounds

                    _fb = obj_p3.get_bounds()

                    bounds_p3 = []

                    for _ip in range(7):
                        _v = float(x0_p3[_ip])

                        _lo = max(float(_fb[_ip, 0]), _v * 0.95)

                        _hi = min(float(_fb[_ip, 1]), _v * 1.05)

                        if _lo > _hi:
                            _lo, _hi = float(_fb[_ip, 0]), float(_fb[_ip, 1])

                        bounds_p3.append((_lo, _hi))

                    res_p3 = scipy.optimize.minimize(
                        obj_p3,
                        x0_p3,
                        method="L-BFGS-B",
                        jac=obj_p3.gradient,
                        bounds=bounds_p3,
                        options={
                            "ftol": 1e-14,
                            "gtol": 1e-10,
                            "maxiter": 500,
                        },
                    )

                    if res_p3.fun < self.best_mse:
                        self.best_mse = res_p3.fun

                        self.best_params = res_p3.x

                        self.logger.info(f" Polish improved RMSE: {np.sqrt(res_p3.fun):.6f}")

                        self._emit_live_best_snapshot()

                    else:
                        self.logger.info("Polish did not improve solution (converged).")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.warning(f"Phase 3 polish failed: {e}")

            if self._finalize_if_stopped():
                return

            # === Phase 4: Residual Uncertainty (3-way Split) ===

            self.progress.emit(90, "Uncertainty (3-way split)...", None)

            # We perform 3 additional local optimizations on subsets of data

            # (mod 3 clues) to estimate sensitivity to sampling.

            # Delta_n = max deviation across all 3 pairs.

            params_list = []  # Will hold 3 param arrays (3-way split)

            if not self.is_stopped:
                try:
                    # os/sys : imports module (pas de import local ici : sinon UnboundLocalError sur os en tete de run())

                    from concurrent.futures import ThreadPoolExecutor

                    n_workers = min(3, get_safe_worker_count())

                    task_runner = SubsetOptimTask(self, wls, n_sub, target_T, target_R, exclude_range)

                    with ThreadPoolExecutor(max_workers=n_workers) as executor:
                        params_list = list(executor.map(task_runner, range(3)))

                    self.progress.emit(100, "Uncertainty calculation done.", None)

                    self.logger.info(" Residual uncertainty calculated (3-way split).")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.warning(f"Residual uncertainty calc failed: {e}")

            # === Phase 5: Final Ultimate Optimization (full grid) ===

            if not self.is_stopped:
                self._run_phase5_final_optimization(obj, params_list)

            if self._finalize_if_stopped(params_list=params_list):
                return

            self.progress.emit(95, "Packaging results...", None)

            # Out-of-bounds Nelder-safety net (e.g. Phase 4 sub-spectra) -> Eg ~ 0.03 eV in the report.

            if self.best_params is not None:
                _b_fix = obj.get_bounds()

                _xp = clip_to_bounds(
                    np.asarray(self.best_params, dtype=np.float64).ravel(),
                    _b_fix[:, 0],
                    _b_fix[:, 1],
                )

                if float(np.max(np.abs(_xp - np.asarray(self.best_params, dtype=np.float64).ravel()))) > 1e-8:
                    self.logger.warning(
                        "TLU: best_params projected within bounds before synthesis (Nelder or sub-spectra average)."
                    )

                    self.best_params = _xp

                    self.best_mse = float(obj(_xp))

            thickness_initial = getattr(self, "thickness_initial", None)

            if thickness_initial is None:
                if hasattr(self, "tlu_results"):
                    thickness_initial = self.tlu_results.optimal_thickness

                else:
                    thickness_initial = self.best_params[0]

                    self.logger.warning("OptimizationWorker: thickness_initial not set  variation will be 0.")

            thickness_optimized = self.best_params[0]

            thickness_variation = ((thickness_optimized - thickness_initial) / thickness_initial) * 100

            self.thickness_variation = thickness_variation

            tlu_params = TLUParameters.from_array(self.best_params[1:7])

            rmse_final = calculate_index_rmse(self.best_mse)

            self.logger.info("\n OPTIMIZATION COMPLETE")

            self.logger.info(f"Final RMSE: {rmse_final:.6f}")

            self.logger.info(f"Initial thickness: {thickness_initial:.4f} nm")

            self.logger.info(f"Optimized thickness: {thickness_optimized:.4f} nm")

            self.logger.info(f"Thickness variation: {thickness_variation:+.2f}%")

            self.logger.info(
                f"TLU Parameters: Eg={tlu_params.Eg:.3f} eV, A={tlu_params.A:.3f}, E0={tlu_params.E0:.3f} eV"
            )

            self.logger.info("=" * 80)

            # Package results

            results = self._package_results(thickness_optimized, tlu_params, params_list=params_list)

            self.progress.emit(100, "Done", None)

            self._cleanup()

            self.execution_time = time.time() - start_time

            try:
                status_val = (
                    ValidationStatus.WARNING_DATA_NORMALIZED
                    if bool(getattr(c, "use_normalized", False))
                    else ValidationStatus.OK
                )
                warnings_list = (
                    ["Input data normalized before optimization."] if bool(getattr(c, "use_normalized", False)) else []
                )
                svc = IndexFitService(runner=lambda _cfg: results)
                svc_resp = svc.fit(
                    IndexFitRequest(
                        config=c,
                        source_paths=[str(getattr(c, "source_file", "") or "")],
                        seed=getattr(c, "random_seed", None),
                        app_id="CERTUS_INDEX",
                        app_version=__version__,
                        warnings=warnings_list,
                        status=status_val,
                    )
                )
                stats = dict(getattr(results, "optimization_stats", {}) or {})
                stats["run_manifest"] = svc_resp.manifest.to_dict()
                results.optimization_stats = stats
            except NUMERICAL_FAULT_EXCEPTIONS as _e_manifest:
                self.logger.debug("IndexFitService manifest wiring skipped: %s", _e_manifest)

            self.finished.emit(results)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f" Optimization error: {e}")

            self.logger.error(traceback.format_exc())

            self._cleanup()

            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")

    def _cleanup(self) -> None:

        if self._optimizer:
            self._optimizer.cleanup()

            self._optimizer = None

    def _package_results(
        self,
        thickness: float,
        tlu_params: TLUParameters,
        params_list: list | None = None,
    ) -> OptimizationResults:
        """Package optimization results. params_list contains 3 param arrays for uncertainty."""

        c = self.config

        l_full = c.target_data["lambda"].to_numpy()

        E_full = HC_EV_NM / l_full

        if c.is_frosted_glass:
            n_sub = get_n_frosted_glass_array(l_full)

        else:
            sub_id = c.substrate_sellmeier_id if c.substrate_sellmeier_id is not None else -1

            n_sub = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)

        eps2 = epsilon2_TLU_array(
            E_full,
            tlu_params.Eg,
            tlu_params.A,
            tlu_params.E0,
            tlu_params.C,
            tlu_params.Eu,
        )

        eps1 = epsilon1_TL_analytic(
            E_full,
            tlu_params.Eg,
            tlu_params.A,
            tlu_params.E0,
            tlu_params.C,
            tlu_params.eps_inf,
        )

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)

        # Use shared source of truth for R/T calculation

        R_calc, T_calc, T_sub = _compute_RT_from_config(c, l_full, n_calc, k_calc, thickness, n_sub)

        with np.errstate(divide="ignore", invalid="ignore"):
            T_sub_safe = np.where(T_sub > T_SUB_MIN_T_NORM, T_sub, np.nan)

            T_norm_calc = np.nan_to_num(T_calc / T_sub_safe, nan=0.0)

            if c.is_frosted_glass:
                R_norm_calc = R_calc.copy()

            else:
                R_norm_calc = calculate_relative_R_normalization(R_calc, T_sub)

        # --- Residual Uncertainty Calculation (3-way split, max deviation) ---

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
            "alpha_cm-1": 4.0 * PI * k_calc / (l_full * 1e-7),
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

        # --- RECALCULATE RMSE ON FINAL DATA ---

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

        if "T" in c.target_data.columns and not c.is_frosted_glass:
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

        final_mse_recalc = self.best_mse

        if total_weight_recalc > 1e-9:
            final_mse_recalc = total_mse_recalc / total_weight_recalc

        # ``final_mse`` exposed to the UI / exports = same metric as the cost function (log-lambda weights, etc.),

        # i.e. ``self.best_mse``, to match the "Final RMSE" log lines. The uniform recalculation

        # above may differ (often lower) - we keep it for diagnostic purposes only.

        if np.isfinite(self.best_mse) and float(self.best_mse) < 1e99:
            final_mse_canonical = float(self.best_mse)

        else:
            final_mse_canonical = float(final_mse_recalc)

        stats = {
            "method": "PGLOBAL + L-BFGS-B + DeepRefine",
            "data_type": c.data_type.name,
            "substrate_mode": c.substrate_mode.name,
            "thickness_variation_pct": getattr(self, "thickness_variation", 0.0),
            "mse_uniform_grid_recalc": float(final_mse_recalc),
        }

        return OptimizationResults(
            config=c,
            optimal_thickness=thickness,
            final_mse=final_mse_canonical,
            df_results=df,
            tlu_params=tlu_params,
            optimization_stats=stats,
            execution_time=getattr(self, "execution_time", 0.0),
        )

class IndexBeamAnalysisWorker(QObject):
    """

    Worker for Beam Analysis (Index Determination).

    Scans thickness +/- 1nm and re-optimizes index parameters.

    """

    finished = pyqtSignal(list)

    progress = pyqtSignal(int, int)

    error = pyqtSignal(str)

    def __init__(
        self,
        start_params: np.ndarray,
        config: OptimizationConfig,  # Re-using config for data/weights/types
        scan_range_nm: float = 1.0,
        step_nm: float = 0.1,
    ) -> None:

        super().__init__()

        self.start_params = start_params

        self.config = config

        self.scan_range = scan_range_nm

        self.step = step_nm

        self.is_running = True

    def stop(self) -> None:

        self.is_running = False

    @pyqtSlot()
    def run(self) -> None:

        try:
            c = self.config

            # Prepare Data Args for Kernel (Same as OptimizationWorker setup)

            # Filter data

            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= c.lambda_max)

            wls = c.target_data.loc[mask, "lambda"].to_numpy()  # float64 default

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

            target_T = np.zeros_like(wls)

            target_R = np.zeros_like(wls)

            use_T = False

            use_R = False

            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()

                    use_T = True

            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()

                    use_R = True

            if not use_T and not use_R:
                self.error.emit("No valid target data for beam analysis.")

                return

            # Replace NaNs

            target_T = np.nan_to_num(target_T, nan=0.0)

            target_R = np.nan_to_num(target_R, nan=0.0)

            n_sub = np.nan_to_num(n_sub, nan=1.5)

            # --- Beam Analysis Scan (Factorized) ---

            self.error.emit("certus_thickness_scanner module is missing; Beam Analysis is currently disabled.")

            return

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(traceback.format_exc())

            self.error.emit(str(e))

# =============================================================================

# LOGGING SYSTEM - Using COMMON utilities

# =============================================================================

# QueueHandler and setup_gui_logger are imported from certus.core.certus_core

# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# =============================================================================

# UI COMPONENTS SPECIFIC TO INDEX

# =============================================================================

