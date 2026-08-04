from __future__ import annotations
from certus.utils.certus_re_config import RE_PHASE4_TRF_TOL_FACTOR
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_config import RE_P4_AP_FD_STEP_DEG
from certus.utils.certus_re_config import RE_SUB_CAUCHY_TUBE_DELTA
from certus.utils.certus_re_config import RE_PHASE2_SPLINE_PREFIT_MAXITER
from certus.utils.certus_re_config import RE_PHASE2_SUB_CAUCHY_FD_STEP
from certus.utils.certus_re_config import RE_PHASE2A_PREFIT_TOL_FACTOR
from certus.utils.certus_re_config import RE_PHASE2A_SKIP_PREFIT_RMSE_THRESHOLD
from certus.utils.certus_re_config import RE_PHASE2B_MAXITER
from certus.utils.certus_re_config import RE_LBFGSB_GTOL
from certus.utils.certus_re_config import RE_LBFGSB_FTOL
from certus.utils.certus_re_math import re_substrate_cauchy_initial_theta
from certus.utils.certus_re_math import re_compute_spline_basis_matrix
from certus.utils.certus_re_math import re_compute_tikhonov_weights
from certus.utils.certus_re_math import re_substrate_cauchy_barrier_residuals_jac
from certus.utils.certus_re_math import re_substrate_cauchy_phi_matrix
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_PHASE2_LAM2_FD_STEP
from certus.utils.certus_re_config import RE_PHASE2_SPLINE_FD_STEP
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_config import RE_RE_DEADZONE_QWOT_ABS
from certus.utils.certus_re_config import RE_RE_DEADZONE_DELTA_RE_ABS
from certus.utils.certus_re_config import RE_HL_DELTA_RE_REG_SQRT_W
import numpy as np
import time
import logging
import traceback
from typing import Any

from scipy.optimize import least_squares
from types import SimpleNamespace
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

from certus.core.certus_re_config import (
    REPhase1Result,
    REPhase2Result,
    REPhase3Result,
    REPhase4Result,
    REPhase2Context,
    _prepend_result_dto,
    _replace_all_with_top_dto,
    _result_dto_at,
    _top_result_dto,
)
from certus.core.certus_re_objectives import (
    _build_re_mse_grad_helper,
    _global_compute_re_mse_gradient,
    _build_qwot_helpers,
    _build_phase2b_output,
    _log_phase4_trf_summary,
    _build_phase4_aperture_bounds,
    _prepare_phase2_bounds_and_topk,
    _build_p2_prefit_bounds,
    _build_phase2_result,
    _prepare_phase2_fd_settings,
)
from certus.utils.certus_re_helpers import (
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    format_re_spline_knots_log,
    re_knots_wavelengths,
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    _re_p4_beam_knots_lam_nm_from_wls,
    _re_trf_residual_rms,
    _re_log_objective_diagnostic,
)
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV
from certus.workers.certus_re_worker_utils import (
    re_live_plot_wls_and_dispersion_nk,
    shake_sigmas_adaptive,
    re_progress_pct_p2a,
    re_progress_pct_p2b,
    re_progress_pct_p3,
    p2_result_to_correc_tuple,
)

class REUserStopRequested(Exception):
    pass

def re_execute_phase1(worker) -> list[dict]:

    from scipy.optimize import least_squares

    from types import SimpleNamespace

    c = worker.ctx

    res_p1 = []

    # ``wt_wls`` = pre-calculated spectral weights on the objective grid lambda.

    def _run_single_phase1(run_idx, label, wt_wls, x0_run):
        if c._stop:
            return None
            
        _run_start = time.perf_counter()
        _max_iter = int(c.cfg.get("re_phase1_maxiter", 100))
        c._emit_re_prog(
            c._pct_p1(run_idx, 0.0),
            f"RE phase 1 (TRF, {label})  variables={c.n_layers_count} (thicknesses); nominal indices"
        )
        _cache = {"x": None, "res": None, "jac": None, "mse": None, "i": 0, "last_emit": time.perf_counter()}

        def _eval_both(x: np.ndarray) -> None:
            if c._stop:
                raise REUserStopRequested()
            if _cache["x"] is not None and np.array_equal(x, _cache["x"]):
                return
            mse, grad, r_out, j_out = c._mse_grad_accumulate_ep(
                x, wt_wls, True, c._correc_nom, return_residuals=True
            )
            _cache["x"] = x.copy()
            _cache["res"] = r_out
            _cache["jac"] = j_out
            _cache["mse"] = float(mse)
            _cache["i"] += 1
            now = time.perf_counter()
            if _cache["i"] == 1 or (now - _cache["last_emit"]) >= 5.0:
                _cache["last_emit"] = now
                rs = float(np.sqrt(max(_cache["mse"], 0.0)))
                rq = c._compute_qwot_rmse(x, c._correc_nom)
                rmse_cur = c._rmse_combined(rs, rq)
                _trf_rms = _re_trf_residual_rms(_cache["res"])
                msg = (
                    f"RE [{label}] TRF iter ~{_cache['i']}  "
                    f"RMSE_facade={rmse_cur:.6f} | TRF_RMS(r)={_trf_rms:.6g}  {now - _run_start:.1f}s"
                )
                logging.info(msg)
                _intra_p1 = min(0.92, float(_cache["i"]) / float(max(_max_iter, 1)))
                c._emit_re_prog(c._pct_p1(run_idx, _intra_p1), msg)
            
            c._emit_re_spectrum_live(x, _cache["i"], correc=c._correc_nom, last_mse=_cache["mse"], force=False)

        def _fun_res(x: np.ndarray) -> Any:
            _eval_both(x)
            return _cache["res"]

        def _jac_res(x: np.ndarray) -> Any:
            _eval_both(x)
            return _cache["jac"]

        try:
            res = least_squares(
                _fun_res, x0_run, method="trf", bounds=c.bounds_trf, jac=_jac_res,
                x_scale="jac", ftol=c.RE_LBFGSB_FTOL, xtol=c.RE_LBFGSB_FTOL,
                gtol=c.RE_LBFGSB_GTOL, max_nfev=max(10, _max_iter),
            )
        except REUserStopRequested:
            x_use = _cache["x"] if _cache["x"] is not None else np.asarray(x0_run, dtype=np.float64).ravel()
            res = SimpleNamespace(x=np.asarray(x_use, dtype=np.float64).copy(), nfev=max(0, int(_cache["i"])), success=False)

        x_final = res.x.copy()
        ep_final = np.asarray(x_final, dtype=np.float64).flatten()
        rmse_final = float(np.sqrt(max(c._report_mse_spectral(ep_final, c._correc_nom), 0.0)))
        rmse_qwot_final = c._compute_qwot_rmse(ep_final, c._correc_nom)
        rmse_comb_final = c._rmse_combined(rmse_final, rmse_qwot_final)
        phase1_result = REPhase1Result(
            label=str(label), ep=ep_final, a=0.0, b=0.0, f=0.0,
            rmse=rmse_final, rmse_qwot=rmse_qwot_final, rmse_combined=rmse_comb_final,
            nfev=int(res.nfev), success=bool(res.success),
        )
        c._emit_re_spectrum_live(ep_final, res.nfev, correc=c._correc_nom, force=True, rmse_override=rmse_comb_final)
        _run_dt = time.perf_counter() - _run_start
        logging.info(f"RE phase 1 (TRF, {label}) done RMSE_combined={rmse_comb_final:.6f}")
        c._emit_re_prog(c._pct_p1(run_idx + 1, 0.0), f"RE phase 1 (TRF, {label}) done.")
        return phase1_result.to_legacy_dict()

    import concurrent.futures
    import sys
    import os
    is_testing = "pytest" in sys.modules
    max_workers = 1 if is_testing else min(8, os.cpu_count() or 4)

    if max_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for run_idx, (label, wt_wls, x0_run) in enumerate(c.runs):
                futures.append(executor.submit(_run_single_phase1, run_idx, label, wt_wls, x0_run))
            
            for future in concurrent.futures.as_completed(futures):
                if c._stop:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                result = future.result()
                if result is not None:
                    res_p1.append(result)
    else:
        for run_idx, (label, wt_wls, x0_run) in enumerate(c.runs):
            if c._stop:
                break
            result = _run_single_phase1(run_idx, label, wt_wls, x0_run)
            if result is not None:
                res_p1.append(result)

    if res_p1:
        res_p1.sort(key=lambda r: r.get("rmse_combined", r["rmse"]))

        _b1 = res_p1[0]

        _re_log_objective_diagnostic(
            "end of phase 1 (best TRF)",
            float(_b1["rmse"]),
            float(_b1.get("rmse_qwot", 0.0)),
            c._a_p1,
        )

        logging.info(
            "RE phase 1 summary: %d start(s), best: %s | "
            "Delta RMSE_facade vs initial: %+.6f (sp: %+.6f, QWOT: %+.6f)",
            len(res_p1),
            _b1.get("label", "?"),
            float(_b1.get("rmse_combined", _b1["rmse"])) - c.rmse_initial_u,
            float(_b1["rmse"]) - c.rmse_initial_sp,
            float(_b1.get("rmse_qwot", 0.0)) - c.rmse_initial_q,
        )

    c.rmse_phase1_milestone[0] = (
        float(res_p1[0].get("rmse_combined", res_p1[0]["rmse"])) if res_p1 else float("nan")
    )

    c.rmse_final_milestone[0] = c.rmse_phase1_milestone[0]

    if res_p1 and c._re_use_staged_order:
        logging.info(
            "RE staged order: step 1/3 finished (phase 1) - TRF thicknesses only, "
            "nominal indices | RMSE_facade=%.6f",
            float(res_p1[0].get("rmse_combined", res_p1[0]["rmse"])),
        )

        logging.info(
            "RE staged order: planned sequence: "
            "(1) phase 1 thick. | (2) P4+thick. (flat ap scan then joint TRF [thick+ap], nominal indices) | "
            "(3) phase 2a/2b joint DeltaRe + phase 3 shakes + phase 4 full joint"
        )

    return res_p1

