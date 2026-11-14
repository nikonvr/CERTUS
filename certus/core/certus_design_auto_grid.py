"""DESIGN's wavelength grid that finds its own number of points, and a first guess of the layer count and the TOT.

Optional (``auto_wavelength_grid``, off by default): a target gives only lambda_min and lambda_max, and the grid finds
its own points. The merit of DESIGN is a quadrature of int w (T - target)^2 d ln(lambda): a grid is good when its
quadrature error is small against the merit, and that is what ``refine_grid`` checks.

1. ``base_grid``: per band, uniform in wavenumber, ``oversampling * 4 * TOT * delta_sigma`` intervals. For a lossless
   stack of constant indices, 1/T is a trigonometric polynomial of the wavenumber whose highest frequency is twice the
   total optical thickness (TOT): ``4 * TOT * delta_sigma`` samples per band are its Nyquist count.
2. ``refine_grid``: for the design at hand, evaluates the squared residual at the middle (in ln lambda) of every
   interval, compares Simpson with the trapezoid on each interval, splits the intervals whose gap exceeds an equal share
   of the tolerance, and stops when the summed gaps are below ``rel_tol`` times the merit. Points are only added, never
   removed, never between two separate bands.

Measured on 2026-11-13 (independent sandbox TMM, three-cavity filter of 72 layers, 450-700 nm): a uniform grid of 328
points was off by 7.7 % on the merit, of 655 points by 3.4 %; ``refine_grid`` reached 0.8 % with 180 points.

Limit: a resonance narrower than the spacing, small at a node and at the next middle, is not seen. Its wavelengths can
be given as ``anchors`` (for instance the poles of ``certus.physics.design_resonances.analyze_resonances``).

``estimate_layers_and_tot``: the contrast estimate of the layer count and of the TOT of a two-material design, from the
reflectance the targets ask for: a quarter-wave stack gives R = tanh^2(N rho), rho = ln(nH / nL) / 2, over a relative
width (4 / pi) rho; one interface brings (4 / pi) rho^2 of int atanh sqrt(R) d ln(sigma) and costs a quarter wave. On the
50/50 beamsplitter 400-1200 nm (2.35 / 1.45) it gives 13 layers and 19.0 QWOT at 500 nm; the best known 13-layer design
has 19.02 QWOT. One case, not a law: a first guess, to show, not to impose. It is 0 for an antireflection (R = 0).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

#: Below this many intervals a band is never sampled, whatever its TOT.
MIN_INTERVALS = 8
#: Default oversampling of the Nyquist count in ``base_grid``.
OVERSAMPLING = 3.0
#: Default relative quadrature error of ``refine_grid``.
REL_TOL = 0.01
#: Highest reflectance the contrast estimate uses (atanh sqrt(R) diverges at 1).
R_CAP = 0.9999


class TargetLike(Protocol):
    lmin: float
    lmax: float
    tmin: float
    tmax: float
    w: float

    def valid(self) -> bool: ...


def merge_bands(bands: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """The bands (lmin, lmax), sorted, overlapping or touching ones merged."""
    merged: list[tuple[float, float]] = []
    for lo, hi in sorted((float(a), float(b)) for a, b in bands if float(b) >= float(a) > 0.0):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def nyquist_count(lmin: float, lmax: float, tot_nm: float) -> float:
    """4 * TOT * (1/lmin - 1/lmax): the number of independent samples a stack of total optical thickness ``tot_nm``
    can shape on the band."""
    return 4.0 * max(float(tot_nm), 0.0) * (1.0 / float(lmin) - 1.0 / float(lmax))


def base_grid(bands: Iterable[tuple[float, float]], tot_nm: float, *, oversampling: float = OVERSAMPLING,
              min_intervals: int = MIN_INTERVALS) -> np.ndarray:
    """Wavelengths (nm, sorted) of every merged band, uniform in wavenumber, ends included."""
    grids = []
    for lo, hi in merge_bands(bands):
        if hi <= lo:
            grids.append(np.array([lo]))
            continue
        intervals = max(int(min_intervals), int(np.ceil(oversampling * nyquist_count(lo, hi, tot_nm))))
        wavelengths = 1.0 / np.linspace(1.0 / hi, 1.0 / lo, intervals + 1)
        wavelengths[0], wavelengths[-1] = hi, lo
        grids.append(wavelengths)
    return np.unique(np.concatenate(grids)) if grids else np.zeros(0)


def target_values_and_weights(targets: Sequence[TargetLike], wls: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Target value and user weight at each wavelength (a later target wins where two overlap, as in
    ``prepare_targets_vectorized``); weight 0 outside every target."""
    wls = np.asarray(wls, dtype=np.float64)
    vals = np.zeros(wls.size)
    weights = np.zeros(wls.size)
    for t in targets:
        if not t.valid():
            continue
        mask = (wls >= t.lmin) & (wls <= t.lmax)
        slope = (t.tmax - t.tmin) / max(t.lmax - t.lmin, 1e-9)
        vals[mask] = t.tmin + slope * (wls[mask] - t.lmin)
        weights[mask] = t.w
    return vals, weights


