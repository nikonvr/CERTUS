#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""Spline Smart Init: spectral preview, manual sigma grids, n/L/d sweep."""


from __future__ import annotations


import logging


import time


from dataclasses import replace


from typing import Any


import numpy as np


from scipy.optimize import minimize_scalar


from certus_core import K_MAX_LIMIT, N_MAX_LIMIT, N_MIN_LIMIT


from certus_index_utils import _ratio_theoretical_from_nk


from certus_physics import calculate_T_substrate_array, calculate_transmission_array


from certus_index_spline_core import (

    DataType,

    NUMERICAL_FAULT_EXCEPTIONS,

    SplineOptConfig,

    L_LNK_MIN_PHYS,

    _to_fraction_T,


)


from spline_objective import (

    SplinePWLObjective,

    nk_from_x_pwlnk,

    physical_nodes_to_x_slice_n,

    spectral_rmse_weights,

    x_slice_n_to_physical_nodes,

    _spline_objective_lam_mask,


)


def _build_smart_preview_grids(cfg: SplineOptConfig) -> dict[str, Any] | None:

    if cfg.t_exp is None or float(cfg.weight_t) <= 0.0:

        return None

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    mask = _spline_objective_lam_mask(cfg)

    lam_f = lam[mask]

    if lam_f.size < 3:

        return None

    n_sub_f = np.asarray(cfg.n_sub, dtype=np.float64).ravel()[mask]

    t_exp_f = _to_fraction_T(np.asarray(cfg.t_exp, dtype=np.float64).ravel()[mask])

    k_hi = float(min(max(cfg.k_clip_hi, cfg.k_clip_lo * 1.0001), float(K_MAX_LIMIT)))

    L_lo = float(max(np.log(max(cfg.k_clip_lo, 1e-30)), L_LNK_MIN_PHYS))

    L_hi = float(np.log(k_hi))

    w_t = spectral_rmse_weights(lam_f).astype(np.float64, copy=False)

    inv_npix = 1.0 / max(int(lam_f.size), 1)

    t_sub_cache = None

    if cfg.t_is_ratio and float(cfg.weight_t) > 0.0:

        t_sub_cache = np.asarray(

            calculate_T_substrate_array(lam_f, n_sub_f), dtype=np.float64

        )

    sig_f = 1.0 / np.maximum(lam_f, 1e-9)

    return {

        "lam_f": lam_f,

        "t_exp_f": t_exp_f,

        "n_sub_f": n_sub_f,

        "w_t": w_t,

        "inv_npix": inv_npix,

        "sig_f": sig_f,

        "t_sub_cache": t_sub_cache,

        "L_lo": L_lo,

        "L_hi": L_hi,

    }


def smart_preview_append_sigma_mid_between_two_longest_lambda(sk: np.ndarray) -> np.ndarray:

    """11th knot: midpoint in sigma=1/lambda between the longest lambda and the second-to-last (Cauchy grid at 10)."""

    sk = np.asarray(sk, dtype=np.float64).ravel()

    if sk.size < 2:

        return sk.copy()

    lam = 1.0 / np.maximum(sk, 1e-30)

    ord_l = np.argsort(lam)

    s_prev = float(sk[int(ord_l[-2])])

    s_last = float(sk[int(ord_l[-1])])

    s_mid = 0.5 * (s_prev + s_last)

    sk_ext = np.append(sk, s_mid)

    sk_u = np.unique(np.sort(sk_ext))

    if sk_u.size == sk.size:

        span = float(max(np.max(sk), 1e-18) - min(np.min(sk), np.max(sk)))

        s_mid = float(s_mid + max(1e-14, 1e-8 * span))

        sk_u = np.unique(np.sort(np.append(sk, s_mid)))

    return sk_u.astype(np.float64, copy=False)


def build_smart_manual_sigma_knots_from_preview_grid(

    sig_f: np.ndarray,

    *,

    n_uniform_in_sigma2: int = 11,


) -> np.ndarray:

    """sigma nodes for Smart Init manual mode: uniform in sigma² over the interval covered by ``sig_f``.

    ``sig_f`` is typically ``grids['sig_f']`` (objective lambda points, thus already truncated if RMSE window is active).

    Same logic as ``compute_smart_init_spectral_preview(..., uniform_sigma_nodes=...)``.

    """

    sig_f = np.asarray(sig_f, dtype=np.float64).ravel()

    if int(sig_f.size) < 2:

        raise ValueError("build_smart_manual_sigma_knots_from_preview_grid: sig_f must have at least 2 points")

    s_lo, s_hi = float(np.min(sig_f)), float(np.max(sig_f))

    u_lo, u_hi = float(s_lo * s_lo), float(s_hi * s_hi)

    if u_lo > u_hi:

        u_lo, u_hi = u_hi, u_lo

    nu = int(max(2, n_uniform_in_sigma2))

    u_grid = np.linspace(u_lo, u_hi, nu, dtype=np.float64)

    sk = np.sqrt(np.maximum(u_grid, 0.0))

    return smart_preview_append_sigma_mid_between_two_longest_lambda(sk)


