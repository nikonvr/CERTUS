#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pretraitement spectral partage (CERTUS Curve Smoother, Substrate Index, etc.)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import find_peaks, savgol_filter


def _ensure_odd(n: int) -> int:
    pass
    if n < 3:
        return 3
    if n % 2 == 0:
        n += 1
    return n


def _safe_clip_percent(y: np.ndarray) -> np.ndarray:
    return np.clip(y, 0.0, 100.0)


def _prepare_xy(x_lambda: np.ndarray, y: np.ndarray):
    x = np.asarray(x_lambda, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)

    if x.size != y.size:
        n = min(int(x.size), int(y.size))
        x = x[:n]
        y = y[:n]

    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]

    if x.size < 5:
        raise ValueError("Not enough valid points for smoothing.")

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    unique_x, inverse = np.unique(x, return_inverse=True)
    if unique_x.size != x.size:
        y_acc = np.zeros_like(unique_x, dtype=float)
        cnt = np.zeros_like(unique_x, dtype=float)
        for i, idx in enumerate(inverse):
            y_acc[idx] += y[i]
            cnt[idx] += 1.0
        y = y_acc / np.maximum(cnt, 1.0)
        x = unique_x

    return x, y


def _remove_spikes(y: np.ndarray, z_thresh: float = 5.0):
    """Replace isolated spikes by local interpolation when possible."""
    y = np.asarray(y, dtype=float).copy()
    if y.size < 7:
        return y

    w = _ensure_odd(min(9, y.size - (1 if y.size % 2 == 0 else 0)))
    try:
        trend = savgol_filter(y, window_length=w, polyorder=min(2, w - 1))
    except Exception:
        trend = np.full_like(y, np.median(y))

    resid = y - trend
    mad = np.median(np.abs(resid - np.median(resid)))
    if mad <= 1e-12:
        return y

    robust_z = 0.6745 * resid / mad
    bad = np.abs(robust_z) > z_thresh
    if not np.any(bad):
        return y

    good_idx = np.where(~bad)[0]
    if good_idx.size < 2:
        return y

    y[bad] = np.interp(np.where(bad)[0], good_idx, y[good_idx])
    return y


def _interpolate_uniform_in_k(x_lambda: np.ndarray, y: np.ndarray, n_points: int | None = None):
    x, y = _prepare_xy(x_lambda, y)
    y = _remove_spikes(y)

    k = 1.0 / x
    order = np.argsort(k)
    k = k[order]
    y = y[order]

    if n_points is None:
        n_points = len(k)

    n_points = max(int(n_points), 5)
    k_uniform = np.linspace(float(k.min()), float(k.max()), n_points)

    # Linear interpolation is robust; fallback to edge values if needed.
    f = interp1d(
        k,
        y,
        kind="linear",
        fill_value=(float(y[0]), float(y[-1])),
        bounds_error=False,
        assume_sorted=True,
    )
    y_uniform = f(k_uniform)

    return x, k_uniform, y_uniform


