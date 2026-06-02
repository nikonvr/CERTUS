import time
import traceback

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import joblib

from functools import partial
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Protocol, Callable

import numpy as np

from scipy.optimize import least_squares

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

from certus.ui.certus_qt_widgets import QThread

from certus.ui.certus_ui import WorkerSignals

def _dbg_write(msg: str) -> None:
    logger.debug(msg)


def _re_precompute_union_indices(oblique_config_meta: list[dict[str, Any]]) -> None:
    """Populate per-meta union indices used by later RE phases."""
    empty_idx = np.array([], dtype=np.int64)
    for meta in oblique_config_meta:
        buckets = meta.get("buckets", [])
        pos_list = [b["local_positions"] for b in buckets if b.get("local_positions", empty_idx).size > 0]

        if not pos_list:
            meta["pos_all_union"] = empty_idx
            continue

        pos_all = np.unique(np.concatenate(pos_list)).astype(np.int64, copy=False)
        meta["pos_all_union"] = pos_all

        for bucket in buckets:
            pos = bucket.get("local_positions", empty_idx)
            bucket["idx_union"] = empty_idx if pos.size == 0 else np.searchsorted(pos_all, pos).astype(np.int64, copy=False)


def _re_init_context_fields(self, _re_t0: float) -> tuple:
    """Gather RE context inputs needed by _build_re_run_context."""
    re_pct_hi = [0.0]

    def _emit_re_prog(target: float, msg: str) -> None:
        v = max(re_pct_hi[0], float(target))
        re_pct_hi[0] = max(0.0, min(99.0, v))
        self.signals.progress.emit(int(round(re_pct_hi[0])), msg)

    mats = self.cfg["mats"]
    stack = self.cfg["stack"]
    ep0 = np.asarray(self.cfg["ep0"], dtype=np.float64)
    lambda_ref = float(self.cfg.get("lambda_ref", self.cfg["l0"]))
    oblique_tgts = self.cfg.get("oblique_tgts", [])
    wls, _, _ = re_objective_wls_grid(self.cfg, oblique_tgts, float_dtype=np.float64)
    _p4_beam_knots_lam = _re_p4_beam_knots_lam_nm_from_wls(wls, self.cfg)
    n_layers_nominal, n_sub_nominal, is_H, is_L, n_ref_nom_per_layer, lref_arr = re_nominal_indices_at_wls(
        mats, stack, wls, lambda_ref, complex_dtype=np.complex128
    )
    oblique_config_meta = re_oblique_config_meta_from_wls(wls, oblique_tgts)
    _re_precompute_union_indices(oblique_config_meta)
    return (
        1.5,
        27.5,
        oblique_config_meta,
        ep0,
        wls,
        n_layers_nominal,
        n_sub_nominal,
        is_H,
        is_L,
        n_ref_nom_per_layer,
        lambda_ref,
        lref_arr,
        _p4_beam_knots_lam,
        re_pct_hi,
        _emit_re_prog,
    )


def _prepare_re_run_context_setup(self, _re_t0: float) -> tuple[Any, dict[str, Any]]:
    _RE_P_SETUP, _RE_P_P1, oblique_config_meta, ep0, wls, n_layers_nominal, n_sub_nominal, is_H, is_L, n_ref_nom_per_layer, lambda_ref, _lref_arr, _p4_beam_knots_lam, _re_pct_hi, _emit_re_prog = _re_init_context_fields(self, _re_t0)
    mats = self.cfg["mats"]
    stack = self.cfg["stack"]
    radius = float(self.cfg.get("radius", 5.0))
    oblique_tgts = self.cfg.get("oblique_tgts", [])
    wls_min = float(np.min(wls))
    wls_max = float(np.max(wls))
    wt_spectral = re_objective_wls_weight_log_trap(wls)
    re_env_s = float(self.cfg.get("re_envelope_scale", 1.0))
    _re_env_on_wls = re_envelope_max_delta_n(wls, scale=re_env_s)
    _ap_gui = float(np.clip(float(self.cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG)), RE_P4_BEAM_AP_BOUNDS_DEG[0], RE_P4_BEAM_AP_BOUNDS_DEG[1]))
    _re_state = {"is_phase4": False, "re_aperture_knots": np.full(int(RE_P4_BEAM_N_KNOTS), _ap_gui, dtype=np.float64), "re_p4_beam_knots_lam_nm": np.asarray(_p4_beam_knots_lam, dtype=np.float64).copy(), "p4_prof": None}
    n_layers_count = len(ep0)
    var_idx = np.arange(n_layers_count, dtype=np.int64)
    ctx = REMseContext(_alpha_slot=[float(self.cfg.get("re_qwot_penalty_weight", RE_GUI_DEFAULT_RE_QWOT_ALPHA))], _lref_arr=_lref_arr, _re_env_on_wls=_re_env_on_wls, _re_state=_re_state, ep0=ep0, is_H=is_H, is_L=is_L, lambda_ref=lambda_ref, n_layers_count=n_layers_count, n_layers_nominal=n_layers_nominal, n_ref_nom_per_layer=n_ref_nom_per_layer, n_sub_nominal=n_sub_nominal, oblique_config_meta=oblique_config_meta, re_env_s=re_env_s, var_idx=var_idx, wls=wls)
    prep = {"mats": mats, "stack": stack, "ep0": ep0, "radius": radius, "oblique_tgts": oblique_tgts, "lambda_ref": lambda_ref, "n_layers_count": n_layers_count, "n_layers_nominal": n_layers_nominal, "n_sub_nominal": n_sub_nominal, "is_H": is_H, "is_L": is_L, "n_ref_nom_per_layer": n_ref_nom_per_layer, "_lref_arr": _lref_arr, "_p4_beam_knots_lam": _p4_beam_knots_lam, "oblique_config_meta": oblique_config_meta, "wt_spectral": wt_spectral, "re_env_s": re_env_s, "_re_env_on_wls": _re_env_on_wls, "_ap_gui": _ap_gui, "_re_state": _re_state, "wls_min": wls_min, "wls_max": wls_max, "wls": wls, "_RE_P_SETUP": _RE_P_SETUP, "_RE_P_P1": _RE_P_P1, "_re_pct_hi": _re_pct_hi, "_emit_re_prog": _emit_re_prog}
    return ctx, prep


def _build_re_mse_grad_helper(self, ctx):
    def _mse_grad_accumulate_ep(ep_arr: np.ndarray, wt: np.ndarray, want_grad: bool, correc: tuple, return_residuals: bool = False) -> tuple:
        return _global_compute_re_mse_gradient(self.cfg, ctx, ep_arr, wt, want_grad, correc, return_residuals=return_residuals)
    return _mse_grad_accumulate_ep


def _build_qwot_helpers(self, ep0, n_ref_nom_per_layer, is_H, is_L, lambda_ref, re_env_s, _lref_arr, _alpha_slot):
    _dz_qw_cfg = float(self.cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))
    def _get_delta_qwot(ep: np.ndarray, correc: tuple) -> np.ndarray:
        _qc = correc if (correc and len(correc) > 0 and correc[0] in RE_SPLINE_CORREC_KINDS) else None
        return re_delta_qwot_per_layer(np.asarray(ep, dtype=np.float64), ep0, n_ref_nom_per_layer, is_H, is_L, float(lambda_ref), float(re_env_s), _lref_arr, correc=_qc)
    def _compute_qwot_rmse(ep: np.ndarray, correc: tuple) -> float:
        _dq = _get_delta_qwot(ep, correc)
        if _dq.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(_re_deadzone_excess_abs(_dq, _dz_qw_cfg) ** 2)))
    def _compute_qwot_rmse_raw(ep: np.ndarray, correc: tuple) -> float:
        _dq = _get_delta_qwot(ep, correc)
        if _dq.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(_dq**2)))
    def _rmse_combined(rmse_sp: float, rmse_qwot: float) -> float:
        return _re_rmse_combined_spectral_qwot(float(rmse_sp), float(rmse_qwot), float(_alpha_slot[0]))
    return {"_get_delta_qwot": _get_delta_qwot, "_compute_qwot_rmse": _compute_qwot_rmse, "_compute_qwot_rmse_raw": _compute_qwot_rmse_raw, "_rmse_combined": _rmse_combined}


def _prepare_phase2_fd_settings(self, re_env_s: float):
    _p2fd_spl = float(self.cfg.get("re_phase2_spline_fd_step", RE_PHASE2_SPLINE_FD_STEP))
    _p2fd_lam = float(self.cfg.get("re_phase2_lam2_fd_step", RE_PHASE2_LAM2_FD_STEP))
    _fd_1s = bool(self.cfg.get("re_phase2_onesided_spline_fd", RE_PHASE2_ONESIDED_SPLINE_FD))
    _fd_par = bool(self.cfg.get("re_phase2_fd_parallel", RE_PHASE2_FD_PARALLEL))
    _mw_cfg = int(self.cfg.get("re_phase2_fd_max_workers", RE_PHASE2_FD_MAX_WORKERS))
    from certus.core.certus_core import _get_cpu_count
    _cpu = _get_cpu_count()
    _fd_cap = _mw_cfg if _mw_cfg > 0 else min(_cpu, 2 * int(RE_SPLINE_N_KNOTS) + 1)
    _nk = int(RE_SPLINE_N_KNOTS)
    _fd_nw = max(1, min(_fd_cap, 2 * _nk + 1)) if _fd_par else 1
    _knot0 = re_knots_wavelengths(RE_SPLINE_NODE2_DEFAULT_NM)
    _env_knot = re_envelope_max_delta_n(_knot0, scale=re_env_s)
    return {
        "_p2fd_spl": _p2fd_spl,
        "_p2fd_lam": _p2fd_lam,
        "_fd_1s": _fd_1s,
        "_fd_par": _fd_par,
        "_fd_nw": _fd_nw,
        "_nk": _nk,
        "_knot0": _knot0,
        "_env_knot": _env_knot,
    }


def _prepare_phase2_bounds_and_topk(self, *, results, bind_p2_plan, emit_re_prog, re_p2_plan, nk, wls, re_use_staged_order, env_knot, bounds):
    results.sort(key=lambda r: r.get("rmse_combined", r["rmse"]))
    re_p2_plan[0] = bind_p2_plan(len(results))
    pl = re_p2_plan[0]
    prep_msg = (
        f"RE step 3/3: full joint optimization preparing (K={nk} spline knots, nlambda={len(wls)})..."
        if re_use_staged_order
        else f"RE phase 2: preparing optimization (K={nk} spline knots, nlambda={len(wls)})..."
    )
    emit_re_prog(float(pl["prep_mid"]), prep_msg)
    top_k = min(int(RE_GUI_DEFAULT_RE_PHASE2_TOP_K), len(results))
    if re_use_staged_order and top_k > 1:
        top_k = 1
        logging.info("event=re_phase2 top_k=1 reason=staged_order best_only=true")
    merge_rtol = float(self.cfg.get("re_phase2_top_k_merge_rel_tol", RE_PHASE2_TOP_K_MERGE_REL_TOL))
    if top_k > 1 and len(results) >= 2 and merge_rtol >= 0.0:
        c0_dto = _result_dto_at(results, 0)
        c1_dto = _result_dto_at(results, 1)
        c0 = float(c0_dto.rmse_combined) if c0_dto is not None else float("inf")
        c1 = float(c1_dto.rmse_combined) if c1_dto is not None else float("inf")
        if abs(c0 - c1) <= merge_rtol * max(abs(c0), 1e-12):
            top_k = 1
            logging.info("event=re_phase2 top_k=1 reason=near_identical_candidates rel_tol=%.2g", merge_rtol)
    if re_use_staged_order:
        logging.info("event=re_phase2 start_stage=3/3 top_k=%d focus=joint_optimization", int(top_k))
    act_h = bool(self.cfg.get("re_refine_h", False))
    act_l = bool(self.cfg.get("re_refine_l", False))
    b_lam = RE_SPLINE_NODE2_BOUNDS_NM if (act_h or act_l) else (RE_SPLINE_NODE2_DEFAULT_NM - 1e-10, RE_SPLINE_NODE2_DEFAULT_NM + 1e-10)
    env_knot = np.asarray(env_knot, dtype=np.float64)
    bounds_spline = list(zip((-env_knot).tolist(), env_knot.tolist()))
    b_spline_H = bounds_spline if act_h else [(-1e-15, 1e-15)] * nk
    b_spline_L = bounds_spline if act_l else [(-1e-15, 1e-15)] * nk
    bounds_p2 = list(bounds) + b_spline_H + b_spline_L + [b_lam]
    return {"_top_k": top_k, "bounds_p2": bounds_p2, "b_lam": b_lam, "bounds_spline": bounds_spline, "_act_h": act_h, "_act_l": act_l, "_merge_rtol": merge_rtol}


def _build_p2_prefit_bounds(bounds_spref):
    lb = np.array([float(b[0]) for b in bounds_spref], dtype=np.float64)
    ub = np.array([float(b[1]) for b in bounds_spref], dtype=np.float64)
    return lb, ub


def _build_phase4_aperture_bounds(bounds_p2_trf: tuple, nap: int, lo_ap: float, hi_ap: float) -> tuple[np.ndarray, np.ndarray]:
    """Append independent aperture bounds to the base phase-2 bounds."""

    return (
        np.concatenate([bounds_p2_trf[0], np.full(nap, float(lo_ap), dtype=np.float64)]),
        np.concatenate([bounds_p2_trf[1], np.full(nap, float(hi_ap), dtype=np.float64)]),
    )


def _phase4_aperture_slice(x: np.ndarray, i_ap0: int, nap: int) -> np.ndarray:
    """Return the phase-4 aperture knot slice as a contiguous float64 vector."""

    return np.asarray(x[i_ap0 : i_ap0 + nap], dtype=np.float64).ravel()


def _build_phase2_result(
    *,
    res_p2: Any,
    ep_end: np.ndarray,
    dh_end: np.ndarray,
    dl_end: np.ndarray,
    knots_end: np.ndarray,
    lam_end: float,
    rmse_p2: float,
    rmse_qwot_p2: float,
    rmse_comb_p2: float,
    nfev_p1: int,
    nfev_phase2_prefit: int,
    th_end: np.ndarray | None,
) -> REPhase2Result:
    """Build the immutable phase-2 result payload."""

    return REPhase2Result(
        label=RE_RESULT_LABEL_WITH_DRIFT,
        ep=np.asarray(ep_end, dtype=np.float64).flatten(),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.asarray(dh_end, dtype=np.float64).flatten(),
        re_dl_knots=np.asarray(dl_end, dtype=np.float64).flatten(),
        re_knots_nm=np.asarray(knots_end, dtype=np.float64).flatten(),
        re_spline_lam_node2_nm=float(lam_end),
        rmse=float(rmse_p2),
        rmse_qwot=float(rmse_qwot_p2),
        rmse_combined=float(rmse_comb_p2),
        nfev=int(res_p2.nfev),
        success=bool(res_p2.success),
        nfev_phase1=int(nfev_p1),
        nfev_phase2_prefit=int(nfev_phase2_prefit),
        re_sub_cauchy_a0=float(th_end[0]) if th_end is not None else None,
        re_sub_cauchy_a1=float(th_end[1]) if th_end is not None else None,
        re_sub_cauchy_a2=float(th_end[2]) if th_end is not None else None,
    )


