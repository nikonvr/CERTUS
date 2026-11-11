"""CERTUS-INDEX-SPLINE corridors - the three jobs a corridor worker thread runs: the refit at fixed d over a regular grid, the healing of its gaps, the deep polish from the minimum of the curve (functions moved, text unchanged, out of certus_index_spline_common.py, which goes on exposing them). They compute and know nothing of the window."""

from __future__ import annotations

from threading import Event
from typing import Any

import numpy as np

from certus.spline.certus_index_spline_core import SplineOptConfig
from certus.spline.spline_profile_corridors import compute_regular_grid_rmse_profile, quick_pwlnk_refit_result_dict


def _worker_corridor_rmse_regular_grid(
    cfg: SplineOptConfig,
    base_snapshot: dict,
    d_grid_nm: np.ndarray,
    stop_event: Event,
    breakpoint_lookback_points: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Worker: refit n,L at fixed d on a grid (same masked spectral objective as the corridor)."""

    progress_cb = kwargs.get("progress_cb")

    live_cb = kwargs.get("live_cb")

    def _stop() -> bool:

        try:
            return stop_event is not None and stop_event.is_set()

        except (AttributeError, TypeError):
            return False

    visit_anchor = kwargs.get("visit_anchor_nm")

    visit_anchor_kw: float | None = None

    if visit_anchor is not None and np.isfinite(float(visit_anchor)):
        visit_anchor_kw = float(visit_anchor)

    return compute_regular_grid_rmse_profile(
        cfg,
        base_snapshot,
        d_grid_nm,
        profile_polish_maxfun=None,
        breakpoint_lookback_points=int(max(2, breakpoint_lookback_points)),
        visit_anchor_nm=visit_anchor_kw,
        progress_cb=progress_cb,
        stop_check=_stop,
        live_cb=live_cb,
    )


def _worker_corridor_rmse_healer(
    cfg: SplineOptConfig,
    tasks: list[tuple[float, dict]],
    stop_event: Event,
    **kwargs: Any,
) -> list[dict]:
    """Worker designed to heal gaps: each (d, seed) is optimized independently."""
    results = []
    progress_cb = kwargs.get("progress_cb")
    n = len(tasks)
    for i, (d_target, seed) in enumerate(tasks):
        if stop_event is not None and stop_event.is_set():
            break

        # Prepare a specific config/seed for this point
        point_seed = dict(seed)
        point_seed["d_nm"] = float(d_target)

        # Standard polish at fixed d
        res = quick_pwlnk_refit_result_dict(cfg, point_seed, maxfun=1200)
        if isinstance(res, dict):
            res["profile_d_val_nm"] = float(d_target)
            results.append(res)

        if progress_cb:
            progress_cb(float(i + 1) / n, f"Heal {i + 1}/{n} @ d={d_target:.2f}")

    return results


def _worker_curve_minimum_deep_refit(
    cfg: SplineOptConfig,
    seed_dict: dict,
    stop_event: Event,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """After RMSE(d): L-BFGS-B polish on (d, nodes) from the discrete grid minimum (local thickness freedom)."""
    if stop_event is not None and stop_event.is_set():
        return None
    maxfun = int(kwargs.get("deep_maxfun", 10000))
    seed_clean = {k: v for k, v in dict(seed_dict).items() if not str(k).startswith("profile_d")}
    out = quick_pwlnk_refit_result_dict(cfg, seed_clean, maxfun=maxfun)
    if not isinstance(out, dict):
        return None
    for _k in list(out.keys()):
        if str(_k).startswith("profile_d"):
            del out[_k]
    rm = float(out.get("rmse", float("nan")))
    if np.isfinite(rm):
        out["mse"] = float(rm * rm)
    out["gui_curve_minimum_deep_refit"] = True
    return out