def interp_n_L_pwlnk_to_sigmas(

    sigma_knots_src: np.ndarray,

    n_physical_src: np.ndarray,

    L_src: np.ndarray,

    sigma_tgt: np.ndarray,

    *,

    diag_log: logging.Logger | None = None,

    diag_tag: str = "REGRID_SIGMA",


) -> tuple[np.ndarray, np.ndarray]:

    """Maps search (n, L) in sigma from source knots onto ``sigma_tgt``.

    - If a target sigma coincides (within tolerance) with a source node: **exact copy** of n and ln k

      (no floating point interpolation error) - useful when **adding** canonical IR/UV nodes.

    - Between two sources: linear interpolation in sigma (same polygon as source PWL).

    - Beyond the source sigma interval: **linear extrapolation** of the last PWL segment

      (instead of ``np.interp`` plateau), to avoid artificially 'freezing' the edge.

    If ``diag_log`` is provided: logs each target node (snap / interp / extrap_lo / extrap_hi mode),

    the deviation compared to a **plateau** ``np.interp`` at the edges (previous behavior), and a summary.

    """

    sk = np.asarray(sigma_knots_src, dtype=np.float64).ravel()

    sn = np.asarray(n_physical_src, dtype=np.float64).ravel()

    sL = np.asarray(L_src, dtype=np.float64).ravel()

    if sk.size != sn.size or sk.size != sL.size:

        raise ValueError("sigma_knots_src, n_physical_src, L_src: inconsistent sizes")

    order = np.argsort(sk)

    sk_s = sk[order]

    sn_s = sn[order]

    sL_s = sL[order]

    sig_t = np.asarray(sigma_tgt, dtype=np.float64).ravel()

    n_out = np.empty(sig_t.shape, dtype=np.float64)

    L_out = np.empty(sig_t.shape, dtype=np.float64)

    s0 = float(sk_s[0])

    s1m = float(sk_s[-1])

    lam_src_lo = 1.0 / max(s1m, 1e-30)

    lam_src_hi = 1.0 / max(s0, 1e-30)

    cnt_snap = cnt_interp = cnt_exlo = cnt_exhi = cnt_exlo_flat = cnt_exhi_flat = 0

    max_dn_c = max_dL_c = 0.0

    if diag_log is not None:

        diag_log.info(

            "%s | ENTER re-gridding (linear in sigma between source nodes)  K_src=%d  "

            "sigma_src[min,max]=[%.8e,%.8e] nm^-1  lambda_src~[%.2f, %.2f] nm  ->  K_tgt=%d",

            diag_tag,

            int(sk_s.size),

            s0,

            s1m,

            lam_src_lo,

            lam_src_hi,

            int(sig_t.size),

        )

    n_const = np.interp(sig_t, sk_s, sn_s, left=float(sn_s[0]), right=float(sn_s[-1]))
    L_const = np.interp(sig_t, sk_s, sL_s, left=float(sL_s[0]), right=float(sL_s[-1]))
    n_out[:] = n_const
    L_out[:] = L_const

    idx = np.searchsorted(sk_s, sig_t, side="left")
    c0 = np.clip(idx - 1, 0, sk_s.size - 1)
    c1 = np.clip(idx, 0, sk_s.size - 1)
    d0 = np.abs(sig_t - sk_s[c0])
    d1 = np.abs(sig_t - sk_s[c1])
    choose_1 = d1 < d0
    j_arr = np.where(choose_1, c1, c0)
    dmin = np.where(choose_1, d1, d0)
    tol = 1e-14 + 1e-9 * np.maximum.reduce([np.abs(sig_t), np.abs(sk_s[j_arr]), np.full(sig_t.shape, 1e-30)])
    mask_snap = dmin <= tol

    if np.any(mask_snap):
        n_out[mask_snap] = sn_s[j_arr[mask_snap]]
        L_out[mask_snap] = sL_s[j_arr[mask_snap]]

    mode_arr = np.full(sig_t.shape, "interp", dtype=object)
    mode_arr[mask_snap] = "snap"

    mask_lo = (~mask_snap) & (sig_t <= s0)
    mask_hi = (~mask_snap) & (sig_t >= s1m)

    if sk_s.size >= 2:
        den_lo = float(sk_s[1] - sk_s[0])
        if abs(den_lo) < 1e-30:
            if np.any(mask_lo):
                n_out[mask_lo] = float(sn_s[0])
                L_out[mask_lo] = float(sL_s[0])
                mode_arr[mask_lo] = "extrap_lo_flat"
        else:
            if np.any(mask_lo):
                t_lo = (sig_t[mask_lo] - s0) / den_lo
                n_out[mask_lo] = sn_s[0] + t_lo * (sn_s[1] - sn_s[0])
                L_out[mask_lo] = sL_s[0] + t_lo * (sL_s[1] - sL_s[0])
                mode_arr[mask_lo] = "extrap_lo"

        den_hi = float(sk_s[-1] - sk_s[-2])
        if abs(den_hi) < 1e-30:
            if np.any(mask_hi):
                n_out[mask_hi] = float(sn_s[-1])
                L_out[mask_hi] = float(sL_s[-1])
                mode_arr[mask_hi] = "extrap_hi_flat"
        else:
            if np.any(mask_hi):
                t_hi = (sig_t[mask_hi] - s1m) / den_hi
                n_out[mask_hi] = sn_s[-1] + t_hi * (sn_s[-1] - sn_s[-2])
                L_out[mask_hi] = sL_s[-1] + t_hi * (sL_s[-1] - sL_s[-2])
                mode_arr[mask_hi] = "extrap_hi"
    else:
        if np.any(mask_lo):
            n_out[mask_lo] = float(sn_s[0])
            L_out[mask_lo] = float(sL_s[0])
            mode_arr[mask_lo] = "extrap_lo_flat"
        if np.any(mask_hi):
            n_out[mask_hi] = float(sn_s[-1])
            L_out[mask_hi] = float(sL_s[-1])
            mode_arr[mask_hi] = "extrap_hi_flat"

    dn_all = n_out - n_const
    dL_all = L_out - L_const
    max_dn_c = float(np.max(np.abs(dn_all))) if dn_all.size else 0.0
    max_dL_c = float(np.max(np.abs(dL_all))) if dL_all.size else 0.0

    cnt_snap = int(np.sum(mode_arr == "snap"))
    cnt_interp = int(np.sum(mode_arr == "interp"))
    cnt_exlo = int(np.sum(mode_arr == "extrap_lo"))
    cnt_exhi = int(np.sum(mode_arr == "extrap_hi"))
    cnt_exlo_flat = int(np.sum(mode_arr == "extrap_lo_flat"))
    cnt_exhi_flat = int(np.sum(mode_arr == "extrap_hi_flat"))

    if diag_log is not None:
        for i in range(int(sig_t.size)):
            s = float(sig_t[i])
            lam_nm = 1.0 / max(s, 1e-30)
            mode = str(mode_arr[i])
            j = int(j_arr[i])
            j_note = f"j={j} d_sigma={float(dmin[i]):.3e}" if mode == "snap" else "-"
            dn_c = float(dn_all[i])
            dL_c = float(dL_all[i])
            diag_log.info(
                "%s | tgt %2d/%d  lambda=%10.4f nm  sigma=%.8e nm^-1 | %-16s %-22s | "
                "n=%.8f ln_k=%.6f | vs_plateau(np.interp) d_n=%+.4e d_ln_k=%+.4e",
                diag_tag,
                i + 1,
                int(sig_t.size),
                lam_nm,
                s,
                mode,
                j_note,
                float(n_out[i]),
                float(L_out[i]),
                dn_c,
                dL_c,
            )

    if diag_log is not None:

        diag_log.info(

            "%s | SMART INIT: snap=%d interp=%d extrap_lo=%d extrap_hi=%d | "

            "max|d_n|_vs_plateau=%.4e max|d_ln_k|_vs_plateau=%.4e",

            diag_tag,

            cnt_snap,

            cnt_interp,

            cnt_exlo,

            cnt_exhi,

            max_dn_c,

            max_dL_c,

        )

        diag_log.info(

            "%s | SMART GUIDANCE: If you see large 'extrap_lo' or 'extrap_hi', the initial UI grid is smaller than the target spectral window. "

            "This degrades initial RMSE. Consider generating your starting mesh using a wider spectral window if possible.",

            diag_tag,

        )

        sig_min_t = float(np.min(sig_t))

        sig_max_t = float(np.max(sig_t))

        lam_tgt_long = 1.0 / max(sig_min_t, 1e-30)

        lam_tgt_short = 1.0 / max(sig_max_t, 1e-30)

        gap_ir = lam_tgt_long - lam_src_hi

        diag_log.info(

            "%s | MESH ALIGNMENT (K_src %d -> K_tgt %d) | UI Max Wavelength: %.2f nm | Target Canonical Grid Wavelength: %.2f nm | Gap: %.2f nm",

            diag_tag,

            int(sk_s.size),

            int(sig_t.size),

            lam_src_hi,

            lam_tgt_long,

            max(0.0, gap_ir),

        )

        if gap_ir > 50.0 or int(sk_s.size) != int(sig_t.size):

            diag_log.info(

                "%s | ACTION: Your initial knots (K=%d) do not precisely align with the final solver knots (K=%d). "

                "This geometry mismatch artificially penalizes the startup RMSE. Avoid trimming the active lambda range "

                "in your UI if you want native 1:1 RMSE matching between the preview and the final solver.",

                diag_tag,

                int(sk_s.size),

                int(sig_t.size)

            )

    return n_out, L_out