def _build_phase2b_output(
    *,
    res_p2: Any,
    x0_p2: np.ndarray,
    cb2_ref: list,
    n_layers_count: int,
    nk: int,
    i0: int,
    i_lam: int,
    i_cu: int,
    use_sub_c3: bool,
    report_mse_spectral,
    compute_qwot_rmse,
    rmse_combined,
    alpha_slot: list,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray | None, float, float, float]:
    """Convert phase-2b optimizer output into scientific arrays and RMSE values."""

    x_end = np.asarray(res_p2.x, dtype=np.float64).ravel()
    ep_end = np.asarray(x_end[:n_layers_count], dtype=np.float64).flatten()
    dh_end = np.asarray(x_end[i0 : i0 + nk], dtype=np.float64).flatten()
    dl_end = np.asarray(x_end[i0 + nk : i_lam], dtype=np.float64).flatten()
    lam_end = float(x_end[i_lam])
    if use_sub_c3:
        th_end = np.asarray(x_end[i_cu : i_cu + 3], dtype=np.float64).ravel()
        cor_end = (
            "spline_sub3",
            dh_end,
            dl_end,
            lam_end,
            float(th_end[0]),
            float(th_end[1]),
            float(th_end[2]),
        )
    else:
        th_end = None
        cor_end = ("spline", dh_end, dl_end, lam_end)
    rmse_p2 = float(np.sqrt(max(report_mse_spectral(ep_end, cor_end), 0.0)))
    rmse_qwot_p2 = compute_qwot_rmse(ep_end, cor_end)
    rmse_comb_p2 = rmse_combined(rmse_p2, rmse_qwot_p2)
    return ep_end, dh_end, dl_end, lam_end, th_end, rmse_p2, rmse_qwot_p2, rmse_comb_p2


def _build_phase2b_output(
    *,
    res_p2: Any,
    x0_p2: np.ndarray,
    cb2_ref: list,
    n_layers_count: int,
    nk: int,
    i0: int,
    i_lam: int,
    i_cu: int,
    use_sub_c3: bool,
    report_mse_spectral: Any,
    compute_qwot_rmse: Any,
    rmse_combined: Any,
    alpha_slot: list,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray | None, float, float, float]:
    """Build phase-2b vectors and metrics from an optimization result."""

    x_end = res_p2.x
    ep_end = np.asarray(x_end[:n_layers_count], dtype=np.float64).flatten()
    dh_end = np.asarray(x_end[i0 : i0 + nk], dtype=np.float64).flatten()
    dl_end = np.asarray(x_end[i0 + nk : i_lam], dtype=np.float64).flatten()
    lam_end = float(x_end[i_lam])
    knots_end = re_knots_wavelengths(lam_end)

    if use_sub_c3:
        th_end = np.asarray(x_end[i_cu : i_cu + 3], dtype=np.float64).ravel()
        cor_end = (
            "spline_sub3",
            dh_end,
            dl_end,
            lam_end,
            float(th_end[0]),
            float(th_end[1]),
            float(th_end[2]),
        )
    else:
        th_end = None
        cor_end = ("spline", dh_end, dl_end, lam_end)

    rmse_p2 = float(np.sqrt(max(report_mse_spectral(ep_end, cor_end), 0.0)))
    rmse_qwot_p2 = compute_qwot_rmse(ep_end, cor_end)
    rmse_comb_p2 = rmse_combined(rmse_p2, rmse_qwot_p2)

    return ep_end, dh_end, dl_end, lam_end, th_end, rmse_p2, rmse_qwot_p2, rmse_comb_p2


def _log_phase4_trf_summary(
    *,
    res_p4: Any,
    _cost_0: float | None,
    _cost_f: float,
    _opt: float,
    _njev: int,
    _ap_i: np.ndarray,
    _ap_f: np.ndarray,
    kn_log: np.ndarray,
    wmin_obj: float,
    wmax_obj: float,
    p4_trf_wall_s: float,
    p4_trf_mse_evals: int,
    nap: int,
) -> None:
    """Emit the standard phase-4 TRF diagnostic logs."""

    logging.info(
        "RE phase 4 TRF summary | success=%s | nfev=%d njev=%d | "
        "cost_final=%.8g optimality=%.4g | cost_init_scan_ap=%s | "
        "ap_init_deg=%s ap_final_deg=%s | msg=%s | "
        "tune: re_phase4_trf_max_nfev re_phase4_trf_tol_factor re_p4_ap_fd_step_deg",
        res_p4.success,
        int(res_p4.nfev),
        _njev,
        _cost_f,
        _opt,
        (f"{_cost_0:.8g}" if _cost_0 is not None else "n/a"),
        np.array2string(_ap_i, precision=2, separator=","),
        np.array2string(_ap_f, precision=2, separator=","),
        str(getattr(res_p4, "message", "")).replace("\n", " "),
    )

    logging.info(
        "RE phase 4 TRF plateaus | init=%s | final=%s",
        _re_p4_ap_band_intervals_str(kn_log, _ap_i, wmin_obj, wmax_obj),
        _re_p4_ap_band_intervals_str(kn_log, _ap_f, wmin_obj, wmax_obj),
    )

    logging.info(
        "RE phase 4 TRF profile | wall_s=%.4f | MSE_ep_count_since_TRF_reset=%d | "
        "ls_nfev=%d | jac: ~njev×(1+%d) MSE_ep (1 residu + %d FD ap_knots + restore) | "
        "s_per_ls_nfev%.5f | opt: re_phase4_trf_max_nfev tol_factor ou jac ap analytique",
        p4_trf_wall_s,
        p4_trf_mse_evals,
        int(res_p4.nfev),
        nap,
        nap,
        p4_trf_wall_s / max(int(res_p4.nfev), 1),
    )

from certus.utils.certus_re_helpers import (
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    RE_GUI_DEFAULT_RE_PHASE1_RESTARTS,
    RE_GUI_DEFAULT_RE_PHASE2_TOP_K,
    RE_GUI_DEFAULT_RE_PHASE3_SHAKES,
    RE_GUI_DEFAULT_RE_QWOT_ALPHA,
    RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV,
    RE_HL_DELTA_RE_REG_SQRT_W,
    RE_LBFGSB_FTOL,
    RE_LBFGSB_GTOL,
    RE_P4_AP_FD_STEP_DEG,
    RE_P4_BEAM_AP_BOUNDS_DEG,
    RE_P4_BEAM_N_KNOTS,
    RE_PHASE2A_PREFIT_TOL_FACTOR,
    RE_PHASE2B_MAXITER,
    RE_PHASE2_FD_MAX_WORKERS,
    RE_PHASE2_FD_PARALLEL,
    RE_PHASE2_LAM2_FD_STEP,
    RE_PHASE2_ONESIDED_SPLINE_FD,
    RE_PHASE2_SPLINE_FD_STEP,
    RE_PHASE2_SPLINE_PREFIT_MAXITER,
    RE_PHASE2_SUB_CAUCHY_FD_STEP,
    RE_PHASE2_TOP_K_MERGE_REL_TOL,
    RE_PHASE4_APERTURE_SCAN_POINTS,
    RE_PHASE4_TRF_MAX_NFEV,
    RE_PHASE4_TRF_TOL_FACTOR,
    RE_RANKING_ALPHA_REF,
    RE_RE_DEADZONE_DELTA_RE_ABS,
    RE_RE_DEADZONE_QWOT_ABS,
    RE_RESULT_LABEL_WITH_DRIFT,
    RE_SPLINE_CORREC_KINDS,
    RE_SPLINE_NODE2_BOUNDS_NM,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    RE_SUB_CAUCHY_BARRIER_SQRT_W,
    RE_SUB_CAUCHY_TUBE_DELTA,
    format_re_spline_knots_log,
    re_compute_spline_basis_matrix,
    re_compute_tikhonov_weights,
    re_delta_qwot_per_layer,
    re_envelope_max_delta_n,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    re_substrate_cauchy_barrier_residuals_jac,
    re_substrate_cauchy_initial_theta,
    re_substrate_cauchy_phi_matrix,
    # Private symbols (underscore-prefixed, not exported by import *)
    _re_apply_correc,
    _re_calc_spectrum_for_config,
    _re_correc_to_nk_preview_payload,
    _re_deadzone_excess_abs,
    _re_log_objective_diagnostic,
    _re_p4_ap_band_intervals_str,
    _re_p4_band_ap_deg,
    _re_p4_beam_knots_lam_nm_from_wls,
    _re_p4_chromatic_band_masks,
    _re_p4_effective_half_width_deg,
    _re_rmse_combined_spectral_qwot,
    _re_sort_results_best_for_table_and_apply,
    # Worker DTOs and Physics Helpers
    REMseContext,
    REPhase2Context,
    REWorkerRequest,
    REPhase1Result,
    REPhase2Result,
    REPhase3Result,
    REPhase4Result,
    _re_phase23_result_to_legacy_dict,
    _result_dto_at,
    _top_result_dto,
    _set_top_result_dto,
    _prepend_result_dto,
    _replace_all_with_top_dto,
    _re_trf_residual_rms,
    _re_backside_bundle_fixed,
    _re_eval_angle_physics_for,
)

from certus.workers.certus_re_worker_utils import (
    RE_CORREC_NOMINAL_PCT,
    p2_result_to_correc_tuple,
    re_build_p2_progress_plan,
    re_enrich_results_ranking_fields,
    re_finalize_finished_main_log_line,
    re_finalize_progress_message_done,
    re_finalize_ranking_log_suffix,
    re_finalize_rmse_milestone_log_line,
    re_live_plot_wls_and_dispersion_nk,
    re_nominal_indices_at_wls,
    re_objective_wls_grid,
    re_objective_wls_weight_log_trap,
    re_oblique_config_meta_from_wls,
    re_phase1_trf_runs_multistart,
    re_progress_pct_p1,
    re_progress_pct_p2a,
    re_progress_pct_p2b,
    re_progress_pct_p3,
    re_trf_bounds_scipy_tuples,
    re_trf_thickness_bounds,
    resolve_re_qwot_alphas,
    shake_sigmas_adaptive,
)

from certus.utils.certus_re_results_builder import REResultsBuilder as REResultsPayloadBuilder

class REUserStopRequested(Exception):
    """Stop button requests cooperative exit (best TRF state already cached)."""

def _global_compute_re_mse_gradient(cfg, ctx, 
    ep_local,
    spectral_weights_wls,
    want_grad: bool,
    correc: tuple,
    return_residuals: bool = False,
) -> tuple | None:

    n_lay_m, n_sub_m = _re_apply_correc(
        ctx.n_layers_nominal,
        ctx.n_sub_nominal,
        is_H=ctx.is_H,
        is_L=ctx.is_L,
        wls=ctx.wls,
        lambda_ref=ctx.lambda_ref,
        correc=correc,
        re_env_s=ctx.re_env_s,
        env_cache=ctx._re_env_on_wls,
    )

    n_lay_full = np.ascontiguousarray(n_lay_m.T)

    n_sub_full = np.ascontiguousarray(n_sub_m)

    ep_use = np.asarray(ep_local, dtype=np.float64)

    total_err = 0.0

    total_w = 0.0

    grad_raw = np.zeros(ctx.n_layers_count, dtype=np.float64)

    res_list = []

    jac_list = []

    # ``stats`` groups weights/user targets per bucket.
    # ``spectral_weights_local`` applies the Deltaln(lambda) quadrature on the points of the bucket.
    def _accum_from_stats(y_vals, dy_vals, stats, spectral_weights_local) -> None:
        nonlocal total_err, total_w, grad_raw
        ws = float(stats["w_sum"])
        if ws <= 0.0:
            return

        wt_sum = float(np.sum(spectral_weights_local))
        wy = spectral_weights_local * y_vals
        wy2_sum = float(np.dot(wy, y_vals))
        wy_sum = float(np.sum(wy))
        w_tgt_sum = float(stats["w_tgt_sum"])
        w_tgt2_sum = float(stats["w_tgt2_sum"])

        total_err += (ws * wy2_sum) - (2.0 * w_tgt_sum * wy_sum) + (w_tgt2_sum * wt_sum)
        total_w += ws * wt_sum

        if want_grad:
            coeff = spectral_weights_local * (ws * y_vals - w_tgt_sum)
            grad_raw += np.dot(coeff, dy_vals)

        if return_residuals:
            mean_t = w_tgt_sum / ws
            scale_f = np.sqrt(ws * spectral_weights_local)
            res_list.append(scale_f * (y_vals - mean_t))
            if want_grad:
                jac_list.append(dy_vals * scale_f[:, np.newaxis])

    _global_evaluate_oblique_physics(
        ctx,
        ep_use,
        n_lay_full,
        n_sub_full,
        spectral_weights_wls,
        want_grad,
        return_residuals,
        _accum_from_stats,
    )

    if return_residuals:
        _global_add_regularization_residuals(
            ctx,
            ep_local,
            correc,
            want_grad,
            res_list,
            jac_list,
        )

    denom = max(total_w, 1e-12)
    mse = total_err / denom
    grad = (2.0 / denom) * grad_raw if want_grad else np.zeros(ctx.n_layers_count)

    if return_residuals:
        f2 = np.sqrt(2.0 / denom)
        r_out = np.concatenate(res_list) * f2 if res_list else np.array([], dtype=np.float64)
        j_out = np.vstack(jac_list) * f2 if jac_list else np.empty((0, ctx.n_layers_count), dtype=np.float64)
        return mse, grad, r_out, j_out

    return mse, grad





