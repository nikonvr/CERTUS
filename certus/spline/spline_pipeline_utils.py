from __future__ import annotations

"""Main spline pipeline: JSON logging, RMSE snapshots, worker orchestration."""
import copy as _copy
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
import logging
from dataclasses import dataclass
import time
from threading import Event
from typing import Any, Callable
import numpy as np
from scipy.interpolate import PchipInterpolator
from certus.spline.certus_index_spline_core import (
    K_MIN_PHYS,
    SplineOptConfig,
    _canonical_knots_min_lambda_kw,
    canonical_spline_sigma_knots,
    corridor_profile_refit_maxfun,
    _bounds_x0_for_sigma_knots,
    _log_index_spline_best_config,
    log_index_spline_d_trace,
    _log_spline_pipeline_json,
    _reflectance_absolute_backside_from_nk,
    apply_rmse_fit_window_nk_nan_to_result,
    enforce_k_floor_on_nodes,
    snapshot_result_with_rmse_fit_meta,
    x_slice_n_to_physical_nodes,
    physical_nodes_to_x_slice_n,
)
from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _sorted_finite_sigma_knots as _sorted_finite_sigma_knots_for_log,
    _transmittance_absolute_from_nk,
)
from certus_physics import (
    clip_to_bounds,
)
from certus.spline.spline_objective import (
    build_segment_optimizer_x_vector,
    build_spline_objective_masked_grid,
    spectral_mse_rmse_masked_from_nk,
    spline_objective_mse_on_masked_grid,
)
from certus.spline.spline_finalize import (
    _collect_post_s3_candidates,
    _finalize_spectral_rmse_mesh_polish_and_best,
    _log_skipped_knot_insertion_fixed_mesh,
    _select_final_scientific_candidate,
    _spectral_polish_node_mesh_profile,
)
from certus.spline.certus_corridor_config import ProfileCorridorConfig
from certus.spline.spline_profile_corridors import compute_profiled_corridors_by_d
from certus.spline.certus_corridor_utils import widen_corridor_envelope_to_include_nk_in_result
from certus.spline.certus_corridor_logger import (
    log_coaching_corridor_pipeline_skip_empty,
    log_coaching_uncertainty_parameter_guide,
)



class _WorkerProgressCoordinator:
    """

    Monotonic gauge for the UI: maps local sub-phases (0-100) onto global ranges,

    without backtracking (avoids jumps like 93 % -> 5 % between SOL2 and legacy free-knot stage).

    Values sent to ``root_cb`` are **centi-percent** integers in ``0..10000`` (i.e. ``5423``

    means ``54.23 %``), except completion which emits ``10000`` for a full bar.

    """

    __slots__ = ("_root", "_last")

    def __init__(self, root_cb: Callable[[int, str], None]) -> None:

        self._root = root_cb

        self._last = 0.0

    def emit(self, g: float, msg: str) -> None:
        g = float(np.clip(g, 0.0, 99.99))
        if g < self._last:
            g = self._last
        self._last = g
        # Log percentage for linearity analysis (INFO for transitions, DEBUG for iterations)
        _logger = logging.getLogger("CERTUS")
        if "iterations=" in msg or "Polish L-BFGS-B" in msg:
            _logger.debug("[%5.2f%%] %s", g, msg)
        else:
            _logger.info("[%5.2f%%] %s", g, msg)
        self._root(int(min(10000, max(0, round(g * 100.0)))), msg)

    def scoped(self, lo: float, hi: float) -> Callable[[float | int, str], None]:
        lo = float(np.clip(lo, 0.0, 100.0))
        hi = float(max(lo, min(100.0, float(hi))))
        span = max(1e-9, hi - lo)
        coord = self

        def inner(p_local: float | int, msg: str) -> None:
            pl = float(np.clip(float(p_local), 0.0, 100.0))
            g = lo + span * (pl / 100.0)
            coord.emit(g, msg)

        return inner

    def finish(self, msg: str) -> None:
        self._last = 100.0
        logging.getLogger("CERTUS").info("[100.00%%] %s", msg)
        self._root(10000, msg)

