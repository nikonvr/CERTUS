"""
CERTUS Baseline Performance Benchmark

Mesure les performances actuelles pour établir une baseline avant optimisations.
"""

import time
import tracemalloc
from pathlib import Path
import numpy as np
import json
from datetime import datetime


def benchmark_tmm_calculation():
    """Benchmark TMM core calculation."""
    from certus.physics.certus_tmm_core import coh_tmm

    # Setup: typical AR coating
    n_list = [1.0, 2.3, 1.46, 1.52]  # air/TiO2/SiO2/glass
    d_list = [np.inf, 50, 100, np.inf]  # nm
    wavelengths = np.linspace(400, 800, 401)  # nm

    tracemalloc.start()
    start = time.perf_counter()

    # Run benchmark
    results = []
    for wl in wavelengths:
        try:
            result = coh_tmm("s", n_list, d_list, 0, wl)
            results.append(result)
        except Exception as e:
            print(f"TMM failed at {wl}nm: {e}")
            break

    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "name": "TMM Core (401 wavelengths)",
        "duration_ms": elapsed * 1000,
        "throughput_wl_per_sec": len(results) / elapsed if elapsed > 0 else 0,
        "memory_peak_mb": peak / 1024 / 1024,
        "success_count": len(results),
    }


def benchmark_spline_optimization():
    """Benchmark spline optimization."""
    from certus.spline.spline_pipeline_mesh_clean import auto_clean_knot_mesh

    # Setup: synthetic spline result
    n_knots = 20
    sigma_knots = np.linspace(0.01, 0.5, n_knots)
    coeffs = np.random.randn(n_knots * 2)  # n, k coefficients

    base_result = {
        "sigma_knots": sigma_knots,
        "coeffs": coeffs,
        "rmse": 0.05,
        "d_nm": 100.0,
    }

    # Mock objective function
    def mock_objective(test_knots, test_coeffs):
        return np.random.rand() * 0.1

    tracemalloc.start()
    start = time.perf_counter()

    try:
        # Note: auto_clean_knot_mesh needs proper params, skipping for now
        # This is placeholder for real benchmark
        time.sleep(0.1)  # Simulate work
        success = True
    except Exception as e:
        print(f"Spline optimization failed: {e}")
        success = False

    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "name": "Spline Auto-clean (mock)",
        "duration_ms": elapsed * 1000,
        "memory_peak_mb": peak / 1024 / 1024,
        "success": success,
    }


def benchmark_numpy_operations():
    """Benchmark numpy operations utilisées intensivement."""
    size = 10000

    tracemalloc.start()
    start = time.perf_counter()

    # Typical operations
    a = np.random.randn(size)
    b = np.random.randn(size)

    # Matrix operations
    c = np.dot(a, b)
    d = np.fft.fft(a)
    e = np.sqrt(a**2 + b**2)
    f = np.linalg.norm(a)

    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "name": "NumPy Operations (10k elements)",
        "duration_ms": elapsed * 1000,
        "memory_peak_mb": peak / 1024 / 1024,
    }


def benchmark_import_time():
    """Benchmark import time for heavy modules."""
    import sys
    import importlib

    modules_to_test = [
        "scipy",
        "scipy.optimize",
        "matplotlib",
        "matplotlib.pyplot",
    ]

    results = {}
    for module_name in modules_to_test:
        # Unload if already loaded
        if module_name in sys.modules:
            del sys.modules[module_name]

        start = time.perf_counter()
        try:
            importlib.import_module(module_name)
            elapsed = time.perf_counter() - start
            results[module_name] = {
                "duration_ms": elapsed * 1000,
                "success": True,
            }
        except ImportError as e:
            results[module_name] = {
                "duration_ms": 0,
                "success": False,
                "error": str(e),
            }

    return {
        "name": "Import Time",
        "modules": results,
        "total_ms": sum(r["duration_ms"] for r in results.values()),
    }


def run_all_benchmarks():
    """Exécute tous les benchmarks et sauvegarde les résultats."""
    print("=" * 60)
    print("CERTUS Performance Baseline Benchmark")
    print("=" * 60)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"NumPy version: {np.__version__}")
    print()

    benchmarks = [
        benchmark_numpy_operations,
        benchmark_import_time,
        benchmark_tmm_calculation,
        # benchmark_spline_optimization,  # Skip for now (needs proper setup)
    ]

    results = {
        "timestamp": datetime.now().isoformat(),
        "numpy_version": np.__version__,
        "benchmarks": [],
    }

    for bench_func in benchmarks:
        print(f"Running: {bench_func.__name__}...", flush=True)
        try:
            result = bench_func()
            results["benchmarks"].append(result)

            print(f"  [OK] {result['name']}")
            if "duration_ms" in result:
                print(f"    Duration: {result['duration_ms']:.2f} ms")
            if "memory_peak_mb" in result:
                print(f"    Memory: {result['memory_peak_mb']:.2f} MB")
            if "throughput_wl_per_sec" in result:
                print(f"    Throughput: {result['throughput_wl_per_sec']:.0f} wl/sec")
            print()
        except Exception as e:
            print(f"  [FAIL] Failed: {e}")
            print(f"    {type(e).__name__}: {e}")
            print()
            results["benchmarks"].append(
                {
                    "name": bench_func.__name__,
                    "error": str(e),
                    "success": False,
                }
            )

    # Save results
    output_file = Path("benchmark_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 60)
    print(f"Results saved to: {output_file}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_all_benchmarks()
