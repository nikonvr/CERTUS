"""No stop before the last extremum is declared (`arming`, D98), on request; the default keeps the stop at the level.

The kernel counts a turning point at the position of the extremum. A causal controller declares it only once the signal
has come back from it by the detection threshold h, and cannot stop before: a level nearer the last extremum than h is
crossed while the controller still waits. With `arming` the stop then falls where the extremum is declared, T_last -+ h,
the late stop of `scripts/probe_oms_sequentiel.py`. Measured on the nominal plans on 2026-10-10
(`scripts/probe_armement.py`): 22 plans of the judge of paix at 1x, 38 at 2x, the first at rank 23.

The oracle finds the extrema of the window on the independent TMM (tests/oracle/tmm_reference.py), refined by a bounded
minimisation; the kernel runs with its anchors at the extremum and its exact stop (D96, D97), so that the only
difference left between the two is the arming.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq, minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack

from certus.physics.certus_strat_growth import (
    CRASH_NOT_ARMED,
    CRASH_SENTINEL_UNIT,
    _armed_level,
    simulate_growth_kernel,
)
from certus.physics.certus_strat_readings import ARMING_LATE_STOP, ARMING_NEVER_STOPS

pytestmark = pytest.mark.kernels

N_SUB, N_H, N_L = 1.52, 2.35, 1.46
WL = 560.0
H = 8.3e-4  # 1.66 A, A = 5e-4
PREV = np.array([62.0, 95.0, 104.0, 97.0]) * np.array([1.01, 0.985, 1.02, 0.99])


def _t(thicknesses, j: int, d: float) -> float:
    """T of layers 0 .. j - 1 (thicknesses `thicknesses`) under layer j grown to the depth `d`."""
    return rt_stack(WL, [N_H if k % 2 == 0 else N_L for k in range(j + 1)], [*thicknesses[:j], d], 1.0, N_SUB)[1]


def _extrema(thicknesses, j: int, d_hi: float) -> list[float]:
    """T at the extrema of layer j inside (0, `d_hi`): bracketed every 0.5 nm, refined on the oracle."""
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
            found.append(_t(thicknesses, j, res.x))
    return found


def _oracle(nominal, i: int, j0: int, armed: bool) -> tuple[float, float, float]:
    """(stop, level, distance of the level from the last extremum) of layer i on the oracle, POEM on exact extrema."""
    ext_n = [v for j in range(j0, i) for v in _extrema(nominal, j, nominal[j])] + _extrema(nominal, i, nominal[i])
    ext_r = [v for j in range(j0, i) for v in _extrema(PREV, j, PREV[j])] + _extrema(PREV, i, nominal[i])
    fraction = (_t(nominal, i, nominal[i]) - ext_n[-2]) / (ext_n[-1] - ext_n[-2])
    level = ext_r[-2] + fraction * (ext_r[-1] - ext_r[-2])
    gap = abs(ext_r[-1] - level)
    if armed:
        direction = -1.0 if ext_r[-1] > ext_r[-2] else 1.0
        if (level - (ext_r[-1] + direction * H)) * direction < 0.0:
            level = ext_r[-1] + direction * H

    def g(d: float) -> float:
        return _t(PREV, i, d) - level

    for s in range(1, 400):  # the crossing nearest the nominal thickness, as `_invert_thickness_exact` returns it
        for lo, hi in ((nominal[i] + (s - 1) * 0.1, nominal[i] + s * 0.1), (nominal[i] - s * 0.1, nominal[i] - (s - 1) * 0.1)):
            if g(lo) * g(hi) <= 0.0:
                return brentq(g, lo, hi, xtol=1e-12), level, gap
    raise AssertionError("the oracle level is never crossed")


def _kernel(nominal, i: int, j0: int, *flags) -> float:
    return simulate_growth_kernel(
        nominal, i, PREV, WL, N_H + 0j, N_L + 0j, N_SUB + 0j, 2.5, 0.0, 2.0, 0, j0, 0.0, 0, 0, H, 1.0, 0.0, 0.0, True, 1,
        -1.0, -1.0, False, None, 0, 0.0, None, *flags,
    )[0]


# The layer being grown alone in its block, stopped 0.8 nm after its maximum: the level lies under the summit by less
# than the threshold. Then a block from layer 2 stopped 1.7 nm after a minimum of the layer being grown.
AFTER_A_MAXIMUM = (np.array([62.0, 95.0, 104.0, 97.0, 94.6]), 4, 4)
AFTER_A_MINIMUM = (np.array([62.0, 95.0, 104.0, 97.0, 36.0]), 4, 2)


@pytest.mark.parametrize("case", [AFTER_A_MAXIMUM, AFTER_A_MINIMUM], ids=["after a maximum", "after a minimum"])
def test_a_level_crossed_before_the_extremum_is_declared_stops_at_the_declaration(case) -> None:
    nominal, i, j0 = case
    stop, _, gap = _oracle(nominal, i, j0, armed=False)
    armed_stop, armed_level, _ = _oracle(nominal, i, j0, armed=True)
    assert gap < H  # the case is the one D98 is about
    assert abs(armed_stop - stop) > 0.1  # and the declaration comes late enough to matter

    assert _kernel(nominal, i, j0, True, True, False) == pytest.approx(stop, abs=1e-6)
    assert _kernel(nominal, i, j0, True, True, True) == pytest.approx(armed_stop, abs=1e-6)
    assert _t(PREV, i, armed_stop) == pytest.approx(armed_level, abs=1e-12)


def test_a_level_farther_than_the_threshold_is_not_touched() -> None:
    """Stopped near the extremum BEFORE the last one: the last is declared long before the level comes."""
    nominal, i, j0 = np.array([62.0, 95.0, 104.0, 97.0, 150.0]), 4, 4
    assert _oracle(nominal, i, j0, armed=False)[2] > H

    assert _kernel(nominal, i, j0, True, True, True) == _kernel(nominal, i, j0, True, True, False)


def test_without_the_flag_the_kernel_is_unchanged_bit_for_bit() -> None:
    nominal, i, j0 = AFTER_A_MAXIMUM

    assert _kernel(nominal, i, j0) == _kernel(nominal, i, j0, False, False, False)


@pytest.mark.parametrize(
    ("T_prev", "T_last", "level", "expected"),
    [
        (0.40, 0.90, 0.8995, 0.90 - H),  # after a maximum, under it by less than h: the declaration
        (0.40, 0.90, 0.80, 0.80),  # after a maximum, under it by more than h: the level
        (0.90, 0.40, 0.4005, 0.40 + H),  # after a minimum, above it by less than h: the declaration
        (0.90, 0.40, 0.50, 0.50),  # after a minimum, above it by more than h: the level
    ],
)
def test_the_armed_level_is_the_later_of_the_level_and_the_declaration(T_prev, T_last, level, expected) -> None:
    assert _armed_level(T_prev, T_last, H, level) == pytest.approx(expected, abs=1e-15)


@pytest.mark.parametrize("case", [AFTER_A_MAXIMUM, AFTER_A_MINIMUM], ids=["after a maximum", "after a minimum"])
def test_a_controller_that_waits_for_ever_never_ends_the_layer(case) -> None:
    """D98, decided 2026-10-12: the OMS waits for ever when the level is crossed before the extremum is declared (mode 2)."""
    nominal, i, j0 = case
    assert _oracle(nominal, i, j0, armed=False)[2] < H

    thickness = _kernel(nominal, i, j0, True, True, ARMING_NEVER_STOPS)

    assert thickness == pytest.approx(nominal[i] + CRASH_NOT_ARMED * CRASH_SENTINEL_UNIT)
    assert _kernel(nominal, i, j0, True, True, ARMING_LATE_STOP) == _kernel(nominal, i, j0, True, True, True)  # mode 1 is the late stop


def test_waiting_for_ever_does_not_touch_a_level_farther_than_the_threshold() -> None:
    nominal, i, j0 = np.array([62.0, 95.0, 104.0, 97.0, 150.0]), 4, 4

    assert _kernel(nominal, i, j0, True, True, ARMING_NEVER_STOPS) == _kernel(nominal, i, j0, True, True, False)
