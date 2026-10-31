"""Memetic global search for DESIGN: a population of polished designs recombined by blocks of layers.

Every member of the population is a local minimum (L-BFGS-B with the analytic gradient). A child
copies one parent and takes a contiguous block of layers [lo, hi) from another, is jittered, then
polished; it replaces the worst member when it beats it and is not a copy of a member. The layer
count and the materials are those of the stack, so any cut point gives a valid child.

On the 50/50 splitter 400-1200 nm (example/example_design/JSON-design-example.json) this search
reached an RMSE of 1.7e-4 with 32 layers, where random restarts reached 4.8e-4 with 34 layers and
the PGLOBAL workflow 1.8e-3 to 4.2e-3 (reports/DESIGN_bs5050_2026-10-22/journal.md).

OptimWorker uses it when ``memetic_children`` > 0 in its configuration (the window's default since
2026-10-23). With a pool of threads it polishes several designs at once: the polish is one Numba
kernel call after another, and the kernels release the GIL.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass
from threading import Event, Lock
from types import SimpleNamespace

import numpy as np
from scipy.optimize import minimize


@dataclass
class MemeticResult:
    """Best design found: thicknesses of the variable layers, its cost, and the cost calls made."""

    x: np.ndarray
    y: float
    evaluations: int
    generation: int = 0


def run_memetic(
    cost_and_grad: Callable[[np.ndarray], tuple[float, np.ndarray]],
    bounds: np.ndarray,
    *,
    x0: np.ndarray | None,
    population: int,
    children: int,
    seed: int | None = None,
    jitter: float = 0.02,
    screen_maxiter: int = 0,
    local_maxiter: int = 3000,
    stop_event: Event | None = None,
    on_improve: Callable[[SimpleNamespace], None] | None = None,
    init_bounds: np.ndarray | None = None,
    merge_shift_every: int = 0,
    pool: Executor | None = None,
    batch: int = 1,
) -> MemeticResult:
    """Run the memetic search inside ``bounds`` (one (low, high) row per variable layer).

    ``x0``, when given, joins the initial population (polished); the others are drawn uniformly
    inside ``init_bounds`` (default: the bounds), then polished inside the bounds. Drawing inside
    wide bounds starts from designs far thicker than useful ones. ``screen_maxiter`` > 0 polishes each child briefly first and gives the full
    polish only to a child that already beats the worst member. ``on_improve`` receives an object
    with ``x``, ``y`` and ``generation`` each time the best cost improves.

    ``pool`` with ``batch`` > 1 polishes ``batch`` designs at a time on the pool's threads, so
    ``cost_and_grad`` must be thread-safe: first the random starts, then the children, drawn
    ``batch`` at a time from the same population and judged in the order they were drawn. The
    starts are the sequential ones; the children differ from the sequential search, which
    ``pool=None`` (default) keeps unchanged.
    """
    lo_b = np.asarray(bounds, dtype=np.float64)[:, 0]
    hi_b = np.asarray(bounds, dtype=np.float64)[:, 1]
    dim = len(lo_b)
    rng = np.random.default_rng(seed)
    init = np.asarray(init_bounds if init_bounds is not None else bounds, dtype=np.float64)
    init_lo, init_hi = np.maximum(init[:, 0], lo_b), np.minimum(init[:, 1], hi_b)
    calls = {"n": 0}
    calls_lock = Lock()
    parallel = pool is not None and batch > 1

    def f(x: np.ndarray) -> tuple[float, np.ndarray]:
        with calls_lock:
            calls["n"] += 1
        c, g = cost_and_grad(np.ascontiguousarray(x, dtype=np.float64))
        return float(c), np.asarray(g, dtype=np.float64)

    def polish(x: np.ndarray, maxiter: int) -> tuple[np.ndarray, float]:
        res = minimize(f, np.clip(x, lo_b, hi_b), jac=True, method="L-BFGS-B", bounds=list(zip(lo_b, hi_b, strict=True)),
                       options={"maxiter": maxiter, "ftol": 1e-15, "gtol": 1e-12})
        return np.asarray(res.x, dtype=np.float64), float(res.fun)

    def stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    best = {"y": np.inf, "x": None, "gen": 0}

    def record(x: np.ndarray, y: float, gen: int) -> None:
        if y < best["y"]:
            best.update(y=y, x=x.copy(), gen=gen)
            if on_improve is not None:
                on_improve(SimpleNamespace(x=x.copy(), y=y, generation=gen))

    pop: list[tuple[np.ndarray, float]] = []
    if x0 is not None and len(x0) == dim:
        pop.append(polish(np.asarray(x0, dtype=np.float64), local_maxiter))
        record(*pop[-1], 0)
    while len(pop) < max(2, population) and not stopped():
        if parallel:
            starts = [rng.uniform(init_lo, init_hi) for _ in range(min(batch, max(2, population) - len(pop)))]
            for x, y in pool.map(polish, starts, [local_maxiter] * len(starts)):
                pop.append((x, y))
                record(x, y, 0)
        else:
            pop.append(polish(rng.uniform(init_lo, init_hi), local_maxiter))
            record(*pop[-1], 0)

    def worst_index() -> int:
        return int(np.argmax([m[1] for m in pop]))

    def draw_child(gen: int) -> np.ndarray:
        i, j = rng.choice(len(pop), 2, replace=False)
        child = pop[i][0].copy()
        if merge_shift_every > 0 and dim >= 4 and gen % merge_shift_every == 0:
            child = _prune_merge_shift_child(child, lo_b, hi_b, init_lo, init_hi, rng)
        else:
            cut_lo, cut_hi = sorted(rng.choice(np.arange(1, dim), 2, replace=False)) if dim > 2 else (1, 2)
            child[cut_lo:cut_hi] = pop[j][0][cut_lo:cut_hi]
        child *= 1.0 + jitter * rng.standard_normal(dim)
        return child

    def polish_child(child: np.ndarray, worst_cost: float) -> tuple[np.ndarray, float]:
        if screen_maxiter:
            x, y = polish(child, screen_maxiter)
            if y < worst_cost:
                x, y = polish(x, local_maxiter)
            return x, y
        return polish(child, local_maxiter)

    def judge(x: np.ndarray, y: float, gen: int) -> None:
        worst = worst_index()
        duplicate = any(abs(y - m[1]) <= 1e-12 * max(abs(y), 1e-30) for m in pop)
        if y < pop[worst][1] and not duplicate:
            pop[worst] = (x, y)
        record(x, y, gen)

    gen = 0
    while gen < children and not (stopped() or len(pop) < 2 or dim < 2):
        size = min(batch, children - gen) if parallel else 1
        kids = [draw_child(gen + 1 + k) for k in range(size)]
        worst_cost = pop[worst_index()][1]
        polished = pool.map(polish_child, kids, [worst_cost] * size) if parallel else [polish_child(kids[0], worst_cost)]
        for k, (x, y) in enumerate(polished):
            judge(x, y, gen + 1 + k)
        gen += size

    if best["x"] is None:
        return MemeticResult(x=np.asarray(x0 if x0 is not None else lo_b, dtype=np.float64), y=np.inf,
                             evaluations=calls["n"])
    return MemeticResult(x=best["x"], y=float(best["y"]), evaluations=calls["n"], generation=int(best["gen"]))


def _prune_merge_shift_child(
    parent: np.ndarray,
    lo_b: np.ndarray,
    hi_b: np.ndarray,
    init_lo: np.ndarray,
    init_hi: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Delete one of the thinnest interior layers, merge its identical-material neighbours, and shift by two indices."""
    dim = len(parent)
    interior = np.arange(1, dim - 1)
    span = np.maximum(init_hi[interior] - lo_b[interior], 1e-12)
    rank = np.argsort((parent[interior] - lo_b[interior]) / span)
    k = int(interior[rank[rng.integers(0, min(3, len(interior)))]])
    merged = min(float(hi_b[k - 1]), float(parent[k - 1] + parent[k + 1]))
    child = parent.copy()
    if rng.random() < 0.5:
        child[2 : k + 1] = parent[0 : k - 1]
        child[k + 1] = merged
        child[0] = rng.uniform(lo_b[0], lo_b[0] + 0.25 * (init_hi[0] - init_lo[0]))
        child[1] = rng.uniform(init_lo[1], min(hi_b[1], init_lo[1] + 2.2 * (init_hi[1] - init_lo[1])))
    else:
        child[k - 1] = merged
        child[k : dim - 2] = parent[k + 2 : dim]
        child[dim - 2 : dim] = rng.uniform(init_lo[dim - 2 : dim], init_hi[dim - 2 : dim])
    return child


def widen_upper_bounds(bounds: np.ndarray, qwot_nm: np.ndarray, layer_qwot_max: float) -> np.ndarray:
    """Raise each upper bound to at least ``layer_qwot_max`` quarter waves (``qwot_nm`` = one QWOT in nm)."""
    out = np.array(bounds, dtype=np.float64, copy=True)
    out[:, 1] = np.maximum(out[:, 1], layer_qwot_max * np.asarray(qwot_nm, dtype=np.float64))
    return out
