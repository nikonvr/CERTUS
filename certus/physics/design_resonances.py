"""Optional hidden-resonance analysis and refinement for lossless normal-incidence T targets.

Complex wavelengths are diagnostic only. The canonical characteristic matrix and
amplitude helper supply the denominator; real residuals and analytic thickness
Jacobians come from the existing DESIGN kernel. Layers start at the substrate.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numba import njit
from scipy.optimize import brentq, least_squares, minimize_scalar

from certus.physics.certus_opt_tmm import reflection_amplitudes
from certus.physics.certus_tmm_oblique import oblique_front_char_matrix_single
from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel


@dataclass(frozen=True)
class TransmissionBand:
    """One constant target interval with its uniform nominal sampling step, in nm."""

    lower_nm: float
    upper_nm: float
    target: float
    step_nm: float = 1.0

    def __post_init__(self) -> None:
        values = np.array([self.lower_nm, self.upper_nm, self.target, self.step_nm])
        if not np.isfinite(values).all() or not 0 < self.lower_nm < self.upper_nm or self.step_nm <= 0:
            raise ValueError("Target bands require positive finite wavelength bounds and sampling steps.")
        intervals = (self.upper_nm - self.lower_nm) / self.step_nm
        if intervals < 4 or not np.isclose(intervals, round(intervals), rtol=0, atol=1e-7):
            raise ValueError("Each target band needs at least five uniformly spaced nominal wavelengths.")
        if not 0 <= self.target <= 1:
            raise ValueError("Transmission targets must be fractions between zero and one.")


@dataclass(frozen=True)
class TransmissionProblem:
    """Air / constant lossless indices / real substrate, without a rear surface."""

    indices: np.ndarray
    substrate_index: float
    bands: tuple[TransmissionBand, ...]

    def __post_init__(self) -> None:
        indices = np.array(self.indices, dtype=np.complex128, copy=True)
        if indices.ndim != 1 or not len(indices) or not np.isfinite(indices).all() or np.any(indices.real <= 0):
            raise ValueError("Layer indices must be a nonempty finite positive one-dimensional array.")
        if np.any(indices.imag != 0):
            raise ValueError("The resonance treatment currently requires constant lossless layer indices.")
        if not np.isfinite(self.substrate_index) or self.substrate_index <= 0:
            raise ValueError("The substrate index must be positive, real and finite.")
        if not self.bands:
            raise ValueError("At least one constant transmission target band is required.")
        ordered = sorted(self.bands, key=lambda band: band.lower_nm)
        if any(a.upper_nm >= b.lower_nm for a, b in pairwise(ordered)):
            raise ValueError("Target bands must not overlap or share an endpoint.")
        if not np.allclose([b.step_nm for b in self.bands], self.bands[0].step_nm, rtol=0, atol=1e-12):
            raise ValueError("The initial resonance implementation requires a common uniform sampling step.")
        indices.setflags(write=False)
        object.__setattr__(self, "indices", indices)
        object.__setattr__(self, "bands", tuple(self.bands))

    def grid(self) -> tuple[np.ndarray, np.ndarray]:
        """The nominal wavelengths and targets, retaining the caller's band order."""
        wl = [np.linspace(b.lower_nm, b.upper_nm, round((b.upper_nm - b.lower_nm) / b.step_nm) + 1)
              for b in self.bands]
        return np.concatenate(wl), np.concatenate([np.full(len(w), b.target)
                                                  for w, b in zip(wl, self.bands, strict=True)])


@dataclass(frozen=True)
class ResonanceSettings:
    """Explicit optional-treatment settings; no ordinary DESIGN call enables them."""

    rounds: int = 40
    burst: int = 30
    gamma_nm: float | None = None
    height_threshold: float = 1e-3
    max_width_nm: float = 0.5
    count_step_nm: float = 0.02
    max_ot_nm: float | None = None

    def __post_init__(self) -> None:
        if self.rounds < 0 or self.burst < 1:
            raise ValueError("Refinement rounds must be nonnegative and the burst limit positive.")
        positive = [self.max_width_nm, self.count_step_nm]
        positive += [v for v in (self.gamma_nm, self.max_ot_nm) if v is not None]
        if not np.isfinite(positive).all() or min(positive) <= 0:
            raise ValueError("Widths, count steps and optional bounds must be positive and finite.")
        if not np.isfinite(self.height_threshold) or not 0 <= self.height_threshold <= 1:
            raise ValueError("The peak-height threshold must be a fraction between zero and one.")


