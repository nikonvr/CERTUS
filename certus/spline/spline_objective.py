#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""Spline spectral objective (masked grid, PWL nk, sigma codecs)."""

from __future__ import annotations


import threading


from typing import Any


import numpy as np

from scipy.interpolate import CubicSpline


from certus.core.certus_core import N_MIN_LIMIT, N_MAX_LIMIT
from certus.core.certus_array_utils import as_float64_1d, sorted_float64, interp_sorted
from certus.utils.certus_index_utils import _ratio_theoretical_from_nk, _transmittance_absolute_from_nk, spectral_rmse_weights

import functools


# Thread-safe LRU cache for weights, avoiding global thrashing
@functools.lru_cache(maxsize=16)
def _cached_spectral_rmse_weights_inner(key: bytes) -> np.ndarray:
    lam_f = np.frombuffer(key, dtype=np.float64)
    return spectral_rmse_weights(lam_f).astype(np.float64, copy=False)


def _cached_spectral_rmse_weights(lam_f: np.ndarray) -> np.ndarray:
    """Trapezoidal ln lambda weights for ``lam_f``; avoids ~N identical calls."""
    key = as_float64_1d(lam_f).tobytes()
    return _cached_spectral_rmse_weights_inner(key)


@functools.lru_cache(maxsize=32)
def _cached_cubic_interp_matrix_inner(sk_key: bytes, sig_key: bytes, k_nodes: int) -> np.ndarray:
    """Cached interpolation matrix M such that y(sig) = M @ y(sk) in smooth mode."""
    sk = np.frombuffer(sk_key, dtype=np.float64)
    sig = np.frombuffer(sig_key, dtype=np.float64)
    sp = CubicSpline(sk, np.eye(k_nodes), bc_type="not-a-knot")
    sig_c = np.clip(sig, float(sk[0]), float(sk[-1]))
    return np.asarray(sp(sig_c), dtype=np.float64)


def _cached_cubic_interp_matrix(sk: np.ndarray, sig: np.ndarray) -> np.ndarray:
    sk_f = as_float64_1d(sk)
    sig_f = as_float64_1d(sig)
    return _cached_cubic_interp_matrix_inner(sk_f.tobytes(), sig_f.tobytes(), int(sk_f.size))


from numba import njit
from certus_physics import (
    calculate_RT_single_layer_backside_array,
    calculate_bare_substrate_RT,
    batch_single_layer_T_mse,
    batch_single_layer_RT_mse,
    _compute_single_layer_sensitivity_array,
    calculate_transmission_single,
)

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _njit_single_layer_mse_fused(
    lam_f: np.ndarray,
    n_sub_f: np.ndarray,
    w: np.ndarray,
    inv_npix: float,
    t_exp_f: np.ndarray,
    r_exp_f: np.ndarray,
    n_l: np.ndarray,
    k_l: np.ndarray,
    d: float,
    wt: float,
    wr: float,
    need_t: bool,
    need_r: bool,
    t_is_ratio: bool,
    t_sub_cache: np.ndarray,
) -> float:
    n_pix = lam_f.shape[0]
    wsum = 0.0
    loss = 0.0
    
    if need_t:
        wsum += wt
    if need_r:
        wsum += wr
        
    if wsum <= 0.0:
        return 1e30
        
    for j in range(n_pix):
        r_th, t_th = calculate_transmission_single(
            lam_f[j], n_l[j], k_l[j], d, complex(n_sub_f[j], 0.0)
        )
        
        if t_is_ratio:
            # Prevent division by zero
            sub_t = t_sub_cache[j]
            t_th = t_th / sub_t if sub_t > 1e-12 else 0.0
            
        wj = w[j]
        if need_t:
            e_t = t_exp_f[j] - t_th
            loss += wt * wj * e_t * e_t
        if need_r:
            e_r = r_exp_f[j] - r_th
            loss += wr * wj * e_r * e_r
            
    return loss * inv_npix / wsum


from certus.spline.certus_index_spline_core import (
    DataType,
    SplineOptConfig,
    K_MIN_PHYS,
    SIGMA_KNOTS_MIN_SEP_REL,
    _reflectance_absolute_backside_from_nk,
    _to_fraction_T,
    n_lambda_rising_with_wavelength_penalty,
    physical_nodes_to_x_slice_n,
    x_slice_n_to_physical_nodes,
)


def sigma_knots_encode(sk: np.ndarray, s_lo: float, s_hi: float) -> np.ndarray:
    """Encodes sigma knots as log-proportions (M = K-1 components) for free optimization."""

    sks = np.sort(np.asarray(sk, dtype=np.float64).ravel())

    ds = np.diff(np.clip(sks, s_lo, s_hi))

    ds = np.clip(ds, 1e-12, None)

    ds /= np.sum(ds)

    return np.log(np.clip(ds, 1e-12, None))


def sigma_knots_decode(
    raw: np.ndarray,
    s_lo: float,
    s_hi: float,
    eps_s: float | None = None,
    *,
    work: dict[str, np.ndarray] | None = None,
    reuse_output: bool = False,
) -> np.ndarray:
    """Decodes log-proportions -> sorted sigma knots in [s_lo, s_hi]."""

    raw_f = np.asarray(raw, dtype=np.float64).ravel()
    m = int(raw_f.size)

    if work is not None:
        ww = work.get("ww")
        ds = work.get("ds")
        c = work.get("c")
        sk = work.get("sk")
        if ww is None or ww.size != m:
            ww = np.empty(m, dtype=np.float64)
            work["ww"] = ww
        if ds is None or ds.size != m:
            ds = np.empty(m, dtype=np.float64)
            work["ds"] = ds
        if c is None or c.size != m:
            c = np.empty(m, dtype=np.float64)
            work["c"] = c
        if sk is None or sk.size != m + 1:
            sk = np.empty(m + 1, dtype=np.float64)
            work["sk"] = sk
    else:
        ww = np.empty(m, dtype=np.float64)
        ds = np.empty(m, dtype=np.float64)
        c = np.empty(m, dtype=np.float64)
        sk = np.empty(m + 1, dtype=np.float64)

    np.copyto(ww, raw_f)
    np.clip(ww, -20.0, 20.0, out=ww)
    np.exp(ww, out=ww)

    sw = float(np.sum(ww))

    if not np.isfinite(sw) or sw <= 0.0:
        ww.fill(1.0)

        sw = float(m)

    if eps_s is None:
        eps_s = max(1e-10, SIGMA_KNOTS_MIN_SEP_REL * max(s_hi - s_lo, 1e-12))

    np.divide(ww, sw, out=ds)

    ds *= s_hi - s_lo

    np.cumsum(ds, out=c)

    sk[0] = s_lo
    if m > 1:
        sk[1:-1] = s_lo + c[:-1]
    sk[-1] = s_hi

    sk[1:] = np.maximum(sk[1:], sk[:-1] + eps_s)

    sk[-1] = s_hi

    if reuse_output and work is not None:
        return sk
    return sk.copy()


