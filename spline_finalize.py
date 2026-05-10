#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""Spline pipeline finalization: spectral polish on sigma mesh (cubic spline between knots)."""

from __future__ import annotations
from certus_core import NUMERICAL_FAULT_EXCEPTIONS


import logging


import time


from threading import Event


from typing import Any, Callable


import numpy as np


from scipy.optimize import minimize


from certus_physics import (
    clip_to_bounds,
)


from certus_index_spline_core import (
    SplineOptConfig,
    _canonical_knots_min_lambda_kw,
    canonical_spline_sigma_knots,
    _log_spline_pipeline_json,
)


from spline_objective import (
    build_spline_objective_masked_grid,
    nk_from_x_pwlnk,
    spectral_mse_rmse_masked_from_nk,
    spline_objective_mse_on_masked_grid,
    SplinePWLObjective,
    spline_pwl_analytic_grad_supported,
)


def _log_skipped_knot_insertion_fixed_mesh(
    cfg: SplineOptConfig,
    base_result: dict,
    stop_event: Event,
    progress_cb,
    live_cb=None,
) -> None:
    """Knot insertion post-legacy free-knot B: disabled - logs effective K and RMSE (fixed sigma mesh)."""

    del stop_event, progress_cb, live_cb

    log = logging.getLogger("CERTUS")

    cur = dict(base_result)

    cur_rmse = float(cur.get("rmse", float("inf")))

    if not np.isfinite(cur_rmse):
        return

    # K from result or canonical grid.

    sk_r = np.asarray(cur.get("sigma_knots"), dtype=np.float64).ravel()

    if sk_r.size >= 2:
        k_fix = int(sk_r.size)

    else:
        lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

        k_fix = int(
            canonical_spline_sigma_knots(
                float(np.min(lam)),
                float(np.max(lam)),
                **_canonical_knots_min_lambda_kw(cfg),
            ).size
        )

    nseg_fix = max(1, k_fix - 1)

    _log_spline_pipeline_json(
        log,
        "final_insert_skipped",
        seq="05",
        reason="fixed_k_mesh",
        K_nodes=int(k_fix),
        n_seg_fixed=int(nseg_fix),
        rmse_carry=float(cur_rmse),
    )