@dataclass(frozen=True)
class GridRefinement:
    """The refined grid, and what ``refine_grid`` measured on it."""

    wavelengths: np.ndarray
    merit: float  # Simpson estimate of the mean squared residual over ln(lambda), last round
    error: float  # summed |Simpson - trapezoid| of the last round, same units
    rounds: int
    evaluations: int
    converged: bool


def refine_grid(bands: Iterable[tuple[float, float]], wavelengths: np.ndarray,
                squared_residual: Callable[[np.ndarray], np.ndarray], *, rel_tol: float = REL_TOL,
                abs_tol: float = 1e-14, max_rounds: int = 12, max_points: int = 20000,
                anchors: Iterable[float] | None = None) -> GridRefinement:
    """Add points to ``wavelengths`` where the quadrature of ``squared_residual`` (an array of w (T - target)^2 for an
    array of wavelengths) is not resolved, until its estimated error is below ``rel_tol * merit + abs_tol``.

    The points outside the bands are dropped; every band keeps its two ends. ``anchors`` (wavelengths inside the bands)
    are added first.
    """
    segments = merge_bands(bands)
    if not segments:
        return GridRefinement(np.zeros(0), 0.0, 0.0, 0, 0, True)
    lam = np.asarray(wavelengths, dtype=np.float64).ravel()
    extra = np.asarray(list(anchors) if anchors is not None else [], dtype=np.float64)
    pieces = []
    for lo, hi in segments:
        inside = np.concatenate((lam[(lam >= lo) & (lam <= hi)], extra[(extra >= lo) & (extra <= hi)], [lo, hi]))
        pieces.append(np.unique(inside))
    values = np.asarray(squared_residual(np.concatenate(pieces)), dtype=np.float64)
    evaluations = values.size
    split = np.cumsum([p.size for p in pieces])[:-1]
    f = list(np.split(values, split))
    merit = error = 0.0
    converged = False
    rounds = 0
    for rounds in range(max_rounds + 1):  # noqa: B007 - `rounds` is reported
        mids = [np.sqrt(p[:-1] * p[1:]) for p in pieces]
        fm_all = np.asarray(squared_residual(np.concatenate(mids)), dtype=np.float64) if sum(m.size for m in mids) else np.zeros(0)
        evaluations += fm_all.size
        fm = np.split(fm_all, np.cumsum([m.size for m in mids])[:-1])
        widths = [np.log(p[1:] / p[:-1]) for p in pieces]
        gaps = [h * np.abs(4.0 * m - 2.0 * a[:-1] - 2.0 * a[1:]) / 6.0 for h, m, a in zip(widths, fm, f, strict=True)]
        simpson = sum(float(np.sum(h * (a[:-1] + 4.0 * m + a[1:]) / 6.0)) for h, m, a in zip(widths, fm, f, strict=True))
        span = sum(float(np.sum(h)) for h in widths)
        if span <= 0.0:
            return GridRefinement(np.concatenate(pieces), 0.0, 0.0, rounds, evaluations, True)
        merit = simpson / span
        error = sum(float(np.sum(g)) for g in gaps) / span
        budget = rel_tol * merit + abs_tol
        points = sum(p.size for p in pieces)
        if error <= budget:
            converged = True
            break
        if rounds == max_rounds or points >= max_points:
            break
        n_intervals = points - len(pieces)
        share = budget * span / max(n_intervals, 1)
        flat = np.concatenate(gaps)
        chosen = flat > share
        room = max_points - points
        if np.count_nonzero(chosen) > room:
            chosen = np.zeros(flat.size, dtype=bool)
            chosen[np.argsort(flat)[::-1][:room]] = True
        offsets = np.cumsum([0, *(g.size for g in gaps)])
        for k in range(len(pieces)):
            pick = chosen[offsets[k]:offsets[k + 1]]
            if not np.any(pick):
                continue
            order = np.argsort(np.concatenate((pieces[k], mids[k][pick])), kind="stable")
            pieces[k] = np.concatenate((pieces[k], mids[k][pick]))[order]
            f[k] = np.concatenate((f[k], fm[k][pick]))[order]
    return GridRefinement(np.concatenate(pieces), merit, error, rounds, evaluations, converged)


