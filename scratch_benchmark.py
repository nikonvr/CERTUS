import time
import json
import logging
from certus.core.certus_core import get_certus_logger

# Simple run to establish baseline
def run_benchmark():
    start = time.perf_counter()
    import numpy as np
    
    # 50 layers stack
    num_layers = 50
    p_thick = np.full(num_layers, 50.0, dtype=np.float64)
    nH = np.full(1000, 2.3, dtype=np.complex128)
    nL = np.full(1000, 1.45, dtype=np.complex128)
    nSub = np.full(1000, 1.5, dtype=np.complex128)
    wl_arr = np.linspace(400, 800, 1000)
    
    from certus.physics.certus_tmm_matrix import calculate_reflectance_bilayer_vectorized
    for _ in range(500):
        # We simulate the matrix product 500 times
        calculate_reflectance_bilayer_vectorized(wl_arr, nH, nL, nSub, p_thick, 1.0, 0.0)
    
    elapsed = time.perf_counter() - start
    print(f"BASELINE: {elapsed:.4f}s")
    return elapsed

if __name__ == "__main__":
    run_benchmark()
