#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS-INDEX-SPLINE  Global fit of n(lambda), k(lambda) as piecewise-linear in sigma=1/lambda (ln k at nodes).


Standalone: no imports from CERTUS_INDEX nor certus_swanepool. PGlobal from certus_physics.


"""


from __future__ import annotations


import argparse


import json


import logging


import time


import multiprocessing


import os


import sys


from dataclasses import dataclass, replace, field


from typing import Any, Callable


from enum import Enum, auto


from threading import Event


import numpy as np


import pandas as pd


from scipy.optimize import minimize, minimize_scalar


from certus_core import (

    K_MAX_LIMIT,

    N_MAX_LIMIT,

    N_MIN_LIMIT,

    SUBSTRATES,

    SUBSTRATE_LIST,

    create_module_environment,

    setup_logging,


)


from certus_data import read_data_file_robust


from certus_physics import (

    PGlobalConfig,

    PGlobalOptimizer,

    Sample,

    calculate_RT_vectorized_real,

    calculate_T_substrate_array,

    calculate_reflection_array,

    calculate_transmission_array,

    clip_to_bounds,

    get_n_substrate_array_by_id,

    warmup_physics,


)


from certus_index_utils import (

    _ratio_theoretical_from_nk,

    _reflectance_ratio_theoretical_from_nk,

    log_structured_json_event,


)


# --- UI Imports (Optional for headless / test use) ---


try:

    from certus_ui import (

        CertusBaseApp,

        CertusLogPanel,

        CertusScientificPlot,

        CertusTheme,

        FlashyCard,

        GenericWorker,

        apply_certus_theme,

        create_styled_button,

        get_certus_last_dir,

        init_certus_app,

        plot_widget_plot_finite,

        sanitize_xy_for_plot,

        set_certus_last_dir,

        setup_pyqtgraph_defaults,

        wrap_scientific_plot_with_toolbar,

    )

    from certus_reset_framework import create_reset_button

    HAS_UI = True


except (ImportError, RuntimeError, Exception):

    # In headless mode (automated tests), some Qt libraries may fail.

    HAS_UI = False


# Bootstrap


_env = create_module_environment(__file__, "CERTUS_INDEX_SPLINE")


_SCRIPT_DIR = _env["script_dir"]


logger = logging.getLogger("CERTUS_INDEX_SPLINE")


# Évite de répéter la même ligne INFO à chaque appel (canonical_spline_sigma_knots est très sollicité).


_CANONICAL_IR_MESH_INFO_SEEN: set[tuple[float, int, int]] = set()


_QS_SPLINE_ORG = "CERTUS"


_QS_SPLINE_APP = "INDEX_SPLINE"


_QS_LAST_SPECTRUM = "last_spectrum_path"


# Exclude k < 1e-9 (L = ln k >= ln(1e-9)); knot bounds, warm start, post-PWL clipping.


K_MIN_PHYS: float = 1e-9


L_LNK_MIN_PHYS: float = float(np.log(K_MIN_PHYS))


# k floor consistent with SplineOptConfig.k_clip_lo (default 1e-5).


K_FLOOR_DEFAULT: float = 1e-5


# Minimum relative separation between consecutive sigma nodes (log-softmax codec).


SIGMA_KNOTS_MIN_SEP_REL: float = 0.005


# Standard numerical-fault exceptions caught at boundaries of optimisation /
# diagnostic blocks (degraded-but-recoverable). Centralised so the safety net
# stays consistent across the spline pipeline / corridors / smart-init.
NUMERICAL_FAULT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
    RuntimeError,
    AttributeError,
    KeyError,
    IndexError,
    FileNotFoundError,
)


def _enforce_sigma_min_sep(sk: np.ndarray, s_lo: float, s_hi: float) -> np.ndarray:
    """Forward sweep enforcing SIGMA_KNOTS_MIN_SEP_REL between consecutive knots.

    Same eps_s as ``sigma_knots_decode`` so that encode→decode is a no-op on
    a mesh that already satisfies the constraint.
    """
    sk = np.sort(np.asarray(sk, dtype=np.float64).ravel()).copy()
    if sk.size < 2:
        return sk
    eps_s = max(1e-10, SIGMA_KNOTS_MIN_SEP_REL * max(s_hi - s_lo, 1e-12))
    for i in range(1, sk.size):
        sk[i] = max(sk[i], sk[i - 1] + eps_s)
    # Preserve exact upper boundary.
    sk[-1] = max(s_hi, sk[-1])
    return sk


def enforce_k_floor_on_nodes(

    sigma_knots: np.ndarray,

    L_nodes: np.ndarray,

    k_floor: float = K_FLOOR_DEFAULT,

    *,

    eps_rel: float = 0.05,

    allow_insert: bool = True,


) -> tuple[np.ndarray, np.ndarray, bool]:

    """Enforce k >= k_floor on L = ln(k) nodes of a PWL spline.

    1. Clamp: L_j = max(L_j, ln(k_floor)) for all j.

    2. Flat: if both nodes of a segment are <= k_floor*(1+eps),

               set them exactly to ln(k_floor) (removes micro-slopes).

    3. Insert: if a segment crosses the threshold (one node above, one below

               *before* clamp), insert an intermediate knot sigma* at intersection

               point to keep the sub-threshold side perfectly flat.

    Returns (sigma_knots_new, L_nodes_new, modified).

    ``sigma_knots_new`` may be larger than input if nodes are inserted

    (disabled if ``allow_insert=False``, e.g. intermediate packing without resizing x).

    """

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel().copy()

    LL = np.asarray(L_nodes, dtype=np.float64).ravel().copy()

    if sk.size < 2 or LL.size != sk.size:

        return sk, LL, False

    L_floor = float(np.log(max(k_floor, 1e-30)))

    L_near = float(np.log(max(k_floor * (1.0 + eps_rel), 1e-30)))

    modified = False

    # --- Step 3: insertion of intermediate nodes (BEFORE clamp) ---

    if allow_insert:

        inserts: list[tuple[float, float]] = []  # (sigma_star, L_floor)

        for j in range(sk.size - 1):

            L_a, L_b = float(LL[j]), float(LL[j + 1])

            if (L_a < L_floor and L_b > L_near) or (L_b < L_floor and L_a > L_near):

                s_a, s_b = float(sk[j]), float(sk[j + 1])

                dL = L_b - L_a

                if abs(dL) > 1e-30:

                    t = (L_floor - L_a) / dL

                    t = float(np.clip(t, 0.01, 0.99))

                    sigma_star = s_a + t * (s_b - s_a)

                    inserts.append((sigma_star, L_floor))

        if inserts:

            for s_ins, L_ins in inserts:

                sk = np.append(sk, s_ins)

                LL = np.append(LL, L_ins)

            order = np.argsort(sk)

            sk = sk[order]

            LL = LL[order]

            modified = True

    # --- Step 1: individual clamp ---

    below = LL < L_floor

    if np.any(below):

        LL[below] = L_floor

        modified = True

    # --- Step 2: flattening of segments close to the floor ---

    for j in range(sk.size - 1):

        if float(LL[j]) <= L_near and float(LL[j + 1]) <= L_near:

            if float(LL[j]) != L_floor or float(LL[j + 1]) != L_floor:

                LL[j] = L_floor

                LL[j + 1] = L_floor

                modified = True

    return sk, LL, modified


# n monotonicity in sigma=1/lambda (nm): n increases with sigma, therefore decreases with lambda.


# lambda band by default (GUI): from short spectral edge to min(lambda_max, cap) nm.


N_MONO_BAND_HI_CAP_NM: float = 2000.0


N_MONO_XI_BOUNDS: tuple[float, float] = (-14.0, 14.0)


def default_n_mono_band_nm_from_spectrum(

    lam_nm: np.ndarray,

    *,

    hi_cap_nm: float = N_MONO_BAND_HI_CAP_NM,


) -> tuple[float, float] | None:

    """Band [lambda_min, min(lambda_max, hi_cap)] for ξ reparameterization (n non-decreasing in sigma on segments overlapping the band).

    Returns ``None`` if spectrum is empty or if min(lambda_max, hi_cap) <= lambda_min.

    """

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    lam = lam[np.isfinite(lam)]

    if lam.size == 0:

        return None

    lo = float(np.min(lam))

    hi = min(float(np.max(lam)), float(hi_cap_nm))

    if hi <= lo + 1e-9:

        return None

    return (lo, hi)


def _mono_sigmoid(z: float | np.ndarray) -> np.ndarray:

    z = np.asarray(z, dtype=np.float64)

    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


def _mono_logit(p: float) -> float:

    p = float(np.clip(p, 1e-9, 1.0 - 1e-9))

    return float(np.log(p / (1.0 - p)))


def n_mono_segment_flags(

    sigma_knots: np.ndarray, lam_lo_nm: float, lam_hi_nm: float


) -> np.ndarray:

    """True on segment [sigma_j,sigma_{j+1}] when the corresponding lambda interval intersects [lam_lo, lam_hi] (nm)."""

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    K = int(sk.size)

    if K < 2:

        return np.zeros(0, dtype=bool)

    lam_a = float(min(lam_lo_nm, lam_hi_nm))

    lam_b = float(max(lam_lo_nm, lam_hi_nm))

    if lam_b <= 0.0:

        return np.zeros(max(0, K - 1), dtype=bool)

    lam_a = max(0.0, lam_a)

    out = np.zeros(K - 1, dtype=bool)

    for j in range(K - 1):

        s0, s1 = float(sk[j]), float(sk[j + 1])

        slo, shi = (s0, s1) if s0 < s1 else (s1, s0)

        lam_max_seg = 1.0 / max(slo, 1e-18)

        lam_min_seg = 1.0 / max(shi, 1e-18)

        if lam_min_seg > lam_max_seg:

            lam_min_seg, lam_max_seg = lam_max_seg, lam_min_seg

        if not (lam_max_seg < lam_a or lam_min_seg > lam_b):

            out[j] = True

    return out


def n_lambda_rising_with_wavelength_penalty(

    cfg: "SplineOptConfig",

    sigma_knots_n: np.ndarray,

    n_nodes: np.ndarray,


) -> float:

    """

    Penalty: n increasing with lambda (typical "impossible" dispersion) on PWL 

    segments whose lambda interval overlaps ``n_lambda_rising_penalty_band_nm``.

    On a segment sigma_j->sigma_{j+1} (sigma increasing, lambda decreasing along the index), if n_j > n_{j+1},

    then n increases when lambda increases along the segment; we accumulate

    relu(n_j - n_{j+1} - slack)^2 if ``n_lambda_rising_penalty_slack`` > 0.

    """

    w = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)

    band = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)

    slack = float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0)

    if slack < 0.0:

        slack = 0.0

    if w <= 0.0 or band is None:

        return 0.0

    lam_lo = float(min(float(band[0]), float(band[1])))

    lam_hi = float(max(float(band[0]), float(band[1])))

    sk = np.asarray(sigma_knots_n, dtype=np.float64).ravel()

    nn = np.asarray(n_nodes, dtype=np.float64).ravel()

    if sk.size < 2 or nn.size != sk.size:

        return 0.0

    eps = 1e-12
    s0 = sk[:-1]
    s1 = sk[1:]
    valid = s1 > (s0 + eps)
    if not np.any(valid):
        return 0.0

    lam_min_seg = 1.0 / np.maximum(s1, 1e-30)
    lam_max_seg = 1.0 / np.maximum(s0, 1e-30)
    seg_lo = np.minimum(lam_min_seg, lam_max_seg)
    seg_hi = np.maximum(lam_min_seg, lam_max_seg)

    in_band = (seg_hi >= lam_lo) & (seg_lo <= lam_hi) & valid
    if not np.any(in_band):
        return 0.0

    viol = nn[:-1] - nn[1:]
    ve = np.maximum(viol - slack, 0.0)
    active = in_band & (viol > eps) & (ve > 0.0)
    if not np.any(active):
        return 0.0

    acc = float(np.dot(ve[active], ve[active]))
    return w * acc


def n_mono_knot_chains(seg_mono: np.ndarray) -> list[tuple[int, int]]:

    """Partition knot indices 0..K-1 into chains where n is non-decreasing along sigma."""

    K = int(seg_mono.size) + 1

    chains: list[tuple[int, int]] = []

    start = 0

    for j in range(len(seg_mono)):

        if not seg_mono[j]:

            chains.append((start, j))

            start = j + 1

    chains.append((start, K - 1))

    return chains


def decode_xi_n_to_physical_n(

    xi_n: np.ndarray,

    chains: list[tuple[int, int]],

    n_min: float,

    n_max: float,


) -> np.ndarray:

    """Map  to physical n: within each chain, n_{i+1} = n_i + (n_max-n_i)*sigmoid(_{i+1})."""

    xi_n = np.asarray(xi_n, dtype=np.float64).ravel()

    K = int(xi_n.size)

    n_out = np.zeros(K, dtype=np.float64)

    lo, hi = float(n_min), float(n_max)

    span0 = hi - lo

    for a, b in chains:

        n_out[a] = lo + span0 * float(_mono_sigmoid(xi_n[a]))

        prev = float(n_out[a])

        for idx in range(a + 1, b + 1):

            span = hi - prev

            if span < 1e-14:

                n_out[idx] = prev

            else:

                prev = prev + span * float(_mono_sigmoid(xi_n[idx]))

                n_out[idx] = prev

    np.clip(n_out, lo, hi, out=n_out)

    return n_out


def project_n_pwl_monotone_chains(n: np.ndarray, chains: list[tuple[int, int]]) -> np.ndarray:

    n = np.asarray(n, dtype=np.float64).ravel().copy()

    for a, b in chains:

        for idx in range(a + 1, b + 1):

            n[idx] = max(n[idx], n[idx - 1])

    return n


def encode_physical_n_to_xi_n(

    n_phys: np.ndarray,

    chains: list[tuple[int, int]],

    n_min: float,

    n_max: float,


) -> np.ndarray:

    """Apply per-chain isotonic projection, then inverse sigmoid reparameterization."""

    n_phys = project_n_pwl_monotone_chains(

        np.clip(np.asarray(n_phys, dtype=np.float64).ravel(), n_min, n_max), chains

    )

    K = int(n_phys.size)

    xi = np.zeros(K, dtype=np.float64)

    lo, hi = float(n_min), float(n_max)

    span0 = hi - lo

    for a, b in chains:

        ra = (float(n_phys[a]) - lo) / max(span0, 1e-30)

        xi[a] = _mono_logit(float(np.clip(ra, 1e-6, 1.0 - 1e-6)))

        prev = float(n_phys[a])

        for idx in range(a + 1, b + 1):

            span = hi - prev

            if span < 1e-14:

                xi[idx] = float(N_MONO_XI_BOUNDS[0])

            else:

                r = (float(n_phys[idx]) - prev) / span

                r = float(np.clip(r, 1e-8, 1.0 - 1e-8))

                xi[idx] = _mono_logit(r)

            prev = float(n_phys[idx])

    return xi


def x_slice_n_to_physical_nodes(

    x_n: np.ndarray,

    sigma_knots: np.ndarray,

    n_mono_band_nm: tuple[float, float] | None,


) -> np.ndarray:

    """Decode x slice (physical n or ξ) to physical n at sigma knots."""

    if n_mono_band_nm is None:

        return np.asarray(x_n, dtype=np.float64).ravel().copy()

    lam_lo, lam_hi = float(n_mono_band_nm[0]), float(n_mono_band_nm[1])

    seg = n_mono_segment_flags(sigma_knots, lam_lo, lam_hi)

    chains = n_mono_knot_chains(seg)

    return decode_xi_n_to_physical_n(

        x_n, chains, float(N_MIN_LIMIT), float(N_MAX_LIMIT)

    )


def physical_nodes_to_x_slice_n(

    n_phys: np.ndarray,

    sigma_knots: np.ndarray,

    n_mono_band_nm: tuple[float, float] | None,


) -> np.ndarray:

    """Encode physical n nodes to x slice (physical n or ξ) for optimization bounds."""

    if n_mono_band_nm is None:

        return np.clip(

            np.asarray(n_phys, dtype=np.float64).ravel(),

            float(N_MIN_LIMIT),

            float(N_MAX_LIMIT),

        )

    lam_lo, lam_hi = float(n_mono_band_nm[0]), float(n_mono_band_nm[1])

    seg = n_mono_segment_flags(sigma_knots, lam_lo, lam_hi)

    chains = n_mono_knot_chains(seg)

    return encode_physical_n_to_xi_n(

        np.asarray(n_phys, dtype=np.float64).ravel(),

        chains,

        float(N_MIN_LIMIT),

        float(N_MAX_LIMIT),

    )


def _reflectance_absolute_backside_from_nk(

    lam_nm: np.ndarray,

    n_l: np.ndarray,

    k_l: np.ndarray,

    d_nm: float,

    n_sub: np.ndarray,


) -> np.ndarray:

    """R(lambda) consistent with ``SplinePWLObjective``: TMM single layer, incoherent backside."""

    lam_nm = np.asarray(lam_nm, dtype=np.float64).ravel()

    n_l = np.asarray(n_l, dtype=np.float64).ravel()

    k_l = np.asarray(k_l, dtype=np.float64).ravel()

    n_sub = np.asarray(n_sub, dtype=np.float64).ravel()

    n_pts = int(lam_nm.size)

    thicknesses = np.array([float(d_nm)], dtype=np.float64)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    r_th, _ = calculate_RT_vectorized_real(

        thicknesses, n_layers_all, n_sub, lam_nm, with_backside=True

    )

    return np.asarray(r_th, dtype=np.float64).ravel()


# Adaptive mesh + needle: mandatory local descent (seed / after probe)


NEEDLE_POST_POLISH_MIN_MAXFUN: int = 800


ADAPTIVE_STAGE_LOCAL_DEFAULT_MAXFUN: int = 900


# Automation / perf presets (overridden by explicit fields if provided)


SPLINE_PERF_PRESETS: dict[str, dict[str, float | int | None]] = {

    "standard": {},

    "fast": {

        "pglobal_max_iter": 18,

        "pglobal_max_feval": 84000,

        "pglobal_max_time": 240.0,

        "polish_maxfun": 10000,

        "pglobal_local_search_budget": 12000,

    },

    "quality": {

        "pglobal_max_iter": 55,

        "pglobal_max_feval": 280000,

        "pglobal_max_time": 720.0,

        "polish_maxfun": 28000,

        "pglobal_local_search_budget": 104000,

    },

    "max": {

        "pglobal_max_iter": 88,

        "pglobal_max_feval": 760000,

        "pglobal_max_time": 3200.0,

        "polish_maxfun": 64000,

        "pglobal_local_search_budget": 240000,

    },


}


def merge_spline_preset(

    preset_name: str,

    explicit: dict[str, float | int | None],


) -> dict[str, float | int | None]:

    """Merges preset + explicit non-None kwargs (explicit wins)."""

    base = dict(SPLINE_PERF_PRESETS.get(preset_name, {}))

    for k, v in explicit.items():

        if v is not None:

            base[k] = v

    return base


def sigma_segment_indices(sig: np.ndarray, sigma_knots: np.ndarray) -> np.ndarray:

    """For each sigma, index of the segment ``[sigma_j, sigma_{j+1}]`` (sigma increasing with j)."""

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    n_seg = int(sk.size) - 1

    if n_seg < 1:

        return np.zeros(sig.shape[0], dtype=np.int32)

    j = np.searchsorted(sk, np.asarray(sig, dtype=np.float64), side="right") - 1

    return np.clip(j, 0, n_seg - 1).astype(np.int32)


def gui_perf_preset_only(preset_name: str) -> dict[str, float | int]:

    """Subset for GUI: no PGlobal iterations (defined by dedicated spinbox)."""

    d = dict(SPLINE_PERF_PRESETS.get(preset_name, {}))

    d.pop("pglobal_max_iter", None)

    return d


def export_spline_result_jsonable(

    r: dict, *, full_arrays: bool = True, embed_child_stages: bool = True


) -> dict:

    """JSON-serializable structure (lists instead of ndarrays)."""

    def _arr(x):

        if x is None:

            return None

        return np.asarray(x, dtype=np.float64).tolist()

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

            [float(r["n_mono_band_nm"][0]), float(r["n_mono_band_nm"][1])]

            if r.get("n_mono_band_nm") is not None

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

            out["stages"] = [

                export_spline_result_jsonable(s, full_arrays=True, embed_child_stages=False)

                for s in st

            ]

    if r.get("smart_mesh"):

        out["smart_mesh"] = r["smart_mesh"]

    return out


# --- sigma PWL Model ----------------------------------------------------------------


#


# Physical reminder: between two consecutive sigma nodes, n(sigma) and ln k(sigma) are linear in sigma = 1/lambda.


# The number of segments thus controls the resolution at which n and k can be curved 


# as a function of wavelength; far IR (high lambda, small sigma) often has only one wide segment 


# with the 12-point "log sigma" grid - hence the optional extension below.


#


# INDEX SPLINE: "canonical" mesh used by the entire worker (SOL2, SOL3, exports).


#   • Always 12 nodes as a first approximation: uniform distribution in log(sigma), 


#     equivalent to a geometric progression of lambda between lambda_min and lambda_max 


#     (not a constant step in nm).


#   • If the spectrum extends far into the IR (lambda_max strictly beyond the threshold), 


#     exactly 2 more nodes are added to better capture n/k between ~4000 nm and the last wavelength.


#


SPLINE_PWL_K_NODES: int = 12


SPLINE_PWL_N_SEG: int = SPLINE_PWL_K_NODES - 1


# Threshold (nm): as long as max(lambda_min, lambda_max) <= this value, the mesh remains 


# strictly identical to the legacy one (K = 12) - no regression for classic 


# VIS / near-IR spectra.


SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM: float = 4000.0


def min_relative_lambda_spacing_ratio(

    sk: np.ndarray,

    lam_min_nm: float,

    lam_max_nm: float,


) -> float:

    """min_i (lambda_{i+1}-lambda_i) / lambdā with sorted lambda (nm), lambdā = (file lambda_min + file lambda_max) / 2."""

    sk = np.sort(np.asarray(sk, dtype=np.float64).ravel())

    if int(sk.size) < 2:

        return float("inf")

    lam = 1.0 / np.maximum(sk, 1e-30)

    lam_sorted = np.sort(lam)

    gaps = np.diff(lam_sorted)

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    lam_mean = 0.5 * (lo + hi)

    if lam_mean <= 1e-30 or gaps.size == 0:

        return float("inf")

    return float(np.min(gaps) / lam_mean)


def build_sigma_knots_log_uniform(lam_min_nm: float, lam_max_nm: float, n_seg: int) -> np.ndarray:

    """K = n_seg+1 sigma nodes, uniform log(sigma) distribution on [1/lambda_max, 1/lambda_min] (same logic as K=12)."""

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    sig_min = 1.0 / max(hi, 1e-9)

    sig_max = 1.0 / max(lo, 1e-9)

    k = int(n_seg) + 1

    k = max(2, k)

    return np.exp(np.linspace(np.log(sig_min), np.log(sig_max), k)).astype(np.float64)


def _canonical_knots_min_lambda_kw(cfg: SplineOptConfig | None) -> dict[str, float]:

    """Arguments optionnels pour ``canonical_spline_sigma_knots`` depuis la config."""

    if cfg is None:

        return {}

    v = getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.02)

    try:

        fv = float(v)

    except (TypeError, ValueError):

        return {}

    if fv <= 0.0 or not np.isfinite(fv):

        return {}

    return {"min_delta_lambda_over_lambda_mean": fv}


def _insert_two_equi_lambda_in_last_sigma_segment(sk_base: np.ndarray) -> np.ndarray:

    """Refines only the last lambda interval (long lambda side) by two equidistant lambda nodes.

    sigma table convention throughout the module: ``sk`` is sorted by increasing sigma.

      • sk[0] = smallest sigma = 1 / lambda_max  ("long IR" end, last wavelength of the fit).

      • sk[1] = next sigma = 1 / lambda_pen      where lambda_pen is the **2nd largest** lambda among base mesh nodes.

    Other nodes (UV -> near IR) are untouched: only two sigma abscissae strictly 

    between sk[0] and sk[1] are inserted, at positions lambda = lambda_pen + (j/3)(lambda_max - lambda_pen) 

    for j ∈ {1, 2}, then sigma_j = 1/lambda_j. This yields three PWL sub-segments in lambda 

    on the often "difficult" zone (reststrahlen, atypical index behaviors beyond ~4 µm).

    Returns: new sorted sigma vector, size len(sk_base) + 2 on numerical success.

    """

    sk = np.sort(np.asarray(sk_base, dtype=np.float64).ravel())

    if int(sk.size) < 2:

        return sk.copy()

    # sigma[0] < sigma[1] < … : recall, lambda decreases when sigma index increases.

    s0, s1 = float(sk[0]), float(sk[1])

    lam_max = 1.0 / max(s0, 1e-30)  # red edge of the spectrum (last lambda point)

    lam_pen = float(1.0 / max(s1, 1e-30))  # penultimate node in increasing lambda order

    if not (lam_pen < lam_max):

        # Pathological case (sigma duplicates or degenerate mesh): do not modify.

        return sk.copy()

    dlam = lam_max - lam_pen

    # Thirds in lambda (not sigma): uniform distribution on [lambda_pen, lambda_max].

    lam_a = lam_pen + dlam / 3.0

    lam_b = lam_pen + 2.0 * dlam / 3.0

    sa = 1.0 / max(lam_a, 1e-30)

    sb = 1.0 / max(lam_b, 1e-30)

    merged = np.unique(np.sort(np.append(sk, [sa, sb])))

    if int(merged.size) != int(sk.size) + 2:

        # Floating collisions (very rare): slight relative offset to force uniqueness.

        span = max(s1 - s0, 1e-18)

        eps = max(1e-14, 1e-9 * span)

        merged = np.unique(np.sort(np.append(sk, [sa + eps, sb - eps])))

    return merged.astype(np.float64, copy=False)


def canonical_spline_sigma_knots(

    lam_min_nm: float,

    lam_max_nm: float,

    *,

    min_delta_lambda_over_lambda_mean: float | None = None,


) -> np.ndarray:

    """Constructs the sigma mesh used by the INDEX SPLINE optimizer for this spectrum.

    Steps:

      1) Base grid K = n_seg+1 (nominal n_seg=11 -> K=12), uniform log sigma, unless

         ``min_delta_lambda_over_lambda_mean`` > 0: n_seg is reduced until

         min(Deltalambda)/lambdā >= this threshold (lambdā = arithmetic average of file lambda_min, lambda_max).

      2) If max(lambda) <= ``SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM`` -> no IR extension.

      3) Otherwise -> insertion of 2 nodes on the last lambda segment (K=14) if the Deltalambda/lambdā

         constraint remains satisfied; otherwise extension omitted.

    The entire chain (``make_bounds_and_x0``, Smart Init "Continue", worker) must rely on **this**

    function so that sizes of x0, bounds, and ``sigma_knots`` remain consistent.

    """

    lo = float(min(float(lam_min_nm), float(lam_max_nm)))

    hi = float(max(float(lam_min_nm), float(lam_max_nm)))

    lam_mean = 0.5 * (lo + hi)

    sig_lo = 1.0 / max(hi, 1e-9)

    sig_hi = 1.0 / max(lo, 1e-9)

    ratio_req: float | None = None

    if min_delta_lambda_over_lambda_mean is not None:

        r = float(min_delta_lambda_over_lambda_mean)

        if r > 0.0 and np.isfinite(r) and lam_mean > 1e-30:

            ratio_req = r

    if ratio_req is None:

        sk12 = build_sigma_knots(lam_min_nm, lam_max_nm, SPLINE_PWL_N_SEG)

    else:

        sk12 = None

        for n_seg_try in range(int(SPLINE_PWL_N_SEG), 0, -1):

            cand = build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, n_seg_try)

            if min_relative_lambda_spacing_ratio(cand, lo, hi) >= ratio_req - 1e-15:

                sk12 = cand

                if n_seg_try < int(SPLINE_PWL_N_SEG):

                    logger.info(

                        "INDEX_SPLINE: sigma mesh reduced to n_seg=%d (K=%d) for min(Deltalambda)/lambdā >= %.5g "

                        "(lambdā=%.1f nm).",

                        n_seg_try,

                        int(cand.size),

                        ratio_req,

                        lam_mean,

                    )

                break

        if sk12 is None:

            sk12 = build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, 1)

            logger.warning(

                "INDEX_SPLINE: repli maillage K=2 - min(Deltalambda)/lambdā pourrait rester < %.5g.",

                ratio_req,

            )

    if hi <= SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM:

        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    out = _insert_two_equi_lambda_in_last_sigma_segment(sk12)

    if int(out.size) != int(sk12.size) + 2:

        logger.warning(

            "INDEX_SPLINE: IR extension (2 equi-lambda knots) ignored - degeneracy; K=%d.",

            int(sk12.size),

        )

        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    out = _enforce_sigma_min_sep(out, sig_lo, sig_hi)

    if ratio_req is not None and min_relative_lambda_spacing_ratio(out, lo, hi) < ratio_req - 1e-12:

        logger.info(

            "INDEX_SPLINE: extension IR (2 nœuds lambda) omise - violerait min(Deltalambda)/lambdā >= %.5g.",

            ratio_req,

        )

        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    _mesh_sig = (

        round(float(hi), 1),

        int(out.size),

        int(out.size - sk12.size),

    )

    if _mesh_sig in _CANONICAL_IR_MESH_INFO_SEEN:

        logger.debug(

            "INDEX_SPLINE: lambda_max=%.1f nm > %.0f nm - canonical mesh K=%d (+%d equi-lambda knots, last lambda segment).",

            hi,

            SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,

            int(out.size),

            int(out.size - sk12.size),

        )

    else:

        _CANONICAL_IR_MESH_INFO_SEEN.add(_mesh_sig)

        logger.info(

            "INDEX_SPLINE: lambda_max=%.1f nm > %.0f nm - canonical mesh K=%d (+%d equi-lambda knots, last lambda segment).",

            hi,

            SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,

            int(out.size),

            int(out.size - sk12.size),

        )

    return out


def bridge_sigma_knots_preserve_manual(

    sigma_src: np.ndarray,

    lam_min_nm: float,

    lam_max_nm: float,

    *,

    rmse_fit_lambda_nm: tuple[float, float] | None = None,

    min_delta_lambda_over_lambda_mean: float | None = None,


) -> np.ndarray:

    """Worker K-canonical mesh while preserving manual mode knots.

    Strategy:

      - Target K = len(canonical_spline_sigma_knots(...)).

      - If K_src >= target_K: canonical return (no ad-hoc reduction/pruning here).

      - If K_src < target_K: we **add** knots (manual knots are not moved).

        Addition candidates come from the canonical grid, plus the RMSE window bounds 

        (if active) to limit extrapolation in the noted zone.

    """

    sk_src = np.sort(np.asarray(sigma_src, dtype=np.float64).ravel())

    _can_kw: dict[str, float] = {}

    if min_delta_lambda_over_lambda_mean is not None:

        r = float(min_delta_lambda_over_lambda_mean)

        if r > 0.0 and np.isfinite(r):

            _can_kw["min_delta_lambda_over_lambda_mean"] = r

    sk_canon = np.sort(canonical_spline_sigma_knots(lam_min_nm, lam_max_nm, **_can_kw))

    if int(sk_src.size) < 2 or int(sk_src.size) >= int(sk_canon.size):

        return sk_canon

    s_min = float(min(1.0 / max(lam_max_nm, 1e-30), 1.0 / max(lam_min_nm, 1e-30)))

    s_max = float(max(1.0 / max(lam_max_nm, 1e-30), 1.0 / max(lam_min_nm, 1e-30)))

    sel = sk_src[(sk_src >= s_min - 1e-15) & (sk_src <= s_max + 1e-15)].copy()

    if int(sel.size) < 2:

        return sk_canon

    # Force spectral edges (especially useful if preview is truncated by rmse_fit_lambda_nm).

    # Do not duplicate existing sigma (mesh extremes ~ 1/lambda_max, 1/lambda_min within epsilon).

    tol_e = max(1e-14, 1e-9 * max(float(np.max(sel) - np.min(sel)), 1e-12))

    _edge_extra: list[float] = []

    if not np.any(np.abs(sel - s_min) <= tol_e):

        _edge_extra.append(s_min)

    if not np.any(np.abs(sel - s_max) <= tol_e):

        _edge_extra.append(s_max)

    if _edge_extra:

        sel = np.unique(np.concatenate((sel, np.asarray(_edge_extra, dtype=np.float64))))

    tol = max(1e-14, 1e-9 * max(float(np.max(sel) - np.min(sel)), 1e-12))

    cand = list(np.asarray(sk_canon, dtype=np.float64).ravel())

    if rmse_fit_lambda_nm is not None:

        lo_w = float(min(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

        hi_w = float(max(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

        if lo_w > 0.0 and hi_w > 0.0:

            cand.extend([1.0 / hi_w, 1.0 / lo_w])

    cands = np.asarray(cand, dtype=np.float64).ravel()

    cands = cands[(cands >= s_min - tol) & (cands <= s_max + tol)]

    target_k = int(sk_canon.size)

    need = target_k - int(sel.size)

    if need > 0:

        missing: list[float] = []

        for s in sk_canon:

            sf = float(s)

            if not np.any(np.abs(sel - sf) <= tol):

                missing.append(sf)

        # Common case: K=12 preview = exact subset of worker mesh (e.g., +2 IR nodes).

        # Fill with missing canonical sigma (fixed order) rather than greedy which may diverge.

        if len(missing) == need:

            out = np.sort(

                np.unique(

                    np.concatenate((sel, np.asarray(missing, dtype=np.float64)))

                )

            )

            if int(out.size) == target_k:

                return out.astype(np.float64, copy=False)

            sel = out

            need = target_k - int(sel.size)

    while int(sel.size) < target_k:

        best = None

        best_dist = -1.0

        for s in cands:

            if np.any(np.abs(sel - s) <= tol):

                continue

            d = float(np.min(np.abs(sel - s)))

            if d > best_dist:

                best_dist = d

                best = float(s)

        if best is None:

            break

        sel = np.unique(np.concatenate((sel, np.asarray([best], dtype=np.float64))))

    out = np.sort(np.asarray(sel, dtype=np.float64).ravel())

    if int(out.size) != target_k:

        return sk_canon

    return out


def build_sigma_knots(lam_min_nm: float, lam_max_nm: float, n_seg: int) -> np.ndarray:

    """Constructs a list of sigma on [1/lambda_max, 1/lambda_min]; used by ``canonical_spline_sigma_knots`` (K=12).

    For ``n_seg == 11`` (canonical K=12) delegates to :func:`build_sigma_knots_log_uniform`
    (uniform in log(sigma)). For other ``n_seg`` keeps the legacy linear-in-sigma layout used
    by external tools / tests outside the canonical 12-node pipeline.
    """

    k = int(n_seg) + 1

    if k == 12:

        # Nominal INDEX SPLINE case: uniform in log(sigma) -> geometric progression in lambda.
        return build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, n_seg)

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    sig_min = 1.0 / max(hi, 1e-9)

    sig_max = 1.0 / max(lo, 1e-9)

    # Other tools / tests: linear mesh in sigma (outside the canonical 12-node pipeline).

    return np.linspace(sig_min, sig_max, k, dtype=np.float64)






def _to_fraction_T(y: np.ndarray) -> np.ndarray:

    arr = np.asarray(y, float)

    if float(np.nanmedian(arr)) > 2.5:

        return arr / 100.0

    return arr


def ensure_lam_nm_array(lam: np.ndarray) -> np.ndarray:

    """If max(lambda) < 100, interpret as um and convert to nm (consistent with nm optics)."""

    v = np.asarray(lam, dtype=np.float64).ravel()

    if v.size and float(np.nanmax(v)) < 100.0:

        return (v * 1000.0).astype(np.float64, copy=False)

    return v


def prepare_exp_TR_for_fit(

    lam_nm: np.ndarray,

    n_sub: np.ndarray,

    t_exp: np.ndarray | None,

    r_exp: np.ndarray | None,

    *,

    t_is_ratio: bool,


) -> tuple[np.ndarray | None, np.ndarray | None]:

    """Applies ``_to_fraction_T`` (% -> fraction if needed). Does not divide by T_sub.

    In ratio mode (``t_is_ratio`` in config), the file already contains the same 

    ratio as the model (T_film/bare T_sub, R_film/bare T_sub with backside). A second 

    division by T_sub would be an error. ``lam_nm`` / ``n_sub`` remain for calling compatibility.

    """

    _ = lam_nm, n_sub, t_is_ratio

    t_o = (

        None

        if t_exp is None

        else _to_fraction_T(np.asarray(t_exp, dtype=np.float64).ravel()).astype(np.float64, copy=False)

    )

    r_o = (

        None

        if r_exp is None

        else _to_fraction_T(np.asarray(r_exp, dtype=np.float64).ravel()).astype(np.float64, copy=False)

    )

    return t_o, r_o


_LAMBDA_NAMES = (

    "lambda",

    "Lambda",

    "wavelength",

    "Wavelength",

    "Wavelength, nm",

    "wl",

    "WL",

    "nm",


)


def _find_lambda_column(df: pd.DataFrame) -> str | None:

    for name in _LAMBDA_NAMES:

        if name in df.columns:

            return name

    for c in df.columns:

        cl = str(c).strip().lower()

        if "wavelength" in cl or cl.endswith(", nm") or cl == "lambda (nm)":

            return str(c)

    return None


def _find_transmission_column(df: pd.DataFrame, lam_col: str) -> str | None:

    for name in ("T", "t", "Trans", "Transmission", "T_rel", "Tr", "fab1", "FAB1"):

        if name in df.columns and str(name) != lam_col:

            return name

    for c in df.columns:

        if str(c) == lam_col:

            continue

        cl = str(c).lower()

        if "reflect" in cl:

            continue

        if "trans" in cl or cl.startswith("t") or "rel" in cl or cl == "fab1":

            return str(c)

    candidates = [c for c in df.columns if c != lam_col and pd.api.types.is_numeric_dtype(df[c])]

    if len(candidates) == 1:

        return str(candidates[0])

    return None


def normalize_spectrum_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    """Renames to lambda / T / R for the rest of the pipeline."""

    if df is None or df.empty:

        return df

    out = df.copy()

    lam_c = _find_lambda_column(out)

    if not lam_c:

        raise ValueError("Wavelength column not found (expected e.g. 'lambda', 'Wavelength, nm').")

    out.rename(columns={lam_c: "lambda"}, inplace=True)

    t_c = _find_transmission_column(out, "lambda")

    if t_c and t_c != "lambda":

        out.rename(columns={t_c: "T"}, inplace=True)

    for rname in ("R", "r", "Reflect", "Reflection"):

        if rname in out.columns and rname != "T":

            out.rename(columns={rname: "R"}, inplace=True)

            break

    return out


class DataType(Enum):

    TRANSMISSION = auto()

    REFLECTION = auto()

    BOTH = auto()


def substrate_id_from_name(name: str) -> int:

    return int(SUBSTRATES[name]["id"])


def allowed_substrate_names() -> list[str]:

    return [n for n in SUBSTRATE_LIST if int(SUBSTRATES[n]["id"]) >= 0]


# --- P4 Refactor: Sub-configs ---
@dataclass
class SplinePGlobalConfig:
    """PGlobal optimizer + SOL3 phase 1 + local-only fallback settings."""
    pglobal_max_iter: int = 35
    polish_maxfun: int = 8000
    sol3_phase1_maxfun: int | None = None
    pglobal_max_feval: int | None = None
    pglobal_max_time: float | None = None
    pglobal_local_search_budget: int | None = None
    pglobal_random_seed: int | None = None
    pglobal_trust_region_by_k: bool = False
    pglobal_trust_k_lo: int = 4
    pglobal_trust_k_hi: int = 14
    pglobal_trust_rho_lo: float = 0.12
    pglobal_trust_rho_hi: float = 0.5
    auto_knot_dual_seed: bool = True
    auto_knot_recovery_perturb: bool = True
    auto_knot_recovery_rel_tol: float = 0.02
    spline_local_only: bool = False
    stage_mandatory_local_maxfun: int = 0

@dataclass
class SplineSmartInitConfig:
    """Smart-Init preview hook + post-preview overrides."""
    smart_init_preview_hook: Callable[[dict], bool] | None = None
    smart_init_preview_shown: bool = False
    smart_preview_node_override: tuple[np.ndarray, np.ndarray] | None = None
    smart_preview_d_nm_override: float | None = None
    smart_preview_accepted_rmse: float | None = None
    smart_init_manual_force_restart: bool = False
    smart_preview_exact_sigma_knots: np.ndarray | None = None
    smart_preview_exact_n_L: tuple[np.ndarray, np.ndarray] | None = None
    fixed_sigma_knots_count: int | None = None
    spline_smart_init_deep_two_phase: bool = True

@dataclass
class SplineCorridorConfig:
    """d-profiling corridor parameters (without bootstrap, see SplineBootstrapConfig)."""
    corridor_profile_d_enabled: bool = False
    corridor_profile_d_mode: str = "abs_delta_adaptive"
    corridor_profile_d_rmse_alpha: float = 1.05
    corridor_profile_d_rmse_abs_tolerance: float = 2.5e-4
    corridor_profile_d_base_source: str = "best_polished"
    corridor_profile_d_threshold_basis: str = "max"
    corridor_profile_d_threshold_ratio_guard: float = 1.25
    corridor_profile_d_auto_relax_max_factor: float = 1.5
    corridor_profile_d_step_nm: float = 1.0
    corridor_profile_d_step_nm_initial: float = 1.0
    corridor_profile_d_step_growth: float = 1.4
    corridor_profile_d_step_nm_max: float = 4.0
    corridor_profile_d_max_span_nm: float = 15.0
    corridor_profile_d_min_valid_each_side: int = 1
    corridor_profile_d_lr_conf_level: float = 0.95
    corridor_profile_d_sigma_t: float | None = None
    corridor_profile_d_sigma_r: float | None = None
    corridor_profile_d_sigma_hetero: bool = False
    corridor_profile_d_sigma_hetero_scale: float = 1.0
    corridor_profile_d_n_starts: int = 1
    corridor_profile_d_jitter_n: float = 0.02
    corridor_profile_d_jitter_L: float = 0.15
    corridor_profile_d_rng_seed: int = 0
    corridor_profile_d_fit_auto_n_starts: bool = False
    corridor_profile_d_fit_max_n_starts: int = 2
    corridor_profile_d_fit_retry_maxfun_scale: float = 1.5
    corridor_profile_d_seed_gate_keep_nominal_if_refit_worse: bool = True
    corridor_profile_d_seed_gate_tol_rel: float = 0.0
    corridor_profile_d_seed_gate_tol_abs: float = 1e-5
    corridor_profile_d_polish_maxfun: int | None = None
    corridor_profile_d_parallel_walks: bool = True
    corridor_profile_d_auto_relax_threshold: bool = True
    corridor_profile_d_auto_relax_epsilon: float = 0.002
    corridor_scientific_nominal_enabled: bool = True
    corridor_profile_d_parabola_half_window_pts: int = 4
    corridor_profile_d_symmetric_center_mode: str = "parabola"
    corridor_profile_d_adaptive_rmse_ref_half_width_nm: float = 1.5
    corridor_profile_d_adaptive_rmse_probe_steps_each_side: int = 3
    corridor_profile_d_adaptive_rmse_noise_factor: float = 3.0
    corridor_profile_d_adaptive_rmse_min: float = 2.5e-5
    corridor_reg_sensitivity_enabled: bool = False
    corridor_reg_sensitivity_points: int = 5
    corridor_reg_sensitivity_decades: int = 2
    corridor_reg_sensitivity_n_workers: int = 1

@dataclass
class SplineBootstrapConfig:
    """Parametric / residual bootstrap for corridor confidence bands."""
    corridor_bootstrap_enabled: bool = False
    corridor_bootstrap_n: int = 40
    corridor_bootstrap_seed: int = 0
    corridor_bootstrap_percentile: float = 0.95
    corridor_bootstrap_sigma_t: float | None = None
    corridor_bootstrap_sigma_r: float | None = None
    corridor_bootstrap_mode: str = "parametric"
    corridor_bootstrap_block_len: int = 1
    corridor_bootstrap_quick_refit: bool = False
    corridor_bootstrap_quick_refit_maxfun: int = 4000
    corridor_bootstrap_n_workers: int = 1

@dataclass
class SplineNonlinearAlphaConfig:
    """Post-pass alpha refinement (linear scale factor on T/R)."""
    nonlinear_alpha_refinement_enabled: bool = True
    nonlinear_alpha_budget_mode: str = "slow"
    nonlinear_alpha_second_pass_enabled: bool = True
    nonlinear_alpha_second_pass_maxfun: int | None = None
    nl_alpha_adaptive_early_stop: bool = True
    nl_alpha_pure_spectral: bool = True
    nl_alpha_bisection_refine: bool = True
    nl_alpha_bisection_max_iter: int = 8

@dataclass(init=False)
class SplineOptConfig:
    lam_nm: np.ndarray
    t_exp: np.ndarray | None
    r_exp: np.ndarray | None
    n_sub: np.ndarray
    data_type: DataType
    n_seg: int
    d_lo: float
    d_hi: float
    weight_t: float
    weight_r: float
    substrate_name: str
    t_is_ratio: bool = False
    x0_warm: np.ndarray | None = None
    k_clip_lo: float = 1e-5
    k_clip_hi: float = min(0.99, float(K_MAX_LIMIT))
    sigma_knots_override: np.ndarray | None = None
    n_mono_band_nm: tuple[float, float] | None = None
    n_mono_continuous_penalty: float = 0.0
    n_lambda_rising_penalty_band_nm: tuple[float, float] | None = (400.0, 1500.0)
    n_lambda_rising_penalty_weight: float = 3000.0
    n_lambda_rising_penalty_slack: float = 0.001
    x0_warm_encoding: str | None = None
    x0_warm_n_mono_band_for_decode: tuple[float, float] | None = None
    lnk_spline_stage_enabled: bool = True
    lnk_spline_reg_weight: float = 1e-3
    spline_pure_spectral_objective: bool = False
    lnk_spline_min_sep_rel: float = 0.01
    node_mesh_spectral_polish_enabled: bool = True
    node_model_spectral_polish_maxfun: int | None = None
    rmse_fit_lambda_nm: tuple[float, float] | None = None
    nk_profile_interp: str = "smooth"
    spline_min_delta_lambda_over_lambda_mean: float = 0.02

    # --- Composed configs ---
    pglobal: SplinePGlobalConfig = field(default_factory=SplinePGlobalConfig)
    smart_init: SplineSmartInitConfig = field(default_factory=SplineSmartInitConfig)
    corridor: SplineCorridorConfig = field(default_factory=SplineCorridorConfig)
    bootstrap: SplineBootstrapConfig = field(default_factory=SplineBootstrapConfig)
    nonlinear_alpha: SplineNonlinearAlphaConfig = field(default_factory=SplineNonlinearAlphaConfig)

    def __init__(self, substrate_name, weight_r, weight_t, d_hi, d_lo, n_seg, data_type, n_sub, r_exp, t_exp, lam_nm, t_is_ratio=False, x0_warm=None, k_clip_lo=1e-5, k_clip_hi=min(0.99, float(K_MAX_LIMIT)), sigma_knots_override=None, n_mono_band_nm=None, n_mono_continuous_penalty=0.0, n_lambda_rising_penalty_band_nm=(400.0, 1500.0), n_lambda_rising_penalty_weight=3000.0, n_lambda_rising_penalty_slack=0.001, x0_warm_encoding=None, x0_warm_n_mono_band_for_decode=None, lnk_spline_stage_enabled=True, lnk_spline_reg_weight=1e-3, spline_pure_spectral_objective=False, lnk_spline_min_sep_rel=0.01, node_mesh_spectral_polish_enabled=True, node_model_spectral_polish_maxfun=None, rmse_fit_lambda_nm=None, nk_profile_interp="smooth", spline_min_delta_lambda_over_lambda_mean=0.02, **kwargs):
        self.lam_nm = lam_nm
        self.t_exp = t_exp
        self.r_exp = r_exp
        self.n_sub = n_sub
        self.data_type = data_type
        self.n_seg = n_seg
        self.d_lo = d_lo
        self.d_hi = d_hi
        self.weight_t = weight_t
        self.weight_r = weight_r
        self.substrate_name = substrate_name
        self.t_is_ratio = t_is_ratio
        self.x0_warm = x0_warm
        self.k_clip_lo = k_clip_lo
        self.k_clip_hi = k_clip_hi
        self.sigma_knots_override = sigma_knots_override
        self.n_mono_band_nm = n_mono_band_nm
        self.n_mono_continuous_penalty = n_mono_continuous_penalty
        self.n_lambda_rising_penalty_band_nm = n_lambda_rising_penalty_band_nm
        self.n_lambda_rising_penalty_weight = n_lambda_rising_penalty_weight
        self.n_lambda_rising_penalty_slack = n_lambda_rising_penalty_slack
        self.x0_warm_encoding = x0_warm_encoding
        self.x0_warm_n_mono_band_for_decode = x0_warm_n_mono_band_for_decode
        self.lnk_spline_stage_enabled = lnk_spline_stage_enabled
        self.lnk_spline_reg_weight = lnk_spline_reg_weight
        self.spline_pure_spectral_objective = spline_pure_spectral_objective
        self.lnk_spline_min_sep_rel = lnk_spline_min_sep_rel
        self.node_mesh_spectral_polish_enabled = node_mesh_spectral_polish_enabled
        self.node_model_spectral_polish_maxfun = node_model_spectral_polish_maxfun
        self.rmse_fit_lambda_nm = rmse_fit_lambda_nm
        self.nk_profile_interp = nk_profile_interp
        self.spline_min_delta_lambda_over_lambda_mean = spline_min_delta_lambda_over_lambda_mean
        self.pglobal = SplinePGlobalConfig()
        self.smart_init = SplineSmartInitConfig()
        self.corridor = SplineCorridorConfig()
        self.bootstrap = SplineBootstrapConfig()
        self.nonlinear_alpha = SplineNonlinearAlphaConfig()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def replace(self, **changes):
        import copy
        new_obj = copy.copy(self)
        new_obj.pglobal = copy.copy(self.pglobal)
        new_obj.smart_init = copy.copy(self.smart_init)
        new_obj.corridor = copy.copy(self.corridor)
        new_obj.bootstrap = copy.copy(self.bootstrap)
        new_obj.nonlinear_alpha = copy.copy(self.nonlinear_alpha)
        for k, v in changes.items():
            setattr(new_obj, k, v)
        return new_obj




    # --- Legacy Properties ---
    @property
    def pglobal_max_iter(self): return self.pglobal.pglobal_max_iter
    @pglobal_max_iter.setter
    def pglobal_max_iter(self, value): self.pglobal.pglobal_max_iter = value

    @property
    def polish_maxfun(self): return self.pglobal.polish_maxfun
    @polish_maxfun.setter
    def polish_maxfun(self, value): self.pglobal.polish_maxfun = value

    @property
    def sol3_phase1_maxfun(self): return self.pglobal.sol3_phase1_maxfun
    @sol3_phase1_maxfun.setter
    def sol3_phase1_maxfun(self, value): self.pglobal.sol3_phase1_maxfun = value

    @property
    def pglobal_max_feval(self): return self.pglobal.pglobal_max_feval
    @pglobal_max_feval.setter
    def pglobal_max_feval(self, value): self.pglobal.pglobal_max_feval = value

    @property
    def pglobal_max_time(self): return self.pglobal.pglobal_max_time
    @pglobal_max_time.setter
    def pglobal_max_time(self, value): self.pglobal.pglobal_max_time = value

    @property
    def pglobal_local_search_budget(self): return self.pglobal.pglobal_local_search_budget
    @pglobal_local_search_budget.setter
    def pglobal_local_search_budget(self, value): self.pglobal.pglobal_local_search_budget = value

    @property
    def pglobal_random_seed(self): return self.pglobal.pglobal_random_seed
    @pglobal_random_seed.setter
    def pglobal_random_seed(self, value): self.pglobal.pglobal_random_seed = value

    @property
    def pglobal_trust_region_by_k(self): return self.pglobal.pglobal_trust_region_by_k
    @pglobal_trust_region_by_k.setter
    def pglobal_trust_region_by_k(self, value): self.pglobal.pglobal_trust_region_by_k = value

    @property
    def pglobal_trust_k_lo(self): return self.pglobal.pglobal_trust_k_lo
    @pglobal_trust_k_lo.setter
    def pglobal_trust_k_lo(self, value): self.pglobal.pglobal_trust_k_lo = value

    @property
    def pglobal_trust_k_hi(self): return self.pglobal.pglobal_trust_k_hi
    @pglobal_trust_k_hi.setter
    def pglobal_trust_k_hi(self, value): self.pglobal.pglobal_trust_k_hi = value

    @property
    def pglobal_trust_rho_lo(self): return self.pglobal.pglobal_trust_rho_lo
    @pglobal_trust_rho_lo.setter
    def pglobal_trust_rho_lo(self, value): self.pglobal.pglobal_trust_rho_lo = value

    @property
    def pglobal_trust_rho_hi(self): return self.pglobal.pglobal_trust_rho_hi
    @pglobal_trust_rho_hi.setter
    def pglobal_trust_rho_hi(self, value): self.pglobal.pglobal_trust_rho_hi = value

    @property
    def auto_knot_dual_seed(self): return self.pglobal.auto_knot_dual_seed
    @auto_knot_dual_seed.setter
    def auto_knot_dual_seed(self, value): self.pglobal.auto_knot_dual_seed = value

    @property
    def auto_knot_recovery_perturb(self): return self.pglobal.auto_knot_recovery_perturb
    @auto_knot_recovery_perturb.setter
    def auto_knot_recovery_perturb(self, value): self.pglobal.auto_knot_recovery_perturb = value

    @property
    def auto_knot_recovery_rel_tol(self): return self.pglobal.auto_knot_recovery_rel_tol
    @auto_knot_recovery_rel_tol.setter
    def auto_knot_recovery_rel_tol(self, value): self.pglobal.auto_knot_recovery_rel_tol = value

    @property
    def spline_local_only(self): return self.pglobal.spline_local_only
    @spline_local_only.setter
    def spline_local_only(self, value): self.pglobal.spline_local_only = value

    @property
    def stage_mandatory_local_maxfun(self): return self.pglobal.stage_mandatory_local_maxfun
    @stage_mandatory_local_maxfun.setter
    def stage_mandatory_local_maxfun(self, value): self.pglobal.stage_mandatory_local_maxfun = value

    @property
    def smart_init_preview_hook(self): return self.smart_init.smart_init_preview_hook
    @smart_init_preview_hook.setter
    def smart_init_preview_hook(self, value): self.smart_init.smart_init_preview_hook = value

    @property
    def smart_init_preview_shown(self): return self.smart_init.smart_init_preview_shown
    @smart_init_preview_shown.setter
    def smart_init_preview_shown(self, value): self.smart_init.smart_init_preview_shown = value

    @property
    def smart_preview_node_override(self): return self.smart_init.smart_preview_node_override
    @smart_preview_node_override.setter
    def smart_preview_node_override(self, value): self.smart_init.smart_preview_node_override = value

    @property
    def smart_preview_d_nm_override(self): return self.smart_init.smart_preview_d_nm_override
    @smart_preview_d_nm_override.setter
    def smart_preview_d_nm_override(self, value): self.smart_init.smart_preview_d_nm_override = value

    @property
    def smart_preview_accepted_rmse(self): return self.smart_init.smart_preview_accepted_rmse
    @smart_preview_accepted_rmse.setter
    def smart_preview_accepted_rmse(self, value): self.smart_init.smart_preview_accepted_rmse = value

    @property
    def smart_init_manual_force_restart(self): return self.smart_init.smart_init_manual_force_restart
    @smart_init_manual_force_restart.setter
    def smart_init_manual_force_restart(self, value): self.smart_init.smart_init_manual_force_restart = value

    @property
    def smart_preview_exact_sigma_knots(self): return self.smart_init.smart_preview_exact_sigma_knots
    @smart_preview_exact_sigma_knots.setter
    def smart_preview_exact_sigma_knots(self, value): self.smart_init.smart_preview_exact_sigma_knots = value

    @property
    def smart_preview_exact_n_L(self): return self.smart_init.smart_preview_exact_n_L
    @smart_preview_exact_n_L.setter
    def smart_preview_exact_n_L(self, value): self.smart_init.smart_preview_exact_n_L = value

    @property
    def fixed_sigma_knots_count(self): return self.smart_init.fixed_sigma_knots_count
    @fixed_sigma_knots_count.setter
    def fixed_sigma_knots_count(self, value): self.smart_init.fixed_sigma_knots_count = value

    @property
    def spline_smart_init_deep_two_phase(self): return self.smart_init.spline_smart_init_deep_two_phase
    @spline_smart_init_deep_two_phase.setter
    def spline_smart_init_deep_two_phase(self, value): self.smart_init.spline_smart_init_deep_two_phase = value

    @property
    def corridor_profile_d_enabled(self): return self.corridor.corridor_profile_d_enabled
    @corridor_profile_d_enabled.setter
    def corridor_profile_d_enabled(self, value): self.corridor.corridor_profile_d_enabled = value

    @property
    def corridor_profile_d_mode(self): return self.corridor.corridor_profile_d_mode
    @corridor_profile_d_mode.setter
    def corridor_profile_d_mode(self, value): self.corridor.corridor_profile_d_mode = value

    @property
    def corridor_profile_d_rmse_alpha(self): return self.corridor.corridor_profile_d_rmse_alpha
    @corridor_profile_d_rmse_alpha.setter
    def corridor_profile_d_rmse_alpha(self, value): self.corridor.corridor_profile_d_rmse_alpha = value

    @property
    def corridor_profile_d_rmse_abs_tolerance(self): return self.corridor.corridor_profile_d_rmse_abs_tolerance
    @corridor_profile_d_rmse_abs_tolerance.setter
    def corridor_profile_d_rmse_abs_tolerance(self, value): self.corridor.corridor_profile_d_rmse_abs_tolerance = value

    @property
    def corridor_profile_d_base_source(self): return self.corridor.corridor_profile_d_base_source
    @corridor_profile_d_base_source.setter
    def corridor_profile_d_base_source(self, value): self.corridor.corridor_profile_d_base_source = value

    @property
    def corridor_profile_d_threshold_basis(self): return self.corridor.corridor_profile_d_threshold_basis
    @corridor_profile_d_threshold_basis.setter
    def corridor_profile_d_threshold_basis(self, value): self.corridor.corridor_profile_d_threshold_basis = value

    @property
    def corridor_profile_d_threshold_ratio_guard(self): return self.corridor.corridor_profile_d_threshold_ratio_guard
    @corridor_profile_d_threshold_ratio_guard.setter
    def corridor_profile_d_threshold_ratio_guard(self, value): self.corridor.corridor_profile_d_threshold_ratio_guard = value

    @property
    def corridor_profile_d_auto_relax_max_factor(self): return self.corridor.corridor_profile_d_auto_relax_max_factor
    @corridor_profile_d_auto_relax_max_factor.setter
    def corridor_profile_d_auto_relax_max_factor(self, value): self.corridor.corridor_profile_d_auto_relax_max_factor = value

    @property
    def corridor_profile_d_step_nm(self): return self.corridor.corridor_profile_d_step_nm
    @corridor_profile_d_step_nm.setter
    def corridor_profile_d_step_nm(self, value): self.corridor.corridor_profile_d_step_nm = value

    @property
    def corridor_profile_d_step_nm_initial(self): return self.corridor.corridor_profile_d_step_nm_initial
    @corridor_profile_d_step_nm_initial.setter
    def corridor_profile_d_step_nm_initial(self, value): self.corridor.corridor_profile_d_step_nm_initial = value

    @property
    def corridor_profile_d_step_growth(self): return self.corridor.corridor_profile_d_step_growth
    @corridor_profile_d_step_growth.setter
    def corridor_profile_d_step_growth(self, value): self.corridor.corridor_profile_d_step_growth = value

    @property
    def corridor_profile_d_step_nm_max(self): return self.corridor.corridor_profile_d_step_nm_max
    @corridor_profile_d_step_nm_max.setter
    def corridor_profile_d_step_nm_max(self, value): self.corridor.corridor_profile_d_step_nm_max = value

    @property
    def corridor_profile_d_max_span_nm(self): return self.corridor.corridor_profile_d_max_span_nm
    @corridor_profile_d_max_span_nm.setter
    def corridor_profile_d_max_span_nm(self, value): self.corridor.corridor_profile_d_max_span_nm = value

    @property
    def corridor_profile_d_min_valid_each_side(self): return self.corridor.corridor_profile_d_min_valid_each_side
    @corridor_profile_d_min_valid_each_side.setter
    def corridor_profile_d_min_valid_each_side(self, value): self.corridor.corridor_profile_d_min_valid_each_side = value

    @property
    def corridor_profile_d_lr_conf_level(self): return self.corridor.corridor_profile_d_lr_conf_level
    @corridor_profile_d_lr_conf_level.setter
    def corridor_profile_d_lr_conf_level(self, value): self.corridor.corridor_profile_d_lr_conf_level = value

    @property
    def corridor_profile_d_sigma_t(self): return self.corridor.corridor_profile_d_sigma_t
    @corridor_profile_d_sigma_t.setter
    def corridor_profile_d_sigma_t(self, value): self.corridor.corridor_profile_d_sigma_t = value

    @property
    def corridor_profile_d_sigma_r(self): return self.corridor.corridor_profile_d_sigma_r
    @corridor_profile_d_sigma_r.setter
    def corridor_profile_d_sigma_r(self, value): self.corridor.corridor_profile_d_sigma_r = value

    @property
    def corridor_profile_d_sigma_hetero(self): return self.corridor.corridor_profile_d_sigma_hetero
    @corridor_profile_d_sigma_hetero.setter
    def corridor_profile_d_sigma_hetero(self, value): self.corridor.corridor_profile_d_sigma_hetero = value

    @property
    def corridor_profile_d_sigma_hetero_scale(self): return self.corridor.corridor_profile_d_sigma_hetero_scale
    @corridor_profile_d_sigma_hetero_scale.setter
    def corridor_profile_d_sigma_hetero_scale(self, value): self.corridor.corridor_profile_d_sigma_hetero_scale = value

    @property
    def corridor_profile_d_n_starts(self): return self.corridor.corridor_profile_d_n_starts
    @corridor_profile_d_n_starts.setter
    def corridor_profile_d_n_starts(self, value): self.corridor.corridor_profile_d_n_starts = value

    @property
    def corridor_profile_d_jitter_n(self): return self.corridor.corridor_profile_d_jitter_n
    @corridor_profile_d_jitter_n.setter
    def corridor_profile_d_jitter_n(self, value): self.corridor.corridor_profile_d_jitter_n = value

    @property
    def corridor_profile_d_jitter_L(self): return self.corridor.corridor_profile_d_jitter_L
    @corridor_profile_d_jitter_L.setter
    def corridor_profile_d_jitter_L(self, value): self.corridor.corridor_profile_d_jitter_L = value

    @property
    def corridor_profile_d_rng_seed(self): return self.corridor.corridor_profile_d_rng_seed
    @corridor_profile_d_rng_seed.setter
    def corridor_profile_d_rng_seed(self, value): self.corridor.corridor_profile_d_rng_seed = value

    @property
    def corridor_profile_d_fit_auto_n_starts(self): return self.corridor.corridor_profile_d_fit_auto_n_starts
    @corridor_profile_d_fit_auto_n_starts.setter
    def corridor_profile_d_fit_auto_n_starts(self, value): self.corridor.corridor_profile_d_fit_auto_n_starts = value

    @property
    def corridor_profile_d_fit_max_n_starts(self): return self.corridor.corridor_profile_d_fit_max_n_starts
    @corridor_profile_d_fit_max_n_starts.setter
    def corridor_profile_d_fit_max_n_starts(self, value): self.corridor.corridor_profile_d_fit_max_n_starts = value

    @property
    def corridor_profile_d_fit_retry_maxfun_scale(self): return self.corridor.corridor_profile_d_fit_retry_maxfun_scale
    @corridor_profile_d_fit_retry_maxfun_scale.setter
    def corridor_profile_d_fit_retry_maxfun_scale(self, value): self.corridor.corridor_profile_d_fit_retry_maxfun_scale = value

    @property
    def corridor_profile_d_seed_gate_keep_nominal_if_refit_worse(self): return self.corridor.corridor_profile_d_seed_gate_keep_nominal_if_refit_worse
    @corridor_profile_d_seed_gate_keep_nominal_if_refit_worse.setter
    def corridor_profile_d_seed_gate_keep_nominal_if_refit_worse(self, value): self.corridor.corridor_profile_d_seed_gate_keep_nominal_if_refit_worse = value

    @property
    def corridor_profile_d_seed_gate_tol_rel(self): return self.corridor.corridor_profile_d_seed_gate_tol_rel
    @corridor_profile_d_seed_gate_tol_rel.setter
    def corridor_profile_d_seed_gate_tol_rel(self, value): self.corridor.corridor_profile_d_seed_gate_tol_rel = value

    @property
    def corridor_profile_d_seed_gate_tol_abs(self): return self.corridor.corridor_profile_d_seed_gate_tol_abs
    @corridor_profile_d_seed_gate_tol_abs.setter
    def corridor_profile_d_seed_gate_tol_abs(self, value): self.corridor.corridor_profile_d_seed_gate_tol_abs = value

    @property
    def corridor_profile_d_polish_maxfun(self): return self.corridor.corridor_profile_d_polish_maxfun
    @corridor_profile_d_polish_maxfun.setter
    def corridor_profile_d_polish_maxfun(self, value): self.corridor.corridor_profile_d_polish_maxfun = value

    @property
    def corridor_profile_d_parallel_walks(self): return self.corridor.corridor_profile_d_parallel_walks
    @corridor_profile_d_parallel_walks.setter
    def corridor_profile_d_parallel_walks(self, value): self.corridor.corridor_profile_d_parallel_walks = value

    @property
    def corridor_profile_d_auto_relax_threshold(self): return self.corridor.corridor_profile_d_auto_relax_threshold
    @corridor_profile_d_auto_relax_threshold.setter
    def corridor_profile_d_auto_relax_threshold(self, value): self.corridor.corridor_profile_d_auto_relax_threshold = value

    @property
    def corridor_profile_d_auto_relax_epsilon(self): return self.corridor.corridor_profile_d_auto_relax_epsilon
    @corridor_profile_d_auto_relax_epsilon.setter
    def corridor_profile_d_auto_relax_epsilon(self, value): self.corridor.corridor_profile_d_auto_relax_epsilon = value

    @property
    def corridor_scientific_nominal_enabled(self): return self.corridor.corridor_scientific_nominal_enabled
    @corridor_scientific_nominal_enabled.setter
    def corridor_scientific_nominal_enabled(self, value): self.corridor.corridor_scientific_nominal_enabled = value

    @property
    def corridor_profile_d_parabola_half_window_pts(self): return self.corridor.corridor_profile_d_parabola_half_window_pts
    @corridor_profile_d_parabola_half_window_pts.setter
    def corridor_profile_d_parabola_half_window_pts(self, value): self.corridor.corridor_profile_d_parabola_half_window_pts = value

    @property
    def corridor_profile_d_symmetric_center_mode(self): return self.corridor.corridor_profile_d_symmetric_center_mode
    @corridor_profile_d_symmetric_center_mode.setter
    def corridor_profile_d_symmetric_center_mode(self, value): self.corridor.corridor_profile_d_symmetric_center_mode = value

    @property
    def corridor_profile_d_adaptive_rmse_ref_half_width_nm(self): return self.corridor.corridor_profile_d_adaptive_rmse_ref_half_width_nm
    @corridor_profile_d_adaptive_rmse_ref_half_width_nm.setter
    def corridor_profile_d_adaptive_rmse_ref_half_width_nm(self, value): self.corridor.corridor_profile_d_adaptive_rmse_ref_half_width_nm = value

    @property
    def corridor_profile_d_adaptive_rmse_probe_steps_each_side(self): return self.corridor.corridor_profile_d_adaptive_rmse_probe_steps_each_side
    @corridor_profile_d_adaptive_rmse_probe_steps_each_side.setter
    def corridor_profile_d_adaptive_rmse_probe_steps_each_side(self, value): self.corridor.corridor_profile_d_adaptive_rmse_probe_steps_each_side = value

    @property
    def corridor_profile_d_adaptive_rmse_noise_factor(self): return self.corridor.corridor_profile_d_adaptive_rmse_noise_factor
    @corridor_profile_d_adaptive_rmse_noise_factor.setter
    def corridor_profile_d_adaptive_rmse_noise_factor(self, value): self.corridor.corridor_profile_d_adaptive_rmse_noise_factor = value

    @property
    def corridor_profile_d_adaptive_rmse_min(self): return self.corridor.corridor_profile_d_adaptive_rmse_min
    @corridor_profile_d_adaptive_rmse_min.setter
    def corridor_profile_d_adaptive_rmse_min(self, value): self.corridor.corridor_profile_d_adaptive_rmse_min = value

    @property
    def corridor_reg_sensitivity_enabled(self): return self.corridor.corridor_reg_sensitivity_enabled
    @corridor_reg_sensitivity_enabled.setter
    def corridor_reg_sensitivity_enabled(self, value): self.corridor.corridor_reg_sensitivity_enabled = value

    @property
    def corridor_reg_sensitivity_points(self): return self.corridor.corridor_reg_sensitivity_points
    @corridor_reg_sensitivity_points.setter
    def corridor_reg_sensitivity_points(self, value): self.corridor.corridor_reg_sensitivity_points = value

    @property
    def corridor_reg_sensitivity_decades(self): return self.corridor.corridor_reg_sensitivity_decades
    @corridor_reg_sensitivity_decades.setter
    def corridor_reg_sensitivity_decades(self, value): self.corridor.corridor_reg_sensitivity_decades = value

    @property
    def corridor_reg_sensitivity_n_workers(self): return self.corridor.corridor_reg_sensitivity_n_workers
    @corridor_reg_sensitivity_n_workers.setter
    def corridor_reg_sensitivity_n_workers(self, value): self.corridor.corridor_reg_sensitivity_n_workers = value

    @property
    def corridor_bootstrap_enabled(self): return self.bootstrap.corridor_bootstrap_enabled
    @corridor_bootstrap_enabled.setter
    def corridor_bootstrap_enabled(self, value): self.bootstrap.corridor_bootstrap_enabled = value

    @property
    def corridor_bootstrap_n(self): return self.bootstrap.corridor_bootstrap_n
    @corridor_bootstrap_n.setter
    def corridor_bootstrap_n(self, value): self.bootstrap.corridor_bootstrap_n = value

    @property
    def corridor_bootstrap_seed(self): return self.bootstrap.corridor_bootstrap_seed
    @corridor_bootstrap_seed.setter
    def corridor_bootstrap_seed(self, value): self.bootstrap.corridor_bootstrap_seed = value

    @property
    def corridor_bootstrap_percentile(self): return self.bootstrap.corridor_bootstrap_percentile
    @corridor_bootstrap_percentile.setter
    def corridor_bootstrap_percentile(self, value): self.bootstrap.corridor_bootstrap_percentile = value

    @property
    def corridor_bootstrap_sigma_t(self): return self.bootstrap.corridor_bootstrap_sigma_t
    @corridor_bootstrap_sigma_t.setter
    def corridor_bootstrap_sigma_t(self, value): self.bootstrap.corridor_bootstrap_sigma_t = value

    @property
    def corridor_bootstrap_sigma_r(self): return self.bootstrap.corridor_bootstrap_sigma_r
    @corridor_bootstrap_sigma_r.setter
    def corridor_bootstrap_sigma_r(self, value): self.bootstrap.corridor_bootstrap_sigma_r = value

    @property
    def corridor_bootstrap_mode(self): return self.bootstrap.corridor_bootstrap_mode
    @corridor_bootstrap_mode.setter
    def corridor_bootstrap_mode(self, value): self.bootstrap.corridor_bootstrap_mode = value

    @property
    def corridor_bootstrap_block_len(self): return self.bootstrap.corridor_bootstrap_block_len
    @corridor_bootstrap_block_len.setter
    def corridor_bootstrap_block_len(self, value): self.bootstrap.corridor_bootstrap_block_len = value

    @property
    def corridor_bootstrap_quick_refit(self): return self.bootstrap.corridor_bootstrap_quick_refit
    @corridor_bootstrap_quick_refit.setter
    def corridor_bootstrap_quick_refit(self, value): self.bootstrap.corridor_bootstrap_quick_refit = value

    @property
    def corridor_bootstrap_quick_refit_maxfun(self): return self.bootstrap.corridor_bootstrap_quick_refit_maxfun
    @corridor_bootstrap_quick_refit_maxfun.setter
    def corridor_bootstrap_quick_refit_maxfun(self, value): self.bootstrap.corridor_bootstrap_quick_refit_maxfun = value

    @property
    def corridor_bootstrap_n_workers(self): return self.bootstrap.corridor_bootstrap_n_workers
    @corridor_bootstrap_n_workers.setter
    def corridor_bootstrap_n_workers(self, value): self.bootstrap.corridor_bootstrap_n_workers = value

    @property
    def nonlinear_alpha_refinement_enabled(self): return self.nonlinear_alpha.nonlinear_alpha_refinement_enabled
    @nonlinear_alpha_refinement_enabled.setter
    def nonlinear_alpha_refinement_enabled(self, value): self.nonlinear_alpha.nonlinear_alpha_refinement_enabled = value

    @property
    def nonlinear_alpha_budget_mode(self): return self.nonlinear_alpha.nonlinear_alpha_budget_mode
    @nonlinear_alpha_budget_mode.setter
    def nonlinear_alpha_budget_mode(self, value): self.nonlinear_alpha.nonlinear_alpha_budget_mode = value

    @property
    def nonlinear_alpha_second_pass_enabled(self): return self.nonlinear_alpha.nonlinear_alpha_second_pass_enabled
    @nonlinear_alpha_second_pass_enabled.setter
    def nonlinear_alpha_second_pass_enabled(self, value): self.nonlinear_alpha.nonlinear_alpha_second_pass_enabled = value

    @property
    def nonlinear_alpha_second_pass_maxfun(self): return self.nonlinear_alpha.nonlinear_alpha_second_pass_maxfun
    @nonlinear_alpha_second_pass_maxfun.setter
    def nonlinear_alpha_second_pass_maxfun(self, value): self.nonlinear_alpha.nonlinear_alpha_second_pass_maxfun = value

    @property
    def nl_alpha_adaptive_early_stop(self): return self.nonlinear_alpha.nl_alpha_adaptive_early_stop
    @nl_alpha_adaptive_early_stop.setter
    def nl_alpha_adaptive_early_stop(self, value): self.nonlinear_alpha.nl_alpha_adaptive_early_stop = value

    @property
    def nl_alpha_pure_spectral(self): return self.nonlinear_alpha.nl_alpha_pure_spectral
    @nl_alpha_pure_spectral.setter
    def nl_alpha_pure_spectral(self, value): self.nonlinear_alpha.nl_alpha_pure_spectral = value

    @property
    def nl_alpha_bisection_refine(self): return self.nonlinear_alpha.nl_alpha_bisection_refine
    @nl_alpha_bisection_refine.setter
    def nl_alpha_bisection_refine(self, value): self.nonlinear_alpha.nl_alpha_bisection_refine = value

    @property
    def nl_alpha_bisection_max_iter(self): return self.nonlinear_alpha.nl_alpha_bisection_max_iter
    @nl_alpha_bisection_max_iter.setter
    def nl_alpha_bisection_max_iter(self, value): self.nonlinear_alpha.nl_alpha_bisection_max_iter = value

    # --- Legacy Composition & View Methods (P4 Scaffold Compatibility) ---
    def compose(self):
        return self

    def pglobal_view(self): return self.pglobal
    def smart_init_view(self): return self.smart_init
    def corridor_view(self): return self.corridor
    def bootstrap_view(self): return self.bootstrap
    def nonlinear_alpha_view(self): return self.nonlinear_alpha




def sol3_phase1_maxfun_effective_from_view(view: SplinePGlobalConfig) -> int:

    """View-based core of :func:`sol3_phase1_maxfun_effective` (Lot B2).

    Takes the read-only :class:`SplinePGlobalConfig`; all information needed
    comes from the pglobal sub-domain.
    """

    v = view.sol3_phase1_maxfun
    if v is None:
        return 10000
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return 10000
    if iv <= 0:
        return 10000
    return int(max(300, iv))


def sol3_phase1_maxfun_effective(cfg: SplineOptConfig) -> int:

    """L-BFGS-B ``maxfun`` for SOL3 / SOL3b phase 1 (descent). Legacy default 10000 if unset or non-positive."""

    return sol3_phase1_maxfun_effective_from_view(cfg.pglobal_view())


def corridor_profile_refit_maxfun_from_views(
    corridor: SplineCorridorConfig,
    pglobal: SplinePGlobalConfig,
    override: int | None = None,
) -> int:

    """View-based core of :func:`corridor_profile_refit_maxfun` (Lot B2).

    Uses ``corridor.corridor_profile_d_polish_maxfun`` and falls back to
    ``pglobal.polish_maxfun`` when unset/non-positive.
    """

    if override is not None:
        return int(max(300, int(override)))
    v = corridor.corridor_profile_d_polish_maxfun
    if v is not None:
        try:
            iv = int(v)
            if iv > 0:
                return int(max(300, iv))
        except (TypeError, ValueError):
            pass
    pm = int(pglobal.polish_maxfun or 4000)
    return int(max(300, pm))


def corridor_profile_refit_maxfun(cfg: SplineOptConfig, override: int | None = None) -> int:

    """Effective L-BFGS-B budget for each d profiling refit (floor 300)."""

    return corridor_profile_refit_maxfun_from_views(
        cfg.corridor_view(), cfg.pglobal_view(), override=override,
    )


# Minimum number of spectral points in the objective mask (after RMSE window if active).


SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS: int = 3


class SmartInitPreviewCancelled(Exception):

    """User cancellation after Smart Init preview."""


def reset_smart_init_preview_guard(cfg: SplineOptConfig | None = None) -> None:

    """Allows the Smart Init dialog again for a new run (``cfg.smart_init_preview_shown = False``)."""

    if cfg is not None:

        cfg.smart_init_preview_shown = False


def _flog_spectral_rmse_field(x: Any) -> str:

    if x is None:

        return "n/a"

    try:

        fx = float(x)

    except (TypeError, ValueError):

        return "n/a"

    return f"{fx:.8f}" if np.isfinite(fx) else "n/a"


def _log_smart_coaching_advice(logger: logging.Logger, r: dict) -> None:

    """Proactive coaching: analyzes results to suggest pipeline or config improvements."""

    prefix = "SMART COACHING |"

    # 1. Analyze RMSE

    rmse = r.get("rmse")

    if rmse is not None:

        try:

            frmse = float(rmse)

            if frmse > 0.05:
                logger.debug("%s High RMSE (%.4f) detected.", prefix, frmse)
            elif frmse > 0.02:
                logger.debug("%s Moderate RMSE (%.4f).", prefix, frmse)

        except (ValueError, TypeError):

            pass

    # 2. Analyze n hitting bounds

    n_nodes = r.get("n_nodes_physical")

    if n_nodes is not None:

        n_nod = np.asarray(n_nodes, dtype=np.float64)

        if np.any(n_nod <= N_MIN_LIMIT + 0.01) or np.any(n_nod >= N_MAX_LIMIT - 0.01):
            logger.debug("%s Index 'n' is hitting physical limits (%.2f-%.2f). Thickness or substrate index might be off.", prefix, N_MIN_LIMIT, N_MAX_LIMIT)

    # 3. Analyze k hitting floor

    L_nodes = r.get("L_nodes")

    if L_nodes is not None:

        L_nod = np.asarray(L_nodes, dtype=np.float64)

        k_val = np.exp(L_nod)

        # Using a typical floor heuristic

        if np.any(k_val <= 1.1e-4):
            logger.debug("%s Extinction 'k' is hitting the floor (normal for transparent films).", prefix)

    # 4. Check mesh polish

    rs = r.get("spectral_rmse_seg_spline_sigma")

    rref = r.get("spectral_rmse_segments")

    if rs is not None and rref is not None:

        try:

            frs = float(rs)

            frref = float(rref)

            if frs > frref * 1.5:
                logger.debug("%s Cubic polish significantly increased RMSE. Suggestion: Your node grid might be too sparse.", prefix)

        except (ValueError, TypeError):

            pass


def _log_spectral_mesh_polish_rmse_block(logger: logging.Logger, r: dict) -> None:

    """Spectral RMSE: sigma-spline mesh polish + solver ref before polish + best model."""

    rs = r.get("spectral_rmse_seg_spline_sigma")

    rref = r.get("spectral_rmse_segments")

    if (

        (rs is not None and np.isfinite(float(rs)))

        or (rref is not None and np.isfinite(float(rref)))

    ):

        logger.debug(
            "Spectral RMSE (mesh polish) - cubic sigma-spline=%s | solver ref (before polish)=%s",
            _flog_spectral_rmse_field(rs),
            _flog_spectral_rmse_field(rref),
        )

    _log_smart_coaching_advice(logger, r)

    bl = r.get("spectral_rmse_best_label")

    bv = r.get("spectral_rmse_best_value")

    if bl is not None and bv is not None and np.isfinite(float(bv)):

        logger.debug(
            "Best model (spectral RMSE): %s = %.8f",
            str(bl),
            float(bv),
        )


def _log_index_spline_best_config(

    logger: logging.Logger | None,

    r: dict,

    rmse: float,

    title: str = "[BEST RMSE]",


) -> None:

    """Log RMSE, thickness, mesh polish RMSE block, node table (if consistent)."""

    if logger is None:

        return

    sk = np.asarray(r.get("sigma_knots", []), dtype=np.float64).ravel()

    k = int(sk.size)

    if k == 0:

        logger.info("%s RMSE=%.8f | missing sigma_knots in result snapshot", title, float(rmse))

        return

    n_n = np.asarray(r.get("n_nodes_physical", []), dtype=np.float64).ravel()

    L_n = np.asarray(r.get("L_nodes", []), dtype=np.float64).ravel()

    xa_raw = r.get("x")

    xa = np.asarray(xa_raw, dtype=np.float64).ravel() if xa_raw is not None else None

    n_mono = r.get("n_mono_band_nm")

    if (n_n.size != k) and xa is not None and xa.size == 1 + 2 * k:

        n_n = x_slice_n_to_physical_nodes(xa[1 : 1 + k], sk, n_mono)

    if (L_n.size != k) and xa is not None and xa.size == 1 + 2 * k:

        L_n = np.asarray(xa[1 + k : 1 + 2 * k], dtype=np.float64).ravel()

    if n_n.size != k or L_n.size != k:

        logger.info(

            "%s RMSE=%.8f | d_nm=%s | node shape mismatch (K=%d, len(n)=%d, len(L)=%d)",

            title,

            float(rmse),

            r.get("d_nm"),

            k,

            int(n_n.size),

            int(L_n.size),

        )

        if xa is not None:

            logger.info("  x = %s", np.array2string(xa, precision=12, separator=", ", max_line_width=240))

        _log_spectral_mesh_polish_rmse_block(logger, r)

        return

    d_from_dict = float(r.get("d_nm", float("nan")))

    d_from_x = float(xa[0]) if xa is not None and xa.size > 0 else float("nan")

    # After mesh polish or rmse/mse recalculation, dict d_nm may differ from x[0] (solver vector).

    if np.isfinite(d_from_dict):

        d_nm = d_from_dict

    elif np.isfinite(d_from_x):

        d_nm = d_from_x

    else:

        d_nm = float("nan")

    if np.isfinite(d_from_dict) and np.isfinite(d_from_x) and abs(d_from_dict - d_from_x) > 0.01:

        logger.info(

            "%s note d_nm: dict=%.6f nm ≠ x[0]=%.6f nm - displaying dict thickness (aligned with recalculated rmse/mse).",

            title,

            d_from_dict,

            d_from_x,

        )

    x_encoding = str(r.get("x_encoding", "?"))

    logger.info("%s RMSE=%.8f | d_nm=%.6f nm | K=%d sigma knots | x_encoding=%s", title, float(rmse), d_nm, k, x_encoding)

    _log_spectral_mesh_polish_rmse_block(logger, r)

    for i in range(k):
        sig = float(sk[i])
        lam_i = 1.0 / max(sig, 1e-30)
        logger.debug(
            "  #%02d sigma=%.10e nm^-1 | lambda=%.4f nm | n=%.8f | ln(k)=%.8f",
            i, sig, lam_i, float(n_n[i]), float(L_n[i]),
        )

    if xa is not None:
        logger.debug(
            "  x [%d] (d, then n or xi, then L=ln(k)): %s",
            xa.size, np.array2string(xa, precision=12, separator=", ", max_line_width=240),
        )


def _log_spline_pipeline_json(

    log: logging.Logger, event: str, *, seq: str | None = None, **fields: Any


) -> None:

    """Structured spline pipeline log (grep: SPLINE_PIPELINE_JSON)."""

    log_structured_json_event(log, "SPLINE_PIPELINE_JSON", event, seq=seq, **fields)


def reconcile_spline_x_warm_for_config(

    x: np.ndarray,

    sigma_knots: np.ndarray,

    *,

    n_mono_target: tuple[float, float] | None,

    x_encoding_in: str,

    n_mono_band_for_xi_decode: tuple[float, float] | None = None,


) -> np.ndarray:

    """Adapts a loaded ``x`` vector (JSON export, other run) to current mono config."""

    x = np.asarray(x, dtype=np.float64).ravel().copy()

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    K = int(sk.size)

    if x.size != 1 + 2 * K:

        return x

    n_part = x[1 : 1 + K]

    if n_mono_target is not None and x_encoding_in == "n_physical":

        x[1 : 1 + K] = physical_nodes_to_x_slice_n(n_part, sk, n_mono_target)

    elif n_mono_target is None and x_encoding_in == "xi_n_mono":

        band = n_mono_band_for_xi_decode

        if band is not None:

            x[1 : 1 + K] = x_slice_n_to_physical_nodes(n_part, sk, band)

    return x


def warm_start_interpolate_nodes(

    x_prev: np.ndarray,

    n_seg_prev: int,

    n_seg_new: int,

    lam_min_nm: float,

    lam_max_nm: float,

    L_lo: float,

    L_hi: float,

    *,

    n_mono_band_nm: tuple[float, float] | None = None,


) -> np.ndarray:

    """Spread d, n_j and L_j on the new sigma grid (linear interpolation)."""

    ko = int(n_seg_prev) + 1

    kn = int(n_seg_new) + 1

    sig_o = build_sigma_knots(lam_min_nm, lam_max_nm, n_seg_prev)

    sig_n = build_sigma_knots(lam_min_nm, lam_max_nm, n_seg_new)

    xp = np.asarray(x_prev, float).ravel()

    d = float(xp[0])

    n_o_phys = x_slice_n_to_physical_nodes(xp[1 : 1 + ko], sig_o, n_mono_band_nm)

    L_o = xp[1 + ko : 1 + 2 * ko]

    n_n_phys = np.interp(sig_n, sig_o, n_o_phys)

    L_n = np.interp(sig_n, sig_o, L_o)

    n_n = physical_nodes_to_x_slice_n(n_n_phys, sig_n, n_mono_band_nm)

    L_n = np.clip(L_n, L_lo, L_hi)

    return np.concatenate(([d], n_n, L_n))


def _rmse_fit_lambda_inside_mask(

    lam_nm: np.ndarray,

    rmse_fit_lambda_nm: tuple[float, float] | None,


) -> np.ndarray:

    """Boolean mask True on lambda in the RMSE window (all True if no window)."""

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    if rmse_fit_lambda_nm is None:

        return np.ones(lam.size, dtype=bool)

    lo = float(min(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

    hi = float(max(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

    return (lam >= lo) & (lam <= hi) & np.isfinite(lam)


def nan_nk_outside_rmse_lambda_window(

    lam_nm: np.ndarray,

    n_lam: np.ndarray,

    k_lam: np.ndarray,

    rmse_fit_lambda_nm: tuple[float, float] | None,


) -> tuple[np.ndarray, np.ndarray]:

    """Copies n, k with NaN outside the ``rmse_fit_lambda_nm`` band (display / export)."""

    n_out = np.asarray(n_lam, dtype=np.float64).copy()

    k_out = np.asarray(k_lam, dtype=np.float64).copy()

    if rmse_fit_lambda_nm is None:

        return n_out, k_out

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    if lam.size != n_out.size or lam.size != k_out.size:

        return n_out, k_out

    ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

    n_out[~ins] = np.nan

    k_out[~ins] = np.nan

    return n_out, k_out


def apply_rmse_fit_window_nk_nan_to_result(

    out: dict[str, Any],

    rmse_fit_lambda_nm: tuple[float, float] | None,


) -> dict[str, Any]:

    """

    Sets n_lam, k_lam (and displayed derived fields) to NaN outside the RMSE window.

    ``t_theo`` / ``r_theo`` remain on the full spectral grid.

    """

    if rmse_fit_lambda_nm is None:

        return out

    lam = np.asarray(out.get("lam_nm"), dtype=np.float64).ravel()

    if not lam.size or "n_lam" not in out or "k_lam" not in out:

        return out

    n_new, k_new = nan_nk_outside_rmse_lambda_window(

        lam, out["n_lam"], out["k_lam"], rmse_fit_lambda_nm

    )

    out["n_lam"] = n_new

    out["k_lam"] = k_new

    if "ln_k_lam" in out:

        lk = np.asarray(out["ln_k_lam"], dtype=np.float64).ravel().copy()

        if lk.size == lam.size:

            ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

            lk[~ins] = np.nan

            out["ln_k_lam"] = lk

    # Corridors (profiling on d): mask in the same way as n_lam/k_lam.

    for key in (

        "corridor_n_lo",

        "corridor_n_hi",

        "corridor_k_lo",

        "corridor_k_hi",

        "corridor_reference_n_lam",

        "corridor_reference_k_lam",

        "boot_corridor_n_lo",

        "boot_corridor_n_hi",

        "boot_corridor_k_lo",

        "boot_corridor_k_hi",

        "boot_corridor_L_lo",

        "boot_corridor_L_hi",

    ):

        arr = out.get(key)

        if arr is None:

            continue

        a = np.asarray(arr, dtype=np.float64).ravel().copy()

        if a.size != lam.size:

            continue

        ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

        a[~ins] = np.nan

        out[key] = a

    return out


def snapshot_result_with_rmse_fit_meta(

    cfg: SplineOptConfig,

    d: dict[str, Any],


) -> dict[str, Any]:

    """Copies result + ``rmse_fit_lambda_nm`` key (title / SMART) then masks n,k outside the band."""

    o = dict(d)

    o["rmse_fit_lambda_nm"] = cfg.rmse_fit_lambda_nm

    return apply_rmse_fit_window_nk_nan_to_result(o, cfg.rmse_fit_lambda_nm)


def _bounds_x0_for_sigma_knots(

    cfg: SplineOptConfig,

    sk: np.ndarray,


) -> tuple[np.ndarray, np.ndarray, float, float]:

    """Bounds and default x0 for a given sigma grid (K = len(sk) knots)."""

    sk = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk.size)

    dim = 1 + 2 * k

    k_hi = float(min(max(cfg.k_clip_hi, cfg.k_clip_lo * 1.0001), float(K_MAX_LIMIT)))

    L_lo = float(max(np.log(max(cfg.k_clip_lo, 1e-30)), L_LNK_MIN_PHYS))

    L_hi = float(np.log(k_hi))

    bounds = np.zeros((dim, 2), dtype=np.float64)

    bounds[0] = [float(min(cfg.d_lo, cfg.d_hi)), float(max(cfg.d_lo, cfg.d_hi))]

    xi_lo, xi_hi = N_MONO_XI_BOUNDS

    if cfg.n_mono_band_nm is None:

        bounds[1 : 1 + k] = [N_MIN_LIMIT, N_MAX_LIMIT]

    else:

        bounds[1 : 1 + k] = [float(xi_lo), float(xi_hi)]

    bounds[1 + k : 1 + 2 * k] = [L_lo, L_hi]

    x0 = 0.5 * (bounds[:, 0] + bounds[:, 1])

    x0[0] = float(np.clip(0.5 * (cfg.d_lo + cfg.d_hi), bounds[0, 0], bounds[0, 1]))

    if cfg.n_mono_band_nm is None:

        x0[1 : 1 + k] = np.clip(1.65, N_MIN_LIMIT, N_MAX_LIMIT)

    else:

        n_flat = np.full(k, 1.65, dtype=np.float64)

        x0[1 : 1 + k] = physical_nodes_to_x_slice_n(n_flat, sk, cfg.n_mono_band_nm)

    x0[1 + k : 1 + 2 * k] = np.clip(np.log(1e-3), L_lo, L_hi)

    return bounds, x0, L_lo, L_hi


def build_x0_smart_preview_exact(

    cfg: SplineOptConfig,

    sk: np.ndarray,

    ne: np.ndarray,

    Le: np.ndarray,

    d_nm: float | None,

    *,

    relax_n_mono: bool = False,


) -> tuple[np.ndarray, np.ndarray]:

    """(bounds, x0) identical to the ``sk_exact`` block of ``make_bounds_and_x0`` (without cfg mutation)."""

    sk_a = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk_a.size)

    ne_a = np.asarray(ne, dtype=np.float64).ravel()

    Le_a = np.asarray(Le, dtype=np.float64).ravel()

    if ne_a.size != k or Le_a.size != k:

        raise ValueError("build_x0_smart_preview_exact: mismatching sizes for ne, Le and sk")

    bounds, x0, L_lo, L_hi = _bounds_x0_for_sigma_knots(cfg, sk_a)

    relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

    if cfg.n_mono_band_nm is None or relax_eff:

        x0[1 : 1 + k] = np.clip(ne_a, N_MIN_LIMIT, N_MAX_LIMIT)

    else:

        x0[1 : 1 + k] = physical_nodes_to_x_slice_n(ne_a, sk_a, cfg.n_mono_band_nm)

    x0[1 + k : 1 + 2 * k] = np.clip(Le_a, L_lo, L_hi)

    if d_nm is not None and np.isfinite(float(d_nm)):

        x0[0] = float(np.clip(float(d_nm), bounds[0, 0], bounds[0, 1]))

    return bounds, x0


def make_bounds_and_x0(

    cfg: SplineOptConfig, *, skip_smart_init: bool = False


) -> tuple[np.ndarray, np.ndarray, np.ndarray]:

    """n bounds via certus_core; L_j = ln k_j, k clipped after interpolation.

    If ``skip_smart_init`` is true, does not launch Swanepoel / preview hook (warm-start or bootstrap).

    """

    from spline_smart_init import (

        compute_smart_init_spectral_preview,

        guess_smart_x0_from_extrema,

        interp_n_L_pwlnk_to_sigmas,

    )

    # Do not let ``x0_warm`` overwrite d / n / L after Smart Init (manual dialog).

    skip_x0_warm = False

    lam_min = float(np.min(cfg.lam_nm))

    lam_max = float(np.max(cfg.lam_nm))

    sig_edge_lo = 1.0 / max(lam_max, 1e-9)

    sig_edge_hi = 1.0 / max(lam_min, 1e-9)

    s_lo, s_hi = float(min(sig_edge_lo, sig_edge_hi)), float(max(sig_edge_lo, sig_edge_hi))

    # Optimization mesh: single source of truth. K is 12 or 14 depending on lambda_max (IR extension).

    # cfg.n_seg must always be K-1 to remain aligned with SplinePWLObjective and workers.

    sk = canonical_spline_sigma_knots(lam_min, lam_max, **_canonical_knots_min_lambda_kw(cfg))

    k = int(sk.size)

    cfg.n_seg = k - 1

    # rmse_fit_lambda_nm only truncates the spectral MSE term **points**; the sigma mesh follows the **entire** file.

    rfw = getattr(cfg, "rmse_fit_lambda_nm", None)

    if rfw is not None:

        lo_w = float(min(rfw[0], rfw[1]))

        hi_w = float(max(rfw[0], rfw[1]))

        try:

            from spline_objective import _spline_objective_lam_mask

            n_pix_obj = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

        except NUMERICAL_FAULT_EXCEPTIONS:

            logger.debug(

                "_spline_objective_lam_mask failed in make_bounds_and_x0", exc_info=True

            )

            n_pix_obj = -1

        if lam_max > hi_w + 0.5 or lam_min < lo_w - 0.5:

            logger.info(

                "INDEX_SPLINE | File lambda [%.2f, %.2f] nm -> canonical sigma mesh K=%d (e.g. IR node at lambda~%.1f nm) ; "

                "rmse_fit_lambda_nm [%.2f, %.2f] nm -> **%d pixels** in spectral MSE only "

                "(lambda > %.2f nm do not count in error, but sigma nodes remain anchored on file lambda_max).",

                lam_min,

                lam_max,

                k,

                lam_max,

                lo_w,

                hi_w,

                n_pix_obj,

                hi_w,

            )

    if cfg.sigma_knots_override is not None:

        logger.info(

            "INDEX_SPLINE: sigma_knots_override ignored - fixed mesh K=%d sigma knots (%d segments).",

            k,

            int(cfg.n_seg),

        )

    dim = 1 + 2 * k

    bounds, x0, L_lo, L_hi = _bounds_x0_for_sigma_knots(cfg, sk)

    # --- NEW : PRIORITE A L'INJECTION MANUELLE ---

    # If we have exact knots or a pending override, we do NOT launch Swanepoel

    has_exact = getattr(cfg, "smart_preview_exact_sigma_knots", None) is not None

    has_over = getattr(cfg, "smart_preview_node_override", None) is not None

    if (

        not skip_smart_init

        and not (has_exact or has_over)

        and cfg.x0_warm is None

        and cfg.t_exp is not None

        and getattr(cfg, "n_sub", None) is not None

    ):

        logger.info(

            "INDEX_SPLINE [Smart Init]: launching Swanepoel on fixed mesh (%s segments -> %s sigma knots) ; "

            "manual dialog: values re-interpolated on canonical grid if needed.",

            int(cfg.n_seg),

            int(k),

        )

        smart_n, smart_L = guess_smart_x0_from_extrema(

            cfg.lam_nm,

            cfg.t_exp,

            cfg.n_sub,

            0.5 * (cfg.d_lo + cfg.d_hi),

            sk

        )

        if smart_n is not None and smart_L is not None:

            if cfg.n_mono_band_nm is None:

                x0[1 : 1 + k] = np.clip(smart_n, N_MIN_LIMIT, N_MAX_LIMIT)

            else:

                x0[1 : 1 + k] = physical_nodes_to_x_slice_n(smart_n, sk, cfg.n_mono_band_nm)

            x0[1 + k : 1 + 2 * k] = np.clip(smart_L, L_lo, L_hi)

            logger.info(

                "INDEX_SPLINE [Smart Init]: success - injecting n and L profiles from interference extrema."

            )

            with np.printoptions(precision=3, suppress=True):

                logger.debug(" -> Profile n_init = %s", np.array2string(smart_n, separator=', '))

                logger.debug(" -> Profile L_init = %s", np.array2string(smart_L, separator=', '))

            with np.printoptions(precision=1, suppress=True):

                logger.debug(" -> Approx k_init = %s", np.array2string(np.exp(smart_L), separator=', '))

            n_prev = np.asarray(smart_n, dtype=np.float64).ravel()

            L_prev = np.asarray(smart_L, dtype=np.float64).ravel()

        else:

            logger.warning(

                "INDEX_SPLINE [Smart Init]: failed (not enough clear fringes or very noisy). Standard fallback (1.65 / 1e-3)."

            )

            if cfg.n_mono_band_nm is None:

                n_prev = np.clip(x0[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT)

            else:

                n_prev = x_slice_n_to_physical_nodes(x0[1 : 1 + k], sk, cfg.n_mono_band_nm)

            L_prev = np.clip(x0[1 + k : 1 + 2 * k], L_lo, L_hi)

            logger.info(

                "INDEX_SPLINE [Smart Init]: manual dialog with standard x0 (Swanepoel unavailable)."

            )

        hook = getattr(cfg, "smart_init_preview_hook", None)

        logger.info(
            "INDEX_SPLINE [Smart Init]: preview dispatch check | hook=%s | preview_shown=%s | K_sigma=%d",
            "set" if hook is not None else "none",
            bool(getattr(cfg, "smart_init_preview_shown", False)),
            int(k),
        )

        if hook is not None and not bool(getattr(cfg, "smart_init_preview_shown", False)):

            pv = compute_smart_init_spectral_preview(

                cfg, sk, n_prev, L_prev, uniform_sigma_nodes=11

            )

            logger.info(
                "INDEX_SPLINE [Smart Init]: preview payload built | pv_present=%s | keys=%s",
                bool(pv is not None),
                sorted(list(pv.keys())) if isinstance(pv, dict) else [],
            )

            if pv is not None:

                logger.info(
                    "INDEX_SPLINE [Smart Init]: calling GUI hook | payload_K=%d | d_best_nm=%.6f",
                    int(np.asarray(pv.get("sigma_knots", []), dtype=np.float64).size),
                    float(pv.get("d_best_nm", float("nan"))),
                )

                if not hook(pv):

                    raise SmartInitPreviewCancelled

                logger.info("INDEX_SPLINE [Smart Init]: GUI hook returned success, preview marked as shown")

                cfg.smart_init_preview_shown = True

                over = getattr(cfg, "smart_preview_node_override", None)

                # Note: "Continue" sets both node_override and smart_preview_exact_*; the 

                # worker mesh + d are reconstructed in the sk_exact block below. Do not apply over here

                # nor clear smart_preview_d_nm_override - otherwise d falls back to default 

                # (e.g. mid-bounds 1700 nm) while the stored RMSE was calculated with final d 

                # (e.g. 1698 nm) -> factual FALSE mismatch.

                exact_pending = getattr(cfg, "smart_preview_exact_sigma_knots", None) is not None

                if over is not None and not exact_pending:

                    n_ov, L_ov = over

                    n_ov = np.asarray(n_ov, dtype=np.float64).ravel()

                    L_ov = np.asarray(L_ov, dtype=np.float64).ravel()

                    accepted = bool(n_ov.size == k and L_ov.size == k)

                    if accepted:

                        if cfg.n_mono_band_nm is None:

                            x0[1 : 1 + k] = np.clip(n_ov, N_MIN_LIMIT, N_MAX_LIMIT)

                        else:

                            x0[1 : 1 + k] = physical_nodes_to_x_slice_n(n_ov, sk, cfg.n_mono_band_nm)

                        x0[1 + k : 1 + 2 * k] = np.clip(L_ov, L_lo, L_hi)

                        d_ov = getattr(cfg, "smart_preview_d_nm_override", None)

                        if d_ov is not None and np.isfinite(float(d_ov)):

                            x0[0] = float(

                                np.clip(float(d_ov), bounds[0, 0], bounds[0, 1])

                            )

                        logger.info(

                            "INDEX_SPLINE [Smart Init]: x0 = n, L from preview dialog, "

                            "on the %s sigma knots of the fixed mesh; d=%.2f nm.",

                            int(k),

                            float(x0[0]),

                        )

                        skip_x0_warm = True

                    cfg.smart_preview_node_override = None

                    cfg.smart_preview_d_nm_override = None

                elif over is not None and exact_pending:

                    cfg.smart_preview_node_override = None

            else:

                logger.warning("INDEX_SPLINE [Smart Init]: preview payload is None, manual dialog skipped")

                logger.info(

                    "INDEX_SPLINE [Smart Init]: spectral preview ignored "

                    "(wT=0 / no T, or knots mismatch / no hook plot)."

                )

    sk_exact = getattr(cfg, "smart_preview_exact_sigma_knots", None)

    pair_ex = getattr(cfg, "smart_preview_exact_n_L", None)

    if sk_exact is not None and pair_ex is not None:

        sk_e = np.asarray(sk_exact, dtype=np.float64).ravel()

        ne, Le = pair_ex

        ne = np.asarray(ne, dtype=np.float64).ravel()

        Le = np.asarray(Le, dtype=np.float64).ravel()

        cfg.smart_preview_exact_sigma_knots = None

        cfg.smart_preview_exact_n_L = None

        if sk_e.size >= 2 and ne.size == sk_e.size and Le.size == sk_e.size:

            # After "Continue" / Autofind: construct a worker K-canonical grid while preserving 

            # manual knots; we add knots instead of moving the entire mesh.

            _mdl = getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.02)

            try:

                _mdl_f = float(_mdl)

            except (TypeError, ValueError):

                _mdl_f = 0.0

            sk_canon = bridge_sigma_knots_preserve_manual(

                sk_e,

                lam_min,

                lam_max,

                rmse_fit_lambda_nm=getattr(cfg, "rmse_fit_lambda_nm", None),

                min_delta_lambda_over_lambda_mean=_mdl_f if _mdl_f > 0.0 else None,

            )

            # Snap + linear sigma interpolation + edge extrapolation (no np.interp plateau).

            _k_src, _k_cn = int(sk_e.size), int(sk_canon.size)

            ne, Le = interp_n_L_pwlnk_to_sigmas(

                sk_e,

                ne,

                Le,

                sk_canon,

                diag_log=logger if _k_src != _k_cn else None,

                diag_tag="INDEX_SPLINE_smart_init_Ksrc_to_worker_mesh",

            )

            sk = sk_canon

            k = int(sk.size)

            cfg.n_seg = k - 1

            dim = 1 + 2 * k

            d_ex = getattr(cfg, "smart_preview_d_nm_override", None)

            d_use = (

                float(d_ex)

                if (d_ex is not None and np.isfinite(float(d_ex)))

                else None

            )

            bounds, x0 = build_x0_smart_preview_exact(cfg, sk, ne, Le, d_use)

            acc_rmse = getattr(cfg, "smart_preview_accepted_rmse", None)

            rmse_s = ""

            if acc_rmse is not None and np.isfinite(float(acc_rmse)):

                rmse_s = f" RMSE (spline objective, √MSE) after manual tuning: {float(acc_rmse):.6f};"

            logger.info(

                "INDEX_SPLINE [Smart Init]: restarting on worker mesh K=%s sigma nodes / %s segments "

                "(manual nodes preserved + additions if needed); "

                "n and ln k: dialogue snap + linear sigma interp. + edge extrap. (no plateau);%s d=%.2f nm.",

                int(k),

                int(cfg.n_seg),

                rmse_s,

                float(x0[0]),

            )

            ord_sig = np.argsort(sk)

            for rank, idx in enumerate(ord_sig, start=1):

                sigv = float(sk[idx])

                lamv = 1.0 / max(sigv, 1e-30)

                logger.info(

                    "INDEX_SPLINE [Smart Init]:   knot %2d/%2d  lambda=%10.4f nm  sigma=%.10e nm⁻1  n=%.6f  ln k=%.6f  k=%.4e",

                    rank,

                    int(k),

                    lamv,

                    sigv,

                    float(ne[idx]),

                    float(Le[idx]),

                    float(np.exp(float(Le[idx]))),

                )

            cfg.pglobal_trust_region_by_k = True

            cfg.pglobal_trust_rho_lo = 0.045

            cfg.pglobal_trust_rho_hi = 0.14

            logger.info(

                "INDEX_SPLINE [Smart Init]: PGlobal trust box [%.3f, %.3f] (after manual tuning in dialog).",

                float(cfg.pglobal_trust_rho_lo),

                float(cfg.pglobal_trust_rho_hi),

            )

            # Lock the number of sigma for stages that refuse fusion / adaptive insertion.

            cfg.fixed_sigma_knots_count = k

            skip_x0_warm = True

    if cfg.x0_warm is not None and not skip_x0_warm:

        xw = np.asarray(cfg.x0_warm, float).ravel()

        if xw.size == dim:

            x0 = xw.astype(np.float64, copy=True)

            enc = cfg.x0_warm_encoding

            if enc is not None:

                x0 = reconcile_spline_x_warm_for_config(

                    x0,

                    sk,

                    n_mono_target=cfg.n_mono_band_nm,

                    x_encoding_in=str(enc),

                    n_mono_band_for_xi_decode=(

                        cfg.x0_warm_n_mono_band_for_decode or cfg.n_mono_band_nm

                    ),

                )

            x0 = clip_to_bounds(x0, bounds[:, 0], bounds[:, 1])

    return bounds, x0, sk


def warm_start_sigma_regrid(

    x_prev: np.ndarray,

    sigma_prev: np.ndarray,

    sigma_new: np.ndarray,

    L_lo: float,

    L_hi: float,

    *,

    n_mono_band_nm: tuple[float, float] | None = None,


) -> np.ndarray:

    """Interpolate (n, L) to new sigma knots; d remains unchanged."""

    sig_o = np.asarray(sigma_prev, dtype=np.float64).ravel()

    sig_n = np.asarray(sigma_new, dtype=np.float64).ravel()

    xp = np.asarray(x_prev, dtype=np.float64).ravel()

    ko = int(sig_o.size)

    assert xp.size == 1 + 2 * ko, (xp.size, ko)

    d = float(xp[0])

    n_o_phys = x_slice_n_to_physical_nodes(xp[1 : 1 + ko], sig_o, n_mono_band_nm)

    L_o = xp[1 + ko : 1 + 2 * ko]

    n_n_phys = np.interp(sig_n, sig_o, n_o_phys)

    L_n = np.interp(sig_n, sig_o, L_o)

    n_n = physical_nodes_to_x_slice_n(n_n_phys, sig_n, n_mono_band_nm)

    L_n = np.clip(L_n, float(L_lo), float(L_hi))

    return np.concatenate(([d], n_n, L_n))


def rmse_at_spline_stage_x0_init(

    cfg: SplineOptConfig,

    sk: np.ndarray,

    ne: np.ndarray,

    Le: np.ndarray,

    d_nm: float | None,

    *,

    relax_n_mono: bool = False,


) -> tuple[float, float]:

    """MSE and RMSE at x0_init (clip bounds): same scalar as the 1st ``obj(x0_init)`` of the stage before L-BFGS-B."""

    from spline_objective import SplinePWLObjective

    bounds, x0 = build_x0_smart_preview_exact(

        cfg, sk, ne, Le, d_nm, relax_n_mono=relax_n_mono

    )

    sk_a = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk_a.size)

    x0_init = np.asarray(x0, dtype=np.float64).copy()

    relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

    if relax_eff:

        x0_init[0] = float(np.clip(x0_init[0], bounds[0, 0], bounds[0, 1]))

        x0_init[1 : 1 + k] = np.clip(x0_init[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT)

        for i in range(k):

            x0_init[1 + k + i] = float(

                np.clip(x0_init[1 + k + i], bounds[1 + k + i, 0], bounds[1 + k + i, 1])

            )

    else:

        x0_init = clip_to_bounds(x0_init, bounds[:, 0], bounds[:, 1])

    cfg_eval = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

    mse = float(SplinePWLObjective(cfg_eval, sk_a)(x0_init))

    return mse, float(np.sqrt(max(mse, 0.0)))


def log_rmse_mesh_bridge_diagnosis(

    cfg: SplineOptConfig,

    sk_dialog: np.ndarray,

    n_dialog: np.ndarray,

    L_dialog: np.ndarray,

    sk_canon: np.ndarray,

    n_canon: np.ndarray,

    L_canon: np.ndarray,

    d_nm: float,

    log: logging.Logger,

    *,

    relax_preview_mono: bool,

    tag: str = "DIAG_RMSE_BRIDGE",


) -> None:

    """Logs spectral MSE vs penalties for dialog K and canonical K (same cfg, same masked lambda grid).

    Explains a factor like 0.007 -> 0.04: often multiplied ``MSE_spectral`` because the **sigma mesh**

    (K, knot positions, edge extrapolation) differs between preview and worker, not a lambda grid bug.

    """

    sk_d = np.asarray(sk_dialog, dtype=np.float64).ravel()

    sk_c = np.asarray(sk_canon, dtype=np.float64).ravel()

    if int(sk_d.size) == int(sk_c.size) and np.allclose(np.sort(sk_d), np.sort(sk_c), rtol=0, atol=1e-12):

        return

    def _x0_after_rmse_clip(

        bounds: np.ndarray, x0: np.ndarray, sk: np.ndarray, *, relax_n_mono: bool

    ) -> np.ndarray:

        k = int(sk.size)

        xi = np.asarray(x0, dtype=np.float64).ravel().copy()

        relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

        if relax_eff:

            xi[0] = float(np.clip(xi[0], bounds[0, 0], bounds[0, 1]))

            xi[1 : 1 + k] = np.clip(xi[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT)

            for i in range(k):

                xi[1 + k + i] = float(

                    np.clip(xi[1 + k + i], bounds[1 + k + i, 0], bounds[1 + k + i, 1])

                )

        else:

            xi = clip_to_bounds(xi, bounds[:, 0], bounds[:, 1])

        return xi

    try:

        from spline_objective import decompose_spline_pwl_objective

        b_d, x0_d = build_x0_smart_preview_exact(

            cfg, sk_d, n_dialog, L_dialog, d_nm, relax_n_mono=relax_preview_mono

        )

        x_d = _x0_after_rmse_clip(b_d, x0_d, sk_d, relax_n_mono=relax_preview_mono)

        relax_eff = bool(relax_preview_mono) and cfg.n_mono_band_nm is not None

        cfg_prev = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

        msp_d, pen_d, tot_d = decompose_spline_pwl_objective(cfg_prev, sk_d, x_d)

        b_c, x0_c = build_x0_smart_preview_exact(

            cfg, sk_c, n_canon, L_canon, d_nm, relax_n_mono=False

        )

        x_c = _x0_after_rmse_clip(b_c, x0_c, sk_c, relax_n_mono=False)

        msp_c, pen_c, tot_c = decompose_spline_pwl_objective(cfg, sk_c, x_c)

        # If the preview is in relax mono, x_c contains ξ (not physical n): evaluate "like the preview"

        # (cfg without n_mono_band_nm) first requires ξ -> n, otherwise nk_from_x interprets ξ as n -> absurd RMSE.

        cfg_canon_relax = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

        if relax_eff:

            kc = int(sk_c.size)

            xi_blk = np.asarray(x_c[1 : 1 + kc], dtype=np.float64).ravel()

            n_phys_c = np.clip(

                x_slice_n_to_physical_nodes(xi_blk, sk_c, cfg.n_mono_band_nm),

                N_MIN_LIMIT,

                N_MAX_LIMIT,

            )

            L_blk = np.asarray(x_c[1 + kc : 1 + 2 * kc], dtype=np.float64).ravel()

            x_cr = np.concatenate((x_c[0:1], n_phys_c, L_blk))

            msp_cr, pen_cr, tot_cr = decompose_spline_pwl_objective(cfg_canon_relax, sk_c, x_cr)

        else:

            msp_cr, pen_cr, tot_cr = float("nan"), float("nan"), float("nan")

        rm_d = float(np.sqrt(max(tot_d, 0.0)))

        rm_c = float(np.sqrt(max(tot_c, 0.0)))

        rm_cr = float(np.sqrt(max(tot_cr, 0.0))) if relax_eff else float("nan")

        log.info(

            "%s | === Pont RMSE Smart Init (lire [A] puis [B] — même histoire que ``GUI Smart Init [Keep] | Fil conducteur``) ===",

            tag,

        )

        log.info(

            "%s | [A] Aperçu / dialogue  K=%2d  RMSE=%.6f  (souvent relax_n_mono, même K que la fenêtre).",

            tag,

            int(sk_d.size),

            rm_d,

        )

        log.info(

            "%s | [B] Maillage worker    K=%2d  RMSE=%.6f  (objectif réel au démarrage INDEX_SPLINE / PGlobal).",

            tag,

            int(sk_c.size),

            rm_c,

        )

        if relax_eff and np.isfinite(rm_cr):

            log.info(

                "%s | [C] Même maillage que [B], spectre seul (n_mono coupé)  K=%2d  RMSE=%.6f  — isole regrille + extrap bords.",

                tag,

                int(sk_c.size),

                rm_cr,

            )

            log.info(

                "%s | Pourquoi [A] < [B] possible: pas le même objectif ([B]: mono ξ, pénalités, K souvent plus grand).",

                tag,

            )

            log.info(

                "%s | Pourquoi [C] ≠ [A]: pondération spectrale proche, mais K et σ diffèrent (regrille / nœuds).",

                tag,

            )

        else:

            log.info(

                "%s | Si [A] ≠ [B]: en général nœuds en plus, extrapolation aux bords, ou positions σ — pas un bug du masque λ.",

                tag,

            )

        log.info(

            "%s | Détail  [A] MSE_sp=%.6e pén.=%.6e total=%.6e  |  [B] MSE_sp=%.6e pén.=%.6e total=%.6e",

            tag,

            msp_d,

            pen_d,

            tot_d,

            msp_c,

            pen_c,

            tot_c,

        )

        ratio_tot = tot_c / max(tot_d, 1e-30)

        ratio_sp = msp_c / max(msp_d, 1e-30)

        log.info(

            "%s | Rapports  total[B]/[A]=%.3f  MSE_sp[B]/[A]=%.3f  (>1 → surtout maillage / extrap / encodage ξ).",

            tag,

            ratio_tot,

            ratio_sp,

        )

        log.info(

            "%s | Retenir: la RMSE de [B] est celle qui aligne FACTUAL SOL2 et la ligne ``INDEX_SPLINE ... RMSE start``.",

            tag,

        )

    except NUMERICAL_FAULT_EXCEPTIONS as exc:

        log.warning("%s | diagnostic failed: %s", tag, exc, exc_info=True)



# Backward compatibility alias for the P4 scaffold
SplineComposedConfig = SplineOptConfig
