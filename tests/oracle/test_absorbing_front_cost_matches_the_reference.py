"""DESIGN's front-only gradient path must optimize the transmittance of absorbing layers given as n - ik.

C20 (D113), measured 2026-11-14: with absorbing layers in the project convention n - ik, a lossless substrate and no
backside, `compute_gradient_all_layers_analytic` handed the indices to `_compute_gradient_analytic_kernel`, which is
right only for n + ik. Its cost was 343 % above the independent reference on the case below, and its gradient was the
derivative of that other cost: L-BFGS-B minimized another objective while the final RMSE, computed by the production
TMM, looked right. The finite-difference tests did not see it: they differentiate the kernel's own cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from tmm_reference import rt_stack

from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

THICKNESSES = np.array([60.0, 100.0, 80.0])
WAVELENGTHS = np.array([450.0, 550.0, 650.0])
TARGETS = np.array([0.6, 0.4, 0.6])
WEIGHTS = np.array([1.0, 2.0, 0.5])
N_SUB = 1.52 + 0j


def _layers() -> np.ndarray:
    n = np.zeros((WAVELENGTHS.size, 3), dtype=np.complex128)
    for i, wl in enumerate(WAVELENGTHS):
        dispersion = 550.0 / wl - 1.0
        n[i] = [complex(2.3 + 0.02 * dispersion, -0.03), complex(1.45 + 0.01 * dispersion, -0.01),
                complex(2.3 + 0.02 * dispersion, -0.05)]
    return n


def _reference_cost(thicknesses: np.ndarray, layers: np.ndarray) -> float:
    rt = [rt_stack(float(wl), layers[i], thicknesses, 1.0 + 0j, N_SUB) for i, wl in enumerate(WAVELENGTHS)]
    transmittance = np.array([t for _r, t in rt])
    return float(np.sum(WEIGHTS * (transmittance - TARGETS) ** 2) / np.sum(WEIGHTS))


def _certus(thicknesses: np.ndarray, layers: np.ndarray) -> tuple[float, np.ndarray]:
    no_back = np.zeros((WAVELENGTHS.size, 0), dtype=np.complex128)
    return compute_gradient_all_layers_analytic(
        thicknesses, layers, np.full(WAVELENGTHS.size, N_SUB), WAVELENGTHS, TARGETS, WEIGHTS, 0.0, False, no_back,
        np.zeros(0), np.arange(THICKNESSES.size, dtype=np.int64),
    )


def test_the_reference_absorbs() -> None:
    layers = _layers()
    for i, wl in enumerate(WAVELENGTHS):
        r, t = rt_stack(float(wl), layers[i], THICKNESSES, 1.0 + 0j, N_SUB)
        assert r + t < 1.0, "n - ik with k > 0 must absorb"


def test_the_front_only_cost_is_the_reference_cost() -> None:
    cost, _ = _certus(THICKNESSES, _layers())
    reference = _reference_cost(THICKNESSES, _layers())
    assert abs(cost - reference) <= 1e-9 * reference, (cost, reference)


def test_the_front_only_gradient_is_the_derivative_of_the_reference_cost() -> None:
    _, gradient = _certus(THICKNESSES, _layers())
    step = 1e-3
    finite = np.array([
        (_reference_cost(THICKNESSES + step * e, _layers()) - _reference_cost(THICKNESSES - step * e, _layers()))
        / (2.0 * step)
        for e in np.eye(THICKNESSES.size)
    ])
    assert np.allclose(gradient, finite, rtol=1e-5, atol=1e-10), (gradient, finite)


def test_lossless_layers_take_the_kernel_unchanged() -> None:
    """C1: the correction only touches absorbing layers; a lossless stack keeps its cost and gradient."""
    lossless = _layers().real.astype(np.complex128)
    cost, _ = _certus(THICKNESSES, lossless)
    assert abs(cost - _reference_cost(THICKNESSES, lossless)) <= 1e-9 * cost