def _log_manual_insert_decision(
    log: logging.Logger,
    *,
    event: str,
    op_id: str,
    decision: str,
    reason: str,
    K_before: int,
    K_after: int,
    rmse_ref: float,
    rmse_cand: float | None,
    mesh_summary: dict[str, Any],
    extra_sigma_knots: list[float],
    explicit_mesh_edit: bool,
    explicit_k_reduction: bool,
    force_reopt: bool,
    **fields: Any,
) -> None:
    rmse_delta = None if rmse_cand is None or not np.isfinite(rmse_cand) else float(rmse_cand - rmse_ref)
    rmse_ratio = None
    rmse_improved = None
    acceptance_rule = "rmse_cand <= rmse_ref"
    if rmse_cand is not None and np.isfinite(rmse_cand) and np.isfinite(rmse_ref):
        rmse_ratio = float(rmse_cand / max(rmse_ref, 1e-12))
        rmse_improved = bool(rmse_cand < rmse_ref)
    expected_decision = "accept" if (rmse_improved is True or explicit_k_reduction) else "reject"
    decision_consistency = None
    if rmse_improved is not None:
        decision_consistency = bool((decision == "accept" and rmse_improved) or (decision == "reject" and not rmse_improved))
    audit_status = "ok"
    human_status = "ACCEPTED" if decision == "accept" else "REJECTED"
    if decision == "accept" and rmse_delta is not None and rmse_delta > 0:
        audit_status = "accepted_worse_rmse"
        human_status = "ACCEPTED (worse RMSE)"
    elif decision == "reject" and rmse_delta is not None and rmse_delta < 0:
        audit_status = "rejected_better_rmse"
        human_status = "REJECTED (better RMSE)"
    elif decision_consistency is False:
        audit_status = "decision_metric_mismatch"
        human_status = f"{human_status} (metric mismatch)"
    _log_spline_pipeline_json(
        log,
        event,
        seq="05b",
        op_id=op_id,
        decision=decision,
        reason=reason,
        K_before=K_before,
        K_after=K_after,
        rmse_ref=float(rmse_ref),
        rmse_cand=(float(rmse_cand) if rmse_cand is not None and np.isfinite(rmse_cand) else None),
        rmse_delta=rmse_delta,
        rmse_ratio=rmse_ratio,
        rmse_improved=rmse_improved,
        expected_decision=expected_decision,
        decision_consistency=decision_consistency,
        acceptance_rule=acceptance_rule,
        audit_status=audit_status,
        extra_sigma_knots=extra_sigma_knots,
        explicit_mesh_edit=bool(explicit_mesh_edit),
        explicit_k_reduction=bool(explicit_k_reduction),
        force_reopt=bool(force_reopt),
        **mesh_summary,
        **fields,
    )

def _spl_rmse_improves_meaningfully(rmse_ref: float, rmse_cand: float) -> bool:
    """True if candidate RMSE beats the reference by more than numerical / tie noise."""
    if not (np.isfinite(rmse_cand) and np.isfinite(rmse_ref)):
        return False
    rr = float(rmse_ref)
    rc = float(rmse_cand)
    if rc >= rr:
        return False
    min_gain = max(1e-7, 1e-4 * max(abs(rr), 1e-12))
    return (rr - rc) > min_gain

def _spl_rmse_regression_exceeds_tolerance(
    cfg: SplineOptConfig,
    rmse_ref: float,
    rmse_cand: float,
) -> bool:
    """True when RMSE regression is larger than configured tolerance.

    Tolerances are optional config fields for explicit manual mesh edits:
    - ``manual_node_insert_max_rmse_regression_abs``
    - ``manual_node_insert_max_rmse_regression_rel``

    Default absolute tolerance is 5e-5 to avoid rejecting negligible regressions
    caused by optimizer noise on explicit manual mesh edits.
    """
    if not (np.isfinite(rmse_ref) and np.isfinite(rmse_cand)):
        return True
    rr = float(rmse_ref)
    rc = float(rmse_cand)
    if rc <= rr:
        return False

    abs_tol = float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5)
    rel_tol = float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0)
    allowed = max(abs_tol, rel_tol * max(abs(rr), 1e-12))
    return (rc - rr) > allowed

