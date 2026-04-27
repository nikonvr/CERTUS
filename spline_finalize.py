#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""Spline pipeline finalization: spectral polish on sigma mesh (cubic spline between knots)."""


from __future__ import annotations


import logging


import time


from threading import Event


from typing import Any, Callable


import numpy as np


from scipy.optimize import minimize


from certus_index_utils import (

    _ratio_theoretical_from_nk,

    _reflectance_ratio_theoretical_from_nk,


)


from certus_physics import (

    calculate_transmission_array,

    clip_to_bounds,


)


from certus_index_spline_core import (

    NUMERICAL_FAULT_EXCEPTIONS,

    SplineOptConfig,

    _canonical_knots_min_lambda_kw,

    canonical_spline_sigma_knots,

    _log_spline_pipeline_json,

    _reflectance_absolute_backside_from_nk,


)


from spline_objective import (

    build_spline_objective_masked_grid,

    nk_from_x_pwlnk,

    spectral_mse_rmse_masked_from_nk,

    spline_objective_mse_on_masked_grid,


)


def _log_skipped_knot_insertion_fixed_mesh(

    cfg: SplineOptConfig,

    base_result: dict,

    stop_event: Event,

    progress_cb,

    live_cb=None,


) -> None:

    """Knot insertion post-SOL3b: disabled - logs effective K and RMSE (fixed sigma mesh)."""

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

    mode_label = (

        "cubic spline (not-a-knot) in sigma between nodes if K>=4, otherwise linear in sigma"

    )

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

    try:

        res = minimize(

            _obj_progress,

            x0,

            method="L-BFGS-B",

            jac=None,

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

    mse_r, rmse_r = spectral_mse_rmse_masked_from_nk(

        cfg, out, lam_full, n_full, k_full, d_best

    )

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

    """Remplit ``spectral_rmse_best_label`` / ``spectral_rmse_best_value`` (polish maillage spline cubique sigma uniquement)."""

    log = logging.getLogger("CERTUS")

    labels_en = {

        "Spline_cubique_sigma": "Mesh + cubic spline interpolation in sigma (L-BFGS-B polish on d and nodes)",

    }

    cand: list[tuple[str, float]] = []

    rs = out.get("spectral_rmse_seg_spline_sigma")

    if rs is not None and np.isfinite(float(rs)):

        cand.append(("Spline_cubique_sigma", float(rs)))

    rseg = out.get("spectral_rmse_segments")

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

        log.info(

            "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] No polished RMSE available - no 'best' to determine "

            "(sigma mesh polish disabled or failed)."

        )

        return

    best = min(cand, key=lambda t: t[1])

    out["spectral_rmse_best_label"] = best[0]

    out["spectral_rmse_best_value"] = float(best[1])

    log.info(

        "INDEX_SPLINE [SPECTRAL RMSE SYNTHESIS] -> Mesh polish model (excluding solver ref only): "

        "%s = %.8f - %s",

        best[0],

        float(best[1]),

        labels_en.get(best[0], best[0]),

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