def _finalize_smart_preview_from_nodes(

    cfg: SplineOptConfig,

    sk: np.ndarray,

    n_phys: np.ndarray,

    L_at_nodes: np.ndarray,

    grids: dict[str, Any],

    *,

    d_scan_points: int = 96,

    d_nm_fixed: float | None = None,

    relax_n_mono: bool = False,


) -> dict[str, Any] | None:

    sk = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk.size)

    sn = np.asarray(n_phys, dtype=np.float64).ravel()

    sL = np.asarray(L_at_nodes, dtype=np.float64).ravel()

    if sn.size != k or sL.size != k:

        return None

    L_lo = float(grids["L_lo"])

    L_hi = float(grids["L_hi"])

    relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

    # Smart Init manual: free physical n (no isotone projection -> ξ) as long as relax_eff is True.

    if cfg.n_mono_band_nm is None or relax_eff:

        n_slice = np.clip(sn, N_MIN_LIMIT, N_MAX_LIMIT)

    else:

        n_slice = physical_nodes_to_x_slice_n(sn, sk, cfg.n_mono_band_nm)

    L_slice = np.clip(sL, L_lo, L_hi)

    nm_eval = None if (relax_eff or cfg.n_mono_band_nm is None) else cfg.n_mono_band_nm

    lam_f = grids["lam_f"]

    t_exp_f = grids["t_exp_f"]

    n_sub_f = grids["n_sub_f"]

    w_t = grids["w_t"]

    inv_npix = float(grids["inv_npix"])

    sig_f = grids["sig_f"]

    t_sub_cache = grids["t_sub_cache"]

    d_lo, d_hi = float(cfg.d_lo), float(cfg.d_hi)

    if d_hi <= d_lo:

        d_hi = d_lo + 1.0

    use_combined_d = (

        cfg.data_type == DataType.BOTH

        and float(cfg.weight_t) > 0.0

        and float(cfg.weight_r) > 0.0

        and cfg.r_exp is not None

        and cfg.t_exp is not None

    )

    def _eval_d_mse_and_t(dv: float) -> tuple[float, np.ndarray]:

        dv = float(dv)

        x = np.concatenate((np.asarray([dv], dtype=np.float64), n_slice, L_slice))

        n_l, k_l = nk_from_x_pwlnk(

            x,

            lam_f,

            sk,

            cfg.k_clip_lo,

            cfg.k_clip_hi,

            sig_pre=sig_f,

            n_mono_band_nm=nm_eval,

            profile_interp=cfg.nk_profile_interp,

        )

        if cfg.t_is_ratio and t_sub_cache is not None:

            t_th = _ratio_theoretical_from_nk(lam_f, n_l, k_l, n_sub_f, dv)

        else:

            t_th = calculate_transmission_array(lam_f, n_l, k_l, dv, n_sub_f)

        e = t_exp_f - t_th

        mse = float(np.dot(w_t, e * e)) * inv_npix

        return mse, np.asarray(t_th, dtype=np.float64).copy()

    cfg_obj = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

    obj_combined: SplinePWLObjective | None = (

        SplinePWLObjective(cfg_obj, sk) if use_combined_d else None

    )

    def _eval_d_same_as_optimizer(dv: float) -> tuple[float, np.ndarray]:

        """Same scalar as ``SplinePWLObjective`` (weighted T+R) + T_th for plotting."""

        assert obj_combined is not None

        dv = float(dv)

        x = np.concatenate((np.asarray([dv], dtype=np.float64), n_slice, L_slice))

        mse_full = float(obj_combined(x))

        n_l, k_l = nk_from_x_pwlnk(

            x,

            lam_f,

            sk,

            cfg.k_clip_lo,

            cfg.k_clip_hi,

            sig_pre=sig_f,

            n_mono_band_nm=nm_eval,

            profile_interp=cfg.nk_profile_interp,

        )

        if cfg.t_is_ratio and t_sub_cache is not None:

            t_th = _ratio_theoretical_from_nk(lam_f, n_l, k_l, n_sub_f, dv)

        else:

            t_th = calculate_transmission_array(lam_f, n_l, k_l, dv, n_sub_f)

        return mse_full, np.asarray(t_th, dtype=np.float64).copy()

    _eval_d = _eval_d_same_as_optimizer if use_combined_d else _eval_d_mse_and_t

    if d_nm_fixed is not None and np.isfinite(float(d_nm_fixed)):

        best_d = float(np.clip(float(d_nm_fixed), d_lo, d_hi))

        best_mse, best_t_th = _eval_d(best_d)

    else:

        d_mid = 0.5 * (d_lo + d_hi)

        try:

            sol = minimize_scalar(

                lambda u: _eval_d(u)[0],

                bounds=(d_lo, d_hi),

                method="bounded",

                options={"maxiter": int(max(30, d_scan_points))},

            )

            if np.isfinite(sol.fun) and np.isfinite(sol.x):

                best_d = float(np.clip(float(sol.x), d_lo, d_hi))

                best_mse, best_t_th = _eval_d(best_d)

            else:

                raise RuntimeError("minimize_scalar invalid result")

        except NUMERICAL_FAULT_EXCEPTIONS:

            logging.getLogger("CERTUS").debug(

                "minimize_scalar failed in _finalize_smart_preview_from_nodes, falling back to grid scan",

                exc_info=True,

            )

            best_d = float(d_mid)

            best_mse, best_t_th = _eval_d(best_d)

            d_grid = np.linspace(d_lo, d_hi, int(max(2, d_scan_points)), dtype=np.float64)

            for d in d_grid:

                mse, t_th = _eval_d(float(d))

                if mse < best_mse:

                    best_mse = mse

                    best_d = float(d)

                    best_t_th = t_th

    assert best_t_th is not None

    lam_knots = np.sort(1.0 / np.maximum(sk, 1e-30))

    rmse_w = float(np.sqrt(max(best_mse, 0.0)))

    if relax_eff or cfg.n_mono_band_nm is None:

        n_phys_out = np.clip(n_slice, N_MIN_LIMIT, N_MAX_LIMIT).copy()

    else:

        n_phys_out = x_slice_n_to_physical_nodes(n_slice, sk, cfg.n_mono_band_nm)

    # Calculation of n(lambda) and k(lambda) on the full spectral grid for Live Monitoring

    x_best = np.concatenate((np.asarray([best_d], dtype=np.float64), n_slice, L_slice))

    n_lam_full, k_lam_full = nk_from_x_pwlnk(

        x_best,

        lam_f,

        sk,

        cfg.k_clip_lo,

        cfg.k_clip_hi,

        sig_pre=sig_f,

        n_mono_band_nm=nm_eval,

        profile_interp=cfg.nk_profile_interp,

    )

    return {

        "lam_nm": lam_f.copy(),

        "t_exp": t_exp_f.copy(),

        "t_theo": best_t_th,

        "d_best_nm": best_d,

        "weighted_rmse": rmse_w,

        "weighted_mse": float(best_mse),

        "lambda_knots_nm": lam_knots,

        "t_is_ratio": bool(cfg.t_is_ratio),

        "n_nodes_physical": np.asarray(n_phys_out, dtype=np.float64).copy(),

        "L_nodes": np.asarray(L_slice, dtype=np.float64).copy(),

        "sigma_knots": sk.copy(),

        "preview_grids": grids,

        "cfg": cfg,

        "n_lam": np.asarray(n_lam_full, dtype=np.float64).copy(),

        "k_lam": np.asarray(k_lam_full, dtype=np.float64).copy(),

    }