def _validated_extra_sigma_knots(base_sigma_knots: np.ndarray, extra_sigma_knots: np.ndarray) -> np.ndarray:
    """Return filtered extra sigma knots strictly inside the base range (no duplicates)."""
    sk = np.asarray(base_sigma_knots, dtype=np.float64).ravel()
    extra_raw = np.asarray(extra_sigma_knots, dtype=np.float64).ravel()
    if sk.size < 2 or extra_raw.size == 0:
        return np.empty(0, dtype=np.float64)

    # Filter out non-finite values
    extra_raw = extra_raw[np.isfinite(extra_raw)]
    if extra_raw.size == 0:
        return np.empty(0, dtype=np.float64)

    sigma_lo = float(sk[0])
    sigma_hi = float(sk[-1])
    span = max(abs(sigma_lo), abs(sigma_hi), 1.0)
    tol = max(1e-12, 1e-6 * span)

    valid_list = []
    # Sort to make comparison easier
    extra_sorted = np.sort(extra_raw)

    for val in extra_sorted:
        # 1. Check the boundaries
        if val <= (sigma_lo + tol) or val >= (sigma_hi - tol):
            continue

        # 2. Check distance against existing knots
        if np.any(np.abs(sk - val) <= tol):
            continue

        # 3. Check distance against knots already accepted in this loop
        if valid_list and (val - valid_list[-1]) <= tol:
            continue

        valid_list.append(val)

    return np.array(valid_list, dtype=np.float64)

def _should_skip_manual_insert_for_equal_mesh(
    sk_new: np.ndarray,
    sk: np.ndarray,
    *,
    offset_changed: bool,
    force_reopt: bool,
) -> bool:
    """True when manual insert can be skipped because nothing meaningful changed."""
    if bool(force_reopt):
        return False
    if bool(offset_changed):
        return False
    return bool(sk_new.size == sk.size and np.allclose(sk_new, sk, rtol=1e-10, atol=1e-12))

def _sigma_knot_difference_for_log(
    source_sigma_knots: np.ndarray | None, reference_sigma_knots: np.ndarray | None
) -> np.ndarray:
    src = _sorted_finite_sigma_knots_for_log(source_sigma_knots)
    ref = _sorted_finite_sigma_knots_for_log(reference_sigma_knots)
    if src.size == 0:
        return np.empty(0, dtype=np.float64)
    if ref.size == 0:
        return src.copy()
    used = np.zeros(ref.size, dtype=bool)
    missing: list[float] = []
    for value in src:
        tol = max(1e-12, 1e-8 * max(abs(float(value)), 1.0))
        idx = np.where((~used) & (np.abs(ref - float(value)) <= tol))[0]
        if idx.size:
            used[int(idx[0])] = True
        else:
            missing.append(float(value))
    return np.asarray(missing, dtype=np.float64)

def _sigma_knots_to_lambda_nm_for_log(sigma_knots: np.ndarray | None) -> np.ndarray:
    sig = _sorted_finite_sigma_knots_for_log(sigma_knots)
    if sig.size == 0:
        return np.empty(0, dtype=np.float64)
    return np.sort(1.0 / np.maximum(sig, 1e-30))

def _format_lambda_knots_nm_for_log(
    lambda_knots_nm: np.ndarray | None, *, precision: int = 1, max_items: int = 6
) -> str:
    lam = np.asarray(lambda_knots_nm if lambda_knots_nm is not None else [], dtype=np.float64).ravel()
    lam = lam[np.isfinite(lam) & (lam > 0.0)]
    if lam.size == 0:
        return "[]"
    lam = np.sort(lam)
    if lam.size <= int(max_items):
        return "[" + ", ".join(f"{float(v):.{precision}f}" for v in lam) + "]"
    head = [f"{float(v):.{precision}f}" for v in lam[:3]]
    tail = [f"{float(v):.{precision}f}" for v in lam[-2:]]
    return "[" + ", ".join([*head, "...", *tail]) + "]"

def _sigma_mesh_change_summary_for_log(
    before_sigma_knots: np.ndarray | None, after_sigma_knots: np.ndarray | None
) -> dict[str, Any]:
    before_sigma = _sorted_finite_sigma_knots_for_log(before_sigma_knots)
    after_sigma = _sorted_finite_sigma_knots_for_log(after_sigma_knots)
    removed_sigma = _sigma_knot_difference_for_log(before_sigma, after_sigma)
    added_sigma = _sigma_knot_difference_for_log(after_sigma, before_sigma)
    before_lambda = _sigma_knots_to_lambda_nm_for_log(before_sigma)
    after_lambda = _sigma_knots_to_lambda_nm_for_log(after_sigma)
    removed_lambda = _sigma_knots_to_lambda_nm_for_log(removed_sigma)
    added_lambda = _sigma_knots_to_lambda_nm_for_log(added_sigma)
    return {
        "mesh_delta_k": int(after_sigma.size - before_sigma.size),
        "mesh_removed_count": int(removed_sigma.size),
        "mesh_added_count": int(added_sigma.size),
        "mesh_before_lambda_summary": _format_lambda_knots_nm_for_log(before_lambda),
        "mesh_after_lambda_summary": _format_lambda_knots_nm_for_log(after_lambda),
        "mesh_removed_lambda_summary": _format_lambda_knots_nm_for_log(removed_lambda),
        "mesh_added_lambda_summary": _format_lambda_knots_nm_for_log(added_lambda),
    }

