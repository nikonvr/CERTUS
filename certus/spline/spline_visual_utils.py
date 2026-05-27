#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Headless utilities for live snaps and clipboard export (INDEX SPLINE GUI)."""

from __future__ import annotations


import numpy as np


def snap_spline_visual_dict(r: dict) -> dict:
    """Defensive copy of numpy arrays to freeze a live snap / best RMSE."""

    out = dict(r)

    for k in (
        "lam_nm",
        "n_lam",
        "k_lam",
        "t_theo",
        "r_theo",  # defensive copy: consistency between displayed spectrum / export after live merge
        "sigma_knots",
        "x",
        "n_nodes_physical",
        "L_nodes",
        "corridor_reference_n_lam",
        "corridor_reference_k_lam",
    ):
        if k not in out or out[k] is None:
            continue

        out[k] = np.asarray(out[k], dtype=np.float64).copy()

    return out


def live_monitor_nk_clipboard_tsv_2nm(lam: np.ndarray, n_: np.ndarray, k_: np.ndarray) -> str | None:
    """

    TSV: lambda (nm) increasing integers, n and k linearly interpolated on a 2 nm step grid

    between min(lambda) and max(lambda).

    """

    lam = np.asarray(lam, dtype=np.float64).ravel()

    n_ = np.asarray(n_, dtype=np.float64).ravel()

    k_ = np.asarray(k_, dtype=np.float64).ravel()

    m = int(min(lam.size, n_.size, k_.size))

    if m == 0:
        return None

    lam, n_, k_ = lam[:m], n_[:m], k_[:m]

    ok = np.isfinite(lam) & np.isfinite(n_) & np.isfinite(k_)

    lam, n_, k_ = lam[ok], n_[ok], k_[ok]

    if lam.size == 0:
        return None

    o = np.argsort(lam, kind="mergesort")

    lam_s, n_s, k_s = lam[o], n_[o], k_[o]

    u_lam = np.unique(lam_s)

    if u_lam.size < lam_s.size:
        n_u = np.array([float(np.mean(n_s[lam_s == ll])) for ll in u_lam], dtype=np.float64)

        k_u = np.array([float(np.mean(k_s[lam_s == ll])) for ll in u_lam], dtype=np.float64)

    else:
        n_u, k_u = n_s, k_s

    lo = float(u_lam[0])

    hi = float(u_lam[-1])

    i_lo = int(np.ceil(lo))

    i_hi = int(np.floor(hi))

    if i_hi < i_lo:
        lam_i = np.array([int(round(0.5 * (lo + hi)))], dtype=np.int64)

    else:
        lam_i = np.arange(i_lo, i_hi + 1, 2, dtype=np.int64)

    lam_grid = lam_i.astype(np.float64)

    if lam_grid.size == 0:
        lam_i = np.unique(np.round(u_lam).astype(np.int64))

        lam_grid = lam_i.astype(np.float64)

    n_i = np.interp(lam_grid, u_lam, n_u, left=np.nan, right=np.nan)

    k_i = np.interp(lam_grid, u_lam, k_u, left=np.nan, right=np.nan)

    good = np.isfinite(n_i) & np.isfinite(k_i)

    lam_i, n_i, k_i = lam_i[good], n_i[good], k_i[good]

    if lam_i.size == 0:
        return None

    lines = ["lambda_nm\tn\tk"]

    for i in range(int(lam_i.size)):
        lines.append(f"{int(lam_i[i])}\t{n_i[i]:.10f}\t{k_i[i]:.10e}")

    return "\n".join(lines)