@dataclass(frozen=True)
class Resonance:
    """A localized pole and, where assessed, its real transmission-error maximum."""

    sigma: complex
    wavelength_nm: float
    width_nm: float
    band_index: int
    peak_wavelength_nm: float | None = None
    height: float | None = None


@dataclass(frozen=True)
class PoleCount:
    """Localization and two-resolution contour count in the same wavelength rectangle."""

    band_index: int
    located: int
    counted: int


@dataclass(frozen=True)
class ResonanceAnalysis:
    """Dimensionless nominal/charged RMS scores; the latter retains normalization 1/J."""

    nominal_mf: float
    charged_mf: float
    resonances: tuple[Resonance, ...]
    charged_peaks: tuple[Resonance, ...]
    counts: tuple[PoleCount, ...]


@dataclass(frozen=True)
class ResonanceRefinement:
    """A fixed-layer refinement selected by charged score among admissible rounds."""

    thicknesses: np.ndarray
    initial: ResonanceAnalysis
    final: ResonanceAnalysis
    selected_round: int
    history: tuple[ResonanceAnalysis, ...]
    cancelled: bool = False
    round_thicknesses: tuple[np.ndarray, ...] = ()


class _Cancelled(Exception):
    """Cooperative cancellation without applying a partly evaluated trial."""


class _NoErrorMaximum(RuntimeError):
    """A physical resonance need not be an unwanted maximum of the target error."""


@njit(cache=True, fastmath=False, nogil=True)
def _denominator_kernel(indices: np.ndarray, d: np.ndarray, wavelengths: np.ndarray, ns: float) -> np.ndarray:
    result = np.empty(len(wavelengths), dtype=np.complex128)
    for i in range(len(wavelengths)):
        m00, m01, m10, m11 = oblique_front_char_matrix_single(wavelengths[i], indices, d, 0., 1., True)
        result[i] = reflection_amplitudes(1. + 0j, m00 + m01 * ns, m10 + m11 * ns)[0]
    return result


def _thicknesses(problem: TransmissionProblem, d: np.ndarray) -> np.ndarray:
    values = np.array(d, dtype=np.float64, copy=True)
    if values.shape != problem.indices.shape or not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Positive finite thicknesses must match the layer indices.")
    return values


def transmission_denominator(problem: TransmissionProblem, d: np.ndarray, wavelengths: np.ndarray) -> np.ndarray:
    """D = eta0 B + C at real or complex wavelengths, from the canonical TMM."""
    values = np.atleast_1d(np.asarray(wavelengths, dtype=np.complex128))
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values.real <= 0):
        raise ValueError("Diagnostic wavelengths need positive finite real parts.")
    return _denominator_kernel(problem.indices, _thicknesses(problem, d), values, problem.substrate_index)


