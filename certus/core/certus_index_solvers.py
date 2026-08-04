from pathlib import Path
from certus.core.certus_core import create_module_environment
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import scipy
import scipy.optimize

_env = create_module_environment(__file__, 'CERTUS_INDEX_CORE')
script_dir = _env['script_dir']

from numba import njit, prange, set_num_threads

def _numba_set_threads_clamped(n: int) -> int:
    """Numba impose set_num_threads dans [1, 31] (sinon ValueError, ex. Python 3.14 / grosse machine)."""
    return max(1, min(31, int(n)))
import logging
import numpy as np
import pandas as pd
from enum import Enum, auto
from typing import Any

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    HC_EV_NM,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    OH_BAND_MAX,
    OH_BAND_MIN,
    PI,
    SMALL_EPSILON,
    T_SUB_MIN_R_NORM,
    T_SUB_MIN_T_NORM,
    SUBSTRATE_LIST,
    SUBSTRATES,
    SELLMEIER_COEFFS_BY_ID,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
    substrate_sellmeier_id,
    __version__,
    get_resource_path,
    get_safe_worker_count,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
)
from certus_physics import (
    PGlobalConfig,
    Sample,
    SingleLinkageClusterer,
    TLUParameters,
    _compute_index_cost_gradient_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_phase2_derivatives_kernel,
    _compute_ir_global_cost_gradient_kernel,
    calculate_single_interface_R,
    calculate_reflection_array,
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    calculate_transmission_single,
    clip_to_bounds,
    compute_mse_vectorized,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_n_frosted_glass_array,
    get_n_substrate_array_by_id,
    SplineBasisCache,
)
from certus.utils.certus_index_utils import (
    spectral_rmse_weights,
    sellmeier_2poles_eval_nj,
    sellmeier_2poles_eval,
    k_law_8p_eval,
    _deduce_knots_from_k8p,
    _ensure_strictly_increasing,
    _merge_closest_knot_pair,
    _sellmeier_residuals,
    fit_sellmeier_global,
    fit_k_global_8p,
    DataType,
    _detect_data_type_from_array,
    _detect_type_from_column_name,
    detect_data_type,
    analyze_loaded_data,
    _get_substrate_n_array_index,
    normalize_index_config,
    calculate_index_rmse,
)

# from .certus_index_config import *  # Unused
# from .certus_index_objectives import *  # Unused

class GradientSearcher:
    """L-BFGS-B local search using Analytic Gradient"""

    def __init__(
        self,
        func,
        bounds: np.ndarray,
        config: PGlobalConfig,
        stop_event: Event | None = None,
        monitor_callback=None,
    ) -> None:

        self.func = func

        self.bounds = bounds

        self.lb = bounds[:, 0]

        self.ub = bounds[:, 1]

        self.dim = len(bounds)

        self.config = config

        self.stop_event = stop_event

        self.monitor_callback = monitor_callback

    def search(self, x0: np.ndarray, max_feval: int = 1500) -> tuple:
        """Run L-BFGS-B from x0"""

        if self.stop_event and self.stop_event.is_set():
            return x0, float(self.func(x0)), 0

        # Ensure x0 is within bounds

        x0 = clip_to_bounds(x0.copy(), self.lb, self.ub)

        # Scipy L-BFGS-B wrapper

        # func should be TLUObjective object which has .gradient() method,

        # OR func is a wrapper. In PGlobalOptimizerINDEX init: self.objective = objective

        # which is the TLUObjective instance.

        # But wait, self.func passed here is self.objective.

        # Check if self.func has gradient method.

        obj_instance = self.func

        # Verify if obj_instance has gradient method, else fallback?

        # In CERTUS_INDEX logic, 'objective' passed to PGlobalOptimizerINDEX is TLUObjective instance.

        # It has __call__ and gradient(x).

        try:
            # Check if gradient exists, else use numerical approximation

            jac = getattr(obj_instance, "gradient", None)

            res = scipy.optimize.minimize(
                obj_instance,
                x0,
                method="L-BFGS-B",
                jac=jac,
                bounds=[(l, u) for l, u in zip(self.lb, self.ub)],
                options={
                    "ftol": 1e-9,
                    "gtol": 1e-9,
                    "maxfun": max_feval,
                    "maxiter": max_feval // 2,  # Heuristic
                },
                callback=self.monitor_callback,
            )

            return res.x, res.fun, res.nfev

        except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
            # Fallback if gradient fails (e.g. numerical singularity, ZeroDivisionError in TLU kernel).

            # Aligned with CERTUS_INDEX OLD.py: do not let the exception propagate -> Phase 1 PGLOBAL continues.

            logging.debug("event=index_gradient_opt status=fallback reason=%s", e)

            val = float(obj_instance(x0))

            return x0, val, 1