def _spectral_polish_node_mesh_profile(
    cfg: SplineOptConfig,
    out: dict[str, Any],
    x0: np.ndarray,
    sk: np.ndarray,
    bounds: np.ndarray,
    *,
    stop_event: Event | None,
    maxfun: int,
    progress_cb: Callable[[float | int, str], None] | None = None,
) -> dict[str, Any] | None:
    """

    L-BFGS-B on the mesh vector ``x = [d, n…, L…]`` with cubic spline in sigma between knots

    (not-a-knot if K>=4, linear fallback otherwise), minimizing masked spectral MSE.

    """

    log = logging.getLogger("CERTUS")

    mode = "smooth"

    mode_label = "cubic spline (not-a-knot) in sigma between nodes if K>=4, otherwise linear in sigma"

    if stop_event is not None and stop_event.is_set():
        log.info(
            "INDEX_SPLINE [sigma MESH POLISH] Abort: stop_event already raised before calculation.",
        )

        return None

    mgf = build_spline_objective_masked_grid(cfg)

    if mgf is None:
        log.warning(
            "INDEX_SPLINE [sigma MESH POLISH] Abort: no points in the spectral objective mask "
            "(build_spline_objective_masked_grid -> None). Check T/R data and lambda RMSE window.",
        )

        return None

    lam_f, sig_f, n_sub_f_mg, w_f, inv_npix, t_exp_f, r_exp_f = mgf

    n_mask = int(lam_f.size)

    n_sub_eff_f = np.asarray(n_sub_f_mg, dtype=np.float64)

    sk_a = np.asarray(sk, dtype=np.float64).ravel()

    b_arr = np.asarray(bounds, dtype=np.float64)

    x0 = np.asarray(x0, dtype=np.float64).ravel().copy()

    if x0.size != b_arr.shape[0] or sk_a.size * 2 + 1 != x0.size:
        log.warning(
            "INDEX_SPLINE [MESH POLISH] Abort: dimension inconsistency - len(x0)=%d, bounds=%s, K=%d (expected dim=1+2K=%d).",
            int(x0.size),
            str(b_arr.shape),
            int(sk_a.size),
            int(1 + 2 * sk_a.size),
        )

        return None

    x0 = clip_to_bounds(x0, b_arr[:, 0], b_arr[:, 1])

    def _obj(xv: np.ndarray) -> float:

        n_l, k_l = nk_from_x_pwlnk(
            xv,
            lam_f,
            sk_a,
            cfg.k_clip_lo,
            cfg.k_clip_hi,
            sig_pre=sig_f,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=mode,
        )

        m = spline_objective_mse_on_masked_grid(
            cfg,
            lam_f=lam_f,
            n_sub_f=n_sub_eff_f,
            w=w_f,
            inv_npix=inv_npix,
            t_exp_f=t_exp_f,
            r_exp_f=r_exp_f,
            n_l=n_l,
            k_l=k_l,
            d=float(xv[0]),
        )

        return float(m) if np.isfinite(m) else 1e30

    dim = int(x0.size)

    bds = [(float(b_arr[i, 0]), float(b_arr[i, 1])) for i in range(dim)]

    mf_use = int(max(200, maxfun))

    m0 = _obj(x0)

    prog = {
        "nfev": 0,
        "nit": 0,
        "t0": time.monotonic(),
        "last_emit": 0.0,
        "last_fun": float(m0),
    }

    rm0 = float(np.sqrt(max(m0, 0.0))) if np.isfinite(m0) else float("nan")

    log.info(
        "INDEX_SPLINE [sigma MESH POLISH] Starting L-BFGS-B | %s | K=%d sigma nodes | dim(x)=%d | "
        "objective mask points=%d | MSE(x0)=%.6e | RMSE(x0)=%.8f | d(x0)=%.6f nm | maxfun=%d | "
        "weights wT=%.4f wR=%.4f | data_type=%s",
        mode_label,
        int(sk_a.size),
        dim,
        n_mask,
        float(m0) if np.isfinite(m0) else float("nan"),
        rm0,
        float(x0[0]),
        mf_use,
        float(cfg.weight_t),
        float(cfg.weight_r),
        str(getattr(cfg.data_type, "name", cfg.data_type)),
    )

    def _emit_progress(force: bool = False) -> None:

        if progress_cb is None:
            return

        now = time.monotonic()

        frac = min(1.0, float(prog["nfev"]) / float(max(1, mf_use)))

        pct = 100.0 * frac

        if force or now - float(prog["last_emit"]) >= 5.0:
            prog["last_emit"] = now

            progress_cb(
                pct,
                f"Spectral mesh polish: evals={int(prog['nfev'])}/{mf_use} | nit={int(prog['nit'])} | RMSE={float(np.sqrt(max(float(prog['last_fun']), 0.0))):.6f} | elapsed={now - float(prog['t0']):.0f}s",
            )

    def _obj_progress(xv: np.ndarray) -> float:

        if stop_event is not None and stop_event.is_set():
            return 1e30

        prog["nfev"] += 1

        val = float(_obj(xv))

        prog["last_fun"] = val

        _emit_progress(force=False)

        return val

    def _cb_progress(_xk: np.ndarray) -> None:

        prog["nit"] += 1

        _emit_progress(force=False)

    _emit_progress(force=True)

    # Attempt analytic gradient via SplinePWLObjective (pure spectral, no penalty)
    # to match the _obj closure exactly while enabling jac=True.
    _minimize_fn = _obj_progress
    _minimize_jac = None
    try:
        cfg_pure = cfg.replace(spline_pure_spectral_objective=True)
        _spline_obj = SplinePWLObjective(cfg_pure, sk_a)
        if spline_pwl_analytic_grad_supported(cfg_pure):
            _gt = _spline_obj.analytic_gradient(x0)
            if _gt is not None and np.all(np.isfinite(_gt)):
                _grad_fn = _spline_obj.analytic_gradient

                def _combined_fun_and_grad(xv):
                    f = _obj_progress(xv)  # goes through progress tracking
                    g = _grad_fn(xv)
                    if g is None:
                        return f  # scipy falls back to FD
                    return f, g

                _minimize_fn = _combined_fun_and_grad
                _minimize_jac = True
                log.info("INDEX_SPLINE [sigma MESH POLISH] Analytic gradient enabled (jac=True).")
    except NUMERICAL_FAULT_EXCEPTIONS:
        log.debug(
            "Analytic gradient probe failed in mesh polish, using FD fallback",
            exc_info=True,
        )

    try:
        res = minimize(
            _minimize_fn,
            x0,
            method="L-BFGS-B",
            jac=_minimize_jac,
            bounds=bds,
            options={
                "maxfun": mf_use,
                "ftol": 1e-11,
                "gtol": 1e-8,
            },
            callback=_cb_progress,
        )

        prog["nfev"] = max(int(prog["nfev"]), int(getattr(res, "nfev", 0) or 0))

        prog["nit"] = max(int(prog["nit"]), int(getattr(res, "nit", 0) or 0))

        _emit_progress(force=True)

        x1 = np.asarray(res.x, dtype=np.float64).ravel()

        m1 = _obj(x1)

        nit = int(getattr(res, "nit", 0) or 0)

        nfev = int(getattr(res, "nfev", 0) or 0)

        if np.isfinite(m1) and m1 <= m0 + 1e-14:
            x_best, m_best, used = x1, m1, "lbfgsb"

            log.info(
                "INDEX_SPLINE [sigma MESH POLISH] L-BFGS-B completed | optimizer success | "
                "MSE %.6e -> %.6e | RMSE %.8f -> %.8f | d %.6f -> %.6f nm | nit=%d nfev=%d | message=%s",
                float(m0),
                float(m1),
                rm0,
                float(np.sqrt(max(m1, 0.0))) if np.isfinite(m1) else float("nan"),
                float(x0[0]),
                float(x1[0]),
                nit,
                nfev,
                str(getattr(res, "message", "")),
            )

        else:
            x_best, m_best, used = x0, m0, "x0_fallback"

            log.info(
                "INDEX_SPLINE [sigma MESH POLISH] Fallback to x0 initiated: MSE after L-BFGS-B (%.6e) "
                "not better than initial MSE (%.6e) - keeping starter.",
                float(m1) if np.isfinite(m1) else float("nan"),
                float(m0),
            )

    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        log.warning(
            "INDEX_SPLINE [sigma MESH POLISH] L-BFGS-B error (%s) - full fallback to x0 initiated.",
            ex,
            exc_info=True,
        )

        x_best, m_best, used = x0, m0, "exception_fallback"

    lam_full = np.asarray(out.get("lam_nm", cfg.lam_nm), dtype=np.float64).ravel()

    sig_full = 1.0 / np.maximum(lam_full, 1e-9)

    n_full, k_full = nk_from_x_pwlnk(
        x_best,
        lam_full,
        sk_a,
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=sig_full,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=mode,
    )

    d_best = float(x_best[0])

    mse_r, rmse_r = spectral_mse_rmse_masked_from_nk(cfg, out, lam_full, n_full, k_full, d_best)

    log.info(
        "INDEX_SPLINE [sigma MESH POLISH] Final summary (%s) | internal objective MSE=%.6e | "
        "recalculated RMSE (spectral_mse_rmse_masked_from_nk, full lambda grid)=%.8f | d=%.6f nm | "
        "n(lambda),k(lambda) curves exported under keys n_lam_seg_spline_sigma / k_lam_seg_spline_sigma",
        used,
        float(m_best),
        float(rmse_r) if np.isfinite(rmse_r) else float("nan"),
        d_best,
    )

    return {
        "x_best": np.asarray(x_best, dtype=np.float64).copy(),
        "n_lam": np.asarray(n_full, dtype=np.float64).copy(),
        "k_lam": np.asarray(k_full, dtype=np.float64).copy(),
        "d_nm": d_best,
        "spectral_rmse": float(rmse_r) if np.isfinite(rmse_r) else None,
        "spectral_mse": float(mse_r) if np.isfinite(mse_r) else None,
        "used": str(used),
        "profile_interp": mode,
    }