def compute_smart_init_spectral_preview(

    cfg: SplineOptConfig,

    sigma_knots: np.ndarray,

    smart_n_physical: np.ndarray,

    smart_L: np.ndarray,

    *,

    d_scan_points: int = 96,

    uniform_sigma_nodes: int | None = None,


) -> dict[str, Any] | None:

    """Transmission (or ratio) spectrum: piecewise linear n(sigma) and L=ln k(sigma) between nodes (endpoints);

    only thickness d is adjusted by 1D minimization on [d_lo, d_hi]: weighted T MSE if T only,

    otherwise same combined T+R objective as ``SplinePWLObjective`` (wT, wR > 0).

    If ``uniform_sigma_nodes`` >= 2: **11** regular positions in **1/lambda²** (sigma²) over data,

    then **12th** knot at **sigma midpoint** between longest lambda and second-to-last among the 11;

    nominal n and L are interpolated from ``sigma_knots`` at the **12** abscissae.

    """

    grids = _build_smart_preview_grids(cfg)

    if grids is None:

        return None

    sk_in = np.asarray(sigma_knots, dtype=np.float64).ravel()

    sn = np.asarray(smart_n_physical, dtype=np.float64).ravel()

    sL = np.asarray(smart_L, dtype=np.float64).ravel()

    if sn.size != sk_in.size or sL.size != sk_in.size:

        return None

    if uniform_sigma_nodes is not None and int(uniform_sigma_nodes) >= 2:

        sig_f = grids["sig_f"]

        sk = build_smart_manual_sigma_knots_from_preview_grid(

            sig_f, n_uniform_in_sigma2=int(uniform_sigma_nodes)

        )

        sn, sL = interp_n_L_pwlnk_to_sigmas(sk_in, sn, sL, sk)

    else:

        sk = sk_in

    return _finalize_smart_preview_from_nodes(

        cfg, sk, sn, sL, grids, d_scan_points=d_scan_points

    )


