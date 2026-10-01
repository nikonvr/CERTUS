"""The distances and the margins to the turning points of the signal are those of the signal (audit v2, plan S3.2).

`calculate_extrema_distances`, `calculate_level_margins_to_extrema` and `check_level_margin_batch` (`certus/physics/certus_strat_math.py`, 29 % of the file covered before this one)
read the transmission of a layer that grows on a stack, find its turning points, and tell how close a stopping thickness is to them: in nanometres of optical thickness
(`calculate_extrema_distances`) or in units of T (`calculate_level_margins_to_extrema`, the criterion that replaced the thickness one). What is pinned here, against truths that
do not come from the code:

    THE SIGNAL: T is computed by the independent oracle (`tests/oracle/tmm_reference.py`). A high-index layer on glass has a turning point at every multiple of lambda / (4 n), and,
        because T is even in the thickness, one at the start of the growth of a bare substrate
    DISTANCES: a stop a few nanometres before a turning point is that many nanometres of optical thickness from it (to the 0.5 nm of the scan), a turning point out of the
        +/- 16 nm window is not reported (999), the start of a layer that grows on a turning point is at distance 0
    MARGINS: the algorithm the docstring describes (64 points over 3 thicknesses, the stop at index 21, the last reversal before it, the first after it, the gap in T), rewritten
        in plain Python on the oracle's signal, gives the kernel's margins; a missing side is MARGIN_NONE; the margin is in T
    THE BATCH: a candidate is admitted when both margins reach the threshold, and a side without a turning point constrains nothing
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from certus.physics.certus_strat_math import (
    MARGIN_NONE,
    calculate_extrema_distances,
    calculate_level_margins_to_extrema,
    check_level_margin_batch,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

pytestmark = pytest.mark.kernels

WL = 550.0
N_HIGH = 2.35 + 0.0j
N_SUB = 1.52 + 0.0j
QUARTER = WL / (4 * N_HIGH.real)  # 58.51 nm
BARE = np.eye(2, dtype=np.complex128)
POINTS = 64
SCAN = 3.0
STOP_INDEX = round((POINTS - 1) / SCAN)  # 21


def signal(thickness, matrix=BARE, wl=WL, n_layer=N_HIGH):
    """T of the layer added on top of the stack whose matrix is `matrix`, by the oracle: the characteristic matrix of the added layer times the matrix of what is below."""
    total = oracle.characteristic_matrix(n_layer, thickness, wl) @ matrix
    return oracle.rt_from_assembly(total, 1.0 + 0.0j, N_SUB)[1]


def after_the_layer(thickness):
    return oracle.stack_matrix([N_HIGH], [thickness], WL)


def sign_of(difference):
    return 1.0 if difference > 1e-15 else (-1.0 if difference < -1e-15 else 0.0)


def plain_margins(nominal, matrix=BARE, wl=WL):
    """The margins as the docstring describes them, on the oracle's signal: (margin before the stop, margin after it)."""
    if wl < 0.1 or nominal <= 0.0001:
        return MARGIN_NONE, MARGIN_NONE
    step = SCAN * nominal / (POINTS - 1)
    ts = np.array([signal(k * step, matrix, wl) for k in range(POINTS)])
    t_stop = ts[STOP_INDEX]
    margin_before = MARGIN_NONE
    reference = sign_of(ts[STOP_INDEX] - ts[STOP_INDEX - 1])
    for k in range(STOP_INDEX - 1, 0, -1):
        s = sign_of(ts[k] - ts[k - 1])
        if s != 0.0 and reference != 0.0 and s != reference:
            margin_before = abs(t_stop - ts[k])
            break
        if reference == 0.0:
            reference = s
    margin_after = MARGIN_NONE
    reference = sign_of(ts[STOP_INDEX + 1] - ts[STOP_INDEX])
    for k in range(STOP_INDEX + 1, POINTS - 1):
        s = sign_of(ts[k + 1] - ts[k])
        if s != 0.0 and reference != 0.0 and s != reference:
            margin_after = abs(t_stop - ts[k])
            break
        if reference == 0.0:
            reference = s
    return margin_before, margin_after


# --- the distances in nanometres of optical thickness ------------------------------------------------------------------------------------------


def distances(nominal, matrix=BARE, wl=WL):
    return calculate_extrema_distances(wl, N_HIGH, N_SUB, float(nominal), matrix)


def test_the_start_of_a_bare_substrate_is_on_a_turning_point_of_the_signal():
    # T is even in the thickness, so the bare substrate (d = 0) is an extremum of T(d). The scan finds it on its grid of 0.5 nm: within half a step (here 0.19 nm,
    # 0.45 nm of optical thickness), on the side of the grid point, so one distance is that and the other is not reported.
    start_before, start_after, _, _ = distances(40.0)
    assert min(start_before, start_after) <= 0.5 * N_HIGH.real + 0.01