def re_execute_phase1_p4_scan(worker) -> None:
    """Step 2/3 in sequential order: flat ap scan + joint TRF thick+ap (nominal indices)."""

    L = worker._re_phase_ns

    results = L.results

    if (
        L._re_use_staged_order
        and results
        and not worker._stop
        and any(float(meta["angle"]) >= 10.0 for meta in L.oblique_config_meta)
    ):
        logging.info(
            "RE staged order: step 2/3 - scalar ap scan (flat across lambda knots) then joint TRF "
            "[thicknesses + %d ap knots]; P4 angular averaging active; nominal indices.",
            int(RE_P4_BEAM_N_KNOTS),
        )

        L._emit_re_prog(
            L._RE_P_SETUP + L._RE_P_P1 + 1.0,
            "RE step 2/3: aperture (P4) + thicknesses (nominal indices)",
        )

        _t_s2_wall = time.perf_counter()

        best_p1_dto = _top_result_dto(results)
        if best_p1_dto is None:
            return

        ep_stage = np.asarray(best_p1_dto.ep, dtype=np.float64).ravel().copy()

        _nap_s2 = int(RE_P4_BEAM_N_KNOTS)

        _lo_ap_s2, _hi_ap_s2 = RE_P4_BEAM_AP_BOUNDS_DEG
        _n_ap_scan_s2 = max(4, int(worker.cfg.get("re_phase4_aperture_scan_points", RE_PHASE4_APERTURE_SCAN_POINTS)))

        _apb_cfg_s2 = worker.cfg.get("re_phase4_ap_bounds_deg")
        if _apb_cfg_s2 is not None:
            _vb = np.asarray(_apb_cfg_s2, dtype=np.float64).ravel()
            if _vb.size >= 2:
                _c0, _c1 = float(_vb[0]), float(_vb[1])
                if 0.0 < _c0 < _c1 < 90.0:
                    _lo_ap_s2, _hi_ap_s2 = _c0, _c1

        _p4_fd_ap_s2 = float(worker.cfg.get("re_p4_ap_fd_step_deg", RE_P4_AP_FD_STEP_DEG))
        _p4_tol_s2 = float(worker.cfg.get("re_phase4_trf_tol_factor", RE_PHASE4_TRF_TOL_FACTOR))
        _p4_nfev_s2 = max(8, int(worker.cfg.get("re_phase4_ep_stage_max_nfev", worker.cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))))

        L._re_state["is_phase4"] = True

        best_ap_s2 = float(
            np.clip(
                L._ap_gui,
                _lo_ap_s2,
                _hi_ap_s2,
            )
        )

        best_cost_s2 = float("inf")

        for test_ap in np.linspace(_lo_ap_s2, _hi_ap_s2, _n_ap_scan_s2):
            _ta = float(test_ap)

            L._re_state["re_aperture_knots"][:] = _ta

            _mse_s2 = float(
                L._mse_grad_accumulate_ep(
                    ep_stage,
                    L.wt_spectral,
                    False,
                    L._correc_nom,
                    return_residuals=False,
                )[0]
            )

            if _mse_s2 < best_cost_s2:
                best_cost_s2 = _mse_s2

                best_ap_s2 = _ta

        L._re_state["re_aperture_knots"][:] = best_ap_s2

        x0_s2 = np.concatenate(
            [
                ep_stage,
                np.full(_nap_s2, float(best_ap_s2), dtype=np.float64),
            ]
        )

        bounds_s2 = (
            np.concatenate(
                [
                    np.asarray(L.bounds_trf[0], dtype=np.float64),
                    np.full(_nap_s2, float(_lo_ap_s2), dtype=np.float64),
                ]
            ),
            np.concatenate(
                [
                    np.asarray(L.bounds_trf[1], dtype=np.float64),
                    np.full(_nap_s2, float(_hi_ap_s2), dtype=np.float64),
                ]
            ),
        )

        i_ap_s2 = L.n_layers_count

        _c_s2 = {
            "x": None,
            "res": None,
            "jac": None,
            "mse": None,
            "i": 0,
            "last_emit": time.perf_counter(),
        }

        def _eval_both_s2(xv_full: np.ndarray, *, emit_interval: float = 5.0) -> None:

            if worker._stop:
                raise REUserStopRequested()

            if _c_s2["x"] is not None and np.array_equal(xv_full, _c_s2["x"]):
                return

            ep_s2 = np.asarray(xv_full[:i_ap_s2], dtype=np.float64).ravel()

            ap_s2 = np.asarray(xv_full[i_ap_s2 : i_ap_s2 + _nap_s2], dtype=np.float64).ravel()

            L._re_state["re_aperture_knots"][:] = ap_s2

            mse_s2, _, r_s2, j_ep_s2 = L._mse_grad_accumulate_ep(
                ep_s2,
                L.wt_spectral,
                True,
                L._correc_nom,
                return_residuals=True,
            )

            j_ap = np.zeros((r_s2.shape[0], _nap_s2), dtype=np.float64)

            b_lo_s2, b_hi_s2 = bounds_s2[0], bounds_s2[1]

            for _k in range(_nap_s2):
                _ik = i_ap_s2 + _k

                _xk = float(xv_full[_ik])

                _hi = float(b_hi_s2[_ik])

                _lo = float(b_lo_s2[_ik])

                _step = min(_p4_fd_ap_s2, _hi - _xk)

                if _step < 1e-12:
                    _step = max(-_p4_fd_ap_s2, _lo - _xk)

                if abs(_step) < 1e-15:
                    continue

                xv_p = np.array(xv_full, dtype=np.float64, copy=True)

                xv_p[_ik] = _xk + _step

                L._re_state["re_aperture_knots"][:] = xv_p[i_ap_s2 : i_ap_s2 + _nap_s2]

                r_p = L._mse_grad_accumulate_ep(
                    xv_p[:i_ap_s2],
                    L.wt_spectral,
                    False,
                    L._correc_nom,
                    return_residuals=True,
                )[2]

                j_ap[:, _k] = (r_p - r_s2) / _step

            L._re_state["re_aperture_knots"][:] = ap_s2

            _c_s2["x"] = xv_full.copy()

            _c_s2["res"] = r_s2

            _c_s2["jac"] = np.hstack([j_ep_s2, j_ap])

            _c_s2["mse"] = float(mse_s2)

            _c_s2["i"] = int(_c_s2["i"]) + 1

            now = time.perf_counter()

            if _c_s2["i"] == 1 or (now - float(_c_s2["last_emit"])) >= emit_interval:
                _c_s2["last_emit"] = now

                rs2 = float(np.sqrt(max(_c_s2["mse"], 0.0)))

                rq2 = L._compute_qwot_rmse(ep_s2, L._correc_nom)

                rmse2 = L._rmse_combined(rs2, rq2)

                _trf_r2 = _re_trf_residual_rms(_c_s2["res"])

                logging.info(
                    "RE step 2/3 [P4+ep] TRF it ~%d  RMSE_facade=%.6f | TRF_RMS(r)=%.6g | ap=%s",
                    int(_c_s2["i"]),
                    rmse2,
                    _trf_r2,
                    np.array2string(ap_s2, precision=2, separator=","),
                )

        def _fun_s2(xv_full: np.ndarray) -> Any:

            _eval_both_s2(xv_full)

            return _c_s2["res"]

        def _jac_s2(xv_full: np.ndarray) -> Any:

            _eval_both_s2(xv_full)

            return _c_s2["jac"]

        try:
            res_s2 = least_squares(
                _fun_s2,
                x0_s2,
                method="trf",
                bounds=bounds_s2,
                jac=_jac_s2,
                x_scale="jac",
                ftol=RE_LBFGSB_FTOL * _p4_tol_s2,
                xtol=RE_LBFGSB_FTOL * _p4_tol_s2,
                gtol=RE_LBFGSB_GTOL * _p4_tol_s2,
                max_nfev=_p4_nfev_s2,
            )

            x_s2 = np.asarray(res_s2.x, dtype=np.float64).ravel()

            ok_s2 = bool(res_s2.success)

            nfev_s2 = int(res_s2.nfev)

        except REUserStopRequested:
            x_s2 = np.asarray(x0_s2, dtype=np.float64).ravel()

            ok_s2 = False

            nfev_s2 = int(_c_s2.get("i", 0))

        except NUMERICAL_FAULT_EXCEPTIONS as _e_s2:
            logging.warning(
                "RE staged order  step 2/3 fallback to phase-1 best: %s",
                _e_s2,
            )

            x_s2 = np.asarray(x0_s2, dtype=np.float64).ravel()

            ok_s2 = False

            nfev_s2 = int(_c_s2.get("i", 0))

        ep_s2_f = np.asarray(x_s2[:i_ap_s2], dtype=np.float64).ravel()

        ap_s2_f = np.asarray(x_s2[i_ap_s2 : i_ap_s2 + _nap_s2], dtype=np.float64).ravel()

        L._re_state["re_aperture_knots"][:] = ap_s2_f

        rmse_s2_sp = float(np.sqrt(max(L._report_mse_spectral(ep_s2_f, L._correc_nom), 0.0)))

        rmse_s2_q = L._compute_qwot_rmse(ep_s2_f, L._correc_nom)

        rmse_s2_c = L._rmse_combined(rmse_s2_sp, rmse_s2_q)

        _kn_s2 = np.asarray(L._re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[:_nap_s2]

        phase_s2_result = REPhase4Result(
            label="P4 aperture+thickness (pre-joint)",
            ep=np.asarray(ep_s2_f, dtype=np.float64).ravel(),
            a=0.0,
            b=0.0,
            f=0.0,
            re_dh_knots=np.array([], dtype=np.float64),
            re_dl_knots=np.array([], dtype=np.float64),
            re_knots_nm=np.array([], dtype=np.float64),
            re_spline_lam_node2_nm=0.0,
            rmse=float(rmse_s2_sp),
            rmse_qwot=float(rmse_s2_q),
            rmse_combined=float(rmse_s2_c),
            nfev=int(best_p1_dto.nfev) + nfev_s2,
            success=bool(ok_s2),
            nfev_phase1=int(best_p1_dto.nfev),
            nfev_phase2_prefit=0,
            re_p4_aperture_deg=float(np.mean(ap_s2_f)),
            re_p4_beam_ap_knots_nm=np.asarray(_kn_s2, dtype=np.float64).ravel(),
            re_p4_beam_ap_knots_deg=np.asarray(ap_s2_f, dtype=np.float64).ravel(),
        )
        _prepend_result_dto(results, phase_s2_result)

        results.sort(key=lambda r: r.get("rmse_combined", r["rmse"]))
        _top_s2_dto = _top_result_dto(results)

        L.rmse_final_milestone[0] = float(_top_s2_dto.rmse_combined if _top_s2_dto is not None else float("nan"))

        _wall_s2 = float(time.perf_counter() - _t_s2_wall)

        _pairs_s2_done = ", ".join(
            f"(lambda={float(lk):.0f}nm->{float(ak):.2f})" for lk, ak in zip(_kn_s2, ap_s2_f, strict=False)
        )

        logging.info(
            "RE staged order  step 2/3 finished | wall_s=%.2f | ls_nfev=%d | success=%s | "
            "RMSE_sp=%.6f RMSE_OT=%.6f RMSE=%.6f | best ap scan flat=%.2f (TRF starter) | "
            "ap=[%s]",
            _wall_s2,
            int(nfev_s2),
            str(bool(ok_s2)),
            rmse_s2_sp,
            rmse_s2_q,
            rmse_s2_c,
            float(best_ap_s2),
            _pairs_s2_done,
        )

    elif L._re_use_staged_order and not any(float(meta["angle"]) >= 10.0 for meta in L.oblique_config_meta):
        logging.info("RE staged order  step 2/3 skipped (all angles < 10 for P4 averaging).")

    elif L._re_use_staged_order and not results and not worker._stop:
        logging.info("RE staged order  step 2/3 skipped (no available phase-1 candidate).")

def re_execute_phase2_splines(worker) -> None:
    """Phase 2: DeltaRe splines + prefit 2a / joint 2b (top-K).

    Structure (kept as single function due to closure coupling):
      §1  L+30   Local alias extraction from worker._re_phase_ns
      §2  L+100  FD config, knots, envelope, Cauchy substrate setup
      §3  L+180  Bounds construction, top-K selection, Tikhonov
      §4  L+320  Closures: _eval_both_p2, _fun_res_p2, _jac_res_p2
      §5  L+700  Top-K loop: prefit 2a + joint 2b per candidate
      §6  L+1170 Finalization: sort, replace, emit live spectrum
    """

    L = worker._re_phase_ns
    _t_p2 = time.perf_counter()

    results = L.results

    wls = L.wls

    re_env_s = L.re_env_s

    n_sub_nominal = L.n_sub_nominal

    lambda_ref = L.lambda_ref

    bounds = L.bounds

    re_p2_plan = L.re_p2_plan

    _bind_p2_plan = L._bind_p2_plan

    _pct_p2a = L._pct_p2a

    _pct_p2b = L._pct_p2b


    _emit_re_prog = L._emit_re_prog

    _emit_re_spectrum_live = L._emit_re_spectrum_live


    _re_use_staged_order = L._re_use_staged_order

    _mse_grad_accumulate_ep = L._mse_grad_accumulate_ep

    wt_spectral = L.wt_spectral

    _correc_nom = L._correc_nom

    _report_mse_spectral = L._report_mse_spectral

    _compute_qwot_rmse = L._compute_qwot_rmse

    _rmse_combined = L._rmse_combined

    _re_state = L._re_state

    n_layers_count = L.n_layers_count

    _alpha_slot = L._alpha_slot

    _a_p2a = L._a_p2a

    _a_p2b = L._a_p2b

    _any_spl_act = L._any_spl_act

    _maxiter_p2b = L._maxiter_p2b

    _re_pct_hi = L._re_pct_hi

    _RE_P_SETUP = L._RE_P_SETUP

    _RE_P_P1 = L._RE_P_P1

    # ── §2 FD config, knots, envelope ────────────────────────────────
    # Phase 2: thicknesses + 2×K knot DeltaRe + lambda knot #2 ; linear interp + envelope clamp ; fixed substrate.

    _fd = _prepare_phase2_fd_settings(worker, re_env_s)
    _p2fd_spl = _fd["_p2fd_spl"]
    _p2fd_lam = _fd["_p2fd_lam"]
    _fd_1s = _fd["_fd_1s"]
    _fd_par = _fd["_fd_par"]
    _fd_nw = _fd["_fd_nw"]
    _nk = _fd["_nk"]
    _knot0 = _fd["_knot0"]
    _env_knot = _fd["_env_knot"]

    logging.info(
        "event=re_phase2 prep=fd nlambda=%d layers=%d stop=%s env_knot_min=%.4f env_knot_max=%.4f scale=%.3g fd_threads=%d parallel=%s",
        len(wls),
        n_layers_count,
        worker._stop,
        float(np.min(_env_knot)),
        float(np.max(_env_knot)),
        re_env_s,
        _fd_nw,
        _fd_par,
    )

    _use_sub_c3 = False

    L._use_sub_c3_shared = False

    # ── §3 Bounds, top-K, Tikhonov ────────────────────────────────────
    if results and not worker._stop:
        bounds_ctx = _prepare_phase2_bounds_and_topk(
            worker,
            results=results,
            bind_p2_plan=_bind_p2_plan,
            emit_re_prog=_emit_re_prog,
            re_p2_plan=re_p2_plan,
            nk=_nk,
            wls=wls,
            re_use_staged_order=_re_use_staged_order,
            env_knot=_env_knot,
            bounds=bounds,
        )
        _top_k = bounds_ctx["_top_k"]
        bounds_p2 = bounds_ctx["bounds_p2"]
        b_lam = bounds_ctx["b_lam"]
        bounds_spline = bounds_ctx["bounds_spline"]
        _act_h = bounds_ctx["_act_h"]
        _act_l = bounds_ctx["_act_l"]
        pl = re_p2_plan[0]
        p2_candidates = []

        n_sp = 2 * _nk + 1

        _n_tab_sub = np.real(np.asarray(n_sub_nominal, dtype=np.complex128)).astype(np.float64).ravel()

        _Phi_sub = re_substrate_cauchy_phi_matrix(wls, lambda_ref)

        _theta0_sub = re_substrate_cauchy_initial_theta(_n_tab_sub, wls, lambda_ref)

        _use_sub_c3 = bool(worker.cfg.get("re_phase2b_substrate_cauchy", True)) and (_theta0_sub is not None)

        L._use_sub_c3_shared = bool(_use_sub_c3)

        if _use_sub_c3:
            _b_sub_c = [(-12.0, 12.0), (-12.0, 12.0), (-12.0, 12.0)]

            bounds_p2 = list(bounds_p2) + _b_sub_c

            logging.info(
                "event=re_phase2b substrate=cauchy status=enabled tube_delta=%.2g nlambda=%d",
                RE_SUB_CAUCHY_TUBE_DELTA,
                len(wls),
            )

        elif bool(worker.cfg.get("re_phase2b_substrate_cauchy", True)):
            logging.warning("event=re_phase2b substrate=cauchy status=unavailable reason=empty_feasible_set")

        elif not bool(worker.cfg.get("re_phase2b_substrate_cauchy", True)):
            logging.info("event=re_phase2b substrate=fixed_tabulated status=active")

        _theta0_sub_arr = (
            np.asarray(_theta0_sub, dtype=np.float64).ravel()[:3]
            if _theta0_sub is not None
            else np.zeros(3, dtype=np.float64)
        )

        bounds_spref = bounds_spline + bounds_spline + [b_lam]

        _prefit_max = (
            int(
                worker.cfg.get(
                    "re_phase2_spline_prefit_maxiter",
                    RE_PHASE2_SPLINE_PREFIT_MAXITER,
                )
            )
            if _any_spl_act
            else 0
        )

        _skip_2a = bool(worker.cfg.get("re_phase2_skip_spline_prefit", False)) or not _any_spl_act

        if _skip_2a:
            _prefit_max = 0

        _hl_w = float(worker.cfg.get("re_hl_delta_re_reg_sqrt_w", RE_HL_DELTA_RE_REG_SQRT_W))

        _dzre_l = float(worker.cfg.get("re_hl_delta_re_deadzone_abs", RE_RE_DEADZONE_DELTA_RE_ABS))

        _dzqw_l = float(worker.cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))

        logging.info(
            "event=re_phase2 prep=joint top_k=%d layers=%d spline_vars=%d prefit_2a_maxiter=%d prefit_2a=%s tikhonov=%s hl_reg_sqrt_w=%s hl_deadzone=%.3g qwot_deadzone=%.3g fd_step_spline=%.2e fd_step_lam2=%.4f",
            _top_k,
            n_layers_count,
            2 * _nk,
            _prefit_max,
            "on" if _prefit_max > 0 else "off",
            worker.cfg.get("re_spline_tikhonov_scale", RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
            f"{_hl_w:g}" if _hl_w > 0.0 else "off",
            _dzre_l,
            _dzqw_l,
            _p2fd_spl,
            _p2fd_lam,
        )

        i0 = n_layers_count

        i_lam = i0 + 2 * _nk

        i_cu = i_lam + 1

        _p2fd_cu = float(
            worker.cfg.get(
                "re_phase2_sub_cauchy_fd_step",
                RE_PHASE2_SUB_CAUCHY_FD_STEP,
            )
        )

        _n_joint_fd = n_sp + (3 if _use_sub_c3 else 0)

        b_lb = np.array([float(b[0]) for b in bounds_p2], dtype=np.float64)

        b_ub = np.array([float(b[1]) for b in bounds_p2], dtype=np.float64)

        bounds_p2_trf = (b_lb, b_ub)

        _emit_re_prog(
            float(pl["prep_end"]),
            f"RE phase 2: spline prefit (maxiter={_prefit_max}) or skip; "
            f"~{1 + (n_sp if _fd_1s else 2 * n_sp)} MSE/grad (FD={'forward' if _fd_1s else 'centered'})...",
        )

        _cb2_ref: list = [None]

        _p2_ki_slot = [0]

        # Label for "RE [...] TRF it" rows (phase 2b joint vs phase 3 shakes).

        _p2_trf_log_tag = ["phase 2b joint"]

        ctx_p2 = REPhase2Context(
            _Phi_sub=_Phi_sub,
            _cb2_ref=_cb2_ref,
            _compute_qwot_rmse=_compute_qwot_rmse,
            _emit_re_prog=_emit_re_prog,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _fd_1s=_fd_1s,
            _fd_nw=_fd_nw,
            _maxiter_p2b=_maxiter_p2b,
            _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
            _n_joint_fd=_n_joint_fd,
            _n_tab_sub=_n_tab_sub,
            _nk=_nk,
            _p2_ki_slot=_p2_ki_slot,
            _p2_trf_log_tag=_p2_trf_log_tag,
            _p2fd_cu=_p2fd_cu,
            _p2fd_lam=_p2fd_lam,
            _p2fd_spl=_p2fd_spl,
            _pct_p2a=_pct_p2a,
            _pct_p2b=_pct_p2b,
            _prefit_max=_prefit_max,
            _re_state=_re_state,
            _rmse_combined=_rmse_combined,
            _t_p2=_t_p2,
            _use_sub_c3=_use_sub_c3,
            i0=i0,
            i_cu=i_cu,
            i_lam=i_lam,
            n_layers_count=n_layers_count,
            n_sp=n_sp,
            pl=pl,
            re_env_s=re_env_s,
            wls=wls,
            wt_spectral=wt_spectral,
            ep_p1=None,
        )

        def _eval_both_p2(xv: np.ndarray, emit_interval: float = 5.0) -> tuple | None:
            return worker._compute_eval_both_p2(ctx_p2, xv, emit_interval)

        def _fun_res_p2(xv: np.ndarray, emit_interval: float = 5.0) -> Any:
            return worker._compute_fun_res_p2(ctx_p2, xv, emit_interval)

        def _jac_res_p2(xv: np.ndarray, emit_interval: float = 5.0) -> Any:
            return worker._compute_jac_res_p2(ctx_p2, xv, emit_interval)

        L._p2_ctx = {
            "_nk": _nk,
            "i0": i0,
            "i_lam": i_lam,
            "b_lb": b_lb,
            "b_ub": b_ub,
            "bounds_p2_trf": bounds_p2_trf,
            "_cb2_ref": _cb2_ref,
            "_p2_ki_slot": _p2_ki_slot,
            "_p2_trf_log_tag": _p2_trf_log_tag,
            "_eval_both_p2": _eval_both_p2,
            "_fun_res_p2": _fun_res_p2,
            "_jac_res_p2": _jac_res_p2,
        }

        # ── §5 Top-K loop: prefit 2a + joint 2b per candidate ────────
        for _ki in range(_top_k):
            if worker._stop:
                break

            _p2_ki_slot[0] = _ki

            candidate_dict = worker._execute_phase2_candidate(
                ki=_ki,
                top_k=_top_k,
                results=results,
                ctx_p2=ctx_p2,
                alpha_slot=_alpha_slot,
                a_p2a=_a_p2a,
                a_p2b=_a_p2b,
                nk=_nk,
                n_sp=n_sp,
                n_layers_count=n_layers_count,
                use_sub_c3=_use_sub_c3,
                theta0_sub_arr=_theta0_sub_arr,
                correc_nom=_correc_nom,
                prefit_max=_prefit_max,
                b_lam=b_lam,
                bounds_spref=bounds_spref,
                bounds_p2_trf=bounds_p2_trf,
                cb2_ref=_cb2_ref,
                report_mse_spectral=_report_mse_spectral,
                compute_qwot_rmse=_compute_qwot_rmse,
                rmse_combined=_rmse_combined,
                emit_re_prog=_emit_re_prog,
                pct_p2a=_pct_p2a,
                pct_p2b=_pct_p2b,
                p2fd_spl=_p2fd_spl,
                p2fd_lam=_p2fd_lam,
                fd_1s=_fd_1s,
                i0=i0,
                i_lam=i_lam,
                i_cu=i_cu,
                pl=pl,
                fun_res_p2=_fun_res_p2,
                jac_res_p2=_jac_res_p2,
            )

            if candidate_dict is None:
                # user stop during prefit 2a
                break

            p2_candidates.append(candidate_dict)

        # ── §6 Finalization ────────────────────────────────────────────
        if p2_candidates:
            p2_candidates.sort(key=lambda r: r.get("rmse_combined", r["rmse"]))

            _replace_all_with_top_dto(
                results,
                REPhase4Result.from_legacy_dict(p2_candidates[0]),
            )

            _cor_best_p2 = p2_result_to_correc_tuple(results[0], _use_sub_c3)
            _top_p2_dto = _top_result_dto(results)
            if _top_p2_dto is None:
                _top_p2_dto = _result_dto_at(results, 0)
            if _top_p2_dto is None:
                _top_p2_dto = REPhase4Result.from_legacy_dict(results[0])

            _emit_re_spectrum_live(
                np.asarray(_top_p2_dto.ep, dtype=np.float64).flatten(),
                int(_top_p2_dto.nfev),
                correc=_cor_best_p2,
                force=True,
                rmse_override=float(_top_p2_dto.rmse_combined),
            )

            _rb = p2_candidates[0]

            _re_log_objective_diagnostic(
                "end of phase 2b (best top-K)",
                float(_rb["rmse"]),
                float(_rb.get("rmse_qwot", 0.0)),
                _a_p2b,
            )

    elif not results:
        logging.warning("RE phase 2: not run (no phase 1 result).")

        _emit_re_prog(
            min(95.0, _RE_P_SETUP + _RE_P_P1 + 4.0),
            "RE phase 2: not run (no phase 1 result).",
        )

    elif worker._stop:
        logging.warning("RE phase 2: not run (stop requested before phase 2).")

        _emit_re_prog(
            min(95.0, _re_pct_hi[0] + 1.0),
            "RE phase 2 cancelled (stopped by user).",
        )

def re_execute_phase2_candidate(
    worker,
    *,
    ki: int,
    top_k: int,
    results: list,
    ctx_p2: Any,
    alpha_slot: list,
    a_p2a: float,
    a_p2b: float,
    nk: int,
    n_sp: int,
    n_layers_count: int,
    use_sub_c3: bool,
    theta0_sub_arr: np.ndarray,
    correc_nom: Any,
    prefit_max: int,
    b_lam: tuple,
    bounds_spref: list,
    bounds_p2_trf: tuple,
    cb2_ref: list,
    report_mse_spectral: Any,
    compute_qwot_rmse: Any,
    rmse_combined: Any,
    emit_re_prog: Any,
    pct_p2a: Any,
    pct_p2b: Any,
    p2fd_spl: float,
    p2fd_lam: float,
    fd_1s: bool,
    i0: int,
    i_lam: int,
    i_cu: int,
    pl: Any,
    fun_res_p2: Any,
    jac_res_p2: Any,
) -> dict | None:
    """Run prefit 2a + joint 2b for one top-K candidate.

    Returns the legacy result dict, or None if the user stopped during prefit 2a.
    """
    ep_p1 = np.asarray(results[ki]["ep"], dtype=np.float64).flatten()
    ctx_p2.ep_p1 = ep_p1

    nfev_p1 = int(results[ki].get("nfev", 0))

    alpha_slot[0] = a_p2a

    x0_p2 = np.concatenate(
        [
            ep_p1,
            np.zeros(2 * nk, dtype=np.float64),
            np.array([RE_SPLINE_NODE2_DEFAULT_NM], dtype=np.float64),
        ]
        + ([theta0_sub_arr] if use_sub_c3 else [])
    )

    rmse_p2_x0_sp = float(np.sqrt(max(report_mse_spectral(ep_p1, correc_nom), 0.0)))

    rmse_p2_x0 = rmse_combined(rmse_p2_x0_sp, compute_qwot_rmse(ep_p1, correc_nom))

    nfev_phase2_prefit = 0

    logging.info(
        "RE phase 2  candidate %d/%d (phase1 nfev=%d) RMSE start=%.6f",
        ki + 1,
        top_k,
        nfev_p1,
        rmse_p2_x0,
    )

    if prefit_max > 0 and rmse_p2_x0 > RE_PHASE2A_SKIP_PREFIT_RMSE_THRESHOLD and not worker._stop:
        _t_pf = time.perf_counter()

        x0_pf = np.concatenate(
            [
                np.zeros(2 * nk, dtype=np.float64),
                np.array([RE_SPLINE_NODE2_DEFAULT_NM], dtype=np.float64),
            ]
        )

        _cb2a = {
            "x": None,
            "res": None,
            "jac": None,
            "mse": None,
            "i": 0,
            "last_emit": time.perf_counter(),
            "tk_w_c": None,
            "tk_lam2": None,
            "fd_executor": None,
        }

        def _eval_both_p2a(
            x_sp: np.ndarray,
            _cb2a=_cb2a,
            ep_p1=ep_p1,
            _ki=ki,
            _t_pf=_t_pf,
        ) -> tuple | None:
            return worker._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, ep_p1, _ki, _t_pf)

        def _fun_res_p2a(x_sp: np.ndarray, _cb2a=_cb2a) -> Any:
            return worker._compute_fun_res_p2a(ctx_p2, x_sp, _cb2a)

        def _jac_res_p2a(x_sp: np.ndarray, _cb2a=_cb2a) -> Any:
            return worker._compute_jac_res_p2a(ctx_p2, x_sp, _cb2a)

        logging.info(
            "RE phase 2a  starting TRF (vars=%d, lambda\u2082[%.0f,%.0f] nm)",
            n_sp,
            float(b_lam[0]),
            float(b_lam[1]),
        )

        bounds_pf_trf = _build_p2_prefit_bounds(bounds_spref)

        try:
            res_pf = least_squares(
                _fun_res_p2a,
                x0_pf,
                method="trf",
                bounds=bounds_pf_trf,
                jac=_jac_res_p2a,
                x_scale="jac",
                ftol=RE_LBFGSB_FTOL * RE_PHASE2A_PREFIT_TOL_FACTOR,
                xtol=RE_LBFGSB_FTOL * RE_PHASE2A_PREFIT_TOL_FACTOR,
                gtol=RE_LBFGSB_GTOL * RE_PHASE2A_PREFIT_TOL_FACTOR,
                max_nfev=max(10, prefit_max),
            )

        except REUserStopRequested:
            logging.info("RE phase 2a  stopped by user")
            return None

        finally:
            _ex_pf = _cb2a.get("fd_executor")

            if _ex_pf is not None:
                _ex_pf.shutdown(wait=False)

                _cb2a["fd_executor"] = None

        nfev_phase2_prefit = int(getattr(res_pf, "nfev", 0))

        x_pf = np.asarray(res_pf.x, dtype=np.float64).ravel()

        x0_p2 = np.concatenate([ep_p1, x_pf] + ([theta0_sub_arr] if use_sub_c3 else []))

        lam_pf = float(x_pf[2 * nk])

        cor_pf = ("spline", x_pf[:nk], x_pf[nk : 2 * nk], lam_pf)

        rmse_sp_pf = float(np.sqrt(max(report_mse_spectral(ep_p1, cor_pf), 0.0)))

        rmse_after_prefit = rmse_combined(rmse_sp_pf, compute_qwot_rmse(ep_p1, cor_pf))

        _dt_pf = time.perf_counter() - _t_pf

        logging.info(
            f"RE phase 2a (splines+lambda2, fixed ep) end {_dt_pf:.1f}s "
            f"nfev={nfev_phase2_prefit} grad_calls{_cb2a['i']} "
            f" RMSE {rmse_p2_x0:.6f} -> {rmse_after_prefit:.6f}"
        )

        emit_re_prog(
            pct_p2a(pl, ki, 1.0),
            f"RE phase 2a done  RMSE {rmse_after_prefit:.6f}, {nfev_phase2_prefit} evals",
        )

    else:
        rmse_after_prefit = rmse_p2_x0

        logging.info("RE phase 2a  skipped (re_phase2_spline_prefit_maxiter=0), using zero splines for 2b.")

        emit_re_prog(
            pct_p2b(pl, ki, 0.0),
            "RE phase 2a skipped  starting joint phase 2b...",
        )

    alpha_slot[0] = a_p2b

    _p2b_sub_log = (
        f"+ Cauchy substrate (tube +/-{RE_SUB_CAUCHY_TUBE_DELTA:g}) "
        if use_sub_c3
        else "tabulated substrate; "
    )

    logging.info(
        f"RE phase 2b: joint TRF {n_layers_count} ep + spline (K={nk}, "
        f"lambda\u2082[{b_lam[0]:.0f},{b_lam[1]:.0f}] nm) {_p2b_sub_log}"
        f"FD spl={p2fd_spl:g}, FD lambda\u2082={p2fd_lam:g} ({'forward' if fd_1s else 'centered'})  "
        f"phase1 nfev={nfev_p1}  start RMSE={rmse_after_prefit:.6f}"
    )

    emit_re_prog(
        pct_p2b(pl, ki, 0.06),
        f"RE phase 2  joint optimization, start RMSE {rmse_after_prefit:.6f}...",
    )

    _t_p2 = time.perf_counter()

    cb2_ref[0] = {
        "x": None,
        "res": None,
        "jac": None,
        "mse": None,
        "best_rmse_combined": None,
        "i": 0,
        "last_emit": time.perf_counter(),
        "tk_w_c": None,
        "tk_lam2": None,
    }

    maxiter_p2b = int(worker.cfg.get("re_phase2b_maxiter", RE_PHASE2B_MAXITER))

    _dim_p2b = n_layers_count + n_sp + (3 if use_sub_c3 else 0)

    logging.info(
        "RE phase 2b  starting joint TRF (dim=%d)",
        _dim_p2b,
    )

    emit_re_prog(
        pct_p2b(pl, ki, 0.1),
        f"RE phase 2b  joint TRF dim={_dim_p2b} (TRF max_nfev={max(10, maxiter_p2b)})...",
    )

    try:
        res_p2 = least_squares(
            fun_res_p2,
            x0_p2,
            method="trf",
            bounds=bounds_p2_trf,
            jac=jac_res_p2,
            x_scale="jac",
            ftol=RE_LBFGSB_FTOL,
            xtol=RE_LBFGSB_FTOL,
            gtol=RE_LBFGSB_GTOL,
            max_nfev=max(10, maxiter_p2b),
        )

    except REUserStopRequested:
        _crp = cb2_ref[0]

        if _crp is not None and _crp.get("x") is not None:
            _xf = np.asarray(_crp["x"], dtype=np.float64).ravel()

            _nfev_p2b = int(_crp.get("i", 0))

        else:
            _xf = np.asarray(x0_p2, dtype=np.float64).ravel()

            _nfev_p2b = 0

        res_p2 = SimpleNamespace(
            x=_xf.copy(),
            nfev=_nfev_p2b,
            success=False,
        )

    if not getattr(res_p2, "success", True):
        logging.warning(
            "RE phase 2b: TRF did not converge (nfev=%d, message=%s)",
            getattr(res_p2, "nfev", 0),
            getattr(res_p2, "message", "unknown"),
        )

    ep_end, dh_end, dl_end, lam_end, th_end, rmse_p2, rmse_qwot_p2, rmse_comb_p2 = _build_phase2b_output(
        res_p2=res_p2,
        x0_p2=x0_p2,
        cb2_ref=cb2_ref,
        n_layers_count=n_layers_count,
        nk=nk,
        i0=i0,
        i_lam=i_lam,
        i_cu=i_cu,
        use_sub_c3=use_sub_c3,
        report_mse_spectral=report_mse_spectral,
        compute_qwot_rmse=compute_qwot_rmse,
        rmse_combined=rmse_combined,
        alpha_slot=alpha_slot,
    )
    knots_end = re_knots_wavelengths(lam_end)

    _dt_p2 = time.perf_counter() - _t_p2

    logging.info(
        f"RE phase 2b end {_dt_p2:.1f}s nfev={res_p2.nfev} "
        f"RMSE_spectral={rmse_p2:.6f} | RMSE_QWOT={rmse_qwot_p2:.6f} | "
        f"RMSE_combined={rmse_comb_p2:.6f} (={alpha_slot[0]}) "
        f"{format_re_spline_knots_log(knots_end, dh_end, dl_end)}"
    )

    emit_re_prog(
        pct_p2b(pl, ki, 1.0),
        f"RE phase 2 done - "
        f"RMSE_sp={rmse_p2:.5f} | RMSE_OT={rmse_qwot_p2:.5f} | "
        f"RMSE={rmse_comb_p2:.5f}, nfev={res_p2.nfev}",
    )

    phase2_result = _build_phase2_result(
        res_p2=res_p2,
        ep_end=ep_end,
        dh_end=dh_end,
        dl_end=dl_end,
        knots_end=knots_end,
        lam_end=lam_end,
        rmse_p2=rmse_p2,
        rmse_qwot_p2=rmse_qwot_p2,
        rmse_comb_p2=rmse_comb_p2,
        nfev_p1=nfev_p1,
        nfev_phase2_prefit=nfev_phase2_prefit,
        th_end=th_end,
    )
    return phase2_result.to_legacy_dict()

