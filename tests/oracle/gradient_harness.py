"""Analytical gradient verification harness.

RATIONALE
---------
An incorrect gradient raises no error. It produces no NaN, triggers no
assertion: it simply shifts the optimum towards which the optimizer converges. It is
the most costly category of defect in a solver, and the least visible.

This module provides a single verification — analytical derivative versus centered
finite difference — applied to all project functions exporting a gradient.

TWO PRINCIPLES
--------------
1. **Compare to the cost returned by the function ITSELF**, never to a reconstructed cost
   on the side. This is what makes the test decisive: it verifies the internal consistency
   of the (cost, gradient) pair, which is exactly what the optimizer needs. A reconstructed
   cost would introduce a second source of error and make any discrepancy ambiguous.

2. **Use NON-UNIFORM weights.** Several normalization errors — dividing
   by the number of points instead of the sum of weights, for instance — are invisible
   with weights all equal to 1, where the two denominators differ only by a constant factor.

CHOICE OF STEP AND TOLERANCE
----------------------------
The central step h balances truncation error (O(h²)) and rounding error
(O(eps/h)). For layer thicknesses in nm of the order of 100, h = 1e-6 nm places the expected
error around 1e-9 relative.

The discrepancy is referenced to the NORM of the gradient, ||g_a - g_n||_inf / ||g_n||_inf,
and not to each component taken in isolation. The noise of a finite difference is absolute —
of the order of eps.|cost|/h — thus independent of the measured component: referenced to a
direction a hundred times less sensitive than the dominant direction, it produces a huge
relative error without the gradient being incorrect.

Effective sensitivity, measured on compute_gradient_all_layers_analytic:

    global error of 0.001 %          -> DETECTED
    global error of 0.0001 %         -> not detected
    a single component at 0.01 %     -> DETECTED (including the smallest one)

In other words, the tolerance filters out numerical noise and nothing else. Structural
errors actually encountered in this repository — missing factor of 2, bad normalization,
inverted sign — manifest as discrepancies of 50% or 100%.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

__all__ = ["central_difference", "check_gradient", "GradientMismatch"]


class GradientMismatch(AssertionError):
    """Analytical gradient does not match finite difference."""


def central_difference(
    cost_of: Callable[[np.ndarray], float],
    params: np.ndarray,
    step: float = 1e-6,
) -> np.ndarray:
    """Centered finite difference of cost, parameter by parameter.

    Args:
        cost_of: function returning scalar cost for a parameter vector.
        params: evaluation point.
        step: central step size.

    Returns:
        Vector of numerical derivatives, same length as ``params``.
    """
    base = np.asarray(params, dtype=np.float64)
    numerical = np.zeros(base.size, dtype=np.float64)

    for i in range(base.size):
        forward = base.copy()
        forward[i] += step
        backward = base.copy()
        backward[i] -= step

        numerical[i] = (cost_of(forward) - cost_of(backward)) / (2.0 * step)

    return numerical


def check_gradient(
    cost_and_grad: Callable[[np.ndarray], tuple[float, np.ndarray]],
    params: np.ndarray,
    *,
    step: float = 1e-6,
    rtol: float = 1e-6,
    atol: float = 1e-12,
    label: str = "",
    blocks: list[tuple[int, int]] | None = None,
) -> np.ndarray:
    """Verifies that an analytical gradient is the derivative of the cost it accompanies.

    Args:
        cost_and_grad: function returning ``(cost, gradient)`` for a parameter
            vector. IT IS INDEED ITS OWN cost that serves as reference.
        params: evaluation point.
        step: step size for centered finite difference.
        rtol: relative tolerance.
        atol: threshold below which a component is considered zero.
        label: name displayed on failure.

    Returns:
        The verified analytical gradient.

    Raises:
        GradientMismatch: if a component diverges, or if the gradient is
            identically zero — in which case the test proves nothing.
    """
    base = np.asarray(params, dtype=np.float64)
    _, analytic = cost_and_grad(base)
    analytic = np.asarray(analytic, dtype=np.float64).ravel()[: base.size]

    numerical = central_difference(lambda p: cost_and_grad(p)[0], base, step)

    # An identically zero gradient would trivially coincide with a zero finite
    #difference: the test would pass without demonstrating anything. We disallow it.
    if np.max(np.abs(analytic)) < atol:
        raise GradientMismatch(
            f"{label}: analytical gradient is identically zero — "
            f"the evaluation point is degenerate, the test proves nothing."
        )

    # Standard metric in optimization: ||g_a - g_n||_inf / ||g_n||_inf, applied
    # BLOCK BY BLOCK.
    #
    # A component should not be compared against itself: the noise of a finite difference
    #is ABSOLUTE (of the order of eps.|cost|/h), so relative to a direction a hundred times
    #less sensitive than the dominant one it produces a huge relative error without the
    #gradient being incorrect.
    #
    # But it must not be compared to a family of parameters of a completely different scale
    #either. Measured on the objective spline: the gradient is ~6.7e+02 on n-nodes and
    # ~1e-04 on ln(k)-nodes — six orders of magnitude. Under a global norm, a 2% error
    #on the k block becomes invisible. This is exactly what made this harness blind
    #to a chain rule bug that was actually present.
    spans = blocks if blocks is not None else [(0, analytic.size)]

    for start_idx, stop_idx in spans:
        block_analytic = analytic[start_idx:stop_idx]
        block_numerical = numerical[start_idx:stop_idx]

        if block_analytic.size == 0:
            continue

        magnitude = max(float(np.max(np.abs(block_numerical))), atol)
        relative = np.abs(block_analytic - block_numerical) / magnitude

        worst = int(np.argmax(relative))
        if relative[worst] > rtol:
            details = [
                f"{label}: block [{start_idx}:{stop_idx}], component {start_idx + worst}",
                f"  analytical  = {block_analytic[worst]:.12e}",
                f"  finite diff = {block_numerical[worst]:.12e}",
                f"  relative gap = {relative[worst]:.3e} > {rtol:.1e}",
                f"  analytical block : {np.array2string(block_analytic, precision=8)}",
                f"  finite diff block : {np.array2string(block_numerical, precision=8)}",
            ]
            raise GradientMismatch(chr(10).join(details))

    return analytic


def non_uniform_weights(count: int, lo: float = 0.4, hi: float = 3.0) -> np.ndarray:
    """Deliberately non-uniform weights.

    With all weights equal, normalization by the number of points and normalization
    by the sum of weights differ only by a constant factor: the error becomes
    invisible. These weights reveal it.
    """
    return np.linspace(lo, hi, count, dtype=np.float64)

