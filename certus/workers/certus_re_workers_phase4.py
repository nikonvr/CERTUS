from certus.utils.certus_re_math import re_envelope_max_delta_n
from certus.utils.certus_re_config import RE_PHASE4_TRF_TOL_FACTOR
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_P4_AP_FD_STEP_DEG
from certus.utils.certus_re_config import RE_LBFGSB_GTOL
from certus.utils.certus_re_config import RE_LBFGSB_FTOL
from certus.utils.certus_re_math import re_compute_spline_basis_matrix
from certus.utils.certus_re_math import re_compute_tikhonov_weights
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
import logging
import time
import math
from copy import deepcopy
import numpy as np
from typing import Any, Callable

from certus.core.certus_core import CFG, get_float_dtype, get_complex_dtype
from certus.core.certus_lazy_imports import lazy_scipy
scipy = lazy_scipy()
from certus.core.certus_re_config import REPhase4Result, RE_RESULT_LABEL_WITH_DRIFT, _prepend_result_dto
from certus.utils.certus_re_math import (
    RE_P4_BEAM_N_KNOTS,
    re_compute_spline_basis_matrix,
    re_compute_tikhonov_weights,
    re_envelope_max_delta_n,
    re_knots_wavelengths,
)

#
from certus.utils.certus_re_math import _re_p4_ap_band_intervals_str
from certus.utils.certus_re_helpers import _re_trf_residual_rms, RE_GUI_DEFAULT_BEAM_APERTURE_DEG

# from certus.core.certus_re_solvers import *  # Unused
from certus.workers.certus_re_worker_utils import p2_result_to_correc_tuple


