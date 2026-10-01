"""`check_extrema_proximity` refuses a stop near a turning point of the signal, and the zones it refuses are measured here (audit v2, plan S3.2; ETAT D70).

A layer that stops just BEFORE a turning point of the transmission signal can lose the run: an upstream error makes the signal turn before the stopping level is
reached, the machine waits for a level that never comes. Stopping AFTER a turning point is safe: the signal moves away from it. `check_extrema_proximity`
(`certus/physics/certus_strat_math.py`, 29 % covered before this file) refuses the stops that fall too close to a turning point, wider before it than after.

The truth against which it is measured does not come from the code: a high-index layer on glass has a turning point of T at every multiple of lambda / (4 n),
and the independent oracle (`tests/oracle/tmm_reference.py`) says that the slope changes sign there.

WHAT THE CODE DOES, which is not what its docstring says (ETAT D70). The docstring and the comment of the growth kernel announce a forbidden zone of 3 widths before
a turning point and 1 width after it. The code samples T at d - w, d, d + w and d + 3w and compares the sign of three slopes, whose centres are at d - w/2, d + w/2
and d + 2w: it refuses a stop with a turning point between d - w/2 and d + 2w, that is, a turning point at most **2 widths ahead** of the stop and at most **half a width
behind** it, whatever the width. The asymmetry is 4 to 1 and not 3 to 1. This file PINS THE BEHAVIOUR, so that changing it is a decision and not an accident; whether the
code or the documentation should move is the owner's.

    the refused stops: exactly the interval [turning point - 2 w, turning point + w / 2], for three widths, at the first and at the second turning point
    the accepted stops: those just outside it, and the middle of the layer; a stop on the turning point is refused
    the arrival check is skipped for a layer thinner than the width; a wavelength under 0.1 nm is refused
    the start check (`check_start`): a start on a turning point is refused; with `wl_changed` a turning point ahead of the start is refused too, which the symmetric check alone does not see
    a previous index that is not positive is replaced by the current one
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from certus.physics.certus_strat_math import check_extrema_proximity

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

pytestmark = pytest.mark.kernels

WL = 550.0
N_HIGH = 2.35 + 0.0j
N_SUB = 1.52 + 0.0j
QUARTER = WL / (4 * N_HIGH.real)  # 58.51 nm: the first turning point of T for one high-index layer on glass
BARE = np.eye(2, dtype=np.complex128)
STEP = 0.05


def accepted(thickness, width, matrix=BARE, check_start=False, wl_changed=False, n_previous=N_HIGH, wl=WL):
    return check_extrema_proximity(wl, N_HIGH, n_previous, N_SUB, float(thickness), matrix, float(width), check_start, wl_changed)


def refused_interval(centre, width, span=3.0):
    """The stops that are refused around `centre`, found by sweeping the thickness at 0.05 nm: (smallest, largest) refused stop, and how many they are."""
    sweep = np.arange(centre - span * width, centre + 2.0 * width, STEP)
    refused = [float(d) for d in sweep if not accepted(d, width)]
    assert refused, "no stop is refused near the turning point"
    return refused[0], refused[-1], len(refused)


def after_the_layer(thickness):
    """The characteristic matrix of the high-index layer already grown to `thickness` (the oracle's, not the code's)."""
    return oracle.stack_matrix([N_HIGH], [thickness], WL)


# --- the truth: where the turning points are --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("multiple", [1, 2, 3])
def test_the_signal_of_one_high_index_layer_turns_at_every_quarter_wave(multiple):
    d = multiple * QUARTER
    before, at, after = (oracle.rt_stack(WL, [N_HIGH], [x], 1.0 + 0.0j, N_SUB)[1] for x in (d - 1.0, d, d + 1.0))
    assert (at - before) * (after - at) < 0  # the slope changes sign: a maximum or a minimum


# --- the arrival check: which stops are refused ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("width", [2.0, 5.0, 10.0])
@pytest.mark.parametrize("turning_point", [1, 2])
def test_the_refused_stops_are_two_widths_before_a_turning_point_and_half_a_width_after(width, turning_point):
    centre = turning_point * QUARTER
    first, last, count = refused_interval(centre, width)
    assert first == pytest.approx(centre - 2.0 * width, abs=0.12)
    assert last == pytest.approx(centre + 0.5 * width, abs=0.12)
    # one interval. At most one accepted stop inside it: where a slope is exactly zero (a stop half a width before the turning point, symmetric with the one
    # a width further) the test of the sign change does not fire. A single point of a continuum, and the grid of 0.05 nm hits it for one width only.
    holes = round((last - first) / STEP) + 1 - count
    assert 0 <= holes <= 1


def test_a_stop_on_the_turning_point_is_refused():
    assert not accepted(QUARTER, 5.0)


@pytest.mark.parametrize("offset", [-2.0 * 5.0 - 0.5, 0.5 * 5.0 + 0.5, -3.0 * 5.0, 3.0 * 5.0])
def test_a_stop_just_outside_the_zones_is_accepted(offset):
    assert accepted(QUARTER + offset, 5.0)


def test_the_middle_of_a_layer_between_two_turning_points_is_accepted():
    assert accepted(1.5 * QUARTER, 2.0)


def test_the_zone_before_a_turning_point_is_wider_than_the_zone_after_it():
    first, last, _ = refused_interval(QUARTER, 5.0)
    assert QUARTER - first > 3.0 * (last - QUARTER)


def test_a_thin_layer_skips_the_arrival_check():
    # the turning point is 8.5 nm ahead of a stop at 50 nm; a width of 40 nm sees it, a width of 100 nm makes the layer "thinner than the width" and nothing is checked
    assert not accepted(50.0, 40.0)
    assert accepted(50.0, 100.0)


def test_the_arrival_check_starts_when_the_layer_is_thicker_than_the_width():
    assert accepted(40.0, 40.0)  # as thick as the width: skipped
    assert not accepted(40.5, 40.0)  # a little thicker: checked, and the turning point 18 nm ahead is seen


def test_a_wavelength_under_a_tenth_of_a_nanometre_is_refused():
    assert not accepted(QUARTER / 2, 2.0, wl=0.05)
    assert accepted(QUARTER / 2, 2.0, wl=WL)


# --- the start check ------------------------------------------------------------------------------------------------------------------------


def start(d0, width, wl_changed, n_previous=N_HIGH):
    """The start of the next layer of the same material, after `d0` of it: only the start check decides (the arrival check is skipped by a thin layer)."""
    return check_extrema_proximity(WL, N_HIGH, n_previous, N_SUB, 0.5 * width, after_the_layer(d0), width, True, wl_changed)


@pytest.mark.parametrize("wl_changed", [False, True])
def test_a_start_on_a_turning_point_is_refused(wl_changed):
    assert not start(QUARTER, 2.0, wl_changed)


@pytest.mark.parametrize("wl_changed", [False, True])
def test_a_start_far_from_a_turning_point_is_accepted(wl_changed):
    assert start(QUARTER - 5.0 * 2.0, 2.0, wl_changed)
    assert start(QUARTER + 5.0 * 2.0, 2.0, wl_changed)


def test_a_turning_point_ahead_of_the_start_is_refused_only_when_the_wavelength_changed():
    d0 = QUARTER - 1.5 * 2.0  # the turning point is one and a half widths ahead
    assert start(d0, 2.0, wl_changed=False)  # the symmetric check sees half a width on each side only
    assert not start(d0, 2.0, wl_changed=True)


def test_without_the_start_check_a_start_on_a_turning_point_is_not_looked_at():
    assert check_extrema_proximity(WL, N_HIGH, N_HIGH, N_SUB, 1.0, after_the_layer(QUARTER), 2.0, False, False)


def test_a_previous_index_that_is_not_positive_is_replaced_by_the_current_one():
    for d0 in (QUARTER - 1.0, QUARTER + 0.7, QUARTER - 3.0):
        for wl_changed in (False, True):
            assert start(d0, 2.0, wl_changed, n_previous=0.0 + 0.0j) == start(d0, 2.0, wl_changed, n_previous=N_HIGH)
