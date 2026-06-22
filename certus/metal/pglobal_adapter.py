"""METAL adapter for the native PGlobal optimizer."""

from __future__ import annotations

import dataclasses
import logging
import os
import time
from typing import Any, Callable

import numpy as np
from scipy.optimize import OptimizeResult, minimize

from certus.core._certus_physics_impl import PGlobalConfig, PGlobalOptimizer
from certus.metal.certus_metal_common import build_metal_progress_event

logger = logging.getLogger(__name__)


def _safe_rmse(value: float) -> float:
    return float(np.sqrt(max(float(value), 0.0)))



def _head(vec: Any, max_items: int = 50) -> list[float]:
    try:
        arr = np.asarray(vec, dtype=np.float64)
    except Exception:
        return []
    if arr.size == 0:
        return []
    return np.round(arr[: min(max_items, arr.size)], 6).tolist()


def run_pglobal_optimization(
    objective_fn: Callable[[np.ndarray], float],
    bounds: np.ndarray,
    *,
    x0: np.ndarray | None = None,
    max_iter: int = 50,
    max_feval: int = 5000,
    workers: int = 1,
    stop_event: Any | None = None,
    callback: Callable[[dict[str, Any]], None] | None = None,
    config: PGlobalConfig | None = None,
    ultra_wide: bool = False,
    progress_logger: Callable[[str], None] | None = None,
    skip_polish: bool = False,
) -> OptimizeResult:
    """Run CERTUS-native PGlobal and return an OptimizeResult-compatible object."""

    bounds_arr = np.asarray(bounds, dtype=np.float64)
    dim = int(bounds_arr.shape[0])
    ultra_wide = bool(ultra_wide or os.getenv("CERTUS_METAL_ULTRA_WIDE", "0").strip().lower() in {"1", "true", "yes", "on"})
    # METAL is highly multi-modal. A nominal 5k budget is too small for an 8D
    # spline/thickness fit and was stopping after the first useful callback.
    # Keep a configurable internal floor while still allowing users to lower it
    # through CERTUS_METAL_PGLOBAL_MIN_FEVAL_FACTOR=1.
    user_budget = max(1, int(max_feval))
    if ultra_wide:
        base_samples = max(12000, 1500 * dim)
    else:
        base_samples = max(2400, 320 * dim)
    min_feval_factor = float(os.getenv("CERTUS_METAL_PGLOBAL_MIN_FEVAL_FACTOR", "8" if ultra_wide else "6") or 6)
    budget = int(max(user_budget, base_samples * max(1.0, min_feval_factor)))
    cfg = config or PGlobalConfig.for_dimension(dim=dim, base_samples=base_samples, max_feval=budget)
    overrides: dict[str, Any] = {}
    if hasattr(cfg, "max_feval"):
        overrides["max_feval"] = budget
    if hasattr(cfg, "max_time"):
        overrides["max_time"] = max(float(getattr(cfg, "max_time", 300.0)), 900.0)
    if hasattr(cfg, "workers"):
        overrides["workers"] = int(workers)
    if hasattr(cfg, "local_search_budget"):
        if config is None:
            default_local_budget = 30000 if ultra_wide else 15000
            overrides["local_search_budget"] = min(max(int(getattr(cfg, "local_search_budget", 0)), default_local_budget), max(default_local_budget, budget))
    if hasattr(cfg, "reduction_ratio"):
        overrides["reduction_ratio"] = 0.5 if ultra_wide else min(float(getattr(cfg, "reduction_ratio", 0.3)), 0.35)
    if overrides:
        cfg = dataclasses.replace(cfg, **overrides)

    x0_arr = None if x0 is None else np.asarray(x0, dtype=np.float64)
    mesh_size = 0
    if x0_arr is None or x0_arr.size == 0:
        lows = bounds_arr[:, 0]
        highs = bounds_arr[:, 1]
        midpoint = (lows + highs) / 2.0
        mesh_size = max(16, min(96, int(os.getenv("CERTUS_METAL_INITIAL_MESH_SIZE", "48") or 48)))
        rng = np.random.default_rng(int(os.getenv("CERTUS_METAL_INITIAL_MESH_SEED", "12345") or 12345))
        samples = [midpoint]
        for _ in range(mesh_size - 1):
            # Quasi-structured random mesh around the whole domain with a bias
            # toward the midpoint so the first iterate is already physically sane.
            u = rng.random(dim)
            candidate = lows + u * (highs - lows)
            if rng.random() < 0.5:
                candidate = 0.65 * candidate + 0.35 * midpoint
            samples.append(candidate)
        best_sample = midpoint
        best_sample_fun = float("inf")
        for candidate in samples:
            try:
                val = float(objective_fn(np.asarray(candidate, dtype=np.float64)))
                if np.isfinite(val) and val < best_sample_fun:
                    best_sample_fun = val
                    best_sample = np.asarray(candidate, dtype=np.float64)
            except Exception:
                continue
        x0_arr = best_sample.copy()
        local_radius = np.asarray(highs - lows, dtype=np.float64)
        x0_arr = np.clip(x0_arr, lows, highs)
        if mesh_size >= 32:
            local_rng = np.random.default_rng(int(os.getenv("CERTUS_METAL_LOCAL_MESH_SEED", "54321") or 54321))
            local_samples = [x0_arr]
            shrink = 0.18 if ultra_wide else 0.12
            for _ in range(max(24, mesh_size // 2)):
                cand = x0_arr + local_rng.normal(0.0, shrink, size=dim) * local_radius
                local_samples.append(np.clip(cand, lows, highs))
            local_best = x0_arr.copy()
            local_best_fun = best_sample_fun
            for candidate in local_samples:
                try:
                    val = float(objective_fn(np.asarray(candidate, dtype=np.float64)))
                    if np.isfinite(val) and val < local_best_fun:
                        local_best_fun = val
                        local_best = np.asarray(candidate, dtype=np.float64)
                except Exception:
                    continue
            x0_arr = local_best.copy()

    ultra_log_every = max(1, int(os.getenv("CERTUS_METAL_ULTRA_WIDE_LOG_EVERY", "1") or 1))
    ultra_summary_prefix = "[ULTRA-WIDE]" if ultra_wide else "[PGLOBAL]"
    if progress_logger is not None:
        try:
            seed_eval = float(objective_fn(np.asarray(x0_arr, dtype=np.float64)))
            progress_logger(
                f"{ultra_summary_prefix} x0_probe | rmse={_safe_rmse(seed_eval):.6e} | x0_head={_head(x0_arr)} | x0_dim={x0_arr.size}"
            )
        except Exception as exc:
            progress_logger(
                f"{ultra_summary_prefix} x0_probe_failed | reason={exc} | x0_head={_head(x0_arr)} | x0_dim={x0_arr.size}"
            )
            failure_hist = locals().get("failure_hist", {})
            failure_hist["x0_probe_failed"] = failure_hist.get("x0_probe_failed", 0) + 1
            _write = getattr(objective_fn, "__self__", None)

    optimizer = PGlobalOptimizer(
        objective_fn,
        bounds_arr,
        config=cfg,
        stop_event=stop_event,
        x0=x0_arr,
    )
    optimizer._n_workers = int(workers)

    t0 = time.monotonic()
    best_seen_x = x0_arr.copy() if x0_arr is not None else np.asarray([])
    best_seen_y = float("inf")
    prev_best_seen_y = float("inf")
    prev_logged_best = float("inf")
    failure_hist: dict[str, int] = {}
    if progress_logger is not None:
        progress_logger(
            f"{ultra_summary_prefix} start | dim={dim} | base_samples={base_samples} | requested_max_feval={max_feval} | effective_max_feval={budget} | max_iter={max_iter} | workers={workers} | x0={'provided' if x0 is not None else 'mesh_best'} | mesh_size={mesh_size if x0 is None or np.asarray(x0).size == 0 else 0} | bounds_min={np.round(bounds_arr[:,0], 6).tolist()} | bounds_max={np.round(bounds_arr[:,1], 6).tolist()} | cfg={cfg}"
        )

    def _cb(sample: Any) -> None:
        nonlocal best_seen_x, best_seen_y, prev_best_seen_y, prev_logged_best
        sample_x = np.asarray(getattr(sample, "x", []), dtype=np.float64)
        sample_y = float(getattr(sample, "y", float("inf")))
        if not np.isfinite(sample_y):
            failure_hist["non_finite_sample"] = failure_hist.get("non_finite_sample", 0) + 1
            if progress_logger is not None:
                progress_logger(f"{ultra_summary_prefix} non_finite_sample | iter=N/A | count={failure_hist['non_finite_sample']} | x_head={_head(sample_x)}")
        improved = False
        if sample_x.size > 0 and sample_y < best_seen_y:
            prev_best_seen_y = best_seen_y
            best_seen_x = sample_x.copy()
            best_seen_y = sample_y
            improved = True
        iteration = int(getattr(sample, "generation", 0) or getattr(sample, "iteration", 0) or 0)
        evals = int(getattr(optimizer, "n_evals", 0))
        elapsed = float(time.monotonic() - t0)
        best_cost_now = float(sample_y if np.isfinite(sample_y) else best_seen_y)
        curr_rmse = _safe_rmse(best_cost_now)
        best_rmse = _safe_rmse(best_seen_y)
        x_head = np.round(sample_x[:min(50, sample_x.size)], 6).tolist() if sample_x.size else []
        best_head = np.round(best_seen_x[:min(50, best_seen_x.size)], 6).tolist() if best_seen_x.size else []
        should_log = progress_logger is not None and (
            iteration <= 5
            or iteration % ultra_log_every == 0
            or improved
            or (np.isfinite(best_cost_now) and best_cost_now < prev_logged_best * 0.999)
        )
        if should_log:
            n_clusters = len(getattr(optimizer.clusterer, "get_clusters", lambda: [])()) if hasattr(optimizer, "clusterer") else 0
            cfg_samples = getattr(optimizer.config, "n_samples_per_iter", "N/A")
            cfg_reduct = getattr(optimizer.config, "reduction_ratio", "N/A")
            cfg_local_b = getattr(optimizer.config, "local_search_budget", "N/A")
            cfg_max_c = getattr(optimizer.config, "max_active_clusters", "N/A")
            
            progress_logger(
                f"{ultra_summary_prefix} iter={iteration:04d}/{max_iter} evals={evals} "
                f"RMSE={best_rmse:.6e} (curr_RMSE={curr_rmse:.6e}) "
                f"improved={'yes' if improved else 'no'} elapsed={elapsed:.1f}s | "
                f"clusters={n_clusters} | cfg: samples={cfg_samples}, reduct={cfg_reduct}, local_budget={cfg_local_b}, max_clusters={cfg_max_c} | "
                f"best_head={best_head}"
            )
        if callback is None:
            return
            
        pct_iter = iteration / max(1, max_iter)
        pct_evals = evals / max(1, budget)
        real_progress_pct = min(100, int(100 * max(pct_iter, pct_evals)))
        
        payload = build_metal_progress_event(
            phase="global_opt",
            progress_pct=real_progress_pct,
            message=f"PGLOBAL | Gen {iteration}/{max_iter} | {'improved' if improved else 'running'}",
            iteration=iteration,
            max_iteration=int(max_iter),
            evaluation_count=evals,
            best_cost=float(best_seen_y if np.isfinite(best_seen_y) else best_cost_now),
            elapsed_s=elapsed,
            mode="global",
        )
        callback({
            "phase": payload.phase,
            "progress_pct": payload.progress_pct,
            "message": payload.message,
            "iteration": payload.iteration,
            "max_iteration": payload.max_iteration,
            "evaluation_count": payload.evaluation_count,
            "progress_pct": min(100, int(100 * max(iteration / max(1, max_iter), evals / max(1, budget)))),
            "current_rmse": curr_rmse,
            "best_rmse": best_rmse,
            "mse": curr_rmse ** 2,
            "best_cost": best_rmse ** 2,
            "evaluation_count": evals,
            "elapsed_s": elapsed,
            "best_x": best_seen_x.tolist() if best_seen_x.size else None,
            "params": best_seen_x.tolist() if best_seen_x.size else None,
            "iteration": iteration,
            "max_iteration": max_iter,
            "mode": "global",
            "improved": improved,
            "x_head": x_head,
            "best_head": best_head,
        })

    best = optimizer.optimize(max_iter=int(max_iter), callback=_cb)

    final_x = None
    final_fun = float("inf")
    if best is not None and getattr(best, "x", None) is not None and np.asarray(best.x).size > 0:
        final_x = np.asarray(best.x, dtype=np.float64)
        final_fun = float(best.y)
    else:
        final_x = best_seen_x.copy()
        final_fun = float(best_seen_y)

    if final_x is None or final_x.size == 0:
        return OptimizeResult(
            x=np.asarray(x0_arr, dtype=np.float64),
            fun=float("inf"),
            success=False,
            message="No feasible solution found",
            nit=int(getattr(optimizer, "n_evals", 0)),
            nfev=int(getattr(optimizer, "n_evals", 0)),
        )

    if not skip_polish:
        if progress_logger is not None:
            progress_logger(f"{ultra_summary_prefix} pre-polish | nfev={int(getattr(optimizer, 'n_evals', 0))} | x_dim={final_x.size} | x_head={np.round(final_x[:min(6, final_x.size)], 6).tolist()}")

        # Multi-start local polish to recover sharp minima on tough single-layer cases.
        polish_starts = [final_x.copy()]
        rng_seed = os.getenv("CERTUS_METAL_POLISH_SEED", "12345")
        rng = np.random.default_rng(int(rng_seed) if str(rng_seed).strip().isdigit() else 12345)
        n_extra_polish = int(os.getenv("CERTUS_METAL_POLISH_RESTARTS", "6" if ultra_wide else "4") or 4)
        span = bounds_arr[:, 1] - bounds_arr[:, 0]
        for scale in np.linspace(0.015, 0.08 if ultra_wide else 0.05, max(1, n_extra_polish)):
            candidate = final_x + rng.normal(0.0, scale, size=final_x.size) * span
            polish_starts.append(np.clip(candidate, bounds_arr[:, 0], bounds_arr[:, 1]))

        for polish_idx, start_x in enumerate(polish_starts):
            try:
                polish = minimize(
                    objective_fn,
                    start_x,
                    method="L-BFGS-B",
                    bounds=[tuple(b) for b in bounds_arr],
                    options={"maxiter": max(300, min(3000, budget // 8)), "ftol": 1e-12, "gtol": 1e-8},
                )
                polished_fun = float(getattr(polish, "fun", np.inf))
                if np.isfinite(polished_fun) and polished_fun <= final_fun:
                    final_x = np.asarray(polish.x, dtype=np.float64)
                    final_fun = polished_fun
                    if progress_logger is not None:
                        progress_logger(
                            f"{ultra_summary_prefix} polish accepted | restart={polish_idx}/{len(polish_starts)-1} | best_rmse={_safe_rmse(final_fun):.6e} | x_head={np.round(final_x[:min(6, final_x.size)], 6).tolist()}"
                        )
                elif progress_logger is not None:
                    progress_logger(
                        f"{ultra_summary_prefix} polish rejected | restart={polish_idx}/{len(polish_starts)-1} | polished_rmse={_safe_rmse(polished_fun):.6e} | keep_rmse={_safe_rmse(final_fun):.6e}"
                    )
            except Exception as exc:
                if progress_logger is not None:
                    progress_logger(f"{ultra_summary_prefix} polish failed | restart={polish_idx}/{len(polish_starts)-1} | reason={exc}")

    severe_polish_enabled = False if skip_polish else (str(os.getenv("CERTUS_METAL_SEVERE_POLISH", "1")).strip().lower() not in {"0", "false", "no", "off"})
    if severe_polish_enabled and final_x.size > 0:
        severe_restarts = int(os.getenv("CERTUS_METAL_SEVERE_POLISH_RESTARTS", "6" if ultra_wide else "4") or 4)
        severe_span_scale = float(os.getenv("CERTUS_METAL_SEVERE_POLISH_SPAN_SCALE", "0.02" if ultra_wide else "0.012") or 0.012)
        severe_maxiter = int(os.getenv("CERTUS_METAL_SEVERE_POLISH_MAXITER", str(max(800, min(5000, budget // 4)))) or max(800, min(5000, budget // 4)))
        severe_seed = os.getenv("CERTUS_METAL_SEVERE_POLISH_SEED", rng_seed)
        severe_rng = np.random.default_rng(int(severe_seed) if str(severe_seed).strip().isdigit() else 24680)
        severe_span = np.asarray(bounds_arr[:, 1] - bounds_arr[:, 0], dtype=np.float64)
        if progress_logger is not None:
            progress_logger(
                f"{ultra_summary_prefix} severe_polish start | restarts={severe_restarts} | span_scale={severe_span_scale} | maxiter={severe_maxiter} | seed={severe_seed}"
            )
        for severe_idx in range(severe_restarts):
            if severe_idx == 0:
                start_x = final_x.copy()
            else:
                perturb = severe_rng.normal(0.0, severe_span_scale, size=final_x.size) * severe_span
                start_x = np.clip(final_x + perturb, bounds_arr[:, 0], bounds_arr[:, 1])
            try:
                severe = minimize(
                    objective_fn,
                    start_x,
                    method="L-BFGS-B",
                    bounds=[tuple(b) for b in bounds_arr],
                    options={"maxiter": severe_maxiter, "ftol": 1e-14, "gtol": 1e-10},
                )
                severe_fun = float(getattr(severe, "fun", np.inf))
                if np.isfinite(severe_fun) and severe_fun <= final_fun:
                    final_x = np.asarray(severe.x, dtype=np.float64)
                    final_fun = severe_fun
                    if progress_logger is not None:
                        progress_logger(
                            f"{ultra_summary_prefix} severe_polish accepted | restart={severe_idx}/{severe_restarts-1} | best_rmse={_safe_rmse(final_fun):.6e} | x_head={np.round(final_x[:min(6, final_x.size)], 6).tolist()}"
                        )
                elif progress_logger is not None:
                    progress_logger(
                        f"{ultra_summary_prefix} severe_polish rejected | restart={severe_idx}/{severe_restarts-1} | polished_rmse={_safe_rmse(severe_fun):.6e} | keep_rmse={_safe_rmse(final_fun):.6e}"
                    )
            except Exception as exc:
                if progress_logger is not None:
                    progress_logger(
                        f"{ultra_summary_prefix} severe_polish failed | restart={severe_idx}/{severe_restarts-1} | reason={exc}"
                    )
        if progress_logger is not None:
            progress_logger(f"{ultra_summary_prefix} severe_polish end | best_rmse={_safe_rmse(final_fun):.6e}")

    if progress_logger is not None:
        progress_logger(f"{ultra_summary_prefix} final | best_rmse={_safe_rmse(final_fun):.6e} | nfev={int(getattr(optimizer, 'n_evals', 0))} | success=True")
        progress_logger(
            f"{ultra_summary_prefix} final_vector | x_head={np.round(final_x[:min(8, final_x.size)], 6).tolist()} | x_dim={final_x.size}"
        )

    return OptimizeResult(
        x=final_x,
        fun=final_fun,
        success=True,
        message="Optimization completed",
        nit=int(getattr(best, "iteration", max_iter) if best is not None else max_iter),
        nfev=int(getattr(optimizer, "n_evals", 0)),
    )
