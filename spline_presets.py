#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Material presets for Nb₂O₅, SiO₂, Ta₂O₅ and projection onto a sigma mesh (INDEX SPLINE)."""

from __future__ import annotations

import numpy as np

from certus_array_utils import as_float64_1d, sorted_float64, interp_sorted
from certus_core import K_MAX_LIMIT, N_MAX_LIMIT, N_MIN_LIMIT


NB2O5_PRESET_KNOTS = {
    "sk": [
        2.00000000e-04,
        2.80697979e-04,
        3.93956777e-04,
        5.52914357e-04,
        7.76009713e-04,
        1.08912179e-03,
        1.52857143e-03,
        1.87133042e-03,
        2.16037601e-03,
        2.41507172e-03,
        2.64535789e-03,
        2.85714286e-03,
    ],
    "n": [
        2.088937,
        2.169167,
        2.205069,
        2.227367,
        2.246464,
        2.269717,
        2.317580,
        2.374467,
        2.437140,
        2.513521,
        2.613011,
        2.769120,
    ],
    "L": [
        -6.703264,
        -7.152820,
        -7.960887,
        -9.278301,
        -9.809617,
        -9.623061,
        -10.058708,
        -10.260035,
        -10.849293,
        -10.097427,
        -7.047266,
        -4.038027,
    ],
    "d_nm": 1715.956871,
}



# SiO₂ - nodes (sigma, n, ln k) extracted from CERTUS logs (INDEX_SPLINE [CORRIDORS d] geometry base,

# certus_index_spline.log 2026-04-10): n visible/IR ~1.40-1.52, not a high-index oxide.

_SIO2_PRESET_SK = np.array(
    [
        1.923121e-04,
        4.400282e-04,
        7.351814e-04,
        1.006826e-03,
        1.278051e-03,
        1.797176e-03,
        2.196878e-03,
        2.534305e-03,
        2.831807e-03,
        3.100897e-03,
        3.348431e-03,
        3.578885e-03,
        3.795372e-03,
        4.000160e-03,
    ],
    dtype=np.float64,
)

_SIO2_PRESET_N = np.array(
    [
        1.401188,
        1.445316,
        1.457400,
        1.460256,
        1.463356,
        1.469598,
        1.475180,
        1.480329,
        1.486439,
        1.493496,
        1.499712,
        1.506259,
        1.511942,
        1.522015,
    ],
    dtype=np.float64,
)

_SIO2_PRESET_L = np.array(
    [
        -6.9875353,
        -8.0468854,
        -8.7255874,
        -9.8175088,
        -9.7072566,
        -9.9238170,
        -10.3392233,
        -10.6639135,
        -10.7415710,
        -9.5932497,
        -8.7760910,
        -7.6154403,
        -6.6359352,
        -6.6566466,
    ],
    dtype=np.float64,
)

SIO2_PRESET_D_NM: float = 1699.745274

SIO2_PRESET_KNOTS: dict[str, np.ndarray | float] = {
    "sk": _SIO2_PRESET_SK.copy(),
    "n": _SIO2_PRESET_N.copy(),
    "L": _SIO2_PRESET_L.copy(),
    "d_nm": SIO2_PRESET_D_NM,
}