def re_run_phase4_joint_trf(
    worker,
    *,
    p4_trf_nfev: int,
    nap: int,
    x0_base: np.ndarray,
    best_ap: float,
    lo_ap: float,
    hi_ap: float,
    bounds_p2_trf: tuple,
    p4_fd_ap: float,
    p4_tol: float,
    i0: int,
    i_lam: int,
    i_cu: int,
    nk: int,
    n_layers_count: int,
    use_sub_c3: bool,
    kn_log: np.ndarray,
    wmin_obj: float,
    wmax_obj: float,
    fun_res_p2: Any,
    eval_both_p2: Any,
    cb2_ref: list,
    re_state: dict,
    p2_trf_log_tag: list,
    p2_ki_slot: list,
    insert_p4_result: Any,
    results: list,
) -> tuple:
    """Joint TRF optimization for phase 4 beam aperture.

    Returns (p4_trf_wall_s, p4_trf_mse_evals, p4_best_seen_rmse).
    Only runs if p4_trf_nfev > 0 and not stopped.
    """
    p4_trf_wall_s = 0.0
    p4_trf_mse_evals = 0
    p4_best_seen_rmse: float | None = None

    if p4_trf_nfev <= 0 or worker._stop:
        return p4_trf_wall_s, p4_trf_mse_evals, p4_best_seen_rmse

    x0_p4 = np.concatenate([x0_base, np.full(nap, float(best_ap), dtype=np.float64)])
    bounds_p4 = _build_phase4_aperture_bounds(bounds_p2_trf, nap, lo_ap, hi_ap)

    i_ap0 = len(x0_p4) - nap

    def _restore_aperture_knots(xv: np.ndarray) -> None:
        re_state["re_aperture_knots"][:] = xv[i_ap0 : i_ap0 + nap]

    def _fun_res_p4(xv) -> Any:
        _restore_aperture_knots(xv)
        return fun_res_p2(xv[:i_ap0], emit_interval=8.0)

    def _jac_res_p4(xv_full: np.ndarray) -> np.ndarray:
        _restore_aperture_knots(xv_full)
        eval_both_p2(xv_full[:i_ap0], emit_interval=1.0e9)
        r0 = np.asarray(cb2_ref[0]["res"], dtype=np.float64).copy()
        j0 = np.asarray(cb2_ref[0]["jac"], dtype=np.float64).copy()
        j_ap = np.zeros((r0.shape[0], nap), dtype=np.float64)
        b_lo, b_hi = bounds_p4[0], bounds_p4[1]

        for _k in range(nap):
            _ik = i_ap0 + _k
            _xk = float(xv_full[_ik])
            _step = min(p4_fd_ap, float(b_hi[_ik]) - _xk)
            if _step < 1e-12:
                _step = max(-p4_fd_ap, float(b_lo[_ik]) - _xk)
            if abs(_step) < 1e-15:
                continue
            xv_p = np.array(xv_full, dtype=np.float64, copy=True)
            xv_p[_ik] = _xk + _step
            _restore_aperture_knots(xv_p)
            eval_both_p2(xv_p[:i_ap0], emit_interval=1.0e9)
            j_ap[:, _k] = (np.asarray(cb2_ref[0]["res"], dtype=np.float64) - r0) / _step

        _restore_aperture_knots(xv_full)
        eval_both_p2(xv_full[:i_ap0], emit_interval=1.0e9)
        return np.hstack([j0, j_ap])

    cb2_ref[0] = {
        "x": None,
        "res": None,
        "jac": None,
        "mse": None,
        "best_rmse_combined": None,
        "i": 0,
        "last_emit": time.perf_counter(),
        "tk_w_c": None,
        "tk_lam2": None,
    }

    p2_trf_log_tag[0] = "phase 4 finale"
    p2_ki_slot[0] = 0

    logging.info(
        "RE phase 4: **joint TRF** - %d **independent** ap (lambda-stepped active in the model); "
        "starting point = best flat scan %.6f on all knots.",
        nap,
        float(best_ap),
    )

    _t_p4_trf_wall = time.perf_counter()

    try:
        res_p4 = least_squares(
            _fun_res_p4,
            x0_p4,
            method="trf",
            bounds=bounds_p4,
            jac=_jac_res_p4,
            x_scale="jac",
            ftol=RE_LBFGSB_FTOL * p4_tol,
            xtol=RE_LBFGSB_FTOL * p4_tol,
            gtol=RE_LBFGSB_GTOL * p4_tol,
            max_nfev=max(8, p4_trf_nfev),
        )

        x_p4 = res_p4.x
        re_state["re_aperture_knots"][:] = x_p4[i_ap0 : i_ap0 + nap]
        ep_p4_f = np.asarray(x_p4[:n_layers_count], dtype=np.float64)
        dh_p4 = x_p4[i0 : i0 + nk]
        dl_p4 = x_p4[i0 + nk : i_lam]
        lam_p4 = float(x_p4[i_lam])
        th_p4 = np.asarray(x_p4[i_cu : i_cu + 3], dtype=np.float64).ravel() if use_sub_c3 else None
        _ap_i = np.asarray(x0_p4[i_ap0 : i_ap0 + nap], dtype=np.float64).ravel()
        _ap_f = np.asarray(x_p4[i_ap0 : i_ap0 + nap], dtype=np.float64).ravel()

        _cost_0 = None
        try:
            re_state["re_aperture_knots"][:] = _ap_i
            eval_both_p2(x0_base, emit_interval=1.0e9)
            _r0 = cb2_ref[0]["res"]
            _cost_0 = float(np.dot(_r0, _r0))
        except NUMERICAL_FAULT_EXCEPTIONS:
            pass

        # Restore knot apertures to TRF solution
        re_state["re_aperture_knots"][:] = _ap_f

        _cost_f = float(getattr(res_p4, "cost", np.nan))
        _opt = float(getattr(res_p4, "optimality", float("nan")))
        _njev = int(getattr(res_p4, "njev", -1))

        p4_trf_wall_s = float(time.perf_counter() - _t_p4_trf_wall)
        p4_trf_mse_evals = int(cb2_ref[0]["i"])
        p4_best_seen_rmse = (
            float(cb2_ref[0]["best_rmse_combined"])
            if cb2_ref[0].get("best_rmse_combined") is not None
            else None
        )

        _log_phase4_trf_summary(
            res_p4=res_p4,
            _cost_0=_cost_0,
            _cost_f=_cost_f,
            _opt=_opt,
            _njev=_njev,
            _ap_i=_ap_i,
            _ap_f=_ap_f,
            kn_log=kn_log,
            wmin_obj=wmin_obj,
            wmax_obj=wmax_obj,
            p4_trf_wall_s=p4_trf_wall_s,
            p4_trf_mse_evals=p4_trf_mse_evals,
            nap=nap,
        )

        insert_p4_result(
            ep_f=ep_p4_f,
            dh_v=dh_p4,
            dl_v=dl_p4,
            lam_v=lam_p4,
            th_v=th_p4,
            nfev_extra=int(res_p4.nfev),
            p4_label_suffix="P4 aperture+TRF",
            success=bool(res_p4.success),
        )

        if p4_best_seen_rmse is not None and results:
            _p4_top_dto = _top_result_dto(results)
            if _p4_top_dto is None:
                _p4_top_dto = _result_dto_at(results, 0)
            if _p4_top_dto is None:
                _sel = float("nan")
            else:
                _sel = float(_p4_top_dto.rmse_combined)

            logging.info(
                "RE phase 4 TRF best tracker | RMSE_best_seen=%.6f | RMSE_selected_result=%.6f",
                float(p4_best_seen_rmse),
                _sel,
            )

            _gap = float(_sel - float(p4_best_seen_rmse))

            if _gap < -1e-10:
                logging.info(
                    "RE phase 4 invariant check | selected_result (%.6f) < best_seen (%.6f), gap=%.6g "
                    "-> final selection improved beyond tracked intermediate best (acceptable).",
                    _sel,
                    float(p4_best_seen_rmse),
                    _gap,
                )
            elif _gap > 1e-4:
                logging.warning(
                    "RE phase 4 invariant check | selected_result (%.6f) > best_seen (%.6f), gap=%.6g "
                    "-> best intermediate was not retained as final selected result.",
                    _sel,
                    float(p4_best_seen_rmse),
                    _gap,
                )
            else:
                logging.info(
                    "RE phase 4 invariant check | OK (selected_result and best_seen consistent, gap=%.6g).",
                    _gap,
                )

    except REUserStopRequested:
        if p4_trf_wall_s <= 0.0:
            p4_trf_wall_s = float(time.perf_counter() - _t_p4_trf_wall)
        p4_trf_mse_evals = int(cb2_ref[0].get("i", 0))
        logging.info(
            "RE phase 4 TRF interrupted | user stop  wall_partial=%.4fs MSE_ep_partial=%d  "
            "last cached state may be stale; compare logs above for scan/TRF progress",
            p4_trf_wall_s,
            p4_trf_mse_evals,
        )

    return p4_trf_wall_s, p4_trf_mse_evals, p4_best_seen_rmse