class REPhase4Strategy:
    def _get_phase4_aperture_bounds(self, worker) -> tuple[float, float]:
        """Return validated beam aperture bounds for phase 4."""
        lo_ap, hi_ap = RE_P4_BEAM_AP_BOUNDS_DEG
        apb_cfg = worker.cfg.get("re_phase4_ap_bounds_deg")
        if apb_cfg is not None:
            vb = np.asarray(apb_cfg, dtype=np.float64).ravel()
            if vb.size >= 2:
                c0, c1 = (float(vb[0]), float(vb[1]))
                if 0.0 < c0 < c1 < 90.0:
                    lo_ap, hi_ap = (c0, c1)
        return (lo_ap, hi_ap)

    def _run_phase4_aperture_scan(
        self,
        worker,
        *,
        _emit_re_prog: Callable,
        _nap: int,
        _lo_ap: float,
        _hi_ap: float,
        _n_ap_scan: int,
        x0_base: np.ndarray,
        _eval_both_p2: Callable,
        _cb2_ref: list,
        _re_state: dict,
        _report_mse_spectral: Callable,
        _cor_base: tuple,
        ep_p4: np.ndarray,
        _kn_log: np.ndarray,
        _wmin_obj: float,
        _wmax_obj: float,
    ) -> tuple[list[tuple[float, float]], float, float, float, int, float]:
        """Run the aperture scan phase 4 logic."""
        _emit_re_prog(
            98.5,
            f"RE phase 4: scalar ap scan ({_n_ap_scan} pts, {_lo_ap} to {_hi_ap} deg): same ap on all {_nap} lambda knots per trial (flat beam during scan; joint TRF -> indep. ap per lambda knot)",
        )
        logging.info(
            "RE phase 4: during **scan**, a single ap is set at a time, replicated over all %d lambda knots (no chromatic steps at this stage).",
            _nap,
        )
        best_ap = 1.0
        best_ls_sq = float("inf")
        _p4_scan_emit = 1000000000.0
        _p4_scan_trace: list[tuple[float, float]] = []
        _p4_cb_i_before_scan = int(_cb2_ref[0]["i"])
        _t_p4_scan_wall = time.perf_counter()
        for test_ap in np.linspace(_lo_ap, _hi_ap, _n_ap_scan):
            if worker._stop:
                break
            _ta = float(test_ap)
            _re_state["re_aperture_knots"][:] = _ta
            _eval_both_p2(x0_base, emit_interval=_p4_scan_emit)
            _r_sc = _cb2_ref[0]["res"]
            _cost_sc = float(np.dot(_r_sc, _r_sc))
            _p4_scan_trace.append((_ta, _cost_sc))
            logging.debug(
                "RE phase 4 scan step | ap_deg=%.2f | ||r||^2=%.8g | n_res=%d", _ta, _cost_sc, int(_r_sc.size)
            )
            if _cost_sc < best_ls_sq:
                best_ls_sq = _cost_sc
                best_ap = _ta
        _re_state["re_aperture_knots"][:] = best_ap
        _eval_both_p2(x0_base, emit_interval=_p4_scan_emit)
        best_rmse_ap = float(np.sqrt(max(_report_mse_spectral(ep_p4, _cor_base), 0.0)))
        _p4_scan_wall_s = float(time.perf_counter() - _t_p4_scan_wall)
        _p4_scan_mse_evals = int(_cb2_ref[0]["i"]) - _p4_cb_i_before_scan
        logging.info(
            "RE phase 4 scan profile | wall_s=%.4f | MSE_ep_delta=%d | scan_steps=%d | s_per_MSE_ep%.5f | opt: re_phase4_aperture_scan_points ou snap grille / warm cache",
            _p4_scan_wall_s,
            _p4_scan_mse_evals,
            len(_p4_scan_trace),
            _p4_scan_wall_s / max(_p4_scan_mse_evals, 1),
        )
        if _p4_scan_trace:
            _costs = [c for _, c in _p4_scan_trace]
            _worst_ls = float(max(_costs))
            _spread = _worst_ls - float(best_ls_sq)
            logging.info(
                "RE phase 4 scan summary | n_steps=%d | best_ap_deg=%.2f | min||r||^2=%.8g | max||r||^2=%.8g | spread=%.8g | RMSE_sp(at_best)~%.6f | tune: re_phase4_aperture_scan_points bounds",
                len(_p4_scan_trace),
                best_ap,
                best_ls_sq,
                _worst_ls,
                _spread,
                best_rmse_ap,
            )
            logging.info(
                "RE phase 4 scan best plateaus (explicit): %s",
                _re_p4_ap_band_intervals_str(
                    _kn_log, np.full(_nap, float(best_ap), dtype=np.float64), _wmin_obj, _wmax_obj
                ),
            )
            logging.debug(
                "RE phase 4 scan detail | " + " | ".join((f"ap={a:.2f}||r||2={c:.6g}" for a, c in _p4_scan_trace))
            )
        return (_p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap)

    def _get_phase4_scan_inputs(
        self,
        worker,
        x0_base: np.ndarray,
        _nap: int,
        _ap_gui: float,
        wls: np.ndarray,
        oblique_config_meta: list[dict[str, Any]],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float], list[float], str]:
        """Build derived phase-4 scan inputs and diagnostics."""
        _kn_log = np.asarray(worker._re_phase_ns._re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[:_nap]
        _p4_hi_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) >= 10.0})
        _p4_lo_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) < 10.0})
        _kn_sorted_cfg = np.sort(np.asarray(_kn_log, dtype=np.float64).ravel().copy())
        _p4_band_thr = np.array(
            [0.5 * (_kn_sorted_cfg[i] + _kn_sorted_cfg[i + 1]) for i in range(_nap - 1)], dtype=np.float64
        )
        _p4_scan_plateaus_s = _re_p4_ap_band_intervals_str(
            _kn_log, np.full(_nap, float(_ap_gui), dtype=np.float64), float(np.min(wls)), float(np.max(wls))
        )
        return (
            _kn_log,
            _p4_band_thr,
            _p4_scan_plateaus_s,
            _p4_hi_ang,
            _p4_lo_ang,
            repr(worker.cfg.get("re_p4_beam_ap_knots_nm")),
        )

    def _build_phase4_result(
        self,
        worker,
        *,
        ep_f: np.ndarray,
        dh_v: np.ndarray,
        dl_v: np.ndarray,
        lam_v: float,
        th_v: np.ndarray | None,
        nfev_extra: int,
        p4_label_suffix: str,
        success: bool,
        best_res_dto: REPhase4Result,
        _use_sub_c3: bool,
        _report_mse_spectral,
        _compute_qwot_rmse,
        _rmse_combined,
        _re_state: dict[str, Any],
        wls: np.ndarray,
        _wmin_obj: float,
        _wmax_obj: float,
    ) -> tuple[REPhase4Result, float]:
        b_mc = re_compute_spline_basis_matrix(re_knots_wavelengths(lam_v), wls)
        env_c = re_envelope_max_delta_n(wls, scale=worker._re_phase_ns.re_env_s)
        tk_mc = re_compute_tikhonov_weights(re_knots_wavelengths(lam_v), wls)
        if _use_sub_c3 and th_v is not None:
            cor_p4 = (
                "spline_cached_sub3",
                dh_v,
                dl_v,
                lam_v,
                b_mc,
                env_c,
                tk_mc,
                float(th_v[0]),
                float(th_v[1]),
                float(th_v[2]),
            )
        else:
            cor_p4 = ("spline_cached", dh_v, dl_v, lam_v, b_mc, env_c, tk_mc)
        rmse_p4_sp = float(np.sqrt(max(_report_mse_spectral(ep_f, cor_p4), 0.0)))
        rmse_qwot_p4 = _compute_qwot_rmse(ep_f, cor_p4)
        rmse_comb_p4 = _rmse_combined(rmse_p4_sp, rmse_qwot_p4)
        _ak4 = np.asarray(_re_state["re_aperture_knots"], dtype=np.float64).ravel()[: int(RE_P4_BEAM_N_KNOTS)]
        _kn4 = np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[: int(RE_P4_BEAM_N_KNOTS)]
        logging.info(
            "RE phase 4 result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | ap_deg(n knots)=%s | knots_lam_nm=%s | label=%s | tune: re_envelope_scale re_qwot_penalty_weight alpha schedule",
            rmse_comb_p4,
            rmse_p4_sp,
            rmse_qwot_p4,
            np.array2string(_ak4, precision=2, separator=","),
            np.array2string(_kn4, precision=2, separator=","),
            p4_label_suffix,
        )
        logging.info(
            "RE phase 4 plateaus (result explicit): %s", _re_p4_ap_band_intervals_str(_kn4, _ak4, _wmin_obj, _wmax_obj)
        )
        phase4_result = REPhase4Result(
            label=RE_RESULT_LABEL_WITH_DRIFT + f" ({p4_label_suffix})",
            ep=np.asarray(ep_f, dtype=np.float64).flatten(),
            a=0.0,
            b=0.0,
            f=0.0,
            re_dh_knots=np.asarray(dh_v, dtype=np.float64).flatten(),
            re_dl_knots=np.asarray(dl_v, dtype=np.float64).flatten(),
            re_knots_nm=np.asarray(re_knots_wavelengths(lam_v), dtype=np.float64).flatten(),
            re_spline_lam_node2_nm=float(lam_v),
            rmse=float(rmse_p4_sp),
            rmse_qwot=float(rmse_qwot_p4),
            rmse_combined=float(rmse_comb_p4),
            nfev=int(best_res_dto.nfev) + int(nfev_extra),
            success=bool(success),
            nfev_phase1=int(best_res_dto.nfev_phase1),
            nfev_phase2_prefit=int(best_res_dto.nfev_phase2_prefit),
            re_p4_aperture_deg=float(np.mean(_ak4)),
            re_p4_beam_ap_knots_nm=np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[
                : int(RE_P4_BEAM_N_KNOTS)
            ],
            re_p4_beam_ap_knots_deg=np.asarray(_ak4, dtype=np.float64).flatten(),
            re_sub_cauchy_a0=float(th_v[0]) if _use_sub_c3 and th_v is not None else None,
            re_sub_cauchy_a1=float(th_v[1]) if _use_sub_c3 and th_v is not None else None,
            re_sub_cauchy_a2=float(th_v[2]) if _use_sub_c3 and th_v is not None else None,
        )
        return (phase4_result, rmse_comb_p4)

    def _execute_phase4_beam(self, worker) -> None:
        """Phase 4: beam aperture (stepped ap over lambda), scan + joint TRF."""
        L = worker._re_phase_ns
        results = L.results
        _p2_ctx = L._p2_ctx
        _use_sub_c3 = bool(L._use_sub_c3_shared)
        if not _p2_ctx:
            logging.warning("RE phase 4 skipped: phase-2 context unavailable.")
            return
        _nk = int(_p2_ctx["_nk"])
        i0 = int(_p2_ctx["i0"])
        i_lam = int(_p2_ctx["i_lam"])
        i_cu = i_lam + 1
        _cb2_ref = _p2_ctx["_cb2_ref"]
        _p2_ki_slot = _p2_ctx["_p2_ki_slot"]
        _p2_trf_log_tag = _p2_ctx["_p2_trf_log_tag"]
        _eval_both_p2 = _p2_ctx["_eval_both_p2"]
        _fun_res_p2 = _p2_ctx["_fun_res_p2"]
        bounds_p2_trf = _p2_ctx["bounds_p2_trf"]
        oblique_config_meta = L.oblique_config_meta
        _re_state = L._re_state
        _emit_re_prog = L._emit_re_prog
        _re_use_staged_order = L._re_use_staged_order
        _correc_nom = L._correc_nom
        n_layers_count = L.n_layers_count
        wls = L.wls
        _ap_gui = L._ap_gui
        rmse_final_milestone = L.rmse_final_milestone
        _report_mse_spectral = L._report_mse_spectral
        _compute_qwot_rmse = L._compute_qwot_rmse
        _rmse_combined = L._rmse_combined
        re_env_s = L.re_env_s
        _has_high_angle = any((float(meta["angle"]) >= 10.0 for meta in oblique_config_meta))
        _p4_best_seen_rmse: float | None = None
        if results and (not worker._stop):
            best_res = results[0]
            best_res_dto = REPhase4Result.from_legacy_dict(best_res)
            ep_p4 = np.asarray(best_res_dto.ep, dtype=np.float64)
            _x0_p4 = [ep_p4]
            if best_res_dto.re_dh_knots.size > 0:
                _x0_p4.append(np.asarray(best_res_dto.re_dh_knots, dtype=np.float64))
                _x0_p4.append(np.asarray(best_res_dto.re_dl_knots, dtype=np.float64))
                _x0_p4.append(np.array([best_res_dto.re_spline_lam_node2_nm], dtype=np.float64))
                if _use_sub_c3 and best_res_dto.re_sub_cauchy_a0 is not None:
                    _x0_p4.append(
                        np.array(
                            [
                                best_res_dto.re_sub_cauchy_a0,
                                best_res_dto.re_sub_cauchy_a1,
                                best_res_dto.re_sub_cauchy_a2,
                            ],
                            dtype=np.float64,
                        )
                    )
            if _has_high_angle and len(_x0_p4) > 1:
                _t_p4_wall = time.perf_counter()
                _emit_re_prog(
                    98.0,
                    f"RE step 3/3: full joint optimization + beam (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots)"
                    if _re_use_staged_order
                    else f"RE phase 4: beam aperture (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots) - re_phase4_* cfg",
                )
                _re_state["is_phase4"] = True
                _re_state["p4_prof"] = {
                    "phy_wall_s": 0.0,
                    "phi_calls": 0,
                    "band_groups": 0,
                    "band_mask_steps": 0,
                    "meta_p4_count": 0,
                    "n_wls_union_max": 0,
                }
                _p4_scan_wall_s = 0.0
                _p4_trf_wall_s = 0.0
                _p4_scan_mse_evals = 0
                _p4_trf_mse_evals = 0
                x0_base = np.concatenate(_x0_p4)
                _cor_base = (
                    p2_result_to_correc_tuple(best_res, _use_sub_c3)
                    if best_res.get("re_dH_knots") is not None
                    else _correc_nom
                )
                _n_ap_scan = max(
                    4, int(worker.cfg.get("re_phase4_aperture_scan_points", RE_PHASE4_APERTURE_SCAN_POINTS))
                )
                _lo_ap, _hi_ap = worker._get_phase4_aperture_bounds()
                _p4_trf_nfev = int(worker.cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))
                _p4_tol = float(worker.cfg.get("re_phase4_trf_tol_factor", RE_PHASE4_TRF_TOL_FACTOR))
                _p4_fd_ap = float(worker.cfg.get("re_p4_ap_fd_step_deg", RE_P4_AP_FD_STEP_DEG))
                _nap = int(RE_P4_BEAM_N_KNOTS)
                _kn_log, _p4_band_thr, _p4_scan_plateaus_s, _p4_hi_ang, _p4_lo_ang, _p4_cfg_knm = (
                    worker._get_phase4_scan_inputs(x0_base, _nap, _ap_gui, wls, oblique_config_meta)
                )
                _p4_ft_eff = float(RE_LBFGSB_FTOL) * _p4_tol
                _p4_gt_eff = float(RE_LBFGSB_GTOL) * _p4_tol
                _p4_band_thr_s = np.array2string(_p4_band_thr, precision=2, separator=",")
                _wmin_obj = float(np.min(wls))
                _wmax_obj = float(np.max(wls))
                logging.info(
                    "RE phase 4 config | wall_t0=same_block | n_wls_obj=%d lambda_nm[min,max]=[%.2f,%.2f] | physics_groups=%d angles_ge_10deg=%s | knots_lam_nm(sorted_display)=%s | cfg_re_p4_beam_ap_knots_nm=%s | band_fastpath_n=%d lambda_thresholds_nm=%s (paliers ap / bande) | ap_bounds_deg=[%.4f,%.4f] | scan_grid=linspace_n=%d | trf_max_nfev=%d | trf_tol_factor=%.4g -> ftol~%.3g xtol~%.3g gtol~%.3g | ap_fd_step_deg=%.5g | joint_nvar=%d (n_layers=%d spline_block=%d sub_cauchy3=%s) | re_beam_aperture_deg_init(cfg)=%.4f",
                    int(wls.size),
                    float(np.min(wls)),
                    float(np.max(wls)),
                    len(oblique_config_meta),
                    _p4_hi_ang,
                    np.array2string(_kn_log, precision=2, separator=","),
                    repr(_p4_cfg_knm),
                    _nap,
                    _p4_band_thr_s,
                    _lo_ap,
                    _hi_ap,
                    _n_ap_scan,
                    _p4_trf_nfev,
                    _p4_tol,
                    _p4_ft_eff,
                    _p4_ft_eff,
                    _p4_gt_eff,
                    _p4_fd_ap,
                    len(x0_base),
                    n_layers_count,
                    int(len(x0_base) - n_layers_count),
                    _use_sub_c3,
                    float(worker.cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG)),
                )
                logging.info("RE phase 4 plateaus (scan grid, lambda intervals): %s", _p4_scan_plateaus_s)
                if _p4_lo_ang:
                    logging.info(
                        "RE phase 4 angle policy | P4 applied only for angles >=10: %s | angles <10 kept without beam aperture averaging: %s",
                        _p4_hi_ang,
                        _p4_lo_ang,
                    )
                logging.info(
                    "RE phase 4 cost model | grep  P4 profile  +  P4 scan profile  +  TRF profile  | one full MSE_ep: physics_groups × P4_block; P4_block (stepped lambda) <= %d bands × (1 or 2) analytical oblique calls on lambda sub-grids | scan: ~(n_scan+1) MSE_ep | TRF: each nfev LS = 1 residual; each jac ap = 1 MSE + %d FD(ap) + 1 restore (see SciPy njev)",
                    _nap,
                    _nap,
                )
                _p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap = (
                    worker._run_phase4_aperture_scan(
                        _emit_re_prog=_emit_re_prog,
                        _nap=_nap,
                        _lo_ap=_lo_ap,
                        _hi_ap=_hi_ap,
                        _n_ap_scan=_n_ap_scan,
                        x0_base=x0_base,
                        _eval_both_p2=_eval_both_p2,
                        _cb2_ref=_cb2_ref,
                        _re_state=_re_state,
                        _report_mse_spectral=_report_mse_spectral,
                        _cor_base=_cor_base,
                        ep_p4=ep_p4,
                        _kn_log=_kn_log,
                        _wmin_obj=_wmin_obj,
                        _wmax_obj=_wmax_obj,
                    )
                )

                def _insert_p4_result(
                    *,
                    ep_f: np.ndarray,
                    dh_v: np.ndarray,
                    dl_v: np.ndarray,
                    lam_v: float,
                    th_v: np.ndarray | None,
                    nfev_extra: int,
                    p4_label_suffix: str,
                    success: bool,
                ) -> None:
                    phase4_result, rmse_comb_p4 = worker._build_phase4_result(
                        ep_f=ep_f,
                        dh_v=dh_v,
                        dl_v=dl_v,
                        lam_v=lam_v,
                        th_v=th_v,
                        nfev_extra=nfev_extra,
                        p4_label_suffix=p4_label_suffix,
                        success=success,
                        best_res_dto=best_res_dto,
                        _use_sub_c3=_use_sub_c3,
                        _report_mse_spectral=_report_mse_spectral,
                        _compute_qwot_rmse=_compute_qwot_rmse,
                        _rmse_combined=_rmse_combined,
                        _re_state=_re_state,
                        wls=wls,
                        _wmin_obj=_wmin_obj,
                        _wmax_obj=_wmax_obj,
                    )
                    _prepend_result_dto(results, phase4_result)
                    rmse_final_milestone[0] = float(rmse_comb_p4)

                _p4_trf_wall_s, _p4_trf_mse_evals, _p4_best_seen_rmse = worker._run_phase4_joint_trf(
                    p4_trf_nfev=_p4_trf_nfev,
                    nap=_nap,
                    x0_base=x0_base,
                    best_ap=best_ap,
                    lo_ap=_lo_ap,
                    hi_ap=_hi_ap,
                    bounds_p2_trf=bounds_p2_trf,
                    p4_fd_ap=_p4_fd_ap,
                    p4_tol=_p4_tol,
                    i0=i0,
                    i_lam=i_lam,
                    i_cu=i_cu,
                    nk=_nk,
                    n_layers_count=n_layers_count,
                    use_sub_c3=_use_sub_c3,
                    kn_log=_kn_log,
                    wmin_obj=_wmin_obj,
                    wmax_obj=_wmax_obj,
                    fun_res_p2=_fun_res_p2,
                    eval_both_p2=_eval_both_p2,
                    cb2_ref=_cb2_ref,
                    re_state=_re_state,
                    p2_trf_log_tag=_p2_trf_log_tag,
                    p2_ki_slot=_p2_ki_slot,
                    insert_p4_result=_insert_p4_result,
                    results=results,
                )
                if not worker._stop:
                    logging.info(
                        "RE phase 4: joint TRF disabled | re_phase4_trf_max_nfev=0  scan-only (raise max_nfev to polish ap knots + thickness+splines jointly)"
                    )
                    rmse_q_scan = _compute_qwot_rmse(ep_p4, _cor_base)
                    rmse_c_scan = _rmse_combined(float(best_rmse_ap), rmse_q_scan)
                    _sk = np.asarray(_re_state["re_aperture_knots"], dtype=np.float64).ravel()[
                        : int(RE_P4_BEAM_N_KNOTS)
                    ]
                    _skn = np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[
                        : int(RE_P4_BEAM_N_KNOTS)
                    ]
                    logging.info(
                        "RE phase 4 scan-only result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | min||r||^2(scan)=%.8g | ap_deg(n knots)=%s | knots_lam_nm=%s",
                        rmse_c_scan,
                        float(best_rmse_ap),
                        rmse_q_scan,
                        float(best_ls_sq),
                        np.array2string(_sk, precision=2, separator=","),
                        np.array2string(_skn, precision=2, separator=","),
                    )
                    logging.info(
                        "RE phase 4 scan-only plateaus (explicit): %s",
                        _re_p4_ap_band_intervals_str(_skn, _sk, _wmin_obj, _wmax_obj),
                    )
                    phase4_scan = REPhase4Result.from_legacy_dict(best_res)
                    phase4_scan = REPhase4Result(
                        label=RE_RESULT_LABEL_WITH_DRIFT + " (P4 aperture scan)",
                        ep=phase4_scan.ep,
                        a=phase4_scan.a,
                        b=phase4_scan.b,
                        f=phase4_scan.f,
                        re_dh_knots=phase4_scan.re_dh_knots,
                        re_dl_knots=phase4_scan.re_dl_knots,
                        re_knots_nm=phase4_scan.re_knots_nm,
                        re_spline_lam_node2_nm=phase4_scan.re_spline_lam_node2_nm,
                        rmse=float(best_rmse_ap),
                        rmse_qwot=float(rmse_q_scan),
                        rmse_combined=float(rmse_c_scan),
                        nfev=phase4_scan.nfev,
                        success=True,
                        nfev_phase1=phase4_scan.nfev_phase1,
                        nfev_phase2_prefit=phase4_scan.nfev_phase2_prefit,
                        re_p4_aperture_deg=float(np.mean(_sk)),
                        re_p4_beam_ap_knots_nm=np.asarray(
                            _re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64
                        ).ravel()[: int(RE_P4_BEAM_N_KNOTS)],
                        re_p4_beam_ap_knots_deg=np.asarray(_sk, dtype=np.float64).flatten(),
                        re_sub_cauchy_a0=phase4_scan.re_sub_cauchy_a0,
                        re_sub_cauchy_a1=phase4_scan.re_sub_cauchy_a1,
                        re_sub_cauchy_a2=phase4_scan.re_sub_cauchy_a2,
                    )
                    _prepend_result_dto(results, phase4_scan)
                    rmse_final_milestone[0] = float(rmse_c_scan)
                _re_state["is_phase4"] = False
                _pp_fin = _re_state.get("p4_prof")
                _wall_p4_tot = float(time.perf_counter() - _t_p4_wall)
                if _pp_fin is not None:
                    logging.info(
                        "RE phase 4 P4 profile (in each MSE_ep, blocks >= 10, lambda-stepped ap) - inner_physics_wall_s=%.4f | oblique_phi_calls=%d | meta_passes=%d | n_wls_union_max=%d | band_groups=%d band_mask_steps=%d | <=%d -calls/group (2×%d lambda knots); vectorizing by band reduces Python overhead",
                        float(_pp_fin.get("phy_wall_s", 0.0)),
                        int(_pp_fin.get("phi_calls", 0)),
                        int(_pp_fin.get("meta_p4_count", 0)),
                        int(_pp_fin.get("n_wls_union_max", 0)),
                        int(_pp_fin.get("band_groups", 0)),
                        int(_pp_fin.get("band_mask_steps", 0)),
                        2 * int(RE_P4_BEAM_N_KNOTS),
                        int(RE_P4_BEAM_N_KNOTS),
                    )
                logging.info(
                    "RE phase 4 wall | total=%.3fs | scan=%.3fs | TRF=%.3fs | overheadmax(0,total-scan-TRF-inner_physics) | grep  RE phase 4  /  P4 profile  to retune cfg & code",
                    _wall_p4_tot,
                    float(_p4_scan_wall_s),
                    float(_p4_trf_wall_s),
                )
                _re_state["p4_prof"] = None
            elif _has_high_angle:
                logging.info(
                    "RE phase 4 skipped | reason=no_spline_state_on_best | need re_dH_knots/re_dL_knots on results[0] (phase 2 splines)"
                )
                _emit_re_prog(99.0, "RE phase 4  skipped (no Delta Re splines on best candidate)")
            else:
                logging.info(
                    "RE phase 4 skipped | reason=all_angles_below_10deg | beam average not applied for low incidence"
                )
                _emit_re_prog(99.0, "RE phase 4  skipped (all angles < 10 deg)")
            _emit_re_prog(99.0, "RE phase 4  done")
