"""Adjoint of the monotone n reparametrization (``n_mono_band_nm``): d(cost)/d(xi) from d(cost)/d(physical n knots).

Used by ``SplinePWLObjective._compute_analytic_gradient`` when ``spline_mono_analytic_gradient`` is on (the default).
"""

from __future__ import annotations

import numpy as np

from certus.core.certus_core import N_MAX_LIMIT, N_MIN_LIMIT
from certus.spline.certus_index_spline_core import _mono_sigmoid, n_mono_knot_chains, n_mono_segment_flags


def decode_xi_n_vjp(
    xi_n: np.ndarray,
    chains: list[tuple[int, int]],
    n_min: float,
    n_max: float,
    g_n: np.ndarray,
) -> np.ndarray:
    """Vector-Jacobian product of ``decode_xi_n_to_physical_n``: d(cost)/d(xi) from d(cost)/d(n).

    Replays the forward recursion branch by branch (``_mono_sigmoid`` clamp at |xi| = 60, saturated span
    below 1e-14, final clip to [n_min, n_max]) and back-propagates along each chain, from its last knot to its first.
    """

    xi_n = np.asarray(xi_n, dtype=np.float64).ravel()
    g_n = np.asarray(g_n, dtype=np.float64).ravel()
    K = int(xi_n.size)
    lo, hi = float(n_min), float(n_max)
    span0 = hi - lo
    sigmoids = _mono_sigmoid(xi_n)
    dsig = np.where(np.abs(xi_n) <= 60.0, sigmoids * (1.0 - sigmoids), 0.0)

    dn_dxi = np.zeros(K, dtype=np.float64)
    dn_dprev = np.zeros(K, dtype=np.float64)
    n_raw = np.zeros(K, dtype=np.float64)

    for a, b in chains:
        n_raw[a] = lo + span0 * float(sigmoids[a])
        dn_dxi[a] = span0 * float(dsig[a])
        prev = float(n_raw[a])

        for idx in range(a + 1, b + 1):
            span = hi - prev

            if span < 1e-14:
                n_raw[idx] = prev
                dn_dprev[idx] = 1.0
            else:
                prev = prev + span * float(sigmoids[idx])
                n_raw[idx] = prev
                dn_dxi[idx] = span * float(dsig[idx])
                dn_dprev[idx] = 1.0 - float(sigmoids[idx])

    # The final clip only touches the output, not the recursion: a clipped knot passes no gradient.
    g_eff = np.where((n_raw >= lo) & (n_raw <= hi), g_n, 0.0)

    g_xi = np.zeros(K, dtype=np.float64)

    for a, b in chains:
        carry = 0.0

        for idx in range(b, a - 1, -1):
            adj = float(g_eff[idx]) + carry
            g_xi[idx] = adj * dn_dxi[idx]
            carry = adj * dn_dprev[idx]

    return g_xi


def x_slice_n_grad_to_x(
    x_n: np.ndarray,
    sigma_knots: np.ndarray,
    n_mono_band_nm: tuple[float, float] | None,
    g_n: np.ndarray,
) -> np.ndarray:
    """Map a gradient on physical n knots to the x slice (physical n or xi), adjoint of ``x_slice_n_to_physical_nodes``."""

    if n_mono_band_nm is None:
        return np.asarray(g_n, dtype=np.float64).ravel().copy()

    lam_lo, lam_hi = float(n_mono_band_nm[0]), float(n_mono_band_nm[1])

    seg = n_mono_segment_flags(sigma_knots, lam_lo, lam_hi)

    chains = n_mono_knot_chains(seg)

    return decode_xi_n_vjp(x_n, chains, float(N_MIN_LIMIT), float(N_MAX_LIMIT), g_n)
