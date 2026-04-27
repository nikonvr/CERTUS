import sys
import os
import time
from pathlib import Path
import numpy as np

# Ensure parent directory is in path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from CERTUS_INDEX import run_coordinate_descent_RT, run_coordinate_descent_fixed_d_RT


def benchmark_index_optimization():
    print("Benchmarking CERTUS_INDEX optimization functions...")

    # Data Setup
    n_pts = 5000  # High number of points to stress the loop
    wls = np.linspace(350, 1000, n_pts).astype(np.float64)
    n_sub = np.ones(n_pts, dtype=np.float64) * 1.5

    # Targets (synthetic)
    target_T = np.ones(n_pts, dtype=np.float64) * 0.9
    target_R = np.ones(n_pts, dtype=np.float64) * 0.04
    weights = np.ones(n_pts, dtype=np.float64)

    # Initial Params [d, Eg, A, E0, C, Eu, eps_inf]
    start_params = np.array([100.0, 3.5, 100.0, 4.0, 1.0, 0.5, 2.0], dtype=np.float64)

    # Config
    max_iter = 50
    use_T = True
    use_R = True
    use_normalized = True  # This triggers the loop we want to optimize
    weight_T = 1.0
    weight_R = 1.0
    is_frosted = False

    # Warmup
    print("Warmup...")
    run_coordinate_descent_RT(
        start_params,
        wls[:100],
        target_T[:100],
        target_R[:100],
        n_sub[:100],
        weights[:100],
        use_T,
        use_R,
        use_normalized,
        weight_T,
        weight_R,
        is_frosted,
        max_iter=5,
    )

    # Benchmark run_coordinate_descent_RT
    print(f"Running run_coordinate_descent_RT ({n_pts} pts, {max_iter} iters)...")
    start_time = time.perf_counter()
    res_params, res_mse = run_coordinate_descent_RT(
        start_params,
        wls,
        target_T,
        target_R,
        n_sub,
        weights,
        use_T,
        use_R,
        use_normalized,
        weight_T,
        weight_R,
        is_frosted,
        max_iter,
    )
    end_time = time.perf_counter()
    duration = (end_time - start_time) * 1000.0
    print(f"run_coordinate_descent_RT Time: {duration:.2f} ms")

    # Benchmark run_coordinate_descent_fixed_d_RT
    print(
        f"Running run_coordinate_descent_fixed_d_RT ({n_pts} pts, {max_iter} iters)..."
    )
    start_time_fixed = time.perf_counter()
    res_params_fixed, res_mse_fixed = run_coordinate_descent_fixed_d_RT(
        start_params,
        wls,
        target_T,
        target_R,
        n_sub,
        weights,
        use_T,
        use_R,
        use_normalized,
        weight_T,
        weight_R,
        is_frosted,
        max_iter,
    )
    end_time_fixed = time.perf_counter()
    duration_fixed = (end_time_fixed - start_time_fixed) * 1000.0
    print(f"run_coordinate_descent_fixed_d_RT Time: {duration_fixed:.2f} ms")

    return duration, duration_fixed


if __name__ == "__main__":
    benchmark_index_optimization()