def nearest_grid_point(turning_point, centre):
    """The scan of the end looks at centre +/- 16 / |n| nm in steps of 0.5 nm; it reports a turning point at the grid point nearest to it (the sign of the slope changes there)."""
    start = centre - 16.0 / abs(N_HIGH)
    return start + 0.5 * round((turning_point - start) / 0.5)


@pytest.mark.parametrize("ahead", [1.0, 2.7, 3.0, 4.1, 5.0])
def test_a_turning_point_ahead_of_the_stop_is_that_far_in_optical_thickness(ahead):
    nominal = QUARTER - ahead
    _, _, _, after = distances(nominal)
    # the true distance is ahead * n; the scan reports the grid point nearest to the turning point, which is within 0.25 nm of it (0.59 nm of optical thickness)
    assert after == pytest.approx((nearest_grid_point(QUARTER, nominal) - nominal) * N_HIGH.real, abs=1e-9)
    assert after == pytest.approx(ahead * N_HIGH.real, abs=0.25 * N_HIGH.real + 1e-9)


@pytest.mark.parametrize("behind", [1.0, 2.7, 3.0, 4.1, 5.0])
def test_a_turning_point_behind_the_stop_is_that_far_in_optical_thickness(behind):
    nominal = QUARTER + behind
    _, _, before, _ = distances(nominal)
    assert before == pytest.approx((nominal - nearest_grid_point(QUARTER, nominal)) * N_HIGH.real, abs=1e-9)
    assert before == pytest.approx(behind * N_HIGH.real, abs=0.25 * N_HIGH.real + 1e-9)


def test_a_turning_point_ahead_beyond_the_window_is_not_reported():
    # the window is 16 nm of optical thickness, 6.8 nm of physical thickness: a stop 15 nm before the turning point sees none ahead
    _, _, _, after = distances(QUARTER - 15.0)
    assert after == 999.0


def test_the_extrema_of_the_two_windows_are_pooled_so_the_end_can_see_the_one_found_at_the_start():
    # no turning point in the window of the end (43.5 nm +/- 6.8): the nearest one behind is the one found in the window of the START, 43 nm back: the
    # docstring says 999 when nothing is found inside the window, and the code reports the distance to the pooled extremum instead
    nominal = QUARTER - 15.0
    _, start_after, before, _ = distances(nominal)
    assert before == pytest.approx((nominal - start_after / N_HIGH.real) * N_HIGH.real, abs=1e-9)
    assert before > 16.0


def test_a_layer_that_grows_on_a_turning_point_starts_on_it():
    # the layer below is grown to a quarter wave: the next layer of the same material starts on the minimum, found within half a step of the grid
    start_before, start_after, _, _ = distances(40.0, after_the_layer(QUARTER))
    assert min(start_before, start_after) <= 0.5 * N_HIGH.real + 0.01


def test_the_start_sees_a_turning_point_a_few_nanometres_ahead():
    matrix = after_the_layer(QUARTER - 4.0)
    start_before, start_after, _, _ = distances(40.0, matrix)
    assert start_after == pytest.approx(4.0 * N_HIGH.real, abs=0.5 * N_HIGH.real + 0.01)
    assert start_before == 999.0


@pytest.mark.parametrize("wl", [0.02, 0.03, 0.06])
def test_a_wavelength_under_a_tenth_of_a_nanometre_has_no_distances(wl):
    # without the guard these wavelengths do find turning points (the signal aliases on the 0.5 nm grid): the answer would not be 999
    assert calculate_extrema_distances(wl, N_HIGH, N_SUB, 40.0, BARE) == (999.0, 999.0, 999.0, 999.0)
    assert calculate_extrema_distances(0.2, N_HIGH, N_SUB, 40.0, BARE) != (999.0, 999.0, 999.0, 999.0)


# --- the margins in units of T ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("nominal", [20.0, 30.0, 45.0, 58.0, 80.0, 100.0, 120.0, 150.0])
def test_the_margins_are_those_of_a_plain_scan_of_the_oracles_signal(nominal):
    expected = plain_margins(nominal)
    got = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, nominal, BARE)
    assert got == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("below", [0.0, 30.0, 58.5, 90.0])
def test_the_margins_are_those_of_a_plain_scan_when_the_layer_grows_on_a_stack(below):
    matrix = after_the_layer(below) if below else BARE
    expected = plain_margins(40.0, matrix)
    got = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, 40.0, matrix)
    assert got == pytest.approx(expected, abs=1e-9)


def test_a_margin_is_a_gap_in_transmission_between_zero_and_one():
    before, after = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, 120.0, BARE)
    for margin in (before, after):
        assert 0.0 <= margin < 1.0


