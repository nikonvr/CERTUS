#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

Pretraitement spectral partage (CERTUS Curve Smoother, Substrate Index, etc.).

"""


from __future__ import annotations


import numpy as np

import pandas as pd

from scipy.signal import savgol_filter


# Poids lambda pour le melange brut / Savitzky-Golay (identique anciens modules).

_WL_RAW_LO, _WL_RAW_HI = 2350.0, 3200.0

_WL_HEAVY_LO, _WL_HEAVY_HI = 4400.0, 4800.0


def dynamic_savgol_blend(

    x: np.ndarray,

    y: np.ndarray,

    base_window: int,

    poly: int,

    heavy_window: int = 0,

) -> np.ndarray:

    """Lissage adaptatif : melange y brut, S-G  base  et S-G  heavy  selon lambda."""

    n_pts = y.shape[-1]

    y_base = savgol_filter(y, window_length=base_window, polyorder=poly, axis=-1)

    if heavy_window == 0:

        w_heavy = min(base_window * 4, n_pts - (1 if n_pts % 2 == 0 else 0))

    else:

        w_heavy = min(heavy_window, n_pts - (1 if n_pts % 2 == 0 else 0))

    if w_heavy % 2 == 0:

        w_heavy -= 1

    w_heavy = max(w_heavy, base_window)

    try:

        y_heavy = savgol_filter(y, window_length=w_heavy, polyorder=poly, axis=-1)

    except ValueError:

        y_heavy = y_base

    w_raw = np.interp(x, [_WL_RAW_LO, _WL_RAW_HI], [1.0, 0.0])

    w_high = np.interp(x, [_WL_HEAVY_LO, _WL_HEAVY_HI], [0.0, 1.0])

    w_mid = 1.0 - w_raw - w_high

    y_smoothed = (y * w_raw) + (y_base * w_mid) + (y_heavy * w_high)

    return np.round(y_smoothed, 2)


def auto_tune_savgol_params(

    x: np.ndarray,

    y_mat: np.ndarray,

    mode: str,

) -> tuple[int, int, int]:

    """

    Choisit (window_base, poly, window_heavy) pour un empilement de spectres (lignes = courbes).

    *y_mat* : forme (n_curves, n_lambda).

    """

    penalties = {

        "Soft (High Fidelity)": (150.0, 600.0),

        "Medium (Balanced)": (400.0, 1500.0),

        "Hard (Smooth)": (1000.0, 3500.0),

        "Extreme (Aggressive)": (2500.0, 8000.0),

    }

    pen_base, pen_heavy = penalties.get(mode, (400.0, 1500.0))

    test_polys = [2] if "Extreme" in mode else [2, 3, 4]

    best_score_b, best_score_h = float("inf"), float("inf")

    best_w, best_hw, best_p = 15, 25, 3

    y_mat = np.asarray(y_mat, dtype=np.float64)

    n_pts = y_mat.shape[-1]

    try:

        w_macro = 51 if n_pts >= 51 else (n_pts - 1 if n_pts % 2 == 0 else n_pts)

        w_macro = max(3, w_macro)

        y_macro = savgol_filter(y_mat, window_length=w_macro, polyorder=3, axis=-1)

    except ValueError:

        y_macro = y_mat

    d2y = np.abs(np.diff(y_macro, n=2, axis=-1))

    d2y = np.pad(d2y, ((0, 0), (1, 1)), mode="edge")

    max_d2y = np.max(d2y, axis=-1, keepdims=True) + 1e-9

    w_curv = 1.0 + (50.0 * (d2y / max_d2y))

    for p in test_polys:

        for w in range(max(11, p + 2), 95, 2):

            if w % 2 == 0:

                continue

            try:

                y_sm = savgol_filter(y_mat, window_length=w, polyorder=p, axis=-1)

            except ValueError:

                continue

            rough = np.sum(np.abs(np.diff(y_sm, axis=-1)))

            fit = np.sum(((y_mat - y_sm) ** 2) * w_curv)

            score_b = (rough * pen_base) + fit

            score_h = (rough * pen_heavy) + fit

            if score_b < best_score_b:

                best_score_b, best_w, best_p = score_b, w, p

            if score_h < best_score_h:

                best_score_h, best_hw = score_h, w

    best_hw = max(best_hw, best_w + 4)

    return best_w, best_p, best_hw


def auto_tune_savgol_params_from_dataframe(

    x: np.ndarray,

    df: pd.DataFrame,

    mode: str,

) -> tuple[int, int, int]:

    """Auto-tune a partir dun DataFrame (colonne 0 = lambda, suivantes = spectres)."""

    y_mat = df.iloc[:, 1:].values.T

    return auto_tune_savgol_params(x, y_mat, mode)