def _estimate_fringe_period(k: np.ndarray, y: np.ndarray):
    y_centered = y - np.median(y)
    amp = np.std(y_centered)
    if amp < 1e-9:
        return (k.max() - k.min()) / 10.0, 0, 0.0

    prominence = max(0.25 * amp, 1e-6)
    distance = max(2, len(k) // 50)
    peaks, _ = find_peaks(y_centered, prominence=prominence, distance=distance)
    valleys, _ = find_peaks(-y_centered, prominence=prominence, distance=distance)
    all_extrema = np.sort(np.concatenate([peaks, valleys]))
    if all_extrema.size >= 3:
        diffs = np.diff(k[all_extrema])
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if diffs.size > 0:
            return float(np.median(diffs)), int(all_extrema.size), float(np.std(diffs) / max(np.mean(diffs), 1e-12))
    return (k.max() - k.min()) / 12.0, int(all_extrema.size), 1.0


def _estimate_noise_level(y: np.ndarray):
    if len(y) < 7:
        return float(np.std(y))

    w = _ensure_odd(min(11, len(y) - (1 if len(y) % 2 == 0 else 0)))
    if w >= len(y):
        w = _ensure_odd(max(5, len(y) - 1))

    try:
        trend = savgol_filter(y, window_length=w, polyorder=min(2, w - 1))
    except Exception:
        trend = np.full_like(y, np.median(y))

    resid = y - trend
    mad = np.median(np.abs(resid - np.median(resid)))
    return float(1.4826 * mad)


def _choose_params(level: str, period_k: float, noise: float, span_k: float, n_points: int, *, fringe_count: int = 0, fringe_jitter: float = 0.0):
    level = str(level).strip().lower()
    if level in {"faible", "low"}:
        mult = 0.55
        poly = 2
        alpha = 0.22
    elif level in {"moyen", "medium"}:
        mult = 0.95
        poly = 2
        alpha = 0.42
    elif level in {"fort", "high"}:
        mult = 1.45
        poly = 2
        alpha = 0.62
    else:
        mult = 0.95
        poly = 2
        alpha = 0.42

    dk = span_k / max(n_points - 1, 1)
    window_pts = period_k / max(dk, 1e-12)
    window_pts *= mult

    # Stronger noise -> slightly larger windows, but cap it to preserve fringes.
    if noise > 0:
        ref = np.percentile(np.abs(np.linspace(-1, 1, n_points)), 75) or 1.0
        noise_ratio = min(noise / max(ref, 1e-12), 3.0)
        window_pts *= (1.0 + 0.05 * noise_ratio)

    # More regular fringe trains allow a slightly larger base window.
    if fringe_count >= 6 and fringe_jitter < 0.35:
        window_pts *= 1.08
    elif fringe_count <= 2:
        window_pts *= 0.92

    window_pts = _ensure_odd(window_pts)
    max_valid = n_points - 1 if n_points % 2 == 0 else n_points
    max_valid = max(5, max_valid)
    window_pts = min(window_pts, max_valid)
    if window_pts <= poly:
        window_pts = _ensure_odd(poly + 3)
    if window_pts > max_valid:
        window_pts = max_valid if max_valid % 2 == 1 else max_valid - 1

    heavy_window = _ensure_odd(min(max_valid, int(window_pts * 1.6)))
    if heavy_window <= window_pts:
        heavy_window = _ensure_odd(window_pts + 2)
    heavy_window = min(heavy_window, max_valid)
    if heavy_window <= poly:
        heavy_window = _ensure_odd(poly + 5)

    return int(window_pts), int(poly), int(heavy_window), float(alpha)


def smooth_spectrum_auto(x_lambda: np.ndarray, y: np.ndarray, level: str = "moyen"):
    x, k_uniform, y_uniform = _interpolate_uniform_in_k(x_lambda, y)

    # Final robustness pass after interpolation.
    y_uniform = _remove_spikes(y_uniform, z_thresh=5.0)

    period_k, fringe_count, fringe_jitter = _estimate_fringe_period(k_uniform, y_uniform)
    noise = _estimate_noise_level(y_uniform)
    span_k = float(k_uniform.max() - k_uniform.min())

    window_base, poly, window_heavy, alpha = _choose_params(
        level=level,
        period_k=period_k,
        noise=noise,
        span_k=span_k,
        n_points=len(k_uniform),
        fringe_count=fringe_count,
        fringe_jitter=fringe_jitter,
    )

    try:
        y_base = savgol_filter(y_uniform, window_length=window_base, polyorder=poly, mode="interp")
    except Exception:
        y_base = y_uniform.copy()

    try:
        y_heavy = savgol_filter(y_uniform, window_length=window_heavy, polyorder=poly, mode="interp")
    except Exception:
        y_heavy = y_base.copy()

    # Preserve local structure by mixing the two scales.
    y_smoothed_uniform = (1.0 - alpha) * y_base + alpha * y_heavy
    y_smoothed_uniform = _safe_clip_percent(y_smoothed_uniform)

    f_back = interp1d(
        k_uniform,
        y_smoothed_uniform,
        kind="linear",
        fill_value=(float(y_smoothed_uniform[0]), float(y_smoothed_uniform[-1])),
        bounds_error=False,
        assume_sorted=True,
    )
    # On ré-évalue sur l'abscisse D'ORIGINE, pas sur le `x` renvoyé par _prepare_xy :
    # celui-ci a été trié par ordre croissant et dédupliqué. Évaluer dessus renvoyait un
    # vecteur aligné sur l'ordre TRIÉ, que les appelants réaffectaient positionnellement
    # sur l'ordre du fichier — un spectre mesuré en lambda décroissant (sortie standard de
    # beaucoup de spectrophotomètres) ressortait donc EN MIROIR, sans aucune erreur.
    # La déduplication changeait en outre la longueur du vecteur (ValueError chez l'appelant).
    x_original = np.asarray(x_lambda, dtype=float).ravel()
    y_smoothed = f_back(1.0 / x_original)

    quality_score = 1.0
    if np.isfinite(period_k) and period_k > 0:
        quality_score *= 1.0 / (1.0 + max(0.0, fringe_jitter))
    quality_score *= 1.0 / (1.0 + min(max(noise, 0.0), 10.0) * 0.15)
    quality_score *= 1.0 if fringe_count >= 3 else 0.88
    quality_score = float(np.clip(quality_score, 0.0, 1.0))

    diagnostics = {
        "level": level,
        "window_base": window_base,
        "polyorder": poly,
        "window_heavy": window_heavy,
        "estimated_period_k": period_k,
        "noise_level": noise,
        "fringe_count": fringe_count,
        "fringe_jitter": fringe_jitter,
        "alpha": alpha,
        "samples_kept": int(x.size),
        "quality_score": quality_score,
        "quality_label": "good" if quality_score >= 0.75 else ("degraded" if quality_score >= 0.45 else "poor"),
    }

    return _safe_clip_percent(y_smoothed), diagnostics


def smooth_dataframe_auto(df: pd.DataFrame, level: str = "moyen") -> tuple[pd.DataFrame, dict]:
    if df is None or df.shape[1] < 2:
        raise ValueError("DataFrame must contain at least one wavelength column and one spectrum column.")

    x = df.iloc[:, 0].values
    out = df.copy()
    last_info = {}

    for col in out.columns[1:]:
        y = out[col].values
        y_sm, info = smooth_spectrum_auto(x, y, level=level)
        out[col] = y_sm
        last_info = info

    return out, last_info


def summarize_smoothing_quality(info: dict | None) -> str:
    """Return a compact human-readable quality summary for logs/UI."""

    if not info:
        return "smoother: unavailable"

    q = info.get("quality_score", None)
    label = str(info.get("quality_label", "unknown"))
    base = info.get("window_base", "?")
    heavy = info.get("window_heavy", "?")
    period = info.get("estimated_period_k", None)
    period_txt = f"period_k={float(period):.4g}" if isinstance(period, (int, float, np.floating)) else "period_k=?"
    q_txt = f"q={float(q):.3f}" if isinstance(q, (int, float, np.floating)) else "q=?"
    return f"smoother[{label}] {q_txt} base={base} heavy={heavy} {period_txt}"


def auto_tune_savgol_params(
    x_lambda: np.ndarray,
    y_mat: np.ndarray,
    preset: str = "Medium (Balanced)",
) -> tuple[int, int, int]:
    """Estimate Savitzky-Golay window parameters from spectral data.

    Parameters
    ----------
    x_lambda : 1-D wavelength array (nm).
    y_mat    : 2-D array (n_spectra, n_points) or 1-D (n_points,).
    preset   : smoothing preset — one of:
               "Soft (High Fidelity)", "Medium (Balanced)", "Extreme (Aggressive)".
               Unknown values fall back to "Medium (Balanced)".

    Returns
    -------
    (window_base, poly, window_heavy) — all int, both windows are odd,
    window_heavy >= window_base.
    """
    _PRESET_MAP: dict[str, str] = {
        "soft (high fidelity)": "faible",
        "medium (balanced)": "moyen",
        "extreme (aggressive)": "fort",
    }
    level = _PRESET_MAP.get(str(preset).strip().lower(), "moyen")

    y_mat = np.asarray(y_mat, dtype=float)
    x = np.asarray(x_lambda, dtype=float).ravel()

    y_rep: np.ndarray = np.mean(y_mat, axis=0) if y_mat.ndim == 2 else y_mat.ravel()

    try:
        _x_s, k_uniform, y_uniform = _interpolate_uniform_in_k(x, y_rep)
        y_uniform = _remove_spikes(y_uniform, z_thresh=5.0)
        period_k, fringe_count, fringe_jitter = _estimate_fringe_period(k_uniform, y_uniform)
        noise = _estimate_noise_level(y_uniform)
        span_k = float(k_uniform.max() - k_uniform.min())
        n_pts = len(k_uniform)
    except Exception:
        n_pts = max(int(x.size), 10)
        period_k = 1e-4
        noise = 0.0
        span_k = 1e-3
        fringe_count = 0
        fringe_jitter = 0.0

    try:
        window_base, poly, window_heavy, _alpha = _choose_params(
            level=level,
            period_k=period_k,
            noise=noise,
            span_k=span_k,
            n_points=n_pts,
            fringe_count=fringe_count,
            fringe_jitter=fringe_jitter,
        )
    except Exception:
        window_base = _ensure_odd(max(3, n_pts // 8))
        poly = 2
        window_heavy = _ensure_odd(max(window_base + 2, int(window_base * 1.6)))

    return int(window_base), int(poly), int(window_heavy)


def auto_tune_savgol_params_from_dataframe(
    x_lambda: np.ndarray,
    df: pd.DataFrame,
    preset: str = "Medium (Balanced)",
) -> tuple[int, int, int]:
    """Convenience wrapper: extract y_mat from a DataFrame and call auto_tune_savgol_params.

    Assumes column 0 is the wavelength axis; remaining columns are spectra.
    """
    y_mat = df.iloc[:, 1:].values.T  # shape (n_spectra, n_points)
    return auto_tune_savgol_params(x_lambda, y_mat, preset)


def dynamic_savgol_blend(x: np.ndarray, y: np.ndarray, base_window: int, poly: int, heavy_window: int = 0) -> np.ndarray:
    """Backward-compatible wrapper used by older callers.

    When explicit windows are provided, preserve that intent. Otherwise fall back
    to the automatic smoother for robustness.
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # Support 2-D input (n_spectra, n_points): apply row-wise and stack.
    if y.ndim == 2:
        return np.vstack(
            [dynamic_savgol_blend(x, row, base_window, poly, heavy_window) for row in y]
        )

    base_window = int(base_window)
    poly = int(poly)
    heavy_window = int(heavy_window)

    try:
        if base_window >= 3 and base_window > poly:
            base_window = _ensure_odd(base_window)
            if heavy_window < base_window:
                heavy_window = _ensure_odd(max(base_window + 2, int(round(base_window * 1.6))))
            heavy_window = max(heavy_window, base_window)
            if heavy_window % 2 == 0:
                heavy_window += 1

            x_prep, k_uniform, y_uniform = _interpolate_uniform_in_k(x, y)
            y_uniform = _remove_spikes(y_uniform, z_thresh=5.0)

            max_valid = len(k_uniform) - 1 if len(k_uniform) % 2 == 0 else len(k_uniform)
            max_valid = max(5, max_valid)
            base_window = min(base_window, max_valid)
            heavy_window = min(heavy_window, max_valid)
            if base_window <= poly:
                base_window = _ensure_odd(poly + 3)
            if heavy_window <= base_window:
                heavy_window = _ensure_odd(base_window + 2)
            heavy_window = min(heavy_window, max_valid)
            if heavy_window <= poly:
                heavy_window = _ensure_odd(poly + 5)

            y_base = savgol_filter(y_uniform, window_length=base_window, polyorder=poly, mode="interp")
            try:
                y_heavy = savgol_filter(y_uniform, window_length=heavy_window, polyorder=poly, mode="interp")
            except Exception:
                y_heavy = y_base.copy()

            y_smoothed_uniform = 0.58 * y_base + 0.42 * y_heavy
            f_back = interp1d(
                k_uniform,
                _safe_clip_percent(y_smoothed_uniform),
                kind="linear",
                fill_value=(float(y_smoothed_uniform[0]), float(y_smoothed_uniform[-1])),
                bounds_error=False,
                assume_sorted=True,
            )
            # Idem : `x` est l'abscisse d'origine, `x_prep` est triée/dédupliquée.
            return _safe_clip_percent(f_back(1.0 / x))
    except Exception:
        pass

    y_smoothed, _info = smooth_spectrum_auto(x, y, level="moyen")
    return y_smoothed