@pytest.mark.parametrize("side", [-1.0, 1.0])
def test_the_margin_grows_as_the_square_of_the_distance_to_the_turning_point(side):
    """T ~ T_ext - c (d - d0)^2 (the docstring's own law): outside the blind zone the margin to the turning point is quadratic in the distance, to 30 % (the grid is 2.8 nm)."""
    near, far = 2.0, 3.5
    a = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, QUARTER + side * near, BARE)
    b = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, QUARTER + side * far, BARE)
    index = 1 if side < 0 else 0  # a stop before the turning point sees it ahead (margin_after), a stop after it sees it behind (margin_before)
    assert a[index] < 1.0
    assert b[index] < 1.0
    assert b[index] / a[index] == pytest.approx((far / near) ** 2, rel=0.3)


@pytest.mark.xfail(
    strict=True,
    reason="D73: a stop within half a grid step of a turning point is in a blind zone of the margin criterion: the turning point at the stop is no one's neighbour",
)
def test_a_stop_on_a_turning_point_has_no_margin_to_it():
    """The worst stop there is: the level is the extremum's, and half the noise realizations put the target beyond it. The margin to the turning point is then zero, on one side at least.

    It is not: from 1.25 nm before the turning point to 1.25 nm after it (a grid step is 2.8 nm), the margins are (MARGIN_NONE, 0.28), the second being the gap to the OTHER
    kind of extremum; `check_level_margin_batch` admits the stop for any threshold under 0.28. Strict: the day the function counts the turning point under the stop, this test
    passes, and the mark has to go."""
    for offset in (-1.0, -0.5, 0.0, 0.5, 1.0):
        margins = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, QUARTER + offset, BARE)
        assert min(margins) < 0.01, f"offset {offset} nm: margins {margins}"


def test_the_blind_zone_of_the_margin_criterion_is_where_the_stop_is_within_half_a_step_of_the_turning_point():
    """What the xfail above says, measured: the zone is [-1.25, +1.25] nm around the turning point at the quarter wave (half a step), and nowhere else near it."""
    step = SCAN * QUARTER / (POINTS - 1)
    for offset in np.arange(-3.0, 3.01, 0.25):
        margins = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, QUARTER + offset, BARE)
        blind = min(margins) > 0.1
        assert blind == (abs(offset) < step / 2), f"offset {offset}: margins {margins}"


def test_a_missing_side_is_the_marker_and_not_a_huge_margin():
    # a very thin layer scans 3 thicknesses of a few nanometres: no turning point on either side
    before, after = calculate_level_margins_to_extrema(WL, N_HIGH, N_SUB, 3.0, BARE)
    assert after == MARGIN_NONE
    assert MARGIN_NONE == 999.0
    assert before == MARGIN_NONE or before < 1.0


@pytest.mark.parametrize(("wl", "nominal"), [(0.05, 40.0), (WL, 0.0), (WL, 0.00005), (WL, -3.0), (WL, -40.0)])
def test_a_wavelength_under_a_tenth_of_a_nanometre_or_a_nothing_of_a_layer_has_no_margin(wl, nominal):
    assert calculate_level_margins_to_extrema(wl, N_HIGH, N_SUB, nominal, BARE) == (MARGIN_NONE, MARGIN_NONE)


# --- the batch -----------------------------------------------------------------------------------------------------------------------------------


def batch(thresholds, nominal=120.0):
    wls = np.array([WL, WL, 500.0, 650.0])
    n_currents = np.full(4, N_HIGH, dtype=np.complex128)
    n_subs = np.full(4, N_SUB, dtype=np.complex128)
    matrices = np.stack([BARE, after_the_layer(40.0), BARE, after_the_layer(20.0)])
    out = {}
    for margin in thresholds:
        out[margin] = check_level_margin_batch(wls, n_currents, n_subs, nominal, matrices, margin)
    return out, (wls, n_currents, n_subs, matrices)


def test_a_candidate_is_admitted_when_both_margins_reach_the_threshold():
    results, (wls, n_currents, n_subs, matrices) = batch([0.0, 0.01, 0.05, 0.2, 2.0])
    margins = [calculate_level_margins_to_extrema(wls[i], n_currents[i], n_subs[i], 120.0, matrices[i]) for i in range(4)]
    for threshold, admitted in results.items():
        expected = [(mp >= threshold) and (mn >= threshold) for mp, mn in margins]
        assert list(admitted) == expected


def test_the_threshold_selects_more_candidates_as_it_comes_down():
    results, _ = batch([0.0, 0.01, 0.05, 0.2, 2.0])
    counts = [int(results[t].sum()) for t in (0.0, 0.01, 0.05, 0.2, 2.0)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == 4  # a threshold of zero admits everybody, including a candidate with no turning point on one side
    assert counts[-1] == 0  # a threshold over 1 admits only a candidate with no turning point on either side, and there is none here
