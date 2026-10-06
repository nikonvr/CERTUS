import logging
import time
import traceback

logger = logging.getLogger(__name__)
from typing import Any, Protocol

import numpy as np
from PyQt6.QtCore import QThread

from certus.core.certus_re_config import REPhase4Result, REWorkerRequest
from certus.utils.certus_progress_tracker import StepState, build_progress_snapshot
from certus.utils.certus_re_config import RE_RANKING_ALPHA_REF
from certus.utils.certus_re_results_builder import REResultsBuilder as REResultsPayloadBuilder
from certus.workers.certus_base_workers import WorkerSignals


class REWorker(QThread):
    """Two-stage RE: (1) TRF Deltaln(lambda) trapezoidal, thicknesses only, tabulated n;

    (2a) TRF DeltaRe splines only (thicknesses = end of phase 1);

    (2b) joint TRF thicknesses + splines + lambda₂ + optional Cauchy substrate (a0,a1,a2), tube |n-n_tab|<=Delta.

    Same index model as `re_apply_re_index_model` / `_compute_re_rmse`.

    """

    def __init__(self, cfg: dict[str, Any] | REWorkerRequest) -> None:
        super().__init__()
        self.request = cfg if isinstance(cfg, REWorkerRequest) else REWorkerRequest.from_legacy(cfg)
        self.cfg = dict(self.request.cfg)
        self.signals = WorkerSignals()
        self._stop = False
        self._last_live_emit_time = 0.0

    def request_stop(self) -> None:
        """Cooperative stop (Stop button  not only QThread.requestInterruption)."""
        self._stop = True

    def _build_cached_spline_correc(
        self,
        ctx,
        dh: np.ndarray,
        dl: np.ndarray,
        lam: float,
        tk_w_c: np.ndarray,
        cached: bool = True,
        b_mat_c: np.ndarray | None = None,
        env_c: np.ndarray | None = None,
        th4: np.ndarray | None = None,
    ) -> tuple:
        if ctx._use_sub_c3:
            th = th4 if th4 is not None else np.zeros(3)
            if cached:
                return (
                    "spline_cached_sub3", dh, dl, float(lam), b_mat_c, env_c, tk_w_c,
                    float(th[0]), float(th[1]), float(th[2]),
                )
            return (
                "spline_sub3", dh, dl, float(lam), tk_w_c,
                float(th[0]), float(th[1]), float(th[2]),
            )
        if cached:
            return ("spline_cached", dh, dl, float(lam), b_mat_c, env_c, tk_w_c)
        return ("spline", dh, dl, float(lam), tk_w_c)

    def _evaluate_p2_fd_derivative(
        self,
        ctx,
        j: int,
        xv64: np.ndarray,
        ep_x: np.ndarray,
        r_c: np.ndarray,
        b_mat_c: np.ndarray,
        env_c: np.ndarray,
        tk_w_c: np.ndarray,
        dh4: np.ndarray,
        dl4: np.ndarray,
        lam2: float,
        th4: np.ndarray | None,
    ) -> tuple[int, np.ndarray]:
        def _cor_sub3(_dh, _dl, _lam, _th) -> tuple:
            return (
                "spline_cached_sub3", _dh, _dl, float(_lam), b_mat_c, env_c, tk_w_c,
                float(_th[0]), float(_th[1]), float(_th[2]),
            )

        if ctx._use_sub_c3:
            if j < 2 * ctx._nk:
                dh_p = xv64[ctx.i0 : ctx.i0 + ctx._nk].copy()
                dl_p = xv64[ctx.i0 + ctx._nk : ctx.i_lam].copy()
                if j < ctx._nk:
                    dh_p[j] += ctx._p2fd_spl
                else:
                    dl_p[j - ctx._nk] += ctx._p2fd_spl
                cor_p = _cor_sub3(dh_p, dl_p, float(xv64[ctx.i_lam]), th4)
                h = ctx._p2fd_spl
            elif j == 2 * ctx._nk:
                lam_p = float(xv64[ctx.i_lam]) + ctx._p2fd_lam
                cor_p = (
                    "spline_sub3", dh4, dl4, lam_p, tk_w_c,
                    float(th4[0]), float(th4[1]), float(th4[2]),
                )
                h = ctx._p2fd_lam
            else:
                k = j - ctx.n_sp
                thp = np.array(th4, dtype=np.float64, copy=True)
                thp[k] += ctx._p2fd_cu
                cor_p = _cor_sub3(dh4, dl4, lam2, thp)
                h = ctx._p2fd_cu
        elif j < 2 * ctx._nk:
            dh_p = xv64[ctx.i0 : ctx.i0 + ctx._nk].copy()
            dl_p = xv64[ctx.i0 + ctx._nk : ctx.i_lam].copy()
            if j < ctx._nk:
                dh_p[j] += ctx._p2fd_spl
            else:
                dl_p[j - ctx._nk] += ctx._p2fd_spl
            cor_p = self._build_cached_spline_correc(
                ctx, dh_p, dl_p, float(xv64[ctx.i_lam]), tk_w_c,
                cached=True, b_mat_c=b_mat_c, env_c=env_c,
            )
            h = ctx._p2fd_spl
        else:
            lam_p = float(xv64[ctx.i_lam]) + ctx._p2fd_lam
            cor_p = ("spline", dh4, dl4, lam_p, tk_w_c)
            h = ctx._p2fd_lam

        r_p = ctx._mse_grad_accumulate_ep(
            ep_x, ctx.wt_spectral, False, cor_p, return_residuals=True,
        )[2]
        if ctx._fd_1s:
            return j, (r_p - r_c) / h

        if ctx._use_sub_c3:
            if j < 2 * ctx._nk:
                dh_m = xv64[ctx.i0 : ctx.i0 + ctx._nk].copy()
                dl_m = xv64[ctx.i0 + ctx._nk : ctx.i_lam].copy()
                if j < ctx._nk:
                    dh_m[j] -= ctx._p2fd_spl
                else:
                    dl_m[j - ctx._nk] -= ctx._p2fd_spl
                cor_m = self._build_cached_spline_correc(
                    ctx, dh_m, dl_m, float(xv64[ctx.i_lam]), tk_w_c,
                    th4=th4, cached=True, b_mat_c=b_mat_c, env_c=env_c,
                )
            elif j == 2 * ctx._nk:
                lam_m = float(xv64[ctx.i_lam]) - ctx._p2fd_lam
                cor_m = self._build_cached_spline_correc(
                    ctx, dh4, dl4, lam_m, tk_w_c,
                    th4=th4, cached=False, b_mat_c=b_mat_c, env_c=env_c,
                )
            else:
                k = j - ctx.n_sp
                thm = np.array(th4, dtype=np.float64, copy=True)
                thm[k] -= ctx._p2fd_cu
                cor_m = _cor_sub3(dh4, dl4, lam2, thm)
        elif j < 2 * ctx._nk:
            dh_m = xv64[ctx.i0 : ctx.i0 + ctx._nk].copy()
            dl_m = xv64[ctx.i0 + ctx._nk : ctx.i_lam].copy()
            if j < ctx._nk:
                dh_m[j] -= ctx._p2fd_spl
            else:
                dl_m[j - ctx._nk] -= ctx._p2fd_spl
            cor_m = (
                "spline_cached", dh_m, dl_m, float(xv64[ctx.i_lam]),
                b_mat_c, env_c, tk_w_c,
            )
        else:
            lam_m = float(xv64[ctx.i_lam]) - ctx._p2fd_lam
            cor_m = ("spline", dh4, dl4, lam_m, tk_w_c)

        r_m = ctx._mse_grad_accumulate_ep(
            ep_x, ctx.wt_spectral, False, cor_m, return_residuals=True,
        )[2]
        return j, (r_p - r_m) / (2.0 * h)

    def _execute_phase1(self) -> list[dict]:
        from certus.core.certus_re_solvers import re_execute_phase1
        return re_execute_phase1(self)

    def _execute_phase1_p4_scan(self) -> None:
        from certus.core.certus_re_solvers import re_execute_phase1_p4_scan
        return re_execute_phase1_p4_scan(self)

    def _execute_phase2_splines(self) -> None:
        from certus.core.certus_re_solvers import re_execute_phase2_splines
        return re_execute_phase2_splines(self)

    def _execute_phase2_candidate(self, *args, **kwargs):
        from certus.core.certus_re_solvers import re_execute_phase2_candidate
        return re_execute_phase2_candidate(self, *args, **kwargs)

    def _run_phase4_joint_trf(self, *args, **kwargs):
        from certus.core.certus_re_solvers import re_run_phase4_joint_trf
        return re_run_phase4_joint_trf(self, *args, **kwargs)

    def _execute_phase3_shakes(self) -> None:
        from certus.workers.certus_re_workers_phase3 import REPhase3Strategy
        return REPhase3Strategy._execute_phase3_shakes(None, self)

    def _finalize_re_run(self, **kwargs) -> None:
        from certus.workers.certus_re_workers_context import REContextStrategy
        return REContextStrategy._finalize_re_run(self, **kwargs)

    def _emit_re_spectrum_live_helper(self, ep_vec: np.ndarray, evals: int, **kwargs) -> None:
        from certus.workers.certus_re_workers_context import REContextStrategy
        return REContextStrategy._emit_re_spectrum_live_helper(self, ep_vec, evals, **kwargs)

    def _build_re_run_context(self, _re_t0: float) -> Any:
        from certus.workers.certus_re_workers_context import REContextStrategy
        return REContextStrategy._build_re_run_context(self, _re_t0)

    def _compute_eval_both_p2(self, ctx, xv: np.ndarray, emit_interval: float=5.0) -> tuple | None:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_eval_both_p2(self, ctx, xv, emit_interval)

    def _compute_fun_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float=5.0) -> Any:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_fun_res_p2(self, ctx_p2, xv, emit_interval)

    def _compute_jac_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float=5.0) -> Any:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_jac_res_p2(self, ctx_p2, xv, emit_interval)

    def _compute_eval_both_p2a(self, ctx, x_sp: np.ndarray, _cb2a, ep_p1, _ki, _t_pf) -> tuple | None:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_eval_both_p2a(self, ctx, x_sp, _cb2a, ep_p1, _ki, _t_pf)

    def _compute_fun_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_fun_res_p2a(self, ctx_p2, x_sp, _cb2a)

    def _compute_jac_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:
        from certus.workers.certus_re_workers_math import REMathStrategy
        return REMathStrategy._compute_jac_res_p2a(self, ctx_p2, x_sp, _cb2a)

    def _execute_re_phases(self) -> None:
        """Orchestrate RE phases in nominal order."""
        REPhasesService(self).execute_all()

    def _finalize_from_context(self, fin) -> None:
        """Finalization adapter using the context built upstream."""
        _alpha_rank_ref = float(self.cfg.get('re_ranking_alpha_ref', RE_RANKING_ALPHA_REF))
        self._finalize_re_run(results=fin.results, rmse_initial_sp=fin.rmse_initial_sp, rmse_initial_q=fin.rmse_initial_q, rmse_initial_u=fin.rmse_initial_u, rmse_initial_milestone=fin.rmse_initial_milestone, rmse_phase1_milestone=fin.rmse_phase1_milestone, rmse_final_milestone=fin.rmse_final_milestone, _alpha_slot=fin._alpha_slot, _alpha_rank_ref=_alpha_rank_ref, re_qwot_alphas=(float(fin._a_p1), float(fin._a_p2a), float(fin._a_p2b), float(fin._a_p3)), _compute_qwot_rmse_raw=fin._compute_qwot_rmse_raw, _compute_qwot_rmse=fin._compute_qwot_rmse, _correc_nom=fin._correc_nom, _emit_re_spectrum_live=fin._emit_re_spectrum_live, _report_t0=fin._re_t0, _re_pct_hi=fin._re_pct_hi, n_sub_nominal=fin.n_sub_nominal, wls=fin.wls, lambda_ref=fin.lambda_ref, ep0=fin.ep0, _thickness_uncertainty=getattr(fin, '_thickness_uncertainty', None))

    def _run_re_workflow(self) -> None:
        """Nominal body of the RE thread (without UI error handling)."""
        logger.debug('_run_re_workflow start')
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='building context', progress_ratio=0.01, display_ratio=0.01, eta_seconds=None, confidence=0.2, state=StepState.RUNNING, module='RE', phase='START', is_indeterminate=True))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='building context', progress_ratio=0.02, display_ratio=0.02, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='RE', phase='BUILD_CONTEXT', is_indeterminate=True))
        _re_t0 = time.perf_counter()
        fin = self._build_re_run_context(_re_t0)
        logger.debug('_run_re_workflow context built')
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='context built', progress_ratio=0.15, display_ratio=0.15, eta_seconds=None, confidence=0.3, state=StepState.RUNNING, module='RE', phase='PHASES_START'))
        self._execute_re_phases()
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='finalizing', progress_ratio=0.95, display_ratio=0.95, eta_seconds=None, confidence=0.2, state=StepState.RUNNING, module='RE', phase='FINALIZE'))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='phases done, finalizing', progress_ratio=0.90, display_ratio=0.90, eta_seconds=None, confidence=0.35, state=StepState.RUNNING, module='RE', phase='FINALIZE'))
        self._finalize_from_context(fin)
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='finished', progress_ratio=1.0, display_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module='RE', phase='DONE'))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE workflow', sub_message='finished', progress_ratio=1.0, display_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module='RE', phase='DONE'))

    def run(self) -> None:
        logger.info('RE worker run started')
        self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE worker', sub_message='thread started', progress_ratio=0.0, display_ratio=0.0, eta_seconds=None, confidence=0.2, state=StepState.RUNNING, module='RE', phase='START'))
        try:
            self._run_re_workflow()
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception('RE worker run failed: %s', e)
            self.signals.progress_snapshot.emit(build_progress_snapshot(message='RE worker', sub_message=f'exception: {e}', progress_ratio=None, display_ratio=None, eta_seconds=None, confidence=0.0, state=StepState.ERROR, module='RE', phase='ERROR', metadata={'exception': str(e)}))
            self.signals.error.emit(tb)
            self.signals.finished.emit(REResultsPayloadBuilder.build_error_payload(self.cfg.get('ep0')))

    def _get_phase4_aperture_bounds(self) -> tuple[float, float]:
        from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
        return REPhase4Strategy._get_phase4_aperture_bounds(None, self)

    def _run_phase4_aperture_scan(self, **kwargs) -> tuple[list[tuple[float, float]], float, float, float, int, float]:
        from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
        return REPhase4Strategy._run_phase4_aperture_scan(None, self, **kwargs)

    def _get_phase4_scan_inputs(self, x0_base: np.ndarray, _nap: int, _ap_gui: float, wls: np.ndarray, oblique_config_meta: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float], list[float], str]:
        from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
        return REPhase4Strategy._get_phase4_scan_inputs(None, self, x0_base, _nap, _ap_gui, wls, oblique_config_meta)

    def _build_phase4_result(self, **kwargs) -> tuple[REPhase4Result, float]:
        from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
        return REPhase4Strategy._build_phase4_result(None, self, **kwargs)

    def _execute_phase4_beam(self) -> None:
        from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
        return REPhase4Strategy._execute_phase4_beam(None, self)

