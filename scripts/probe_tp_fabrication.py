"""ACTIONS A1 and A2 of the roadmap -- turning-point detection under smoothing.

    .venv\\Scripts\\python.exe scripts\\probe_tp_fabrication.py

Takes no argument. Prints three tables and a verdict per action. Paste the WHOLE
output. Nothing to configure, nothing to choose.

WHAT IT MEASURES

  A1 -- FABRICATION. On a perfectly FLAT clean signal, any turning point the
        detector reports was made by the noise alone. The fraction of layers
        where that happens is the quantity that governs the crash rate.

  A2 -- SURVIVAL. On a clean signal WITHOUT noise, smoothing must not erase a
        real extremum. This is the face of the problem that has never been
        measured.

WHY IT IS BUILT THIS WAY

  * It calls the REAL `detect_turning_points` and the REAL
    `_seeded_noise_sample`. A reimplementation would measure a copy, not the
    code -- and CLAUDE.md forbid 7 exists because two sign bugs were found in
    reimplementations.
  * No TMM, no Monte-Carlo, no bench. Seconds, not minutes.
  * The smoothing here is CENTRED, which is what the frozen model of 9bis
    describes. The kernel currently implements a trailing average (finding 3 of
    section 17); this probe measures the model, not the defect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from certus.physics.certus_strat_math import _seeded_noise_sample  # noqa: E402
from certus_physics import detect_turning_points  # noqa: E402

#: Reading-noise half-amplitude, in T units. A = trigger_tolerance / 100 = 5e-4.
A: float = 5e-4
#: Draws per configuration. 20 000 is what produced the reference table of 12.2.
N_DRAWS: int = 20_000
#: Reference seed. Fixed so the numbers are reproducible.
SEED: int = 20260809


@njit(cache=True, nogil=True)
def _smooth_centred_into(x, out, k):
    """Centred moving average of `k` samples, shrinking symmetrically at the edges.

    Centred, not trailing: a trailing average shifts a detected extremum by
    (k-1)/2 samples, which 9bis-5 forbids ("no delay").
    """
    n = x.size
    if k <= 1:
        for i in range(n):
            out[i] = x[i]
        return
    half = k // 2
    for i in range(n):
        lo = i - half
        hi = i + half + 1
        if lo < 0:
            lo = 0
        if hi > n:
            hi = n
        acc = 0.0
        for j in range(lo, hi):
            acc += x[j]
        out[i] = acc / (hi - lo)


@njit(cache=True, nogil=True)
def _fabrication_loop(n_draws, n_samples, k, hysteresis, noise_scale, amp, seed):
    """Driver loop, compiled. Calls the REAL noise generator and the REAL detector.

    Compiled because the Python version needs ~16 million scalar calls and does not
    finish in ten minutes. Nothing about the measurement changes -- only the speed.
    """
    raw = np.empty(n_samples, dtype=np.float64)
    smoothed = np.empty(n_samples, dtype=np.float64)
    fabricated = 0
    for draw in range(n_draws):
        for m in range(n_samples):
            raw[m] = noise_scale * amp * _seeded_noise_sample(seed, 0, draw, m, True)
        _smooth_centred_into(raw, smoothed, k)  # clean part is flat and equal to 0
        n_tp, _, _ = detect_turning_points(smoothed, n_samples, n_samples - 1, False, hysteresis)
        if n_tp > 0:
            fabricated += 1
    return fabricated


def smooth_centred(x: np.ndarray, k: int) -> np.ndarray:
    out = np.empty(x.size, dtype=np.float64)
    _smooth_centred_into(x, out, k)
    return out


def fabrication_rate(n_samples: int, k: int, factor: float, noise_scale: float = 1.0) -> float:
    """Fraction of draws where noise alone fabricates a turning point on a FLAT signal."""
    fabricated = _fabrication_loop(
        N_DRAWS, n_samples, k, factor * A, noise_scale, A, SEED
    )
    return 100.0 * fabricated / N_DRAWS


def clean_cosine(n_samples: int, n_periods: float) -> np.ndarray:
    """Clean noiseless monitoring-like signal with a KNOWN number of extrema."""
    d = np.linspace(0.0, n_periods * 2.0 * np.pi, n_samples)
    return 0.5 - 0.45 * np.cos(d)


def main() -> int:
    print("=" * 78)
    print("A1 -- FABRICATION OF TURNING POINTS BY NOISE ALONE (flat clean signal)")
    print(f"     A = {A:g}   draws = {N_DRAWS}   seed = {SEED}   smoothing = CENTRED")
    print("=" * 78)

    print("\nStep 1 -- REPRODUCE A KNOWN LINE. If this is not ~99.9 %, the probe is")
    print("          wrong and everything below is meaningless. STOP there.")
    known = fabrication_rate(n_samples=800, k=1, factor=1.66)
    print(f"\n  k=1, threshold 1.66 A, N=800  ->  {known:8.3f} %     (reference: 99.935 %)")
    step1_ok = 99.0 <= known <= 100.0
    print(f"  STEP1={'OK' if step1_ok else 'FAILED -- STOP HERE, DO NOT CONTINUE'}")
    if not step1_ok:
        print("\nA1=INVALID")
        return 1

    print("\nStep 2 -- THE MEASUREMENT. Frozen model: k = 8, threshold 1/sqrt(8) = 0.354.")
    frozen = fabrication_rate(n_samples=800, k=8, factor=0.354)
    print(f"\n  k=8, threshold 0.354 A, N=800  ->  {frozen:8.3f} %    (expected: ~0 %)")

    print("\nStep 3 -- TRAP 1. Divide the noise by 100. A quantity that does not vary")
    print("          with the noise is an artifact, without exception.")
    tiny = fabrication_rate(n_samples=800, k=8, factor=0.354, noise_scale=0.01)
    print(f"\n  same, noise x0.01              ->  {tiny:8.3f} %     (expected: 0.000 %)")

    print("\nStep 4 -- SWEEP k with the derived threshold 1/sqrt(k).")
    print(f"\n  {'k':>4s}  {'threshold':>10s}  {'fabrication':>12s}")
    print("  " + "-" * 30)
    sweep = []
    for k in (1, 2, 4, 8, 16):
        f = 1.0 / np.sqrt(k)
        rate = fabrication_rate(n_samples=800, k=k, factor=f)
        sweep.append(rate)
        print(f"  {k:>4d}  {f:>10.4f}  {rate:>11.3f} %")
    monotonic = all(sweep[i] >= sweep[i + 1] - 1e-9 for i in range(len(sweep) - 1))
    print(f"\n  MONOTONIC={'YES' if monotonic else 'NO -- report this, do not smooth it over'}")

    print("\nStep 5 -- THE EMPIRICAL BOUND. 12.2 says in writing that 0.354 is a")
    print("          DERIVATION, not a measurement, and that the bound must be")
    print("          measured because neighbouring samples are correlated.")
    print("          Here it is, at k = 8, N = 800.")
    print(f"\n  {'factor':>8s}  {'in sigma_smoothed':>18s}  {'fabrication':>12s}")
    print("  " + "-" * 44)
    sigma_smoothed_in_A = 1.0 / (3.0 * np.sqrt(8.0))
    bound = None
    for factor in (0.354, 0.5, 0.707, 1.0, 1.25, 1.5, 1.66, 2.0, 2.4):
        rate = fabrication_rate(n_samples=800, k=8, factor=factor)
        print(f"  {factor:>8.3f}  {factor / sigma_smoothed_in_A:>18.2f}  {rate:>11.3f} %")
        if bound is None and rate < 1.0:
            bound = factor
    print(f"\n  FIRST FACTOR UNDER 1 % = {bound if bound is not None else 'NONE IN RANGE'}")

    print("\n" + "-" * 78)
    if frozen <= 1.0 and tiny <= 0.05:
        print("A1=PASS   the frozen model of 9bis holds on this measurement")
    else:
        print("A1=FAIL   PASTE THIS OUTPUT AND STOP.")
        print("          DO NOT RAISE THE THRESHOLD TO MAKE THE NUMBER PASS.")
        print("          It is 9bis that gets reopened, not this action.")

    print("\n" + "=" * 78)
    print("A2 -- DO REAL EXTREMA SURVIVE THE SMOOTHING? (clean signal, NO noise)")
    print("=" * 78)
    print(f"\n  {'periods':>8s}  {'N':>6s}  {'k=1':>6s}  {'k=8':>6s}  {'k=16':>6s}  {'k=32':>6s}  verdict")
    print("  " + "-" * 62)
    a2_ok = True
    for periods, n_samples in ((2.0, 800), (4.0, 800), (8.0, 800), (16.0, 800)):
        clean = clean_cosine(n_samples, periods)
        counts = []
        for k in (1, 8, 16, 32):
            sig = smooth_centred(clean, k)
            n_tp, _, _ = detect_turning_points(sig, n_samples, n_samples - 1, False, 0.354 * A)
            counts.append(n_tp)
        ok = counts[1] == counts[0]
        a2_ok = a2_ok and ok
        verdict = "ok" if ok else "LOST AT k=8"
        print(
            f"  {periods:>8.1f}  {n_samples:>6d}  {counts[0]:>6d}  {counts[1]:>6d}  "
            f"{counts[2]:>6d}  {counts[3]:>6d}  {verdict}"
        )
    print("\n  Read the k=8 column against k=1. They must be EQUAL.")
    print("  A drop means the window rounds off real extrema and is too wide.")
    print(f"\nA2={'PASS' if a2_ok else 'FAIL -- say so, the window is too wide'}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
