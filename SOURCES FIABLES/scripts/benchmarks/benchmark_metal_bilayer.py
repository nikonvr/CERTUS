import sys

import os
from pathlib import Path



sys.path.append(str(Path(__file__).resolve().parents[2]))



import time

import numpy as np

from numba import njit



try:

    from certus.core.certus_core import TWO_PI

except ImportError:

    # If certus_core is not found, define TWO_PI manually or try another path

    TWO_PI = 2.0 * np.pi



# Import the optimized function

try:

    from certus.core._certus_physics_impl import calculate_reflectance_bilayer_vectorized

except ImportError:

    from certus_physics import calculate_reflectance_bilayer_vectorized





# Define a SERIAL version for comparison (Gold Standard)

@njit(cache=True, fastmath=True)

def calculate_reflectance_bilayer_serial(

    l_array, nM_complex_array, eM_phys, eL_phys, nL_complex_array, nSub_complex_array

):

    n_pts = len(l_array)

    n0 = 1.0  # Air

    R_out = np.empty(n_pts, dtype=np.float64)



    for i in range(n_pts):

        wl = l_array[i]

        k0 = TWO_PI / wl



        nM = nM_complex_array[i]

        phiM = k0 * nM * eM_phys

        cM = np.cos(phiM)

        ispM = 1j * np.sin(phiM)

        m01_M = ispM / nM if abs(nM) > 1e-14 else 0j

        m10_M = ispM * nM



        nL = nL_complex_array[i]

        phiL = k0 * nL * eL_phys

        cL = np.cos(phiL)

        ispL = 1j * np.sin(phiL)

        m01_L = ispL / nL if abs(nL) > 1e-14 else 0j

        m10_L = ispL * nL



        # TMM CONVENTION: M @ L (Metal on Air side, Dielectric on Sub side)

        # Consistent with L_new @ M_old

        Mt00 = cM * cL + m01_M * m10_L

        Mt01 = cM * m01_L + m01_M * cL

        Mt10 = m10_M * cL + cM * m10_L

        Mt11 = m10_M * m01_L + cM * cL



        nS = nSub_complex_array[i]



        term1 = n0 * (Mt00 + nS * Mt01)

        term2 = Mt10 + nS * Mt11



        num = term1 - term2

        den = term1 + term2



        r = num / den if abs(den) > 1e-20 else 0j

        R = (r.real * r.real) + (r.imag * r.imag)



        if R < 0.0:

            R = 0.0

        elif R > 1.0:

            R = 1.0



        R_out[i] = R

    return R_out





def benchmark():

    print("Benchmarking METAL_BILAYER Kernel...")



    # Setup Data

    N = 100_000  # Large enough to see parallel benefits

    l_array = np.linspace(300, 1000, N)



    # Metal (Drude-like)

    n_metal = np.linspace(0.5, 1.5, N)

    k_metal = np.linspace(2.0, 4.0, N)

    nM_complex = n_metal - 1j * k_metal  # n - ik (Macleod)



    # Dielectric (Cauchy)

    nL_complex = np.linspace(1.45, 1.46, N) + 0j



    # substrate (Silicon-like)

    n_sub = np.linspace(3.5, 4.0, N)

    k_sub = np.linspace(0.1, 0.01, N)

    nSub_complex = n_sub - 1j * k_sub  # n - ik (Macleod)



    eM = 20.0

    eL = 900.0



    # Warmup

    print("Warmup JIT...")

    _ = calculate_reflectance_bilayer_serial(

        l_array[:10], nM_complex[:10], eM, eL, nL_complex[:10], nSub_complex[:10]

    )

    _ = calculate_reflectance_bilayer_vectorized(

        l_array[:10], nM_complex[:10], eM, eL, nL_complex[:10], nSub_complex[:10]

    )



    # Run Serial

    start = time.perf_counter()

    R_serial = calculate_reflectance_bilayer_serial(

        l_array, nM_complex, eM, eL, nL_complex, nSub_complex

    )

    time_serial = time.perf_counter() - start

    print(f"Serial Time:   {time_serial*1000:.2f} ms")



    # Run Parallel (Optimized)

    start = time.perf_counter()

    R_parallel = calculate_reflectance_bilayer_vectorized(

        l_array, nM_complex, eM, eL, nL_complex, nSub_complex

    )

    time_parallel = time.perf_counter() - start

    print(f"Parallel Time: {time_parallel*1000:.2f} ms")



    # Compute Speedup

    print(f"Speedup:       x{time_serial/time_parallel:.2f}")



    # Verification

    diff = np.max(np.abs(R_serial - R_parallel))

    print(f"Max Difference: {diff:.2e}")

    if diff < 1e-12:

        print("✅ VERIFICATION PASSED")

    else:

        print("❌ VERIFICATION FAILED")





if __name__ == "__main__":

    benchmark()