def _knots_cache_key(knots: np.ndarray) -> tuple[float, ...]:
    """Round knots to 15 decimals and return as hashable tuple."""
    arr = np.asarray(knots, dtype=np.float64).ravel()
    return tuple(float(v) for v in np.round(arr, decimals=15))

def _fmt_d_nm(v) -> str:
    """Format thickness value for log messages."""
    try:
        dv = float(v)
    except (TypeError, ValueError):
        return "n/a"
    return f"{dv:.3f} nm" if np.isfinite(dv) else "n/a"

def _meshes_match(a: np.ndarray, b: np.ndarray) -> bool:
    """Check if two sigma meshes are numerically identical within floating-point tolerance."""
    a1 = np.asarray(a, dtype=np.float64).ravel()
    b1 = np.asarray(b, dtype=np.float64).ravel()
    if a1.size != b1.size or a1.size == 0:
        return False
    span = max(abs(float(b1[-1] - b1[0])), 1.0)
    atol = max(1e-12, 1e-9 * span)
    return bool(np.allclose(a1, b1, rtol=0.0, atol=atol))

def _candidate_mesh_matches_target(cand: dict | None, target_knots: np.ndarray) -> bool:
    """Check if a candidate result dict has the expected sigma mesh."""
    if not isinstance(cand, dict):
        return False
    return _meshes_match(np.asarray(cand.get("sigma_knots", []), dtype=np.float64), target_knots)

def _pipeline_mesh_dimensions(
    cfg: SplineOptConfig,
) -> tuple[np.ndarray, int, int, int, float | None, float | None]:
    """Compute lambda array, bounds, and canonical mesh-derived SOL2 dimensions."""
    lam_arr = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    lam_min = float(np.min(lam_arr)) if lam_arr.size else None
    lam_max = float(np.max(lam_arr)) if lam_arr.size else None
    if lam_arr.size:
        sk_mesh = canonical_spline_sigma_knots(
            float(lam_min),
            float(lam_max),
            **_canonical_knots_min_lambda_kw(cfg),
        )
        k_mesh = int(np.asarray(sk_mesh).size)
    else:
        k_mesh = 12
    nseg_mesh = max(1, k_mesh - 1)
    dim_sol2 = 1 + 2 * k_mesh
    return lam_arr, k_mesh, nseg_mesh, dim_sol2, lam_min, lam_max

def _log_worker_start_payload(
    log: logging.Logger,
    cfg: SplineOptConfig,
    *,
    lam_arr: np.ndarray,
    k_mesh: int,
    nseg_mesh: int,
    lam_min: float | None,
    lam_max: float | None,
) -> None:
    """Emit the structured worker-start payload."""
    _log_spline_pipeline_json(
        log,
        "worker_start",
        seq="01",
        n_lambda=int(lam_arr.size),
        lam_nm_min=lam_min,
        lam_nm_max=lam_max,
        d_bounds=(float(cfg.d_lo), float(cfg.d_hi)),
        data_type=str(getattr(cfg.data_type, "name", cfg.data_type)),
        polish_maxfun=int(cfg.polish_maxfun),
        optimization_mode="local_only",
        lnk_spline_stage_enabled=bool(getattr(cfg, "lnk_spline_stage_enabled", True)),
        node_mesh_spectral_polish_enabled=bool(getattr(cfg, "node_mesh_spectral_polish_enabled", True)),
        t_is_ratio=bool(cfg.t_is_ratio),
        weight_t=float(cfg.weight_t),
        weight_r=float(cfg.weight_r),
        K_sigma_mesh=int(k_mesh),
        n_seg_mesh=int(nseg_mesh),
    )

