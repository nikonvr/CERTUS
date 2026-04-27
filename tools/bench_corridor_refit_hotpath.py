#!/usr/bin/env python3

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
from spline_objective import SplinePWLObjective, build_spline_objective_masked_grid
from spline_profile_corridors import _bounds_for_nodes_only, _fit_nodes_at_fixed_d


def make_cfg(n_pts: int = 40) -> SplineOptConfig:
    lam = np.linspace(400.0, 800.0, int(n_pts), dtype=np.float64)
    t_exp = np.full_like(lam, 0.62)
    n_sub = np.full_like(lam, 1.52)
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=5,
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
        lnk_spline_reg_weight=1.0,
    )


def make_seeds(k: int, n_seeds: int, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(int(seed))
    n_nodes = np.full(k, 1.65, dtype=np.float64)
    L_nodes = np.linspace(np.log(5e-4), np.log(2e-3), k, dtype=np.float64)
    x0 = np.concatenate((n_nodes, L_nodes))
    out = [x0.copy()]
    for _ in range(max(0, int(n_seeds) - 1)):
        j = x0.copy()
        j[:k] += rng.normal(0.0, 0.02, size=k)
        j[k:] += rng.normal(0.0, 0.03, size=k)
        out.append(j)
    return out


def run_batch(
    cfg: SplineOptConfig,
    sk: np.ndarray,
    bounds: np.ndarray,
    d_nm: float,
    seeds: list[np.ndarray],
    *,
    cached: bool,
    maxfun: int,
) -> float:
    t0 = time.perf_counter()

    cfg_fit = None
    obj_stage = None
    mg = None
    if cached:
        cfg_fit = cfg.replace(spline_pure_spectral_objective=True)
        obj_stage = SplinePWLObjective(cfg_fit, sk)
        mg = build_spline_objective_masked_grid(cfg_fit)

    for x0 in seeds:
        _fit_nodes_at_fixed_d(
            cfg,
            sk,
            float(d_nm),
            x0,
            bounds,
            maxfun=int(maxfun),
            pure_spectral=True,
            use_lr=True,
            sig_t=0.01,
            sig_r=0.01,
            masked_grid_cache=mg,
            cfg_effective=cfg_fit,
            obj_stage_cache=obj_stage,
        )

    return time.perf_counter() - t0


def bench() -> None:
    cfg = make_cfg(n_pts=40)
    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    sk = canonical_spline_sigma_knots(float(np.min(lam)), float(np.max(lam)))
    k = int(sk.size)
    bounds, _ = _bounds_for_nodes_only(cfg, k)
    seeds = make_seeds(k, n_seeds=8, seed=123)
    d_nm = 2000.0

    # Warmup
    run_batch(cfg, sk, bounds, d_nm, seeds[:2], cached=False, maxfun=120)
    run_batch(cfg, sk, bounds, d_nm, seeds[:2], cached=True, maxfun=120)

    n_repeat = 6
    unc = []
    cac = []
    for _ in range(n_repeat):
        unc.append(run_batch(cfg, sk, bounds, d_nm, seeds, cached=False, maxfun=160))
        cac.append(run_batch(cfg, sk, bounds, d_nm, seeds, cached=True, maxfun=160))

    t_unc = float(np.mean(unc))
    t_cac = float(np.mean(cac))
    speedup = t_unc / max(t_cac, 1e-12)

    print("=== corridor refit hotpath bench ===")
    print(f"seeds={len(seeds)}  n_repeat={n_repeat}  maxfun=160")
    print(f"uncached mean: {t_unc:.4f}s")
    print(f"cached   mean: {t_cac:.4f}s")
    print(f"speedup: x{speedup:.2f}")


if __name__ == "__main__":
    bench()
