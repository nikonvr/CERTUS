#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import time
import logging
from contextlib import contextmanager
from pathlib import Path

import numpy as np

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
import spline_profile_corridors as _spc

from spline_profile_corridors import ProfileCorridorConfig, compute_profiled_corridors_by_d


def _lam(lo: float = 400.0, hi: float = 800.0, n: int = 28) -> np.ndarray:
    return np.linspace(lo, hi, int(n), dtype=np.float64)


def _cfg_base(lam: np.ndarray, *, n_seg: int = 5) -> SplineOptConfig:
    return SplineOptConfig(
        lam_nm=np.asarray(lam, dtype=np.float64),
        t_exp=0.6 * np.ones_like(lam, dtype=np.float64),
        r_exp=None,
        n_sub=np.full_like(lam, 1.52, dtype=np.float64),
        data_type=DataType.TRANSMISSION,
        n_seg=int(n_seg),
        d_lo=500.0,
        d_hi=4000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Bench",
        t_is_ratio=False,
        corridor_profile_d_enabled=True,
        polish_maxfun=300,
        corridor_profile_d_polish_maxfun=300,
        corridor_profile_d_parallel_walks=False,
    )


def _base_result(lam: np.ndarray) -> dict:
    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))
    k = int(sk.size)
    return {
        "sigma_knots": sk,
        "d_nm": 2000.0,
        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),
        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),
        "rmse": 0.01,
        "spectral_rmse_segments": 0.01,
    }


def _pfast_alpha() -> ProfileCorridorConfig:
    return ProfileCorridorConfig(
        enabled=True,
        mode="alpha",
        rmse_alpha=1.6,
        step_nm=18.0,
        max_span_nm=72.0,
        max_steps_each_side=4,
        refine_boundary=False,
        n_starts=2,
        rng_seed=123,
    )


def _pfast_lr() -> ProfileCorridorConfig:
    return ProfileCorridorConfig(
        enabled=True,
        mode="lr",
        step_nm=18.0,
        max_span_nm=72.0,
        max_steps_each_side=4,
        refine_boundary=False,
        n_starts=2,
        lr_conf_level=0.95,
        rng_seed=123,
    )


def _run_one(cfg: SplineOptConfig, base: dict, pconf: ProfileCorridorConfig, n_repeat: int = 5) -> tuple[float, float]:
    vals = []
    for _ in range(int(n_repeat)):
        t0 = time.perf_counter()
        out = compute_profiled_corridors_by_d(cfg, dict(base), pconf=pconf, profile_polish_maxfun=300)
        dt = time.perf_counter() - t0
        vals.append(dt)
        if out:
            _ = out.get("profile_d_interval_nm")
    arr = np.asarray(vals, dtype=np.float64)
    return float(np.mean(arr)), float(np.min(arr))


@contextmanager
def _corridor_cache_mode(use_cache: bool):
    """A/B cache switch for corridor refit hotpath.

    When ``use_cache`` is False, cache-related kwargs are forcibly cleared before
    calling the real ``_fit_nodes_at_fixed_d`` implementation.
    """
    if use_cache:
        yield
        return

    original = _spc._fit_nodes_at_fixed_d

    def _fit_nodes_uncached(*args, **kwargs):
        kwargs["masked_grid_cache"] = None
        kwargs["cfg_effective"] = None
        kwargs["obj_stage_cache"] = None
        kwargs["bds_cache"] = None
        return original(*args, **kwargs)

    _spc._fit_nodes_at_fixed_d = _fit_nodes_uncached
    try:
        yield
    finally:
        _spc._fit_nodes_at_fixed_d = original


def _run_mode(
    cfg: SplineOptConfig,
    base: dict,
    *,
    use_cache: bool,
    n_repeat: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    with _corridor_cache_mode(use_cache):
        # Warmup
        _run_one(cfg, base, _pfast_alpha(), n_repeat=1)
        _run_one(cfg, base, _pfast_lr(), n_repeat=1)
        alpha = _run_one(cfg, base, _pfast_alpha(), n_repeat=n_repeat)
        lr = _run_one(cfg, base, _pfast_lr(), n_repeat=n_repeat)
    return alpha, lr


def main() -> None:
    logging.getLogger("CERTUS").setLevel(logging.WARNING)

    lam = _lam(n=28)
    cfg = _cfg_base(lam, n_seg=5)
    base = _base_result(lam)

    n_repeat = 5
    (alpha_cache_mean, alpha_cache_min), (lr_cache_mean, lr_cache_min) = _run_mode(
        cfg, base, use_cache=True, n_repeat=n_repeat
    )
    (alpha_no_mean, alpha_no_min), (lr_no_mean, lr_no_min) = _run_mode(
        cfg, base, use_cache=False, n_repeat=n_repeat
    )

    sp_alpha = alpha_no_mean / max(alpha_cache_mean, 1e-12)
    sp_lr = lr_no_mean / max(lr_cache_mean, 1e-12)

    print("=== corridor end-to-end bench ===")
    print("scenario: lam=28, n_seg=5, n_starts=2, max_span=72nm, maxfun=300, repeats=5")
    print(f"alpha cached:   mean={alpha_cache_mean:.4f}s min={alpha_cache_min:.4f}s")
    print(f"alpha uncached: mean={alpha_no_mean:.4f}s min={alpha_no_min:.4f}s")
    print(f"alpha speedup (cache on): x{sp_alpha:.2f}")
    print(f"lr    cached:   mean={lr_cache_mean:.4f}s min={lr_cache_min:.4f}s")
    print(f"lr    uncached: mean={lr_no_mean:.4f}s min={lr_no_min:.4f}s")
    print(f"lr    speedup (cache on): x{sp_lr:.2f}")


if __name__ == "__main__":
    main()
