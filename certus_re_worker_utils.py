# =============================================================================

# Testable helpers for REWorker (no Qt): QWOT alpha schedule, phase-2 correc tuple, shake sigmas.

# =============================================================================

from __future__ import annotations


from collections import defaultdict

from typing import Any, Final


import numpy as np


# Nominal tabulated indices (no Deltan correction) - same tuple everywhere in RE.

RE_CORREC_NOMINAL_PCT: Final[tuple[str, float, float, float]] = (
    "pct",
    0.0,
    0.0,
    0.0,
)


def re_objective_wls_weight_log_trap(wls: np.ndarray) -> np.ndarray:
    """

    Spectral weights for RE objective: Delta ln lambda trapezoidal quadrature.

    Unified with certus_index / certus_index_spline (spectral_rmse_weights).

    """

    # Canonical source for shared spectral weighting in CERTUS.

    from certus_index_utils import spectral_rmse_weights

    return spectral_rmse_weights(wls)


def re_objective_wls_grid(
    cfg: dict[str, Any],
    oblique_tgts: list,
    *,
    float_dtype=np.float64,
) -> tuple[np.ndarray, float, float]:
    """

    lambda grid for RE objective: band centers per active target, otherwise dense grid.

    Returns (wls, wls_min, wls_max).

    """

    wls_min = float(cfg.get("wls_min", 1000.0))

    wls_max = float(cfg.get("wls_max", 5200.0))

    tgt_centers = sorted({(t.lmin + t.lmax) / 2.0 for t in oblique_tgts if t.on})

    if tgt_centers:
        wls = np.array(tgt_centers, dtype=float_dtype)

    else:
        n_wls = max(500, int((wls_max - wls_min) / 2.0))

        wls = np.linspace(wls_min, wls_max, n_wls, dtype=float_dtype)

    return wls, wls_min, wls_max


def re_oblique_config_meta_from_wls(
    wls: np.ndarray,
    oblique_tgts: list,
) -> list[dict[str, Any]]:
    """

    Groups oblique targets by (angle, pol, backside) and builds spectral

    buckets (same logic as REWorker._build_re_run_context).

    """

    config_groups: dict[tuple[Any, Any, Any], list] = defaultdict(list)

    for tgt in oblique_tgts:
        if not tgt.on:
            continue

        config_groups[(tgt.angle, tgt.pol, tgt.include_backside)].append(tgt)

    oblique_config_meta: list[dict[str, Any]] = []

    for (angle, pol, include_backside), tgt_list in config_groups.items():
        buckets_by_pos: dict[tuple[int, ...], dict[str, Any]] = {}

        for tgt in tgt_list:
            mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)

            positions = np.where(mask)[0]

            if positions.size == 0:
                continue

            tgt_val = float((tgt.tmin + tgt.tmax) / 2.0)

            pos_key = tuple(int(p) for p in positions.tolist())

            bucket = buckets_by_pos.get(pos_key)

            if bucket is None:
                bucket = {
                    "local_positions": positions,
                    "R": {"w_sum": 0.0, "w_tgt_sum": 0.0, "w_tgt2_sum": 0.0},
                    "T": {"w_sum": 0.0, "w_tgt_sum": 0.0, "w_tgt2_sum": 0.0},
                }

                buckets_by_pos[pos_key] = bucket

            stats = bucket["R" if tgt.target_type == "R" else "T"]

            w_t = float(tgt.w)

            stats["w_sum"] += w_t

            stats["w_tgt_sum"] += w_t * tgt_val

            stats["w_tgt2_sum"] += w_t * tgt_val * tgt_val

        if buckets_by_pos:
            oblique_config_meta.append(
                {
                    "angle": angle,
                    "pol": pol,
                    "include_backside": include_backside,
                    "buckets": list(buckets_by_pos.values()),
                }
            )

    return oblique_config_meta


