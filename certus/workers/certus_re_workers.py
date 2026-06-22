from certus.utils.certus_re_math import re_envelope_max_delta_n
from certus.utils.certus_re_config import RE_PHASE4_TRF_TOL_FACTOR
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_config import RE_P4_AP_FD_STEP_DEG
from certus.utils.certus_re_config import RE_LBFGSB_GTOL
from certus.utils.certus_re_config import RE_LBFGSB_FTOL
from certus.utils.certus_re_math import re_compute_tikhonov_weights
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_math import re_substrate_cauchy_barrier_residuals_jac
from certus.utils.certus_re_math import re_substrate_cauchy_phi_matrix, re_envelope_max_delta_n
import time
import traceback
import logging
from pathlib import Path
logger = logging.getLogger(__name__)
from concurrent.futures import ThreadPoolExecutor, as_completed
import joblib
from functools import partial
from types import SimpleNamespace
from typing import Any, Protocol, Callable
import numpy as np
from scipy.optimize import least_squares
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
from certus.core.certus_re_config import REWorkerRequest, REPhase3Result, REPhase4Result, _top_result_dto, _set_top_result_dto, _prepend_result_dto, RE_RESULT_LABEL_WITH_DRIFT
from certus.utils.certus_re_helpers import _re_apply_correc, _re_correc_to_nk_preview_payload, _re_calc_spectrum_for_config, _re_p4_ap_band_intervals_str, _re_log_objective_diagnostic, RE_GUI_DEFAULT_BEAM_APERTURE_DEG, _re_sort_results_best_for_table_and_apply, re_knots_wavelengths, _re_trf_residual_rms
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_PHASE3_SHAKES, RE_SUB_CAUCHY_BARRIER_SQRT_W, RE_SUB_CAUCHY_TUBE_DELTA, RE_LBFGSB_FTOL, RE_LBFGSB_GTOL, RE_GUI_DEFAULT_RE_PHASE1_RESTARTS, RE_P4_BEAM_AP_BOUNDS_DEG, RE_GUI_DEFAULT_RE_PHASE2_TOP_K, RE_GUI_DEFAULT_RE_QWOT_ALPHA, RE_P4_AP_FD_STEP_DEG, RE_P4_BEAM_N_KNOTS, RE_PHASE2B_MAXITER, RE_PHASE2_SPLINE_PREFIT_MAXITER, RE_PHASE4_APERTURE_SCAN_POINTS, RE_PHASE4_TRF_MAX_NFEV, RE_PHASE4_TRF_TOL_FACTOR, RE_RANKING_ALPHA_REF
from certus.utils.certus_re_math import re_compute_spline_basis_matrix, re_compute_tikhonov_weights

from certus.workers.certus_re_worker_utils import shake_sigmas_adaptive, p2_result_to_correc_tuple, re_enrich_results_ranking_fields, re_finalize_ranking_log_suffix, re_finalize_finished_main_log_line, re_finalize_rmse_milestone_log_line, re_finalize_progress_message_done, re_live_plot_wls_and_dispersion_nk, re_trf_thickness_bounds, re_trf_bounds_scipy_tuples, re_phase1_trf_runs_multistart, RE_CORREC_NOMINAL_PCT, re_build_p2_progress_plan, re_progress_pct_p1, re_progress_pct_p2a, re_progress_pct_p2b, re_progress_pct_p3, resolve_re_qwot_alphas
from certus.utils.certus_re_results_builder import REResultsBuilder as REResultsPayloadBuilder
from certus.core.certus_re_solvers import REUserStopRequested
from certus.ui.certus_qt_widgets import QThread
from certus.ui.certus_ui import WorkerSignals
from certus.core.certus_re_objectives import _prepare_re_run_context_setup, _build_re_mse_grad_helper, _build_qwot_helpers

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

    def request_stop(self) -> None:
        """Cooperative stop (Stop button  not only QThread.requestInterruption)."""
        self._stop = True

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
        self._finalize_re_run(results=fin.results, rmse_initial_sp=fin.rmse_initial_sp, rmse_initial_q=fin.rmse_initial_q, rmse_initial_u=fin.rmse_initial_u, rmse_initial_milestone=fin.rmse_initial_milestone, rmse_phase1_milestone=fin.rmse_phase1_milestone, rmse_final_milestone=fin.rmse_final_milestone, _alpha_slot=fin._alpha_slot, _alpha_rank_ref=_alpha_rank_ref, re_qwot_alphas=(float(fin._a_p1), float(fin._a_p2a), float(fin._a_p2b), float(fin._a_p3)), _compute_qwot_rmse_raw=fin._compute_qwot_rmse_raw, _compute_qwot_rmse=fin._compute_qwot_rmse, _correc_nom=fin._correc_nom, _emit_re_spectrum_live=fin._emit_re_spectrum_live, _report_t0=fin._re_t0, _re_pct_hi=fin._re_pct_hi, n_sub_nominal=fin.n_sub_nominal, wls=fin.wls, lambda_ref=fin.lambda_ref, ep0=fin.ep0)

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

    def __init__(self, worker: REWorker, steps: list['REPhaseStep'] | None=None, state_service: 'REPhaseStateService | None'=None) -> None:
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