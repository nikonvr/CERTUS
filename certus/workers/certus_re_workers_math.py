from certus.utils.certus_re_math import re_envelope_max_delta_n
from certus.utils.certus_re_math import re_compute_spline_basis_matrix
from certus.utils.certus_re_math import re_compute_tikhonov_weights
from certus.utils.certus_re_math import re_substrate_cauchy_barrier_residuals_jac
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
import logging
import joblib
import time
import math
from copy import deepcopy
import numpy as np
from typing import Any, Callable
from certus.utils.certus_re_math import (
    RE_P4_BEAM_N_KNOTS,
    RE_SUB_CAUCHY_BARRIER_SQRT_W,
    re_compute_spline_basis_matrix,
    re_compute_tikhonov_weights,
    re_envelope_max_delta_n,
    re_knots_wavelengths,
    re_substrate_cauchy_barrier_residuals_jac,
)

# 
from certus.utils.certus_re_helpers import _re_trf_residual_rms
# from certus.core.certus_re_solvers import *  # Unused
from concurrent.futures import ThreadPoolExecutor, as_completed
from certus.core.certus_re_solvers import REUserStopRequested


class REMathStrategy:
    def _compute_eval_both_p2(worker, ctx, xv: np.ndarray, emit_interval: float=5.0) -> tuple | None:
        if worker._stop:
            raise REUserStopRequested()
        _c = ctx._cb2_ref[0]
        if _c is None:
            return
        _ph4_ap_now = None
        if ctx._re_state.get('is_phase4'):
            _kap = np.asarray(ctx._re_state['re_aperture_knots'], dtype=np.float64).ravel()[:int(RE_P4_BEAM_N_KNOTS)]
            _ph4_ap_now = tuple((float(x) for x in _kap))
        if _c['x'] is not None and np.array_equal(xv, _c['x']):
            if _ph4_ap_now is None:
                return
            if _c.get('_ph4_ap_snap') == _ph4_ap_now:
                return
        cur_lam2 = float(xv[ctx.i_lam])
        if _c['tk_w_c'] is None or abs(cur_lam2 - (_c['tk_lam2'] or 0.0)) > 1.0:
            _c['tk_w_c'] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)
            _c['tk_lam2'] = cur_lam2
        tk_w_c = _c['tk_w_c']
        _c['i'] += 1
        ep_x = np.asarray(xv[:ctx.n_layers_count], dtype=np.float64, copy=False)
        dh4 = xv[ctx.i0:ctx.i0 + ctx._nk].copy()
        dl4 = xv[ctx.i0 + ctx._nk:ctx.i_lam].copy()
        lam2 = float(xv[ctx.i_lam])
        th4 = np.asarray(xv[ctx.i_cu:ctx.i_cu + 3], dtype=np.float64).ravel() if ctx._use_sub_c3 else None
        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam2), ctx.wls)
        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)
        if ctx._use_sub_c3:
            cor_spl = ('spline_cached_sub3', dh4, dl4, lam2, b_mat_c, env_c, tk_w_c, float(th4[0]), float(th4[1]), float(th4[2]))
        else:
            cor_spl = ('spline_cached', dh4, dl4, lam2, b_mat_c, env_c, tk_w_c)
        mse, _, r_c, j_ep = ctx._mse_grad_accumulate_ep(ep_x, ctx.wt_spectral, True, cor_spl, return_residuals=True)
        if _c['i'] == 1:
            _n_fd = ctx._n_joint_fd if ctx._fd_1s else ctx._n_joint_fd * 2
            logging.info('RE phase 2b  1st TRF eval: %d thick. analytic, %d FD residual blocks (%s)  FD_threads=%d', ctx.n_layers_count, _n_fd, 'forward' if ctx._fd_1s else 'centered', ctx._fd_nw)
        J_var = np.zeros((len(r_c), ctx._n_joint_fd), dtype=np.float64)
        xv64 = np.asarray(xv, dtype=np.float64, copy=True)
    
        def _p2_fd_j_res(j: int) -> tuple[int, np.ndarray]:
            return worker._evaluate_p2_fd_derivative(ctx, j, xv64, ep_x, r_c, b_mat_c, env_c, tk_w_c, dh4, dl4, lam2, th4)
        _nw_j = min(ctx._fd_nw, ctx._n_joint_fd)
        _active_js = []
        _act_h = bool(worker.cfg.get('re_refine_h', True))
        _act_l = bool(worker.cfg.get('re_refine_l', True))
        for j in range(ctx._n_joint_fd):
            if j < ctx._nk and (not _act_h):
                continue
            if ctx._nk <= j < 2 * ctx._nk and (not _act_l):
                continue
            if j == 2 * ctx._nk and (not (_act_h or _act_l)):
                continue
            _active_js.append(j)
        if _nw_j <= 1:
            for j in _active_js:
                jj, j_col = _p2_fd_j_res(j)
                J_var[:, jj] = j_col
        else:
            _fd_executor_kind = str(worker.cfg.get('re_phase2_fd_executor', 'thread')).lower()
            _ex_p2 = _c.get('fd_executor')
            if _ex_p2 is None:
                _backend = 'loky' if _fd_executor_kind == 'process' else 'threading'
                _ex_p2 = joblib.Parallel(n_jobs=_nw_j, backend=_backend)
                _c['fd_executor'] = _ex_p2
            try:
                results = _ex_p2((joblib.delayed(_p2_fd_j_res)(j) for j in _active_js))
                for res in results:
                    jj, j_col = res
                    J_var[:, jj] = j_col
            except Exception:
                if _fd_executor_kind == 'process':
                    logging.getLogger(__name__).warning('RE phase2 FD process executor (loky) fallback to threading', exc_info=True)
                    _fallback = joblib.Parallel(n_jobs=_nw_j, backend='threading')
                    _c['fd_executor'] = _fallback
                    results = _fallback((joblib.delayed(_p2_fd_j_res)(j) for j in _active_js))
                    for res in results:
                        jj, j_col = res
                        J_var[:, jj] = j_col
                else:
                    raise
        if ctx._use_sub_c3:
            J_spl = J_var[:, :ctx.n_sp]
            J_cu = J_var[:, ctx.n_sp:ctx.n_sp + 3]
            J_top = np.hstack([j_ep, J_spl, J_cu])
            sw_b = float(worker.cfg.get('re_sub_cauchy_barrier_sqrt_w', RE_SUB_CAUCHY_BARRIER_SQRT_W))
            r_b, J_b = re_substrate_cauchy_barrier_residuals_jac(th4, ctx._Phi_sub, ctx._n_tab_sub, sqrt_w=sw_b)
            J_bot = np.hstack([np.zeros((len(r_b), ctx.n_layers_count + ctx.n_sp), dtype=np.float64), J_b])
            _c['res'] = np.concatenate((r_c, r_b))
            _c['jac'] = np.vstack([J_top, J_bot])
            _c['barrier_norm'] = float(np.linalg.norm(r_b))
        else:
            _c['res'] = r_c
            _c['jac'] = np.hstack([j_ep, J_var[:, :ctx.n_sp]])
            _c['barrier_norm'] = None
        _c['x'] = xv.copy()
        _c['mse'] = float(mse)
        _c['_ph4_ap_snap'] = _ph4_ap_now
        now = time.perf_counter()
        if _c['i'] == 1 or now - _c['last_emit'] >= emit_interval:
            _c['last_emit'] = now
            rs2 = float(np.sqrt(max(_c['mse'], 0.0)))
            rq2 = ctx._compute_qwot_rmse(ep_x, cor_spl)
            rmse_cur = ctx._rmse_combined(rs2, rq2)
            if ctx._p2_trf_log_tag[0] == 'phase 4 finale':
                _ap_k = np.asarray(ctx._re_state['re_aperture_knots'], dtype=float).ravel()[:int(RE_P4_BEAM_N_KNOTS)]
                _lam_k = np.asarray(ctx._re_state.get('re_p4_beam_knots_lam_nm', []), dtype=float).ravel()[:_ap_k.size]
                _pairs = ', '.join((f'(lambda={lk:.0f}nm->{ak:.2f})' for lk, ak in zip(_lam_k, _ap_k, strict=False)))
                ap_sfx = f' | ap=[{_pairs}]'
            else:
                ap_sfx = ''
            _bn = _c.get('barrier_norm')
            _bar_sfx = f' | ||barrier||={float(_bn):.4g}' if _bn is not None else ''
            _best_prev = _c.get('best_rmse_combined')
            if _best_prev is None or rmse_cur < float(_best_prev):
                _c['best_rmse_combined'] = float(rmse_cur)
            rmse_best_so_far = float(_c.get('best_rmse_combined', rmse_cur))
            _trf_rms_p2 = _re_trf_residual_rms(_c['res'])
            msg = f"RE [{ctx._p2_trf_log_tag[0]}] TRF it ~{_c['i']}  RMSE_facade(curr)={rmse_cur:.6f} | RMSE_facade(best)={rmse_best_so_far:.6f} (sqrt(sp2+alpha·QWOT2); hors Tikhonov/pen H-L dans r) | TRF_RMS(res)={_trf_rms_p2:.6g}{ap_sfx}{_bar_sfx}  {now - ctx._t_p2:.1f}s"
            logging.info(msg)
            _intra_2b = min(0.92, float(_c['i']) / float(max(ctx._maxiter_p2b, 1)))
            ctx._emit_re_prog(ctx._pct_p2b(ctx.pl, ctx._p2_ki_slot[0], _intra_2b), msg)
        
        ctx._emit_re_spectrum_live(ep_x, _c['i'], correc=cor_spl, last_mse=_c['mse'], force=False)

    def _compute_fun_res_p2(worker, ctx_p2, xv: np.ndarray, emit_interval: float=5.0) -> Any:
        worker._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)
        return ctx_p2._cb2_ref[0]['res']

    def _compute_jac_res_p2(worker, ctx_p2, xv: np.ndarray, emit_interval: float=5.0) -> Any:
        worker._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)
        return ctx_p2._cb2_ref[0]['jac']

    def _compute_eval_both_p2a(worker, ctx, x_sp: np.ndarray, _cb2a, ep_p1, _ki, _t_pf) -> tuple | None:
        if worker._stop:
            raise REUserStopRequested()
        if _cb2a['x'] is not None and np.array_equal(x_sp, _cb2a['x']):
            return
        cur_lam2 = float(x_sp[2 * ctx._nk])
        if _cb2a['tk_w_c'] is None or abs(cur_lam2 - (_cb2a['tk_lam2'] or 0.0)) > 1.0:
            _cb2a['tk_w_c'] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)
            _cb2a['tk_lam2'] = cur_lam2
        tk_w_c = _cb2a['tk_w_c']
        _cb2a['i'] += 1
        dh = np.asarray(x_sp[:ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)
        dl = np.asarray(x_sp[ctx._nk:2 * ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)
        lam_p = float(x_sp[2 * ctx._nk])
        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam_p), ctx.wls)
        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)
        cor_c = worker._build_cached_spline_correc(ctx, dh, dl, lam_p, tk_w_c, cached=True, b_mat_c=b_mat_c, env_c=env_c)
        mse, _, r_c, _ = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_c, return_residuals=True)
        if _cb2a['i'] == 1:
            _n_fd = ctx.n_sp if ctx._fd_1s else ctx.n_sp * 2
            logging.info('RE phase 2a  1st TRF eval: 0 thick. analytic, %d FD residual blocks (%s)  FD_threads=%d', _n_fd, 'forward' if ctx._fd_1s else 'centered', ctx._fd_nw)
            ctx._emit_re_prog(ctx._pct_p2a(ctx.pl, _ki, 0.05), 'RE phase 2a  first FD objective+grad eval (may take a few s)...')
        J_sp = np.zeros((len(r_c), ctx.n_sp), dtype=np.float64)
        x_c = np.asarray(x_sp, dtype=np.float64, copy=True)
    
        def _pf_fd_j_res(j: int) -> tuple[int, np.ndarray]:
            hs = ctx._p2fd_lam if j == 2 * ctx._nk else ctx._p2fd_spl
            xp = np.array(x_c, copy=True)
            xp[j] += hs
            cor_p = worker._build_cached_spline_correc(ctx, xp[:ctx._nk], xp[ctx._nk:2 * ctx._nk], float(xp[2 * ctx._nk]), tk_w_c, cached=j < 2 * ctx._nk, b_mat_c=b_mat_c, env_c=env_c)
            r_p = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_p, return_residuals=True)[2]
            if ctx._fd_1s:
                return (j, (r_p - r_c) / hs)
            xm = np.array(x_c, copy=True)
            xm[j] -= hs
            cor_m = worker._build_cached_spline_correc(ctx, xm[:ctx._nk], xm[ctx._nk:2 * ctx._nk], float(xm[2 * ctx._nk]), tk_w_c, cached=j < 2 * ctx._nk, b_mat_c=b_mat_c, env_c=env_c)
            r_m = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_m, return_residuals=True)[2]
            return (j, (r_p - r_m) / (2.0 * hs))
        _nw_sp = min(ctx._fd_nw, ctx.n_sp)
        if _nw_sp <= 1:
            for j in range(ctx.n_sp):
                jj, j_col = _pf_fd_j_res(j)
                J_sp[:, jj] = j_col
        else:
            _ex_pf = _cb2a.get('fd_executor')
            if _ex_pf is None:
                _ex_pf = ThreadPoolExecutor(max_workers=_nw_sp)
                _cb2a['fd_executor'] = _ex_pf
            _f_pf = [_ex_pf.submit(_pf_fd_j_res, j) for j in range(ctx.n_sp)]
            for _fu in as_completed(_f_pf):
                jj, j_col = _fu.result()
                J_sp[:, jj] = j_col
        _cb2a['x'] = x_sp.copy()
        _cb2a['res'] = r_c
        _cb2a['jac'] = J_sp
        _cb2a['mse'] = float(mse)
        now = time.perf_counter()
        if _cb2a['i'] == 1 or now - _cb2a['last_emit'] >= 5.0:
            _cb2a['last_emit'] = now
            logging.info('RE phase 2a  TRF iter ~%d (%.1fs since prefit start)', _cb2a['i'], now - _t_pf)
            _intra_2a = min(0.92, float(_cb2a['i']) / float(max(ctx._prefit_max, 1)))
            ctx._emit_re_prog(ctx._pct_p2a(ctx.pl, _ki, _intra_2a), f"RE phase 2a  iter {_cb2a['i']} TRF spline prefit...")
        
        ctx._emit_re_spectrum_live(ep_p1, _cb2a['i'], correc=cor_c, last_mse=float(mse), force=False)

    def _compute_fun_res_p2a(worker, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:
        worker._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))
        return _cb2a['res']

    def _compute_jac_res_p2a(worker, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:
        worker._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))
        return _cb2a['jac']

