# -*- coding: utf-8 -*-

"""Shared contract helpers for live corridor RMSE payloads."""

from __future__ import annotations

from typing import Any

import numpy as np

CORRIDOR_LIVE_STATUS = "manual_grid_live"
CORRIDOR_KEYS = {
    "d_values": ("profile_d_values_nm", "corridor_d_plot", "d_plot"),
    "rmse_values": ("profile_d_rmse_values", "corridor_rmse_plot", "r_plot"),
    "d_vis": ("corridor_d_vis", "profile_d_values_nm"),
    "rmse_vis": ("corridor_rmse_vis", "profile_d_rmse_values"),
}


def _first_array(src: dict[str, Any], keys: tuple[str, ...]) -> np.ndarray:
    for key in keys:
        if key in src:
            return np.asarray(src.get(key, []), dtype=np.float64).ravel()
    return np.asarray([], dtype=np.float64)


def normalize_corridor_live_payload(src: dict[str, Any]) -> dict[str, Any]:
    d_vals = _first_array(src, CORRIDOR_KEYS["d_values"])
    r_vals = _first_array(src, CORRIDOR_KEYS["rmse_values"])
    d_vis = _first_array(src, CORRIDOR_KEYS["d_vis"])
    r_vis = _first_array(src, CORRIDOR_KEYS["rmse_vis"])

    if d_vals.size != r_vals.size:
        n = min(d_vals.size, r_vals.size)
        d_vals = d_vals[:n]
        r_vals = r_vals[:n]
    if d_vis.size != r_vis.size:
        n = min(d_vis.size, r_vis.size)
        d_vis = d_vis[:n]
        r_vis = r_vis[:n]

    out = dict(src)
    out.setdefault("profile_d_status", src.get("profile_d_status", CORRIDOR_LIVE_STATUS))
    out["profile_d_values_nm"] = d_vals
    out["profile_d_rmse_values"] = r_vals
    out.setdefault("corridor_d_plot", d_vals)
    out.setdefault("corridor_rmse_plot", r_vals)
    out.setdefault("corridor_d_vis", d_vis if d_vis.size else d_vals)
    out.setdefault("corridor_rmse_vis", r_vis if r_vis.size else r_vals)
    return out