def _interpolate_along_sigma(
    sig: np.ndarray,
    sigma_knots: np.ndarray,
    values_at_knots: np.ndarray,
    profile_interp: str,
) -> np.ndarray:
    """Interpolates values at sigma nodes along sigma: PWL or cubic spline (not-a-knot, >=4 nodes)."""

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    v = np.asarray(values_at_knots, dtype=np.float64).ravel()

    sig_a = np.asarray(sig, dtype=np.float64)

    k = int(sk.size)

    if k < 2:
        raise ValueError("_interpolate_along_sigma: at least 2 nodes required")

    mode = str(profile_interp or "smooth").strip().lower()

    if mode not in ("pwl", "smooth"):
        mode = "smooth"

    if mode == "smooth" and k >= 4:
        sig_r = sig_a.ravel()
        mat = _cached_cubic_interp_matrix(sk, sig_r)
        out = np.asarray(mat @ v, dtype=np.float64)
        return out.reshape(sig_a.shape)

    return np.interp(sig_a, sk, v)


def nk_from_x_pwlnk(
    x: np.ndarray,
    lam_nm: np.ndarray,
    sigma_knots: np.ndarray,
    k_clip_lo: float,
    k_clip_hi: float,
    sig_pre: np.ndarray | None = None,
    *,
    n_mono_band_nm: tuple[float, float] | None = None,
    profile_interp: str = "smooth",
) -> tuple[np.ndarray, np.ndarray]:
    """Decode optimization vector to (n, k) arrays on the wavelength grid.

    Parameters
    ----------
    x : array_like
        Optimization vector ``[d, xi_n_0..xi_n_{K-1}, L_0..L_{K-1}]``
        where L = ln(k) at sigma knots.
    lam_nm : array_like
        Wavelengths in nm.
    sigma_knots : array_like
        Sigma knot positions (1/nm), size K.
    k_clip_lo, k_clip_hi : float
        Physical bounds for k clipping.
    sig_pre : np.ndarray, optional
        Pre-computed 1/lambda to avoid recomputation.
    n_mono_band_nm : tuple(float, float), optional
        If set, enforce n monotonicity on sigma segments overlapping this band.
    profile_interp : str
        ``"pwl"`` for piecewise-linear or ``"smooth"`` for cubic spline.

    Returns
    -------
    n_lam, k_lam : np.ndarray
        Refractive index and extinction coefficient on *lam_nm*.
    """

    x = np.asarray(x, dtype=np.float64, order="C").ravel()

    sigma_knots = np.asarray(sigma_knots, dtype=np.float64).ravel()

    k = int(sigma_knots.size)

    xi_or_n = x[1 : 1 + k]

    n_n = x_slice_n_to_physical_nodes(xi_or_n, sigma_knots, n_mono_band_nm)

    L_n = x[1 + k : 1 + 2 * k]

    if sig_pre is None:
        lam = np.asarray(lam_nm, dtype=np.float64).ravel()

        sig = 1.0 / np.maximum(lam, 1e-9)

    else:
        sig = sig_pre

    mode = str(profile_interp or "smooth").strip().lower()

    if mode not in ("pwl", "smooth"):
        mode = "smooth"

    n_lam = _interpolate_along_sigma(sig, sigma_knots, n_n, mode)

    L_lam = _interpolate_along_sigma(sig, sigma_knots, L_n, mode)

    k_lam = np.exp(L_lam)

    k_lo_eff = max(float(k_clip_lo), K_MIN_PHYS)

    k_hi_eff = float(k_clip_hi)

    np.clip(k_lam, k_lo_eff, k_hi_eff, out=k_lam)

    np.clip(n_lam, N_MIN_LIMIT, N_MAX_LIMIT, out=n_lam)

    return n_lam, k_lam


def build_segment_optimizer_x_vector(out: dict[str, Any], cfg: SplineOptConfig) -> tuple[np.ndarray, np.ndarray] | None:
    """Reconstruct the optimization vector from a segmental result dict.

    Parameters
    ----------
    out : dict
        Solver result containing ``sigma_knots``, ``x`` or
        ``n_nodes_physical`` + ``L_nodes`` + ``d_nm``.
    cfg : SplineOptConfig
        Configuration (used for monotonicity reparameterization).

    Returns
    -------
    tuple(np.ndarray, np.ndarray) or None
        ``(x_vector, sigma_knots)`` or None if reconstruction fails.
    """

    sk = np.asarray(out.get("sigma_knots"), dtype=np.float64).ravel()

    k = int(sk.size)

    if k < 2:
        return None

    xa = out.get("x")

    if xa is not None:
        xa = np.asarray(xa, dtype=np.float64).ravel()

        if xa.size == 1 + 2 * k:
            return xa.copy(), sk.copy()

    n_phys = np.asarray(out.get("n_nodes_physical"), dtype=np.float64).ravel()

    L_n = np.asarray(out.get("L_nodes"), dtype=np.float64).ravel()

    if n_phys.size != k or L_n.size != k:
        return None

    d_nm = float(out.get("d_nm", float("nan")))

    if not np.isfinite(d_nm):
        return None

    xi = physical_nodes_to_x_slice_n(n_phys, sk, cfg.n_mono_band_nm)

    xb = np.concatenate(
        (
            np.asarray([d_nm], dtype=np.float64),
            np.asarray(xi, dtype=np.float64).ravel(),
            np.asarray(L_n, dtype=np.float64).ravel(),
        )
    )

    return xb, sk


