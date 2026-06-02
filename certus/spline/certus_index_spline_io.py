#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I/O and serialization utilities for CERTUS-INDEX-SPLINE.
Extracted from certus_index_spline_core to decouple mathematical kernels from formatting logic.
"""

from __future__ import annotations
import numpy as np

def export_spline_result_jsonable(r: dict, *, full_arrays: bool = True, embed_child_stages: bool = True) -> dict:
    """JSON-serializable structure (lists instead of ndarrays)."""

    def _arr(x):

        if x is None:
            return None

        return np.asarray(x, dtype=np.float64).tolist()

    n_mono = r.get("n_mono_band_nm")

    slim = {
        "mse": float(r.get("mse", 0.0)),
        "rmse": float(r.get("rmse", 0.0)),
        "d_nm": float(r.get("d_nm", 0.0)),
        "n_seg": int(r.get("n_seg", 0)),
        "K": int(np.asarray(r.get("sigma_knots", [])).size),
        "nfev_pglobal": int(r.get("nfev_pglobal", 0)),
        "nit_polish": int(r.get("nit_polish", 0)),
        "t_is_ratio": bool(r.get("t_is_ratio", False)),
        "adaptive_mesh": bool(r.get("adaptive_mesh", False)),
        "continuous_model": bool(r.get("continuous_model", False)),
        "x_encoding": r.get("x_encoding"),
        "n_mono_band_nm": (
            [float(n_mono[0]), float(n_mono[1])]
            if n_mono is not None
            else None
        ),
    }

    rfw = r.get("rmse_fit_lambda_nm")

    if rfw is not None:
        slim["rmse_fit_lambda_nm"] = [float(rfw[0]), float(rfw[1])]

    pwl_bl = r.get("pwl_baseline_mse")

    if pwl_bl is not None:
        slim["pwl_baseline_mse"] = float(pwl_bl)

    nkpi = r.get("nk_profile_interp")

    if nkpi is not None:
        slim["nk_profile_interp"] = str(nkpi)

    for _k in (
        "spectral_rmse_segments",
        "spectral_rmse_seg_spline_sigma",
        "spectral_rmse_best_value",
    ):
        v = r.get(_k)

        if v is not None and np.isfinite(float(v)):
            slim[_k] = float(v)

    if r.get("spectral_rmse_best_label") is not None:
        slim["spectral_rmse_best_label"] = str(r["spectral_rmse_best_label"])

    for _nk in (
        "nl_alpha_opt",
        "nl_rmse_vs_meas_orig",
        "nl_rmse_vs_meas_scaled",
        "nl_rmse_reference_best",
    ):
        v = r.get(_nk)

        if v is not None:
            try:
                fv = float(v)

            except (TypeError, ValueError):
                continue

            if np.isfinite(fv):
                slim[_nk] = fv

    if r.get("nl_profile_mode") is not None:
        slim["nl_profile_mode"] = str(r["nl_profile_mode"])

    if r.get("nl_optim_ok") is not None:
        slim["nl_optim_ok"] = bool(r["nl_optim_ok"])

    if r.get("nl_second_pass_applied") is not None:
        slim["nl_second_pass_applied"] = bool(r["nl_second_pass_applied"])

    if r.get("nl_alpha_grid_n") is not None:
        try:
            slim["nl_alpha_grid_n"] = int(r["nl_alpha_grid_n"])

        except (TypeError, ValueError):
            pass

    if r.get("nl_alpha_grid_step") is not None:
        try:
            gfs = float(r["nl_alpha_grid_step"])

            if np.isfinite(gfs):
                slim["nl_alpha_grid_step"] = gfs

        except (TypeError, ValueError):
            pass

    if r.get("nl_alpha_budget_mode") is not None:
        slim["nl_alpha_budget_mode"] = str(r["nl_alpha_budget_mode"])

    if r.get("nl_second_pass_maxfun") is not None:
        try:
            slim["nl_second_pass_maxfun"] = int(r["nl_second_pass_maxfun"])

        except (TypeError, ValueError):
            pass

    if r.get("d_nm_nl") is not None:
        try:
            dnl = float(r["d_nm_nl"])

            if np.isfinite(dnl):
                slim["d_nm_nl"] = dnl

        except (TypeError, ValueError):
            pass

    out = dict(slim)

    st_all = r.get("auto_knot_stages")

    if st_all:
        ib = r.get("auto_knot_best_stage_index")

        if ib is not None:
            out["auto_knot_best_stage_index"] = int(ib)

        kb = r.get("auto_knots_K_best")

        if kb is not None:
            out["auto_knots_K_best"] = int(kb)

        out["auto_knots_K_last"] = int(np.asarray(st_all[-1]["sigma_knots"]).size)

    if full_arrays:
        out["x"] = _arr(r.get("x"))

        out["sigma_knots"] = _arr(r.get("sigma_knots"))

        out["lam_nm"] = _arr(r.get("lam_nm"))

        out["n_lam"] = _arr(r.get("n_lam"))

        out["k_lam"] = _arr(r.get("k_lam"))

        if r.get("ln_k_lam") is not None:
            out["ln_k_lam"] = _arr(r.get("ln_k_lam"))

        out["t_theo"] = _arr(r.get("t_theo"))

        out["r_theo"] = _arr(r.get("r_theo"))

        if r.get("nl_lam_nm") is not None:
            out["nl_lam_nm"] = _arr(r.get("nl_lam_nm"))

        if r.get("n_lam_nl") is not None:
            out["n_lam_nl"] = _arr(r.get("n_lam_nl"))

        if r.get("k_lam_nl") is not None:
            out["k_lam_nl"] = _arr(r.get("k_lam_nl"))

        if r.get("n_nodes_physical") is not None:
            out["n_nodes_physical"] = _arr(r.get("n_nodes_physical"))

    if embed_child_stages:
        st = r.get("auto_knot_stages")

        if st:
            out["stages"] = [export_spline_result_jsonable(s, full_arrays=True, embed_child_stages=False) for s in st]

    if r.get("smart_mesh"):
        out["smart_mesh"] = r["smart_mesh"]

    return out
