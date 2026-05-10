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
    """Une ligne ``<channel> {...}`` pour grep / scripts (AUTO_BEST_JSON, CONT_JSON, SPLINE_PIPELINE_JSON, …)."""

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
    """

    Calcule le ratio theorique exact T = T_film_total / T_substrat_nu.

    Inclut la correction de face arriere exacte (inconsistent cavity).

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
    """

    Calcule la transmittance absolue T_film_total (avec correction face arriere).

    Identique a _ratio_theoretical_from_nk mais sans normaliser par T_substrat_nu.

    """

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(len(lam), 1)

    # Calcul exact R et T (avec backside)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    return t_film_tot


def _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """

    Calcule le ratio theorique exact R_rel = R_total / T_substrat_nu.

    Selon le protocole experimental R/Tnu.

    """

    n_pts = len(lam)

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam, n_sub), 1e-7)

    return r_film_tot / t_sub_nu


def spectral_rmse_weights(lam, weight_space="log"):
    """

    Genere les weights pour le calcul de la RMSE en echelle Log-Lambda.

    Utilise le gradient de ln(lambda) pour compenser la densite d'echantillonnage

    (quadrature trapezoidale sur ln lambda ; ``weight_space`` reserve pour compatibilite).

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
