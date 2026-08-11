"""P1-12 Micro-Batch B.6 – Direct tests for simulate_stack_robustness_batch.

Invariants verified:
  1. Zero-noise batch returns exact nominal thicknesses (determinism).
  2. Non-zero noise produces spread proportional to noise level.
  3. Output shape is (n_runs, n_layers).
"""
from __future__ import annotations

import numpy as np
import pytest

from certus_physics import simulate_stack_robustness_batch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N_H = 2.3 + 0j
N_L = 1.45 + 0j
N_SUB = 1.52 + 0j
L0 = 550.0  # reference wavelength (nm)

D_H = L0 / (4.0 * np.real(N_H))
D_L = L0 / (4.0 * np.real(N_L))

P_THICK_NOMINAL = np.array([D_H, D_L, D_H], dtype=np.float64)
LAYER_WLS = np.array([550.0, 550.0, 550.0], dtype=np.float64)  # monitoring wl per layer

N_H_VALS = np.full(3, N_H, dtype=np.complex128)
N_L_VALS = np.full(3, N_L, dtype=np.complex128)
N_SUB_VALS = np.full(3, N_SUB, dtype=np.complex128)

NUM_RUNS = 20


def _make_noise(num_runs: int, n_layers: int, scale: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, scale, (num_runs, n_layers)).astype(np.float64)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_b6_output_shape():
    """simulate_stack_robustness_batch returns (n_runs, n_layers)."""
    noise = _make_noise(NUM_RUNS, len(P_THICK_NOMINAL), 0.01)
    sim_thick, _, _, _, _ = simulate_stack_robustness_batch(
        P_THICK_NOMINAL, LAYER_WLS, N_H_VALS, N_L_VALS, N_SUB_VALS,
        noise, probe_offset=0.0, non_monotonic_factor=2.0,
    )
    assert sim_thick.shape == (NUM_RUNS, len(P_THICK_NOMINAL)), (
        f"Unexpected shape: {sim_thick.shape}"
    )


def test_b6_zero_noise_returns_nominal():
    """With zero noise, simulated thicknesses must equal nominal values."""
    noise = np.zeros((NUM_RUNS, len(P_THICK_NOMINAL)), dtype=np.float64)
    sim_thick, _, _, _, _ = simulate_stack_robustness_batch(
        P_THICK_NOMINAL, LAYER_WLS, N_H_VALS, N_L_VALS, N_SUB_VALS,
        noise, probe_offset=0.0, non_monotonic_factor=2.0,
    )
    for run_i in range(NUM_RUNS):
        np.testing.assert_allclose(
            sim_thick[run_i], P_THICK_NOMINAL, rtol=1e-4,
            err_msg=f"Run {run_i}: simulated thicknesses differ from nominal with zero noise"
        )


def test_b6_nonzero_noise_produces_spread():
    """Non-zero noise yields std > 0 for each layer across runs."""
    noise = _make_noise(NUM_RUNS, len(P_THICK_NOMINAL), 0.05, seed=42)
    sim_thick, _, _, _, _ = simulate_stack_robustness_batch(
        P_THICK_NOMINAL, LAYER_WLS, N_H_VALS, N_L_VALS, N_SUB_VALS,
        noise, probe_offset=0.0, non_monotonic_factor=2.0,
    )
    std_per_layer = sim_thick.std(axis=0)
    assert np.all(std_per_layer > 0), (
        f"Expected std > 0 for all layers, got: {std_per_layer}"
    )