class PGlobalOptimizerINDEX:
    """PGLOBAL optimizer adapted for INDEX"""

    def __init__(
        self,
        objective,
        bounds: np.ndarray,
        n_workers: int = None,
        config: PGlobalConfig | None = None,
        log_clues: list | None = None,
        stop_event: Event | None = None,
    ) -> None:

        self.objective = objective

        self.bounds = np.asarray(bounds, dtype=np.float64)

        self.dim = len(bounds)

        self.lb = self.bounds[:, 0]

        self.ub = self.bounds[:, 1]

        self.config = config or PGlobalConfig()

        # Safe worker count (frozen: 1)

        self.n_workers = n_workers if n_workers is not None else get_safe_worker_count()

        self.clusterer = SingleLinkageClusterer(self.bounds, self.config)

        self._all_samples: list = []

        self.n_evals = 0

        self._n_total_samples = 0

        self.log_clues = log_clues or []

        self.stop_event = stop_event

        self._executor: ThreadPoolExecutor | None = None

        self.sampling_method = "sobol"
        self.random_seed = getattr(self.config, "random_seed", None)
        self._rng = np.random.default_rng(None if self.random_seed is None else int(self.random_seed))

        try:
            from scipy.stats.qmc import Sobol

            self._qmc_engine = Sobol(
                d=self.dim,
                scramble=True,
                seed=None if self.random_seed is None else int(self.random_seed),
            )

        except ImportError:
            self._qmc_engine = None

            self.sampling_method = "uniform"

    def _unit_to_physical(self, unit: np.ndarray, n: int) -> np.ndarray:

        X = np.empty((n, self.dim), dtype=np.float32)

        for i in range(self.dim):
            if i in self.log_clues:
                log_lb = np.float32(np.log10(max(self.lb[i], 1e-9)))

                log_ub = np.float32(np.log10(self.ub[i]))

                X[:, i] = np.power(10, log_lb + unit[:, i].astype(np.float32) * (log_ub - log_lb))

            else:
                X[:, i] = np.float32(self.lb[i]) + unit[:, i].astype(np.float32) * np.float32(self.ub[i] - self.lb[i])

        return X

    def _sample_uniform(self, n: int) -> list:

        if self.stop_event and self.stop_event.is_set():
            return []

        method = getattr(self, "sampling_method", "uniform")

        X = None

        if method == "sobol" and self._qmc_engine is not None:
            try:
                import math

                n_pow2 = 2 ** math.ceil(math.log2(n)) if n > 0 else 0

                unit = self._qmc_engine.random(n_pow2)[:n]

                X = self._unit_to_physical(unit, n)

            except NUMERICAL_FAULT_EXCEPTIONS :
                method = "uniform"

        elif method == "halton":
            try:
                from scipy.stats.qmc import Halton

                # seed= comme pour Sobol plus haut : sans lui, random_seed etait
                # silencieusement ignore sur ce chemin et le run restait
                # irreproductible meme graine fixee.
                sampler = Halton(
                    d=self.dim,
                    scramble=True,
                    seed=None if self.random_seed is None else int(self.random_seed),
                )

                unit = sampler.random(n)

                X = self._unit_to_physical(unit, n)

            except ImportError:
                method = "uniform"

        elif method == "lhs":
            try:
                from scipy.stats.qmc import LatinHypercube

                # idem Halton : random_seed n'etait pas transmis.
                sampler = LatinHypercube(
                    d=self.dim,
                    seed=None if self.random_seed is None else int(self.random_seed),
                )

                unit = sampler.random(n)

                X = self._unit_to_physical(unit, n)

            except ImportError:
                method = "uniform"

        if method == "uniform" or X is None:
            unit = self._rng.uniform(0.0, 1.0, size=(n, self.dim))

            X = self._unit_to_physical(unit, n)

        samples = []

        # Parallel Execution if executor is available

        if self._executor:
            try:
                # Map objective over X in parallel

                # TLUObjective releases GIL in Numba, allowing true parallelism

                results = self._executor.map(self.objective, X)

                for i, y in enumerate(results):
                    if self.stop_event and self.stop_event.is_set():
                        break

                    y_val = float(y)

                    samples.append(Sample(x=X[i].copy(), y=y_val if np.isfinite(y_val) else np.inf))

            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.getLogger("CERTUS").error("[INDEX.PGLOBAL] sampling failed | mode=parallel | reason=%s", e)

                return []

        # Sequential Fallback

        else:
            for x in X:
                if self.stop_event and self.stop_event.is_set():
                    break

                y = float(self.objective(x))

                samples.append(Sample(x=x.copy(), y=y if np.isfinite(y) else np.inf))

        self.n_evals += len(samples)

        self._n_total_samples += len(samples)

        return samples

    def _should_stop_optimization(self, start_time: float, iteration: int) -> bool:
        """Return True when the main optimize loop should stop."""
        if self.stop_event and self.stop_event.is_set():
            return True
        if time.time() - start_time > self.config.max_time:
            return True
        if self.n_evals >= self.config.max_feval:
            return True
        return False

    def _make_monitor_callback(self, callback):
        """Wrap the live callback for sequential local search."""
        if not callback:
            return None

        def monitor(xk):
            return callback(Sample(xk, self.objective(xk)))

        return monitor

    def _local_search_budget(self) -> int:
        """Budget remaining for a local refinement step."""
        return min(self.config.local_search_budget, self.config.max_feval - self.n_evals)

    def _prepare_iteration_batches(self, n_samples: int):
        """Sample, sort and reduce the active set for one optimize iteration."""
        new_samples = self._sample_uniform(n_samples)
        if not new_samples:
            return None

        self._all_samples.extend(new_samples)
        self._all_samples.sort(key=lambda s: s.y)

        n_keep = max(int(len(self._all_samples) * self.config.reduction_ratio), self.n_workers * 2)
        active_samples = self._all_samples[:n_keep]
        x_batch = np.array([s.x for s in active_samples])
        y_batch = np.array([s.y for s in active_samples])
        cand_x, cand_y = self.clusterer.process_batch(x_batch, y_batch, self._n_total_samples)
        return n_keep, cand_x, cand_y

    def _callback_best_so_far(self, callback, best_ever):
        """Emit the best sample available for iteration progress."""
        if callback and len(self._all_samples) > 0:
            best_so_far = self._all_samples[0]
            callback(best_so_far if best_ever is None or best_so_far.y <= best_ever.y else best_ever)

    def _run_sequential_local_search(self, cand_x, cand_y, n_dispatch: int, callback, best_ever):
        """Run local search sequentially for the best candidates."""
        idx_sorted = np.argsort(cand_y)[:n_dispatch]
        for idx in idx_sorted:
            if self.stop_event and self.stop_event.is_set():
                break
            x_start = cand_x[idx]
            searcher = GradientSearcher(
                self.objective,
                self.bounds,
                self.config,
                self.stop_event,
                monitor_callback=self._make_monitor_callback(callback),
            )
            try:
                x_opt, f_opt, n_ev = searcher.search(x_start, self._local_search_budget())
                self.n_evals += n_ev
                self.clusterer.add_cluster_result(x_opt, f_opt)
                if best_ever is None or f_opt < best_ever.y:
                    best_ever = Sample(x=x_opt, y=f_opt)
                    if callback:
                        callback(best_ever)
            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.getLogger("CERTUS").error("[INDEX.PGLOBAL] local search failed | mode=sequential | reason=%s", e, exc_info=True)
        return best_ever

    def _run_parallel_local_search(self, cand_x, cand_y, n_dispatch: int, callback, best_ever):
        """Run local search in the executor for the best candidates."""
        idx_sorted = np.argsort(cand_y)[:n_dispatch]
        futures = {}
        for idx in idx_sorted:
            if self.stop_event and self.stop_event.is_set():
                break
            x_start = cand_x[idx]
            searcher = GradientSearcher(
                self.objective,
                self.bounds,
                self.config,
                self.stop_event,
                monitor_callback=None,
            )
            futures[self._executor.submit(searcher.search, x_start, self._local_search_budget())] = x_start
        for future in as_completed(futures):
            if self.stop_event and self.stop_event.is_set():
                break
            try:
                x_opt, f_opt, n_ev = future.result(timeout=60)
                self.n_evals += n_ev
                self.clusterer.add_cluster_result(x_opt, f_opt)
                if best_ever is None or f_opt < best_ever.y:
                    best_ever = Sample(x=x_opt, y=f_opt)
                    if callback:
                        callback(best_ever)
            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.getLogger("CERTUS").error("[INDEX.PGLOBAL] local search failed | mode=parallel | reason=%s", e, exc_info=True)
        return best_ever

    def optimize(self, max_iter: int = 30, callback=None, x0: np.ndarray | None = None) -> Sample | None:

        start_time = time.time()

        best_ever: Sample | None = None

        # Inject initial guess if provided

        if x0 is not None:
            try:
                y0 = float(self.objective(x0))

                s0 = Sample(x=x0.copy(), y=y0)

                self._all_samples.append(s0)

                best_ever = s0

                self.n_evals += 1

                if callback:
                    callback(best_ever)

            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.getLogger("CERTUS").debug("[INDEX.PGLOBAL] initial guess rejected | reason=%s", e)

        # Limit Numba threads when using ThreadPoolExecutor to avoid CPU oversubscription

        _numba_restore = None

        if self.n_workers > 1:
            import numba

            nb_cores = _get_cpu_count()

            try:
                _numba_restore = int(numba.get_num_threads())

            except NUMERICAL_FAULT_EXCEPTIONS :
                _numba_restore = _numba_set_threads_clamped(nb_cores)

            # nb_cores // n_workers peut depasser 31 ; restauration utilisait nb_cores brut -> ValueError

            numba.set_num_threads(_numba_set_threads_clamped(max(1, nb_cores // self.n_workers)))

            self._executor = ThreadPoolExecutor(max_workers=self.n_workers)

        else:
            self._executor = None

        try:
            for iteration in range(max_iter):
                if self._should_stop_optimization(start_time, iteration):
                    break

                n_samples = self.config.n_samples_per_iter
                if iteration == 0:
                    n_samples = int(n_samples * 1.5)

                prepared = self._prepare_iteration_batches(n_samples)
                if not prepared:
                    break
                n_keep, cand_x, cand_y = prepared
                n_dispatch = min(len(cand_y), self.n_workers)

                self._callback_best_so_far(callback, best_ever)

                if self.n_workers <= 1 and n_dispatch > 0:
                    best_ever = self._run_sequential_local_search(cand_x, cand_y, n_dispatch, callback, best_ever)
                elif n_dispatch > 0 and self._executor:
                    best_ever = self._run_parallel_local_search(cand_x, cand_y, n_dispatch, callback, best_ever)

                if len(self._all_samples) > n_keep * 2:
                    self._all_samples = self._all_samples[:n_keep]

        finally:
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)

                self._executor = None

            # Restore Numba thread count after parallel sampling

            if _numba_restore is not None:

                numba.set_num_threads(_numba_set_threads_clamped(_numba_restore))

        best_cluster = self.clusterer.get_best_minimum()

        if best_cluster:
            x_best, y_best = best_cluster

            if best_ever is None or y_best < best_ever.y:
                best_ever = Sample(x=x_best, y=y_best)

        # Return true best: may be a Sobol sample never refined by L-BFGS-B

        if self._all_samples:
            self._all_samples.sort(key=lambda s: s.y)

            best_sample = self._all_samples[0]

            if best_ever is None or best_sample.y < best_ever.y:
                best_ever = best_sample

        return best_ever

    def cleanup(self) -> None:

        self.clusterer.clear()


class SubsetOptimTask:
    def __init__(self, worker, wls, n_sub, target_T, target_R, exclude_range) -> None:

        self.worker = worker

        self.wls = wls

        self.n_sub = n_sub

        self.target_T = target_T

        self.target_R = target_R

        self.exclude_range = exclude_range

    def __call__(self, offset) -> Any:

        return self.worker._run_subset_optim(
            slice(offset, None, 3), self.wls, self.n_sub, self.target_T, self.target_R, self.exclude_range
        )