def _log_final_insert_enter(
    log: logging.Logger,
    sol_spline: dict,
    *,
    k_mesh: int,
    nseg_mesh: int,
) -> None:
    """Emit fixed-mesh final-stage entry payload."""
    _log_spline_pipeline_json(
        log,
        "worker_final_insert_enter",
        seq="05",
        rmse_before=float(sol_spline["rmse"]),
        fixed_mesh=True,
        K_nodes=int(k_mesh),
        n_seg_fixed=int(nseg_mesh),
    )

def _log_after_final_insert(
    log: logging.Logger,
    sol_spline: dict,
    out: dict,
    *,
    mwir_insert_accepted: bool = False,
) -> None:
    """Emit payload after fixed-mesh insertion stage."""
    _log_spline_pipeline_json(
        log,
        "worker_after_final_insert",
        seq="06",
        rmse_sol_spline=float(sol_spline["rmse"]),
        rmse_chosen=float(out["rmse"]),
        used_insert_result=bool(mwir_insert_accepted),
        mwir_insert_accepted=bool(mwir_insert_accepted),
    )

def _log_fixed_mesh_stage_summary(
    log: logging.Logger, k_mesh: int, nseg_mesh: int, rmse: float, delta_ns: float = 0.0
) -> None:
    """Emit human-readable fixed-mesh stage summary."""
    log.info(
        "PIPELINE [05/09] Fixed mesh baseline prepared after SOL2 hand-off (K=%d sigma knots, %d segments) | RMSE=%.6f | delta_ns=%+.6f | optional MWIR stage follows before k-floor and corridors",
        int(k_mesh),
        int(nseg_mesh),
        float(rmse),
        float(delta_ns),
    )

def _log_after_final_stage_summary(
    log: logging.Logger,
    rmse: float,
    *,
    mwir_stage_considered: bool,
    mwir_insert_accepted: bool,
) -> None:
    """Emit summary after fixed-mesh stage completion."""
    if mwir_insert_accepted:
        mwir_txt = "MWIR extra-node accepted"
    elif mwir_stage_considered:
        mwir_txt = "MWIR extra-node evaluated but not kept"
    else:
        mwir_txt = "MWIR extra-node not applicable or disabled"
    log.info(
        "PIPELINE [06/09] After fixed-mesh/MWIR stage | kept RMSE=%.6f | %s "
        "(current spline solution before k-floor and before any downstream corridor worker)",
        float(rmse),
        mwir_txt,
    )

def _emit_enter_fixed_mesh_stage(coord: _WorkerProgressCoordinator) -> None:
    """Emit fixed-mesh stage entry progress marker."""
    coord.emit(68, "Final spline: fixed mesh baseline (optional MWIR stage next)...")

