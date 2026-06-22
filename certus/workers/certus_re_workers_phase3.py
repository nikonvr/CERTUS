import logging
import time
import math
from copy import deepcopy
import numpy as np
from scipy.optimize import least_squares
from typing import Any, Callable

from certus.core.certus_core import CFG, get_float_dtype, get_complex_dtype
from certus.core.certus_re_config import REPhase3Result, REPhase4Result, _set_top_result_dto, _top_result_dto, RE_RESULT_LABEL_WITH_DRIFT
from certus.core.certus_re_solvers import REUserStopRequested
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_PHASE3_SHAKES, RE_LBFGSB_FTOL, RE_LBFGSB_GTOL
from certus.utils.certus_re_helpers import re_knots_wavelengths
from certus.workers.certus_re_worker_utils import p2_result_to_correc_tuple, shake_sigmas_adaptive


class REPhase3Strategy:
    def _execute_phase3_shakes(self, worker) -> None:
        """Phase 3: perturbations + short TRF refits (escape local minima)."""
        L = worker._re_phase_ns
        results = L.results
        _p2_ctx = L._p2_ctx
        _use_sub_c3 = bool(L._use_sub_c3_shared)
        if not _p2_ctx:
            logging.warning('RE phase 3 skipped: phase-2 context unavailable.')
            return
        _nk = int(_p2_ctx['_nk'])
        i0 = int(_p2_ctx['i0'])
        i_lam = int(_p2_ctx['i_lam'])
        i_cu = i_lam + 1
        b_lb = np.asarray(_p2_ctx['b_lb'], dtype=np.float64)
        b_ub = np.asarray(_p2_ctx['b_ub'], dtype=np.float64)
        bounds_p2_trf = _p2_ctx['bounds_p2_trf']
        _cb2_ref = _p2_ctx['_cb2_ref']
        _p2_trf_log_tag = _p2_ctx['_p2_trf_log_tag']
        _eval_both_p2 = _p2_ctx['_eval_both_p2']
        _fun_res_p2 = _p2_ctx['_fun_res_p2']
        _jac_res_p2 = _p2_ctx['_jac_res_p2']
        n_layers_count = L.n_layers_count
        _alpha_slot = L._alpha_slot
        _a_p3 = L._a_p3
        re_p2_plan = L.re_p2_plan
        pl = re_p2_plan[0] if re_p2_plan else None
        _pct_p3 = L._pct_p3
        _emit_re_prog = L._emit_re_prog
        _emit_re_spectrum_live = L._emit_re_spectrum_live
        _report_mse_spectral = L._report_mse_spectral
        _compute_qwot_rmse = L._compute_qwot_rmse
        _rmse_combined = L._rmse_combined
        rmse_final_milestone = L.rmse_final_milestone
        RE_PHASE3_SHAKE_EP_SIGMA_PCT = 1.5
        RE_PHASE3_SHAKE_SPL_SIGMA = 0.01
        RE_PHASE3_SHAKE_MAXITER = 80
        n_shakes = int(worker.cfg.get('re_phase3_shake_rounds', RE_GUI_DEFAULT_RE_PHASE3_SHAKES))
        if n_shakes > 0 and (not worker._stop) and results:
            _alpha_slot[0] = _a_p3
            _sk_sh = worker.cfg.get('re_phase3_shake_seed', -1)
            try:
                _sk_i = int(_sk_sh)
            except (TypeError, ValueError):
                _sk_i = -1
            _rng3 = np.random.default_rng(_sk_i % 2 ** 32 if _sk_i >= 0 else None)
            best_res = results[0]
            best_res_dto = REPhase4Result.from_legacy_dict(best_res)
            x_best = np.concatenate([best_res_dto.ep, best_res_dto.re_dh_knots, best_res_dto.re_dl_knots, [best_res_dto.re_spline_lam_node2_nm], [best_res_dto.re_sub_cauchy_a0, best_res_dto.re_sub_cauchy_a1, best_res_dto.re_sub_cauchy_a2] if _use_sub_c3 and best_res_dto.re_sub_cauchy_a0 is not None else []])
            rmse_best = float(best_res_dto.rmse_combined)
            cor_best = p2_result_to_correc_tuple(best_res, _use_sub_c3)
            _cb2_ref[0] = {'x': None, 'res': None, 'jac': None, 'mse': None, 'best_rmse_combined': None, 'i': 0, 'last_emit': time.perf_counter(), 'tk_w_c': None, 'tk_lam2': None}
            _p2_trf_log_tag[0] = 'pre-phase 3 warmup'
            _eval_both_p2(np.asarray(x_best, dtype=np.float64))
            _r0_ref = _cb2_ref[0].get('res')
            if _r0_ref is None:
                _r0_ref = np.array([0.0], dtype=np.float64)
            _rn0 = float(np.linalg.norm(_r0_ref))
            try:
                from scipy.stats.qmc import LatinHypercube
                _lhs_samples = LatinHypercube(d=n_layers_count + 2 * _nk, seed=_rng3).random(n=n_shakes)
                _lhs_samples = _lhs_samples * 2.0 - 1.0
            except ImportError:
                _lhs_samples = _rng3.uniform(-1.0, 1.0, (n_shakes, n_layers_count + 2 * _nk))
            for _si in range(n_shakes):
                if worker._stop:
                    break
                _sig_ep, _sig_sp = shake_sigmas_adaptive(_rn0, base_ep_sigma_pct=float(worker.cfg.get('re_phase3_shake_ep_sigma_pct', RE_PHASE3_SHAKE_EP_SIGMA_PCT)), base_spl_sigma=float(worker.cfg.get('re_phase3_shake_spl_sigma', RE_PHASE3_SHAKE_SPL_SIGMA)), ref_norm=float(worker.cfg.get('re_phase3_shake_ref_norm', 1.0)))
                x_shake = np.array(x_best, dtype=np.float64).copy()
                _u = _lhs_samples[_si]
                x_shake[:n_layers_count] += _u[:n_layers_count] * (_sig_ep / 100.0 * x_best[:n_layers_count])
                x_shake[i0:i_lam] += _u[n_layers_count:] * _sig_sp
                np.clip(x_shake, b_lb, b_ub, out=x_shake)
                _p2_trf_log_tag[0] = f'phase 3 shake {_si + 1}/{n_shakes}'
                _cr3 = _cb2_ref[0]
                if _cr3 is not None:
                    _cr3['i'] = 0
                    _cr3['x'] = None
                    _cr3['res'] = None
                    _cr3['jac'] = None
                    _cr3['mse'] = None
                    _cr3['best_rmse_combined'] = None
                    _cr3['last_emit'] = time.perf_counter()
                try:
                    res_sh = least_squares(_fun_res_p2, x_shake, method='trf', bounds=bounds_p2_trf, jac=_jac_res_p2, x_scale='jac', ftol=RE_LBFGSB_FTOL * 10, gtol=RE_LBFGSB_GTOL * 10, max_nfev=RE_PHASE3_SHAKE_MAXITER)
                except REUserStopRequested:
                    logging.info('RE phase 3  stopped by user (keeping best phase 2 result)')
                    break
                x_sh = res_sh.x
                ep_sh = np.asarray(x_sh[:n_layers_count], dtype=np.float64).flatten()
                dh_sh = np.asarray(x_sh[i0:i0 + _nk], dtype=np.float64).flatten()
                dl_sh = np.asarray(x_sh[i0 + _nk:i_lam], dtype=np.float64).flatten()
                lam_sh = float(x_sh[i_lam])
                knots_sh = re_knots_wavelengths(lam_sh)
                if _use_sub_c3:
                    th_sh = np.asarray(x_sh[i_cu:i_cu + 3], dtype=np.float64).ravel()
                    cor_sh = ('spline_sub3', dh_sh, dl_sh, lam_sh, float(th_sh[0]), float(th_sh[1]), float(th_sh[2]))
                else:
                    cor_sh = ('spline', dh_sh, dl_sh, lam_sh)
                rmse_p2_sh = float(np.sqrt(max(_report_mse_spectral(ep_sh, cor_sh), 0.0)))
                rmse_qwot_sh = _compute_qwot_rmse(ep_sh, cor_sh)
                rmse_comb_sh = _rmse_combined(rmse_p2_sh, rmse_qwot_sh)
                if rmse_comb_sh < rmse_best - 1e-08:
                    x_best = res_sh.x.copy()
                    rmse_best = rmse_comb_sh
                    logging.info(f'RE phase 3 shake #{_si + 1}: improved -> RMSE_combined={rmse_best:.6f}')
                    phase3_result = REPhase3Result(label=RE_RESULT_LABEL_WITH_DRIFT, ep=np.asarray(ep_sh, dtype=np.float64).flatten(), a=0.0, b=0.0, f=0.0, re_dh_knots=np.asarray(dh_sh, dtype=np.float64).flatten(), re_dl_knots=np.asarray(dl_sh, dtype=np.float64).flatten(), re_knots_nm=np.asarray(knots_sh, dtype=np.float64).flatten(), re_spline_lam_node2_nm=float(lam_sh), rmse=float(rmse_p2_sh), rmse_qwot=float(rmse_qwot_sh), rmse_combined=float(rmse_comb_sh), nfev=int(best_res_dto.nfev + res_sh.nfev), success=bool(res_sh.success), nfev_phase1=int(best_res_dto.nfev_phase1), nfev_phase2_prefit=int(best_res_dto.nfev_phase2_prefit), re_sub_cauchy_a0=float(th_sh[0]) if _use_sub_c3 else None, re_sub_cauchy_a1=float(th_sh[1]) if _use_sub_c3 else None, re_sub_cauchy_a2=float(th_sh[2]) if _use_sub_c3 else None)
                    _phase3_as_p4 = REPhase4Result.from_legacy_dict(phase3_result.to_legacy_dict())
                    _set_top_result_dto(results, _phase3_as_p4)
                    cor_best = cor_sh
                    rmse_final_milestone[0] = float(_phase3_as_p4.rmse_combined)
                    _shake_best = float(_cb2_ref[0].get('best_rmse_combined', rmse_comb_sh))
                    if pl is not None:
                        _emit_re_prog(_pct_p3(pl, _si, 1.0), f'RE phase 3 shake {_si + 1}/{n_shakes}: best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}')
                    else:
                        _emit_re_prog(97.0, f'RE phase 3 shake {_si + 1}/{n_shakes}: best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}')
                    _new_top_dto = _top_result_dto(results)
                    if _new_top_dto is not None and _new_top_dto.rmse_combined < best_res_dto.rmse_combined:
                        _emit_re_spectrum_live(np.asarray(_new_top_dto.ep, dtype=np.float64).flatten(), int(_new_top_dto.nfev), correc=cor_best, force=True, rmse_override=float(_new_top_dto.rmse_combined))