def _spline_objective_lam_mask(cfg: SplineOptConfig) -> np.ndarray:
    """Same lambda mask as ``SplinePWLObjective`` (points used in the loss).

    Stages SOL3 / SOL3b / Deltan_sub refinement: ``build_spline_objective_masked_grid`` and

    ``spline_objective_mse_on_masked_grid`` use the same spectral criterion."""

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    mask = np.isfinite(lam) & np.isfinite(np.asarray(cfg.n_sub, dtype=np.float64).ravel())

    if cfg.t_exp is not None:
        mask &= np.isfinite(np.asarray(cfg.t_exp, dtype=np.float64).ravel())

    if cfg.r_exp is not None and cfg.data_type != DataType.TRANSMISSION:
        mask &= np.isfinite(np.asarray(cfg.r_exp, dtype=np.float64).ravel())

    if cfg.rmse_fit_lambda_nm is not None:
        lo = float(min(cfg.rmse_fit_lambda_nm[0], cfg.rmse_fit_lambda_nm[1]))

        hi = float(max(cfg.rmse_fit_lambda_nm[0], cfg.rmse_fit_lambda_nm[1]))

        mask &= (lam >= lo) & (lam <= hi)

    return mask


def objective_lam_mask_on_target_grid(
    cfg: SplineOptConfig,
    lam_target: np.ndarray,
) -> np.ndarray:
    """

    Same definition as ``_spline_objective_lam_mask(cfg)``, sampled on ``lam_target``.

    If the grids coincide (within tolerance), returns the direct mask; otherwise linear interp 0/1

    on sorted ascending ``lam``.

    """

    lam_tgt = np.asarray(lam_target, dtype=np.float64).ravel()

    lam_src = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    m_src = _spline_objective_lam_mask(cfg)

    if lam_tgt.size == 0:
        return np.zeros(0, dtype=bool)

    if lam_src.size == 0:
        return np.zeros(lam_tgt.size, dtype=bool)

    if lam_tgt.shape == lam_src.shape and np.allclose(lam_tgt, lam_src, rtol=0.0, atol=1e-3):
        return m_src.astype(bool, copy=False)

    order = np.argsort(lam_src, kind="mergesort")

    ls = lam_src[order]

    ms = m_src[order].astype(np.float64)

    if ls.size < 2:
        v = float(ms[0]) if ls.size == 1 else 0.0

        return np.full(lam_tgt.size, v >= 0.5, dtype=bool)

    interp_vals = np.interp(lam_tgt, ls, ms, left=float(ms[0]), right=float(ms[-1]))

    return interp_vals >= 0.5


def build_spline_objective_masked_grid(
    cfg: SplineOptConfig,
) -> (
    tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        float,
        np.ndarray | None,
        np.ndarray | None,
    ]
    | None
):
    """Build the masked spectral grid for the spline objective function.

    Applies the RMSE window, data availability mask, and computes
    trapezoidal ln(lambda) weights.

    Parameters
    ----------
    cfg : SplineOptConfig
        Full configuration including ``lam_nm``, ``t_exp``, ``r_exp``,
        ``n_sub``, and RMSE window bounds.

    Returns
    -------
    tuple or None
        ``(lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f)``
        where ``_f`` denotes masked arrays. None if no valid points.
    """

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    mask = _spline_objective_lam_mask(cfg)

    lam_f = lam[mask]

    if lam_f.size == 0:
        return None

    n_sub_f = np.asarray(cfg.n_sub, dtype=np.float64).ravel()[mask]

    t_exp_f = _to_fraction_T(np.asarray(cfg.t_exp, float).ravel()[mask]) if cfg.t_exp is not None else None

    r_exp_f = _to_fraction_T(np.asarray(cfg.r_exp, float).ravel()[mask]) if cfg.r_exp is not None else None

    sig_f = 1.0 / np.maximum(lam_f, 1e-9)

    n_pix = int(sig_f.size)

    inv_npix = 1.0 / max(n_pix, 1)

    w = _cached_spectral_rmse_weights(lam_f)

    return lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f


def spline_objective_mse_on_masked_grid(
    cfg: SplineOptConfig,
    *,
    lam_f: np.ndarray,
    n_sub_f: np.ndarray,
    w: np.ndarray,
    inv_npix: float,
    t_exp_f: np.ndarray | None,
    r_exp_f: np.ndarray | None,
    n_l: np.ndarray,
    k_l: np.ndarray,
    d: float,
) -> float:
    """Weighted MSE on pre-masked spectral grid (same formula as SplinePWLObjective).

    Parameters
    ----------
    cfg : SplineOptConfig
        Configuration (data_type, weight_t/r, t_is_ratio).
    lam_f, n_sub_f, w : np.ndarray
        Masked wavelengths, substrate index, and quadrature weights.
    inv_npix : float
        1 / number_of_masked_points.
    t_exp_f, r_exp_f : np.ndarray or None
        Experimental T and/or R on the masked grid.
    n_l, k_l : np.ndarray
        Model n and k on the masked grid.
    d : float
        Film thickness in nm.

    Returns
    -------
    float
        Weighted average MSE (T and/or R channels).
    """

    loss = 0.0

    wsum = 0.0

    wt = float(cfg.weight_t)

    wr = float(cfg.weight_r)

    t_sub_cache = None

    if cfg.t_is_ratio:
        use_t = cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and wt > 0.0

        use_r = cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and wr > 0.0

        if use_t or use_r:
            t_sub_cache = np.asarray(calculate_bare_substrate_RT(lam_f, n_sub_f), dtype=np.float64)

    need_t = cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and wt > 0.0
    need_r = cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and wr > 0.0

    # ZERO-ALLOCATION FAST PATH
    _t_exp = t_exp_f if t_exp_f is not None else np.zeros(0, dtype=np.float64)
    _r_exp = r_exp_f if r_exp_f is not None else np.zeros(0, dtype=np.float64)
    _t_sub = t_sub_cache if t_sub_cache is not None else np.zeros(0, dtype=np.float64)
    
    # Fast boolean cast
    _t_ratio = bool(cfg.t_is_ratio)

    loss_scalar = _njit_single_layer_mse_fused(
        lam_f, n_sub_f, w, inv_npix, 
        _t_exp, _r_exp, 
        n_l, k_l, float(d), 
        wt, wr, need_t, need_r, _t_ratio, _t_sub
    )

    return float(loss_scalar)