def _sync_theoretical_tr_from_nk_dict(
    cfg: SplineOptConfig,
    out: dict[str, Any],
    *,
    log: logging.Logger | None = None,
    reason: str = "generique",
) -> None:
    """Rebuild ``t_theo`` / ``r_theo`` from ``out`` wavelengths, ``n_lam``, ``k_lam``, ``d_nm``.

    Keeps the displayed / exported spectrum model aligned with indices when ``n_lam`` /
    ``k_lam`` / ``d_nm`` change without a prior transfer-matrix refresh (e.g. corridor
    promotion).
    """
    _audit_corridor = reason == "corridor_profile_bloc_fin"
    _warn_skip = log is not None and _audit_corridor

    def _skip(msg: str) -> None:
        if _warn_skip:
            log.warning(
                "PIPELINE [MODELE_SPECTRAL_SYNC] SKIP (audit corridor) | %s | reason=%s",
                msg,
                reason,
            )
        elif log is not None:
            log.debug("PIPELINE: skip t_theo sync | %s | raison=%s", msg, reason)

    lam_src = out.get("lam_nm", getattr(cfg, "lam_nm", None))
    if lam_src is None:
        _skip("pas de lam_nm ni cfg.lam_nm")
        return
    lam_full = np.asarray(lam_src, dtype=np.float64).ravel()
    n_l = np.asarray(out.get("n_lam"), dtype=np.float64).ravel()
    k_l = np.asarray(out.get("k_lam"), dtype=np.float64).ravel()
    if lam_full.size < 2 or n_l.size != lam_full.size or k_l.size != lam_full.size:
        _skip(f"tailles incompatibles lam={lam_full.size} n={n_l.size} k={k_l.size} (attendu n=k=lam)")
        return
    d_raw = out.get("d_nm", float("nan"))
    try:
        d_nm = float(d_raw)
    except (TypeError, ValueError):
        _skip("d_nm non convertible en float")
        return
    if not np.isfinite(d_nm):
        _skip("d_nm non fini")
        return
    if not (np.all(np.isfinite(lam_full)) and np.all(np.isfinite(n_l)) and np.all(np.isfinite(k_l))):
        _skip("lam/n/k contain non-finite values (sync impossible)")
        return
    n_sub_raw = out.get("n_sub_effective", getattr(cfg, "n_sub", None))
    n_sub_full = np.asarray(n_sub_raw, dtype=np.float64).ravel()
    if n_sub_full.size != lam_full.size:
        _skip(f"tailles incompatibles n_sub={n_sub_full.size} lam={lam_full.size} (attendu n_sub=lam)")
        return
    try:
        if cfg.t_is_ratio:
            out["t_theo"] = _ratio_theoretical_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
        else:
            out["t_theo"] = _transmittance_absolute_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
        if cfg.r_exp is not None:
            if cfg.t_is_ratio:
                out["r_theo"] = _reflectance_ratio_theoretical_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
            else:
                out["r_theo"] = _reflectance_absolute_backside_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        if log is not None:
            log.warning(
                "PIPELINE [MODELE_SPECTRAL_SYNC] FAILED recalculation (non-blocking) | reason=%s | %s",
                reason,
                ex,
            )
        return

    if log is None:
        return

    tt = np.asarray(out["t_theo"], dtype=np.float64).ravel()
    i1 = int(lam_full.size - 1)
    t0 = float(tt[0]) if tt.size == lam_full.size else float("nan")
    t1 = float(tt[i1]) if tt.size == lam_full.size else float("nan")
    l0 = float(lam_full[0])
    l1 = float(lam_full[i1])
    promoted = bool(out.get("profile_d_promoted"))
    log.info(
        "PIPELINE [MODELE_SPECTRAL_SYNC] OK | reason=%s | T_theo (and R_theo if active) recalculated "
        "from n_lam,k_lam,d_nm — proof that the model spectrum is aligned on the n,k tab "
        "(fix for \"noisy T\" bug after corridor promotion) | lam_pts=%d lambda[0,last]=[%.4f,%.4f] nm "
        "d_nm=%.6f T_substrat_norm=%s R_theo=%s | T_theo(λ_0,λ_last)=(%.6g,%.6g) | "
        "profile_d_promoted=%s",
        reason,
        int(lam_full.size),
        l0,
        l1,
        float(d_nm),
        bool(cfg.t_is_ratio),
        bool(cfg.r_exp is not None),
        t0,
        t1,
        promoted,
    )

def _stop_with_snapshot_if_requested(
    stop_event: Event,
    coord: _WorkerProgressCoordinator,
    stop_msg: str,
    cfg: SplineOptConfig,
    result: dict,
) -> dict | None:
    """Finish worker and return snapshot when stop is requested."""
    if not stop_event.is_set():
        return None
    coord.finish(stop_msg)
    return snapshot_result_with_rmse_fit_meta(cfg, result)

def enforce_local_optimization_policy(cfg: SplineOptConfig) -> None:
    """INDEX-SPLINE policy: optimization is local-only (L-BFGS-B)."""
    cfg.spline_local_only = True



def _interp_series_at_sigma_knots(
    lam_grid: np.ndarray, y_grid: np.ndarray, sigma_knots: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate a spectral series at sigma-knot wavelengths and return points sorted by lambda."""
    lam_g = np.asarray(lam_grid, dtype=np.float64).ravel()
    y_g = np.asarray(y_grid, dtype=np.float64).ravel()
    sig_k = np.asarray(sigma_knots, dtype=np.float64).ravel()

    m = np.isfinite(lam_g) & np.isfinite(y_g)
    if not np.any(m):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_f = lam_g[m]
    y_f = y_g[m]
    order_grid = np.argsort(lam_f, kind="mergesort")
    lam_f = lam_f[order_grid]
    y_f = y_f[order_grid]

    lam_k = 1.0 / np.maximum(sig_k, 1e-30)
    mk = np.isfinite(lam_k)
    if not np.any(mk):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_k = lam_k[mk]
    y_k = np.interp(lam_k, lam_f, y_f, left=y_f[0], right=y_f[-1])
    order_k = np.argsort(lam_k, kind="mergesort")

    return lam_k[order_k], y_k[order_k]
