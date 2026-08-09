from __future__ import annotations
import numpy as np
from numba import njit, prange
from typing import Callable, TYPE_CHECKING
import time
import os
import math
import threading
from scipy.optimize import minimize
from threading import RLock
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict
from certus.core.certus_core import PI
from threading import Event

if TYPE_CHECKING:
    from certus_physics.structures import Sample
    from certus.core._certus_physics_impl import PGlobalConfig


# [MONOLITHIC BLOCK] PGLOBAL ALGORITHM


# DO NOT SPLIT - Tightly coupled with optimization kernels


# =========================================================================================


# OPTIMIZATION ALGORITHMS (PGLOBAL)


# =============================================================================


def get_lbfgsb_params(dim: int) -> dict:
    """L-BFGS-B tolerances - dynamically adjustable via env var."""
    tol = 1e-12
    env_tol = os.environ.get("CERTUS_LBFGSB_TOL")
    if env_tol:
        try:
            tol = float(env_tol)
        except ValueError:
            pass

    return {"ftol": tol, "gtol": 1e-10, "maxcor": min(50, max(20, dim + 5))}


class LBFGSBSearcher:
    """Local Search via L-BFGS-B (direct Fortran setulb for 2× less overhead)."""

    # Try to import the Fortran kernel once at class definition time.
    # Falls back to scipy.optimize.minimize if unavailable.
    try:
        from scipy.optimize._lbfgsb import setulb as _setulb
    except ImportError:
        _setulb = None

    def __init__(
        self,
        func: Callable,
        bounds: np.ndarray,
        config: PGlobalConfig | None = None,
        gradient_func: Callable | None = None,
    ):

        self.func = func

        # Pre-compute bounds list once (avoid O(dim) list creation per search)
        self._bounds_list = list(zip(bounds[:, 0], bounds[:, 1]))

        self.dim = len(bounds)

        self.config = config

        self.gradient_func = gradient_func

        # Pre-compute L-BFGS-B parameters (dimension-dependent, constant per searcher)
        self._lbfgsb_params = get_lbfgsb_params(self.dim)

        # Pre-compute Fortran-format bounds arrays (used by direct setulb path)
        self._low_bnd = np.ascontiguousarray(bounds[:, 0], dtype=np.float64)
        self._upper_bnd = np.ascontiguousarray(bounds[:, 1], dtype=np.float64)
        self._nbd = np.full(self.dim, 2, dtype=np.int32)  # 2 = both bounds

        # Pre-build combined fun+grad closure (probed once in __init__,
        # not per search call). Saves ~2 TMM evals per local search.
        self._objective_fn = func
        self._jac_arg = None

        if gradient_func is not None:
            _func = func
            _grad = gradient_func

            def _fun_and_grad(x):
                f = _func(x)
                g = _grad(x)
                if isinstance(g, tuple):
                    g = g[1]
                if g is None:
                    return f
                return f, g

            self._fun_and_grad = _fun_and_grad
            # Probe deferred to first search() call where x0 is available
            self._grad_probed = False
        else:
            self._fun_and_grad = None
            self._grad_probed = True  # nothing to probe

    def _probe_gradient(self, x0: np.ndarray):
        """One-time probe: does gradient_func work for the given x0?"""
        if self._grad_probed:
            return
        self._grad_probed = True
        if self._fun_and_grad is None:
            return
        try:
            _probe = self._fun_and_grad(x0)
            if isinstance(_probe, tuple) and len(_probe) == 2:
                self._objective_fn = self._fun_and_grad
                self._jac_arg = True
        except ValueError, RuntimeError, TypeError:
            pass

    def _search_direct(
        self,
        x0: np.ndarray,
        max_feval: int,
        fun_and_grad: Callable,
    ) -> tuple[np.ndarray, float, int]:
        """Direct Fortran setulb call — bypasses scipy.optimize.minimize wrapper.

        Eliminates ScalarFunction, _prepare_bounds, and OptimizeResult overhead
        (~35us per function evaluation, measured 2× speedup vs minimize).
        """
        n = self.dim
        m = self._lbfgsb_params["maxcor"]
        ftol = self._lbfgsb_params["ftol"]
        gtol = self._lbfgsb_params["gtol"]

        x = np.array(x0, dtype=np.float64)
        f = np.float64(0.0)
        g = np.zeros(n, dtype=np.float64)

        factr = ftol / np.finfo(np.float64).eps

        wa = np.zeros(2 * m * n + 5 * n + 11 * m * m + 8 * m, dtype=np.float64)
        iwa = np.zeros(3 * n, dtype=np.int32)
        task = np.zeros(2, dtype=np.int32)
        ln_task = np.zeros(2, dtype=np.int32)
        lsave = np.zeros(4, dtype=np.int32)
        isave = np.zeros(44, dtype=np.int32)
        dsave = np.zeros(29, dtype=np.float64)

        nfev = 0
        maxiter = max(100, max_feval // (n + 1))
        maxls = 20

        _setulb = self._setulb
        while True:
            _setulb(
                m,
                x,
                self._low_bnd,
                self._upper_bnd,
                self._nbd,
                f,
                g,
                factr,
                gtol,
                wa,
                iwa,
                task,
                lsave,
                isave,
                dsave,
                maxls,
                ln_task,
            )
            if task[0] == 3:  # FG request — evaluate objective + gradient
                result = fun_and_grad(x)
                if isinstance(result, tuple):
                    fv, gv = result
                    f = np.float64(fv)
                    g[:] = np.asarray(gv, dtype=np.float64)
                else:
                    f = np.float64(result)
                    # FD gradient will be handled by setulb internally
                nfev += 1
                if nfev >= max_feval:
                    task[0] = 5
                    task[1] = 502
            elif task[0] == 1:  # NEW_X — new iteration completed
                if isave[29] >= maxiter:
                    task[0] = 5
                    task[1] = 504
            else:
                break

        return x.copy(), float(f), nfev

    def search(self, x0: np.ndarray, max_feval: int = 1000, callback: Callable = None) -> tuple[np.ndarray, float, int]:

        try:
            # Probe gradient on first call (needs x0 to test)
            self._probe_gradient(x0)

            # Fast path: direct Fortran setulb (bypasses scipy wrapper overhead).
            # Used when: gradient is available (jac=True) and no callback needed
            # (PGlobal never uses callback on local searches).
            if self._setulb is not None and self._jac_arg is True and callback is None:
                return self._search_direct(x0, max_feval, self._objective_fn)

            # Fallback: scipy.optimize.minimize (handles FD gradient, callbacks, etc.)
            options = {
                "ftol": self._lbfgsb_params["ftol"],
                "gtol": self._lbfgsb_params["gtol"],
                "maxcor": self._lbfgsb_params["maxcor"],
                "maxfun": max_feval,
                "maxiter": max(100, max_feval // (self.dim + 1)),
            }

            if "eps" in self._lbfgsb_params:
                options["eps"] = self._lbfgsb_params["eps"]

            min_callback = None

            if callback:

                def min_callback(xk):

                    callback(xk)

            res = minimize(
                self._objective_fn,
                x0,
                method="L-BFGS-B",
                bounds=self._bounds_list,
                options=options,
                jac=self._jac_arg,
                callback=min_callback,
            )

            return res.x, float(res.fun), int(res.nfev)

        except ValueError, RuntimeError, np.linalg.LinAlgError:
            return x0.copy(), float(self.func(x0)), 1


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_critical_distance(n: int, dim: int, alpha: float) -> float:

    # Exact MLSL / Csendes Critical Distance:

    # r_k = pi^(-1/2) * [ Gamma(1 + d/2) * m(S) * sigma * log(n)/n ]^(1/d)

    # Since we normalize the space to the unit hypercube [0, 1]^d, the measure m(S) = 1.

    # 1. Use log-gamma to prevent float64 overflow in high dimensions (dim > 170)

    log_gamma = math.lgamma(1.0 + dim / 2.0)

    # log_val = log_gamma + log(alpha) + log(log(n)) - log(n)

    # Taking the (1/d) power becomes division by dim in log space

    if n <= 1:
        n = 2  # prevent log(log(1)) error

    log_val = log_gamma + math.log(alpha) + math.log(max(1e-12, math.log(float(n)))) - math.log(float(n))

    rk = (1.0 / math.sqrt(PI)) * math.exp(log_val / dim)

    # 2. Heuristic Csendes cap: max normalized distance in unit hypercube is sqrt(dim).

    # We should not cluster across more than half the hypercube diagonal.

    max_rk = math.sqrt(float(dim)) * 0.5

    if rk > max_rk:
        rk = max_rk

    return float(rk)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def fast_clustering_kernel(
    x_batch: np.ndarray,
    y_batch: np.ndarray,
    seeds_x: np.ndarray,
    seeds_y: np.ndarray,
    dc: float,
    bounds_min: np.ndarray,
    bounds_ptp: np.ndarray,
) -> np.ndarray:

    # Note: x_batch MUST be sorted by y_batch ascending before calling!

    n_batch = len(x_batch)

    n_seeds = len(seeds_x)

    cluster_ids = np.full(n_batch, -1, dtype=np.int32)

    dc_sq = dc * dc

    for i in prange(n_batch):
        # Strict MLSL condition: x_i launches local search UNLESS there is a

        # point x_j (seed or intra-batch point) such that f(x_j) < f(x_i) AND

        # normalized_distance(x_i, x_j) < d_c.

        min_dist_sq = 1e30

        best_seed = -1

        # 1. Compare against PREVIOUS iterations' local minima / seeds

        for j in range(n_seeds):
            if seeds_y[j] < y_batch[i]:  # Gradient condition (f_j < f_i)
                dist_sq = 0.0

                for k in range(x_batch.shape[1]):
                    d = (x_batch[i, k] - seeds_x[j, k]) / bounds_ptp[k]

                    dist_sq += d * d

                if dist_sq < dc_sq and dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq

                    best_seed = j

        # 2. Compare against BETTER points in the SAME batch (indexes j < i)

        # Since batch is sorted ascending by y, any j < i automatically satisfies f(x_j) <= f(x_i)

        # This prevents redundant local searches from the same batch mapping to the same basin!

        for j in range(i):
            dist_sq = 0.0

            for k in range(x_batch.shape[1]):
                d = (x_batch[i, k] - x_batch[j, k]) / bounds_ptp[k]

                dist_sq += d * d

            if dist_sq < dc_sq and dist_sq < min_dist_sq:
                min_dist_sq = dist_sq

                best_seed = -2  # -2 means "clustered within same batch"

        cluster_ids[i] = best_seed

    return cluster_ids


class SingleLinkageClusterer:
    """Strict MLSL / Single-linkage clustering for PGLOBAL"""

    _INITIAL_BUF_CAP = 256

    def __init__(self, bounds: np.ndarray, config: PGlobalConfig):

        self.bounds = bounds

        self.dim = len(bounds)

        self.bounds_min = np.ascontiguousarray(bounds[:, 0])

        self.bounds_ptp = np.ascontiguousarray(bounds[:, 1] - bounds[:, 0])

        # Prevent division by zero if bounds are identical

        self.bounds_ptp = np.maximum(self.bounds_ptp, 1e-12)

        self.config = config

        self.clusters: list[dict] = []

        # Pre-allocated doubling buffers for seeds (amortized O(1) append)
        self._seeds_x_buf = np.empty((self._INITIAL_BUF_CAP, self.dim), dtype=np.float64)
        self._seeds_y_buf = np.empty(self._INITIAL_BUF_CAP, dtype=np.float64)
        self._seeds_count = 0

        # Pre-allocated doubling buffers for unique basins
        self._basins_x_buf = np.empty((64, self.dim), dtype=np.float64)
        self._basins_y_buf = np.empty(64, dtype=np.float64)
        self._basins_count = 0

        self.total_local_searches_started = 0

        self._lock = RLock()

    # ── Property views into pre-allocated buffers (zero-copy) ──────────

    @property
    def x_seeds_cache(self) -> np.ndarray:
        return self._seeds_x_buf[: self._seeds_count]

    @property
    def y_seeds_cache(self) -> np.ndarray:
        return self._seeds_y_buf[: self._seeds_count]

    @property
    def unique_basins_x(self) -> np.ndarray:
        return self._basins_x_buf[: self._basins_count]

    @property
    def unique_basins_y(self) -> np.ndarray:
        return self._basins_y_buf[: self._basins_count]

    def process_batch(
        self, x_batch: np.ndarray, y_batch: np.ndarray, n_total_samples: int
    ) -> tuple[np.ndarray, np.ndarray]:

        if len(x_batch) == 0:
            return np.zeros((0, self.dim)), np.zeros(0)

        # Standard MLSL: points must be processed sequentially in ascending order of objective!

        # This allows multiple local starts in the same batch mapping to the same basin to be filtered out perfectly.

        sort_idx = np.argsort(y_batch)

        s_x_batch = x_batch[sort_idx]

        s_y_batch = y_batch[sort_idx]

        with self._lock:
            dc = compute_critical_distance(max(n_total_samples, 2), self.dim, self.config.alpha)

            # cluster_ids returns -1 if point should launch local search

            # >=0 if it clustered to a previous seed, -2 if it clustered to a better point in THIS batch

            cluster_ids = fast_clustering_kernel(
                s_x_batch, s_y_batch, self.x_seeds_cache, self.y_seeds_cache, dc, self.bounds_min, self.bounds_ptp
            )

            mask_unclustered = cluster_ids == -1

            # The unclustered points become seeds for future batches

            unclustered_x = s_x_batch[mask_unclustered]

            unclustered_y = s_y_batch[mask_unclustered]

            if len(unclustered_x) > 0:
                self._append_to_seeds(unclustered_x, unclustered_y)

            return unclustered_x, unclustered_y

    def add_cluster_result(self, x_local: np.ndarray, y_local: float):
        """

        Registers a completed L-BFGS-B local search.

        Identifies if it converged to a NEW unique basin or a KNOWN one.

        """

        with self._lock:
            self.total_local_searches_started += 1

            # 1. Add as a seed point so that future batches map to this minimum

            self._append_to_seeds(np.atleast_2d(x_local), np.array([y_local]))

            self.clusters.append({"x": x_local.copy(), "y": y_local})

            # 2. Add to unique basins if it's new (vectorized distance check)

            is_new_basin = True

            if self._basins_count > 0:
                by = self._basins_y_buf[: self._basins_count]
                y_tol = 1e-6 * max(abs(y_local), 1e-8)
                y_close = np.abs(by - y_local) < y_tol
                if np.any(y_close):
                    bx = self._basins_x_buf[: self._basins_count][y_close]
                    dx = (x_local - bx) / self.bounds_ptp
                    if np.any(np.sum(dx * dx, axis=1) < 1e-4):
                        is_new_basin = False

            if is_new_basin:
                self._append_to_basins(np.atleast_1d(x_local), float(y_local))

    def get_bayesian_estimate(self) -> tuple[float, float]:
        """

        Returns (Expected_Total_Minima, Expected_Undiscovered_Minima)

        using the precise Boender, Rinnooy Kan (1987) Bayesian stopping rule.

        Expectation E(W|w, N) = w(N-1) / (N-w-2)  for N > w + 2

        """

        with self._lock:
            w = float(len(self.unique_basins_y))

            N = float(self.total_local_searches_started)

            if N <= w + 2 or w == 0:
                return float("inf"), float("inf")

            expected_total = (w * (N - 1)) / (N - w - 2)

            expected_undiscovered = expected_total - w

            return expected_total, expected_undiscovered

    def _append_to_seeds(self, x_array: np.ndarray, y_array: np.ndarray):
        """Amortized O(1) append into pre-allocated doubling buffer."""
        x_new = np.atleast_2d(x_array)
        y_new = np.asarray(y_array, dtype=np.float64).ravel()
        n_new = x_new.shape[0]
        needed = self._seeds_count + n_new
        if needed > self._seeds_x_buf.shape[0]:
            new_cap = max(needed, self._seeds_x_buf.shape[0] * 2)
            new_xb = np.empty((new_cap, self.dim), dtype=np.float64)
            new_yb = np.empty(new_cap, dtype=np.float64)
            new_xb[: self._seeds_count] = self._seeds_x_buf[: self._seeds_count]
            new_yb[: self._seeds_count] = self._seeds_y_buf[: self._seeds_count]
            self._seeds_x_buf = new_xb
            self._seeds_y_buf = new_yb
        self._seeds_x_buf[self._seeds_count : self._seeds_count + n_new] = x_new
        self._seeds_y_buf[self._seeds_count : self._seeds_count + n_new] = y_new
        self._seeds_count += n_new

    def _append_to_basins(self, x_local: np.ndarray, y_local: float):
        """Amortized O(1) append into pre-allocated doubling buffer."""
        needed = self._basins_count + 1
        if needed > self._basins_x_buf.shape[0]:
            new_cap = max(needed, self._basins_x_buf.shape[0] * 2)
            new_xb = np.empty((new_cap, self.dim), dtype=np.float64)
            new_yb = np.empty(new_cap, dtype=np.float64)
            new_xb[: self._basins_count] = self._basins_x_buf[: self._basins_count]
            new_yb[: self._basins_count] = self._basins_y_buf[: self._basins_count]
            self._basins_x_buf = new_xb
            self._basins_y_buf = new_yb
        self._basins_x_buf[self._basins_count] = x_local
        self._basins_y_buf[self._basins_count] = y_local
        self._basins_count += 1

    def get_best_minimum(self):

        with self._lock:
            if self._basins_count == 0:
                return None

            idx = int(np.argmin(self._basins_y_buf[: self._basins_count]))

            return self._basins_x_buf[idx].copy(), float(self._basins_y_buf[idx])

    def clear(self):

        with self._lock:
            self.clusters.clear()

            self._seeds_count = 0
            self._seeds_x_buf = np.empty((self._INITIAL_BUF_CAP, self.dim), dtype=np.float64)
            self._seeds_y_buf = np.empty(self._INITIAL_BUF_CAP, dtype=np.float64)

            self._basins_count = 0
            self._basins_x_buf = np.empty((64, self.dim), dtype=np.float64)
            self._basins_y_buf = np.empty(64, dtype=np.float64)

            self.total_local_searches_started = 0


class PGlobalOptimizer:
    """

    PGLOBAL Global Optimizer - Multi-start stochastic global optimization.

    Algorithm (per iteration):

        1. Adaptive Sampling   - Latin-hypercube-like uniform draws, ×2 on first iter

        2. Batch Evaluation     - ThreadPoolExecutor (Numba nogil -> true parallelism)

        3. Reduction            - Keep top-% by objective value (argpartition)

        4. Single-Linkage Clustering - Filter points near known basins

        5. Parallel Local Searches   - L-BFGS-B from each unclustered candidate

        6. Stagnation Detection      - Track relative improvement

    Thread-safety:

        - Steps 2 and 5 run in ThreadPoolExecutor (nogil objective).

        - Global state (n_evals, _best_ever, clusterer) is updated

          synchronously *between* parallel sections, never concurrently.

    """

    # ── Constants ──────────────────────────────────────────────────────

    _MIN_LOCAL_BUDGET: int = 50  # Don't launch L-BFGS-B below this

    _SEQUENTIAL_THRESHOLD: int = 8  # Batch size below which threads are overhead

    _HIGH_DIM_THRESHOLD: int = 15  # Dimension above which we tighten reduction

    def __init__(
        self,
        objective: Callable,
        bounds: np.ndarray,
        config: PGlobalConfig | None = None,
        stop_event: Event | None = None,
        log_clues: list[int] | None = None,
        x0: np.ndarray | None = None,
        gradient_func: Callable | None = None,
    ):

        self.objective = objective

        self.bounds = np.asarray(bounds, dtype=np.float64)

        self.dim = len(bounds)

        if config is None:
            from certus.core._certus_physics_impl import PGlobalConfig
            config = PGlobalConfig()
        self.config = config

        self.clusterer = SingleLinkageClusterer(self.bounds, self.config)

        self._stop_event = stop_event

        self.n_evals = 0

        seed = getattr(self.config, "random_seed", None)
        self.rng = np.random.default_rng(None if seed is None else int(seed))

        # Phase 2: Quasi-Random Sequence (Sobol)

        try:
            from scipy.stats import qmc

            # Scramble prevents identical grids across restarts while keeping low-discrepancy

            self.qmc_engine = qmc.Sobol(d=self.dim, scramble=True, seed=self.rng)

        except ImportError:
            self.qmc_engine = None

        self.x0 = x0

        self.log_clues = log_clues or []

        self._best_ever: Sample | None = None

        self.gradient_func = gradient_func

        # Cached searcher — created once, reused across all local searches
        self._searcher: LBFGSBSearcher | None = None

        # Worker count - computed once, reused across iterations

        self._n_workers = self._resolve_worker_count()

        # Persistent thread pool - created lazily on first parallel call

        self._pool = None

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_worker_count() -> int:
        """Determine thread-pool size (safe for frozen executables)."""

        import sys

        if getattr(sys, "frozen", False):
            try:
                from certus.core.certus_core import get_safe_worker_count

                return get_safe_worker_count()

            except ImportError:
                return 1

        return max(1, (os.cpu_count() or 4) - 2)

    def _is_stopped(self) -> bool:

        return bool(self._stop_event and self._stop_event.is_set())

    def _generate_samples(self, n: int) -> np.ndarray:
        """Draw *n* samples within bounds using Sobol Quasi-Random Sequences."""

        if self.qmc_engine is not None:
            # Generate low-discrepancy samples in [0, 1)^d
            # Scipy QMC Sobol expects n to be a power of 2 for perfect balance properties.
            # To avoid the warning and keep balance, we generate the next power of 2 and slice.
            import math

            n_pow2 = 2 ** math.ceil(math.log2(n)) if n > 0 else 0
            unit_samples = self.qmc_engine.random(n_pow2)[:n]
            # Scale to physical bounds manually to avoid extra scipy calls overhead if needed,
            # though scipy.stats.qmc.scale is also fine. Manual scaling is fast and numba-friendly if extracted.
            bounds_min = self.bounds[:, 0]
            bounds_ptp = self.bounds[:, 1] - bounds_min
            samples = unit_samples * bounds_ptp + bounds_min
        else:
            # Fallback to pseudo-random uniform
            samples = self.rng.uniform(self.bounds[:, 0], self.bounds[:, 1], (n, self.dim))

        if getattr(self, "x0", None) is not None and len(samples) > 0:
            samples[0] = self.x0
            self.x0 = None

        return samples

    # ── Step 2: Batch Evaluation ──────────────────────────────────────

    def _evaluate_batch(self, X: np.ndarray) -> np.ndarray:
        """

        Evaluate objective on *X* (n_points × dim).

        Prefers the objective's own ``evaluate_batch`` (BLAS-batched interpolation),

        then ThreadPoolExecutor, then sequential loop.

        """

        n = len(X)

        # Fast path: batched evaluation (shared interpolation matrix → dgemm)
        _eb = getattr(self.objective, "evaluate_batch", None)
        if _eb is not None:
            try:
                return np.asarray(_eb(X), dtype=np.float64)
            except ValueError, TypeError, RuntimeError:
                pass  # Fallback to per-point

        Y = np.empty(n, dtype=np.float64)

        if n <= self._SEQUENTIAL_THRESHOLD or self._n_workers <= 1:
            for i in range(n):
                Y[i] = self.objective(X[i])

        else:
            pool = self._get_pool()

            for i, val in enumerate(pool.map(self.objective, X)):
                Y[i] = val

        return Y

    # ── Step 5: Local Search Dispatch ─────────────────────────────────

    def _build_dispatch_tasks(
        self, cand_x: np.ndarray, cand_y: np.ndarray, iteration: int
    ) -> list[tuple[np.ndarray, int]]:
        """

        Select unclustered candidates and pair each with a L-BFGS-B budget.

        Returns:

            List of (x_start, budget) tuples ready for parallel dispatch.

        """

        idx_sorted = np.argsort(cand_y)

        # Dispatch proportional to config.max_active_clusters, enabling deep search of multiple basins

        base_dispatch = max(20, self.config.max_active_clusters)

        decay = 0.97**iteration

        n_dispatch = min(len(cand_y), max(5, int(base_dispatch * decay)))

        tasks: list[tuple[np.ndarray, int]] = []

        for k in range(n_dispatch):
            if self._is_stopped():
                break

            x_k = cand_x[idx_sorted[k]]

            # Top candidates (k=0) get 130% budget; bottom get 70%
            budget_factor = 0.7 + 0.6 * (1.0 - k / max(n_dispatch, 1))

            budget = int(self.config.local_search_budget * budget_factor)

            if budget >= self._MIN_LOCAL_BUDGET:
                tasks.append((x_k, budget))

        return tasks

    def _get_searcher(self) -> LBFGSBSearcher:
        """Return cached LBFGSBSearcher (bounds list + lbfgsb params computed once)."""
        if self._searcher is None:
            self._searcher = LBFGSBSearcher(self.objective, self.bounds, self.config, self.gradient_func)
        return self._searcher

    def _run_local_search(self, task: tuple[np.ndarray, int]) -> tuple[np.ndarray, float, int] | None:
        """Execute a single L-BFGS-B local search (designed to run in a thread)."""

        if self._is_stopped():
            return None

        x_start, budget = task

        try:
            x_opt, f_opt, n_ev = self._get_searcher().search(x_start, budget)

            return (x_opt, f_opt, n_ev)

        except ValueError, RuntimeError:
            return None

    def _dispatch_and_collect(
        self,
        tasks: list[tuple[np.ndarray, int]],
        iteration: int,
        best_ever_y: float,
        stagnation_counter: int,
        callback: Callable | None,
    ) -> tuple[float, int]:
        """

        Run all local-search tasks in parallel, process results as they

        complete (as_completed) for better load balancing and earlier

        best-ever updates.

        Returns:

            Updated (best_ever_y, stagnation_counter).

        """

        from concurrent.futures import as_completed

        pool = self._get_pool()

        futures = {pool.submit(self._run_local_search, t): t for t in tasks}

        for future in as_completed(futures):
            if self._is_stopped():
                break

            try:
                res = future.result()
            except ValueError, RuntimeError, TypeError, ArithmeticError:
                continue

            if res is None:
                continue

            x_opt, f_opt, local_evals = res

            self.n_evals += local_evals

            self.clusterer.add_cluster_result(x_opt, f_opt)

            if self._best_ever is None or f_opt < self._best_ever.y:
                from certus_physics.structures import Sample

                self._best_ever = Sample(x_opt.copy(), f_opt, iteration)

                best_ever_y = f_opt

                stagnation_counter = 0

                if callback:
                    callback(self._best_ever)

        return best_ever_y, stagnation_counter

    # ── Main Loop ─────────────────────────────────────────────────────

    @staticmethod
    def _inner_numba_threads(n_workers: int) -> int:
        """Nombre de threads numba a laisser a CHAQUE thread du pool."""
        try:
            import numba

            total = int(numba.config.NUMBA_NUM_THREADS)
        except (ImportError, AttributeError, TypeError, ValueError):
            return 1
        return max(1, total // max(1, int(n_workers)))

    @staticmethod
    def _init_pool_thread(n_inner: int) -> None:
        """Restricts INTERNAL numba parallelism for this pool thread.

        `numba.set_num_threads` is thread-local (verified at runtime):
        setting the value here only affects threads in this pool, not the rest
        of the process.
        """
        try:
            import numba

            numba.set_num_threads(n_inner)
        except (ImportError, ValueError):
            pass

    def _get_pool(self):
        """Return persistent thread pool, creating it lazily on first use."""

        if self._pool is None:
            from concurrent.futures import ThreadPoolExecutor

            # Sur-souscription : le pool lance _n_workers threads, et CHACUN
            # appelle un noyau njit(parallel=True) qui ouvrait a son tour
            #NUMBA_NUM_THREADS threads. On 16 cores with ~10 workers, this
            # faisait ~160 threads pour 16 coeurs, et le temps partait en
            #contention rather than calculation.
            #
            # Mesure sur example/example_design (cout par evaluation de
            # cost_numba_fast, ~850 000 appels par run — le temps total d'un run
            #DESIGN varies from 43 to 85 s and does not allow anything to be concluded):
            #     NUMBA_NUM_THREADS=16 : 953,30 us/appel
            #     NUMBA_NUM_THREADS= 2 : 884,69 us/appel
            #     NUMBA_NUM_THREADS= 1 : 749,50 us/appel
            #
            # C'est le meme constat qui avait motive le numba.set_num_threads(2)
            #from _test_strategy_robustness_task, but applies to the pool.
            self._pool = ThreadPoolExecutor(
                max_workers=self._n_workers,
                initializer=self._init_pool_thread,
                initargs=(self._inner_numba_threads(self._n_workers),),
            )

        return self._pool

    def _shutdown_pool(self):
        """Shutdown the persistent thread pool if it exists."""

        if self._pool is not None:
            self._pool.shutdown(wait=False)

            self._pool = None

    def optimize(self, max_iter: int = 50, callback: Callable | None = None) -> "Sample | None":
        """

        Run the PGLOBAL optimization loop.

        Args:

            max_iter: Maximum number of sampling iterations.

            callback: Optional ``callback(Sample)`` for progress reporting.

        Returns:

            Best :class:`Sample` found, or *None* if no feasible point exists.

        """

        import time

        best_ever_y = float("inf")

        stagnation_counter = 0

        last_best_y = float("inf")

        n_samples_iter = self.config.n_samples_per_iter

        start_time = time.time()

        for iteration in range(max_iter):
            # ── Termination checks ────────────────────────────────

            if self._is_stopped():
                break

            if self.n_evals >= self.config.max_feval:
                break

            if time.time() - start_time > self.config.max_time:
                break

            # ── 1. Adaptive Sampling ──────────────────────────────

            adaptive_factor = 1.0 + 0.5 * (1.0 - iteration / max_iter)

            current_n = int(n_samples_iter * adaptive_factor)

            if iteration == 0:
                current_n *= 2  # Bootstrap: double first batch

            # ── 2. Generation & Evaluation ────────────────────────

            X_batch = self._generate_samples(current_n)

            Y_batch = self._evaluate_batch(X_batch)

            self.n_evals += len(X_batch)

            # ── 3. Reduction ──────────────────────────────────────

            ratio = self.config.reduction_ratio

            if self.dim > self._HIGH_DIM_THRESHOLD:
                ratio = min(0.25, ratio * 1.5)

            n_keep = max(int(current_n * ratio), 10)

            if n_keep < len(Y_batch):
                idx_best = np.argpartition(Y_batch, n_keep)[:n_keep]

            else:
                idx_best = np.arange(len(Y_batch))

            X_reduced = X_batch[idx_best]

            Y_reduced = Y_batch[idx_best]

            # ── 4. Single-Linkage Clustering ──────────────────────

            cand_x, cand_y = self.clusterer.process_batch(X_reduced, Y_reduced, self.n_evals)

            # Progress callback (best-in-batch, pre-local-search)

            best_idx = np.argmin(Y_batch)

            f_best = Y_batch[best_idx]

            if f_best < best_ever_y and callback and iteration % 2 == 0:
                from certus_physics.structures import Sample

                callback(Sample(X_batch[best_idx], f_best, iteration))

            # ── 5. Parallel Local Searches ────────────────────────

            if len(cand_y) > 0 and not self._is_stopped() and self.n_evals < self.config.max_feval:
                tasks = self._build_dispatch_tasks(cand_x, cand_y, iteration)

                if tasks:
                    best_ever_y, stagnation_counter = self._dispatch_and_collect(
                        tasks, iteration, best_ever_y, stagnation_counter, callback
                    )

            # ── 6. Bayesian Stopping Rule ─────────────────────────

            _exp_tot, expected_undiscovered = self.clusterer.get_bayesian_estimate()

            if expected_undiscovered <= 0.5:
                # We expect less than 0.5 unobserved local minima left! We can safely terminate global search.

                # In standard Bayesian statistics this equates to high confidence that all minima have been found.

                break

            # ── 7. Stagnation Detection ───────────────────────────

            if self._best_ever:
                curr_best = self._best_ever.y

                if abs(curr_best - last_best_y) < 1e-8 * max(abs(curr_best), 1e-10):
                    stagnation_counter += 1

                else:
                    stagnation_counter = 0

                last_best_y = curr_best

                # Heuristic fallback if Bayesian stopping doesn't trigger

                if stagnation_counter >= 8:
                    break

        self._shutdown_pool()

        return self._best_ever
