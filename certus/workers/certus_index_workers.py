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
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
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
            self.state[0], self.state[1] = (sample.y, sample.x)
        now = time.time()
        if now - self.state[2] < 2.0:
            return
        self.state[2] = now
        self.worker.evals_update.emit(self.opt_instance.n_evals)
        if not self.emit_plot:
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message=self.title,
                    sub_message="IR global search",
                    progress_ratio=0.90,
                    display_ratio=0.90,
                    eta_seconds=None,
                    confidence=0.25,
                    module="INDEX",
                    phase="IRPGLOBAL",
                    metadata={"best_mse": float(self.state[0])},
                )
            )
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message=self.title,
                    sub_message="IR global search",
                    progress_ratio=0.90,
                    display_ratio=0.90,
                    eta_seconds=None,
                    confidence=0.25,
                    module="INDEX",
                    phase="IRPGLOBAL",
                    metadata={"best_mse": float(self.state[0])},
                )
            )
            return
        self.worker.best_params = self.state[1]
        self.worker.best_mse = self.state[0]
        rmse = np.sqrt(self.state[0])
        improved_for_plot = rmse < self.state[5] * 0.998
        heartbeat_plot = now - self.state[4] >= 10.0
        if not improved_for_plot and (not heartbeat_plot):
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message=self.title,
                    sub_message="IR global search",
                    progress_ratio=0.90,
                    display_ratio=0.90,
                    eta_seconds=None,
                    confidence=0.25,
                    module="INDEX",
                    phase="IRPGLOBAL",
                    metadata={"best_mse": float(self.state[0])},
                )
            )
            return
        n = sellmeier_2poles_eval_nj(self.state[1][:5], self.obj.wl_um)
        k = k_law_8p_eval(self.obj.wl_um, self.state[1][5:])
        Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)
        T_sub_norm = np.where(T_sub_c > 1e-09, T_sub_c, 1.0)
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
        if rmse < self.state[3] or now - self.state[4] >= 10.0:
            if rmse < self.state[3]:
                self.state[3] = rmse
            self.state[4] = now
            self.worker.logger.info(f"  [PGLOBAL] Evals: {self.opt_instance.n_evals:6d} | RMSE: {rmse:.6f}")
        self.worker.emit_progress_snapshot(
            build_progress_snapshot(
                message=self.title,
                sub_message="IR global search",
                progress_ratio=0.90,
                display_ratio=0.90,
                eta_seconds=None,
                confidence=0.25,
                module="INDEX",
                phase="IRPGLOBAL",
                metadata={"n": n, "k": k, "mse": float(self.state[0]), "plot_data": plot_data},
            )
        )


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
            T_sub_norm = np.where(T_sub_c > 1e-09, T_sub_c, 1.0)
            R_v = Rc / T_sub_norm if self.c.use_normalized else Rc
            T_v = Tc / T_sub_norm if self.c.use_normalized else Tc
            if self.c.is_frosted_glass:
                T_v = np.full_like(self.l_full, np.nan)
            _st, _sr = _index_live_spectrum_visibility(self.c)
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Stage 2 polish",
                    sub_message="IR stage 2",
                    progress_ratio=0.91,
                    display_ratio=0.91,
                    eta_seconds=None,
                    confidence=0.25,
                    module="INDEX",
                    phase="IRSTAGE2",
                    metadata={"n": n, "k": k, "mse": None},
                )
            )
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Stage 2 polish",
                    sub_message="IR stage 2",
                    progress_ratio=0.91,
                    display_ratio=0.91,
                    eta_seconds=None,
                    confidence=0.25,
                    module="INDEX",
                    phase="IRSTAGE2",
                    metadata={
                        "n": n,
                        "k": k,
                        "mse": None,
                        "R_calc": R_v,
                        "T_calc": T_v,
                        "live_show_T": _st,
                        "live_show_R": _sr,
                    },
                )
            )
        except NUMERICAL_FAULT_EXCEPTIONS:
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
            T_sub_norm = np.where(T_sub_c > 1e-09, T_sub_c, 1.0)
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
        except NUMERICAL_FAULT_EXCEPTIONS:
            return None

    def __call__(self, xk) -> bool:
        if time.time() - self._last_plot >= 1.5:
            self._last_plot = time.time()
            pd = self.get_plot_data(xk)
            if pd is not None:
                self.worker.emit_progress_snapshot(
                    build_progress_snapshot(
                        message=self.title,
                        sub_message="IR spline",
                        progress_ratio=0.99,
                        display_ratio=0.99,
                        eta_seconds=None,
                        confidence=0.2,
                        module="INDEX",
                        phase="IRSPLINE",
                        metadata={"mse": None},
                    )
                )
                self.worker.emit_progress_snapshot(
                    build_progress_snapshot(
                        message=self.title,
                        sub_message="IR spline",
                        progress_ratio=0.99,
                        display_ratio=0.99,
                        eta_seconds=None,
                        confidence=0.2,
                        module="INDEX",
                        phase="IRSPLINE",
                        metadata={"mse": None, "plot_data": pd},
                    )
                )
        if self.t0 is not None:
            return time.time() - self.t0 >= 10.0