def _finalize_spectral_rmse_mesh_polish_and_best(out: dict[str, Any]) -> None:
    """Populate canonical solver/polished/global spectral RMSE fields.

    ``spectral_rmse_best_*`` remains a compatibility alias for the best polished
    model only.
    """

    log = logging.getLogger("CERTUS")

    labels_en = {
        "Solver_segments": "Current solver n(lambda), k(lambda), d_nm on the masked spectral objective",
        "Spline_cubique_sigma": "Mesh + cubic spline interpolation in sigma (L-BFGS-B polish on d and nodes)",
    }

    cand: list[tuple[str, float]] = []

    rs = out.get("spectral_rmse_seg_spline_sigma")

    if rs is not None and np.isfinite(float(rs)):
        cand.append(("Spline_cubique_sigma", float(rs)))

    rseg = out.get("spectral_rmse_segments")

    solver_rmse = float(rseg) if rseg is not None and np.isfinite(float(rseg)) else None

    out["spectral_rmse_solver_label"] = "Solver_segments" if solver_rmse is not None else None

    out["spectral_rmse_solver_value"] = solver_rmse

    out["spectral_rmse_solver_source"] = "solver" if solver_rmse is not None else None

    out["spectral_rmse_solver_status"] = "available" if solver_rmse is not None else "missing"

    global_cand: list[tuple[str, float]] = []

    if solver_rmse is not None:
        global_cand.append(("Solver_segments", float(solver_rmse)))

    global_cand.extend(cand)

    if global_cand:
        global_best = min(global_cand, key=lambda t: t[1])

        out["spectral_rmse_global_best_label"] = global_best[0]

        out["spectral_rmse_global_best_value"] = float(global_best[1])

        out["spectral_rmse_global_best_source"] = "solver" if global_best[0] == "Solver_segments" else "polished"

        out["spectral_rmse_global_best_status"] = "available"

    else:
        out["spectral_rmse_global_best_label"] = None

        out["spectral_rmse_global_best_value"] = None

        out["spectral_rmse_global_best_source"] = None

        out["spectral_rmse_global_best_status"] = "missing"

    n_cand = len(cand)

    log.info(
        "INDEX_SPLINE [SPECTRAL RMSE SUMMARY] sigma mesh polish (cubic spline) - %d model(s); "
        "each RMSE = measured spectrum vs theoretical T/R for this n(lambda),k(lambda) set - same lambda mask, "
        "same T/R weights as spline objective, nominal n_sub:",
        n_cand,
    )

    for key, val in cand:
        log.info(
            "  • %-26s RMSE = %.8f  (%s)",
            key,
            val,
            labels_en.get(key, key),
        )

    if not cand:
        out["spectral_rmse_best_label"] = None

        out["spectral_rmse_best_value"] = None

        out["spectral_rmse_polished_label"] = None

        out["spectral_rmse_polished_value"] = None

        out["spectral_rmse_polished_source"] = None

        out["spectral_rmse_polished_status"] = "missing"

        out["spectral_rmse_polished_best_label"] = None

        out["spectral_rmse_polished_best_value"] = None

        log.info(
            "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] No polished RMSE available - no 'best' to determine "
            "(sigma mesh polish disabled or failed)."
        )

        return

    best = min(cand, key=lambda t: t[1])

    out["spectral_rmse_best_label"] = best[0]

    out["spectral_rmse_best_value"] = float(best[1])

    out["spectral_rmse_polished_label"] = best[0]

    out["spectral_rmse_polished_value"] = float(best[1])

    out["spectral_rmse_polished_source"] = "polished"

    out["spectral_rmse_polished_status"] = "available"

    out["spectral_rmse_polished_best_label"] = best[0]

    out["spectral_rmse_polished_best_value"] = float(best[1])

    log.info(
        "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] -> Mesh polish model (excluding solver ref only): %s = %.8f - %s",
        best[0],
        float(best[1]),
        labels_en.get(best[0], best[0]),
    )

    if out.get("spectral_rmse_global_best_label") is not None:
        log.info(
            "INDEX_SPLINE [SPECTRAL RMSE GLOBAL] -> Global best among solver and polished models: "
            "%s = %.8f - source=%s",
            str(out.get("spectral_rmse_global_best_label")),
            float(out.get("spectral_rmse_global_best_value")),
            str(out.get("spectral_rmse_global_best_source")),
        )

    if rseg is not None and np.isfinite(float(rseg)):
        rsf = float(rseg)

        rb = float(best[1])

        tol = 1e-10 * max(1.0, rsf)

        if rb < rsf - tol:
            log.info(
                "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] Solver reference (main curves, without sigma mesh polish): "
                "spectral_rmse_segments = %.8f - sigma mesh polish better on spectral mask (%.8f vs %.8f).",
                rsf,
                rb,
                rsf,
            )

        elif rb > rsf + tol:
            log.info(
                "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] Solver reference: spectral_rmse_segments = %.8f - "
                "sigma mesh polish RMSE (%.8f) slightly higher (different n,k parameterization; see maxfun).",
                rsf,
                rb,
            )

            log.info(
                "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] Note: compare solver vs seg_spline_sigma n_lam/k_lam curves if needed.",
            )

        else:
            log.info(
                "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] Solver reference: spectral_rmse_segments = %.8f - "
                "sigma mesh polish RMSE ~ reference (%.8f).",
                rsf,
                rb,
            )