def _clip_n_L_physical(n: np.ndarray, L: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Borne n et L = ln k après interpolation / extrapolation en σ (robustesse plage spectrale)."""
    n_c = np.clip(as_float64_1d(n), float(N_MIN_LIMIT), float(N_MAX_LIMIT))
    L_lo = float(np.log(1e-30))
    L_hi = float(np.log(max(float(K_MAX_LIMIT), 1e-30)))
    L_c = np.clip(as_float64_1d(L), L_lo, L_hi)
    return n_c, L_c


def _interp_n_L_linear_on_sigma(
    sk_ref: np.ndarray,
    n_ref: np.ndarray,
    L_ref: np.ndarray,
    sk_target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """PWL interpolation of *n* and *L* = ln *k* in sigma (nm⁻¹), linear in sigma.

    ``sk_ref`` and ``sk_target`` can be in any order; the result

    follows the order of indices of ``sk_target``.

    """

    sk_target = as_float64_1d(sk_target, copy=True)

    sk_ref = as_float64_1d(sk_ref)

    n_ref = as_float64_1d(n_ref)

    L_ref = as_float64_1d(L_ref)

    if sk_target.size == 0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)

    if sk_ref.size < 2 or n_ref.size != sk_ref.size or L_ref.size != sk_ref.size:
        raise ValueError("_interp_n_L_linear_on_sigma: inconsistent sk_ref, n_ref, L_ref.")

    o = np.argsort(sk_ref)

    sk_s = sk_ref[o]

    n_s = n_ref[o]

    L_s = L_ref[o]

    order_t = np.argsort(sk_target)

    inv_t = np.empty_like(order_t)

    inv_t[order_t] = np.arange(order_t.size)

    sk_sorted = sk_target[order_t]

    n_sorted = interp_sorted(sk_sorted, sk_s, n_s, left=float(n_s[0]), right=float(n_s[-1]))

    L_sorted = interp_sorted(sk_sorted, sk_s, L_s, left=float(L_s[0]), right=float(L_s[-1]))

    return _clip_n_L_physical(n_sorted[inv_t], L_sorted[inv_t])


def _project_nb2o5_preset_to_sigma_knots(
    target_sigma_knots: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Nb₂O₅ reference: n and L (ln k) on the current sigma mesh; *d* from preset."""

    sk_target = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()

    sk_ref = np.asarray(NB2O5_PRESET_KNOTS["sk"], dtype=np.float64).ravel()

    n_ref = np.asarray(NB2O5_PRESET_KNOTS["n"], dtype=np.float64).ravel()

    L_ref = np.asarray(NB2O5_PRESET_KNOTS["L"], dtype=np.float64).ravel()

    d_ref = float(NB2O5_PRESET_KNOTS["d_nm"])

    if sk_ref.size < 2 or sk_target.size == 0:
        return sk_target, np.zeros_like(sk_target), np.zeros_like(sk_target), d_ref

    n_out, L_out = _interp_n_L_linear_on_sigma(sk_ref, n_ref, L_ref, sk_target)

    return sk_target, n_out, L_out, d_ref


def _project_sio2_preset_to_sigma_knots(
    target_sigma_knots: np.ndarray,
    *,
    d_nm_hint: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """SiO₂ reference: tabulated n and L (ln k) (Smart Init) projected onto current sigma mesh."""

    sk_target = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()

    sk_ref = np.asarray(SIO2_PRESET_KNOTS["sk"], dtype=np.float64).ravel()

    n_ref = np.asarray(SIO2_PRESET_KNOTS["n"], dtype=np.float64).ravel()

    L_ref = np.asarray(SIO2_PRESET_KNOTS["L"], dtype=np.float64).ravel()

    d_ref = float(SIO2_PRESET_KNOTS["d_nm"])

    if sk_ref.size < 2 or sk_target.size == 0:
        return sk_target, np.zeros_like(sk_target), np.zeros_like(sk_target), d_ref

    n_out, L_out = _interp_n_L_linear_on_sigma(sk_ref, n_ref, L_ref, sk_target)

    d_out = (
        float(d_nm_hint)
        if d_nm_hint is not None and np.isfinite(float(d_nm_hint)) and float(d_nm_hint) > 0.0
        else d_ref
    )

    return sk_target, n_out, L_out, d_out


def _project_tabulated_nk_lam_preset_to_sigma_knots(
    lam_nm_ref: np.ndarray,
    n_ref: np.ndarray,
    k_ref: np.ndarray,
    target_sigma_knots: np.ndarray,
    *,
    d_nm_hint: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Tabulation (lambda, n, k) -> linear interpolation of *n* and ln *k* in sigma = 1/lambda."""

    sk_target = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()

    lam_nm_ref = np.asarray(lam_nm_ref, dtype=np.float64).ravel()

    n_ref = np.asarray(n_ref, dtype=np.float64).ravel()

    k_ref = np.asarray(k_ref, dtype=np.float64).ravel()

    if sk_target.size == 0:
        z = np.zeros(0, dtype=np.float64)

        return sk_target, z, z, 3000.0

    if lam_nm_ref.size < 2 or n_ref.size != lam_nm_ref.size or k_ref.size != lam_nm_ref.size:
        raise ValueError("preset (lambda,n,k): inconsistent lengths (>= 2 points).")

    sk_ref = 1.0 / np.maximum(lam_nm_ref, 1e-30)

    o = np.argsort(sk_ref)

    L_ref = np.log(np.maximum(k_ref[o], 1e-300))

    n_out, L_out = _interp_n_L_linear_on_sigma(sk_ref[o], n_ref[o], L_ref, sk_target)

    d_out = (
        float(d_nm_hint)
        if d_nm_hint is not None and np.isfinite(float(d_nm_hint)) and float(d_nm_hint) > 0.0
        else 3000.0
    )

    return sk_target, n_out, L_out, d_out


def _ta2o5_tabulation_extended() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ta₂O₅ : points aux bords UV/IR (extrapolation linéaire en λ) pour limiter l’extrapolation plate en σ."""
    lam = np.array([300.0, 400.0, 1500.0, 4500.0], dtype=np.float64)
    n = np.array([2.577294348, 2.286667022, 2.107230774, 2.016490462], dtype=np.float64)
    k = np.array([5.320702e-3, 2.15945e-5, 7.17773e-5, 2.18446e-4], dtype=np.float64)
    lam_lo = 200.0
    n_lo = n[0] + (n[1] - n[0]) * (lam_lo - lam[0]) / (lam[1] - lam[0])
    k_lo = k[0] + (k[1] - k[0]) * (lam_lo - lam[0]) / (lam[1] - lam[0])
    lam_hi = 8000.0
    n_hi = n[3] + (n[3] - n[2]) * (lam_hi - lam[3]) / (lam[3] - lam[2])
    k_hi = k[3] + (k[3] - k[2]) * (lam_hi - lam[3]) / (lam[3] - lam[2])
    lam_f = np.array([lam_lo, lam[0], lam[1], lam[2], lam[3], lam_hi], dtype=np.float64)
    n_f = np.array([n_lo, n[0], n[1], n[2], n[3], n_hi], dtype=np.float64)
    k_f = np.array([k_lo, k[0], k[1], k[2], k[3], k_hi], dtype=np.float64)
    k_f = np.clip(k_f, 1e-30, float(K_MAX_LIMIT))
    return lam_f, n_f, k_f


TA2O5_PRESET_LAM_NM, TA2O5_PRESET_N, TA2O5_PRESET_K = _ta2o5_tabulation_extended()


def project_manual_material_preset(
    preset_id: str,
    target_sigma_knots: np.ndarray,
    *,
    d_nm_hint: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Single entry point: ``nb2o5`` | ``sio2`` | ``ta2o5``."""

    key = str(preset_id).strip().lower().replace("₂", "2").replace("₅", "5")

    if key in ("nb2o5", "nb205"):
        return _project_nb2o5_preset_to_sigma_knots(target_sigma_knots)

    if key in ("sio2", "si2o2"):
        return _project_sio2_preset_to_sigma_knots(target_sigma_knots, d_nm_hint=d_nm_hint)

    if key in ("ta2o5", "ta205"):
        return _project_tabulated_nk_lam_preset_to_sigma_knots(
            TA2O5_PRESET_LAM_NM,
            TA2O5_PRESET_N,
            TA2O5_PRESET_K,
            target_sigma_knots,
            d_nm_hint=d_nm_hint,
        )

    raise ValueError(f"unknown material preset: {preset_id!r} (expected nb2o5, sio2, ta2o5).")