class IRGlobalModelWorker(QObject):
    """

    Refined IR extension pipeline (>2500nm) using PGLOBAL with Sellmeier+EmpiricalK models.

    Replaces the legacy Spline-based approach.

    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str, object)
    progress_snapshot = pyqtSignal(object)
    evals_update = pyqtSignal(int)
    curve_update = pyqtSignal(object)

    def __init__(self, config: OptimizationConfig, tlu_results: OptimizationResults, logger=None) -> None:
        super().__init__()
        self.config = config
        self.tlu_results = tlu_results
        self.logger = logger or logging.getLogger("CertusIndex")
        self._stop_event = Event()
        self.best_mse = np.inf
        self.best_params = None

    def emit_progress_snapshot(self, snapshot) -> None:
        self.progress_snapshot.emit(snapshot)

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def _prepare_ir_phase2_inputs(self) -> tuple:
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._prepare_ir_phase2_inputs(self)

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
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._run_ir_stage0_to_stage2(
            self, c, l_full, n_sub_full, df_tlu, n_tlu_ref, obj, thickness
        )

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
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._run_phase21_refinement(
            self,
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
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._run_phase23_knot_reduction(
            self,
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
            initial_best_n=initial_best_n,
            initial_best_mse=initial_best_mse,
            initial_best_knot_lam=initial_best_knot_lam,
            initial_best_log_k=initial_best_log_k,
            initial_best_p_sell=initial_best_p_sell,
            n_final=n_final,
            k_final=k_final,
            p_opt_final=p_opt_final,
        )

    def _run_phase23_spline_refinement(
        self,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._run_phase23_spline_refinement(self, c, obj, res_pg, l_full, thickness, n_sub_full)

    def run(self) -> None:
        try:
            start_time = time.time()
            c = self.config
            l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness = self._prepare_ir_phase2_inputs()
            stage02 = self._run_ir_stage0_to_stage2(c, l_full, n_sub_full, df_tlu, n_tlu_ref, obj, thickness)
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
            n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values = (
                self._run_phase23_spline_refinement(c, obj, res_pg, l_full, thickness, n_sub_full)
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
            results.execution_time = duration
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
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Done (IR Refined)",
                    sub_message="IR pipeline complete",
                    progress_ratio=1.0,
                    display_ratio=1.0,
                    eta_seconds=0.0,
                    confidence=1.0,
                    module="INDEX",
                    phase="IRDONE",
                    metadata={"result_type": type(results).__name__},
                )
            )
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Done (IR Refined)",
                    sub_message="IR pipeline complete",
                    progress_ratio=1.0,
                    display_ratio=1.0,
                    eta_seconds=0.0,
                    confidence=1.0,
                    module="INDEX",
                    phase="IRDONE",
                    metadata={"result_type": type(results).__name__},
                )
            )
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
        from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy

        return IRGlobalModelStrategy._package_results(
            self, n, k, thickness, l_full, p_opt, n_T, k_T, p_T, k_spline_knots_lambda_um, k_spline_knots_values
        )


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
        return (Rc, nan_arr, nan_arr)
    elif getattr(c, "has_absorbing_substrate", False):
        Rc, Tc = calculate_RT_single_layer_absorbing_substrate_array(l_full, n, k, thickness, n_sub, _k_sub, _D_sub)
        Ts = calculate_bare_substrate_T_absorbing(l_full, n_sub, _k_sub, _D_sub)
        return (Rc, Tc, Ts)
    else:
        Rc, Tc = calculate_RT_single_layer_backside_array(l_full, n, k, thickness, n_sub)
        Ts = calculate_bare_substrate_RT(l_full, n_sub)
        return (Rc, Tc, Ts)


def _spectrum_visibility_target_traces(data_type: DataType, is_frosted_glass: bool) -> tuple[bool, bool]:
    """

    Indicates which T and R curves to display, aligned with TLUObjective

    and _update_spectrum_plot : T only if TRANSMISSION or BOTH (not frosted) ;

    R if REFLECTION, BOTH, or frosted substrate (R only).

    """
    show_t = not is_frosted_glass and data_type in (DataType.TRANSMISSION, DataType.BOTH)
    show_r = is_frosted_glass or data_type in (DataType.REFLECTION, DataType.BOTH)
    return (show_t, show_r)


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
        improved = not np.isfinite(self.worker.best_mse) or s.y < self.worker.best_mse
        if improved:
            self.worker._update_phase1_best(s)
            self.worker._try_active_update(s.x, s.y, force=True)
        now = time.time()
        if improved or now - self._last_status_emit >= 2.0:
            self._last_status_emit = now
            progress = min(60, int(60 * self.worker._optimizer.n_evals / self.max_evals))
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Global Search...",
                    sub_message="Phase 1",
                    progress_ratio=progress / 100.0,
                    display_ratio=progress / 100.0,
                    eta_seconds=None,
                    confidence=0.3,
                    module="INDEX",
                    phase="PHASE1",
                    metadata={"best_mse": float(self.worker.best_mse)},
                )
            )
            self.worker.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Global Search...",
                    sub_message="Phase 1",
                    progress_ratio=progress / 100.0,
                    display_ratio=progress / 100.0,
                    eta_seconds=None,
                    confidence=0.3,
                    module="INDEX",
                    phase="PHASE1",
                    metadata={"best_mse": float(self.worker.best_mse)},
                )
            )


class Phase2PolishCallback:
    def __init__(self, worker) -> None:
        self.worker = worker
        self.polish_iters = 0

    def __call__(self, xk) -> None:
        self.polish_iters += 1
        if self.worker.is_stopped:
            raise StopIteration
        prog_polish = min(75, 60 + int(15 * self.polish_iters / 200))
        self.worker.emit_progress_snapshot(
            build_progress_snapshot(
                message=f"Polish {self.polish_iters}",
                sub_message="Phase 2",
                progress_ratio=prog_polish / 100.0,
                display_ratio=prog_polish / 100.0,
                eta_seconds=None,
                confidence=0.3,
                module="INDEX",
                phase="PHASE2",
                metadata={"best_mse": float(self.worker.best_mse)},
            )
        )
        self.worker.emit_progress_snapshot(
            build_progress_snapshot(
                message=f"Polish {self.polish_iters}",
                sub_message="Phase 2",
                progress_ratio=prog_polish / 100.0,
                display_ratio=prog_polish / 100.0,
                eta_seconds=None,
                confidence=0.3,
                module="INDEX",
                phase="PHASE2",
                metadata={"best_mse": float(self.worker.best_mse)},
            )
        )
        self.worker._try_active_update(xk, self.worker.best_mse, force=False)


class OptimizationWorker(QObject):
    """Worker thread for optimization to keep UI responsive"""

    progress = pyqtSignal(int, str, object)
    progress_snapshot = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    evals_update = pyqtSignal(int)
    curve_update = pyqtSignal(object)

    def emit_progress_snapshot(self, snapshot) -> None:
        self.progress_snapshot.emit(snapshot)

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
        self.min_plot_interval = 1.0
        self.thickness_initial = config.fixed_thickness
        self._last_best_rmse_log_time = 0.0
        self._last_best_rmse_logged = float("inf")

    def _should_emit_active_update(self, now: float, force: bool) -> bool:
        """Return True when live plot refresh should be emitted."""
        if force:
            return now - self.last_plot_update_time > self.min_plot_interval
        return now - self.last_plot_update_time > 5.0

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
        now = time.time()
        significant_improvement = rmse < self._last_best_rmse_logged * 0.995
        time_elapsed = now - self._last_best_rmse_log_time >= 2.0
        if significant_improvement or time_elapsed:
            self._last_best_rmse_log_time = now
            self._last_best_rmse_logged = rmse
            n_ev = self._optimizer.n_evals if self._optimizer is not None else 0
            self.logger.info(
                f"  Best RMSE: {rmse:.6f} | Evaluations: {n_ev} | Thickness: {sample.x[0]:.2f} nm{_tlu_ex}{_k_inline}"
            )
        if _o1 is None and (not getattr(self, "_warned_phase1_missing_obj", False)):
            self.logger.warning(
                "Phase1 TLU diag/k unavailable (neither _phase1_obj nor _optimizer.objective) - run an up-to-date CERTUS_INDEX.py (e.g. folder 1904)."
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
                self.logger.info(
                    f"[LIVE VIEW] Emitted 5s live refresh signal | Index RMSE={np.sqrt(self.best_mse):.6f}"
                )

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
        from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy

        return IndexOptimizationStrategy()._run_subset_optim(
            self, clues_slice, wls, n_sub, target_T, target_R, exclude_range
        )

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
        self, c: OptimizationConfig
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None, tuple[float, float] | None, TLUObjective]:
        from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy

        return IndexOptimizationStrategy()._prepare_run_inputs(self, c)

    def _run_phase5_final_optimization(self, obj: TLUObjective, params_list: list[np.ndarray]) -> None:
        from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy

        return IndexOptimizationStrategy()._run_phase5_final_optimization(self, obj, params_list)

    def _run_phase1_global_search(
        self, c: OptimizationConfig, obj: TLUObjective, wls: np.ndarray, target_T: np.ndarray | None, n_sub: np.ndarray
    ) -> bool:
        from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy

        return IndexOptimizationStrategy()._run_phase1_global_search(self, c, obj, wls, target_T, n_sub)

    def run(self) -> None:
        try:
            start_time = time.time()
            c = self.config
            wls, n_sub, target_T, target_R, exclude_range, obj = self._prepare_run_inputs(c)
            _setup_n_lo = float(N_MIN_LIMIT) + float(TLU_SOFT_EDGE_MARGIN)
            if getattr(obj, "_prior_transparent_low_k", False):
                _setup_n_lo = max(_setup_n_lo, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))
            self.logger.info(
                "TLU setup Phase1 | Eg_min(bounds)=%.4f eV | k_soft_ceiling=%.5g | prior_transparent_substrate(T)=%s | budget_logs_k_pen=%d | hnu_max=%.4f eV | n_lo_soft=%.3f",
                float(obj.param_bounds[0, 0]),
                float(getattr(obj, "_k_soft_ceiling", float("nan"))),
                getattr(obj, "_prior_transparent_low_k", False),
                int(getattr(obj, "_tlu_explode_logs_left", 0)),
                float(np.max(HC_EV_NM / np.maximum(wls, 1.0))),
                _setup_n_lo,
            )
            if self._run_phase1_global_search(c, obj, wls, target_T, n_sub):
                return
            self.logger.info("\n--- PHASE 2: L-BFGS-B Local Polish ---")
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Polish...",
                    sub_message="Phase 3",
                    progress_ratio=0.60,
                    display_ratio=0.60,
                    eta_seconds=None,
                    confidence=0.35,
                    module="INDEX",
                    phase="PHASE3",
                )
            )
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
            if not self.is_stopped:
                self.logger.info("\n--- PHASE 3: L-BFGS-B Local Polish ---")
                self.emit_progress_snapshot(
                    build_progress_snapshot(
                        message="Fine tuning...",
                        sub_message="Phase 3",
                        progress_ratio=0.75,
                        display_ratio=0.75,
                        eta_seconds=None,
                        confidence=0.35,
                        module="INDEX",
                        phase="PHASE3",
                    )
                )
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
                    _fb = obj_p3.get_bounds()
                    bounds_p3 = []
                    for _ip in range(7):
                        _v = float(x0_p3[_ip])
                        _lo = max(float(_fb[_ip, 0]), _v * 0.95)
                        _hi = min(float(_fb[_ip, 1]), _v * 1.05)
                        if _lo > _hi:
                            _lo, _hi = (float(_fb[_ip, 0]), float(_fb[_ip, 1]))
                        bounds_p3.append((_lo, _hi))
                    res_p3 = scipy.optimize.minimize(
                        obj_p3,
                        x0_p3,
                        method="L-BFGS-B",
                        jac=obj_p3.gradient,
                        bounds=bounds_p3,
                        options={"ftol": 1e-14, "gtol": 1e-10, "maxiter": 500},
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
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Uncertainty (3-way split)...",
                    sub_message="Phase 4",
                    progress_ratio=0.90,
                    display_ratio=0.90,
                    eta_seconds=None,
                    confidence=0.35,
                    module="INDEX",
                    phase="PHASE4",
                )
            )
            params_list = []
            if not self.is_stopped:
                try:
                    from concurrent.futures import ThreadPoolExecutor

                    n_workers = min(3, get_safe_worker_count())
                    task_runner = SubsetOptimTask(self, wls, n_sub, target_T, target_R, exclude_range)
                    with ThreadPoolExecutor(max_workers=n_workers) as executor:
                        params_list = list(executor.map(task_runner, range(3)))
                    self.emit_progress_snapshot(
                        build_progress_snapshot(
                            message="Uncertainty calculation done.",
                            sub_message="Phase 4",
                            progress_ratio=1.0,
                            display_ratio=1.0,
                            eta_seconds=0.0,
                            confidence=1.0,
                            module="INDEX",
                            phase="PHASE4",
                            state=StepState.DONE,
                        )
                    )
                    self.logger.info(" Residual uncertainty calculated (3-way split).")
                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.warning(f"Residual uncertainty calc failed: {e}")
            if not self.is_stopped:
                self._run_phase5_final_optimization(obj, params_list)
            if self._finalize_if_stopped(params_list=params_list):
                return
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Packaging results...",
                    sub_message="Finalization",
                    progress_ratio=0.95,
                    display_ratio=0.95,
                    eta_seconds=None,
                    confidence=0.5,
                    module="INDEX",
                    phase="FINALIZE",
                )
            )
            if self.best_params is not None:
                _b_fix = obj.get_bounds()
                _xp = clip_to_bounds(np.asarray(self.best_params, dtype=np.float64).ravel(), _b_fix[:, 0], _b_fix[:, 1])
                if float(np.max(np.abs(_xp - np.asarray(self.best_params, dtype=np.float64).ravel()))) > 1e-08:
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
            thickness_variation = (thickness_optimized - thickness_initial) / thickness_initial * 100
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
            results = self._package_results(thickness_optimized, tlu_params, params_list=params_list)
            self.emit_progress_snapshot(
                build_progress_snapshot(
                    message="Done",
                    sub_message="Complete",
                    progress_ratio=1.0,
                    display_ratio=1.0,
                    eta_seconds=0.0,
                    confidence=1.0,
                    module="INDEX",
                    phase="DONE",
                    state=StepState.DONE,
                )
            )
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
        self, thickness: float, tlu_params: TLUParameters, params_list: list | None = None
    ) -> list[OptimizationResults]:
        from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy

        return IndexOptimizationStrategy()._package_results(self, thickness, tlu_params, params_list)


class IndexBeamAnalysisWorker(QObject):
    """

    Worker for Beam Analysis (Index Determination).

    Scans thickness +/- 1nm and re-optimizes index parameters.

    """

    finished = pyqtSignal(list)
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(
        self, start_params: np.ndarray, config: OptimizationConfig, scan_range_nm: float = 1.0, step_nm: float = 0.1
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
            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= c.lambda_max)
            wls = c.target_data.loc[mask, "lambda"].to_numpy()
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
            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and (not c.is_frosted_glass):
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()
                    use_T = True
            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()
                    use_R = True
            if not use_T and (not use_R):
                self.error.emit("No valid target data for beam analysis.")
                return
            target_T = np.nan_to_num(target_T, nan=0.0)
            target_R = np.nan_to_num(target_R, nan=0.0)
            n_sub = np.nan_to_num(n_sub, nan=1.5)
            self.error.emit("certus_thickness_scanner module is missing; Beam Analysis is currently disabled.")
            return
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(traceback.format_exc())
            self.error.emit(str(e))