def recalc_smart_init_spectral_preview(

    cfg: SplineOptConfig,

    sigma_knots: np.ndarray,

    n_physical_nodes: np.ndarray,

    L_nodes: np.ndarray,

    preview_grids: dict[str, Any],

    *,

    d_scan_points: int = 96,

    d_nm_fixed: float | None = None,

    relax_n_mono: bool = False,


) -> dict[str, Any] | None:

    """Same physics as ``compute_smart_init_spectral_preview`` with modified n, L at knots (fixed grids)."""

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    return _finalize_smart_preview_from_nodes(

        cfg,

        sk,

        np.asarray(n_physical_nodes, dtype=np.float64).ravel(),

        np.asarray(L_nodes, dtype=np.float64).ravel(),

        preview_grids,

        d_scan_points=d_scan_points,

        d_nm_fixed=d_nm_fixed,

        relax_n_mono=relax_n_mono,

    )


def guess_smart_x0_from_extrema(

    lam_nm: np.ndarray,

    t_exp: np.ndarray,

    n_sub: np.ndarray,

    d_est: float,

    sigma_knots: np.ndarray,


) -> tuple[np.ndarray | None, np.ndarray | None]:

    """

    Intelligent approach to initialize n and k (L) at K=5.

    Independent detection of extrema and Swanepoel Inversion.

    """

    from scipy.signal import find_peaks

    eps = 1e-12

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    t = _to_fraction_T(np.asarray(t_exp, dtype=np.float64).ravel())

    ns = np.asarray(n_sub, dtype=np.float64).ravel()

    n_pts = len(lam)

    # Finer smoothing window to avoid killing narrow fringes

    w = max(3, n_pts // 120)

    if w % 2 == 0:

        w += 1

    t_smooth = np.convolve(t, np.ones(w)/w, mode='same')

    dist = max(3, n_pts // 250)

    amp = float(np.nanpercentile(t_smooth, 95) - np.nanpercentile(t_smooth, 5))

    prom = max(1e-4, 0.02 * amp)

    idx_max_s, _ = find_peaks(t_smooth, prominence=prom, distance=dist)

    idx_min_s, _ = find_peaks(-t_smooth, prominence=prom, distance=dist)

    if len(idx_max_s) < 2 or len(idx_min_s) < 2:

        return None, None

    # Re-localization of the true peak on the raw signal (t) not squashed by smoothing

    idx_max = np.array([max(0, i - w) + int(np.argmax(t[max(0, i - w):min(n_pts, i + w)])) for i in idx_max_s])

    idx_min = np.array([max(0, i - w) + int(np.argmin(t[max(0, i - w):min(n_pts, i + w)])) for i in idx_min_s])

    idx_max = np.unique(np.clip(idx_max, 0, n_pts - 1))

    idx_min = np.unique(np.clip(idx_min, 0, n_pts - 1))

    t_top_full = np.interp(lam, lam[idx_max], t[idx_max], left=float(t[idx_max[0]]), right=float(t[idx_max[-1]]))

    t_bot_full = np.interp(lam, lam[idx_min], t[idx_min], left=float(t[idx_min[0]]), right=float(t[idx_min[-1]]))

    r_M = np.clip(t_top_full, eps, 2.0)

    r_m = np.clip(t_bot_full, eps, 2.0)

    t_nu = 2.0 * ns / (ns * ns + 1.0)

    N = 0.5 * (ns * ns + 1.0) * (1.0 + 2.0 * (r_M - r_m) / np.maximum(r_M * r_m, eps))

    inside = np.maximum(N * N - ns * ns, 0.0)

    n_swan = np.sqrt(np.maximum(N + np.sqrt(inside), eps))

    E = (8.0 * n_swan * n_swan * ns) / np.maximum(r_M * t_nu, eps) + (n_swan * n_swan - 1.0) * (n_swan * n_swan - ns * ns)

    A = (n_swan * n_swan - 1.0) ** 3 * (n_swan * n_swan - ns**4)

    disc = np.maximum(E * E - A, 0.0)

    root = np.sqrt(disc)

    den = (n_swan - 1.0) ** 3 * (n_swan - ns * ns)

    # avoid division by zero

    den = np.where(np.abs(den) < eps, eps, den)

    x1 = (E - root) / den

    x2 = (E + root) / den

    valid1 = np.isfinite(x1) & (x1 > 0.0) & (x1 < 1.0)

    valid2 = np.isfinite(x2) & (x2 > 0.0) & (x2 < 1.0)

    x_int = np.where(valid1, x1, np.where(valid2, x2, np.nan))

    x_int = np.clip(x_int, 1e-30, 0.999999)

    k_swan = -(lam / (4.0 * np.pi * max(d_est, 1e-9))) * np.log(x_int)

    m_n = np.isfinite(n_swan)

    if not np.any(m_n):

        return None, None

    n_swan_clean = np.interp(lam, lam[m_n], n_swan[m_n])

    m_k = np.isfinite(k_swan)

    if not np.any(m_k):

        return None, None

    k_swan_clean = np.interp(lam, lam[m_k], k_swan[m_k])

    lam_knots = 1.0 / np.maximum(sigma_knots, 1e-12)

    sort_idx = np.argsort(lam_knots)

    n_knots_sorted = np.interp(lam_knots[sort_idx], lam, n_swan_clean)

    k_knots_sorted = np.interp(lam_knots[sort_idx], lam, k_swan_clean)

    n_knots = np.zeros_like(sigma_knots)

    k_knots = np.zeros_like(sigma_knots)

    n_knots[sort_idx] = n_knots_sorted

    k_knots[sort_idx] = k_knots_sorted

    L_knots = np.log(np.clip(k_knots, 1e-12, 10.0))

    return n_knots, L_knots


def smart_init_sweep_node_thickness_rmse(

    cfg: SplineOptConfig,

    sigma_knots: np.ndarray,

    n_phys: np.ndarray,

    L_nodes: np.ndarray,

    row: int,

    *,

    is_ln_k: bool,

    d_lo: float,

    d_hi: float,

    L_lo: float,

    L_hi: float,

    time_budget_s: float = 2.9,

    grid_d: int = 20,

    grid_param: int = 20,

    d_nm_current: float | None = None,

    relax_n_mono: bool = False,


) -> dict[str, Any]:

    """

    2D sweep (thickness d × n or ln k at knot ``row``) minimizing RMSE via

    ``rmse_at_spline_stage_x0_init``; stops if it exceeds ``time_budget_s``.

    Never returns a state that **degrades** RMSE compared to the starting state:

    reference is always ``rmse_at_spline_stage_x0_init`` with current nodes and

    ``d_nm_current`` (manual slider) if provided, otherwise midpoint of ``[d_lo, d_hi]``.

    """

    from certus_index_spline_core import rmse_at_spline_stage_x0_init

    sk_a = np.asarray(sigma_knots, dtype=np.float64).ravel()

    n0b = np.asarray(n_phys, dtype=np.float64).ravel()

    L0b = np.asarray(L_nodes, dtype=np.float64).ravel()

    r = int(row)

    if r < 0 or r >= n0b.size or sk_a.size != n0b.size or L0b.size != n0b.size:

        raise ValueError(

            "smart_init_sweep_node_thickness_rmse: invalid sizes "

            f"(row={r}, K_sigma={sk_a.size}, len(n)={n0b.size}, len(L)={L0b.size})"

        )

    t_end = time.perf_counter() + max(0.05, float(time_budget_s))

    d_lo = float(d_lo)

    d_hi = float(d_hi)

    if d_hi <= d_lo:

        d_lo, d_hi = d_hi, d_lo

    n0 = float(n0b[r])

    L0 = float(L0b[r])

    if is_ln_k:

        # Scan ln k +/- 20% (relative to the current value L0)

        half = abs(L0) * 0.20

        p_lo = max(float(L_lo), L0 - half)

        p_hi = min(float(L_hi), L0 + half)

    else:

        # Scan n +/- 20% (relative to the current value n0)

        p_lo = max(float(N_MIN_LIMIT), n0 * 0.80)

        p_hi = min(float(N_MAX_LIMIT), n0 * 1.20)

    if p_hi <= p_lo + 1e-14:

        if is_ln_k:

            p_lo, p_hi = float(L_lo), float(L_hi)

        else:

            p_lo, p_hi = float(N_MIN_LIMIT), float(N_MAX_LIMIT)

    nd = int(max(6, min(28, grid_d)))

    npa = int(max(6, min(28, grid_param)))

    d_mid = 0.5 * (d_lo + d_hi)

    if d_nm_current is not None and np.isfinite(float(d_nm_current)):

        d_ref = float(np.clip(float(d_nm_current), d_lo, d_hi))

    else:

        d_ref = float(d_mid)

    # Reference RMSE = **actual** state before "auto" (same d as manual slider).

    try:

        _, rmse_init = rmse_at_spline_stage_x0_init(

            cfg, sk_a, n0b, L0b, d_ref, relax_n_mono=relax_n_mono

        )

    except (TypeError, ValueError, AttributeError, RuntimeError):

        logging.getLogger("CERTUS").debug(

            "rmse_at_spline_stage_x0_init failed for reference RMSE", exc_info=True

        )

        rmse_init = float("inf")

    rel_tol = (

        max(1e-12, abs(float(rmse_init)) * 1e-9)

        if np.isfinite(rmse_init)

        else 1e-12

    )

    def _rmse_of(dv: float, nw: np.ndarray, Lw: np.ndarray) -> float:

        try:

            _, rm = rmse_at_spline_stage_x0_init(

                cfg, sk_a, nw, Lw, float(dv), relax_n_mono=relax_n_mono

            )

            return float(rm)

        except (TypeError, ValueError, AttributeError, RuntimeError):

            return float("inf")

    # Initialization of 2D search via formal local minimization

    # Optimize d (index 0) and knot parameter r (index 1)

    def _obj_2d(p):

        dv = float(p[0])

        pv = float(p[1])

        n_w = n0b.copy()

        L_w = L0b.copy()

        if is_ln_k:

            L_w[r] = pv

        else:

            n_w[r] = pv

        try:

            _, rm = rmse_at_spline_stage_x0_init(

                cfg, sk_a, n_w, L_w, dv, relax_n_mono=relax_n_mono

            )

            return rm

        except (TypeError, ValueError, AttributeError, RuntimeError):

            return 1e30

    from scipy.optimize import minimize

    best_d = float(d_ref)

    best_n = n0b.copy()

    best_L = L0b.copy()

    best_rmse = float(rmse_init) if np.isfinite(rmse_init) else float("inf")

    res = minimize(

        _obj_2d,

        np.array([d_ref, L0 if is_ln_k else n0]),

        method="L-BFGS-B",

        bounds=[(d_lo, d_hi), (p_lo, p_hi)],

        options={"maxfun": 400, "ftol": 1e-6},

    )

    if res.success and getattr(res, "x", None) is not None:

        d_try = float(np.clip(float(res.x[0]), d_lo, d_hi))

        pv_try = float(np.clip(float(res.x[1]), p_lo, p_hi))

        n_try = n0b.copy()

        L_try = L0b.copy()

        if is_ln_k:

            L_try[r] = pv_try

        else:

            n_try[r] = pv_try

        rm_try = _rmse_of(d_try, n_try, L_try)

        # Systematic verification on the same scalar as manual display (not just res.fun).

        if np.isfinite(rm_try) and rm_try <= float(rmse_init) + rel_tol:

            best_d = d_try

            best_n = n_try

            best_L = L_try

            best_rmse = rm_try

    return {

        "d_nm": float(best_d),

        "n_nodes_physical": np.asarray(best_n, dtype=np.float64).copy(),

        "L_nodes": np.asarray(best_L, dtype=np.float64).copy(),

        "rmse": float(best_rmse),

    }


MANUAL_MATERIAL_PRESET_IDS: tuple[str, ...] = ("nb2o5", "sio2", "ta2o5")


def tune_d_and_rmse_for_manual_material_preset(

    cfg: SplineOptConfig,

    preset_id: str,

    target_sigma_knots: np.ndarray,

    *,

    d_nm_hint: float,

    relax_n_mono: bool,


) -> tuple[float, float, np.ndarray, np.ndarray]:

    """

    Projects a preset onto ``target_sigma_knots``, optimizes *d* in [d_lo, d_hi] to minimize

    the ``rmse_at_spline_stage_x0_init`` RMSE (same criterion as Smart Init dialog).

    """

    from certus_index_spline_core import rmse_at_spline_stage_x0_init

    from spline_presets import project_manual_material_preset

    sk_t = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()

    _, n_p, L_p, _dref = project_manual_material_preset(

        str(preset_id), sk_t, d_nm_hint=float(d_nm_hint)

    )

    def obj_d(dv: float) -> float:

        _, rm = rmse_at_spline_stage_x0_init(

            cfg, sk_t, n_p, L_p, float(dv), relax_n_mono=relax_n_mono

        )

        return float(rm)

    res = minimize_scalar(

        obj_d,

        bounds=(float(cfg.d_lo), float(cfg.d_hi)),

        method="bounded",

        options={"xatol": 0.01},

    )

    d_opt = float(res.x) if res.success else float(d_nm_hint)

    _, rmse = rmse_at_spline_stage_x0_init(

        cfg, sk_t, n_p, L_p, d_opt, relax_n_mono=relax_n_mono

    )

    if not np.isfinite(rmse):

        return float("inf"), d_opt, n_p.copy(), L_p.copy()

    return float(rmse), d_opt, n_p.copy(), L_p.copy()


def pick_best_manual_material_preset(

    cfg: SplineOptConfig,

    target_sigma_knots: np.ndarray,

    *,

    d_nm_hint: float,

    relax_n_mono: bool,

    preset_ids: tuple[str, ...] | None = None,


) -> tuple[str, float, float, np.ndarray, np.ndarray, list[tuple[str, float]]] | None:

    """

    Evaluates each preset on the same sigma grid (mini *d* optimization per preset), returns the best.

    Returns ``(preset_id, rmse, d_opt, n_nodes, L_nodes, sorted list (id, rmse) for logs)``.

    ``None`` if no preset produced a finite RMSE.

    """

    ids = preset_ids or MANUAL_MATERIAL_PRESET_IDS

    rows: list[tuple[str, float]] = []

    best_id: str | None = None

    best_rm = float("inf")

    best_d = float(d_nm_hint)

    best_n: np.ndarray | None = None

    best_L: np.ndarray | None = None

    for pid in ids:

        try:

            rm, d_o, n_p, L_p = tune_d_and_rmse_for_manual_material_preset(

                cfg,

                pid,

                target_sigma_knots,

                d_nm_hint=float(d_nm_hint),

                relax_n_mono=relax_n_mono,

            )

        except NUMERICAL_FAULT_EXCEPTIONS:

            logging.getLogger("CERTUS").debug(

                "tune_d_and_rmse_for_manual_material_preset failed for preset %s",

                pid, exc_info=True,

            )

            continue

        if not np.isfinite(rm):

            continue

        rows.append((str(pid), float(rm)))

        if rm < best_rm - 1e-18:

            best_rm = float(rm)

            best_d = float(d_o)

            best_n = n_p

            best_L = L_p

            best_id = str(pid)

    if best_id is None or best_n is None or best_L is None:

        return None

    rows.sort(key=lambda t: t[1])

    return best_id, best_rm, best_d, best_n, best_L, rows