def _global_evaluate_oblique_physics(cfg,
    ctx,
    ep_use: np.ndarray,
    n_lay_full: np.ndarray,
    n_sub_full: np.ndarray,
    spectral_weights_wls: np.ndarray,
    want_grad: bool,
    return_residuals: bool,
    _accum_from_stats,
) -> None:
    for meta in ctx.oblique_config_meta:
        angle = float(meta["angle"])
        pol = str(meta["pol"])
        inc_back = bool(meta["include_backside"])
        pl = pol.lower()

        pos_all = meta.get("pos_all_union", np.array([], dtype=np.int64))
        if pos_all.size == 0:
            continue

        wls_all = ctx.wls[pos_all]
        n_layers_all = n_lay_full[pos_all, :]
        n_sub_all = n_sub_full[pos_all]

        if ctx._re_state["is_phase4"] and angle >= 10.0:
            _p4_prof = ctx._re_state.get("p4_prof")
            _t_p4_phy = time.perf_counter() if _p4_prof is not None else None
            knots_lam = np.asarray(ctx._re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[
                : int(RE_P4_BEAM_N_KNOTS)
            ]
            knots_ap = np.asarray(ctx._re_state["re_aperture_knots"], dtype=np.float64).ravel()[
                : int(RE_P4_BEAM_N_KNOTS)
            ]
            nloc = int(wls_all.size)

            if _p4_prof is not None:
                _p4_prof["meta_p4_count"] = int(_p4_prof.get("meta_p4_count", 0)) + 1
                _p4_prof["n_wls_union_max"] = max(int(_p4_prof.get("n_wls_union_max", 0)), nloc)
                _p4_prof["band_groups"] = int(_p4_prof.get("band_groups", 0)) + 1

            masks = _re_p4_chromatic_band_masks(wls_all, knots_lam)
            yR_all = np.zeros(nloc, dtype=np.float64)
            yT_all = np.zeros(nloc, dtype=np.float64)
            dR_all = None
            dT_all = None

            for m in masks:
                if not np.any(m):
                    continue

                if _p4_prof is not None:
                    _p4_prof["band_mask_steps"] = int(_p4_prof.get("band_mask_steps", 0)) + 1

                sub = np.nonzero(m)[0]
                lam_c = float(np.mean(wls_all[m]))
                ap_b = _re_p4_band_ap_deg(knots_lam, knots_ap, lam_c)
                h = _re_p4_effective_half_width_deg(angle, ap_b)

                if h <= 0.0:
                    if _p4_prof is not None:
                        _p4_prof["phi_calls"] = int(_p4_prof.get("phi_calls", 0)) + 1

                    yR0, dR0, yT0, dT0 = _re_eval_angle_physics_for(
                        sub, angle, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, ctx.var_idx
                    )
                    if dR_all is None:
                        nv = int(dR0.shape[1])
                        dR_all = np.zeros((nloc, nv), dtype=np.float64)
                        dT_all = np.zeros((nloc, nv), dtype=np.float64)

                    yR_all[sub] = yR0
                    yT_all[sub] = yT0
                    dR_all[sub, :] = dR0
                    dT_all[sub, :] = dT0
                else:
                    if _p4_prof is not None:
                        _p4_prof["phi_calls"] = int(_p4_prof.get("phi_calls", 0)) + 2

                    yR1, dR1, yT1, dT1 = _re_eval_angle_physics_for(
                        sub, angle - h, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, ctx.var_idx
                    )
                    yR2, dR2, yT2, dT2 = _re_eval_angle_physics_for(
                        sub, angle + h, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, ctx.var_idx
                    )
                    if dR_all is None:
                        nv = int(dR1.shape[1])
                        dR_all = np.zeros((nloc, nv), dtype=np.float64)
                        dT_all = np.zeros((nloc, nv), dtype=np.float64)

                    yR_all[sub] = 0.5 * (yR1 + yR2)
                    yT_all[sub] = 0.5 * (yT1 + yT2)
                    dR_all[sub, :] = 0.5 * (dR1 + dR2)
                    dT_all[sub, :] = 0.5 * (dT1 + dT2)

            if _p4_prof is not None and _t_p4_phy is not None:
                _p4_prof["phy_wall_s"] = float(_p4_prof.get("phy_wall_s", 0.0)) + (
                    time.perf_counter() - _t_p4_phy
                )
        else:
            yR_all, dR_all, yT_all, dT_all = _re_eval_angle_physics_for(
                None, angle, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, ctx.var_idx
            )

        # Distribute cached kernel evaluations into target buckets
        for bucket in meta["buckets"]:
            pos = bucket["local_positions"]
            if pos.size == 0:
                continue
            idx = bucket.get("idx_union", np.array([], dtype=np.int64))
            if idx.size == 0:
                continue
            spectral_weights_local = spectral_weights_wls[pos]
            _accum_from_stats(yR_all[idx], dR_all[idx, :], bucket["R"], spectral_weights_local)
            _accum_from_stats(yT_all[idx], dT_all[idx, :], bucket["T"], spectral_weights_local)




def _global_add_regularization_residuals(cfg,
    ctx,
    ep_local,
    correc: tuple,
    want_grad: bool,
    res_list: list,
    jac_list: list,
) -> None:
    if (
        correc
        and correc[0]
        in (
            "spline",
            "spline_cached",
            "spline_sub3",
            "spline_cached_sub3",
        )
        and len(correc) >= 3
    ):
        dh = np.asarray(correc[1], dtype=np.float64)
        if dh.size >= 3:
            # Smoothness factor: Default is 5.0.
            # It acts on the discrete 2nd derivative of Delta_n knots
            alpha = float(cfg.get("re_spline_smooth_factor_n", 5.0)) * float(
                cfg.get(
                    "re_spline_tikhonov_scale",
                    RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV,
                )
            )
            tk_w = None
            if correc[0] == "spline_cached_sub3" and len(correc) >= 7:
                tk_w = np.asarray(correc[6], dtype=np.float64)
            elif correc[0] == "spline_cached" and len(correc) >= 7:
                tk_w = np.asarray(correc[6], dtype=np.float64)
            elif correc[0] == "spline_sub3" and len(correc) >= 8 and isinstance(correc[4], np.ndarray):
                tk_w = np.asarray(correc[4], dtype=np.float64)
            elif correc[0] == "spline" and len(correc) >= 5:
                tk_w = np.asarray(correc[4], dtype=np.float64)

            if alpha > 0.0:
                diff2_h = dh[:-2] - 2.0 * dh[1:-1] + dh[2:]
                res_list.append(diff2_h * alpha * tk_w if tk_w is not None else diff2_h * alpha)
                if want_grad:
                    jac_list.append(np.zeros((len(diff2_h), ctx.n_layers_count), dtype=np.float64))

                dl = np.asarray(correc[2], dtype=np.float64)
                diff2_l = dl[:-2] - 2.0 * dl[1:-1] + dl[2:]
                res_list.append(diff2_l * alpha * tk_w if tk_w is not None else diff2_l * alpha)
                if want_grad:
                    jac_list.append(np.zeros((len(diff2_l), ctx.n_layers_count), dtype=np.float64))

    # H/L penalty on DeltaRe at knots (H/L only): |DeltaRe|<= -> 0; else √(w)(max(0,|DeltaRe|)/env)2.
    _w_hl = float(cfg.get("re_hl_delta_re_reg_sqrt_w", RE_HL_DELTA_RE_REG_SQRT_W))
    if _w_hl > 0.0 and correc and correc[0] in RE_SPLINE_CORREC_KINDS:
        _dH_k = np.asarray(correc[1], dtype=np.float64).ravel()
        _dL_k = np.asarray(correc[2], dtype=np.float64).ravel()
        _lam2_c = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)
        _kn = re_knots_wavelengths(_lam2_c)
        _env_k = np.maximum(
            re_envelope_max_delta_n(_kn, scale=ctx.re_env_s),
            1e-18,
        )
        if _dH_k.size == _env_k.size and _dL_k.size == _env_k.size:
            _dz_hl = float(
                cfg.get(
                    "re_hl_delta_re_deadzone_abs",
                    RE_RE_DEADZONE_DELTA_RE_ABS,
                )
            )
            _sqw = np.sqrt(_w_hl)
            _exh = _re_deadzone_excess_abs(_dH_k, _dz_hl)
            _exl = _re_deadzone_excess_abs(_dL_k, _dz_hl)
            _rh = _sqw * ((_exh / _env_k) ** 2)
            _rl = _sqw * ((_exl / _env_k) ** 2)
            res_list.append(_rh)
            res_list.append(_rl)
            if want_grad:
                jac_list.append(np.zeros((len(_rh), ctx.n_layers_count), dtype=np.float64))
                jac_list.append(np.zeros((len(_rl), ctx.n_layers_count), dtype=np.float64))

    # QWOT: dead band |Q|<= -> r_i=0; beyond that r_i = √(max(0,|Q|))².
    # Q = 4n_correp/lambda_ref  ->  Q = (4/lambda_ref)(n_correp - n₀ep₀).
    # Current slot updated per phase (see resolve_re_qwot_alphas).
    _alpha_qwot = float(ctx._alpha_slot[0])
    if _alpha_qwot > 0.0:
        _ep_arr = np.asarray(ep_local, dtype=np.float64)
        _qw_c = correc if (correc and len(correc) > 0 and correc[0] in RE_SPLINE_CORREC_KINDS) else None
        _delta_q = re_delta_qwot_per_layer(
            _ep_arr,
            ctx.ep0,
            ctx.n_ref_nom_per_layer,
            ctx.is_H,
            ctx.is_L,
            float(ctx.lambda_ref),
            float(ctx.re_env_s),
            ctx._lref_arr,
            correc=_qw_c,
        )
        _n_ref_corr = re_n_corr_at_lambda_ref(
            ctx.n_ref_nom_per_layer,
            ctx.is_H,
            ctx.is_L,
            ctx._lref_arr,
            float(ctx.re_env_s),
            correc=_qw_c,
        )
        _kq_wl0 = 4.0 / max(float(ctx.lambda_ref), 1e-9)
        _dz_qw = float(cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))
        _ex_q = _re_deadzone_excess_abs(_delta_q, _dz_qw)
        _r_qwot = np.sqrt(_alpha_qwot) * (_ex_q**2)
        res_list.append(_r_qwot)
        if want_grad:
            # r_i = √ex_i2, ex=max(0,|Q|)  ->  r_i/Q_i = 2√ex_isgn(Q_i)
            _dr_dq = np.where(
                _ex_q > 0.0,
                2.0 * np.sqrt(_alpha_qwot) * _ex_q * np.sign(_delta_q),
                0.0,
            )
            _J_qwot = np.diag(_dr_dq * (_kq_wl0 * _n_ref_corr))
            jac_list.append(_J_qwot)



def _global_build_cached_spline_correc(cfg,
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
                "spline_cached_sub3",
                dh,
                dl,
                float(lam),
                b_mat_c,
                env_c,
                tk_w_c,
                float(th[0]),
                float(th[1]),
                float(th[2]),
            )
        else:
            return (
                "spline_sub3",
                dh,
                dl,
                float(lam),
                tk_w_c,
                float(th[0]),
                float(th[1]),
                float(th[2]),
            )
    else:
        if cached:
            return (
                "spline_cached",
                dh,
                dl,
                float(lam),
                b_mat_c,
                env_c,
                tk_w_c,
            )
        else:
            return (
                "spline",
                dh,
                dl,
                float(lam),
                tk_w_c,
            )