def spectral_mse_rmse_masked_from_nk(
    cfg: SplineOptConfig,
    _out_meta: dict[str, Any],
    lam_full: np.ndarray,
    n_lam: np.ndarray,
    k_lam: np.ndarray,
    d_nm: float,
) -> tuple[float, float]:
    """MSE and RMSE on the full spectral mask from explicit n(lam), k(lam).

    Uses the same mask, weights, and T/R formulas as the spline objective.

    Parameters
    ----------
    cfg : SplineOptConfig
        Configuration.
    out_meta : dict
        Result metadata (unused but kept for API compatibility).
    lam_full : array_like
        Full wavelength grid in nm.
    n_lam, k_lam : array_like
        Model n and k on *lam_full*.
    d_nm : float
        Film thickness in nm.

    Returns
    -------
    mse, rmse : float
        Mean squared error and root-mean-squared error. ``(nan, nan)`` on failure.
    """

    mgf = build_spline_objective_masked_grid(cfg)

    if mgf is None:
        return float("nan"), float("nan")

    lam_f, _sig_f, n_sub_f_mg, w_f, inv_npix, t_exp_f, r_exp_f = mgf

    n_sub_eff_f = np.asarray(n_sub_f_mg, dtype=np.float64)

    lam_full = np.asarray(lam_full, dtype=np.float64).ravel()

    n_l = np.asarray(n_lam, dtype=np.float64).ravel()

    k_l = np.asarray(k_lam, dtype=np.float64).ravel()

    if lam_full.size < 2 or n_l.size != lam_full.size or k_l.size != lam_full.size:
        return float("nan"), float("nan")

    # O(1) Mask extraction if the incoming lam_full matches the configuration (no binary search overhead)
    if lam_full.shape == np.asarray(cfg.lam_nm, dtype=np.float64).ravel().shape:
        mask = _spline_objective_lam_mask(cfg)
        if mask.size == lam_full.size and np.sum(mask) == lam_f.size:
            nlf = n_l[mask]
            klf = k_l[mask]
        else:
            nlf = np.interp(lam_f, lam_full, n_l)
            klf = np.interp(lam_f, lam_full, k_l)
    else:
        nlf = np.interp(lam_f, lam_full, n_l)
        klf = np.interp(lam_f, lam_full, k_l)

    m = spline_objective_mse_on_masked_grid(
        cfg,
        lam_f=lam_f,
        n_sub_f=n_sub_eff_f,
        w=w_f,
        inv_npix=inv_npix,
        t_exp_f=t_exp_f,
        r_exp_f=r_exp_f,
        n_l=nlf,
        k_l=klf,
        d=float(d_nm),
    )

    if not np.isfinite(m) or m >= 1e29:
        return float("nan"), float("nan")

    return float(m), float(np.sqrt(max(m, 0.0)))


def spline_spectral_mse_from_xy_nk(
    cfg: "SplineOptConfig",
    lam_full: np.ndarray,
    n_lam_full: np.ndarray,
    k_lam_full: np.ndarray,
    d_nm: float,
) -> float | None:
    """Spectral MSE only (without auxiliary penalties), on the objective mask."""

    mg = build_spline_objective_masked_grid(cfg)

    if mg is None:
        return None

    lam_f, _sf, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = mg

    lam0 = np.asarray(lam_full, dtype=np.float64).ravel()

    n0 = np.asarray(n_lam_full, dtype=np.float64).ravel()

    k0 = np.asarray(k_lam_full, dtype=np.float64).ravel()

    if n0.size != lam0.size or k0.size != lam0.size:
        return None

    o = np.argsort(lam0, kind="mergesort")

    ls = lam0[o]

    nlf = np.interp(lam_f, ls, n0[o])

    klf = np.interp(lam_f, ls, k0[o])

    if not np.all(np.isfinite(nlf) & np.isfinite(klf)):
        return None

    return float(
        spline_objective_mse_on_masked_grid(
            cfg,
            lam_f=lam_f,
            n_sub_f=n_sub_f,
            w=w,
            inv_npix=inv_npix,
            t_exp_f=t_exp_f,
            r_exp_f=r_exp_f,
            n_l=nlf,
            k_l=klf,
            d=float(d_nm),
        )
    )


def decompose_spline_pwl_objective(
    cfg: SplineOptConfig,
    sigma_knots: np.ndarray,
    x: np.ndarray,
) -> tuple[float, float, float]:
    """Decomposes the cost like ``SplinePWLObjective.__call__``: (mse_spectral, penalties, total).

    Useful to explain a RMSE jump between two sigma meshes (e.g. K=12 in dialog vs K=14 canonical):

    the total is ``mse_spectral + pen``; the displayed RMSE is ``sqrt(mse_spectral)`` (penalties are not RMSE).

    If ``cfg.spline_pure_spectral_objective`` is True, ``pen`` is 0 and ``total == mse_spectral``.

    """

    x = np.asarray(x, dtype=np.float64).ravel()

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    k_nodes = int(sk.size)

    if x.size != 1 + 2 * k_nodes:
        return float("nan"), float("nan"), float("nan")

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    mask = _spline_objective_lam_mask(cfg)

    lam_f = lam[mask]

    if lam_f.size == 0:
        return 1e30, 0.0, 1e30

    n_sub_f = np.asarray(cfg.n_sub, dtype=np.float64).ravel()[mask]

    t_exp_f = _to_fraction_T(np.asarray(cfg.t_exp, float).ravel()[mask]) if cfg.t_exp is not None else None

    r_exp_f = _to_fraction_T(np.asarray(cfg.r_exp, float).ravel()[mask]) if cfg.r_exp is not None else None

    sig_f = 1.0 / np.maximum(lam_f, 1e-9)

    inv_npix = 1.0 / max(int(lam_f.size), 1)

    w = _cached_spectral_rmse_weights(lam_f)

    d = float(x[0])

    n_l, k_l = nk_from_x_pwlnk(
        x,
        lam_f,
        sk,
        float(cfg.k_clip_lo),
        float(cfg.k_clip_hi),
        sig_pre=sig_f,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=cfg.nk_profile_interp,
    )

    n_n = x_slice_n_to_physical_nodes(x[1 : 1 + k_nodes], sk, cfg.n_mono_band_nm)

    if bool(getattr(cfg, "spline_pure_spectral_objective", False)):
        pen = 0.0

    else:
        pen = float(n_lambda_rising_with_wavelength_penalty(cfg, sk, n_n))

    mse_sp = float(
        spline_objective_mse_on_masked_grid(
            cfg,
            lam_f=lam_f,
            n_sub_f=n_sub_f,
            w=w,
            inv_npix=inv_npix,
            t_exp_f=t_exp_f,
            r_exp_f=r_exp_f,
            n_l=n_l,
            k_l=k_l,
            d=d,
        )
    )

    if not np.isfinite(mse_sp):
        mse_sp = 1e30

    tot = float(mse_sp + pen)

    return mse_sp, pen, tot