def re_nominal_indices_at_wls(
    mats: dict[str, Any],
    stack: list,
    wls: np.ndarray,
    lambda_ref: float,
    *,
    complex_dtype=np.complex128,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    nk(lambda) indices per layer, substrate, H/L masks, QWOT anchoring at lambda_ref.

    """

    mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

    n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

    n_sub_nominal = np.ascontiguousarray(mats_nk["Substrate"])

    is_H = np.array([l.mat == "H" for l in stack], dtype=bool)

    is_L = np.array([l.mat == "L" for l in stack], dtype=bool)

    n_layers_count = len(stack)

    _lref_arr = np.array([lambda_ref], dtype=np.float64)

    n_ref_nom_per_layer = np.array(
        [float(mats[stack[i].mat].get_nk(_lref_arr).real[0]) for i in range(n_layers_count)],
        dtype=np.float64,
    )

    return (
        n_layers_nominal,
        n_sub_nominal,
        is_H,
        is_L,
        n_ref_nom_per_layer,
        _lref_arr,
    )


def re_interpolate_progress_segment(
    pl: dict[str, Any],
    step: float,
    n_steps: float,
    k_lo: str,
    k_hi: str,
    intra: float,
) -> float:
    """Monotonic interpolation of RE progress bar percentages (phase 2/3)."""

    i = max(0.0, min(1.0, float(intra)))

    n = float(n_steps)

    lo, hi = float(pl[k_lo]), float(pl[k_hi])

    st = lo + (hi - lo) * (step / n)

    return st + i * (lo + (hi - lo) * ((step + 1) / n) - st)


def re_build_p2_progress_plan(
    n_res: int,
    *,
    re_top_k_cfg: int,
    re_p_setup: float,
    re_p_p1: float,
    re_n_sh_cfg: int,
    re_do_2a_cfg: bool,
) -> dict[str, Any]:
    """Splits progress bounds for phases 2a/2b/3 after phase 1."""

    tk = max(1, min(int(re_top_k_cfg), int(n_res)))

    base = float(re_p_setup) + float(re_p_p1)

    rem = 100.0 - base

    w_prep = 4.0

    w_p3 = 12.0 if int(re_n_sh_cfg) > 0 else 0.0

    w_2a = 11.0 if re_do_2a_cfg else 0.0

    w_2b = rem - w_prep - w_p3 - w_2a

    if w_2b < 12.0:
        w_2b = 12.0

    return {
        "tk": tk,
        "prep_mid": base + 0.5 * w_prep,
        "prep_end": base + w_prep,
        "p2a_lo": base + w_prep,
        "p2a_hi": base + w_prep + w_2a,
        "p2b_lo": base + w_prep + w_2a,
        "p2b_hi": base + w_prep + w_2a + w_2b,
        "p3_lo": base + w_prep + w_2a + w_2b,
        "p3_hi": 99.0,
    }


def re_progress_pct_p1(
    run_idx: int,
    intra: float,
    *,
    re_p_setup: float,
    re_p_p1: float,
    n_sched: int,
) -> float:
    """Percentage during phase 1 (thickness TRF)."""

    return float(re_p_setup) + float(re_p_p1) * (
        (float(run_idx) + max(0.0, min(1.0, float(intra)))) / float(max(1, int(n_sched)))
    )


def re_progress_pct_p2a(pl: dict[str, Any], ki: int, intra: float) -> float:

    return re_interpolate_progress_segment(pl, float(ki), float(pl["tk"]), "p2a_lo", "p2a_hi", intra)


def re_progress_pct_p2b(pl: dict[str, Any], ki: int, intra: float) -> float:

    return re_interpolate_progress_segment(pl, float(ki), float(pl["tk"]), "p2b_lo", "p2b_hi", intra)


def re_progress_pct_p3(pl: dict[str, Any], si: int, intra: float, re_n_sh_cfg: int) -> float:

    if int(re_n_sh_cfg) > 0:
        return re_interpolate_progress_segment(pl, float(si), float(re_n_sh_cfg), "p3_lo", "p3_hi", intra)

    return float(pl["p3_hi"])


def re_trf_thickness_bounds(ep0: np.ndarray, radius_pct: float) -> tuple[np.ndarray, np.ndarray]:
    """

    TRF bounds on thicknesses: +/-radius_pct % around ep0, lower bound >= 0.

    Returns (lb_ep, ub_ep) in float64.

    """

    ep = np.asarray(ep0, dtype=np.float64).ravel()

    pct = float(radius_pct) / 100.0

    lb_ep = np.maximum(0.0, ep * (1.0 - pct))

    ub_ep = ep * (1.0 + pct)

    return lb_ep, ub_ep


def re_trf_bounds_scipy_tuples(lb_ep: np.ndarray, ub_ep: np.ndarray) -> list[tuple[float, float]]:
    """Forme attendue par ``scipy.optimize`` (differential_evolution, etc.)."""

    lb = np.asarray(lb_ep, dtype=np.float64).ravel()

    ub = np.asarray(ub_ep, dtype=np.float64).ravel()

    if lb.size != ub.size:
        raise ValueError("lb_ep and ub_ep must have the same length")

    n = int(lb.size)

    return [(float(lb[i]), float(ub[i])) for i in range(n)]


def re_phase1_trf_runs_multistart(
    ep0: np.ndarray,
    wt_spectral: np.ndarray,
    lb_ep: np.ndarray,
    ub_ep: np.ndarray,
    n_starts: int,
    *,
    lhs_seed: int = 42,
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """

    Phase 1 start points: nominal point + (n_starts-1) LHS samples within TRF bounds.

    Each entry: (label, spectral weight, initial thickness vector x0).

    """

    lb_ep = np.asarray(lb_ep, dtype=np.float64).ravel()

    ub_ep = np.asarray(ub_ep, dtype=np.float64).ravel()

    x0_ep = np.asarray(ep0, dtype=np.float64).copy().ravel()

    # Same spectral weight vector for all multi-starts.

    wt = np.asarray(wt_spectral, dtype=np.float64)

    runs: list[tuple[str, np.ndarray, np.ndarray]] = [
        ("Deltalnlambda", wt, x0_ep.copy()),
    ]

    ns = max(1, int(n_starts))

    if ns <= 1:
        return runs

    rng = np.random.default_rng(int(lhs_seed))

    d = int(x0_ep.size)

    try:
        from scipy.stats.qmc import LatinHypercube

        sampler = LatinHypercube(d=d, seed=rng)

        samples = sampler.random(n=ns - 1)

    except ImportError:
        samples = rng.random((ns - 1, d))

    for i in range(ns - 1):
        x_lhs = lb_ep + samples[i] * (ub_ep - lb_ep)

        runs.append((f"Deltalnlambda (LHS #{i + 2})", wt, x_lhs))

    return runs


def re_live_plot_wls_and_dispersion_nk(
    mats: dict[str, Any],
    stack: list,
    wls_min: float,
    wls_max: float,
    *,
    n_points: int = 300,
    margin_frac: float = 0.20,
    float_dtype=np.float64,
    complex_dtype=np.complex128,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Extended lambda grid for live plot + n(lambda) per layer and substrate (same logic as REWorker).

    Returns (wls_display, n_sub_disp, n_lay_disp).

    """

    # Simplified English description of the plot utility

    margin_min = float(wls_min) * margin_frac

    margin_max = float(wls_max) * margin_frac

    wls_display = np.linspace(
        max(200.0, float(wls_min) - margin_min),
        float(wls_max) + margin_max,
        int(n_points),
    ).astype(float_dtype)

    mats_disp = {k: m.get_nk(wls_display) for k, m in mats.items()}

    n_sub_disp = np.ascontiguousarray(mats_disp["Substrate"])

    n_lay_disp = np.array([mats_disp[l.mat] for l in stack], dtype=complex_dtype)

    return wls_display, n_sub_disp, n_lay_disp


def re_ranking_combined_rmse(
    rmse_spectral: float,
    rmse_qwot_raw: float,
    alpha_ref: float,
) -> float:
    """

    Scalar metric to **rank** RE runs against each other (fixed alpha_ref, independent of

    alphas used during optimization). Same form as RMSE combined: sqrt(sp^2 + alpha_ref * QWOT^2).

    ``rmse_qwot_raw`` must be the RMS of |delta Q| **without** dead zone.

    """

    a = max(float(alpha_ref), 0.0)

    sp = max(float(rmse_spectral), 0.0)

    qw = max(float(rmse_qwot_raw), 0.0)

    return float(np.sqrt(sp * sp + a * qw * qw))


def resolve_re_qwot_alphas(
    cfg: dict[str, Any],
    rmse_sp_init: float,
    rmse_qwot_init: float,
) -> tuple[float, float, float, float]:
    """

    Return (alpha phase1, phase2a, phase2b, phase3).

    If ``re_qwot_per_phase_schedule`` is False, all equal ``re_qwot_penalty_weight``.

    If ``re_qwot_adaptive_init_scale``, multiply by a factor from initial sp/QWOT ratio (clamped).

    """

    base = float(cfg.get("re_qwot_penalty_weight", 0.05))

    if not bool(cfg.get("re_qwot_per_phase_schedule", True)):
        return (base, base, base, base)

    a1 = float(cfg.get("re_qwot_penalty_weight_phase1", 0.15))

    a2a = float(cfg.get("re_qwot_penalty_weight_phase2a", 0.10))

    a2b = float(cfg.get("re_qwot_penalty_weight_phase2b", base))

    a3 = float(cfg.get("re_qwot_penalty_weight_phase3", 0.02))

    if bool(cfg.get("re_qwot_adaptive_init_scale", False)) and rmse_qwot_init > 1e-15:
        s = float(np.clip((rmse_sp_init / rmse_qwot_init) * 0.1, 0.25, 4.0))

        a1, a2a, a2b, a3 = a1 * s, a2a * s, a2b * s, a3 * s

        a1 = float(np.clip(a1, 0.02, 0.5))

        a2a = float(np.clip(a2a, 0.02, 0.5))

        a2b = float(np.clip(a2b, 0.01, 0.5))

        a3 = float(np.clip(a3, 0.005, 0.3))

    return (a1, a2a, a2b, a3)


def p2_result_to_correc_tuple(r: dict[str, Any], use_sub_c3: bool) -> tuple:
    """Rebuild the ``correc`` tuple from a phase-2b result dict."""

    dh = np.asarray(r["re_dH_knots"], dtype=np.float64).ravel()

    dl = np.asarray(r["re_dL_knots"], dtype=np.float64).ravel()

    lam = float(r["re_spline_lam_node2_nm"])

    if use_sub_c3 and r.get("re_sub_cauchy_a0") is not None:
        return (
            "spline_sub3",
            dh,
            dl,
            lam,
            float(r["re_sub_cauchy_a0"]),
            float(r["re_sub_cauchy_a1"]),
            float(r["re_sub_cauchy_a2"]),
        )

    return ("spline", dh, dl, lam)


def re_enrich_results_ranking_fields(
    results: list[dict[str, Any]],
    *,
    alpha_rank_ref: float,
    compute_qwot_rmse_raw,
) -> None:
    """

    For each result in ``results``: derived correc from p2 or nominal,

    raw QWOT, ``re_ranking_alpha_ref``, ``re_ranking_score`` (aligned with ``_finalize_re_run``).

    """

    for _r in results:
        if _r.get("re_dH_knots") is not None and _r.get("re_dL_knots") is not None:
            _u_sub = _r.get("re_sub_cauchy_a0") is not None

            _cor_r = p2_result_to_correc_tuple(_r, _u_sub)

        else:
            _cor_r = RE_CORREC_NOMINAL_PCT

        _ep_r = np.asarray(_r["ep"], dtype=np.float64).flatten()

        _qw_raw = float(compute_qwot_rmse_raw(_ep_r, _cor_r))

        _sp_r = float(_r["rmse"])

        _r["re_rmse_qwot_raw"] = _qw_raw

        _r["re_ranking_alpha_ref"] = alpha_rank_ref

        _r["re_ranking_score"] = float(re_ranking_combined_rmse(_sp_r, _qw_raw, alpha_rank_ref))


def re_finalize_ranking_log_suffix(
    result0: dict[str, Any],
    alpha_rank_ref: float,
) -> str:
    """Ranking log fragment for REWorker finished line (empty if no score)."""

    if result0.get("re_ranking_score") is None:
        return ""

    return (
        f" | RMSE={float(result0['re_ranking_score']):.6f} "
        f"(ranking, _ref={float(result0.get('re_ranking_alpha_ref', alpha_rank_ref)):g}, "
        f"QWOT_raw={float(result0.get('re_rmse_qwot_raw', 0.0)):.6f})"
    )


def re_build_finished_payload_re(
    results: list,
    ep0: np.ndarray,
    rmse_initial_milestone: list[float],
    rmse_phase1_milestone: list[float],
    rmse_final_milestone: list[float],
    *,
    stopped_by_user: bool = False,
    re_qwot_alphas: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """``signals.finished`` payload at the end of RE (aligned with ``_finalize_re_run``)."""

    payload: dict[str, Any] = {
        "ok": True,
        "results": results,
        "ep0": ep0,
        "re_rmse_initial": rmse_initial_milestone[0],
        "re_rmse_phase1": rmse_phase1_milestone[0],
        "re_rmse_final": rmse_final_milestone[0],
        "re_ranking_score": (
            float(results[0]["re_ranking_score"])
            if results and results[0].get("re_ranking_score") is not None
            else None
        ),
        "re_rmse_qwot_raw": (
            float(results[0]["re_rmse_qwot_raw"])
            if results and results[0].get("re_rmse_qwot_raw") is not None
            else None
        ),
        "re_ranking_alpha_ref": (
            float(results[0]["re_ranking_alpha_ref"])
            if results and results[0].get("re_ranking_alpha_ref") is not None
            else None
        ),
    }

    if re_qwot_alphas is not None and len(re_qwot_alphas) == 4:
        a1, a2a, a2b, a3 = (float(x) for x in re_qwot_alphas)

        payload["re_qwot_alphas"] = (a1, a2a, a2b, a3)

        payload["re_qwot_alpha_phase2b"] = a2b

    if stopped_by_user:
        payload["re_stopped_by_user"] = True

    return payload


class REResultsBuilder:
    """Builder helper to centralize REWorker output payload contracts."""

    @staticmethod
    def build_finished_payload(
        *,
        results: list,
        ep0: np.ndarray,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        stopped_by_user: bool = False,
        re_qwot_alphas: tuple[float, float, float, float] | None = None,
    ) -> dict[str, Any]:
        return re_build_finished_payload_re(
            results=results,
            ep0=ep0,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=stopped_by_user,
            re_qwot_alphas=re_qwot_alphas,
        )

    @staticmethod
    def build_error_payload(ep0: Any) -> dict[str, Any]:
        return {"ok": False, "results": [], "ep0": ep0}


def re_result_dict_stop_before_first_trf(
    ep0_flat: np.ndarray,
    *,
    rmse_initial_sp: float,
    rmse_initial_q: float,
    rmse_initial_u: float,
) -> dict[str, Any]:
    """Fake result if cooperative stop before first TRF iteration (``_finalize_re_run``)."""

    return {
        "label": "initial (stop before first TRF iter)",
        "ep": ep0_flat,
        "a": 0.0,
        "b": 0.0,
        "f": 0.0,
        "rmse": float(rmse_initial_sp),
        "rmse_qwot": float(rmse_initial_q),
        "rmse_combined": float(rmse_initial_u),
        "nfev": 0,
        "success": False,
    }


def re_finalize_progress_message_done(
    *,
    stopped_by_user: bool,
    elapsed_s: float,
    best_sp: float,
    best_ot: float,
    best_combined: float,
) -> str:
    """100% progress bar message at RE end (``_finalize_re_run``)."""

    if stopped_by_user:
        return f"RE stopped  best RMSE_sp={best_sp:.5f} | RMSE_OT={best_ot:.5f} | RMSE={best_combined:.5f}"

    return f"RE finished in {elapsed_s:.1f}s  RMSE_sp={best_sp:.5f} | RMSE_OT={best_ot:.5f} | RMSE={best_combined:.5f}"


def re_finalize_finished_main_log_line(
    elapsed_s: float,
    best_sp: float,
    best_ot: float,
    best_combined: float,
    rank_suffix: str,
    n_runs: int,
) -> str:
    """Main log line "REWorker: finished..." (``_finalize_re_run``)."""

    return (
        f"REWorker: finished in {elapsed_s:.2f}s  "
        f"RMSE_sp={best_sp:.6f} | RMSE_OT={best_ot:.6f} | RMSE={best_combined:.6f}"
        f"{rank_suffix} ({n_runs} run(s))."
    )


def re_finalize_rmse_milestone_log_line(
    rmse_initial_milestone: list[float],
    rmse_phase1_milestone: list[float],
    rmse_final_milestone: list[float],
) -> str:
    """RMSE_combined milestone log line (initial / phase1 / final)."""

    return (
        f"RE RMSE_combined: initial{rmse_initial_milestone[0]:.6f} | "
        f"after thickness{rmse_phase1_milestone[0]:.6f} | final={rmse_final_milestone[0]:.6f}"
    )


def shake_sigmas_adaptive(
    residual_norm: float,
    *,
    base_ep_sigma_pct: float,
    base_spl_sigma: float,
    ref_norm: float = 1.0,
    scale_min: float = 0.5,
    scale_max: float = 2.5,
) -> tuple[float, float]:
    """

    Scale shake sigmas: small ||r|| (good fit) -> larger factor (wider exploration);

    large ||r|| -> smaller factor (avoid huge perturbations when the model is still far).

    """

    rn = float(max(residual_norm, 1e-18))

    ref = float(max(ref_norm, 1e-18))

    scale = float(ref / rn)

    scale = float(np.clip(scale, scale_min, scale_max))

    return (base_ep_sigma_pct * scale, base_spl_sigma * scale)
