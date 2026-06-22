from certus.utils.certus_re_math import re_envelope_max_delta_n
from certus.utils.certus_re_config import RE_LBFGSB_GTOL
from certus.utils.certus_re_config import RE_LBFGSB_FTOL
from certus.utils.certus_re_math import re_substrate_cauchy_barrier_residuals_jac
from certus.utils.certus_re_math import re_substrate_cauchy_phi_matrix
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_SUB_CAUCHY_BARRIER_SQRT_W
from certus.utils.certus_re_config import RE_SUB_CAUCHY_TUBE_DELTA
import logging
import time
import math
from copy import deepcopy
from pathlib import Path
from functools import partial
from types import SimpleNamespace
from typing import Any, Callable
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
import numpy as np

logger = logging.getLogger(__name__)

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_re_config import REPhase3Result, REPhase4Result
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_PHASE1_RESTARTS, RE_GUI_DEFAULT_RE_PHASE2_TOP_K, RE_PHASE2_SPLINE_PREFIT_MAXITER, RE_PHASE2B_MAXITER
from certus.utils.certus_re_helpers import (
    _re_apply_correc,
    _re_correc_to_nk_preview_payload,
    _re_calc_spectrum_for_config,
    _re_log_objective_diagnostic,
    _re_sort_results_best_for_table_and_apply,
)
from certus.workers.certus_re_worker_utils import (
    p2_result_to_correc_tuple,
    re_enrich_results_ranking_fields,
    re_finalize_ranking_log_suffix,
    re_finalize_finished_main_log_line,
    re_finalize_rmse_milestone_log_line,
    re_finalize_progress_message_done,
    re_trf_bounds_scipy_tuples,
    re_build_p2_progress_plan,
    re_progress_pct_p1,
    re_progress_pct_p2a,
    re_progress_pct_p2b,
    re_progress_pct_p3,
    re_live_plot_wls_and_dispersion_nk,
    re_trf_thickness_bounds,
    re_phase1_trf_runs_multistart,
    RE_CORREC_NOMINAL_PCT,
    resolve_re_qwot_alphas,
)
from certus.utils.certus_re_results_builder import REResultsBuilder as REResultsPayloadBuilder
from certus.core.certus_re_objectives import _prepare_re_run_context_setup, _build_re_mse_grad_helper, _build_qwot_helpers

