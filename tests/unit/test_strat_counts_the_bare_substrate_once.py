"""The bare substrate is ONE turning point, on the machine grid too (`certus_strat_growth`).

dT/dd = 0 at d = 0, so the first layer leaves the substrate quadratically: at one reading every 0.125 nm the first
readings stay within the noise of the start for several nanometres. A hysteresis detector that does not know which way
the signal goes lets its running maximum move onto one of them, then declares it as a maximum -- on top of the start,
already counted as one. The nominal signal, noise-free, does not, and the kernel calls the difference a miscount crash.

Measured on 2026-10-10 on the judge of paix's winner with a smoothing window of 8 (which switches the machine grid
on), 300 runs: 7.7 %, 21.3 % and 36.0 % of runs crashed at layer 0 at the 0.5x, 1x and 2x noise levels, all by
miscount (`scripts/probe_oms_sequentiel.py` reproduces the machine reading by reading).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_growth import (
    CRASH_SENTINEL_MIN,
    _read_poem_anchors,
    detect_turning_points,
    simulate_growth_kernel,
)

pytestmark = pytest.mark.kernels

A = 5e-4  # reading noise amplitude of the configured machine, in T (ETAT section 3)


def test_a_reading_lifted_by_noise_next_to_a_falling_start_is_not_a_second_maximum() -> None:
    # The start (index 0) is a maximum; reading 1 sits above it by noise; the signal then falls to a minimum at 5.
    ts = np.array([1.0, 1.0004, 0.999, 0.99, 0.98, 0.97, 0.975, 0.985, 0.995])
    h = 0.005

    assert detect_turning_points(ts, len(ts), len(ts) - 1, True, h)[0] == 3  # direction unknown: counted twice
    assert detect_turning_points(ts, len(ts), len(ts) - 1, True, h, -1) == (2, 0, 5)  # the start and the minimum


def test_noise_that_lifts_a_reading_above_a_known_maximum_start_does_not_turn_the_detector() -> None:
    # The start reading came out low (a cold smoothing window leaves it unsmoothed): reading 1 rises above it by more
    # than the threshold. That is not a minimum at the start; turning on it let the next fall declare a second maximum.
    ts = np.array([1.0, 1.006, 1.004, 0.99, 0.98, 0.97, 0.975, 0.985, 0.995])

    assert detect_turning_points(ts, len(ts), len(ts) - 1, True, 0.005, -1) == (2, 0, 5)


def test_a_rising_start_is_a_minimum_and_the_detector_then_looks_for_the_maximum() -> None:
    ts = np.array([0.5, 0.4996, 0.501, 0.51, 0.52, 0.53, 0.525, 0.515, 0.505])

    assert detect_turning_points(ts, len(ts), len(ts) - 1, True, 0.005, 1) == (2, 0, 5)


def test_a_window_that_starts_below_a_maximum_does_not_count_its_noisy_start_as_a_minimum() -> None:
    """A block that starts just below a turning point: its first reading, pushed low by noise, sits more than the
    threshold under the coming maximum. Without the planned direction the start becomes a minimum, counted, and the
    count no longer matches the plan's -- 156 runs of 300 at layer 36 of bench plan 11 of the judge of paix at 2x noise.
    Knowing the signal rises there, the detector tracks the maximum and never counts the start."""
    ts = np.array([0.995, 1.0, 1.003, 1.004, 1.003, 0.99, 0.98, 0.975, 0.98, 0.99])

    assert detect_turning_points(ts, len(ts), 9, False, 0.005) == (3, 3, 7)  # a minimum at 0, the maximum, the minimum
    assert detect_turning_points(ts, len(ts), 9, False, 0.005, 1) == (2, 3, 7)  # the maximum and the minimum only


ANCHOR_NAMES = ("n_tp_real", "n_tp_nom", "margin_missed", "margin_fab", "T_prev_nom", "T_last_nom", "T_prev_real",
                "T_last_real", "poem_ok")


def _machine_grid_anchors(real, nominal, stop, hysteresis) -> dict:
    """`_read_poem_anchors` for layer 47 of a block that starts there, as the machine grid calls it."""
    real, nominal = np.asarray(real, dtype=float), np.asarray(nominal, dtype=float)
    out = _read_poem_anchors(47, 47, real, nominal, len(real), stop, hysteresis, True, True)
    return dict(zip(ANCHOR_NAMES, out, strict=True))


def test_a_window_start_the_plan_counts_stays_poems_first_anchor_on_the_machine_grid() -> None:
    """A block of one layer whose signal climbs far from its start to one maximum before the stop: the plan, read
    without the direction, counts the start, and POEM stops between the start level and the maximum. Given the
    direction and nothing else, the detector never counted the start: one extremum, POEM lost, the absolute level
    unreachable under the photometric curvature -- 34 % of runs at 0.5x on the last layer of plan 96 of the judge of
    paix's population (2026-10-10)."""
    k = np.arange(200)
    nominal = 0.895 - 0.095 * np.cos(np.pi * k / 60.0)  # 0.80 at the start, a maximum of 0.99 at 60, back down at 120
    real = 0.892 - 0.094 * np.cos(np.pi * (k + 4.0) / 61.0)  # another stack: lower, and its maximum earlier

    got = _machine_grid_anchors(real, nominal, 100, A)

    assert got["n_tp_real"] == got["n_tp_nom"] == 2
    assert (got["T_prev_nom"], got["T_prev_real"]) == (nominal[0], real[0])  # the start levels, read on each signal
    assert got["poem_ok"]


def test_a_window_start_the_plan_does_not_count_stays_uncounted_whatever_the_noise_does() -> None:
    """The plan leaves its start 0.86 threshold below a maximum: it does not count the start. The real start reading,
    pushed low by noise, sits more than the threshold under that maximum; the real signal must not count it either."""
    h = 0.005
    nominal = np.array([0.9957, 0.998, 0.9995, 1.0, 0.9995, 0.99, 0.98, 0.975, 0.98, 0.99])
    real = nominal.copy()
    real[0] = 0.994

    got = _machine_grid_anchors(real, nominal, 9, h)

    assert got["n_tp_real"] == got["n_tp_nom"] == 2  # the maximum and the minimum, on both signals


@pytest.mark.parametrize("smoothing", [8, 1])
def test_layer_0_on_the_machine_grid_does_not_crash_by_counting_the_substrate_twice(smoothing) -> None:
    """One high-index layer on glass, 1.5 quarter waves: the stop follows the minimum, and POEM anchors on the start
    and the minimum. A window of 8 switches the machine grid on; at 1 the grid is the coarse one, where the second
    sample lies far below the start and nothing was wrong."""
    wl = 550.0
    n_h, n_l, n_sub = 2.35 + 0j, 1.46 + 0j, 1.52 + 0j
    nominal = np.array([1.5 * wl / (4.0 * n_h.real), 90.0])
    crashed = []
    for run in range(64):
        val = simulate_growth_kernel(
            nominal, 0, np.zeros(0), wl, n_h, n_l, n_sub, 1.0, 0.0, 2.0, 0, -1,
            A, 12345, run, 1.0 * A, 1.0, 0.0, 0.0, True, smoothing,
        )[0]  # fmt: skip
        if val > CRASH_SENTINEL_MIN:
            crashed.append(run)

    assert crashed == []
