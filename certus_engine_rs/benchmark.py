import sys
import os

# Add parent directory to path so we can import certus
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import timeit
import numpy as np
from certus.physics.certus_tmm_matrix import calc_spectrum_front as numba_calc_spectrum_front
from certus.core.certus_core import TWO_PI
import certus_rust_poc

def generate_mock_data(num_wavelengths=2000, num_layers=60):
    # Wavelengths from 400nm to 800nm
    wls = np.linspace(400.0, 800.0, num_wavelengths)
    k0_array = TWO_PI / wls

    # Random layer thicknesses between 10nm and 100nm
    thicknesses = np.random.uniform(10.0, 100.0, num_layers)

    # Random complex refractive indices for the layers
    n_real = np.random.uniform(1.4, 2.5, (num_wavelengths, num_layers))
    k_imag = np.random.uniform(0.0, 0.1, (num_wavelengths, num_layers))
    n_layers_complex = n_real - 1j * k_imag

    # Substrate index (e.g. Glass)
    n_sub_complex = np.full(num_wavelengths, 1.5 - 0.0j, dtype=np.complex128)

    return wls, k0_array, thicknesses, n_layers_complex, n_sub_complex

def run_benchmark():
    print("Generating mock data (2000 wavelengths, 60 layers)...")
    wls, k0_array, thicknesses, n_layers_complex, n_sub_complex = generate_mock_data(2000, 60)

    print("Running Numba implementation (warming up JIT)...")
    T_num, R_num = numba_calc_spectrum_front(wls, thicknesses, n_layers_complex, n_sub_complex)
    
    print("Running Rust implementation...")
    R_rust, T_rust = certus_rust_poc.calc_spectrum_front(k0_array, thicknesses, n_layers_complex, n_sub_complex)

    print("\nValidating precision...")
    if np.allclose(R_num, R_rust, atol=1e-12) and np.allclose(T_num, T_rust, atol=1e-12):
        print("SUCCESS: Rust and Numba outputs match exactly (atol=1e-12).")
    else:
        print("ERROR: Output mismatch!")
        print("Max R diff:", np.max(np.abs(R_num - R_rust)))
        print("Max T diff:", np.max(np.abs(T_num - T_rust)))
        return

    print("\nBenchmarking performance (1000 iterations)...")
    
    numba_time = timeit.timeit(
        lambda: numba_calc_spectrum_front(k0_array, thicknesses, n_layers_complex, n_sub_complex),
        number=1000
    )
    print(f"Numba: {numba_time:.4f} seconds total")
    
    rust_time = timeit.timeit(
        lambda: certus_rust_poc.calc_spectrum_front(k0_array, thicknesses, n_layers_complex, n_sub_complex),
        number=1000
    )
    print(f"Rust:  {rust_time:.4f} seconds total")
    
    speedup = numba_time / rust_time
    print(f"\nRust is {speedup:.2f}x faster than Numba for this workload.")

if __name__ == "__main__":
    run_benchmark()