def _res_jac(problem: TransmissionProblem, d: np.ndarray, wl: np.ndarray, target: np.ndarray,
             variable: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = np.ascontiguousarray(np.tile(problem.indices.real, (len(wl), 1)))
    r, jac, _cost = _res_jac_lossless_normal_kernel(
        d, n, 1. / n, np.full(len(wl), problem.substrate_index), 2 * np.pi / wl, False,
        np.zeros(len(wl)), np.ones(len(wl)), target, np.ones(len(wl)), variable)
    return r, jac


def _newton(problem: TransmissionProblem, d: np.ndarray, start: complex) -> complex | None:
    sigma = complex(start)
    for _ in range(50):
        if not np.isfinite(sigma) or sigma.real <= 1e-10:
            return None
        h = 1e-10
        y = transmission_denominator(problem, d, 1. / np.array([sigma, sigma + h, sigma - h]))
        derivative = (y[1] - y[2]) / (2 * h)
        if not np.isfinite(y).all() or derivative == 0:
            return None
        change = y[0] / derivative
        sigma -= change
        if abs(change) < 1e-15:
            return complex(sigma)
    return None


def _locate(problem: TransmissionProblem, d: np.ndarray, gamma: float) -> tuple[Resonance, ...]:
    found: list[Resonance] = []
    for band_index, band in enumerate(problem.bands):
        w = np.arange(band.lower_nm, band.upper_nm + band.step_nm / 2, band.step_nm)
        phase = np.unwrap(-np.angle(transmission_denominator(problem, d, w + 1j * gamma)))
        derivative = np.gradient(phase, w)
        baseline = np.array([np.median(derivative[max(0, k - 40):k + 41]) for k in range(len(w))])
        excess = np.concatenate(([-np.inf], derivative - baseline, [-np.inf]))
        starts = np.flatnonzero((excess[1:-1] > excess[:-2]) & (excess[1:-1] >= excess[2:])
                               & (excess[1:-1] > 0.25 / gamma))
        for k in starts:
            for offset in np.arange(-2.5, 2.51, 0.25) * gamma:
                pole = _newton(problem, d, 1. / (w[k] + offset))
                if pole is None or pole.real <= 0 or pole.imag <= 0:
                    continue
                lam, width = 1. / pole.real, 2 * pole.imag / pole.real ** 2
                if (band.lower_nm <= lam <= band.upper_nm and abs(lam - w[k]) < 3 * gamma
                        and width < 10 * gamma and all(abs(lam - p.wavelength_nm) > 1e-6 for p in found)):
                    found.append(Resonance(pole, float(lam), float(width), band_index))
    return tuple(found)


def _peak_top(problem: TransmissionProblem, d: np.ndarray, pole: Resonance,
              restrict_band: bool = True) -> tuple[float, float]:
    band = problem.bands[pole.band_index]
    center, width = 1. / pole.sigma.real, 2 * pole.sigma.imag / pole.sigma.real ** 2
    if width <= 0 or not np.isfinite(width):
        raise RuntimeError("The tracked pole no longer describes a passive resonance.")
    variable = np.arange(len(d), dtype=np.int64)

    def error(wl: np.ndarray) -> np.ndarray:
        return np.abs(_res_jac(problem, d, wl, np.full(len(wl), band.target), variable)[0])

    def slope(wl: np.ndarray) -> np.ndarray:
        # With constant indices, T depends on d/lambda: lambda*T_lambda +
        # sum(d_i*T_di) = 0. All layers contribute, including fixed ones.
        residual, jac = _res_jac(problem, d, wl, np.full(len(wl), band.target), variable)
        return np.sign(residual) * (-(jac @ d) / wl)

    lam, h = center, width / 50
    stationary = False
    for _ in range(12):
        derivative = slope(np.array([lam - h, lam, lam + h]))
        first, second = derivative[1], (derivative[2] - derivative[0]) / (2 * h)
        if second >= 0 or not np.isfinite(second):
            break
        step = float(np.clip(-first / second, -width / 2, width / 2))
        lam += step
        if abs(step) < max(1e-12, width * 1e-11):
            stationary = True
            break
    if not stationary:
        lo = max(-2., (band.lower_nm - center) / width) if restrict_band else -2.
        hi = min(2., (band.upper_nm - center) / width) if restrict_band else 2.
        if lo >= hi:
            raise RuntimeError("The tracked resonance has left its target band.")
        sol = minimize_scalar(lambda u: -float(error(np.array([center + width * u]))[0]),
                              bounds=(lo, hi), method="bounded", options={"xatol": 1e-10})
        lam = center + width * sol.x
        if not sol.success or min(sol.x - lo, hi - sol.x) < 1e-7:
            raise _NoErrorMaximum("No isolated interior error maximum was resolved near the tracked pole.")
    left, right = lam - h, lam + h
    if restrict_band:
        left, right = max(left, band.lower_nm), min(right, band.upper_nm)
    if left < right:
        derivatives = slope(np.array([left, right]))
        if derivatives[0] > 0 > derivatives[1]:
            lam = brentq(lambda x: float(slope(np.array([x]))[0]), left, right,
                         xtol=1e-12, rtol=4 * np.finfo(float).eps)
        else:
            raise _NoErrorMaximum("An interior stationary error maximum could not be bracketed.")
    if restrict_band and not band.lower_nm < lam < band.upper_nm:
        raise RuntimeError("The tracked maximum has left the interior of its target band.")
    return float(lam), float(error(np.array([lam]))[0])


def _phase_change(problem: TransmissionProblem, d: np.ndarray, z0: complex, z1: complex, step: float) -> float:
    t = np.linspace(0, 1, max(2, int(np.ceil(abs(z1 - z0) / step)) + 1))
    for _ in range(40):
        values = transmission_denominator(problem, d, z0 + (z1 - z0) * t)
        if not np.isfinite(values).all() or np.any(np.abs(values) < 1e-280):
            raise RuntimeError("A pole-count contour approaches a numerical zero or overflow.")
        increments = np.angle(values[1:] / values[:-1])
        big = np.abs(increments) > np.pi / 4
        if not big.any():
            return float(increments.sum())
        if len(t) > 200000:
            break
        t = np.sort(np.concatenate((t, (t[:-1][big] + t[1:][big]) / 2)))
    raise RuntimeError("The phase could not be resolved on the pole-count contour.")


def _count(problem: TransmissionProblem, d: np.ndarray, band: TransmissionBand,
           gamma: float, delta: float, step: float) -> int:
    contour = [band.lower_nm - 1j * delta, band.upper_nm - 1j * delta,
               band.upper_nm + 1j * gamma, band.lower_nm + 1j * gamma, band.lower_nm - 1j * delta]
    change = sum(_phase_change(problem, d, a, b, h) for a, b, h in
                 zip(contour[:-1], contour[1:], (step, step, 10 * step, step), strict=True)) / (2 * np.pi)
    if abs(change - round(change)) > 1e-6:
        raise RuntimeError("The contour count is not numerically integral.")
    return round(change)


def analyze_resonances(problem: TransmissionProblem, thicknesses: np.ndarray, *,
                       settings: ResonanceSettings | None = None, check_count: bool = True) -> ResonanceAnalysis:
    """Locate poles, assess real maxima and optionally verify the complete strip before height filtering."""
    settings = settings or ResonanceSettings()
    d = _thicknesses(problem, thicknesses)
    gamma = settings.gamma_nm or problem.bands[0].step_nm
    poles = _locate(problem, d, gamma)
    charged: list[Resonance] = []
    for pole in poles:
        if pole.width_nm < settings.max_width_nm:
            try:
                lam, height = _peak_top(problem, d, pole)
            except _NoErrorMaximum:
                continue
            if height > settings.height_threshold:
                charged.append(Resonance(pole.sigma, pole.wavelength_nm, pole.width_nm, pole.band_index, lam, height))
    counts: list[PoleCount] = []
    if check_count:
        delta = settings.max_width_nm / 2
        for i, band in enumerate(problem.bands):
            located = sum(band.lower_nm < (1 / p.sigma).real < band.upper_nm and -delta < (1 / p.sigma).imag < 0
                          for p in poles)
            n1 = _count(problem, d, band, gamma, delta, settings.count_step_nm)
            n2 = _count(problem, d, band, gamma, delta, settings.count_step_nm / 2)
            if n1 != n2 or n1 != located:
                raise RuntimeError(f"Pole audit failed in {band.lower_nm:g}-{band.upper_nm:g} nm: "
                                   f"{located} located, {n1}/{n2} counted. Design unchanged.")
            counts.append(PoleCount(i, int(located), n1))
    wl, target = problem.grid()
    r = _res_jac(problem, d, wl, target, np.empty(0, dtype=np.int64))[0]
    mse = float(r @ r / len(wl))
    extra = sum(float(p.height) ** 2 for p in charged)
    return ResonanceAnalysis(float(np.sqrt(mse)), float(np.sqrt(mse + extra / len(wl))),
                             poles, tuple(charged), tuple(counts))


def refine_resonances(problem: TransmissionProblem, thicknesses: np.ndarray, *,
                      settings: ResonanceSettings | None = None, variable_indices: np.ndarray | None = None,
                      lower_bounds: np.ndarray | None = None, upper_bounds: np.ndarray | None = None,
                      progress: Callable[[int, ResonanceAnalysis], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> ResonanceRefinement:
    """Explicit post-refinement; retain the lowest charged objective within the OT budget.

    Fixed layers and individual bounds are preserved. The OT bound filters retained
    rounds; it does not constrain the intermediate trajectory of least_squares.
    Cancellation returns the original state and never applies a partial trial.
    """
    settings = settings or ResonanceSettings()
    original = _thicknesses(problem, thicknesses)
    d = original.copy()
    variable = (np.arange(len(d), dtype=np.int64) if variable_indices is None
                else np.asarray(variable_indices, dtype=np.int64))
    if variable.ndim != 1 or len(np.unique(variable)) != len(variable) or np.any((variable < 0) | (variable >= len(d))):
        raise ValueError("Variable-layer indices must be unique valid layer positions.")
    lo = np.full(len(d), 0.1) if lower_bounds is None else np.asarray(lower_bounds, dtype=float)
    hi = np.full(len(d), np.inf) if upper_bounds is None else np.asarray(upper_bounds, dtype=float)
    if (lo.shape != d.shape or hi.shape != d.shape or not np.isfinite(lo).all() or np.any(np.isnan(hi))
            or np.any(lo <= 0) or np.any(lo >= hi) or np.any(d < lo) or np.any(d > hi)):
        raise ValueError("Initial thicknesses must satisfy positive individual refinement bounds.")

    def within_ot(values: np.ndarray) -> bool:
        return settings.max_ot_nm is None or float(values @ problem.indices.real) <= settings.max_ot_nm

    if not within_ot(d):
        raise ValueError("The initial design exceeds the optical-thickness budget.")
    initial = analyze_resonances(problem, d, settings=settings)
    current, best, best_d, best_round = initial, initial, d.copy(), 0
    history = [initial]
    states = [d.copy()]
    wl, target = problem.grid()
    norm = 1. / np.sqrt(len(wl))
    try:
        for rnd in range(settings.rounds + 1):
            if cancelled is not None and cancelled():
                raise _Cancelled
            if progress is not None:
                progress(rnd, current)
            if rnd == settings.rounds or not len(variable):
                break
            anchors = current.charged_peaks
            memo: dict[bytes, tuple[np.ndarray, np.ndarray]] = {}

            def both(x: np.ndarray, anchors: tuple[Resonance, ...] = anchors,
                     memo: dict[bytes, tuple[np.ndarray, np.ndarray]] = memo) -> tuple[np.ndarray, np.ndarray]:
                if cancelled is not None and cancelled():
                    raise _Cancelled
                key = x.tobytes()
                if key not in memo:
                    memo.clear()
                    full = d.copy()
                    full[variable] = x
                    r, j = _res_jac(problem, full, wl, target, variable)
                    if anchors:
                        points, targets = [], []
                        for anchor in anchors:
                            sigma = _newton(problem, full, anchor.sigma)
                            if sigma is None:
                                raise RuntimeError("A resonance could not be followed during refinement.")
                            moved = Resonance(sigma, float(1 / sigma.real),
                                              float(2 * sigma.imag / sigma.real ** 2), anchor.band_index)
                            # Follow the pole throughout the burst: a fixed detection
                            # window must not reject a moving maximum. Its anchor's
                            # constant target is retained until the next detection.
                            points.append(_peak_top(problem, full, moved, restrict_band=False)[0])
                            targets.append(problem.bands[anchor.band_index].target)
                        rp, jp = _res_jac(problem, full, np.asarray(points), np.asarray(targets), variable)
                        r, j = np.concatenate((r, rp)), np.vstack((j, jp))
                    memo[key] = norm * r, norm * j
                return memo[key]

            sol = least_squares(lambda x: both(x)[0], d[variable], jac=lambda x: both(x)[1],
                                bounds=(lo[variable], hi[variable]), method="trf", x_scale="jac",
                                ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=settings.burst)
            d[variable] = sol.x
            current = analyze_resonances(problem, d, settings=settings, check_count=False)
            history.append(current)
            states.append(d.copy())
            if within_ot(d) and current.charged_mf < best.charged_mf:
                best, best_d, best_round = current, d.copy(), rnd + 1
    except _Cancelled:
        return ResonanceRefinement(original, initial, initial, 0, tuple(history), True, tuple(states))
    final = analyze_resonances(problem, best_d, settings=settings)
    return ResonanceRefinement(best_d, initial, final, best_round, tuple(history), round_thicknesses=tuple(states))
