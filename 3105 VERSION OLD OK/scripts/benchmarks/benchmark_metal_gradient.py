import sys

import os
from pathlib import Path

import time

import numpy as np



# Ensure parent directory is in path

sys.path.append(str(Path(__file__).resolve().parents[2]))



from certus.core._certus_physics_impl import _compute_metal_tmm_gradient_kernel





def benchmark_metal_gradient():

    print("Benchmarking _compute_metal_tmm_gradient_kernel...")



    # Setup Data

    n_pts = 100000  # 100k points for heavy load

    l_array = np.linspace(400, 800, n_pts).astype(np.float64)

    nM_complex = (0.5 - 3.0j) * np.ones(n_pts, dtype=np.complex128)  # n - ik

    eM = 10.0

    eL = 50.0

    nL_complex = (1.45 + 0.0j) * np.ones(n_pts, dtype=np.complex128)

    nSub_complex = (3.5 + 0.0j) * np.ones(n_pts, dtype=np.complex128)

    r_tgt_array = np.random.rand(n_pts).astype(np.float64) * 0.5



    # Warmup

    print("Warmup...")

    _compute_metal_tmm_gradient_kernel(

        l_array[:100],

        nM_complex[:100],

        eM,

        eL,

        nL_complex[:100],

        nSub_complex[:100],

        r_tgt_array[:100],

    )



    # Benchmark

    print(f"Running benchmark with {n_pts} points...")

    start_time = time.perf_counter()

    res = _compute_metal_tmm_gradient_kernel(

        l_array, nM_complex, eM, eL, nL_complex, nSub_complex, r_tgt_array

    )

    end_time = time.perf_counter()



    duration = (end_time - start_time) * 1000.0

    print(f"Execution Time: {duration:.2f} ms")

    print(f"Result (MSE): {res[0]}")



    return duration





if __name__ == "__main__":

    benchmark_metal_gradient()

