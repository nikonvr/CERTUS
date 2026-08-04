from __future__ import annotations
from certus.utils.certus_re_math import re_substrate_cauchy_barrier_residuals_jac
from certus.utils.certus_re_math import re_substrate_cauchy_phi_matrix
from certus.utils.certus_re_math import RE_SPLINE_NODE2_BOUNDS_NM
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_PHASE2_TOP_K
from certus.utils.certus_re_config import RE_PHASE2_TOP_K_MERGE_REL_TOL
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_PHASE2_FD_MAX_WORKERS
from certus.utils.certus_re_config import RE_PHASE2_FD_PARALLEL
from certus.utils.certus_re_config import RE_PHASE2_ONESIDED_SPLINE_FD
from certus.utils.certus_re_config import RE_PHASE2_LAM2_FD_STEP
from certus.utils.certus_re_config import RE_PHASE2_SPLINE_FD_STEP
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_config import RE_RE_DEADZONE_QWOT_ABS
from certus.utils.certus_re_config import RE_RE_DEADZONE_DELTA_RE_ABS
from certus.utils.certus_re_config import RE_HL_DELTA_RE_REG_SQRT_W
from certus.utils.certus_re_math import re_envelope_max_delta_n
import numpy as np
import time
from typing import Any
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
import logging

logger = logging.getLogger(__name__)

from certus.utils.certus_re_helpers import (
    _re_apply_correc,
    _re_deadzone_excess_abs,
    re_knots_wavelengths,
    re_delta_qwot_per_layer,
    re_n_corr_at_lambda_ref,
    RE_SPLINE_CORREC_KINDS,
    RE_SPLINE_NODE2_DEFAULT_NM,
    _re_p4_chromatic_band_masks,
    _re_p4_band_ap_deg,
    _re_p4_effective_half_width_deg,
    _re_eval_angle_physics_for,
    RE_SPLINE_N_KNOTS,
    _re_p4_beam_knots_lam_nm_from_wls,
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    _re_p4_ap_band_intervals_str,
    _re_rmse_combined_spectral_qwot,
)
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV
from certus.core.certus_re_config import REMseContext, REPhase2Result, RE_RESULT_LABEL_WITH_DRIFT, _result_dto_at
from certus.workers.certus_re_worker_utils import (
    re_objective_wls_grid,
    re_nominal_indices_at_wls,
    re_oblique_config_meta_from_wls,
    re_objective_wls_weight_log_trap,
    p2_result_to_correc_tuple,
    re_finalize_ranking_log_suffix,
    re_finalize_finished_main_log_line,
    re_finalize_rmse_milestone_log_line,
    re_finalize_progress_message_done,
)


def _dbg_write(msg: str) -> None:
    logger.debug(msg)

def _contiguous_selector(idx: np.ndarray):
    """``slice`` equivalent a ``idx`` quand celui-ci est un intervalle contigu.

    Indexer un tableau numpy par un tableau d'entiers COPIE la selection ; par un
    ``slice``, on obtient une vue. Dans la boucle d'objectif de RE, cette copie
    portait sur un bloc (n_points x n_couches) reconstruit deux fois par bucket a
    chaque evaluation.

    Le test est en O(n) mais n'est fait qu'une fois, au montage des buckets. Si
    les indices ne sont pas contigus, on renvoie ``idx`` tel quel : le
    comportement est alors strictement inchange.
    """
    n = int(idx.size)
    if n == 0:
        return idx
    start = int(idx[0])
    stop = start + n
    if int(idx[-1]) == stop - 1 and np.array_equal(idx, np.arange(start, stop, dtype=np.int64)):
        return slice(start, stop)
    return idx


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
            # Selecteurs calcules ici, une seule fois, et non a chaque evaluation.
            bucket["idx_selector"] = _contiguous_selector(bucket["idx_union"])
            bucket["pos_selector"] = _contiguous_selector(np.asarray(pos, dtype=np.int64)) if pos.size else pos

def _re_init_context_fields(self, _re_t0: float) -> tuple:
    """Gather RE context inputs needed by _build_re_run_context."""
    re_pct_hi = [0.0]

    def _emit_re_prog(target: float, msg: str) -> None:
        v = max(re_pct_hi[0], float(target))
        re_pct_hi[0] = max(0.0, min(99.0, v))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message=msg, display_ratio=max(0.0, min(1.0, float(re_pct_hi[0]) / 100.0)), progress_ratio=max(0.0, min(1.0, float(re_pct_hi[0]) / 100.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='RE', phase='OBJECTIVE'))

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
    # Coeurs PHYSIQUES : les colonnes de differences finies appellent des noyaux
    # numba parallel=True, un thread par coeur logique en ouvrirait deux fois trop.
    from certus.core.certus_core import get_physical_core_count
    _cpu = get_physical_core_count()
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

    grad_raw = ctx.grad_raw_buf
    grad_raw.fill(0.0)

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
            cfg,
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