class REContextStrategy:
    def _finalize_re_run(worker, *, results: list[dict], rmse_initial_sp: float, rmse_initial_q: float, rmse_initial_u: float, rmse_initial_milestone: list[float], rmse_phase1_milestone: list[float], rmse_final_milestone: list[float], _alpha_slot: list[float], _alpha_rank_ref: float, re_qwot_alphas: tuple[float, float, float, float], _compute_qwot_rmse_raw, _compute_qwot_rmse, _correc_nom: tuple, _emit_re_spectrum_live, _report_t0: float, _re_pct_hi: list[float], n_sub_nominal: np.ndarray, wls: np.ndarray, lambda_ref: float, ep0: np.ndarray) -> None:
        """Sort/finalize RE results, emit final spectrum, logs and finished payload."""
        _top_result = REResultsPayloadBuilder.finalize_reconcile_top(results=results, stop_requested=bool(worker._stop), cfg_ep0=worker.cfg.get('ep0'), rmse_initial_sp=rmse_initial_sp, rmse_initial_q=rmse_initial_q, rmse_initial_u=rmse_initial_u, alpha_rank_ref=_alpha_rank_ref, compute_qwot_rmse_raw=_compute_qwot_rmse_raw, sort_results=_re_sort_results_best_for_table_and_apply, enrich_results=re_enrich_results_ranking_fields)
        _top_dto = REPhase4Result.from_legacy_dict(_top_result) if _top_result else None
        if _top_dto is not None:
            rmse_final_milestone[0] = float(_top_dto.rmse_combined)
        _stop_live_payload = REResultsPayloadBuilder.stop_live_emit_payload(stop_requested=bool(worker._stop), top_result=_top_result, correc_nominal=_correc_nom, p2_to_correc=p2_result_to_correc_tuple)
        if _stop_live_payload is not None:
            _emit_re_spectrum_live(_stop_live_payload['ep'], _stop_live_payload['nfev'], correc=_stop_live_payload['correc'], force=bool(_stop_live_payload['force']), rmse_override=float(_stop_live_payload['rmse_override']))
        _tot = time.perf_counter() - _report_t0
        _top_metrics = REResultsPayloadBuilder.top_metrics(_top_result)
        _best_sp = float(_top_metrics['best_sp'])
        _best_ot = float(_top_metrics['best_ot'])
        _best = float(_top_metrics['best_combined'])
        rmse_final_u = float(_top_metrics['rmse_final_u'])
        if results:
            _a_gui = float(worker.cfg.get('re_qwot_penalty_weight', RE_GUI_DEFAULT_RE_QWOT_ALPHA))
            _diag_payload = REResultsPayloadBuilder.final_diagnostic_payload(best_sp=float(_best_sp), best_ot=float(_best_ot), alpha_current=float(_alpha_slot[0]), alpha_gui=_a_gui, rmse_final_u=float(rmse_final_u), rmse_initial_u=float(rmse_initial_u), rmse_initial_sp=float(rmse_initial_sp), rmse_initial_q=float(rmse_initial_q))
            logging.info('RE  final summary (progress readout / e.g. reverse_sample.xlsx) ')
            _re_log_objective_diagnostic('final ( from last TRF phase)', _diag_payload['best_sp'], _diag_payload['ot_fin'], _diag_payload['alpha_current'])
            _re_log_objective_diagnostic('final (same sp/QWOT,  from base cfg / preset  comparison)', _diag_payload['best_sp'], _diag_payload['ot_fin'], _diag_payload['alpha_gui'])
            logging.info('RE summary  gains vs init: Delta RMSE=%+.6f | Delta sp=%+.6f | Delta QWOT=%+.6f', _diag_payload['delta_rmse'], _diag_payload['delta_sp'], _diag_payload['delta_qwot'])
            _cauchy_diag = REResultsPayloadBuilder.cauchy_barrier_diagnostic_payload(top_result=_top_result, wls=wls, lambda_ref=lambda_ref, n_sub_nominal=n_sub_nominal, barrier_sqrt_w=float(worker.cfg.get('re_sub_cauchy_barrier_sqrt_w', RE_SUB_CAUCHY_BARRIER_SQRT_W)), tube_delta=float(RE_SUB_CAUCHY_TUBE_DELTA), substrate_phi_matrix=re_substrate_cauchy_phi_matrix, barrier_residuals_jac=re_substrate_cauchy_barrier_residuals_jac)
            if _cauchy_diag is not None:
                logging.info('RE diag [Cauchy substrate barrier] ||r||=%.4g, %d/%d non-zero residuals (tube |nn_tab|<=%.3g)  active boundary -> constraint saturated; zeros -> inside tube.', _cauchy_diag['res_norm'], _cauchy_diag['n_active'], _cauchy_diag['n_total'], _cauchy_diag['tube_delta'])
        _tail = REResultsPayloadBuilder.finalize_tail_bundle(results=results, top_result=_top_result, ep0=ep0, alpha_rank_ref=_alpha_rank_ref, elapsed_s=_tot, best_sp=_best_sp, best_ot=_best_ot, best_combined=_best, rmse_initial_milestone=rmse_initial_milestone, rmse_phase1_milestone=rmse_phase1_milestone, rmse_final_milestone=rmse_final_milestone, stopped_by_user=bool(worker._stop), re_qwot_alphas=re_qwot_alphas, ranking_log_suffix=re_finalize_ranking_log_suffix, finished_main_log_line=re_finalize_finished_main_log_line, rmse_milestone_log_line=re_finalize_rmse_milestone_log_line, progress_message_done=re_finalize_progress_message_done)
        logging.info(_tail['finished_main_log'])
        logging.info(_tail['rmse_milestone_log'])
        _re_pct_hi[0] = 100.0
        worker.signals.progress_snapshot.emit(build_progress_snapshot(message=_tail['progress_done'], display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module='RE', phase='DONE', metadata={'tail': True}))
        worker.signals.finished.emit(_tail['finished_payload'])

    def _emit_re_spectrum_live_helper(worker, ep_vec: np.ndarray, evals: int, *, correc: tuple, last_mse: float | None, force: bool, rmse_override: float | None, _re_live_emit: dict, n_lay_disp: np.ndarray, n_sub_disp: np.ndarray, is_H: np.ndarray, is_L: np.ndarray, wls_display: np.ndarray, lambda_ref: float, re_env_s: float, _re_env_on_wls_disp: np.ndarray, _mse_grad_accumulate_ep, wt_spectral: np.ndarray, _compute_qwot_rmse, _alpha_slot: list, _rmse_combined, oblique_config_meta: list, _re_state: dict, _ap_gui: float, oblique_tgts: list) -> None:
        if worker._stop and (not force):
            return
        now_te = time.perf_counter()
        if not force and _re_live_emit['t'] > 0.0 and (now_te - _re_live_emit['t'] < 5.0):
            return
        _re_live_emit['t'] = now_te
        try:
            ep_use = np.asarray(ep_vec, dtype=np.float64).flatten()
            n_lm, n_sm = _re_apply_correc(n_lay_disp, n_sub_disp, is_H=is_H, is_L=is_L, wls=wls_display, lambda_ref=lambda_ref, correc=correc, re_env_s=re_env_s, env_cache=_re_env_on_wls_disp)
            n_lay_T_corr = np.ascontiguousarray(n_lm.T)
            n_sub_use = np.ascontiguousarray(n_sm)
            if last_mse is not None and np.isfinite(last_mse):
                rs = float(np.sqrt(max(float(last_mse), 0.0)))
            else:
                _sp_mse = float(_mse_grad_accumulate_ep(ep_use, wt_spectral, False, correc)[0])
                rs = float(np.sqrt(max(_sp_mse, 0.0)))
            rq = float(_compute_qwot_rmse(ep_use, correc))
            al_q = float(_alpha_slot[0])
            if rmse_override is not None and np.isfinite(rmse_override):
                rmse_d = float(rmse_override)
            else:
                rmse_d = _rmse_combined(rs, rq)
            spectra_display = {}
            display_keys_done = set()
            for meta in oblique_config_meta:
                angle = float(meta['angle'])
                pol = str(meta['pol'])
                inc_back = bool(meta['include_backside'])
                dkey = (angle, pol, inc_back)
                if dkey in display_keys_done:
                    continue
                display_keys_done.add(dkey)
                R_o, T_o = _re_calc_spectrum_for_config(wls_display, n_lay_T_corr, ep_use, n_sub_use, angle, pol, inc_back, phase4_average=_re_state['is_phase4'], beam_aperture=_ap_gui, beam_aperture_knots_deg=_re_state['re_aperture_knots'], beam_aperture_knots_lam_nm=_re_state['re_p4_beam_knots_lam_nm'])
                spectra_display[dkey] = {'R': R_o, 'T': T_o}
            if not spectra_display:
                return
            first_key = next(iter(spectra_display))
            Ts_first = spectra_display[first_key]['T']
            _nk_prev = _re_correc_to_nk_preview_payload(correc)
            worker.signals.result.emit({'type': 'intermediate', 'wls': wls_display, 'Ts': Ts_first, 'ep': ep_use, 'rmse': rmse_d, 'rmse_sp': rs, 'rmse_qwot': rq, 'alpha_qwot': al_q, 'evals': int(evals), 'is_global_best': True, 'oblique_mode': True, 'spectra_display': spectra_display, 'oblique_tgts': oblique_tgts, **_nk_prev})
            logging.info(f"[LIVE VIEW] Emitted 5s live refresh signal | RE RMSE={rmse_d:.6f} | Evals={evals}")
        except NUMERICAL_FAULT_EXCEPTIONS as _emit_e:
            logging.debug('RE live spectrum emit: %s', _emit_e)

    def _build_re_run_context(worker, _re_t0: float) -> Any:
        """Prepares grids, MSE/QWOT, self.ctx and self._re_phase_ns for RE phases."""
        logger.debug('_build_re_run_context ENTER')
        worker.signals.progress_snapshot.emit(build_progress_snapshot(message='RE context build started', display_ratio=0.01, progress_ratio=0.01, eta_seconds=None, confidence=0.2, state=StepState.RUNNING, module='RE', phase='CONTEXT'))
        ctx, prep = _prepare_re_run_context_setup(worker, _re_t0)
        _emit_re_prog = prep['_emit_re_prog']
        _re_pct_hi = prep['_re_pct_hi']
        wls = prep['wls']
        _RE_P_SETUP = prep['_RE_P_SETUP']
        _RE_P_P1 = prep['_RE_P_P1']
        _mse_grad_accumulate_ep = _build_re_mse_grad_helper(worker, ctx)
        mats = prep['mats']
        stack = prep['stack']
        ep0 = prep['ep0']
        radius = prep['radius']
        oblique_tgts = prep['oblique_tgts']
        lambda_ref = prep['lambda_ref']
        float_dtype = np.float64
        complex_dtype = np.complex128
        n_layers_count = prep['n_layers_count']
        n_layers_nominal = prep['n_layers_nominal']
        n_sub_nominal = prep['n_sub_nominal']
        is_H = prep['is_H']
        is_L = prep['is_L']
        n_ref_nom_per_layer = prep['n_ref_nom_per_layer']
        _lref_arr = prep['_lref_arr']
        _p4_beam_knots_lam = prep['_p4_beam_knots_lam']
        oblique_config_meta = prep['oblique_config_meta']
        wt_spectral = prep['wt_spectral']
        re_env_s = prep['re_env_s']
        _re_env_on_wls = prep['_re_env_on_wls']
        _ap_gui = prep['_ap_gui']
        _re_state = prep['_re_state']
        wls_min = prep['wls_min']
        wls_max = prep['wls_max']
        wls_display, n_sub_disp, n_lay_disp = re_live_plot_wls_and_dispersion_nk(mats, stack, wls_min, wls_max, float_dtype=float_dtype, complex_dtype=complex_dtype)
        lb_ep, ub_ep = re_trf_thickness_bounds(ep0, radius)
        bounds_trf = (lb_ep, ub_ep)
        bounds = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)
        _qwot_helpers = _build_qwot_helpers(worker, ep0, n_ref_nom_per_layer, is_H, is_L, lambda_ref, re_env_s, _lref_arr, ctx._alpha_slot)
        _get_delta_qwot = _qwot_helpers['_get_delta_qwot']
        _compute_qwot_rmse = _qwot_helpers['_compute_qwot_rmse']
        _compute_qwot_rmse_raw = _qwot_helpers['_compute_qwot_rmse_raw']
        _rmse_combined = _qwot_helpers['_rmse_combined']
        _re_env_on_wls_disp = re_envelope_max_delta_n(wls_display, scale=re_env_s)
        _re_live_emit = {'t': 0.0}
    
        def _emit_re_spectrum_live(ep_vec: np.ndarray, evals: int, *, correc: tuple, last_mse: float | None=None, force: bool=False, rmse_override: float | None=None) -> None:
            worker._emit_re_spectrum_live_helper(ep_vec, evals, correc=correc, last_mse=last_mse, force=force, rmse_override=rmse_override, _re_live_emit=_re_live_emit, n_lay_disp=n_lay_disp, n_sub_disp=n_sub_disp, is_H=is_H, is_L=is_L, wls_display=wls_display, lambda_ref=lambda_ref, re_env_s=re_env_s, _re_env_on_wls_disp=_re_env_on_wls_disp, _mse_grad_accumulate_ep=_mse_grad_accumulate_ep, wt_spectral=wt_spectral, _compute_qwot_rmse=_compute_qwot_rmse, _alpha_slot=ctx._alpha_slot, _rmse_combined=_rmse_combined, oblique_config_meta=oblique_config_meta, _re_state=_re_state, _ap_gui=_ap_gui, oblique_tgts=oblique_tgts)
        n_starts = int(worker.cfg.get('re_phase1_multistarts', RE_GUI_DEFAULT_RE_PHASE1_RESTARTS))
        runs = re_phase1_trf_runs_multistart(ep0, wt_spectral, lb_ep, ub_ep, n_starts, lhs_seed=42)
        n_sched = len(runs)
        _correc_nom = RE_CORREC_NOMINAL_PCT
    
        def _report_mse_spectral(ep_arr: np.ndarray, correc_t: tuple) -> float:
            return float(_mse_grad_accumulate_ep(ep_arr, wt_spectral, False, correc_t)[0])
        ep0_u = np.asarray(ep0, dtype=np.float64).flatten()
        rmse_initial_sp = float(np.sqrt(max(_report_mse_spectral(ep0_u, _correc_nom), 0.0)))
        rmse_initial_q = _compute_qwot_rmse(ep0_u, _correc_nom)
        _a_p1, _a_p2a, _a_p2b, _a_p3 = resolve_re_qwot_alphas(worker.cfg, rmse_initial_sp, rmse_initial_q)
        ctx._alpha_slot[0] = _a_p1
        logging.info('RE  QWOT (phase1=%g, 2a=%g, 2b=%g, 3=%g)  per_phase=%s adaptive_init=%s', _a_p1, _a_p2a, _a_p2b, _a_p3, bool(worker.cfg.get('re_qwot_per_phase_schedule', True)), bool(worker.cfg.get('re_qwot_adaptive_init_scale', False)))
        rmse_initial_u = _rmse_combined(rmse_initial_sp, rmse_initial_q)
        _wp_ctx = worker.cfg.get('re_workbook_path')
        if _wp_ctx:
            logging.info('RE context  workbook: %s', Path(str(_wp_ctx)).name)
        _n_tg_on = sum((1 for t in oblique_tgts if getattr(t, 'on', True)))
        _angles = sorted({float(t.angle) for t in oblique_tgts if getattr(t, 'on', True)})
        logging.info('RE context  lambda_ref=%.2f nm | objective grid [%.1f ... %.1f] nm (%d pts) | %d active targets | %d spectral blocks (weight Deltaln(lambda) trapezoidal) | incidence deg: %s | phase1 thickness radius +/-%g%%', float(lambda_ref), float(np.min(wls)) if wls.size else float('nan'), float(np.max(wls)) if wls.size else float('nan'), int(wls.size), _n_tg_on, len(oblique_config_meta), ', '.join((f'{a:g}' for a in _angles)) if _angles else '', float(radius))
        _re_log_objective_diagnostic('initial (Excel design thicknesses)', rmse_initial_sp, rmse_initial_q, _a_p1)
        _de_mx = int(worker.cfg.get('re_phase1_de_maxiter', 0))
        _de_ps = int(worker.cfg.get('re_phase1_de_popsize', 8))
        if _de_mx > 0 and (not worker._stop):
            try:
                from scipy.optimize import differential_evolution
    
                def _obj_de(x) -> float:
                    xa = np.asarray(x, dtype=np.float64).ravel()
                    v = float(_report_mse_spectral(xa, _correc_nom))
                    return float(np.sqrt(max(v, 0.0)))
                bounds_de = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)
                res_de = differential_evolution(_obj_de, bounds_de, maxiter=_de_mx, popsize=max(5, _de_ps), seed=int(worker.cfg.get('re_phase1_de_seed', 42)), polish=False, workers=1)
                runs.insert(0, ('DE->TRF', wt_spectral, np.asarray(res_de.x, dtype=np.float64).ravel()))
                n_sched = len(runs)
                logging.info('RE phase1  differential_evolution seed (maxiter=%d, popsize=%d)', _de_mx, _de_ps)
            except NUMERICAL_FAULT_EXCEPTIONS as _e_de:
                logging.warning('RE phase1 differential_evolution skipped: %s', _e_de)
        _any_spl_act = bool(worker.cfg.get('re_refine_h', True)) or bool(worker.cfg.get('re_refine_l', True))
        _re_top_k_cfg = max(1, int(worker.cfg.get('re_phase2_top_k', RE_GUI_DEFAULT_RE_PHASE2_TOP_K)))
        _re_n_sh_cfg = max(0, int(worker.cfg.get('re_phase3_shake_rounds', 4))) if _any_spl_act else 0
        _re_prefit_max_cfg = int(worker.cfg.get('re_phase2_spline_prefit_maxiter', RE_PHASE2_SPLINE_PREFIT_MAXITER)) if _any_spl_act else 0
        _re_skip_2a_cfg = bool(worker.cfg.get('re_phase2_skip_spline_prefit', False)) or not _any_spl_act
        _re_do_2a_cfg = not _re_skip_2a_cfg and _re_prefit_max_cfg > 0
        _maxiter_p2b = max(10, int(worker.cfg.get('re_phase2b_maxiter', RE_PHASE2B_MAXITER)))
        _re_use_staged_order = bool(_any_spl_act)
        re_p2_plan: list[dict | None] = [None]
        _bind_p2_plan = partial(re_build_p2_progress_plan, re_top_k_cfg=_re_top_k_cfg, re_p_setup=_RE_P_SETUP, re_p_p1=_RE_P_P1, re_n_sh_cfg=_re_n_sh_cfg, re_do_2a_cfg=_re_do_2a_cfg)
        _pct_p1 = partial(re_progress_pct_p1, re_p_setup=_RE_P_SETUP, re_p_p1=_RE_P_P1, n_sched=n_sched)
        _pct_p2a = re_progress_pct_p2a
        _pct_p2b = re_progress_pct_p2b
        _pct_p3 = partial(re_progress_pct_p3, re_n_sh_cfg=_re_n_sh_cfg)
        results = []
        rmse_initial_milestone = [float(rmse_initial_u)]
        rmse_phase1_milestone = [float('nan')]
        rmse_final_milestone = [float('nan')]
        _emit_re_spectrum_live(ep0_u, 0, correc=_correc_nom, force=True, rmse_override=rmse_initial_u)
        worker.ctx = SimpleNamespace(runs=runs, n_layers_count=n_layers_count, _emit_re_prog=_emit_re_prog, _pct_p1=_pct_p1, wt_spectral=wt_spectral, _correc_nom=_correc_nom, _mse_grad_accumulate_ep=_mse_grad_accumulate_ep, _compute_qwot_rmse=_compute_qwot_rmse, _rmse_combined=_rmse_combined, bounds_trf=bounds_trf, RE_LBFGSB_FTOL=RE_LBFGSB_FTOL, RE_LBFGSB_GTOL=RE_LBFGSB_GTOL, _report_mse_spectral=_report_mse_spectral, _emit_re_spectrum_live=_emit_re_spectrum_live, _alpha_slot=ctx._alpha_slot, _a_p1=_a_p1, rmse_initial_u=rmse_initial_u, rmse_initial_sp=rmse_initial_sp, rmse_initial_q=rmse_initial_q, rmse_phase1_milestone=rmse_phase1_milestone, rmse_final_milestone=rmse_final_milestone, _re_use_staged_order=_re_use_staged_order, cfg=worker.cfg, _stop=worker._stop)
        worker._re_phase_ns = SimpleNamespace(results=results, oblique_config_meta=oblique_config_meta, _re_use_staged_order=_re_use_staged_order, _emit_re_prog=_emit_re_prog, _RE_P_SETUP=_RE_P_SETUP, _RE_P_P1=_RE_P_P1, _re_state=_re_state, _ap_gui=_ap_gui, _mse_grad_accumulate_ep=_mse_grad_accumulate_ep, wt_spectral=wt_spectral, _correc_nom=_correc_nom, bounds_trf=bounds_trf, n_layers_count=n_layers_count, _compute_qwot_rmse=_compute_qwot_rmse, _rmse_combined=_rmse_combined, _report_mse_spectral=_report_mse_spectral, rmse_final_milestone=rmse_final_milestone, wls=wls, re_env_s=re_env_s, n_sub_nominal=n_sub_nominal, lambda_ref=lambda_ref, bounds=bounds, _alpha_slot=ctx._alpha_slot, _a_p2a=_a_p2a, _a_p2b=_a_p2b, _a_p3=_a_p3, re_p2_plan=re_p2_plan, _bind_p2_plan=_bind_p2_plan, _pct_p2a=_pct_p2a, _pct_p2b=_pct_p2b, _pct_p3=_pct_p3, _emit_re_spectrum_live=_emit_re_spectrum_live, _re_n_sh_cfg=_re_n_sh_cfg, _any_spl_act=_any_spl_act, _maxiter_p2b=_maxiter_p2b, _re_pct_hi=_re_pct_hi, _use_sub_c3_shared=False, _p2_ctx={})
        return SimpleNamespace(rmse_initial_sp=rmse_initial_sp, rmse_initial_q=rmse_initial_q, rmse_initial_u=rmse_initial_u, rmse_initial_milestone=rmse_initial_milestone, rmse_phase1_milestone=rmse_phase1_milestone, rmse_final_milestone=rmse_final_milestone, _alpha_slot=ctx._alpha_slot, _a_p1=_a_p1, _a_p2a=_a_p2a, _a_p2b=_a_p2b, _a_p3=_a_p3, _correc_nom=_correc_nom, _emit_re_spectrum_live=_emit_re_spectrum_live, _compute_qwot_rmse_raw=_compute_qwot_rmse_raw, _compute_qwot_rmse=_compute_qwot_rmse, n_sub_nominal=n_sub_nominal, wls=wls, lambda_ref=lambda_ref, ep0=ep0, _re_pct_hi=_re_pct_hi, results=results, _re_t0=_re_t0)