def _global_evaluate_p2_fd_derivative(cfg,
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
            "spline_cached_sub3",
            _dh,
            _dl,
            float(_lam),
            b_mat_c,
            env_c,
            tk_w_c,
            float(_th[0]),
            float(_th[1]),
            float(_th[2]),
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
                "spline_sub3",
                dh4,
                dl4,
                lam_p,
                tk_w_c,
                float(th4[0]),
                float(th4[1]),
                float(th4[2]),
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
        cor_p = _global_build_cached_spline_correc(
            ctx,
            dh_p,
            dl_p,
            float(xv64[ctx.i_lam]),
            tk_w_c,
            cached=True,
            b_mat_c=b_mat_c,
            env_c=env_c,
        )
        h = ctx._p2fd_spl
    else:
        lam_p = float(xv64[ctx.i_lam]) + ctx._p2fd_lam
        cor_p = ("spline", dh4, dl4, lam_p, tk_w_c)
        h = ctx._p2fd_lam

    r_p = ctx._mse_grad_accumulate_ep(ep_x, ctx.wt_spectral, False, cor_p, return_residuals=True)[2]

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
            cor_m = _global_build_cached_spline_correc(
                ctx,
                dh_m,
                dl_m,
                float(xv64[ctx.i_lam]),
                tk_w_c,
                th4=th4,
                cached=True,
                b_mat_c=b_mat_c,
                env_c=env_c,
            )
        elif j == 2 * ctx._nk:
            lam_m = float(xv64[ctx.i_lam]) - ctx._p2fd_lam
            cor_m = _global_build_cached_spline_correc(
                ctx,
                dh4,
                dl4,
                lam_m,
                tk_w_c,
                th4=th4,
                cached=False,
                b_mat_c=b_mat_c,
                env_c=env_c,
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
        cor_m = ("spline_cached", dh_m, dl_m, float(xv64[ctx.i_lam]), b_mat_c, env_c, tk_w_c)
    else:
        lam_m = float(xv64[ctx.i_lam]) - ctx._p2fd_lam
        cor_m = ("spline", dh4, dl4, lam_m, tk_w_c)

    r_m = ctx._mse_grad_accumulate_ep(ep_x, ctx.wt_spectral, False, cor_m, return_residuals=True)[2]

    return j, (r_p - r_m) / (2.0 * h)



class REWorker(QThread):
    """Two-stage RE: (1) TRF Deltaln(lambda) trapezoidal, thicknesses only, tabulated n;

    (2a) TRF DeltaRe splines only (thicknesses = end of phase 1);

    (2b) joint TRF thicknesses + splines + lambda₂ + optional Cauchy substrate (a0,a1,a2), tube |n-n_tab|<=Delta.

    Same index model as `re_apply_re_index_model` / `_compute_re_rmse`.

    """

    def __init__(self, cfg: dict[str, Any] | REWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, REWorkerRequest) else REWorkerRequest.from_legacy(cfg)

        # Keep legacy attribute for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

        self._stop = False

    def request_stop(self) -> None:
        """Cooperative stop (Stop button  not only QThread.requestInterruption)."""

        self._stop = True

    def _execute_phase1(self) -> list[dict]:

        from scipy.optimize import least_squares

        from types import SimpleNamespace

        c = self.ctx

        res_p1 = []

        # ``wt_wls`` = pre-calculated spectral weights on the objective grid lambda.

        for run_idx, (label, wt_wls, x0_run) in enumerate(c.runs):
            if c._stop:
                break

            _run_start = time.perf_counter()

            _max_iter = int(c.cfg.get("re_phase1_maxiter", 100))

            c._emit_re_prog(
                c._pct_p1(run_idx, 0.0),
                f"RE phase 1 (TRF, {label})  "
                f"variables={c.n_layers_count} (thicknesses); "
                f"nominal indices (Re H/L/substrate drift = 0%)",
            )

            _cache = {"x": None, "res": None, "jac": None, "mse": None, "i": 0, "last_emit": time.perf_counter()}

            def _eval_both(
                x: np.ndarray,
                _cache=_cache,
                wt_wls=wt_wls,
                label=label,
                _run_start=_run_start,
                _max_iter=_max_iter,
                run_idx=run_idx,
            ) -> None:

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

                if _cache["i"] == 1 or (now - _cache["last_emit"]) >= 3.0:
                    _cache["last_emit"] = now

                    rs = float(np.sqrt(max(_cache["mse"], 0.0)))

                    rq = c._compute_qwot_rmse(x, c._correc_nom)

                    rmse_cur = c._rmse_combined(rs, rq)

                    _trf_rms = _re_trf_residual_rms(_cache["res"])

                    msg = (
                        f"RE [{label}] TRF iter ~{_cache['i']}  "
                        f"RMSE_facade={rmse_cur:.6f} (sqrt(sp2+alpha·QWOT2); Deltaln(lambda) trap) | "
                        f"TRF_RMS(r)={_trf_rms:.6g}  "
                        f"{now - _run_start:.1f}s since run start"
                    )

                    logging.info(msg)

                    _intra_p1 = min(
                        0.92,
                        float(_cache["i"]) / float(max(_max_iter, 1)),
                    )

                    c._emit_re_prog(c._pct_p1(run_idx, _intra_p1), msg)

                    c._emit_re_spectrum_live(x, _cache["i"], correc=c._correc_nom, last_mse=_cache["mse"], force=False)

            def _fun_res(x: np.ndarray, _cache=_cache) -> Any:

                _eval_both(x)

                return _cache["res"]

            def _jac_res(x: np.ndarray, _cache=_cache) -> Any:

                _eval_both(x)

                return _cache["jac"]

            try:
                res = least_squares(
                    _fun_res,
                    x0_run,
                    method="trf",
                    bounds=c.bounds_trf,
                    jac=_jac_res,
                    x_scale="jac",
                    ftol=c.RE_LBFGSB_FTOL,
                    xtol=c.RE_LBFGSB_FTOL,
                    gtol=c.RE_LBFGSB_GTOL,
                    max_nfev=max(10, _max_iter),
                )

            except REUserStopRequested:
                x_use = _cache["x"] if _cache["x"] is not None else np.asarray(x0_run, dtype=np.float64).ravel()

                res = SimpleNamespace(
                    x=np.asarray(x_use, dtype=np.float64).copy(),
                    nfev=max(0, int(_cache["i"])),
                    success=False,
                )

            x_final = res.x.copy()

            ep_final = np.asarray(x_final, dtype=np.float64).flatten()

            a_final = 0.0

            b_final = 0.0

            f_final = 0.0

            rmse_final = float(np.sqrt(max(c._report_mse_spectral(ep_final, c._correc_nom), 0.0)))

            rmse_qwot_final = c._compute_qwot_rmse(ep_final, c._correc_nom)

            rmse_comb_final = c._rmse_combined(rmse_final, rmse_qwot_final)

            phase1_result = REPhase1Result(
                label=str(label),
                ep=np.asarray(ep_final, dtype=np.float64).flatten(),
                a=float(a_final),
                b=float(b_final),
                f=float(f_final),
                rmse=float(rmse_final),
                rmse_qwot=float(rmse_qwot_final),
                rmse_combined=float(rmse_comb_final),
                nfev=int(res.nfev),
                success=bool(res.success),
            )
            res_p1.append(phase1_result.to_legacy_dict())

            c._emit_re_spectrum_live(
                ep_final,
                res.nfev,
                correc=c._correc_nom,
                force=True,
                rmse_override=rmse_comb_final,
            )

            _run_dt = time.perf_counter() - _run_start

            logging.info(
                f"RE phase 1 (TRF, {label}) done  "
                f"RMSE_spectral={rmse_final:.6f} | RMSE_QWOT={rmse_qwot_final:.6f} | "
                f"RMSE_combined={rmse_comb_final:.6f} (={c._alpha_slot[0]})  nfev={res.nfev}"
            )

            c._emit_re_prog(
                c._pct_p1(run_idx + 1, 0.0),
                f"RE phase 1 (TRF, {label}) {float(_run_dt):.1f}s - "
                f"RMSE_sp={float(rmse_final):.5f} | RMSE_OT={float(rmse_qwot_final):.5f} | "
                f"RMSE_facade={float(rmse_comb_final):.5f}",
            )

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

    def _execute_phase1_p4_scan(self) -> None:
        """Step 2/3 in sequential order: flat ap scan + joint TRF thick+ap (nominal indices)."""

        L = self._re_phase_ns

        results = L.results

        if (
            L._re_use_staged_order
            and results
            and not self._stop
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
            _n_ap_scan_s2 = max(4, int(self.cfg.get("re_phase4_aperture_scan_points", RE_PHASE4_APERTURE_SCAN_POINTS)))

            _apb_cfg_s2 = self.cfg.get("re_phase4_ap_bounds_deg")
            if _apb_cfg_s2 is not None:
                _vb = np.asarray(_apb_cfg_s2, dtype=np.float64).ravel()
                if _vb.size >= 2:
                    _c0, _c1 = float(_vb[0]), float(_vb[1])
                    if 0.0 < _c0 < _c1 < 90.0:
                        _lo_ap_s2, _hi_ap_s2 = _c0, _c1

            _p4_fd_ap_s2 = float(self.cfg.get("re_p4_ap_fd_step_deg", RE_P4_AP_FD_STEP_DEG))
            _p4_tol_s2 = float(self.cfg.get("re_phase4_trf_tol_factor", RE_PHASE4_TRF_TOL_FACTOR))
            _p4_nfev_s2 = max(8, int(self.cfg.get("re_phase4_ep_stage_max_nfev", self.cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))))

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

            def _eval_both_s2(xv_full: np.ndarray, *, emit_interval: float = 4.0) -> None:

                if self._stop:
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

        elif L._re_use_staged_order and not results and not self._stop:
            logging.info("RE staged order  step 2/3 skipped (no available phase-1 candidate).")

    def _execute_phase2_splines(self) -> None:
        """Phase 2: DeltaRe splines + prefit 2a / joint 2b (top-K).

        Structure (kept as single function due to closure coupling):
          §1  L+30   Local alias extraction from self._re_phase_ns
          §2  L+100  FD config, knots, envelope, Cauchy substrate setup
          §3  L+180  Bounds construction, top-K selection, Tikhonov
          §4  L+320  Closures: _eval_both_p2, _fun_res_p2, _jac_res_p2
          §5  L+700  Top-K loop: prefit 2a + joint 2b per candidate
          §6  L+1170 Finalization: sort, replace, emit live spectrum
        """

        L = self._re_phase_ns
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

        _fd = _prepare_phase2_fd_settings(self, re_env_s)
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
            self._stop,
            float(np.min(_env_knot)),
            float(np.max(_env_knot)),
            re_env_s,
            _fd_nw,
            _fd_par,
        )

        _use_sub_c3 = False

        L._use_sub_c3_shared = False

        # ── §3 Bounds, top-K, Tikhonov ────────────────────────────────────
        if results and not self._stop:
            bounds_ctx = _prepare_phase2_bounds_and_topk(
                self,
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

            _use_sub_c3 = bool(self.cfg.get("re_phase2b_substrate_cauchy", True)) and (_theta0_sub is not None)

            L._use_sub_c3_shared = bool(_use_sub_c3)

            if _use_sub_c3:
                _b_sub_c = [(-12.0, 12.0), (-12.0, 12.0), (-12.0, 12.0)]

                bounds_p2 = list(bounds_p2) + _b_sub_c

                logging.info(
                    "event=re_phase2b substrate=cauchy status=enabled tube_delta=%.2g nlambda=%d",
                    RE_SUB_CAUCHY_TUBE_DELTA,
                    len(wls),
                )

            elif bool(self.cfg.get("re_phase2b_substrate_cauchy", True)):
                logging.warning("event=re_phase2b substrate=cauchy status=unavailable reason=empty_feasible_set")

            elif not bool(self.cfg.get("re_phase2b_substrate_cauchy", True)):
                logging.info("event=re_phase2b substrate=fixed_tabulated status=active")

            _theta0_sub_arr = (
                np.asarray(_theta0_sub, dtype=np.float64).ravel()[:3]
                if _theta0_sub is not None
                else np.zeros(3, dtype=np.float64)
            )

            bounds_spref = bounds_spline + bounds_spline + [b_lam]

            _prefit_max = (
                int(
                    self.cfg.get(
                        "re_phase2_spline_prefit_maxiter",
                        RE_PHASE2_SPLINE_PREFIT_MAXITER,
                    )
                )
                if _any_spl_act
                else 0
            )

            _skip_2a = bool(self.cfg.get("re_phase2_skip_spline_prefit", False)) or not _any_spl_act

            if _skip_2a:
                _prefit_max = 0

            _hl_w = float(self.cfg.get("re_hl_delta_re_reg_sqrt_w", RE_HL_DELTA_RE_REG_SQRT_W))

            _dzre_l = float(self.cfg.get("re_hl_delta_re_deadzone_abs", RE_RE_DEADZONE_DELTA_RE_ABS))

            _dzqw_l = float(self.cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))

            logging.info(
                "event=re_phase2 prep=joint top_k=%d layers=%d spline_vars=%d prefit_2a_maxiter=%d prefit_2a=%s tikhonov=%s hl_reg_sqrt_w=%s hl_deadzone=%.3g qwot_deadzone=%.3g fd_step_spline=%.2e fd_step_lam2=%.4f",
                _top_k,
                n_layers_count,
                2 * _nk,
                _prefit_max,
                "on" if _prefit_max > 0 else "off",
                self.cfg.get("re_spline_tikhonov_scale", RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
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
                self.cfg.get(
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

            def _eval_both_p2(xv: np.ndarray, emit_interval: float = 3.0) -> tuple | None:
                return self._compute_eval_both_p2(ctx_p2, xv, emit_interval)

            def _fun_res_p2(xv: np.ndarray, emit_interval: float = 3.0) -> Any:
                return self._compute_fun_res_p2(ctx_p2, xv, emit_interval)

            def _jac_res_p2(xv: np.ndarray, emit_interval: float = 3.0) -> Any:
                return self._compute_jac_res_p2(ctx_p2, xv, emit_interval)

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
                if self._stop:
                    break

                _p2_ki_slot[0] = _ki

                candidate_dict = self._execute_phase2_candidate(
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

        elif self._stop:
            logging.warning("RE phase 2: not run (stop requested before phase 2).")

            _emit_re_prog(
                min(95.0, _re_pct_hi[0] + 1.0),
                "RE phase 2 cancelled (stopped by user).",
            )

    def _execute_phase2_candidate(
        self,
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

        if prefit_max > 0 and not self._stop:
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
                return self._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, ep_p1, _ki, _t_pf)

            def _fun_res_p2a(x_sp: np.ndarray, _cb2a=_cb2a) -> Any:
                return self._compute_fun_res_p2a(ctx_p2, x_sp, _cb2a)

            def _jac_res_p2a(x_sp: np.ndarray, _cb2a=_cb2a) -> Any:
                return self._compute_jac_res_p2a(ctx_p2, x_sp, _cb2a)

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

        maxiter_p2b = int(self.cfg.get("re_phase2b_maxiter", RE_PHASE2B_MAXITER))

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

    def _run_phase4_joint_trf(
        self,
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

        if p4_trf_nfev <= 0 or self._stop:
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

    def _execute_phase3_shakes(self) -> None:
        """Phase 3: perturbations + short TRF refits (escape local minima)."""

        L = self._re_phase_ns

        results = L.results

        _p2_ctx = L._p2_ctx

        _use_sub_c3 = bool(L._use_sub_c3_shared)

        if not _p2_ctx:
            logging.warning("RE phase 3 skipped: phase-2 context unavailable.")

            return

        _nk = int(_p2_ctx["_nk"])

        i0 = int(_p2_ctx["i0"])

        i_lam = int(_p2_ctx["i_lam"])

        i_cu = i_lam + 1

        b_lb = np.asarray(_p2_ctx["b_lb"], dtype=np.float64)

        b_ub = np.asarray(_p2_ctx["b_ub"], dtype=np.float64)

        bounds_p2_trf = _p2_ctx["bounds_p2_trf"]

        _cb2_ref = _p2_ctx["_cb2_ref"]


        _p2_trf_log_tag = _p2_ctx["_p2_trf_log_tag"]

        _eval_both_p2 = _p2_ctx["_eval_both_p2"]

        _fun_res_p2 = _p2_ctx["_fun_res_p2"]

        _jac_res_p2 = _p2_ctx["_jac_res_p2"]

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

        # Phase 3: Shake & Refit

        RE_PHASE3_SHAKE_EP_SIGMA_PCT = 1.5

        RE_PHASE3_SHAKE_SPL_SIGMA = 0.01

        RE_PHASE3_SHAKE_MAXITER = 80

        n_shakes = int(self.cfg.get("re_phase3_shake_rounds", RE_GUI_DEFAULT_RE_PHASE3_SHAKES))

        if n_shakes > 0 and not self._stop and results:
            _alpha_slot[0] = _a_p3

            _sk_sh = self.cfg.get("re_phase3_shake_seed", -1)

            try:
                _sk_i = int(_sk_sh)

            except (TypeError, ValueError):
                _sk_i = -1

            _rng3 = np.random.default_rng((_sk_i % (2**32)) if _sk_i >= 0 else None)

            best_res = results[0]
            best_res_dto = REPhase4Result.from_legacy_dict(best_res)

            x_best = np.concatenate(
                [
                    best_res_dto.ep,
                    best_res_dto.re_dh_knots,
                    best_res_dto.re_dl_knots,
                    [best_res_dto.re_spline_lam_node2_nm],
                    (
                        [best_res_dto.re_sub_cauchy_a0, best_res_dto.re_sub_cauchy_a1, best_res_dto.re_sub_cauchy_a2]
                        if _use_sub_c3 and best_res_dto.re_sub_cauchy_a0 is not None
                        else []
                    ),
                ]
            )

            rmse_best = float(best_res_dto.rmse_combined)

            cor_best = p2_result_to_correc_tuple(best_res, _use_sub_c3)

            _cb2_ref[0] = {
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

            _p2_trf_log_tag = ["phase 3 warmup"]

            _p2_trf_log_tag[0] = "pre-phase 3 warmup"

            _eval_both_p2(np.asarray(x_best, dtype=np.float64))

            _r0_ref = _cb2_ref[0].get("res")

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
                if self._stop:
                    break

                _sig_ep, _sig_sp = shake_sigmas_adaptive(
                    _rn0,
                    base_ep_sigma_pct=float(
                        self.cfg.get(
                            "re_phase3_shake_ep_sigma_pct",
                            RE_PHASE3_SHAKE_EP_SIGMA_PCT,
                        )
                    ),
                    base_spl_sigma=float(
                        self.cfg.get(
                            "re_phase3_shake_spl_sigma",
                            RE_PHASE3_SHAKE_SPL_SIGMA,
                        )
                    ),
                    ref_norm=float(self.cfg.get("re_phase3_shake_ref_norm", 1.0)),
                )

                x_shake = np.array(x_best, dtype=np.float64).copy()

                _u = _lhs_samples[_si]

                x_shake[:n_layers_count] += _u[:n_layers_count] * (_sig_ep / 100.0 * x_best[:n_layers_count])

                x_shake[i0:i_lam] += _u[n_layers_count:] * _sig_sp

                np.clip(x_shake, b_lb, b_ub, out=x_shake)

                _p2_trf_log_tag[0] = f"phase 3 shake {_si + 1}/{n_shakes}"

                _cr3 = _cb2_ref[0]

                if _cr3 is not None:
                    _cr3["i"] = 0

                    _cr3["x"] = None

                    _cr3["res"] = None

                    _cr3["jac"] = None

                    _cr3["mse"] = None

                    _cr3["best_rmse_combined"] = None

                    _cr3["last_emit"] = time.perf_counter()

                try:
                    res_sh = least_squares(
                        _fun_res_p2,
                        x_shake,
                        method="trf",
                        bounds=bounds_p2_trf,
                        jac=_jac_res_p2,
                        x_scale="jac",
                        ftol=RE_LBFGSB_FTOL * 10,
                        gtol=RE_LBFGSB_GTOL * 10,
                        max_nfev=RE_PHASE3_SHAKE_MAXITER,
                    )

                except REUserStopRequested:
                    logging.info("RE phase 3  stopped by user (keeping best phase 2 result)")

                    break

                x_sh = res_sh.x

                ep_sh = np.asarray(x_sh[:n_layers_count], dtype=np.float64).flatten()

                dh_sh = np.asarray(x_sh[i0 : i0 + _nk], dtype=np.float64).flatten()

                dl_sh = np.asarray(x_sh[i0 + _nk : i_lam], dtype=np.float64).flatten()

                lam_sh = float(x_sh[i_lam])

                knots_sh = re_knots_wavelengths(lam_sh)

                if _use_sub_c3:
                    th_sh = np.asarray(x_sh[i_cu : i_cu + 3], dtype=np.float64).ravel()

                    cor_sh = ("spline_sub3", dh_sh, dl_sh, lam_sh, float(th_sh[0]), float(th_sh[1]), float(th_sh[2]))

                else:
                    cor_sh = ("spline", dh_sh, dl_sh, lam_sh)

                rmse_p2_sh = float(np.sqrt(max(_report_mse_spectral(ep_sh, cor_sh), 0.0)))

                rmse_qwot_sh = _compute_qwot_rmse(ep_sh, cor_sh)

                rmse_comb_sh = _rmse_combined(rmse_p2_sh, rmse_qwot_sh)

                if rmse_comb_sh < rmse_best - 1e-8:
                    x_best = res_sh.x.copy()

                    rmse_best = rmse_comb_sh

                    logging.info(f"RE phase 3 shake #{_si + 1}: improved -> RMSE_combined={rmse_best:.6f}")

                    phase3_result = REPhase3Result(
                        label=RE_RESULT_LABEL_WITH_DRIFT,
                        ep=np.asarray(ep_sh, dtype=np.float64).flatten(),
                        a=0.0,
                        b=0.0,
                        f=0.0,
                        re_dh_knots=np.asarray(dh_sh, dtype=np.float64).flatten(),
                        re_dl_knots=np.asarray(dl_sh, dtype=np.float64).flatten(),
                        re_knots_nm=np.asarray(knots_sh, dtype=np.float64).flatten(),
                        re_spline_lam_node2_nm=float(lam_sh),
                        rmse=float(rmse_p2_sh),
                        rmse_qwot=float(rmse_qwot_sh),
                        rmse_combined=float(rmse_comb_sh),
                        nfev=int(best_res_dto.nfev + res_sh.nfev),
                        success=bool(res_sh.success),
                        nfev_phase1=int(best_res_dto.nfev_phase1),
                        nfev_phase2_prefit=int(best_res_dto.nfev_phase2_prefit),
                        re_sub_cauchy_a0=float(th_sh[0]) if _use_sub_c3 else None,
                        re_sub_cauchy_a1=float(th_sh[1]) if _use_sub_c3 else None,
                        re_sub_cauchy_a2=float(th_sh[2]) if _use_sub_c3 else None,
                    )
                    _phase3_as_p4 = REPhase4Result.from_legacy_dict(phase3_result.to_legacy_dict())
                    _set_top_result_dto(results, _phase3_as_p4)

                    cor_best = cor_sh

                    rmse_final_milestone[0] = float(_phase3_as_p4.rmse_combined)

                    _shake_best = float(_cb2_ref[0].get("best_rmse_combined", rmse_comb_sh))

                    if pl is not None:
                        _emit_re_prog(
                            _pct_p3(pl, _si, 1.0),
                            f"RE phase 3 shake {_si + 1}/{n_shakes}: "
                            f"best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}",
                        )

                    else:
                        _emit_re_prog(
                            97.0,
                            f"RE phase 3 shake {_si + 1}/{n_shakes}: "
                            f"best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}",
                        )

                    _new_top_dto = _top_result_dto(results)
                    if _new_top_dto is not None and _new_top_dto.rmse_combined < best_res_dto.rmse_combined:
                        _emit_re_spectrum_live(
                            np.asarray(_new_top_dto.ep, dtype=np.float64).flatten(),
                            int(_new_top_dto.nfev),
                            correc=cor_best,
                            force=True,
                            rmse_override=float(_new_top_dto.rmse_combined),
                        )


    def _finalize_re_run(
        self,
        *,
        results: list[dict],
        rmse_initial_sp: float,
        rmse_initial_q: float,
        rmse_initial_u: float,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        _alpha_slot: list[float],
        _alpha_rank_ref: float,
        re_qwot_alphas: tuple[float, float, float, float],
        _compute_qwot_rmse_raw,
        _compute_qwot_rmse,
        _correc_nom: tuple,
        _emit_re_spectrum_live,
        _report_t0: float,
        _re_pct_hi: list[float],
        n_sub_nominal: np.ndarray,
        wls: np.ndarray,
        lambda_ref: float,
        ep0: np.ndarray,
    ) -> None:
        """Sort/finalize RE results, emit final spectrum, logs and finished payload."""

        # Stop fallback, then best combined + tie-break + ranking enrichment.
        _top_result = REResultsPayloadBuilder.finalize_reconcile_top(
            results=results,
            stop_requested=bool(self._stop),
            cfg_ep0=self.cfg.get("ep0"),
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_initial_u=rmse_initial_u,
            alpha_rank_ref=_alpha_rank_ref,
            compute_qwot_rmse_raw=_compute_qwot_rmse_raw,
            sort_results=_re_sort_results_best_for_table_and_apply,
            enrich_results=re_enrich_results_ranking_fields,
        )
        _top_dto = REPhase4Result.from_legacy_dict(_top_result) if _top_result else None

        if _top_dto is not None:
            rmse_final_milestone[0] = float(_top_dto.rmse_combined)

        _stop_live_payload = REResultsPayloadBuilder.stop_live_emit_payload(
            stop_requested=bool(self._stop),
            top_result=_top_result,
            correc_nominal=_correc_nom,
            p2_to_correc=p2_result_to_correc_tuple,
        )
        if _stop_live_payload is not None:
            _emit_re_spectrum_live(
                _stop_live_payload["ep"],
                _stop_live_payload["nfev"],
                correc=_stop_live_payload["correc"],
                force=bool(_stop_live_payload["force"]),
                rmse_override=float(_stop_live_payload["rmse_override"]),
            )

        _tot = time.perf_counter() - _report_t0
        _top_metrics = REResultsPayloadBuilder.top_metrics(_top_result)
        _best_sp = float(_top_metrics["best_sp"])
        _best_ot = float(_top_metrics["best_ot"])
        _best = float(_top_metrics["best_combined"])
        rmse_final_u = float(_top_metrics["rmse_final_u"])

        if results:
            _a_gui = float(self.cfg.get("re_qwot_penalty_weight", RE_GUI_DEFAULT_RE_QWOT_ALPHA))
            _diag_payload = REResultsPayloadBuilder.final_diagnostic_payload(
                best_sp=float(_best_sp),
                best_ot=float(_best_ot),
                alpha_current=float(_alpha_slot[0]),
                alpha_gui=_a_gui,
                rmse_final_u=float(rmse_final_u),
                rmse_initial_u=float(rmse_initial_u),
                rmse_initial_sp=float(rmse_initial_sp),
                rmse_initial_q=float(rmse_initial_q),
            )

            logging.info("RE  final summary (progress readout / e.g. reverse_sample.xlsx) ")

            _re_log_objective_diagnostic(
                "final ( from last TRF phase)",
                _diag_payload["best_sp"],
                _diag_payload["ot_fin"],
                _diag_payload["alpha_current"],
            )

            _re_log_objective_diagnostic(
                "final (same sp/QWOT,  from base cfg / preset  comparison)",
                _diag_payload["best_sp"],
                _diag_payload["ot_fin"],
                _diag_payload["alpha_gui"],
            )

            logging.info(
                "RE summary  gains vs init: Delta RMSE=%+.6f | Delta sp=%+.6f | Delta QWOT=%+.6f",
                _diag_payload["delta_rmse"],
                _diag_payload["delta_sp"],
                _diag_payload["delta_qwot"],
            )

            _cauchy_diag = REResultsPayloadBuilder.cauchy_barrier_diagnostic_payload(
                top_result=_top_result,
                wls=wls,
                lambda_ref=lambda_ref,
                n_sub_nominal=n_sub_nominal,
                barrier_sqrt_w=float(
                    self.cfg.get(
                        "re_sub_cauchy_barrier_sqrt_w",
                        RE_SUB_CAUCHY_BARRIER_SQRT_W,
                    )
                ),
                tube_delta=float(RE_SUB_CAUCHY_TUBE_DELTA),
                substrate_phi_matrix=re_substrate_cauchy_phi_matrix,
                barrier_residuals_jac=re_substrate_cauchy_barrier_residuals_jac,
            )
            if _cauchy_diag is not None:
                logging.info(
                    "RE diag [Cauchy substrate barrier] ||r||=%.4g, %d/%d non-zero residuals "
                    "(tube |nn_tab|<=%.3g)  active boundary -> constraint saturated; zeros -> inside tube.",
                    _cauchy_diag["res_norm"],
                    _cauchy_diag["n_active"],
                    _cauchy_diag["n_total"],
                    _cauchy_diag["tube_delta"],
                )

        _tail = REResultsPayloadBuilder.finalize_tail_bundle(
            results=results,
            top_result=_top_result,
            ep0=ep0,
            alpha_rank_ref=_alpha_rank_ref,
            elapsed_s=_tot,
            best_sp=_best_sp,
            best_ot=_best_ot,
            best_combined=_best,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=bool(self._stop),
            re_qwot_alphas=re_qwot_alphas,
            ranking_log_suffix=re_finalize_ranking_log_suffix,
            finished_main_log_line=re_finalize_finished_main_log_line,
            rmse_milestone_log_line=re_finalize_rmse_milestone_log_line,
            progress_message_done=re_finalize_progress_message_done,
        )
        logging.info(_tail["finished_main_log"])
        logging.info(_tail["rmse_milestone_log"])

        _re_pct_hi[0] = 100.0

        self.signals.progress.emit(100, _tail["progress_done"])

        self.signals.finished.emit(_tail["finished_payload"])


    def _emit_re_spectrum_live_helper(
        self,
        ep_vec: np.ndarray,
        evals: int,
        *,
        correc: tuple,
        last_mse: float | None,
        force: bool,
        rmse_override: float | None,
        _re_live_emit: dict,
        n_lay_disp: np.ndarray,
        n_sub_disp: np.ndarray,
        is_H: np.ndarray,
        is_L: np.ndarray,
        wls_display: np.ndarray,
        lambda_ref: float,
        re_env_s: float,
        _re_env_on_wls_disp: np.ndarray,
        _mse_grad_accumulate_ep,
        wt_spectral: np.ndarray,
        _compute_qwot_rmse,
        _alpha_slot: list,
        _rmse_combined,
        oblique_config_meta: list,
        _re_state: dict,
        _ap_gui: float,
        oblique_tgts: list,
    ) -> None:
        if self._stop and not force:
            return

        now_te = time.perf_counter()
        if not force and _re_live_emit["t"] > 0.0 and (now_te - _re_live_emit["t"]) < 0.45:
            return

        _re_live_emit["t"] = now_te

        try:
            ep_use = np.asarray(ep_vec, dtype=np.float64).flatten()
            n_lm, n_sm = _re_apply_correc(
                n_lay_disp,
                n_sub_disp,
                is_H=is_H,
                is_L=is_L,
                wls=wls_display,
                lambda_ref=lambda_ref,
                correc=correc,
                re_env_s=re_env_s,
                env_cache=_re_env_on_wls_disp,
            )
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
                angle = float(meta["angle"])
                pol = str(meta["pol"])
                inc_back = bool(meta["include_backside"])
                dkey = (angle, pol, inc_back)

                if dkey in display_keys_done:
                    continue
                display_keys_done.add(dkey)

                R_o, T_o = _re_calc_spectrum_for_config(
                    wls_display,
                    n_lay_T_corr,
                    ep_use,
                    n_sub_use,
                    angle,
                    pol,
                    inc_back,
                    phase4_average=_re_state["is_phase4"],
                    beam_aperture=_ap_gui,
                    beam_aperture_knots_deg=_re_state["re_aperture_knots"],
                    beam_aperture_knots_lam_nm=_re_state["re_p4_beam_knots_lam_nm"],
                )
                spectra_display[dkey] = {"R": R_o, "T": T_o}

            if not spectra_display:
                return

            first_key = next(iter(spectra_display))
            Ts_first = spectra_display[first_key]["T"]
            _nk_prev = _re_correc_to_nk_preview_payload(correc)

            self.signals.result.emit(
                {
                    "type": "intermediate",
                    "wls": wls_display,
                    "Ts": Ts_first,
                    "ep": ep_use,
                    "rmse": rmse_d,
                    "rmse_sp": rs,
                    "rmse_qwot": rq,
                    "alpha_qwot": al_q,
                    "evals": int(evals),
                    "is_global_best": True,
                    "oblique_mode": True,
                    "spectra_display": spectra_display,
                    "oblique_tgts": oblique_tgts,
                    **_nk_prev,
                }
            )
        except NUMERICAL_FAULT_EXCEPTIONS as _emit_e:
            logging.debug("RE live spectrum emit: %s", _emit_e)

    def _build_re_run_context(self, _re_t0: float) -> Any:
        """Prepares grids, MSE/QWOT, self.ctx and self._re_phase_ns for RE phases."""
        logger.debug("_build_re_run_context ENTER")
        self.signals.progress.emit(1, "[DBG] _build_re_run_context: started")
        ctx, prep = _prepare_re_run_context_setup(self, _re_t0)
        _emit_re_prog = prep["_emit_re_prog"]
        _re_pct_hi = prep["_re_pct_hi"]
        wls = prep["wls"]
        _RE_P_SETUP = prep["_RE_P_SETUP"]
        _RE_P_P1 = prep["_RE_P_P1"]
        _mse_grad_accumulate_ep = _build_re_mse_grad_helper(self, ctx)
        mats = prep["mats"]
        stack = prep["stack"]
        ep0 = prep["ep0"]
        radius = prep["radius"]
        oblique_tgts = prep["oblique_tgts"]
        lambda_ref = prep["lambda_ref"]
        float_dtype = np.float64
        complex_dtype = np.complex128
        n_layers_count = prep["n_layers_count"]
        n_layers_nominal = prep["n_layers_nominal"]
        n_sub_nominal = prep["n_sub_nominal"]
        is_H = prep["is_H"]
        is_L = prep["is_L"]
        n_ref_nom_per_layer = prep["n_ref_nom_per_layer"]
        _lref_arr = prep["_lref_arr"]
        _p4_beam_knots_lam = prep["_p4_beam_knots_lam"]
        oblique_config_meta = prep["oblique_config_meta"]
        wt_spectral = prep["wt_spectral"]
        re_env_s = prep["re_env_s"]
        _re_env_on_wls = prep["_re_env_on_wls"]
        _ap_gui = prep["_ap_gui"]
        _re_state = prep["_re_state"]
        wls_min = prep["wls_min"]
        wls_max = prep["wls_max"]
        wls_display, n_sub_disp, n_lay_disp = re_live_plot_wls_and_dispersion_nk(
            mats,
            stack,
            wls_min,
            wls_max,
            float_dtype=float_dtype,
            complex_dtype=complex_dtype,
        )

        # Bounds: thicknesses only +/-radius %

        lb_ep, ub_ep = re_trf_thickness_bounds(ep0, radius)

        bounds_trf = (lb_ep, ub_ep)

        bounds = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)

        # --- QWOT RMSE helper (re_delta_qwot_per_layer = residu TRF) ---

        _qwot_helpers = _build_qwot_helpers(self, ep0, n_ref_nom_per_layer, is_H, is_L, lambda_ref, re_env_s, _lref_arr, ctx._alpha_slot)
        _get_delta_qwot = _qwot_helpers["_get_delta_qwot"]
        _compute_qwot_rmse = _qwot_helpers["_compute_qwot_rmse"]
        _compute_qwot_rmse_raw = _qwot_helpers["_compute_qwot_rmse_raw"]
        _rmse_combined = _qwot_helpers["_rmse_combined"]

        _re_env_on_wls_disp = re_envelope_max_delta_n(wls_display, scale=re_env_s)

        _re_live_emit = {"t": 0.0}
        # _ap_gui and _re_state already defined above (before REMseContext instantiation).

        def _emit_re_spectrum_live(
            ep_vec: np.ndarray,
            evals: int,
            *,
            correc: tuple,
            last_mse: float | None = None,
            force: bool = False,
            rmse_override: float | None = None,
        ) -> None:
            self._emit_re_spectrum_live_helper(
                ep_vec,
                evals,
                correc=correc,
                last_mse=last_mse,
                force=force,
                rmse_override=rmse_override,
                _re_live_emit=_re_live_emit,
                n_lay_disp=n_lay_disp,
                n_sub_disp=n_sub_disp,
                is_H=is_H,
                is_L=is_L,
                wls_display=wls_display,
                lambda_ref=lambda_ref,
                re_env_s=re_env_s,
                _re_env_on_wls_disp=_re_env_on_wls_disp,
                _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
                wt_spectral=wt_spectral,
                _compute_qwot_rmse=_compute_qwot_rmse,
                _alpha_slot=ctx._alpha_slot,
                _rmse_combined=_rmse_combined,
                oblique_config_meta=oblique_config_meta,
                _re_state=_re_state,
                _ap_gui=_ap_gui,
                oblique_tgts=oblique_tgts,
            )

        # --- Phase 1: TRF (Least Squares) Deltaln(lambda) trapezoidal, thickness only; tabulated (n,k) nominal ---

        n_starts = int(self.cfg.get("re_phase1_multistarts", RE_GUI_DEFAULT_RE_PHASE1_RESTARTS))

        runs = re_phase1_trf_runs_multistart(ep0, wt_spectral, lb_ep, ub_ep, n_starts, lhs_seed=42)

        n_sched = len(runs)

        _correc_nom = RE_CORREC_NOMINAL_PCT

        def _report_mse_spectral(ep_arr: np.ndarray, correc_t: tuple) -> float:

            return float(_mse_grad_accumulate_ep(ep_arr, wt_spectral, False, correc_t)[0])

        ep0_u = np.asarray(ep0, dtype=np.float64).flatten()

        rmse_initial_sp = float(np.sqrt(max(_report_mse_spectral(ep0_u, _correc_nom), 0.0)))

        rmse_initial_q = _compute_qwot_rmse(ep0_u, _correc_nom)

        _a_p1, _a_p2a, _a_p2b, _a_p3 = resolve_re_qwot_alphas(self.cfg, rmse_initial_sp, rmse_initial_q)

        ctx._alpha_slot[0] = _a_p1

        logging.info(
            "RE  QWOT (phase1=%g, 2a=%g, 2b=%g, 3=%g)  per_phase=%s adaptive_init=%s",
            _a_p1,
            _a_p2a,
            _a_p2b,
            _a_p3,
            bool(self.cfg.get("re_qwot_per_phase_schedule", True)),
            bool(self.cfg.get("re_qwot_adaptive_init_scale", False)),
        )

        rmse_initial_u = _rmse_combined(rmse_initial_sp, rmse_initial_q)

        _wp_ctx = self.cfg.get("re_workbook_path")

        if _wp_ctx:
            logging.info(
                "RE context  workbook: %s",
                Path(str(_wp_ctx)).name,
            )

        _n_tg_on = sum(1 for t in oblique_tgts if getattr(t, "on", True))

        _angles = sorted({float(t.angle) for t in oblique_tgts if getattr(t, "on", True)})

        logging.info(
            "RE context  lambda_ref=%.2f nm | objective grid [%.1f ... %.1f] nm (%d pts) | "
            "%d active targets | %d spectral blocks (weight Deltaln(lambda) trapezoidal) | incidence deg: %s | "
            "phase1 thickness radius +/-%g%%",
            float(lambda_ref),
            float(np.min(wls)) if wls.size else float("nan"),
            float(np.max(wls)) if wls.size else float("nan"),
            int(wls.size),
            _n_tg_on,
            len(oblique_config_meta),
            ", ".join(f"{a:g}" for a in _angles) if _angles else "",
            float(radius),
        )

        _re_log_objective_diagnostic(
            "initial (Excel design thicknesses)",
            rmse_initial_sp,
            rmse_initial_q,
            _a_p1,
        )

        _de_mx = int(self.cfg.get("re_phase1_de_maxiter", 0))

        _de_ps = int(self.cfg.get("re_phase1_de_popsize", 8))

        if _de_mx > 0 and not self._stop:
            try:
                from scipy.optimize import differential_evolution

                def _obj_de(x) -> float:

                    xa = np.asarray(x, dtype=np.float64).ravel()

                    v = float(_report_mse_spectral(xa, _correc_nom))

                    return float(np.sqrt(max(v, 0.0)))

                bounds_de = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)

                res_de = differential_evolution(
                    _obj_de,
                    bounds_de,
                    maxiter=_de_mx,
                    popsize=max(5, _de_ps),
                    seed=int(self.cfg.get("re_phase1_de_seed", 42)),
                    polish=False,
                    workers=1,
                )

                runs.insert(
                    0,
                    (
                        "DE->TRF",
                        wt_spectral,
                        np.asarray(res_de.x, dtype=np.float64).ravel(),
                    ),
                )

                n_sched = len(runs)

                logging.info(
                    "RE phase1  differential_evolution seed (maxiter=%d, popsize=%d)",
                    _de_mx,
                    _de_ps,
                )

            except NUMERICAL_FAULT_EXCEPTIONS as _e_de:
                logging.warning("RE phase1 differential_evolution skipped: %s", _e_de)

        _any_spl_act = bool(self.cfg.get("re_refine_h", True)) or bool(self.cfg.get("re_refine_l", True))

        _re_top_k_cfg = max(1, int(self.cfg.get("re_phase2_top_k", RE_GUI_DEFAULT_RE_PHASE2_TOP_K)))

        _re_n_sh_cfg = max(0, int(self.cfg.get("re_phase3_shake_rounds", 4))) if _any_spl_act else 0

        _re_prefit_max_cfg = (
            int(
                self.cfg.get(
                    "re_phase2_spline_prefit_maxiter",
                    RE_PHASE2_SPLINE_PREFIT_MAXITER,
                )
            )
            if _any_spl_act
            else 0
        )

        _re_skip_2a_cfg = bool(self.cfg.get("re_phase2_skip_spline_prefit", False)) or not _any_spl_act

        _re_do_2a_cfg = (not _re_skip_2a_cfg) and (_re_prefit_max_cfg > 0)


        _maxiter_p2b = max(10, int(self.cfg.get("re_phase2b_maxiter", RE_PHASE2B_MAXITER)))

        _re_use_staged_order = bool(_any_spl_act)

        re_p2_plan: list[dict | None] = [None]

        _bind_p2_plan = partial(
            re_build_p2_progress_plan,
            re_top_k_cfg=_re_top_k_cfg,
            re_p_setup=_RE_P_SETUP,
            re_p_p1=_RE_P_P1,
            re_n_sh_cfg=_re_n_sh_cfg,
            re_do_2a_cfg=_re_do_2a_cfg,
        )

        _pct_p1 = partial(
            re_progress_pct_p1,
            re_p_setup=_RE_P_SETUP,
            re_p_p1=_RE_P_P1,
            n_sched=n_sched,
        )

        _pct_p2a = re_progress_pct_p2a

        _pct_p2b = re_progress_pct_p2b

        _pct_p3 = partial(re_progress_pct_p3, re_n_sh_cfg=_re_n_sh_cfg)

        results = []

        rmse_initial_milestone = [float(rmse_initial_u)]

        rmse_phase1_milestone = [float("nan")]

        rmse_final_milestone = [float("nan")]

        _emit_re_spectrum_live(
            ep0_u,
            0,
            correc=_correc_nom,
            force=True,
            rmse_override=rmse_initial_u,
        )

        self.ctx = SimpleNamespace(
            runs=runs,
            n_layers_count=n_layers_count,
            _emit_re_prog=_emit_re_prog,
            _pct_p1=_pct_p1,
            wt_spectral=wt_spectral,
            _correc_nom=_correc_nom,
            _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
            _compute_qwot_rmse=_compute_qwot_rmse,
            _rmse_combined=_rmse_combined,
            bounds_trf=bounds_trf,
            RE_LBFGSB_FTOL=RE_LBFGSB_FTOL,
            RE_LBFGSB_GTOL=RE_LBFGSB_GTOL,
            _report_mse_spectral=_report_mse_spectral,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _alpha_slot=ctx._alpha_slot,
            _a_p1=_a_p1,
            rmse_initial_u=rmse_initial_u,
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            _re_use_staged_order=_re_use_staged_order,
            cfg=self.cfg,
            _stop=self._stop,
        )

        self._re_phase_ns = SimpleNamespace(
            results=results,
            oblique_config_meta=oblique_config_meta,
            _re_use_staged_order=_re_use_staged_order,
            _emit_re_prog=_emit_re_prog,
            _RE_P_SETUP=_RE_P_SETUP,
            _RE_P_P1=_RE_P_P1,
            _re_state=_re_state,
            _ap_gui=_ap_gui,
            _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
            wt_spectral=wt_spectral,
            _correc_nom=_correc_nom,
            bounds_trf=bounds_trf,
            n_layers_count=n_layers_count,
            _compute_qwot_rmse=_compute_qwot_rmse,
            _rmse_combined=_rmse_combined,
            _report_mse_spectral=_report_mse_spectral,
            rmse_final_milestone=rmse_final_milestone,
            wls=wls,
            re_env_s=re_env_s,
            n_sub_nominal=n_sub_nominal,
            lambda_ref=lambda_ref,
            bounds=bounds,
            _alpha_slot=ctx._alpha_slot,
            _a_p2a=_a_p2a,
            _a_p2b=_a_p2b,
            _a_p3=_a_p3,
            re_p2_plan=re_p2_plan,
            _bind_p2_plan=_bind_p2_plan,
            _pct_p2a=_pct_p2a,
            _pct_p2b=_pct_p2b,
            _pct_p3=_pct_p3,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _re_n_sh_cfg=_re_n_sh_cfg,
            _any_spl_act=_any_spl_act,
            _maxiter_p2b=_maxiter_p2b,
            _re_pct_hi=_re_pct_hi,
            _use_sub_c3_shared=False,
            _p2_ctx={},
        )

        return SimpleNamespace(
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_initial_u=rmse_initial_u,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            _alpha_slot=ctx._alpha_slot,
            _a_p1=_a_p1,
            _a_p2a=_a_p2a,
            _a_p2b=_a_p2b,
            _a_p3=_a_p3,
            _correc_nom=_correc_nom,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _compute_qwot_rmse_raw=_compute_qwot_rmse_raw,
            _compute_qwot_rmse=_compute_qwot_rmse,
            n_sub_nominal=n_sub_nominal,
            wls=wls,
            lambda_ref=lambda_ref,
            ep0=ep0,
            _re_pct_hi=_re_pct_hi,
            results=results,
            _re_t0=_re_t0,
        )


    def _compute_eval_both_p2(self, ctx, xv: np.ndarray, emit_interval: float = 3.0) -> tuple | None:

        if self._stop:
            raise REUserStopRequested()

        _c = ctx._cb2_ref[0]

        if _c is None:
            return

        # Phase 4: aperture knot values change MSE without changing xv  invalidate cache.

        _ph4_ap_now = None

        if ctx._re_state.get("is_phase4"):
            _kap = np.asarray(ctx._re_state["re_aperture_knots"], dtype=np.float64).ravel()[
                : int(RE_P4_BEAM_N_KNOTS)
            ]

            _ph4_ap_now = tuple(float(x) for x in _kap)

        if _c["x"] is not None and np.array_equal(xv, _c["x"]):
            if _ph4_ap_now is None:
                return

            if _c.get("_ph4_ap_snap") == _ph4_ap_now:
                return

        # S2: Invalidate Tikhonov weights when lam2 changes by >1 nm.

        cur_lam2 = float(xv[ctx.i_lam])

        if _c["tk_w_c"] is None or abs(cur_lam2 - (_c["tk_lam2"] or 0.0)) > 1.0:
            _c["tk_w_c"] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)

            _c["tk_lam2"] = cur_lam2

        tk_w_c = _c["tk_w_c"]

        _c["i"] += 1

        ep_x = np.asarray(xv[:ctx.n_layers_count], dtype=np.float64, copy=False)

        dh4 = xv[ctx.i0 : ctx.i0 + ctx._nk].copy()

        dl4 = xv[ctx.i0 + ctx._nk : ctx.i_lam].copy()

        lam2 = float(xv[ctx.i_lam])

        th4 = np.asarray(xv[ctx.i_cu : ctx.i_cu + 3], dtype=np.float64).ravel() if ctx._use_sub_c3 else None

        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam2), ctx.wls)

        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)

        if ctx._use_sub_c3:
            cor_spl = (
                "spline_cached_sub3",
                dh4,
                dl4,
                lam2,
                b_mat_c,
                env_c,
                tk_w_c,
                float(th4[0]),
                float(th4[1]),
                float(th4[2]),
            )

        else:
            cor_spl = ("spline_cached", dh4, dl4, lam2, b_mat_c, env_c, tk_w_c)

        mse, _, r_c, j_ep = ctx._mse_grad_accumulate_ep(ep_x, ctx.wt_spectral, True, cor_spl, return_residuals=True)

        if _c["i"] == 1:
            _n_fd = (ctx._n_joint_fd) if ctx._fd_1s else (ctx._n_joint_fd * 2)

            logging.info(
                "RE phase 2b  1st TRF eval: %d thick. analytic, %d FD residual blocks (%s)  FD_threads=%d",
                ctx.n_layers_count,
                _n_fd,
                "forward" if ctx._fd_1s else "centered",
                ctx._fd_nw,
            )

        J_var = np.zeros((len(r_c), ctx._n_joint_fd), dtype=np.float64)

        xv64 = np.asarray(xv, dtype=np.float64, copy=True)

        def _p2_fd_j_res(j: int) -> tuple[int, np.ndarray]:
            return self._evaluate_p2_fd_derivative(
                ctx,
                j,
                xv64,
                ep_x,
                r_c,
                b_mat_c,
                env_c,
                tk_w_c,
                dh4,
                dl4,
                lam2,
                th4,
            )

        _nw_j = min(ctx._fd_nw, ctx._n_joint_fd)

        _active_js = []

        _act_h = bool(self.cfg.get("re_refine_h", True))

        _act_l = bool(self.cfg.get("re_refine_l", True))

        for j in range(ctx._n_joint_fd):
            if j < ctx._nk and not _act_h:
                continue

            if ctx._nk <= j < 2 * ctx._nk and not _act_l:
                continue

            if j == 2 * ctx._nk and not (_act_h or _act_l):
                continue

            _active_js.append(j)

        if _nw_j <= 1:
            for j in _active_js:
                jj, j_col = _p2_fd_j_res(j)

                J_var[:, jj] = j_col

        else:
            _fd_executor_kind = str(self.cfg.get("re_phase2_fd_executor", "thread")).lower()
            _ex_p2 = _c.get("fd_executor")

            if _ex_p2 is None:
                # Use joblib instead of ThreadPool/ProcessPool for Phase 2 fd evaluation
                _backend = 'loky' if _fd_executor_kind == 'process' else 'threading'
                _ex_p2 = joblib.Parallel(n_jobs=_nw_j, backend=_backend)
                _c["fd_executor"] = _ex_p2

            try:
                # joblib blocks until all done and returns a list of results in order of _active_js
                results = _ex_p2(joblib.delayed(_p2_fd_j_res)(j) for j in _active_js)
                for res in results:
                    jj, j_col = res
                    J_var[:, jj] = j_col
            except Exception:
                if _fd_executor_kind == "process":
                    logging.getLogger(__name__).warning(
                        "RE phase2 FD process executor (loky) fallback to threading", exc_info=True
                    )
                    _fallback = joblib.Parallel(n_jobs=_nw_j, backend='threading')
                    _c["fd_executor"] = _fallback
                    results = _fallback(joblib.delayed(_p2_fd_j_res)(j) for j in _active_js)
                    for res in results:
                        jj, j_col = res
                        J_var[:, jj] = j_col
                else:
                    raise

        if ctx._use_sub_c3:
            J_spl = J_var[:, :ctx.n_sp]

            J_cu = J_var[:, ctx.n_sp : ctx.n_sp + 3]

            J_top = np.hstack([j_ep, J_spl, J_cu])

            sw_b = float(
                self.cfg.get(
                    "re_sub_cauchy_barrier_sqrt_w",
                    RE_SUB_CAUCHY_BARRIER_SQRT_W,
                )
            )

            r_b, J_b = re_substrate_cauchy_barrier_residuals_jac(
                th4,
                ctx._Phi_sub,
                ctx._n_tab_sub,
                sqrt_w=sw_b,
            )

            J_bot = np.hstack(
                [
                    np.zeros(
                        (len(r_b), ctx.n_layers_count + ctx.n_sp),
                        dtype=np.float64,
                    ),
                    J_b,
                ]
            )

            _c["res"] = np.concatenate((r_c, r_b))

            _c["jac"] = np.vstack([J_top, J_bot])

            _c["barrier_norm"] = float(np.linalg.norm(r_b))

        else:
            _c["res"] = r_c

            _c["jac"] = np.hstack([j_ep, J_var[:, :ctx.n_sp]])

            _c["barrier_norm"] = None

        _c["x"] = xv.copy()

        _c["mse"] = float(mse)

        _c["_ph4_ap_snap"] = _ph4_ap_now

        now = time.perf_counter()

        if _c["i"] == 1 or (now - _c["last_emit"]) >= emit_interval:
            _c["last_emit"] = now

            rs2 = float(np.sqrt(max(_c["mse"], 0.0)))

            rq2 = ctx._compute_qwot_rmse(ep_x, cor_spl)

            rmse_cur = ctx._rmse_combined(rs2, rq2)

            if ctx._p2_trf_log_tag[0] == "phase 4 finale":
                _ap_k = np.asarray(ctx._re_state["re_aperture_knots"], dtype=float).ravel()[
                    : int(RE_P4_BEAM_N_KNOTS)
                ]

                _lam_k = np.asarray(ctx._re_state.get("re_p4_beam_knots_lam_nm", []), dtype=float).ravel()[
                    : _ap_k.size
                ]

                _pairs = ", ".join(
                    f"(lambda={lk:.0f}nm->{ak:.2f})" for lk, ak in zip(_lam_k, _ap_k, strict=False)
                )

                ap_sfx = f" | ap=[{_pairs}]"

            else:
                ap_sfx = ""

            _bn = _c.get("barrier_norm")

            _bar_sfx = f" | ||barrier||={float(_bn):.4g}" if _bn is not None else ""

            _best_prev = _c.get("best_rmse_combined")

            if _best_prev is None or rmse_cur < float(_best_prev):
                _c["best_rmse_combined"] = float(rmse_cur)

            rmse_best_so_far = float(_c.get("best_rmse_combined", rmse_cur))

            _trf_rms_p2 = _re_trf_residual_rms(_c["res"])

            msg = (
                f"RE [{ctx._p2_trf_log_tag[0]}] TRF it ~{_c['i']}  "
                f"RMSE_facade(curr)={rmse_cur:.6f} | RMSE_facade(best)={rmse_best_so_far:.6f} "
                f"(sqrt(sp2+alpha·QWOT2); hors Tikhonov/pen H-L dans r) | "
                f"TRF_RMS(res)={_trf_rms_p2:.6g}{ap_sfx}{_bar_sfx}  {now - ctx._t_p2:.1f}s"
            )

            logging.info(msg)

            _intra_2b = min(
                0.92,
                float(_c["i"]) / float(max(ctx._maxiter_p2b, 1)),
            )

            ctx._emit_re_prog(
                ctx._pct_p2b(ctx.pl, ctx._p2_ki_slot[0], _intra_2b),
                msg,
            )

            ctx._emit_re_spectrum_live(ep_x, _c["i"], correc=cor_spl, last_mse=_c["mse"], force=False)

    def _compute_fun_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float = 3.0) -> Any:

        self._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)

        return ctx_p2._cb2_ref[0]["res"]

    def _compute_jac_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float = 3.0) -> Any:

        self._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)

        return ctx_p2._cb2_ref[0]["jac"]

    def _compute_eval_both_p2a(self, ctx, 
        x_sp: np.ndarray,
        _cb2a,
        ep_p1,
        _ki,
        _t_pf,
    ) -> tuple | None:

        if self._stop:
            raise REUserStopRequested()

        if _cb2a["x"] is not None and np.array_equal(x_sp, _cb2a["x"]):
            return

        # S2: Invalidate Tikhonov weights when lam2 changes by >1 nm.

        cur_lam2 = float(x_sp[2 * ctx._nk])

        if _cb2a["tk_w_c"] is None or abs(cur_lam2 - (_cb2a["tk_lam2"] or 0.0)) > 1.0:
            _cb2a["tk_w_c"] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)

            _cb2a["tk_lam2"] = cur_lam2

        tk_w_c = _cb2a["tk_w_c"]

        _cb2a["i"] += 1

        dh = np.asarray(x_sp[:ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)

        dl = np.asarray(x_sp[ctx._nk : 2 * ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)

        lam_p = float(x_sp[2 * ctx._nk])

        # Cache the B_matrix and envelope for the central point and the 10 FD perturbations (dh, dl)

        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam_p), ctx.wls)

        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)

        cor_c = self._build_cached_spline_correc(
            ctx,
            dh,
            dl,
            lam_p,
            tk_w_c,
            cached=True,
            b_mat_c=b_mat_c,
            env_c=env_c,
        )

        mse, _, r_c, _ = ctx._mse_grad_accumulate_ep(
            ep_p1, ctx.wt_spectral, False, cor_c, return_residuals=True
        )

        if _cb2a["i"] == 1:
            _n_fd = ctx.n_sp if ctx._fd_1s else (ctx.n_sp * 2)

            logging.info(
                "RE phase 2a  1st TRF eval: 0 thick. analytic, %d FD residual blocks "
                "(%s)  FD_threads=%d",
                _n_fd,
                "forward" if ctx._fd_1s else "centered",
                ctx._fd_nw,
            )

            ctx._emit_re_prog(
                ctx._pct_p2a(ctx.pl, _ki, 0.05),
                "RE phase 2a  first FD objective+grad eval (may take a few s)...",
            )

        J_sp = np.zeros((len(r_c), ctx.n_sp), dtype=np.float64)

        x_c = np.asarray(x_sp, dtype=np.float64, copy=True)

        def _pf_fd_j_res(j: int) -> tuple[int, np.ndarray]:

            hs = ctx._p2fd_lam if j == 2 * ctx._nk else ctx._p2fd_spl

            xp = np.array(x_c, copy=True)
            xp[j] += hs
            cor_p = self._build_cached_spline_correc(
                ctx,
                xp[:ctx._nk],
                xp[ctx._nk : 2 * ctx._nk],
                float(xp[2 * ctx._nk]),
                tk_w_c,
                cached=(j < 2 * ctx._nk),
                b_mat_c=b_mat_c,
                env_c=env_c,
            )

            r_p = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_p, return_residuals=True)[2]

            if ctx._fd_1s:
                return j, (r_p - r_c) / hs

            xm = np.array(x_c, copy=True)
            xm[j] -= hs
            cor_m = self._build_cached_spline_correc(
                ctx,
                xm[:ctx._nk],
                xm[ctx._nk : 2 * ctx._nk],
                float(xm[2 * ctx._nk]),
                tk_w_c,
                cached=(j < 2 * ctx._nk),
                b_mat_c=b_mat_c,
                env_c=env_c,
            )

            r_m = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_m, return_residuals=True)[2]

            return j, (r_p - r_m) / (2.0 * hs)

        _nw_sp = min(ctx._fd_nw, ctx.n_sp)

        if _nw_sp <= 1:
            for j in range(ctx.n_sp):
                jj, j_col = _pf_fd_j_res(j)

                J_sp[:, jj] = j_col

        else:
            _ex_pf = _cb2a.get("fd_executor")

            if _ex_pf is None:
                _ex_pf = ThreadPoolExecutor(max_workers=_nw_sp)

                _cb2a["fd_executor"] = _ex_pf

            _f_pf = [_ex_pf.submit(_pf_fd_j_res, j) for j in range(ctx.n_sp)]

            for _fu in as_completed(_f_pf):
                jj, j_col = _fu.result()

                J_sp[:, jj] = j_col

        _cb2a["x"] = x_sp.copy()

        _cb2a["res"] = r_c

        _cb2a["jac"] = J_sp

        _cb2a["mse"] = float(mse)

        now = time.perf_counter()

        if _cb2a["i"] == 1 or (now - _cb2a["last_emit"]) >= 3.0:
            _cb2a["last_emit"] = now

            logging.info(
                "RE phase 2a  TRF iter ~%d (%.1fs since prefit start)",
                _cb2a["i"],
                now - _t_pf,
            )

            _intra_2a = min(
                0.92,
                float(_cb2a["i"]) / float(max(ctx._prefit_max, 1)),
            )

            ctx._emit_re_prog(
                ctx._pct_p2a(ctx.pl, _ki, _intra_2a),
                f"RE phase 2a  iter {_cb2a['i']} TRF spline prefit...",
            )

    def _compute_fun_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:

        self._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))

        return _cb2a["res"]

    def _compute_jac_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:

        self._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))

        return _cb2a["jac"]


    def _execute_re_phases(self) -> None:
        """Orchestrate RE phases in nominal order."""
        REPhasesService(self).execute_all()

    def _finalize_from_context(self, fin) -> None:
        """Finalization adapter using the context built upstream."""

        _alpha_rank_ref = float(self.cfg.get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

        self._finalize_re_run(
            results=fin.results,
            rmse_initial_sp=fin.rmse_initial_sp,
            rmse_initial_q=fin.rmse_initial_q,
            rmse_initial_u=fin.rmse_initial_u,
            rmse_initial_milestone=fin.rmse_initial_milestone,
            rmse_phase1_milestone=fin.rmse_phase1_milestone,
            rmse_final_milestone=fin.rmse_final_milestone,
            _alpha_slot=fin._alpha_slot,
            _alpha_rank_ref=_alpha_rank_ref,
            re_qwot_alphas=(
                float(fin._a_p1),
                float(fin._a_p2a),
                float(fin._a_p2b),
                float(fin._a_p3),
            ),
            _compute_qwot_rmse_raw=fin._compute_qwot_rmse_raw,
            _compute_qwot_rmse=fin._compute_qwot_rmse,
            _correc_nom=fin._correc_nom,
            _emit_re_spectrum_live=fin._emit_re_spectrum_live,
            _report_t0=fin._re_t0,
            _re_pct_hi=fin._re_pct_hi,
            n_sub_nominal=fin.n_sub_nominal,
            wls=fin.wls,
            lambda_ref=fin.lambda_ref,
            ep0=fin.ep0,
        )

    def _run_re_workflow(self) -> None:
        """Corps nominal du thread RE (sans gestion d'erreur UI)."""
        logger.debug("_run_re_workflow start")
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: building context...")
        _re_t0 = time.perf_counter()
        fin = self._build_re_run_context(_re_t0)
        logger.debug("_run_re_workflow context built")
        self.signals.progress.emit(1, f"[DBG] _run_re_workflow: context OK in {time.perf_counter()-_re_t0:.2f}s, executing phases...")
        self._execute_re_phases()
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: phases done, finalizing...")
        self._finalize_from_context(fin)
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: finished.")

    def run(self) -> None:
        logger.info("RE worker run started")
        self.signals.progress.emit(1, "[DBG] REWorker.run(): thread started")
        try:
            self._run_re_workflow()
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("RE worker run failed: %s", e)
            self.signals.progress.emit(1, f"[DBG] REWorker.run() EXCEPTION: {e}")
            self.signals.error.emit(tb)
            self.signals.finished.emit(REResultsPayloadBuilder.build_error_payload(self.cfg.get("ep0")))

    def _get_phase4_aperture_bounds(self) -> tuple[float, float]:
        """Return validated beam aperture bounds for phase 4."""
        lo_ap, hi_ap = RE_P4_BEAM_AP_BOUNDS_DEG
        apb_cfg = self.cfg.get("re_phase4_ap_bounds_deg")
        if apb_cfg is not None:
            vb = np.asarray(apb_cfg, dtype=np.float64).ravel()
            if vb.size >= 2:
                c0, c1 = float(vb[0]), float(vb[1])
                if 0.0 < c0 < c1 < 90.0:
                    lo_ap, hi_ap = c0, c1
        return lo_ap, hi_ap

    def _run_phase4_aperture_scan(
        self,
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
            f"RE phase 4: scalar ap scan ({_n_ap_scan} pts, "
            f"{_lo_ap} to {_hi_ap} deg): same ap on all {_nap} lambda knots per trial "
            f"(flat beam during scan; joint TRF -> indep. ap per lambda knot)",
        )

        logging.info(
            "RE phase 4: during **scan**, a single ap is set at a time, "
            "replicated over all %d lambda knots (no chromatic steps at this stage).",
            _nap,
        )

        best_ap = 1.0
        best_ls_sq = float("inf")
        _p4_scan_emit = 1.0e9
        _p4_scan_trace: list[tuple[float, float]] = []
        _p4_cb_i_before_scan = int(_cb2_ref[0]["i"])
        _t_p4_scan_wall = time.perf_counter()

        for test_ap in np.linspace(_lo_ap, _hi_ap, _n_ap_scan):
            if self._stop:
                break
            _ta = float(test_ap)
            _re_state["re_aperture_knots"][:] = _ta
            _eval_both_p2(x0_base, emit_interval=_p4_scan_emit)
            _r_sc = _cb2_ref[0]["res"]
            _cost_sc = float(np.dot(_r_sc, _r_sc))
            _p4_scan_trace.append((_ta, _cost_sc))
            logging.debug(
                "RE phase 4 scan step | ap_deg=%.2f | ||r||^2=%.8g | n_res=%d",
                _ta,
                _cost_sc,
                int(_r_sc.size),
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
            "RE phase 4 scan profile | wall_s=%.4f | MSE_ep_delta=%d | "
            "scan_steps=%d | s_per_MSE_ep%.5f | opt: re_phase4_aperture_scan_points "
            "ou snap grille / warm cache",
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
                "RE phase 4 scan summary | n_steps=%d | best_ap_deg=%.2f | "
                "min||r||^2=%.8g | max||r||^2=%.8g | spread=%.8g | "
                "RMSE_sp(at_best)~%.6f | tune: re_phase4_aperture_scan_points bounds RE_P4_BEAM_AP_BOUNDS_DEG",
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
                    _kn_log,
                    np.full(_nap, float(best_ap), dtype=np.float64),
                    _wmin_obj,
                    _wmax_obj,
                ),
            )

            logging.debug(
                "RE phase 4 scan detail | " + " | ".join(f"ap={a:.2f}||r||2={c:.6g}" for a, c in _p4_scan_trace)
            )

        return _p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap

    def _get_phase4_scan_inputs(self, x0_base: np.ndarray, _nap: int, _ap_gui: float, wls: np.ndarray, oblique_config_meta: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float], list[float], str]:
        """Build derived phase-4 scan inputs and diagnostics."""
        _kn_log = np.asarray(self._re_phase_ns._re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[:_nap]
        _p4_hi_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) >= 10.0})
        _p4_lo_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) < 10.0})
        _kn_sorted_cfg = np.sort(np.asarray(_kn_log, dtype=np.float64).ravel().copy())
        _p4_band_thr = np.array([0.5 * (_kn_sorted_cfg[i] + _kn_sorted_cfg[i + 1]) for i in range(_nap - 1)], dtype=np.float64)
        _p4_scan_plateaus_s = _re_p4_ap_band_intervals_str(
            _kn_log,
            np.full(_nap, float(_ap_gui), dtype=np.float64),
            float(np.min(wls)),
            float(np.max(wls)),
        )
        return _kn_log, _p4_band_thr, _p4_scan_plateaus_s, _p4_hi_ang, _p4_lo_ang, repr(self.cfg.get("re_p4_beam_ap_knots_nm"))



    def _build_phase4_result(
        self,
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
        env_c = re_envelope_max_delta_n(wls, scale=self._re_phase_ns.re_env_s)
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
            cor_p4 = (
                "spline_cached",
                dh_v,
                dl_v,
                lam_v,
                b_mc,
                env_c,
                tk_mc,
            )

        rmse_p4_sp = float(np.sqrt(max(_report_mse_spectral(ep_f, cor_p4), 0.0)))
        rmse_qwot_p4 = _compute_qwot_rmse(ep_f, cor_p4)
        rmse_comb_p4 = _rmse_combined(rmse_p4_sp, rmse_qwot_p4)

        _ak4 = np.asarray(_re_state["re_aperture_knots"], dtype=np.float64).ravel()[: int(RE_P4_BEAM_N_KNOTS)]
        _kn4 = np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[: int(RE_P4_BEAM_N_KNOTS)]

        logging.info(
            "RE phase 4 result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | "
            "ap_deg(n knots)=%s | knots_lam_nm=%s | label=%s | "
            "tune: re_envelope_scale re_qwot_penalty_weight alpha schedule",
            rmse_comb_p4,
            rmse_p4_sp,
            rmse_qwot_p4,
            np.array2string(_ak4, precision=2, separator=","),
            np.array2string(_kn4, precision=2, separator=","),
            p4_label_suffix,
        )

        logging.info(
            "RE phase 4 plateaus (result explicit): %s",
            _re_p4_ap_band_intervals_str(_kn4, _ak4, _wmin_obj, _wmax_obj),
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
            re_p4_beam_ap_knots_nm=np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[: int(RE_P4_BEAM_N_KNOTS)],
            re_p4_beam_ap_knots_deg=np.asarray(_ak4, dtype=np.float64).flatten(),
            re_sub_cauchy_a0=float(th_v[0]) if (_use_sub_c3 and th_v is not None) else None,
            re_sub_cauchy_a1=float(th_v[1]) if (_use_sub_c3 and th_v is not None) else None,
            re_sub_cauchy_a2=float(th_v[2]) if (_use_sub_c3 and th_v is not None) else None,
        )
        return phase4_result, rmse_comb_p4

    def _execute_phase4_beam(self) -> None:
        """Phase 4: beam aperture (stepped ap over lambda), scan + joint TRF."""

        L = self._re_phase_ns

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

        # --- Phase 4: R/T average at theta +/- ap/2 (ap = total angular width); 1D scan + short joint TRF ---

        _has_high_angle = any(float(meta["angle"]) >= 10.0 for meta in oblique_config_meta)

        _p4_best_seen_rmse: float | None = None

        if results and not self._stop:
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
                    (
                        f"RE step 3/3: full joint optimization + beam (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots)"
                        if _re_use_staged_order
                        else f"RE phase 4: beam aperture (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots) - re_phase4_* cfg"
                    ),
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
                    4,
                    int(
                        self.cfg.get(
                            "re_phase4_aperture_scan_points",
                            RE_PHASE4_APERTURE_SCAN_POINTS,
                        )
                    ),
                )

                _lo_ap, _hi_ap = self._get_phase4_aperture_bounds()

                _p4_trf_nfev = int(self.cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))

                _p4_tol = float(self.cfg.get("re_phase4_trf_tol_factor", RE_PHASE4_TRF_TOL_FACTOR))

                _p4_fd_ap = float(self.cfg.get("re_p4_ap_fd_step_deg", RE_P4_AP_FD_STEP_DEG))

                _nap = int(RE_P4_BEAM_N_KNOTS)

                _kn_log, _p4_band_thr, _p4_scan_plateaus_s, _p4_hi_ang, _p4_lo_ang, _p4_cfg_knm = self._get_phase4_scan_inputs(
                    x0_base,
                    _nap,
                    _ap_gui,
                    wls,
                    oblique_config_meta,
                )

                _p4_ft_eff = float(RE_LBFGSB_FTOL) * _p4_tol

                _p4_gt_eff = float(RE_LBFGSB_GTOL) * _p4_tol

                _p4_band_thr_s = np.array2string(_p4_band_thr, precision=2, separator=",")

                _wmin_obj = float(np.min(wls))

                _wmax_obj = float(np.max(wls))

                logging.info(
                    "RE phase 4 config | wall_t0=same_block | n_wls_obj=%d "
                    "lambda_nm[min,max]=[%.2f,%.2f] | physics_groups=%d "
                    "angles_ge_10deg=%s | "
                    "knots_lam_nm(sorted_display)=%s | cfg_re_p4_beam_ap_knots_nm=%s | "
                    "band_fastpath_n=%d lambda_thresholds_nm=%s (paliers ap / bande) | "
                    "ap_bounds_deg=[%.4f,%.4f] | scan_grid=linspace_n=%d | "
                    "trf_max_nfev=%d | trf_tol_factor=%.4g -> ftol~%.3g xtol~%.3g gtol~%.3g | "
                    "ap_fd_step_deg=%.5g | joint_nvar=%d (n_layers=%d spline_block=%d sub_cauchy3=%s) | "
                    "re_beam_aperture_deg_init(cfg)=%.4f",
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
                    float(
                        self.cfg.get(
                            "re_beam_aperture_deg",
                            RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
                        )
                    ),
                )

                logging.info(
                    "RE phase 4 plateaus (scan grid, lambda intervals): %s",
                    _p4_scan_plateaus_s,
                )

                if _p4_lo_ang:
                    logging.info(
                        "RE phase 4 angle policy | P4 applied only for angles >=10: %s | "
                        "angles <10 kept without beam aperture averaging: %s",
                        _p4_hi_ang,
                        _p4_lo_ang,
                    )

                logging.info(
                    "RE phase 4 cost model | grep  P4 profile  +  P4 scan profile  +  TRF profile  "
                    "| one full MSE_ep: physics_groups × P4_block; P4_block (stepped lambda) <= %d bands "
                    "× (1 or 2) analytical oblique calls on lambda sub-grids | "
                    "scan: ~(n_scan+1) MSE_ep | TRF: each nfev LS = 1 residual; each jac ap = "
                    "1 MSE + %d FD(ap) + 1 restore (see SciPy njev)",
                    _nap,
                    _nap,
                )

                _p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap = self._run_phase4_aperture_scan(
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
                    phase4_result, rmse_comb_p4 = self._build_phase4_result(
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

                _p4_trf_wall_s, _p4_trf_mse_evals, _p4_best_seen_rmse = self._run_phase4_joint_trf(
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

                if not self._stop:
                    logging.info(
                        "RE phase 4: joint TRF disabled | re_phase4_trf_max_nfev=0  "
                        "scan-only (raise max_nfev to polish ap knots + thickness+splines jointly)"
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
                        "RE phase 4 scan-only result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | "
                        "min||r||^2(scan)=%.8g | ap_deg(n knots)=%s | knots_lam_nm=%s",
                        rmse_c_scan,
                        float(best_rmse_ap),
                        rmse_q_scan,
                        float(best_ls_sq),
                        np.array2string(_sk, precision=2, separator=","),
                        np.array2string(_skn, precision=2, separator=","),
                    )

                    logging.info(
                        "RE phase 4 scan-only plateaus (explicit): %s",
                        _re_p4_ap_band_intervals_str(
                            _skn,
                            _sk,
                            _wmin_obj,
                            _wmax_obj,
                        ),
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
                        "RE phase 4 P4 profile (in each MSE_ep, blocks >= 10, lambda-stepped ap) - "
                        "inner_physics_wall_s=%.4f | oblique_phi_calls=%d | "
                        "meta_passes=%d | n_wls_union_max=%d | "
                        "band_groups=%d band_mask_steps=%d | "
                        "<=%d -calls/group (2×%d lambda knots); "
                        "vectorizing by band reduces Python overhead",
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
                    "RE phase 4 wall | total=%.3fs | scan=%.3fs | TRF=%.3fs | "
                    "overheadmax(0,total-scan-TRF-inner_physics) | "
                    "grep  RE phase 4  /  P4 profile  pour retuner cfg & code",
                    _wall_p4_tot,
                    float(_p4_scan_wall_s),
                    float(_p4_trf_wall_s),
                )

                _re_state["p4_prof"] = None

            elif _has_high_angle:
                logging.info(
                    "RE phase 4 skipped | reason=no_spline_state_on_best | "
                    "need re_dH_knots/re_dL_knots on results[0] (phase 2 splines)"
                )

                _emit_re_prog(
                    99.0,
                    "RE phase 4  skipped (no Delta Re splines on best candidate)",
                )

            else:
                logging.info(
                    "RE phase 4 skipped | reason=all_angles_below_10deg | beam average not applied for low incidence"
                )

                _emit_re_prog(99.0, "RE phase 4  skipped (all angles < 10 deg)")

            _emit_re_prog(99.0, "RE phase 4  done")

class REPhasesService:
    """Thin service layer to orchestrate RE worker phases."""

    def __init__(
        self,
        worker: REWorker,
        steps: list["REPhaseStep"] | None = None,
        state_service: "REPhaseStateService | None" = None,
    ) -> None:
        self._worker = worker
        self._state_service = state_service or REPhaseStateService()
        self._steps = steps or [
            REPhase1Step(),
            REPhase1P4ScanStep(),
            REPhase2Step(),
            REPhase3Step(),
            REPhase4Step(),
        ]

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

    def run(self, service: REPhasesService) -> None: ...

class REPhaseStateService:
    """State transitions extracted from worker for phase orchestration."""

    def prepare_phase2_state(self, worker: REWorker) -> None:
        worker._re_phase_ns._re_state["is_phase4"] = False
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




# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# =============================================================================

# MAIN APPLICATION

# =============================================================================