def _candidate_float_or_none(value: Any) -> float | None:

    try:
        fval = float(value)

    except (TypeError, ValueError):
        return None

    if not np.isfinite(fval):
        return None

    return fval


def _candidate_curve_or_none(value: Any) -> np.ndarray | None:

    if value is None:
        return None

    arr = np.asarray(value, dtype=np.float64).ravel()

    if arr.size == 0 or not np.all(np.isfinite(arr)):
        return None

    return arr.copy()


def _build_post_s3_candidate(
    *,
    candidate_id: str,
    label: str,
    origin: str,
    rmse: Any,
    n_lam: Any,
    k_lam: Any,
    d_nm: Any,
    selection_eligible: bool,
    corridor_base_mode: str | None,
    decision_reason: str,
    corridor_seed_compatible: bool | None = None,
    export_compatible: bool | None = None,
) -> dict[str, Any]:

    rmse_value = _candidate_float_or_none(rmse)

    n_arr = _candidate_curve_or_none(n_lam)

    k_arr = _candidate_curve_or_none(k_lam)

    d_value = _candidate_float_or_none(d_nm)

    physical_valid = d_value is not None and n_arr is not None and k_arr is not None and n_arr.size == k_arr.size

    eligible = bool(selection_eligible) and rmse_value is not None and physical_valid

    if corridor_seed_compatible is None:
        corridor_seed_compatible = bool(physical_valid and corridor_base_mode)

    if export_compatible is None:
        export_compatible = bool(physical_valid)

    return {
        "id": str(candidate_id),
        "label": str(label),
        "origin": str(origin),
        "rmse": rmse_value,
        "physical_valid": bool(physical_valid),
        "decision_reason": str(decision_reason),
        "selection_status": "collected",
        "selection_eligible": bool(eligible),
        "corridor_seed_compatible": bool(corridor_seed_compatible),
        "corridor_base_mode": None if corridor_base_mode is None else str(corridor_base_mode),
        "export_compatible": bool(export_compatible),
        "n_lam": None if n_arr is None else n_arr.copy(),
        "k_lam": None if k_arr is None else k_arr.copy(),
        "d_nm": d_value,
    }


