"""POEM's anchors read at the extremum of their layer (`exact_anchors`, D96) give the oracle's POEM stop; the default
keeps the coarse samples.

On the coarse scan the kernel takes, as an anchor, the value of the sample at which its detector put the extremum: 16
samples per replayed layer, 64 over three thicknesses of the layer being grown, so the sample sits up to half a step from
the summit, by a different amount on the real and on the nominal signal as soon as their thicknesses differ. Measured on
2026-10-10 on the judge of paix, noise-free, upstream errors of 0.3 nm: the kernel's stop sat 0.055 nm RMS from the exact
POEM stop, 0.021 nm RMS of it from the parabolic inversion (D97), the rest from the anchors.

The oracle below finds every extremum of the window on the independent TMM (tests/oracle/tmm_reference.py), refined by a
bounded minimisation, takes the last two before the nominal stop on each signal, and solves the POEM level on the real
signal: the kernel, with both options, must land on that stop.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq, minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack

from certus.physics.certus_strat_growth import simulate_growth_kernel

pytestmark = pytest.mark.kernels

N_SUB, N_H, N_L = 1.52, 2.35, 1.46
WL = 560.0
HYSTERESIS = 8.3e-4


def _index(j: int) -> float:
    return N_H if j % 2 == 0 else N_L


def _t(thicknesses, j: int, d: float) -> float:
    """T of layers 0 .. j - 1 (thicknesses `thicknesses`) under layer j grown to the depth `d`."""
    return rt_stack(WL, [_index(k) for k in range(j + 1)], [*thicknesses[:j], d], 1.0, N_SUB)[1]


def _extrema(thicknesses, j: int, d_hi: float) -> list[tuple[float, float]]:
    """(depth, T) of the extrema of layer j inside (0, `d_hi`): bracketed every 0.5 nm, refined on the oracle."""
    grid = np.linspace(0.0, d_hi, int(d_hi / 0.5) + 2)
    vals = np.array([_t(thicknesses, j, d) for d in grid])
    found = []
    for k in range(1, len(grid) - 1):
        if (vals[k] - vals[k - 1]) * (vals[k + 1] - vals[k]) < 0.0:
            sign = 1.0 if vals[k] > vals[k - 1] else -1.0
            res = minimize_scalar(
                lambda d, s=sign: -s * _t(thicknesses, j, d), bounds=(grid[k - 1], grid[k + 1]), method="bounded",
                options={"xatol": 1e-11},
            )
            found.append((float(res.x), _t(thicknesses, j, res.x)))
    return found


def _anchors(thicknesses, j0: int, i: int, d_stop: float) -> tuple[list[int], float, float]:
    """The layers holding the last two extrema before the stop (window `j0` .. `i`), and their two values."""
    ext = [(j, v) for j in range(j0, i) for _, v in _extrema(thicknesses, j, thicknesses[j])]
    ext += [(i, v) for _, v in _extrema(thicknesses, i, d_stop)]
    return [ext[-2][0], ext[-1][0]], ext[-2][1], ext[-1][1]


def _oracle_stop(nominal, prev, i: int, j0: int, scale: float = 1.0, offset: float = 0.0, curv: float = 0.0):
    """The POEM stop of layer i on the oracle, read through the drift t + 4c t (1 - t), t = scale T + offset."""

    def read(T: float) -> float:
        t = scale * T + offset
        return t + 4.0 * curv * t * (1.0 - t)

    layers_n, prev_n, last_n = _anchors(nominal, j0, i, nominal[i])
    layers_r, prev_r, last_r = _anchors(prev, j0, i, nominal[i])
    fraction = (_t(nominal, i, nominal[i]) - prev_n) / (last_n - prev_n)
    level = read(prev_r) + fraction * (read(last_r) - read(prev_r))

    def g(d: float) -> float:
        return read(_t(prev, i, d)) - level

    # The crossing nearest the nominal thickness, as `_invert_thickness_exact` returns it.
    for s in range(1, 400):
        for lo, hi in ((nominal[i] + (s - 1) * 0.1, nominal[i] + s * 0.1), (nominal[i] - s * 0.1, nominal[i] - (s - 1) * 0.1)):
            if g(lo) * g(hi) <= 0.0:
                return brentq(g, lo, hi, xtol=1e-12), layers_n, layers_r
    raise AssertionError("the oracle level is never crossed")


def _kernel(nominal, prev, i: int, j0: int, *flags, scale=1.0, offset=0.0, curv=0.0, machine_dd=0.0, stop_noise=0.0):
    return simulate_growth_kernel(
        nominal, i, prev, WL, N_H + 0j, N_L + 0j, N_SUB + 0j, 2.5, stop_noise, 2.0, 0, j0, 0.0, 0, 0, HYSTERESIS,
        scale, offset, curv, True, 1, -1.0, -1.0, False, None, 0, machine_dd, None, *flags,
    )[0]


NOMINAL = np.array([62.0, 95.0, 104.0, 97.0, 150.0])
PREV = NOMINAL[:4] * np.array([1.01, 0.985, 1.02, 0.99])
# The layer being grown alone in its block: its two anchors are extrema of its own, swept on 64 samples.
CURRENT = (NOMINAL, PREV, 4, 4)
# A block from layer 2 and a thin layer 4: the anchors lie in the replayed layers, swept on 16 samples each, at the
# real thickness on one signal and the nominal one on the other.
HISTORY = (np.array([62.0, 95.0, 104.0, 97.0, 15.0]), PREV, 4, 2)


@pytest.mark.parametrize(("case", "anchor_layers"), [(CURRENT, [4, 4]), (HISTORY, [2, 3])], ids=["current", "history"])
def test_the_exact_anchors_give_the_oracles_poem_stop(case, anchor_layers) -> None:
    nominal, prev, i, j0 = case
    stop, layers_n, layers_r = _oracle_stop(nominal, prev, i, j0)
    assert layers_n == layers_r == anchor_layers  # the case exercises the branch it is named after

    exact = _kernel(nominal, prev, i, j0, True, True)
    sampled = _kernel(nominal, prev, i, j0, True, False)

    assert exact == pytest.approx(stop, abs=1e-6)
    assert abs(sampled - stop) > 1e-4  # the coarse samples miss it by a hundred tolerances: the test sees the option


@pytest.mark.parametrize("case", [CURRENT, HISTORY], ids=["current", "history"])
def test_the_real_anchors_go_through_the_instruments_distortion_exactly(case) -> None:
    """Gain, offset and curvature of the photometric drift: the extrema of the read signal are those of T, read through
    the drift; the stop is the oracle's to the bisection's precision, curvature included."""
    nominal, prev, i, j0 = case
    drift = {"scale": 1.03, "offset": -0.012, "curv": 0.02}
    stop, _, _ = _oracle_stop(nominal, prev, i, j0, **drift)

    assert _kernel(nominal, prev, i, j0, True, True, **drift) == pytest.approx(stop, abs=1e-6)


def test_a_level_between_the_coarse_sample_and_the_summit_is_reached() -> None:
    """The moved anchor replaces its sample in the signal: the reachability test, which reads the band the real signal
    spans, sees the summit the level was taken from. A level between the sample and the summit was declared unreachable,
    a crash the machine would not have: it reads the summit on its way."""
    nominal, prev, i, j0 = CURRENT
    (_, prev_n), (_, last_n) = _extrema(nominal, i, nominal[i])[-2:]
    (_, prev_r), (d_last, last_r) = _extrema(prev, i, nominal[i])[-2:]
    level = prev_r + (_t(nominal, i, nominal[i]) - prev_n) / (last_n - prev_n) * (last_r - prev_r)
    samples = 3.0 * nominal[i] * np.arange(64) / 63
    sample = max(_t(prev, i, d) for d in samples[np.abs(samples - d_last) < 3.0 * nominal[i] / 63])
    assert last_r - sample > 1e-4  # the summit, a maximum, lies above the samples around it
    target = 0.5 * (sample + last_r)

    got = _kernel(nominal, prev, i, j0, True, True, stop_noise=target - level)

    assert got < 1e5  # not the sentinel of an unreachable level
    assert _t(prev, i, got) == pytest.approx(target, abs=1e-9)


def test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit() -> None:
    nominal, prev, i, j0 = CURRENT

    assert _kernel(nominal, prev, i, j0, True) == _kernel(nominal, prev, i, j0, True, False)
    assert _kernel(nominal, prev, i, j0) == _kernel(nominal, prev, i, j0, False, False)


def test_the_machine_grid_ignores_the_flag() -> None:
    """The machine grid reads the exact T at every 0.125 nm: its anchors are already at the extremum."""
    nominal, prev, i, j0 = CURRENT

    assert _kernel(nominal, prev, i, j0, False, True, machine_dd=0.125) == _kernel(
        nominal, prev, i, j0, False, False, machine_dd=0.125
    )
