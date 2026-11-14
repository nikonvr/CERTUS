"""Spread of a design's RMSE under random thickness errors.

``rmse_band``, for DESIGN's RMSE-versus-layers plot: each draw perturbs every layer by a Gaussian error whose
two-sigma value is ``rel_2sigma`` of its thickness plus ``abs_2sigma_nm`` (by default 0.1 % + 0.2 nm, owner's request
of 2026-10-23), evaluates the cost, and the band is two standard deviations of the RMSE over the draws. The draws are
seeded: the same design gives the same band.

``spectral_monte_carlo``, for DESIGN's spectral Monte Carlo button (2026-10-27): absolute, relative and
optical-thickness errors, with the mean, sqrt(E[MSE]), percentile, CVaR and yield of the RMSE.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from certus.core.certus_design_cost_context import DesignCostContext, prepare_design_cost_context


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


@dataclass(frozen=True)
class SpectralMonteCarlo:
    """RMSE of a design under random thickness errors: nominal, mean, sqrt(E[MSE]), 95th percentile, CVaR95, yield."""

    nominal: float
    mean: float
    rms: float
    p95: float
    cvar95: float
    yield_fraction: float | None
    draws: int
    samples: np.ndarray


def spectral_monte_carlo(
    cost: Callable[[np.ndarray], float],
    ep: np.ndarray,
    *,
    n_real: np.ndarray | None = None,
    sigma_abs_nm: float = 0.0,
    sigma_rel: float = 0.0,
    sigma_ot_nm: float = 0.0,
    draws: int = 1000,
    seed: int = 0,
    rmse_threshold: float | None = None,
    progress: Callable[[int, int], None] | None = None,
    stop: Callable[[], bool] | None = None,
) -> SpectralMonteCarlo:
    """Monte Carlo of the RMSE of ``ep`` (nm) for the mean-squared-error function ``cost``.

    Each layer i gets the independent Gaussian error sigma_abs_nm * z1 + sigma_rel * ep_i * z2 + sigma_ot_nm / n_i * z3:
    absolute and relative errors in physical thickness, and an absolute error in optical thickness (``n_real``: real
    index of each layer, required when ``sigma_ot_nm`` > 0). The draws of layer i come from the generator seeded by
    (seed, i), row k for draw k: the same layer gets the same draws whatever the stack around it. A thickness below
    zero is set to zero (the layer is absent). ``rmse_threshold`` gives the yield, the share of draws at or below it.
    CVaR95 is the mean of the worst 5 % of the draws (Rockafellar & Uryasev, J. Risk 2, 21, 2000).
    """
    ep = np.asarray(ep, dtype=np.float64)
    if sigma_ot_nm > 0.0 and (n_real is None or len(n_real) != ep.size):
        raise ValueError("sigma_ot_nm > 0 needs the real index of every layer")
    inv_n = 1.0 / np.asarray(n_real, dtype=np.float64) if sigma_ot_nm > 0.0 else np.zeros(ep.size)
    z = np.stack([np.random.default_rng((seed, i)).standard_normal((draws, 3)) for i in range(ep.size)], axis=1)
    errors = sigma_abs_nm * z[:, :, 0] + sigma_rel * ep * z[:, :, 1] + sigma_ot_nm * inv_n * z[:, :, 2]
    values = np.empty(draws, dtype=np.float64)
    done = 0
    for k in range(draws):
        if stop is not None and stop():
            break
        values[k] = np.sqrt(max(float(cost(np.maximum(ep + errors[k], 0.0))), 0.0))
        done = k + 1
        if progress is not None:
            progress(done, draws)
    values = values[:done]
    if done == 0:
        raise ValueError("no Monte Carlo draw was evaluated")
    worst = np.sort(values)[::-1][: max(1, round(0.05 * done))]
    return SpectralMonteCarlo(
        nominal=float(np.sqrt(max(float(cost(ep)), 0.0))),
        mean=float(values.mean()),
        rms=float(np.sqrt(np.mean(values ** 2))),
        p95=float(np.percentile(values, 95)),
        cvar95=float(worst.mean()),
        yield_fraction=None if rmse_threshold is None else float(np.mean(values <= rmse_threshold)),
        draws=done,
        samples=values,
    )


def second_order_robust_rmse(
    residual: Callable[[np.ndarray], np.ndarray],
    ep: np.ndarray,
    alpha: np.ndarray,
    *,
    step_nm: float = 1e-3,
) -> tuple[float, float]:
    """Nominal RMSE and Gauss-Newton estimate of sqrt(E[MSE]) under independent zero-mean errors of standard deviation
    ``alpha`` (nm, one per layer): E[MSE] ~ |r|^2 + sum_i alpha_i^2 |dr/dd_i|^2.

    This is the composite merit function of Tikhonravov et al., Proc. SPIE 4829, 1061 (2003), Eq. (5), with its weights
    equal to the error standard deviations. The first-order cross term and the off-diagonal terms vanish in
    expectation. The diagonal residual-curvature term of the full second-order expansion is omitted; this
    approximation is most useful near a small-residual solution.
    ``residual(ep)`` returns the weighted residual vector whose squared norm is the MSE; its derivatives are central
    differences of step ``step_nm``.
    """
    ep = np.asarray(ep, dtype=np.float64)
    alpha = np.asarray(alpha, dtype=np.float64)
    r0 = np.asarray(residual(ep), dtype=np.float64)
    penalty = 0.0
    for i in range(ep.size):
        if alpha[i] == 0.0:
            continue
        e = np.zeros(ep.size)
        e[i] = step_nm
        d_r = (np.asarray(residual(ep + e)) - np.asarray(residual(np.maximum(ep - e, 0.0)))) / (2.0 * step_nm)
        penalty += alpha[i] ** 2 * float(d_r @ d_r)
    mse = float(r0 @ r0)
    return float(np.sqrt(mse)), float(np.sqrt(mse + penalty))


def error_alpha(ep: np.ndarray, n_real: np.ndarray | None, sigma_abs_nm: float, sigma_rel: float,
                sigma_ot_nm: float) -> np.ndarray:
    """Standard deviation (nm) of the physical-thickness error of each layer for the error model of
    ``spectral_monte_carlo``."""
    ep = np.asarray(ep, dtype=np.float64)
    ot = sigma_ot_nm / np.asarray(n_real, dtype=np.float64) if sigma_ot_nm > 0.0 else np.zeros(ep.size)
    return np.sqrt(sigma_abs_nm ** 2 + (sigma_rel * ep) ** 2 + ot ** 2)


def design_residual_function(mats: dict, stack: list, wls: np.ndarray, tgts: list) -> Callable[[np.ndarray], np.ndarray]:
    """Weighted residual vector sqrt(w_j / sum w) (T_j - target_j) of ``design_cost_function``: its squared norm is that
    cost (front face, normal incidence, CERTUS kernel)."""
    return design_residual_from_context(prepare_design_cost_context(mats, stack, wls, tgts, cast_materials=True))


def design_residual_from_context(context: DesignCostContext) -> Callable[[np.ndarray], np.ndarray]:
    """Evaluate the front-face residual using already prepared optical inputs."""
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside

    tgt_vals, tgt_weights = context.normal_targets()

    def residual(ep: np.ndarray) -> np.ndarray:
        _r, t = calculate_RT_no_backside(
            np.ascontiguousarray(ep, dtype=np.float64), context.n_front, context.n_sub, context.wls,
        )
        valid = (tgt_weights > 0) & np.isfinite(t) & np.isfinite(tgt_vals)
        w = np.where(valid, tgt_weights, 0.0)
        return np.sqrt(w / max(float(w.sum()), 1e-300)) * np.where(valid, t - tgt_vals, 0.0)

    return residual


def design_cost_function(mats: dict, stack: list, wls: np.ndarray, tgts: list) -> Callable[[np.ndarray], float]:
    """Mean-squared error of T for a front stack at normal incidence, with the cost kernel of DESIGN.

    Front face only (no back side), as the RMSE of the window for a design without back coating.
    """
    from certus.physics.gradient_utils import cost_numba_fast

    context = prepare_design_cost_context(mats, stack, wls, tgts, cast_materials=True)
    tgt_vals, tgt_weights = context.normal_targets()

    def cost(ep: np.ndarray) -> float:
        return float(cost_numba_fast(
            np.ascontiguousarray(ep, dtype=np.float64), context.n_front, context.n_sub, context.wls,
            tgt_vals, tgt_weights, 0.0, context.has_back_calc, context.n_back, context.d_back,
        ))

    return cost