def _global_evaluate_oblique_physics(
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

            # Tampons LOCAUX, pas les champs partages de REMseContext.
            #
            # Le contexte est cree UNE SEULE FOIS par run (ligne 135) puis capture par
            # closure ; les 11 threads de derivees finies de la phase 4
            # (certus/workers/certus_re_workers_math.py:96, joblib.Parallel backend
            # 'threading', n_jobs = 2*RE_SPLINE_N_KNOTS+1 = 11) reutilisaient donc TOUS
            # les memes tableaux. Course reproduite : un thread ecrit sa bande, un autre
            # entre et fait son fill(0.0) qui l'efface, le premier relit un spectre a
            # moitie nul. Mesure : 5 essais sur 5 avec 10 a 11 colonnes de jacobien
            # fausses, sans aucune exception ni journal. Consequence : direction de
            # recherche fausse en phase 4, optimum degrade et non reproductible.
            #
            # wls_all.size est le bon dimensionnement : bucket['idx_union'] (ligne 79)
            # indexe la seule union pos_all_union, donc idx < pos_all.size == wls_all.size
            # — c'est deja l'hypothese de la branche non-phase-4 (ligne 572).
            _n_union = int(wls_all.size)
            _n_vars = int(ctx.n_layers_count)
            yR_all = np.zeros(_n_union, dtype=np.float64)
            yT_all = np.zeros(_n_union, dtype=np.float64)
            dR_all = np.zeros((_n_union, _n_vars), dtype=np.float64)
            dT_all = np.zeros((_n_union, _n_vars), dtype=np.float64)

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
            # Selecteurs precalcules : un slice quand la selection est contigue,
            # donc une VUE au lieu d'une copie du bloc (n_points x n_couches).
            # C'est ici que passait la moitie du temps de RE sur le profil a la
            # ligne de example/example_RE (32,1 % + 17,7 %) : la copie etait
            # refaite deux fois par bucket, a chaque evaluation de l'objectif.
            sel = bucket.get("idx_selector", idx)
            sel_pos = bucket.get("pos_selector", pos)
            spectral_weights_local = spectral_weights_wls[sel_pos]
            _accum_from_stats(yR_all[sel], dR_all[sel, :], bucket["R"], spectral_weights_local)
            _accum_from_stats(yT_all[sel], dT_all[sel, :], bucket["T"], spectral_weights_local)

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


def _warmup_re_physics() -> None:
    """Background JIT warmup for Reverse Engineering hot paths."""
    import numpy as np
    from certus.core.certus_re_config import REMseContext
    try:
        wls = np.linspace(400, 800, 10, dtype=np.float64)
        ep0 = np.array([50.0, 50.0], dtype=np.float64)
        is_H = np.array([True, False], dtype=bool)
        is_L = np.array([False, True], dtype=bool)
        n_layers_nominal = np.ones((10, 2), dtype=np.complex128)
        n_sub_nominal = np.ones(10, dtype=np.complex128)
        n_ref_nom_per_layer = np.ones(2, dtype=np.complex128)
        _lref_arr = np.ones(2, dtype=np.float64)
        
        oblique_config_meta = [
            {
                "angle": 0.0,
                "pol": "u",
                "include_backside": False,
                "pos_all_union": np.arange(10, dtype=np.int64),
                "buckets": [
                    {
                        "local_positions": np.arange(10, dtype=np.int64),
                        "idx_union": np.arange(10, dtype=np.int64),
                        "R": {"w_sum": 1.0, "w_tgt_sum": 1.0, "w_tgt2_sum": 1.0},
                        "T": {"w_sum": 1.0, "w_tgt_sum": 1.0, "w_tgt2_sum": 1.0},
                    }
                ]
            }
        ]
        
        ctx = REMseContext(
            _alpha_slot=[1.0],
            _lref_arr=_lref_arr,
            _re_env_on_wls=np.ones(10, dtype=np.float64),
            _re_state={"is_phase4": False},
            ep0=ep0,
            is_H=is_H,
            is_L=is_L,
            lambda_ref=500.0,
            n_layers_count=2,
            n_layers_nominal=n_layers_nominal,
            n_ref_nom_per_layer=n_ref_nom_per_layer,
            n_sub_nominal=n_sub_nominal,
            oblique_config_meta=oblique_config_meta,
            re_env_s=1.0,
            var_idx=np.array([0, 1], dtype=np.int64),
            wls=wls,
        )
        
        _global_compute_re_mse_gradient(
            cfg={"re_qwot_deadzone_abs": 0.0, "re_hl_delta_re_reg_sqrt_w": 0.0},
            ctx=ctx,
            ep_local=ep0,
            spectral_weights_wls=np.ones(10, dtype=np.float64),
            want_grad=True,
            correc=("spline", np.zeros(3), np.zeros(3), 500.0),
            return_residuals=True,
        )
    except Exception:
        pass
