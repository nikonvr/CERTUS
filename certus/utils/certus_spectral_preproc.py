#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pretraitement spectral partage (CERTUS Curve Smoother, Substrate Index, etc.)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import find_peaks, savgol_filter


def _ensure_odd(n: int) -> int:
    n = int(round(n))
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
        return (k.max() - k.min()) / 10.0

    prominence = max(0.25 * amp, 1e-6)
    distance = max(2, len(k) // 50)
    peaks, _ = find_peaks(y_centered, prominence=prominence, distance=distance)
    valleys, _ = find_peaks(-y_centered, prominence=prominence, distance=distance)
    all_extrema = np.sort(np.concatenate([peaks, valleys]))
    if all_extrema.size >= 3:
        diffs = np.diff(k[all_extrema])
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if diffs.size > 0:
            return float(np.median(diffs))
    return (k.max() - k.min()) / 12.0


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


def _choose_params(level: str, period_k: float, noise: float, span_k: float, n_points: int):
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

    period_k = _estimate_fringe_period(k_uniform, y_uniform)
    noise = _estimate_noise_level(y_uniform)
    span_k = float(k_uniform.max() - k_uniform.min())

    window_base, poly, window_heavy, alpha = _choose_params(
        level=level,
        period_k=period_k,
        noise=noise,
        span_k=span_k,
        n_points=len(k_uniform),
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
    y_smoothed = f_back(1.0 / x)

    return _safe_clip_percent(y_smoothed), {
        "level": level,
        "window_base": window_base,
        "polyorder": poly,
        "window_heavy": window_heavy,
        "estimated_period_k": period_k,
        "noise_level": noise,
    }


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


def dynamic_savgol_blend(x: np.ndarray, y: np.ndarray, base_window: int, poly: int, heavy_window: int = 0) -> np.ndarray:
    """Backward-compatible wrapper used by older callers.

    The old API expected a direct blend in wavelength space. We now map it to the
    new automatic smoother while preserving the intent of the call signature.
    """

    del base_window, poly, heavy_window
    y_smoothed, _info = smooth_spectrum_auto(np.asarray(x, dtype=float), np.asarray(y, dtype=float), level="moyen")
    return y_smoothed