def _collect_post_s3_candidates(
    out: dict[str, Any],
    *,
    solver_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:

    candidates: list[dict[str, Any]] = []

    solver_payload = solver_snapshot if isinstance(solver_snapshot, dict) and solver_snapshot else out

    solver_reason_parts = ["retained solver reference after fixed-mesh finalization"]

    if bool(out.get("post_s3_mwir_insert_accepted", False)):
        solver_reason_parts.append("MWIR extra-node retained into solver baseline")

    if bool(out.get("post_s3_k_floor_applied", False)):
        solver_reason_parts.append("k_floor enforced on solver baseline")

    solver_candidate = _build_post_s3_candidate(
        candidate_id="solver_segments",
        label=str(out.get("spectral_rmse_solver_label", "Solver_segments")),
        origin="solver",
        rmse=out.get("spectral_rmse_solver_value", out.get("spectral_rmse_segments")),
        n_lam=solver_payload.get("n_lam"),
        k_lam=solver_payload.get("k_lam"),
        d_nm=solver_payload.get("d_nm"),
        selection_eligible=True,
        corridor_base_mode="solver",
        decision_reason="; ".join(solver_reason_parts) + ".",
    )

    if solver_candidate["rmse"] is not None:
        candidates.append(solver_candidate)

    polished_candidate = _build_post_s3_candidate(
        candidate_id="polish_sigma_best",
        label=str(
            out.get("spectral_rmse_polished_label") or out.get("spectral_rmse_best_label") or "Spline_cubique_sigma"
        ),
        origin="polish_sigma",
        rmse=out.get("spectral_rmse_polished_value", out.get("spectral_rmse_seg_spline_sigma")),
        n_lam=out.get("n_lam_seg_spline_sigma"),
        k_lam=out.get("k_lam_seg_spline_sigma"),
        d_nm=out.get("d_nm_seg_spline_sigma", out.get("d_nm")),
        selection_eligible=True,
        corridor_base_mode="best_polished",
        decision_reason="best sigma-mesh polished model on the masked spectral objective.",
    )

    if polished_candidate["rmse"] is not None:
        candidates.append(polished_candidate)

    if bool(out.get("post_s3_mwir_insert_accepted", False)):
        candidates.append(
            _build_post_s3_candidate(
                candidate_id="mwir_stage_retained",
                label="MWIR_extra_node",
                origin="mwir",
                rmse=solver_candidate.get("rmse"),
                n_lam=solver_payload.get("n_lam"),
                k_lam=solver_payload.get("k_lam"),
                d_nm=solver_payload.get("d_nm"),
                selection_eligible=False,
                corridor_base_mode="solver",
                decision_reason="diagnostic stage marker: MWIR extra-node was retained into the solver baseline.",
                corridor_seed_compatible=bool(solver_candidate.get("corridor_seed_compatible")),
                export_compatible=bool(solver_candidate.get("export_compatible")),
            )
        )

    if bool(out.get("post_s3_k_floor_applied", False)):
        candidates.append(
            _build_post_s3_candidate(
                candidate_id="k_floor_retained",
                label="k_floor_enforced",
                origin="k_floor",
                rmse=out.get("post_s3_k_floor_rmse_after", solver_candidate.get("rmse")),
                n_lam=solver_payload.get("n_lam"),
                k_lam=solver_payload.get("k_lam"),
                d_nm=solver_payload.get("d_nm"),
                selection_eligible=False,
                corridor_base_mode="solver",
                decision_reason="diagnostic stage marker: k_floor physically constrained the retained solver baseline.",
                corridor_seed_compatible=bool(solver_candidate.get("corridor_seed_compatible")),
                export_compatible=bool(solver_candidate.get("export_compatible")),
            )
        )

    return candidates


def _select_final_scientific_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:

    eligible = [
        cand
        for cand in candidates
        if bool(cand.get("selection_eligible")) and bool(cand.get("physical_valid")) and cand.get("rmse") is not None
    ]

    selected = min(eligible, key=lambda cand: float(cand["rmse"])) if eligible else None

    ordered = sorted(eligible, key=lambda cand: float(cand["rmse"])) if eligible else []

    rank_by_id = {str(cand["id"]): idx + 1 for idx, cand in enumerate(ordered)}

    for cand in candidates:
        cand["selection_rank"] = rank_by_id.get(str(cand.get("id")))

        if selected is None:
            cand["selection_status"] = "ineligible" if not bool(cand.get("selection_eligible")) else "unresolved"

            if not bool(cand.get("selection_eligible")):
                continue

            cand["decision_reason"] = "no eligible scientific candidate could be selected."

            continue

        if str(cand.get("id")) == str(selected.get("id")):
            cand["selection_status"] = "selected"

            cand["decision_reason"] = "lowest eligible scientific RMSE among post-S3 candidates."

            continue

        if not bool(cand.get("selection_eligible")):
            cand["selection_status"] = "ineligible"

            continue

        if not bool(cand.get("physical_valid")):
            cand["selection_status"] = "invalid"

            cand["decision_reason"] = "candidate payload is incomplete or not physically valid."

            continue

        cand["selection_status"] = "not_selected"

        cand["decision_reason"] = (
            f"higher RMSE than selected candidate {selected['id']} "
            f"({float(cand['rmse']):.8f} vs {float(selected['rmse']):.8f})."
        )

    return None if selected is None else dict(selected)


def extract_nominal_best_polished_corridor_reference(out: dict[str, Any]) -> dict[str, Any] | None:
    """Extracts the spectral model designated "best" for the scientific corridor.

    Aligned with ``spectral_rmse_best_label`` / ``spectral_rmse_best_value`` (see

    ``_finalize_spectral_rmse_mesh_polish_and_best``). Étendre ici si d’autres labels

    (e.g., PWL sigma) return to the RMSE synthesis.

    Retourne ``None`` si aucun best défini ou données incomplètes.

    """

    label = out.get("spectral_rmse_best_label")

    rs = out.get("spectral_rmse_best_value")

    if label is None or rs is None:
        return None

    try:
        rmse_best = float(rs)

    except (TypeError, ValueError):
        return None

    if not np.isfinite(rmse_best):
        return None

    label_s = str(label)

    lam = np.asarray(out.get("lam_nm"), dtype=np.float64).ravel()

    if label_s == "Spline_cubique_sigma":
        if "n_lam_seg_spline_sigma" not in out or "k_lam_seg_spline_sigma" not in out:
            return None

        n_l = np.asarray(out["n_lam_seg_spline_sigma"], dtype=np.float64).ravel()

        k_l = np.asarray(out["k_lam_seg_spline_sigma"], dtype=np.float64).ravel()

        if lam.size and (n_l.size != lam.size or k_l.size != lam.size):
            return None

        d_raw = out.get("d_nm_seg_spline_sigma", out.get("d_nm"))

        if d_raw is None:
            return None

        try:
            d_nm = float(d_raw)

        except (TypeError, ValueError):
            return None

        if not np.isfinite(d_nm):
            return None

        sk = np.asarray(out.get("sigma_knots"), dtype=np.float64).ravel()

        xs = out.get("x_seg_spline_sigma")

        return {
            "label": label_s,
            "rmse_best": float(rmse_best),
            "lam_nm": lam.copy() if lam.size else lam,
            "n_lam": n_l.copy(),
            "k_lam": k_l.copy(),
            "d_nm": d_nm,
            "sigma_knots": sk.copy() if sk.size else sk,
            "x_seg_spline_sigma": None if xs is None else np.asarray(xs, dtype=np.float64).copy(),
        }

    return None
