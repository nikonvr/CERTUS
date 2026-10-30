"""Throughput of DESIGN's cost-and-gradient call: inner (wavelength) parallelism against parallel candidates (2026-10-29).

The call is the one of the memetic polish and of the local polish, `compute_gradient_all_layers_analytic`, on the 50/50
problem (34 layers, 1601 wavelengths 400-1200 nm, T = 50 %). Throughput in calls per second for:
  A. one caller, all Numba threads (DESIGN today);
  B. one caller, one Numba thread;
  C. WORKERS threads, each with one Numba thread (candidates polished in parallel, the kernel is nogil);
  D. WORKERS threads, each with all Numba threads (oversubscription).
Run alone (CLAUDE.md section 4: a measurement beside another job is not a measurement).

usage: python design_speed_check.py [CALLS] [WORKERS]   -> design_speed_check.out
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numba
import numpy as np
import search as s  # also puts the repository on sys.path

from certus_physics import Target, compute_gradient_all_layers_analytic, prepare_targets_vectorized

CALLS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 7
N = 34
WLS = np.linspace(400.0, 1200.0, 1601)
NL = np.ascontiguousarray(np.array([[2.35 if k % 2 == 0 else 1.45 for k in range(N)]] * len(WLS), dtype=np.complex128))
NSUB = np.full(len(WLS), 1.52 + 0j)
TV, TW = (np.asarray(v, dtype=np.float64) for v in prepare_targets_vectorized(WLS, [Target(400.0, 1200.0, 50.0, 50.0)]))
NB, DB = np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0)
VAR = np.arange(N, dtype=np.int64)
ALL = numba.get_num_threads()


def call(ep):
    return compute_gradient_all_layers_analytic(ep, NL, NSUB, WLS, TV, TW, 0.01, False, NB, DB, VAR)


def run(seed: int, threads: int, calls: int) -> float:
    numba.set_num_threads(threads)
    ep = np.random.default_rng(seed).uniform(20.0, 150.0, N)
    t0 = time.perf_counter()
    for k in range(calls):
        ep[k % N] += 1e-6
        call(ep)
    return time.perf_counter() - t0


def main() -> None:
    call(np.full(N, 80.0))  # compile
    lines = [f"Numba threads available: {ALL}; {CALLS} calls per caller; {WORKERS} parallel callers"]
    t = run(0, ALL, CALLS)
    lines.append(f"A one caller, {ALL} threads: {CALLS / t:.0f} calls/s")
    t = run(0, 1, CALLS)
    lines.append(f"B one caller, 1 thread: {CALLS / t:.0f} calls/s")
    for label, threads in (("C", 1), ("D", ALL)):
        t0 = time.perf_counter()
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(lambda k, th=threads: run(k, th, CALLS), range(WORKERS)))
        t = time.perf_counter() - t0
        lines.append(f"{label} {WORKERS} callers, {threads} thread(s) each: {WORKERS * CALLS / t:.0f} calls/s")
    with open(s.HERE / "design_speed_check.out", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