class SplinePWLObjective:
    """Pre-allocated objective for PWL spline (state-of-the-art, avoids closure allocations)."""

    def __init__(self, cfg: SplineOptConfig, sigma_knots: np.ndarray):

        lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

        mask = _spline_objective_lam_mask(cfg)

        self.lam_f = lam[mask]

        self.n_sub_f = np.asarray(cfg.n_sub, dtype=np.float64).ravel()[mask]

        self.t_exp_f = _to_fraction_T(np.asarray(cfg.t_exp, float).ravel()[mask]) if cfg.t_exp is not None else None

        self.r_exp_f = _to_fraction_T(np.asarray(cfg.r_exp, float).ravel()[mask]) if cfg.r_exp is not None else None

        self.sig_f = 1.0 / np.maximum(self.lam_f, 1e-9)

        self.n_pix = int(self.sig_f.size)

        self.inv_npix = 1.0 / max(self.n_pix, 1)

        self._cached_weights = _cached_spectral_rmse_weights(self.lam_f)

        self.w_t = self._cached_weights

        self.sigma_k = np.asarray(sigma_knots, dtype=np.float64).ravel()

        self.cfg = cfg

        self.wt = float(cfg.weight_t)

        self.wr = float(cfg.weight_r)

        self.k_lo = float(cfg.k_clip_lo)

        self.k_hi = float(cfg.k_clip_hi)

        self.k_lo_eff = max(self.k_lo, K_MIN_PHYS)

        self._K = int(self.sigma_k.size)

        # Pre-cache interpolation mode + matrix (avoids per-eval string
        # parsing, np.asarray, and LRU lookup overhead)
        _mode = str(cfg.nk_profile_interp or "smooth").strip().lower()
        if _mode == "smooth" and self._K >= 4:
            self._interp_mat = _cached_cubic_interp_matrix(self.sigma_k, self.sig_f)
            self._interp_mode = "smooth"
        else:
            self._interp_mat = None
            self._interp_mode = "pwl"

        # ── Pre-resolved flags (avoid per-eval getattr / enum checks) ──
        self._pure_spectral = bool(getattr(cfg, "spline_pure_spectral_objective", False))
        self._need_t = (
            cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and self.t_exp_f is not None and self.wt > 0.0
        )
        self._need_r = (
            cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and self.r_exp_f is not None and self.wr > 0.0
        )
        self._n_mono_band_nm = cfg.n_mono_band_nm

        # ── Pre-resolved penalty config (avoid 7x getattr per gradient call) ──
        self._pen_weight = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)
        _pen_band = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)
        self._pen_band = _pen_band
        self._pen_slack = max(float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0), 0.0)
        if self._pen_weight > 0.0 and _pen_band is not None:
            self._pen_lam_lo = float(min(float(_pen_band[0]), float(_pen_band[1])))
            self._pen_lam_hi = float(max(float(_pen_band[0]), float(_pen_band[1])))
        else:
            self._pen_lam_lo = 0.0
            self._pen_lam_hi = 0.0

        # ── Pre-resolved gradient config (avoid per-call dispatch) ──
        self._wsum, self._use_t, self._use_r = _spectral_wsum_and_channels(cfg, self.t_exp_f, self.r_exp_f)
        self._k_lo_phys = float(max(float(cfg.k_clip_lo), float(K_MIN_PHYS)))
        self._k_hi_phys = float(cfg.k_clip_hi)
        # DO NOT reassign _interp_mode here: it is already resolved above (lines
        # 860-865), together with _interp_mat, and both MUST remain consistent.
        #
        # This line used to put the RAW config string back here. Consequences:
        #  - for K < 4, the top block chooses "pwl" and sets _interp_mat = None, but it
        #    was put back to "smooth": the gradient then took the smooth branch and did
        #    S_mat.T @ ... on None;
        #  - the string was neither .strip() nor .lower() here, unlike line 859:
        #    a value "Smooth " no longer matched the comparison mode == "smooth".
        self._weight_t = float(cfg.weight_t)
        self._weight_r = float(cfg.weight_r)

        # Thread-local cache: each thread gets its own entry, preventing
        # race conditions when PGlobalOptimizer evaluates in parallel.
        self._tls = threading.local()

    def _get_cached(self, x: np.ndarray):

        c = getattr(self._tls, "_cache", None)

        if c is None or c["_xbytes"] != x.data.tobytes():
            return None

        return c

    def _fast_penalty(self, n_n: np.ndarray) -> float:
        """Inlined n-lambda-rising penalty using pre-resolved config (no getattr/asarray overhead)."""
        w = self._pen_weight
        if w <= 0.0 or self._pen_band is None:
            return 0.0
        sk = self.sigma_k
        eps = 1e-12
        viol = n_n[:-1] - n_n[1:]
        ve = np.maximum(viol - self._pen_slack, 0.0)
        # Quick check before geometry
        if not np.any(ve > 0.0):
            return 0.0
        s0 = sk[:-1]
        s1 = sk[1:]
        valid = s1 > (s0 + eps)
        lam_min_seg = 1.0 / np.maximum(s1, 1e-30)
        lam_max_seg = 1.0 / np.maximum(s0, 1e-30)
        seg_lo = np.minimum(lam_min_seg, lam_max_seg)
        seg_hi = np.maximum(lam_min_seg, lam_max_seg)
        in_band = valid & (seg_hi >= self._pen_lam_lo) & (seg_lo <= self._pen_lam_hi)
        active = in_band & (viol > eps) & (ve > 0.0)
        if not np.any(active):
            return 0.0
        acc = float(np.dot(ve[active], ve[active]))
        return w * acc

    def _fast_penalty_grad(self, n_n: np.ndarray) -> np.ndarray:
        """Inlined penalty gradient using pre-resolved config (no getattr/asarray overhead)."""
        K = n_n.size
        g = np.zeros(K, dtype=np.float64)
        w = self._pen_weight
        if w <= 0.0 or self._pen_band is None or K < 2:
            return g
        sk = self.sigma_k
        eps = 1e-12
        viol = n_n[:-1] - n_n[1:]
        ve = np.maximum(viol - self._pen_slack, 0.0)
        if not np.any(ve > 0.0):
            return g
        s0 = sk[:-1]
        s1 = sk[1:]
        valid = s1 > (s0 + eps)
        lam_min_seg = 1.0 / np.maximum(s1, 1e-30)
        lam_max_seg = 1.0 / np.maximum(s0, 1e-30)
        seg_lo = np.minimum(lam_min_seg, lam_max_seg)
        seg_hi = np.maximum(lam_min_seg, lam_max_seg)
        in_band = valid & (seg_hi >= self._pen_lam_lo) & (seg_lo <= self._pen_lam_hi)
        active = in_band & (viol > eps) & (ve > 0.0)
        if not np.any(active):
            return g
        dv = 2.0 * w * ve * active
        g[:-1] += dv
        g[1:] -= dv
        return g

    def _fast_nk(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Interpolate (n_lam, k_lam, n_nodes) from x using pre-cached matrix.

        Returns n_nodes alongside (n_lam, k_lam) so the caller can reuse them
        for the penalty without a redundant ``x_slice_n_to_physical_nodes`` call.
        """
        K = self._K
        n_n = x_slice_n_to_physical_nodes(x[1 : 1 + K], self.sigma_k, self._n_mono_band_nm)
        L_n = x[1 + K : 1 + 2 * K]
        if self._interp_mat is not None:
            n_lam = self._interp_mat @ n_n
            L_lam = self._interp_mat @ L_n
        else:
            n_lam = np.interp(self.sig_f, self.sigma_k, n_n)
            L_lam = np.interp(self.sig_f, self.sigma_k, L_n)
        k_lam = np.exp(L_lam)
        np.clip(k_lam, self.k_lo_eff, self.k_hi, out=k_lam)
        np.clip(n_lam, N_MIN_LIMIT, N_MAX_LIMIT, out=n_lam)
        return n_lam, k_lam, n_n

    def __call__(self, xv: np.ndarray) -> float:

        x = as_float64_1d(xv)

        cached = self._get_cached(x)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        d = float(x[0])

        # _fast_nk returns (n_lam, k_lam, n_nodes) — reuse n_nodes for penalty
        n_l, k_l, n_n = self._fast_nk(x)

        pen = 0.0 if self._pure_spectral else self._fast_penalty(n_n)

        mse_sp = spline_objective_mse_on_masked_grid(
            self.cfg,
            lam_f=self.lam_f,
            n_sub_f=self.n_sub_f,
            w=self.w_t,
            inv_npix=self.inv_npix,
            t_exp_f=self.t_exp_f,
            r_exp_f=self.r_exp_f,
            n_l=n_l,
            k_l=k_l,
            d=d,
        )

        if not np.isfinite(mse_sp):
            mse_sp = 1e30

        final_cost = float(mse_sp) + float(pen)

        # Cache cost + (n_l, k_l) for reuse by analytic_gradient on same x
        self._tls._cache = {"_xbytes": x.data.tobytes(), "cost": final_cost, "n_l": n_l, "k_l": k_l}

        return final_cost

    def cost_and_grad(self, xv: np.ndarray) -> tuple[float, np.ndarray]:
        """Return ``(cost, gradient)`` in one call, for ``minimize(..., jac=True)``.

        Shares the ``(n_l, k_l)`` computation between the objective and gradient
        via the thread-local cache, halving physics evaluations per L-BFGS-B step.
        """
        cost = self.__call__(xv)
        grad = self.analytic_gradient(xv)
        if grad is None:
            grad = np.zeros(np.asarray(xv).ravel().size, dtype=np.float64)
        return cost, grad

    def evaluate_batch(self, X_batch: np.ndarray) -> np.ndarray:
        """Evaluate N points in one pass, exploiting shared interpolation matrix.

        Key optimization: replaces N separate ``mat @ v_i`` (dgemv) with a single
        ``mat @ V.T`` (dgemm) which BLAS parallelizes across all CPU cores.

        Parameters
        ----------
        X_batch : (N, 1 + 2*K) array
            N parameter vectors [d, n_0..n_{K-1}, L_0..L_{K-1}].

        Returns
        -------
        Y : (N,) array of objective values.
        """
        X = np.asarray(X_batch, dtype=np.float64)
        N = X.shape[0]
        K = int(self.sigma_k.size)

        if N == 0:
            return np.empty(0, dtype=np.float64)

        d_all = X[:, 0]

        # Decode n nodes — vectorized when no monotonicity reparametrization
        if self.cfg.n_mono_band_nm is None:
            n_nodes_all = np.clip(X[:, 1 : 1 + K], N_MIN_LIMIT, N_MAX_LIMIT)
        else:
            n_nodes_all = np.empty((N, K), dtype=np.float64)
            for i in range(N):
                n_nodes_all[i] = x_slice_n_to_physical_nodes(X[i, 1 : 1 + K], self.sigma_k, self.cfg.n_mono_band_nm)

        L_nodes_all = X[:, 1 + K : 1 + 2 * K]

        # Batch interpolation: one dgemm instead of N dgemv
        # Uses pre-cached matrix from __init__ (no string parsing / LRU lookup)
        if self._interp_mat is not None:
            n_lam_all = (self._interp_mat @ n_nodes_all.T).T  # (N, n_pix)
            L_lam_all = (self._interp_mat @ L_nodes_all.T).T  # (N, n_pix)
        else:
            n_lam_all = np.empty((N, self.n_pix), dtype=np.float64)
            L_lam_all = np.empty((N, self.n_pix), dtype=np.float64)
            for i in range(N):
                n_lam_all[i] = np.interp(self.sig_f, self.sigma_k, n_nodes_all[i])
                L_lam_all[i] = np.interp(self.sig_f, self.sigma_k, L_nodes_all[i])

        # k from L (vectorized)
        k_lam_all = np.exp(L_lam_all)
        np.clip(k_lam_all, self.k_lo_eff, self.k_hi, out=k_lam_all)
        np.clip(n_lam_all, N_MIN_LIMIT, N_MAX_LIMIT, out=n_lam_all)

        # ── Fused batch TMM path (non-ratio, non-absorbing) ──
        # Uses single prange(N) kernel instead of N separate Python→Numba dispatches.
        pure_spec = self._pure_spectral
        need_t = self._need_t
        need_r = self._need_r
        use_fused = not bool(self.cfg.t_is_ratio)

        Y = np.empty(N, dtype=np.float64)

        if use_fused and need_t and not need_r:
            # T-only fast path: one prange(N) kernel
            mse_batch = batch_single_layer_T_mse(
                self.lam_f,
                self.n_sub_f,
                self.w_t,
                self.inv_npix,
                self.t_exp_f,
                n_lam_all,
                k_lam_all,
                d_all,
            )
            if pure_spec:
                Y[:] = mse_batch
            else:
                for i in range(N):
                    pen = n_lambda_rising_with_wavelength_penalty(self.cfg, self.sigma_k, n_nodes_all[i])
                    Y[i] = float(mse_batch[i]) + float(pen)
        elif use_fused and need_t and need_r:
            # R+T fused fast path: one prange(N) kernel
            mse_batch = batch_single_layer_RT_mse(
                self.lam_f,
                self.n_sub_f,
                self.w_t,
                self.inv_npix,
                self.t_exp_f,
                self.r_exp_f,
                n_lam_all,
                k_lam_all,
                d_all,
                self.wt,
                self.wr,
            )
            if pure_spec:
                Y[:] = mse_batch
            else:
                for i in range(N):
                    pen = n_lambda_rising_with_wavelength_penalty(self.cfg, self.sigma_k, n_nodes_all[i])
                    Y[i] = float(mse_batch[i]) + float(pen)
        else:
            # Fallback: ratio mode or R-only (rare)
            for i in range(N):
                mse_sp = spline_objective_mse_on_masked_grid(
                    self.cfg,
                    lam_f=self.lam_f,
                    n_sub_f=self.n_sub_f,
                    w=self.w_t,
                    inv_npix=self.inv_npix,
                    t_exp_f=self.t_exp_f,
                    r_exp_f=self.r_exp_f,
                    n_l=n_lam_all[i],
                    k_l=k_lam_all[i],
                    d=float(d_all[i]),
                )
                if not np.isfinite(mse_sp):
                    mse_sp = 1e30
                pen = (
                    0.0
                    if pure_spec
                    else n_lambda_rising_with_wavelength_penalty(self.cfg, self.sigma_k, n_nodes_all[i])
                )
                Y[i] = float(mse_sp) + float(pen)

        return Y

    def analytic_gradient(self, xv: np.ndarray) -> np.ndarray | None:
        """Gradient of ``__call__`` when ``spline_pwl_analytic_grad_supported(self.cfg)``."""

        x = as_float64_1d(xv)

        # Reuse (n_l, k_l) from thread-local cache if __call__ was just
        # invoked on the same x (typical in _combined_fun_and_grad).
        cached = self._get_cached(x)
        nk_pre = None
        if cached is not None and "n_l" in cached:
            nk_pre = (cached["n_l"], cached["k_l"])

        return self._compute_analytic_gradient(
            x, nk_precomputed=nk_pre,
        )

    def _compute_analytic_gradient(
        self,
        x: np.ndarray,
        *,
        nk_precomputed: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> np.ndarray | None:
        """Fast analytic gradient using pre-resolved config and inlined penalty."""

        if not spline_pwl_analytic_grad_supported(self.cfg):
            return None

        sk = self.sigma_k
        k_nodes = self._K
        dim = 1 + 2 * k_nodes
        if x.size != dim or k_nodes < 2:
            return None

        lam_f = self.lam_f
        sig_f = self.sig_f
        n_sub_f = self.n_sub_f
        w = self.w_t
        n_pix = self.n_pix
        inv_npix = self.inv_npix
        cfg = self.cfg

        wsum = self._wsum
        use_t = self._use_t
        use_r = self._use_r

        if wsum <= 0.0:
            return None

        mode = self._interp_mode
        S_mat = self._interp_mat

        grad_n_lam = np.zeros(n_pix, dtype=np.float64)
        grad_k_lam = np.zeros(n_pix, dtype=np.float64)

        d_nm = float(x[0])

        # Reuse pre-computed (n_l, k_l) when available (from __call__ cache)
        if nk_precomputed is not None:
            n_l, k_l = nk_precomputed
        else:
            n_l, k_l = nk_from_x_pwlnk(
                x, lam_f, sk,
                float(cfg.k_clip_lo), float(cfg.k_clip_hi),
                sig_pre=sig_f,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=cfg.nk_profile_interp,
            )

        # Fused R+T kernel when both channels active (single TMM pass)
        if use_t and use_r:
            r_th, t_th = calculate_RT_single_layer_backside_array(lam_f, n_l, k_l, d_nm, n_sub_f)
        else:
            t_th = _transmittance_absolute_from_nk(lam_f, n_l, k_l, d_nm, n_sub_f) if use_t else None
            r_th = _reflectance_absolute_backside_from_nk(lam_f, n_l, k_l, d_nm, n_sub_f) if use_r else None

        t_sub_nu = None
        if cfg.t_is_ratio:
            t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam_f, n_sub_f), 1e-7)

        clip_t = None
        if use_t and t_th is not None:
            clip_t = np.where((t_th <= 1e-14) | (t_th >= 1.0 - 1e-14), 0.0, 1.0)
            if cfg.t_is_ratio:
                t_th = t_th / t_sub_nu

        clip_r = None
        if use_r and r_th is not None:
            clip_r = np.where((r_th <= 1e-14) | (r_th >= 1.0 - 1e-14), 0.0, 1.0)
            if cfg.t_is_ratio:
                r_th_abs = r_th.copy()
                r_th = r_th / t_sub_nu

        grad = np.zeros(dim, dtype=np.float64)
        scale = 1.0 / wsum
        fd_eps = 1e-7

        n_n = x_slice_n_to_physical_nodes(x[1 : 1 + k_nodes], sk, cfg.n_mono_band_nm)

        # Inlined penalty gradient (no getattr/asarray)
        if not self._pure_spectral:
            grad[1 : 1 + k_nodes] += self._fast_penalty_grad(n_n)

        # Pre-compute R finite-differences vectorized
        _dRdn_arr = _dRdk_arr = _dRdd_arr = None
        if use_r:
            _rp_n = _reflectance_absolute_backside_from_nk(lam_f, n_l + fd_eps, k_l, d_nm, n_sub_f)
            _rm_n = _reflectance_absolute_backside_from_nk(lam_f, n_l - fd_eps, k_l, d_nm, n_sub_f)
            _dRdn_arr = (_rp_n - _rm_n) / (2.0 * fd_eps)
            _rp_k = _reflectance_absolute_backside_from_nk(lam_f, n_l, k_l + fd_eps, d_nm, n_sub_f)
            _rm_k = _reflectance_absolute_backside_from_nk(lam_f, n_l, k_l - fd_eps, d_nm, n_sub_f)
            r_ref = r_th_abs if cfg.t_is_ratio else r_th
            _dRdk_arr = np.where(
                k_l < fd_eps,
                (_rp_k - r_ref) / fd_eps,
                (_rp_k - _rm_k) / (2.0 * fd_eps),
            )
            _rp_d = _reflectance_absolute_backside_from_nk(lam_f, n_l, k_l, d_nm + fd_eps, n_sub_f)
            _rm_d = _reflectance_absolute_backside_from_nk(lam_f, n_l, k_l, d_nm - fd_eps, n_sub_f)
            _dRdd_arr = (_rp_d - _rm_d) / (2.0 * fd_eps)
            if cfg.t_is_ratio:
                _dRdn_arr = _dRdn_arr / t_sub_nu
                _dRdk_arr = _dRdk_arr / t_sub_nu
                _dRdd_arr = _dRdd_arr / t_sub_nu

        L_n = x[1 + k_nodes : 1 + 2 * k_nodes]
        k_lo = self._k_lo_phys
        k_hi = self._k_hi_phys

        # Vectorized T-sensitivity
        # _compute_single_layer_sensitivity_array imported at module level
        _dTdn_arr = _dTdk_arr = _dTdd_arr = None
        if use_t:
            _dTdn_arr, _dTdk_arr, _, _, _dTdd_arr, _ = _compute_single_layer_sensitivity_array(
                lam_f, n_l, k_l, d_nm, n_sub_f
            )
            if cfg.t_is_ratio:
                _dTdn_arr = _dTdn_arr / t_sub_nu
                _dTdk_arr = _dTdk_arr / t_sub_nu
                _dTdd_arr = _dTdd_arr / t_sub_nu

        # Vectorized residuals & per-pixel gradient contributions
        gn_arr = np.zeros(n_pix, dtype=np.float64)
        gk_arr = np.zeros(n_pix, dtype=np.float64)
        grad_d = 0.0

        if use_t and self.t_exp_f is not None and t_th is not None:
            e_t = self.t_exp_f - t_th
            fac_t = self._weight_t * inv_npix * scale * (-2.0)
            gn_arr += fac_t * w * e_t * _dTdn_arr * clip_t
            gk_arr += fac_t * w * e_t * _dTdk_arr * clip_t
            grad_d += fac_t * float(np.dot(w, e_t * _dTdd_arr * clip_t))

        if use_r and self.r_exp_f is not None and r_th is not None:
            e_r = self.r_exp_f - r_th
            fac_r = self._weight_r * inv_npix * scale * (-2.0)
            gn_arr += fac_r * w * e_r * _dRdn_arr * clip_r
            gk_arr += fac_r * w * e_r * _dRdk_arr * clip_r
            grad_d += fac_r * float(np.dot(w, e_r * _dRdd_arr * clip_r))

        grad[0] += grad_d

        # Scatter per-pixel gradients into knot gradients (VECTORIZED)
        j_arr = np.searchsorted(sk, sig_f, side="right").astype(np.intp) - 1
        np.clip(j_arr, 0, k_nodes - 2, out=j_arr)
        denom = sk[j_arr + 1] - sk[j_arr]
        safe_denom = np.where(denom > 1e-18, denom, 1.0)
        w1 = np.where(denom > 1e-18, (sig_f - sk[j_arr]) / safe_denom, 0.0)
        w1 = np.where(sig_f <= sk[0], 0.0, w1)
        w1 = np.where(sig_f >= sk[-1], 1.0, w1)
        w0 = 1.0 - w1

        # The chain rule factor must be evaluated with the MODEL'S INTERPOLATION,
        # not systematically with piecewise linear.
        #
        # k_lam = exp(L_lam), so d k_lam / d L_node = exp(L_lam) * dL_lam/d L_node.
        # The projection dL_lam/d L_node is properly handled below (S_mat.T in smooth
        # mode, w0/w1 in pwl mode), but the exp(L_lam) factor was ALWAYS calculated
        # from the linear weights w0/w1. In "smooth" mode — the DEFAULT mode as soon
        # as K >= 4 (cf. line 860) — the forward model interpolates by cubic matrix
        # (line 245, mat @ v) : the factor was thus evaluated at the wrong place, and the
        # bound masks dn_mask/dk_mask were tested on the wrong values.
        if mode == "smooth":
            n_unc = S_mat @ n_n
            L_lam_v = S_mat @ L_n
        else:
            n_unc = w0 * n_n[j_arr] + w1 * n_n[j_arr + 1]
            L_lam_v = w0 * L_n[j_arr] + w1 * L_n[j_arr + 1]

        k_unc = np.exp(L_lam_v)

        dn_mask = ((n_unc > N_MIN_LIMIT) & (n_unc < N_MAX_LIMIT)).astype(np.float64)
        dk_mask = ((k_unc > k_lo) & (k_unc < k_hi)).astype(np.float64)

        chain_n = gn_arr * dn_mask
        chain_k = gk_arr * dk_mask * k_unc

        if mode == "pwl":
            cn_w0 = chain_n * w0
            cn_w1 = chain_n * w1
            ck_w0 = chain_k * w0
            ck_w1 = chain_k * w1
            np.add.at(grad, j_arr + 1, cn_w0)
            np.add.at(grad, j_arr + 2, cn_w1)
            np.add.at(grad, j_arr + 1 + k_nodes, ck_w0)
            np.add.at(grad, j_arr + 2 + k_nodes, ck_w1)
        else:
            grad_n_lam[:] = chain_n
            grad_k_lam[:] = chain_k

        if mode == "smooth":
            grad[1 : 1 + k_nodes] += S_mat.T @ grad_n_lam
            grad[1 + k_nodes : 1 + 2 * k_nodes] += S_mat.T @ grad_k_lam

        return grad


def spline_pwl_analytic_grad_supported(cfg: SplineOptConfig) -> bool:
    """True if the analytic gradient (T + penalties; R by FD/lambda) is consistent with the objective."""

    if cfg.n_mono_band_nm is not None:
        return False

    return True


def _spectral_wsum_and_channels(
    cfg: SplineOptConfig,
    t_exp_f: np.ndarray | None,
    r_exp_f: np.ndarray | None,
) -> tuple[float, bool, bool]:

    wt = float(cfg.weight_t)

    wr = float(cfg.weight_r)

    use_t = cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and wt > 0.0

    use_r = cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and wr > 0.0

    wsum = 0.0

    if use_t:
        wsum += wt

    if use_r:
        wsum += wr


    return wsum, use_t, use_r

