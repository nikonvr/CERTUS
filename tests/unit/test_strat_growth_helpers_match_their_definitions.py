"""The small kernels under STRAT's growth simulation do what their documentation defines (certus_strat_growth).

`certus/physics/certus_strat_growth.py` was covered at 4.8 % on 2026-09-30 (the JIT hides it) and the oracle does not
reach it. `simulate_growth_kernel` (1 190 lines) is built from these pieces, and its refactor (plan S5.1) needs them
pinned first. Two kinds of test, none of them a copy of the code:

* physics, against the INDEPENDENT oracle (`tests/oracle/tmm_reference.py`, never against the kernel: prohibition 7):
  the front transmission of a growing layer, its closed form `T(d) = 4 n_sub / (P + Q cos 2 delta + R sin 2 delta)`,
  and the whole-grid version;
* rules stated in the docstrings and worked out by hand: where turning points are, what the hysteresis ignores, that
  the returned index is the extremum itself and not the moment it was noticed, and how the slit bias is read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack, stack_matrix  # noqa: E402

from certus.physics.certus_strat_growth import (  # noqa: E402
    D_SCAN_VAL,
    compute_T_front_at_layer,
    compute_T_front_profile,
    detect_turning_points,
    layer_scan_coeffs,
    next_turning_point_after,
    slit_bias_at,
)

pytestmark = pytest.mark.kernels

N_SUB = 1.52


def _stacks(count: int = 12):
    rng = np.random.default_rng(5)
    for _ in range(count):
        m = int(rng.integers(1, 8))
        yield rng.uniform(1.3, 2.4, m), rng.uniform(20, 150, m), float(rng.uniform(1.3, 2.4)), float(rng.uniform(400, 900))


def _oracle_t(n_prev, d_prev, n_layer, d, wl) -> float:
    """T of the deposited layers plus the growing one, on the substrate, by the independent TMM."""
    return rt_stack(wl, [*n_prev, n_layer], [*d_prev, d], 1.0, N_SUB)[1]


# =============================================================================
# Front transmission of a growing layer
# =============================================================================


@pytest.mark.parametrize("d", [5.0, 40.0, 97.3, 180.0])
def test_the_front_transmission_at_the_end_of_a_layer_is_the_oracles(d) -> None:
    for n_prev, d_prev, n_layer, wl in _stacks():
        m = stack_matrix(n_prev, d_prev, wl)

        got = compute_T_front_at_layer(wl, n_layer + 0j, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], d)

        assert got == pytest.approx(_oracle_t(n_prev, d_prev, n_layer, d, wl), abs=1e-12)


def test_without_a_monitoring_wavelength_nothing_is_read() -> None:
    m = np.eye(2, dtype=np.complex128)

    assert compute_T_front_at_layer(0.0, 2.0 + 0j, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], 50.0) == 0.0


@pytest.mark.parametrize("d", [5.0, 40.0, 97.3, 180.0])
def test_T_of_d_has_the_closed_form_of_its_three_coefficients_and_it_is_the_oracles(d) -> None:
    """T(d) = 4 n_sub / (P + Q cos 2 delta + R sin 2 delta), delta = 2 pi n d / lambda: the same computation, written
    with three coefficients paid once (docstring of `layer_scan_coeffs`, checked here against the oracle)."""
    for n_prev, d_prev, n_layer, wl in _stacks():
        m = stack_matrix(n_prev, d_prev, wl)
        p, q, r = layer_scan_coeffs(m[0, 0], m[0, 1], m[1, 0], m[1, 1], n_layer + 0j, N_SUB + 0j)
        delta = 2 * np.pi * n_layer * d / wl

        closed = 4 * N_SUB / (p + q * np.cos(2 * delta) + r * np.sin(2 * delta))

        assert closed == pytest.approx(_oracle_t(n_prev, d_prev, n_layer, d, wl), abs=1e-12)


def test_the_profile_over_a_grid_is_the_point_by_point_value() -> None:
    n_prev, d_prev, n_layer, wl = next(iter(_stacks(1)))
    m = stack_matrix(n_prev, d_prev, wl)
    grid = np.linspace(0.0, 200.0, 41)

    profile = compute_T_front_profile(wl, n_layer + 0j, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], grid)

    single = [compute_T_front_at_layer(wl, n_layer + 0j, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], d) for d in grid]
    assert profile.shape == grid.shape
    np.testing.assert_allclose(profile, single, rtol=1e-13, atol=0.0)


# =============================================================================
# Turning points of a monitoring signal
# =============================================================================

SIGNAL = np.array([0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0])  # maxima at 1 and 5, a minimum at 3


def test_the_legacy_rule_finds_every_sign_change_of_the_slope_and_keeps_the_last_two() -> None:
    assert detect_turning_points(SIGNAL, len(SIGNAL), 6, False, 0.0) == (3, 3, 5)


def test_an_extremum_beyond_the_stop_is_not_counted_and_kept_only_if_none_came_before() -> None:
    assert detect_turning_points(SIGNAL, len(SIGNAL), 3, False, 0.0) == (2, 1, 3)  # the maximum at 5 is ignored
    assert detect_turning_points(SIGNAL, len(SIGNAL), 0, False, 0.0) == (0, -1, 1)  # first one retained, uncounted


def test_a_start_that_is_a_turning_point_is_counted_first() -> None:
    ramp = np.array([0.0, 1.0, 2.0, 3.0])

    assert detect_turning_points(ramp, 4, 3, False, 0.0) == (0, -1, -1)
    assert detect_turning_points(ramp, 4, 3, True, 0.0) == (1, -1, 0)


RIPPLE = np.array([0.0, 1.0, 0.999, 1.0005, 0.0])


def test_the_legacy_rule_counts_a_ripple_that_the_hysteresis_ignores() -> None:
    assert detect_turning_points(RIPPLE, len(RIPPLE), 4, False, 0.0)[0] == 3  # 1.0 | 0.999 | 1.0005: three extrema
    n_tp, tp_a, tp_b = detect_turning_points(RIPPLE, len(RIPPLE), 4, False, 0.05)

    assert n_tp == 2  # the start (a minimum) and the highest peak: the ripple of 1e-3 is below the threshold
    assert (tp_a, tp_b) == (0, 3)  # the index is that of the extremum itself, not of the moment it was noticed (4)


def test_a_declared_start_is_not_counted_twice_by_the_hysteresis_detector() -> None:
    assert detect_turning_points(RIPPLE, len(RIPPLE), 4, True, 0.05) == (2, 0, 3)  # not 3: index 0 is counted once


def test_the_next_turning_point_after_an_index_follows_the_same_rule() -> None:
    assert next_turning_point_after(SIGNAL, len(SIGNAL), 1, 0.0) == 3
    assert next_turning_point_after(SIGNAL, len(SIGNAL), 3, 0.0) == 5
    assert next_turning_point_after(SIGNAL, len(SIGNAL), 5, 0.0) == 6  # none left: the last index

    assert next_turning_point_after(RIPPLE, len(RIPPLE), 0, 0.05) == 3  # the ripple does not cut the window short
    assert next_turning_point_after(RIPPLE, len(RIPPLE), 0, 0.0) == 1  # the legacy rule stops at the first wiggle


def test_a_monotonic_signal_has_no_next_turning_point_and_the_window_ends_with_the_signal() -> None:
    ramp = np.array([0.0, 1.0, 2.0, 3.0])

    assert next_turning_point_after(ramp, 4, 0, 0.0) == 3
    assert next_turning_point_after(ramp, 4, 0, 0.05) == 3
    assert next_turning_point_after(ramp, 4, 3, 0.05) == 3  # nothing after the last sample


# =============================================================================
# Slit bias
# =============================================================================


def test_the_slit_bias_is_read_by_linear_interpolation_between_nodes_of_the_scanned_window() -> None:
    profiles = np.array([[0.0, 2.0, 4.0, 10.0]])  # 4 nodes over u in [0, D_SCAN_VAL]

    assert slit_bias_at(profiles, 0, 0.0) == 0.0
    assert slit_bias_at(profiles, 0, D_SCAN_VAL / 3) == pytest.approx(2.0)  # exactly on the second node
    assert slit_bias_at(profiles, 0, D_SCAN_VAL / 6) == pytest.approx(1.0)  # halfway between the first two
    assert slit_bias_at(profiles, 0, D_SCAN_VAL) == 10.0


def test_the_slit_bias_is_clamped_beyond_the_window_never_extrapolated() -> None:
    profiles = np.array([[1.0, 2.0, 3.0]])

    assert slit_bias_at(profiles, 0, -5.0) == 1.0
    assert slit_bias_at(profiles, 0, 10 * D_SCAN_VAL) == 3.0


def test_each_layer_reads_its_own_row_and_a_profile_of_one_node_is_no_profile() -> None:
    profiles = np.array([[0.0, 1.0], [5.0, 7.0]])

    assert slit_bias_at(profiles, 1, D_SCAN_VAL / 2) == pytest.approx(6.0)
    assert slit_bias_at(np.array([[3.0]]), 0, 1.0) == 0.0
