"""Spread of a design's RMSE under random thickness errors, for DESIGN's RMSE-versus-layers plot.

Each draw perturbs every layer by a Gaussian error whose two-sigma value is ``rel_2sigma`` of its
thickness plus ``abs_2sigma_nm`` (by default 0.1 % + 0.2 nm, owner's request of 2026-10-23), evaluates
the cost, and the band is two standard deviations of the RMSE over the draws. The draws are seeded:
the same design gives the same band.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RmseBand:
    """Nominal RMSE of a design, mean RMSE of its perturbed copies, and two standard deviations of it."""

    nominal: float
    mean: float
    two_sigma: float
    draws: int


def rmse_band(
    cost: Callable[[np.ndarray], float],
    ep: np.ndarray,
    *,
    rel_2sigma: float = 0.001,
    abs_2sigma_nm: float = 0.2,
    draws: int = 200,
    seed: int = 0,
) -> RmseBand:
    """RMSE band of the design ``ep`` (nm) for the mean-squared-error function ``cost``.

    A perturbed thickness below zero is set to zero (the layer is absent).
    """
    ep = np.asarray(ep, dtype=np.float64)
    sigma = 0.5 * (rel_2sigma * np.abs(ep) + abs_2sigma_nm)
    rng = np.random.default_rng(seed)
    values = np.empty(draws, dtype=np.float64)
    for i in range(draws):
        perturbed = np.maximum(ep + sigma * rng.standard_normal(ep.size), 0.0)
        values[i] = np.sqrt(max(float(cost(perturbed)), 0.0))
    nominal = float(np.sqrt(max(float(cost(ep)), 0.0)))
    return RmseBand(nominal=nominal, mean=float(values.mean()), two_sigma=float(2.0 * values.std()), draws=draws)


def design_cost_function(mats: dict, stack: list, wls: np.ndarray, tgts: list) -> Callable[[np.ndarray], float]:
    """Mean-squared error of T for a front stack at normal incidence, with the cost kernel of DESIGN.

    Front face only (no back side), as the RMSE of the window for a design without back coating.
    """
    from certus.physics.gradient_utils import cost_numba_fast
    from certus_physics import prepare_targets_vectorized

    wls = np.ascontiguousarray(np.asarray(wls, dtype=np.float64))
    nk = {name: np.asarray(m.get_nk(wls), dtype=np.complex128) for name, m in mats.items()}
    sub_key = "Substrate" if "Substrate" in nk else next(k for k in nk if k.lower() == "substrate")
    n_sub = np.ascontiguousarray(nk[sub_key])
    n_layers_t = np.ascontiguousarray(np.array([nk[layer.mat] for layer in stack], dtype=np.complex128).T)
    tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
    no_back_n = np.zeros((len(wls), 0), dtype=np.complex128)
    no_back_d = np.zeros(0, dtype=np.float64)

    def cost(ep: np.ndarray) -> float:
        return float(cost_numba_fast(np.ascontiguousarray(ep, dtype=np.float64), n_layers_t, n_sub, wls,
                                     tgt_vals, tgt_weights, 0.0, False, no_back_n, no_back_d))

    return cost