class REPhasesService:
    """Thin service layer to orchestrate RE worker phases."""

    def __init__(self, worker: REWorker, steps: list[REPhaseStep] | None=None, state_service: REPhaseStateService | None=None) -> None:
        self._worker = worker
        self._state_service = state_service or REPhaseStateService()
        self._steps = steps or [REPhase1Step(), REPhase1P4ScanStep(), REPhase2Step(), REPhase3Step(), REPhase4Step()]

    def execute_phase1(self) -> None:
        w = self._worker
        w._re_phase_ns.results[:] = w._execute_phase1()

    def execute_phase1_p4_scan(self) -> None:
        self._worker._execute_phase1_p4_scan()

    def execute_phase2(self) -> None:
        w = self._worker
        self._state_service.prepare_phase2_state(w)
        w._execute_phase2_splines()

    def execute_phase3(self) -> None:
        self._worker._execute_phase3_shakes()

    def execute_phase4(self) -> None:
        self._worker._execute_phase4_beam()

    def execute_all(self) -> None:
        for step in self._steps:
            step.run(self)

class REPhaseStep(Protocol):
    """Contract for one executable RE phase step."""

    def run(self, service: REPhasesService) -> None:
        ...

class REPhaseStateService:
    """State transitions extracted from worker for phase orchestration."""

    def prepare_phase2_state(self, worker: REWorker) -> None:
        worker._re_phase_ns._re_state['is_phase4'] = False
        worker._re_phase_ns._use_sub_c3_shared = False
        worker._re_phase_ns._p2_ctx = {}

class REPhase1Step:

    def run(self, service: REPhasesService) -> None:
        service.execute_phase1()

class REPhase1P4ScanStep:

    def run(self, service: REPhasesService) -> None:
        service.execute_phase1_p4_scan()

class REPhase2Step:

    def run(self, service: REPhasesService) -> None:
        service.execute_phase2()

class REPhase3Step:

    def run(self, service: REPhasesService) -> None:
        service.execute_phase3()

class REPhase4Step:

    def run(self, service: REPhasesService) -> None:
        service.execute_phase4()