@dataclass(frozen=True)
class LayerEstimate:
    """Contrast estimate of a two-material design: layer count, TOT (nm) and the Nyquist count of the bands."""

    layers: float
    tot_nm: float
    nyquist: float


def estimate_layers_and_tot(targets: Sequence[TargetLike], n_high: float, n_low: float,
                            points: int = 2001) -> LayerEstimate:
    """N0 = (pi / 4 rho^2) int atanh sqrt(R) d ln(sigma), TOT0 = (pi / 16 rho^2) int atanh sqrt(R) d lambda, with
    R = 1 - T of the targets (lossless) and rho = ln(n_high / n_low) / 2; ``nyquist`` is 4 * TOT0 * delta_sigma summed
    over the bands."""
    rho = 0.5 * abs(np.log(float(n_high) / float(n_low)))
    bands = merge_bands((t.lmin, t.lmax) for t in targets if t.valid())
    if rho <= 0.0 or not bands:
        return LayerEstimate(0.0, 0.0, 0.0)
    layers = tot = 0.0
    for lo, hi in bands:
        if hi <= lo:
            continue
        lam = np.linspace(lo, hi, points)
        vals, weights = target_values_and_weights(targets, lam)
        q = np.where(weights > 0.0, np.arctanh(np.sqrt(np.clip(1.0 - vals, 0.0, R_CAP))), 0.0)
        layers += float(np.trapezoid(q / lam, lam))
        tot += float(np.trapezoid(q, lam))
    layers *= np.pi / (4.0 * rho * rho)
    tot *= np.pi / (16.0 * rho * rho)
    return LayerEstimate(float(layers), float(tot), float(sum(nyquist_count(lo, hi, tot) for lo, hi in bands if hi > lo)))


def design_tot_nm(n_real: Sequence[float], thicknesses_nm: Sequence[float]) -> float:
    """Total optical thickness sum n_i d_i (nm)."""
    return float(np.dot(np.asarray(n_real, dtype=np.float64), np.asarray(thicknesses_nm, dtype=np.float64)))


def auto_grid_tot_nm(stack_tot_nm: float, max_total_qwot: Any, l0: float) -> float:
    """TOT that the base grid must resolve: the larger of the design's and of the ceiling of the global stage
    (``max_total_qwot`` quarter waves at ``l0``), when the file gives one."""
    ceiling = float(max_total_qwot) * float(l0) / 4.0 if max_total_qwot else 0.0
    return max(float(stack_tot_nm), ceiling)
