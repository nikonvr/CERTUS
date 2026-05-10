from __future__ import annotations


import json

import logging

import time

from typing import Any


import numpy as np

from certus_physics import calculate_RT_vectorized_real, calculate_bare_substrate_RT


def log_structured_json_event(
    log: logging.Logger | None,
    channel: str,
    event: str,
    *,
    seq: str | None = None,
    **fields: Any,
) -> None:
    """Emit a single-line structured JSON log entry for machine parsing.

    Parameters
    ----------
    log : logging.Logger or None
        Target logger. No-op if None.
    channel : str
        Log channel prefix (e.g. ``SPLINE_PIPELINE_JSON``).
    event : str
        Event name embedded in the JSON payload.
    seq : str, optional
        Sequence tag for ordering in multi-phase pipelines.
    **fields
        Arbitrary key-value pairs added to the JSON payload.
    """

    if log is None:
        return

    payload: dict[str, Any] = {"event": str(event), "ts_epoch_s": float(time.time())}

    if seq is not None:
        payload["seq"] = str(seq)

    payload.update(fields)

    try:
        log.info("%s %s", channel, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
        pass


def _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute transmittance ratio T_film / T_bare_substrate (with backside).

    Parameters
    ----------
    lam : array_like
        Wavelengths in nm.
    n_l, k_l : array_like
        Film refractive index (n) and extinction coefficient (k), same size as *lam*.
    d_nm : float
        Film thickness in nm.
    n_sub : array_like
        Substrate refractive index, same size as *lam*.

    Returns
    -------
    np.ndarray
        T_film_total / T_substrate_bare, element-wise.
    """

    n_pts = len(lam)

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    # Calcul exact R et T (avec backside)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    # T du substrate nu (avec backside) - Securite 1e-7 pour eviter NaN

    t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam, n_sub), 1e-7)

    return t_film_tot / t_sub_nu


_THICK_BUF = np.empty(1, dtype=np.float64)  # Pre-allocated, rewritten in-place


def _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute absolute transmittance T_film_total (with backside correction).

    Same TMM call as :func:`_ratio_theoretical_from_nk` but without
    dividing by the bare substrate transmittance.

    Parameters
    ----------
    lam, n_l, k_l, d_nm, n_sub
        See :func:`_ratio_theoretical_from_nk`.

    Returns
    -------
    np.ndarray
        Absolute film transmittance, element-wise.
    """

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(len(lam), 1)

    # Calcul exact R et T (avec backside)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    return t_film_tot


def _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute reflectance ratio R_film / T_bare_substrate.

    Used in the R/T_nu experimental protocol where both R and T are
    normalized by the bare substrate transmittance.

    Parameters
    ----------
    lam, n_l, k_l, d_nm, n_sub
        See :func:`_ratio_theoretical_from_nk`.

    Returns
    -------
    np.ndarray
        R_film_total / T_substrate_bare, element-wise.
    """

    n_pts = len(lam)

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam, n_sub), 1e-7)

    return r_film_tot / t_sub_nu


def spectral_rmse_weights(lam, weight_space="log"):
    """Trapezoidal quadrature weights on ln(lambda) for spectral RMSE.

    Compensates non-uniform sampling density so that RMSE is not biased
    toward densely sampled spectral regions.

    Parameters
    ----------
    lam : array_like
        Wavelengths in nm (any order).
    weight_space : str, optional
        Reserved for future use. Currently always ``"log"``.

    Returns
    -------
    np.ndarray
        Weight array (same size as *lam*), normalized so that ``sum(w) == len(lam)``.
    """

    lam = np.asarray(lam, dtype=np.float64).ravel()

    n = lam.size

    if n < 2:
        return np.ones_like(lam)

    # Calcul des inter-distances en log(lambda)

    log_lam = np.log(np.maximum(lam, 1e-9))

    # Gradient central (schema trapezoidal)

    w = np.zeros_like(log_lam)

    w[1:-1] = 0.5 * (log_lam[2:] - log_lam[:-2])

    w[0] = log_lam[1] - log_lam[0]

    w[-1] = log_lam[-1] - log_lam[-2]

    # On travaille en value absolue pour gerer les grilles decroissantes

    w = np.abs(w)

    # Normalisation : la somme des weights est egale au nombre de points

    # pour garder une RMSE coherente avec l'echelle physique habituelle.

    sw = np.sum(w)

    if sw > 0:
        w = w * (float(n) / sw)

    else:
        w = np.ones_like(lam)

    return w


def _lam_uniform_grid(lo_h: float, hi_h: float, step: float) -> np.ndarray:
    """Generate a uniform wavelength grid snapped to multiples of *step*.

    Parameters
    ----------
    lo_h, hi_h : float
        Wavelength range bounds in nm.
    step : float
        Grid step in nm (e.g. 2.0, 5.0, 10.0).

    Returns
    -------
    np.ndarray
        Sorted grid points in [ceil(lo/step)*step, floor(hi/step)*step].
        Empty array if *lo_h* >= *hi_h* or non-finite.
    """

    if not (np.isfinite(lo_h) and np.isfinite(hi_h) and hi_h > lo_h):
        return np.array([], dtype=np.float64)

    st = float(np.ceil(lo_h / step) * step)

    en = float(np.floor(hi_h / step) * step)

    if en < st - 1e-9:
        return np.array([0.5 * (lo_h + hi_h)], dtype=np.float64)

    if abs(en - st) < 1e-9:
        return np.array([st], dtype=np.float64)

    return np.arange(st, en + 1e-9, step, dtype=np.float64)


def _sorted_finite_sigma_knots(sigma_knots) -> np.ndarray:
    """Clean and sort sigma knots: keep only finite, strictly positive values.

    Parameters
    ----------
    sigma_knots : array_like or None
        Raw knot positions in sigma space (1/nm).

    Returns
    -------
    np.ndarray
        Sorted unique finite knots (empty array if none valid).
    """

    arr = np.asarray(sigma_knots if sigma_knots is not None else [], dtype=np.float64).ravel()

    arr = arr[np.isfinite(arr) & (arr > 0.0)]

    if arr.size == 0:
        return np.empty(0, dtype=np.float64)

    return np.unique(np.sort(arr))
