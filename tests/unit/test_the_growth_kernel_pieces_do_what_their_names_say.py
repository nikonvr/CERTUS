"""The sub-kernels cut out of `simulate_growth_kernel` (plan S5.1) each do what their name says.

The 1 190 lines of `simulate_growth_kernel` are being cut into named pieces, one per commit, each proved bit for bit on
the STRAT corpus of `scripts/c1_diff.py`. That proof says the kernel still returns the same bits; it does not say that a
piece does what its name promises, and the next person to touch one of them needs it read on its own, from Python, where
Numba compiles it as an ordinary function. One test group per piece, against the INDEPENDENT oracle
(`tests/oracle/tmm_reference.py`, never against the kernel: prohibition 7) or against rules worked out by hand.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack, stack_matrix  # noqa: E402

from certus.physics.certus_strat_growth import (  # noqa: E402
    D_SCAN_VAL,
    MAX_LOOKBACK_VAL,
    RATE_TURN_NM,
    SCAN_ERROR_MARGIN_NM,
    SCAN_NPTS_CURRENT,
    SCAN_NPTS_HISTORY,
    _fill_current_signal,
    _apply_photometric_drift,
    _fill_history_signal,
    _frozen_trigger_level,
    _invert_thickness_from_probes,
    _level_reachability,
    _monotonicity_scan,
    _rate_layer_thickness,
    _read_poem_anchors,
    _resample_on_machine_grid,
    _running_mean,
    _scan_window,
    _stack_matrix,
    _stack_matrix_pair,
    turning_point_margins,
)
from certus.physics.certus_strat_math import _seeded_noise_sample  # noqa: E402

pytestmark = pytest.mark.kernels

N_EVEN, N_ODD = 2.35, 1.46
N_SUB = 1.52


def _stack(count: int = 10):
    rng = np.random.default_rng(11)
    for _ in range(count):
        layers = int(rng.integers(1, 9))
        yield rng.uniform(20, 150, layers), float(rng.uniform(400, 900))


def _indices(first: int, last: int, n_even: float, n_odd: float) -> list[float]:
    return [n_even if j % 2 == 0 else n_odd for j in range(first, last)]


# =============================================================================
# _stack_matrix / _stack_matrix_pair : the characteristic matrix of a run of layers
# =============================================================================


def test_the_stack_matrix_is_the_oracles_for_a_stack_from_the_substrate() -> None:
    for thicknesses, wl in _stack():
        got = _stack_matrix(wl, N_EVEN, N_ODD, thicknesses, 0, len(thicknesses))

        expected = stack_matrix(_indices(0, len(thicknesses), N_EVEN, N_ODD), thicknesses, wl)
        np.testing.assert_allclose(got, [expected[0, 0], expected[0, 1], expected[1, 0], expected[1, 1]], atol=1e-13)


def test_a_window_of_layers_keeps_the_parity_of_the_layers_it_takes() -> None:
    # A witness swapped in at an ODD layer starts on the low index: the parity is that of the layer, not of the window.
    thicknesses = np.array([60.0, 90.0, 40.0, 110.0, 75.0, 55.0])
    wl = 550.0

    got = _stack_matrix(wl, N_EVEN, N_ODD, thicknesses, 3, 6)

    expected = stack_matrix(_indices(3, 6, N_EVEN, N_ODD), thicknesses[3:6], wl)
    np.testing.assert_allclose(got, [expected[0, 0], expected[0, 1], expected[1, 0], expected[1, 1]], atol=1e-13)
    wrong_parity = stack_matrix(_indices(2, 5, N_EVEN, N_ODD), thicknesses[3:6], wl)
    assert not np.allclose(got, [wrong_parity[0, 0], wrong_parity[0, 1], wrong_parity[1, 0], wrong_parity[1, 1]])


@pytest.mark.parametrize("first, last", [(0, 0), (3, 3), (4, 2)])
def test_an_empty_run_of_layers_is_the_identity(first, last) -> None:
    got = _stack_matrix(550.0, N_EVEN, N_ODD, np.array([60.0] * 6), first, last)

    assert got == (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)


def test_the_matrix_of_a_lossless_stack_has_unit_determinant() -> None:
    # det = 1 for every lossless layer, so for their product: a check that does not use any TMM at all.
    for thicknesses, wl in _stack():
        m00, m01, m10, m11 = _stack_matrix(wl, N_EVEN, N_ODD, thicknesses, 0, len(thicknesses))

        assert m00 * m11 - m01 * m10 == pytest.approx(1.0, abs=1e-12)


def test_a_complex_index_is_taken_as_it_is_given() -> None:
    # n - i k with k > 0 is an absorbing layer (Macleod convention, as everywhere in CERTUS).
    thicknesses = np.array([80.0, 120.0, 60.0])
    n_even, n_odd = N_EVEN - 0.05j, N_ODD - 0.002j

    got = _stack_matrix(550.0, n_even, n_odd, thicknesses, 0, 3)

    expected = stack_matrix([n_even, n_odd, n_even], thicknesses, 550.0)
    np.testing.assert_allclose(got, [expected[0, 0], expected[0, 1], expected[1, 0], expected[1, 1]], atol=1e-13)
    lossless = _stack_matrix(550.0, N_EVEN, N_ODD, thicknesses, 0, 3)
    assert not np.allclose(got, lossless, atol=1e-3)  # the absorption is in the matrix


def test_the_pair_is_the_real_and_the_nominal_matrices_each_on_its_own_stack() -> None:
    rng = np.random.default_rng(3)
    real = rng.uniform(20, 150, 7)
    nominal = rng.uniform(20, 150, 7)
    wl = 610.0

    got = _stack_matrix_pair(wl, N_EVEN + 0.0j, N_ODD + 0.0j, real, 2.30 + 0.0j, 1.45 + 0.0j, nominal, 1, 6)

    r = stack_matrix(_indices(1, 6, N_EVEN, N_ODD), real[1:6], wl)
    q = stack_matrix(_indices(1, 6, 2.30, 1.45), nominal[1:6], wl)
    np.testing.assert_allclose(got[:4], [r[0, 0], r[0, 1], r[1, 0], r[1, 1]], atol=1e-13)
    np.testing.assert_allclose(got[4:], [q[0, 0], q[0, 1], q[1, 0], q[1, 1]], atol=1e-13)
    assert not np.allclose(got[:4], got[4:])  # two stacks, two matrices: sharing them would merge the real and the nominal


def test_the_pair_of_an_empty_run_is_two_identities() -> None:
    got = _stack_matrix_pair(550.0, N_EVEN, N_ODD, np.ones(3), N_EVEN, N_ODD, np.ones(3), 2, 2)

    assert got == (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j) * 2


# =============================================================================
# _fill_history_signal : the layers of the block that are replayed, real and nominal
# =============================================================================

NOMINAL_EVEN, NOMINAL_ODD = 2.30, 1.45  # the strategy's indices differ from the real ones: two stacks, not one
WL = 560.0


def _history(j0: int, i_layer: int, *, n_even=N_EVEN, n_odd=N_ODD, noise=0.0, seed=0, run=0, base=0) -> dict:
    """Replay layers j0 .. i_layer - 1 on a stack whose real and nominal thicknesses differ, from the witness `base`."""
    rng = np.random.default_rng(21)
    th_real = rng.uniform(40, 120, 8)
    th_nom = rng.uniform(40, 120, 8)
    r = _stack_matrix(WL, n_even, n_odd, th_real, base, j0)
    q = _stack_matrix(WL, NOMINAL_EVEN, NOMINAL_ODD, th_nom, base, j0)
    n_hist = (i_layer - j0) * SCAN_NPTS_HISTORY
    ts_r, ts_n = np.zeros(n_hist + 7), np.zeros(n_hist + 7)
    out = _fill_history_signal(
        WL,
        N_SUB + 0j,
        n_even,
        n_odd,
        NOMINAL_EVEN,
        NOMINAL_ODD,
        th_real,
        th_nom,
        j0,
        i_layer,
        *r,
        *q,
        ts_r,
        ts_n,
        noise > 0.0,
        noise,
        seed,
        run,
    )
    return {"out": out, "ts_r": ts_r, "ts_n": ts_n, "th_real": th_real, "th_nom": th_nom, "n_hist": n_hist}


def _oracle_point(j: int, k: int, base: int, n_even, n_odd, thicknesses) -> float:
    """T of layers base .. j - 1 in full and layer j grown to k / SCAN_NPTS_HISTORY of its thickness."""
    layers = [n_even if jj % 2 == 0 else n_odd for jj in range(base, j + 1)]
    grown = [*thicknesses[base:j], k / SCAN_NPTS_HISTORY * thicknesses[j]]
    return rt_stack(WL, layers, grown, 1.0, N_SUB)[1]


@pytest.mark.parametrize("imag", [0.0, 0.01])  # the closed form (k < 1e-4) and the matrix path take turns
@pytest.mark.parametrize("j0, i_layer, base", [(0, 3, 0), (2, 5, 0), (3, 6, 1)])
def test_each_point_of_each_replayed_layer_is_the_oracles_transmission(j0, i_layer, base, imag) -> None:
    n_even, n_odd = N_EVEN - 1j * imag, N_ODD - 1j * imag

    got = _history(j0, i_layer, n_even=n_even, n_odd=n_odd, base=base)

    for j in range(j0, i_layer):
        for k in range(1, SCAN_NPTS_HISTORY + 1):
            index = (j - j0) * SCAN_NPTS_HISTORY + (k - 1)
            real = _oracle_point(j, k, base, n_even, n_odd, got["th_real"])
            nominal = _oracle_point(j, k, base, NOMINAL_EVEN, NOMINAL_ODD, got["th_nom"])
            assert got["ts_r"][index] == pytest.approx(real, abs=1e-11), (j, k)
            assert got["ts_n"][index] == pytest.approx(nominal, abs=1e-11), (j, k)


def test_the_replay_hands_back_the_next_free_index_and_the_matrices_of_the_stack_up_to_the_layer() -> None:
    got = _history(2, 5, base=1)

    idx, *matrices = got["out"]
    assert idx == 3 * SCAN_NPTS_HISTORY
    real = stack_matrix(_indices(1, 5, N_EVEN, N_ODD), got["th_real"][1:5], WL)
    nominal = stack_matrix(_indices(1, 5, NOMINAL_EVEN, NOMINAL_ODD), got["th_nom"][1:5], WL)
    np.testing.assert_allclose(matrices[:4], [real[0, 0], real[0, 1], real[1, 0], real[1, 1]], atol=1e-12)
    np.testing.assert_allclose(matrices[4:], [nominal[0, 0], nominal[0, 1], nominal[1, 0], nominal[1, 1]], atol=1e-12)


def test_an_empty_replay_writes_nothing_and_leaves_the_matrices_alone() -> None:
    got = _history(3, 3)

    idx, *matrices = got["out"]
    assert idx == 0
    assert not got["ts_r"].any() and not got["ts_n"].any()
    r = stack_matrix(_indices(0, 3, N_EVEN, N_ODD), got["th_real"][0:3], WL)
    np.testing.assert_allclose(matrices[:4], [r[0, 0], r[0, 1], r[1, 0], r[1, 1]], atol=1e-12)


def test_the_reading_noise_of_a_layer_is_indexed_by_the_layer_and_the_point_not_by_the_window() -> None:
    # "The machine recorded a measurement, it does not remeasure it": layer 3 read from a block that starts at 1 and from
    # one that starts at 3 carries the SAME noise, or two strategies compared on one draw would not see the same past.
    scale, seed, run = 0.01, 5, 2
    clean_a, noisy_a = _history(1, 4), _history(1, 4, noise=scale, seed=seed, run=run)
    clean_b, noisy_b = _history(3, 4), _history(3, 4, noise=scale, seed=seed, run=run)

    layer_3_in_a = slice(2 * SCAN_NPTS_HISTORY, 3 * SCAN_NPTS_HISTORY)
    added_a = noisy_a["ts_r"][layer_3_in_a] - clean_a["ts_r"][layer_3_in_a]
    added_b = noisy_b["ts_r"][: SCAN_NPTS_HISTORY] - clean_b["ts_r"][: SCAN_NPTS_HISTORY]
    expected = [scale * _seeded_noise_sample(seed, 3, run, k - 1, True) for k in range(1, SCAN_NPTS_HISTORY + 1)]
    np.testing.assert_allclose(added_a, expected, atol=1e-15)
    np.testing.assert_allclose(added_b, expected, atol=1e-15)
    assert np.abs(added_a).max() > 0.0


def test_the_nominal_signal_is_never_noised_and_without_a_scale_nothing_is() -> None:
    # `Ts_n` is the strategy computed offline: nobody measures it.
    noisy = _history(1, 4, noise=0.02, seed=1, run=1)
    clean = _history(1, 4)

    np.testing.assert_array_equal(noisy["ts_n"], clean["ts_n"])
    assert not np.array_equal(noisy["ts_r"], clean["ts_r"])
    np.testing.assert_array_equal(_history(1, 4, noise=0.0, seed=9)["ts_r"], clean["ts_r"])


# =============================================================================
# _fill_current_signal : the scan of the layer being grown
# =============================================================================

SENTINEL = -7.0  # what the arrays hold before the scan: anything else at the end is the scan's doing


def _current(i_layer, npts, d_max, *, idx=0, n_hist=0, n_even=N_EVEN, n_odd=N_ODD, noise=0.0, seed=0, run=0, base=0):
    """Scan layer `i_layer` from 0 to `d_max` in `npts` points, on a stack whose real and nominal thicknesses differ."""
    rng = np.random.default_rng(21)
    th_real = rng.uniform(40, 120, 8)
    th_nom = rng.uniform(40, 120, 8)
    r = _stack_matrix(WL, n_even, n_odd, th_real, base, i_layer)
    q = _stack_matrix(WL, NOMINAL_EVEN, NOMINAL_ODD, th_nom, base, i_layer)
    ts_r, ts_n = np.full(idx + npts + 5, SENTINEL), np.full(idx + npts + 5, SENTINEL)
    _fill_current_signal(
        WL,
        N_SUB + 0j,
        n_even,
        n_odd,
        NOMINAL_EVEN,
        NOMINAL_ODD,
        i_layer,
        *r,
        *q,
        d_max,
        npts,
        n_hist,
        idx,
        ts_r,
        ts_n,
        noise > 0.0,
        noise,
        seed,
        run,
    )
    return {"ts_r": ts_r, "ts_n": ts_n, "th_real": th_real, "th_nom": th_nom}


def _oracle_current(i_layer, d, base, n_even, n_odd, thicknesses) -> float:
    """T of layers base .. i_layer - 1 in full and layer `i_layer` grown to `d` nm."""
    layers = [n_even if jj % 2 == 0 else n_odd for jj in range(base, i_layer + 1)]
    return rt_stack(WL, layers, [*thicknesses[base:i_layer], d], 1.0, N_SUB)[1]


@pytest.mark.parametrize("imag", [0.0, 0.01])  # the closed form and the matrix path take turns
@pytest.mark.parametrize("i_layer, base", [(0, 0), (3, 0), (4, 2)])
def test_each_point_of_the_current_scan_is_the_oracles_transmission_from_zero_to_d_max(i_layer, base, imag) -> None:
    npts, d_max = 21, 150.0
    n_even, n_odd = N_EVEN - 1j * imag, N_ODD - 1j * imag

    got = _current(i_layer, npts, d_max, n_even=n_even, n_odd=n_odd, base=base)

    for k in range(npts):
        d = k * d_max / (npts - 1)
        real = _oracle_current(i_layer, d, base, n_even, n_odd, got["th_real"])
        nominal = _oracle_current(i_layer, d, base, NOMINAL_EVEN, NOMINAL_ODD, got["th_nom"])
        assert got["ts_r"][k] == pytest.approx(real, abs=1e-11), k
        assert got["ts_n"][k] == pytest.approx(nominal, abs=1e-11), k


def test_the_scan_writes_from_idx_and_only_there() -> None:
    got = _current(2, 12, 90.0, idx=5)

    for signal in (got["ts_r"], got["ts_n"]):
        assert (signal[:5] == SENTINEL).all() and (signal[17:] == SENTINEL).all()
        assert (signal[5:17] != SENTINEL).all()


def test_the_noise_of_the_current_layer_is_indexed_by_the_layer_and_the_point() -> None:
    scale, seed, run, i_layer, npts = 0.01, 4, 6, 3, 9
    clean, noisy = _current(i_layer, npts, 120.0), _current(i_layer, npts, 120.0, noise=scale, seed=seed, run=run)

    added = noisy["ts_r"][:npts] - clean["ts_r"][:npts]

    expected = [scale * _seeded_noise_sample(seed, i_layer, run, SCAN_NPTS_HISTORY + k, True) for k in range(npts)]
    np.testing.assert_allclose(added, expected, atol=1e-15)


def test_the_first_point_after_a_history_is_the_last_history_point_and_takes_its_noise() -> None:
    # d = 0 of layer i is the end of layer i - 1, the same physical reading: it is drawn once, under the history's index.
    scale, seed, run, i_layer, npts = 0.01, 4, 6, 3, 9
    clean = _current(i_layer, npts, 120.0, n_hist=SCAN_NPTS_HISTORY)
    noisy = _current(i_layer, npts, 120.0, n_hist=SCAN_NPTS_HISTORY, noise=scale, seed=seed, run=run)

    added = noisy["ts_r"][:npts] - clean["ts_r"][:npts]

    assert added[0] == pytest.approx(scale * _seeded_noise_sample(seed, i_layer - 1, run, SCAN_NPTS_HISTORY - 1, True), abs=1e-15)
    assert added[1] == pytest.approx(scale * _seeded_noise_sample(seed, i_layer, run, SCAN_NPTS_HISTORY + 1, True), abs=1e-15)


def test_the_nominal_scan_is_never_noised() -> None:
    noisy = _current(2, 9, 100.0, noise=0.02, seed=1, run=1)
    clean = _current(2, 9, 100.0)

    np.testing.assert_array_equal(noisy["ts_n"], clean["ts_n"])
    assert not np.array_equal(noisy["ts_r"], clean["ts_r"])


# =============================================================================
# _resample_on_machine_grid : the coarse scan read at the machine's cadence
# =============================================================================

DD = 0.125  # the machine reads every 0.125 nm: 240 rpm, 4 readings a second, 0.5 nm/s


def _fine(nominal, i_layer, j0, *, dd=DD, coarse_r=None, coarse_n=None, noise=0.0, seed=0, run=0):
    """Resample the coarse scan of layers j0 .. i_layer (history, then the current one) on the machine grid."""
    nominal = np.asarray(nominal, dtype=float)
    n_hist = SCAN_NPTS_HISTORY * (i_layer - j0)
    size = n_hist + SCAN_NPTS_CURRENT
    ts_r = np.full(size, 0.5) if coarse_r is None else np.array(coarse_r, dtype=float)
    ts_n = np.full(size, 0.25) if coarse_n is None else np.array(coarse_n, dtype=float)
    given = (ts_r.copy(), ts_n.copy())
    out = _resample_on_machine_grid(
        dd, j0, i_layer, nominal[i_layer], n_hist, nominal, nominal * 1.01, ts_r, ts_n, noise > 0.0, noise, seed, run
    )
    return out, given, (ts_r, ts_n)


def _sizes(nominal, i_layer, j0, dd=DD) -> tuple[int, int]:
    m_hist = sum(int(np.ceil(nominal[j] / dd)) for j in range(j0, i_layer))
    return m_hist, m_hist + int(np.ceil(3.0 * nominal[i_layer] / dd)) + 1


@pytest.mark.parametrize("dd", [0.125, 0.2])
@pytest.mark.parametrize("i_layer, j0", [(1, 0), (3, 1), (2, 2)])
def test_the_fine_grid_has_a_reading_every_dd_over_the_history_and_three_thicknesses_of_the_layer(i_layer, j0, dd) -> None:
    nominal = [50.0, 60.0, 42.5, 71.3]

    (ts_r, ts_n, n_tot, stop), _, _ = _fine(nominal, i_layer, j0, dd=dd)

    m_hist, m_tot = _sizes(nominal, i_layer, j0, dd)
    assert n_tot == m_tot and len(ts_r) == len(ts_n) == m_tot
    assert stop == m_hist + int(round(nominal[i_layer] / dd))  # the nominal stop, on the fine grid


def test_smoothing_alone_reads_the_default_grid_of_a_eighth_of_a_nanometre() -> None:
    nominal = [50.0, 60.0]

    (_, _, n_default, stop_default), _, _ = _fine(nominal, 1, 0, dd=0.0)
    (_, _, n_explicit, stop_explicit), _, _ = _fine(nominal, 1, 0, dd=0.125)

    assert (n_default, stop_default) == (n_explicit, stop_explicit)


def test_a_constant_signal_stays_constant_and_the_coarse_scan_is_not_touched() -> None:
    (ts_r, ts_n, _, _), given, after = _fine([50.0, 60.0, 42.5], 2, 0)

    np.testing.assert_allclose(ts_r, 0.5, atol=1e-15)
    np.testing.assert_allclose(ts_n, 0.25, atol=1e-15)
    np.testing.assert_array_equal(after[0], given[0])  # new arrays: the coarse ones are read, never written
    np.testing.assert_array_equal(after[1], given[1])


def test_the_current_layer_is_read_at_its_own_depth() -> None:
    # A ramp in depth on the coarse scan (value = depth in nm) reads back as m * dd on the fine one.
    nominal = [50.0, 60.0]
    n_hist = SCAN_NPTS_HISTORY
    step = 3.0 * nominal[1] / (SCAN_NPTS_CURRENT - 1)
    coarse = np.concatenate([np.zeros(n_hist), np.arange(SCAN_NPTS_CURRENT) * step])

    (ts_r, ts_n, _, _), _, _ = _fine(nominal, 1, 0, coarse_r=coarse, coarse_n=coarse)

    m_hist, m_tot = _sizes(nominal, 1, 0)
    m = np.arange(m_tot - m_hist - 1)  # the last reading falls past the scan: it is extrapolated, not compared
    np.testing.assert_allclose(ts_r[m_hist + m], m * DD, atol=1e-9)
    np.testing.assert_allclose(ts_n[m_hist + m], m * DD, atol=1e-9)


@pytest.mark.xfail(strict=True, reason="D55: a replayed layer is read one coarse step late (d/16), then flat over its last step")
def test_a_replayed_layer_is_read_at_its_own_depth() -> None:
    # The coarse scan of a replayed layer starts at 1/16 of its thickness (0 is the last point of the layer below), the
    # interpolation index starts at 0: a ramp in depth comes back shifted by 1/16, and clamped at 1 over the last 1/16.
    nominal = [50.0, 60.0]
    coarse = np.concatenate([np.arange(1, SCAN_NPTS_HISTORY + 1) / SCAN_NPTS_HISTORY, np.zeros(SCAN_NPTS_CURRENT)])

    (ts_r, _, _, _), _, _ = _fine(nominal, 1, 0, coarse_r=coarse, coarse_n=coarse)

    m = np.arange(int(np.ceil(nominal[0] / DD)))
    np.testing.assert_allclose(ts_r[m], m * DD / nominal[0], atol=1e-2)


def test_the_reading_noise_is_drawn_per_reading_by_layer_and_position_and_never_on_the_nominal_signal() -> None:
    nominal, scale, seed, run = [50.0, 60.0, 42.5], 0.01, 3, 8
    clean = _fine(nominal, 2, 0)[0]
    noisy = _fine(nominal, 2, 0, noise=scale, seed=seed, run=run)[0]

    added = noisy[0] - clean[0]
    m0, m1 = int(np.ceil(nominal[0] / DD)), int(np.ceil(nominal[1] / DD))
    for j, first, count in ((0, 0, m0), (1, m0, m1)):  # a replayed layer j: reading m carries (group j, element m)
        expected = [scale * _seeded_noise_sample(seed, j, run, m, True) for m in range(count)]
        np.testing.assert_allclose(added[first : first + count], expected, atol=1e-15)
    current = m0 + m1
    # The current layer: (group i_layer, element 4096 + m), except its first reading, which is the last one of the layer
    # below and takes ITS draw: one reading is not drawn twice.
    first_draw = scale * _seeded_noise_sample(seed, 1, run, m1 - 1, True)
    assert added[current] == pytest.approx(first_draw, abs=1e-15)
    for m in (1, 2, 40):
        assert added[current + m] == pytest.approx(scale * _seeded_noise_sample(seed, 2, run, 4096 + m, True), abs=1e-15)
    np.testing.assert_array_equal(noisy[1], clean[1])  # the nominal signal is what the strategy expects: nobody measures it


def test_without_a_history_the_first_reading_of_the_layer_is_its_own_draw() -> None:
    nominal, scale, seed, run = [50.0, 60.0], 0.01, 3, 8
    clean = _fine(nominal, 1, 1)[0]
    noisy = _fine(nominal, 1, 1, noise=scale, seed=seed, run=run)[0]

    added = noisy[0] - clean[0]

    assert added[0] == pytest.approx(scale * _seeded_noise_sample(seed, 1, run, 4096, True), abs=1e-15)


# =============================================================================
# _scan_window : which layers are replayed, and how far the current one is swept
# =============================================================================


def _window(block_start, i_layer, *, base=0, nominal_th=50.0, adaptive=False, wl=550.0, n_even=N_EVEN, n_odd=N_ODD):
    j0, n_hist, npts_cur, d_max, n_tot = _scan_window(block_start, i_layer, base, n_even + 0j, n_odd + 0j, nominal_th, adaptive, wl)
    return {"j0": j0, "n_hist": n_hist, "npts_cur": npts_cur, "d_max": d_max, "n_tot": n_tot}


def test_a_layer_alone_replays_nothing_and_is_swept_over_three_thicknesses_in_64_points() -> None:
    for block_start in (-1, 9):  # -1 is the default, and a start past the layer means the same
        got = _window(block_start, 4)

        assert got == {"j0": 4, "n_hist": 0, "npts_cur": SCAN_NPTS_CURRENT, "d_max": D_SCAN_VAL * 50.0, "n_tot": SCAN_NPTS_CURRENT}


def test_a_block_replays_its_layers_before_the_current_one_at_sixteen_points_each() -> None:
    got = _window(2, 5)

    assert got["j0"] == 2 and got["n_hist"] == 3 * SCAN_NPTS_HISTORY
    assert got["n_tot"] == 3 * SCAN_NPTS_HISTORY + SCAN_NPTS_CURRENT


def test_the_history_goes_back_at_most_max_lookback_layers() -> None:
    at_the_limit = _window(9 - MAX_LOOKBACK_VAL, 9)
    one_beyond = _window(9 - MAX_LOOKBACK_VAL - 1, 9)
    far_beyond = _window(0, 9)

    assert at_the_limit["j0"] == one_beyond["j0"] == far_beyond["j0"] == 9 - MAX_LOOKBACK_VAL
    assert far_beyond["n_hist"] == MAX_LOOKBACK_VAL * SCAN_NPTS_HISTORY


def test_a_block_never_starts_below_the_witness_it_is_read_on() -> None:
    # Without the floor `range(witness_base_layer, j0)` would run backwards and the stack under the window would vanish.
    assert _window(1, 4, base=3)["j0"] == 3
    assert _window(1, 4, base=3)["n_hist"] == SCAN_NPTS_HISTORY
    assert _window(1, 4, base=0)["j0"] == 1


@pytest.mark.parametrize("i_layer, n_layer", [(2, N_EVEN), (3, N_ODD)])
def test_the_adaptive_window_is_the_thickness_plus_the_error_margin_plus_half_a_period(i_layer, n_layer) -> None:
    nominal, wl = 80.0, 610.0

    got = _window(-1, i_layer, nominal_th=nominal, adaptive=True, wl=wl)

    half_period = wl / (4.0 * n_layer)  # from an extremum to the next: lambda / 4n
    assert got["d_max"] == pytest.approx(nominal + SCAN_ERROR_MARGIN_NM + half_period)
    density = SCAN_NPTS_CURRENT / (D_SCAN_VAL * nominal)  # the density in points per nm is that of the fixed window
    assert got["npts_cur"] == int(round(density * got["d_max"]))
    assert got["n_tot"] == got["n_hist"] + got["npts_cur"]


def test_the_adaptive_window_of_an_index_of_zero_falls_back_on_one_more_thickness() -> None:
    got = _window(-1, 2, nominal_th=80.0, adaptive=True, n_even=0.0)

    assert got["d_max"] == pytest.approx(80.0 + SCAN_ERROR_MARGIN_NM + 80.0)


def test_a_layer_of_no_thickness_is_swept_with_the_fixed_window_even_when_adaptive() -> None:
    got = _window(-1, 2, nominal_th=0.00005, adaptive=True)

    assert got["npts_cur"] == SCAN_NPTS_CURRENT and got["d_max"] == pytest.approx(D_SCAN_VAL * 0.00005)


# =============================================================================
# _monotonicity_scan and _frozen_trigger_level : what the layer offers, and where the machine will stop it
# =============================================================================


def _stacks_under(i_layer, base=0):
    """The real and the nominal stack under layer `i_layer` (thicknesses differ), and the index of that layer."""
    rng = np.random.default_rng(8)
    th_real, th_nom = rng.uniform(40, 120, 8), rng.uniform(40, 120, 8)
    real = _stack_matrix(WL, N_EVEN, N_ODD, th_real, base, i_layer)
    nominal = _stack_matrix(WL, NOMINAL_EVEN, NOMINAL_ODD, th_nom, base, i_layer)
    return th_real, th_nom, real, nominal, (N_EVEN if i_layer % 2 == 0 else N_ODD)


def _flips(values, tol=1e-9) -> bool:
    """Does the slope of `values` change sign, ignoring the flat parts? (the rule stated in the docstring)"""
    signs = [np.sign(b - a) for a, b in pairwise(values) if abs(b - a) > tol]
    return any(a != b for a, b in pairwise(signs))


@pytest.mark.parametrize("i_layer, base", [(0, 0), (1, 0), (3, 1)])
def test_the_monotonicity_scan_reads_five_depths_of_the_real_stack_from_the_oracle(i_layer, base) -> None:
    th_real, th_nom, real, nominal, n_layer = _stacks_under(i_layer, base)
    nominal_th = 90.0

    non_monotonic, t_mono = _monotonicity_scan(WL, n_layer + 0j, nominal_th, N_SUB + 0j, *real, *nominal)

    layers = [N_EVEN if jj % 2 == 0 else N_ODD for jj in range(base, i_layer + 1)]
    expected = [rt_stack(WL, layers, [*th_real[base:i_layer], k / 4.0 * nominal_th], 1.0, N_SUB)[1] for k in range(5)]
    np.testing.assert_allclose(t_mono, expected, atol=1e-11)
    assert bool(non_monotonic) == _flips(expected)


def test_a_layer_that_stays_under_a_quarter_wave_is_monotonic_and_one_that_crosses_it_is_not() -> None:
    _, _, real, nominal, n_layer = _stacks_under(0)  # the bare substrate under the layer: T falls to a minimum at the quarter wave
    quarter_wave = WL / (4.0 * n_layer)

    short, _ = _monotonicity_scan(WL, n_layer + 0j, 0.6 * quarter_wave, N_SUB + 0j, *real, *nominal)
    crossing, t_mono = _monotonicity_scan(WL, n_layer + 0j, 1.6 * quarter_wave, N_SUB + 0j, *real, *nominal)

    assert not short and crossing
    assert t_mono.min() < t_mono[0]  # it went down and came back up: an extremum was crossed


def test_a_layer_of_no_thickness_has_nothing_to_scan() -> None:
    _, _, real, nominal, n_layer = _stacks_under(2)

    non_monotonic, t_mono = _monotonicity_scan(WL, n_layer + 0j, 0.0, N_SUB + 0j, *real, *nominal)

    assert not non_monotonic
    np.testing.assert_array_equal(t_mono, np.zeros(5))


@pytest.mark.parametrize("i_layer, base", [(0, 0), (2, 0), (3, 1)])
def test_the_trigger_level_is_the_nominal_stack_at_the_nominal_thickness(i_layer, base) -> None:
    th_real, th_nom, real, nominal, n_layer = _stacks_under(i_layer, base)
    nominal_th = 77.0
    n_nominal_layer = NOMINAL_EVEN if i_layer % 2 == 0 else NOMINAL_ODD

    got = _frozen_trigger_level(WL, n_nominal_layer + 0j, nominal_th, N_SUB + 0j, *nominal, 0.123)

    layers = [NOMINAL_EVEN if jj % 2 == 0 else NOMINAL_ODD for jj in range(base, i_layer + 1)]
    expected = rt_stack(WL, layers, [*th_nom[base:i_layer], nominal_th], 1.0, N_SUB)[1]
    assert got == pytest.approx(expected, abs=1e-11)
    assert got != pytest.approx(0.123)  # `T_mono_4` is not read when the layer has a thickness


def test_a_layer_of_no_thickness_stops_at_the_last_point_of_the_scan() -> None:
    _, _, _, nominal, n_layer = _stacks_under(2)

    assert _frozen_trigger_level(WL, n_layer + 0j, 0.0, N_SUB + 0j, *nominal, 0.4321) == 0.4321


# =============================================================================
# _apply_photometric_drift and _running_mean : what the instrument does to the signal
# =============================================================================


def test_the_identity_drift_leaves_the_signal_alone() -> None:
    signal = np.linspace(0.05, 0.95, 12)

    _apply_photometric_drift(signal, len(signal), 1.0, 0.0, 0.0)

    np.testing.assert_array_equal(signal, np.linspace(0.05, 0.95, 12))


@pytest.mark.parametrize("scale, offset, curvature", [(0.98, 0.0, 0.0), (1.0, 0.01, 0.0), (0.95, -0.02, 0.0), (1.0, 0.0, 0.5)])
def test_the_drift_is_an_affine_change_of_T_and_then_the_curvature_no_affine_change_absorbs(scale, offset, curvature) -> None:
    signal = np.linspace(0.05, 0.95, 12)

    drifted = signal.copy()
    _apply_photometric_drift(drifted, len(signal), scale, offset, curvature)

    affine = scale * signal + offset
    np.testing.assert_allclose(drifted, affine + 4.0 * curvature * affine * (1.0 - affine), atol=1e-15)


def test_the_drift_reads_the_first_n_tot_readings_and_nothing_after() -> None:
    signal = np.linspace(0.1, 0.9, 10)

    drifted = signal.copy()
    _apply_photometric_drift(drifted, 6, 0.9, 0.05, 0.3)

    np.testing.assert_array_equal(drifted[6:], signal[6:])
    assert not np.allclose(drifted[:6], signal[:6])


def _running_mean_reference(x: np.ndarray, window: int) -> np.ndarray:
    """The mean of the last `window` readings, of those so far at the start."""
    return np.array([x[max(0, i - window + 1) : i + 1].mean() for i in range(len(x))])


@pytest.mark.parametrize("window", [1, 2, 3, 7, 20, 40])
def test_the_running_mean_is_the_mean_of_the_last_readings_of_each_signal(window) -> None:
    rng = np.random.default_rng(4)
    real, nominal = rng.uniform(0, 1, 30), rng.uniform(0, 1, 30)

    got_r, got_n = real.copy(), nominal.copy()
    _running_mean(got_r, got_n, 30, window)

    np.testing.assert_allclose(got_r, _running_mean_reference(real, window), atol=1e-13)
    np.testing.assert_allclose(got_n, _running_mean_reference(nominal, window), atol=1e-13)


def test_the_running_mean_smooths_the_first_n_tot_readings_only() -> None:
    rng = np.random.default_rng(5)
    real, nominal = rng.uniform(0, 1, 15), rng.uniform(0, 1, 15)

    got_r, got_n = real.copy(), nominal.copy()
    _running_mean(got_r, got_n, 10, 3)

    np.testing.assert_array_equal(got_r[10:], real[10:])
    np.testing.assert_array_equal(got_n[10:], nominal[10:])
    np.testing.assert_allclose(got_r[:10], _running_mean_reference(real[:10], 3), atol=1e-13)


# =============================================================================
# _read_poem_anchors : the turning points, and the two anchors POEM stops on
# =============================================================================

SIGNAL = np.array([0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0])  # maxima at 1 and 5, a minimum at 3


def _anchors(real, nominal, *, i_layer=1, j0=1, stop=6, hysteresis=0.0, poem=True) -> dict:
    names = ("n_tp_real", "n_tp_nom", "margin_missed", "margin_fab", "T_prev_nom", "T_last_nom", "T_prev_real", "T_last_real", "poem_ok")
    real, nominal = np.asarray(real, dtype=float), np.asarray(nominal, dtype=float)
    out = _read_poem_anchors(i_layer, j0, real, nominal, len(real), stop, hysteresis, poem)
    return dict(zip(names, out, strict=True))


def test_the_anchors_are_the_last_two_turning_points_before_the_stop_on_each_signal() -> None:
    real, nominal = 0.5 + 0.20 * SIGNAL, 0.5 + 0.18 * SIGNAL  # the stack drifted: the same shape, another swing

    got = _anchors(real, nominal)

    assert got["n_tp_real"] == got["n_tp_nom"] == 3
    assert (got["T_prev_real"], got["T_last_real"]) == pytest.approx((0.3, 0.7))  # the machine reads them: REAL values
    assert (got["T_prev_nom"], got["T_last_nom"]) == pytest.approx((0.32, 0.68))  # the strategy fixed the fraction on these
    assert got["poem_ok"]


def test_the_stop_cuts_the_anchors_short_and_the_extrema_after_it_are_not_counted() -> None:
    real, nominal = 0.5 + 0.20 * SIGNAL, 0.5 + 0.18 * SIGNAL

    got = _anchors(real, nominal, stop=3)

    assert got["n_tp_real"] == 2  # the maximum at 5 lies beyond the stop
    assert (got["T_prev_real"], got["T_last_real"]) == pytest.approx((0.7, 0.3))


def test_poem_can_be_switched_off_and_the_anchors_are_still_read() -> None:
    real, nominal = 0.5 + 0.20 * SIGNAL, 0.5 + 0.18 * SIGNAL

    got = _anchors(real, nominal, poem=False)

    assert not got["poem_ok"]
    assert got["T_prev_real"] == pytest.approx(0.3)


@pytest.mark.parametrize("real_swing, nominal_swing", [(0.03, 0.30), (0.30, 0.03), (0.03, 0.03)])
def test_poem_needs_a_swing_above_the_floor_on_the_real_and_on_the_nominal_signal(real_swing, nominal_swing) -> None:
    # 0.04, in MEASURED units: below it POEM is ill-conditioned against the reading noise. Both signals are tested.
    got = _anchors(0.5 + real_swing * SIGNAL / 2, 0.5 + nominal_swing * SIGNAL / 2)

    assert not got["poem_ok"]
    assert _anchors(0.5 + 0.30 * SIGNAL / 2, 0.5 + 0.30 * SIGNAL / 2)["poem_ok"]


def test_without_two_turning_points_on_both_signals_there_is_no_anchor_and_nothing_is_read() -> None:
    ramp = np.linspace(0.2, 0.8, 7)

    got = _anchors(0.5 + 0.20 * SIGNAL, ramp)  # the nominal signal has no extremum

    assert not got["poem_ok"]
    assert got["n_tp_nom"] == 0
    assert (got["T_prev_real"], got["T_last_real"], got["T_prev_nom"], got["T_last_nom"]) == (0.0, 0.0, 0.0, 0.0)


def test_the_first_layer_of_the_stack_starts_on_a_turning_point_and_no_other_layer_does() -> None:
    # On the bare substrate T(d) starts stationary: layer 0 of a block that starts at 0 counts its own start.
    valley = np.array([1.0, 0.8, 0.6, 0.4, 0.6, 0.8, 1.0])
    first, later = _anchors(valley, valley, i_layer=0, j0=0), _anchors(valley, valley, i_layer=0, j0=1)

    assert first["n_tp_real"] == first["n_tp_nom"] == later["n_tp_real"] + 1 == later["n_tp_nom"] + 1


def test_the_counting_margins_are_those_of_the_real_signal() -> None:
    real, nominal = 0.5 + 0.20 * SIGNAL, 0.5 + 0.03 * SIGNAL

    got = _anchors(real, nominal, hysteresis=0.05)

    missed, fab = turning_point_margins(real, len(real), 0.05)
    assert (got["margin_missed"], got["margin_fab"]) == pytest.approx((missed, fab))
    assert (missed, fab) != pytest.approx(turning_point_margins(nominal, len(nominal), 0.05))


# =============================================================================
# _level_reachability : is the stopping level between the start of the layer and the next extremum after the stop?
# =============================================================================


def _reach(signal, target, *, n_hist=0, stop=2, hysteresis=0.0):
    signal = np.asarray(signal, dtype=float)
    margin, reached = _level_reachability(signal, len(signal), n_hist, stop, hysteresis, target)
    return margin, bool(reached)


def test_a_level_inside_the_band_is_reached_and_the_margin_is_the_room_to_the_nearer_edge() -> None:
    signal = 0.5 + 0.2 * SIGNAL  # from the stop at 2 the next extremum is the minimum at 3: the band is [0.3, 0.7]

    assert _reach(signal, 0.5) == (pytest.approx(0.2), True)
    assert _reach(signal, 0.6) == (pytest.approx(0.1), True)
    assert _reach(signal, 0.35) == (pytest.approx(0.05), True)


def test_a_level_beyond_the_band_is_not_reached_and_the_margin_says_by_how_much_it_is_missed() -> None:
    signal = 0.5 + 0.2 * SIGNAL

    assert _reach(signal, 0.75) == (pytest.approx(-0.05), False)  # missed by 0.05 above
    assert _reach(signal, 0.25) == (pytest.approx(-0.05), False)  # and below


def test_the_band_ends_at_the_next_extremum_after_the_stop_not_at_the_end_of_the_scan() -> None:
    signal = 0.5 + 0.2 * np.array([0.0, 1.0, 0.0, -1.0, 0.0, 2.0, 0.0])  # a higher maximum at 5 (0.9), after the stop

    assert _reach(signal, 0.8, stop=2)[1] is False  # the machine stops at the next extremum (3), before the 0.9
    assert _reach(signal, 0.8, stop=4)[1] is True  # from 4 the next extremum is the 0.9 itself


def test_the_band_starts_at_the_first_reading_of_the_layer_not_at_the_start_of_the_history() -> None:
    history = [9.0, 9.0]  # two readings of the replayed history: they must not stretch the band
    signal = np.concatenate([history, 0.5 + 0.2 * SIGNAL])

    margin, reached = _reach(signal, 0.5, n_hist=2, stop=4)

    assert reached and margin == pytest.approx(0.2)
    # Near the top of the band the history would show: it would lift the top edge to 9.0 and hide both the margin and a miss.
    assert _reach(signal, 0.65, n_hist=2, stop=4) == (pytest.approx(0.05), True)
    assert _reach(signal, 0.80, n_hist=2, stop=4)[1] is False


def test_there_is_no_tolerance_on_the_edge_of_the_band_beyond_a_picounit() -> None:
    signal = 0.5 + 0.2 * SIGNAL

    assert _reach(signal, 0.7 + 5e-13)[1] is True
    assert _reach(signal, 0.7 + 5e-12)[1] is False


def test_after_the_last_extremum_the_band_runs_to_the_end_of_the_scan() -> None:
    signal = 0.5 + 0.2 * SIGNAL

    assert _reach(signal, 0.6, stop=5)[1] is True  # nothing after 5 but the last reading (0.5)
    assert _reach(signal, 0.9, stop=5)[1] is False


# =============================================================================
# _invert_thickness_from_probes : where the machine stops the layer, read on three probe thicknesses
# =============================================================================

I_LAYER, NOMINAL_TH, PROBE = 1, 60.0, 1.0
TH_UNDER = np.random.default_rng(8).uniform(40, 120, 8)


def _t_of(d: float) -> float:
    """T of the real stack with layer I_LAYER at thickness d, from the independent oracle."""
    return rt_stack(WL, [N_EVEN, N_ODD], [TH_UNDER[0], d], 1.0, N_SUB)[1]


def _error(target, *, scale=1.0, offset=0.0, curvature=0.0, slit=None, probe=PROBE) -> float:
    real = _stack_matrix(WL, N_EVEN, N_ODD, TH_UNDER, 0, I_LAYER)
    return _invert_thickness_from_probes(
        WL, N_ODD + 0j, NOMINAL_TH, probe, N_SUB + 0j, *real, scale, offset, curvature, slit, I_LAYER, target
    )


def test_the_test_setup_is_on_a_slope_not_on_an_extremum() -> None:
    slope = (_t_of(NOMINAL_TH + 0.5) - _t_of(NOMINAL_TH - 0.5)) / 1.0

    assert abs(slope) > 1e-4  # per nm; on an extremum the inversion has nothing to hold on to


@pytest.mark.parametrize("delta", [0.0, 0.4, -0.7, 1.5])
def test_the_error_is_the_distance_from_the_nominal_thickness_to_the_one_that_reaches_the_level(delta) -> None:
    got = _error(_t_of(NOMINAL_TH + delta))

    assert got == pytest.approx(delta, abs=2e-3)  # a parabola through three probes 1 nm apart, on a smooth T(d)


@pytest.mark.parametrize("probe", [0.5, 5.0, 20.0])
def test_the_level_of_the_nominal_thickness_is_inverted_to_no_error_whatever_the_probe_offset(probe) -> None:
    # The parabola passes exactly through the probe AT the nominal thickness: a probe anywhere else would miss it.
    assert _error(_t_of(NOMINAL_TH), probe=probe) == pytest.approx(0.0, abs=1e-7)


@pytest.mark.parametrize("scale, offset", [(0.9574, 0.0), (1.0, 0.02), (0.95, -0.03)])
def test_an_affine_drift_changes_nothing_when_the_level_is_read_with_the_same_instrument(scale, offset) -> None:
    # POEM reports its level on the drifted extrema: the level carries the drift, and so must the probes.
    target = _t_of(NOMINAL_TH + 0.4)

    drifted = _error(scale * target + offset, scale=scale, offset=offset)

    assert drifted == pytest.approx(_error(target), abs=1e-9)
    # In the units of the drifted instrument the target of the ideal one is another equation: the defect of the 2026-08-08.
    assert abs(_error(target, scale=scale, offset=offset) - _error(target)) > 0.5


def test_the_curvature_is_applied_to_the_three_probes_like_the_rest_of_the_drift() -> None:
    target = _t_of(NOMINAL_TH + 0.4)
    scale, offset, curvature = 0.98, 0.01, 0.5
    affine = scale * target + offset
    level = affine + 4.0 * curvature * affine * (1.0 - affine)  # the target as the drifted instrument reads it

    got = _error(level, scale=scale, offset=offset, curvature=curvature)

    assert got == pytest.approx(0.4, abs=2e-2)  # not exact: the curvature is not affine, the parabola only absorbs most of it
    assert abs(_error(level) - 0.4) > 0.5


def test_a_slit_bias_moves_the_probes_and_not_the_level() -> None:
    target = _t_of(NOMINAL_TH + 0.4)
    slope = (_t_of(NOMINAL_TH + 0.5) - _t_of(NOMINAL_TH - 0.5)) / 1.0
    bias = 0.002
    profiles = np.zeros((4, 9))
    profiles[I_LAYER] = bias  # the bias of THIS layer, the same at every depth; the other layers have none

    biased, unbiased = _error(target, slit=profiles), _error(target, slit=np.zeros((4, 9)))

    assert unbiased == pytest.approx(_error(target), abs=1e-12)  # no bias is the same as no profile
    assert biased - unbiased == pytest.approx(-bias / slope, rel=0.05)  # T(d) + bias = level moves the root by -bias / T'


# =============================================================================
# _rate_layer_thickness : a layer laid by turntable turns, from the rate the previous layers of its material gave
# =============================================================================

NOMINAL_RATE = np.array([50.0, 80.0, 50.0, 80.0, 50.0, 80.0])


def _rate(i_layer, real, *, flags=None, nominal=NOMINAL_RATE):
    got, thickness = _rate_layer_thickness(i_layer, np.asarray(real, dtype=float), np.asarray(nominal, dtype=float), flags)
    return bool(got), thickness


def test_a_rate_layer_is_laid_for_the_turns_the_average_ratio_of_its_material_commands() -> None:
    # The two previous layers of the same material came out 10 % thin: A = 50 / 45. The rate believes the machine is fast by A.
    real = [45.0, 72.0, 45.0, 72.0, 0.0, 0.0]

    got, thickness = _rate(4, real)

    assert got
    assert thickness == pytest.approx(50.0 / (50.0 / 45.0))  # d_nominal / A, to the turn
    assert thickness / RATE_TURN_NM == pytest.approx(round(thickness / RATE_TURN_NM))  # a whole number of turns


def test_only_the_layers_of_the_same_material_count() -> None:
    steady = _rate(4, [45.0, 72.0, 45.0, 72.0, 0.0, 0.0])
    other_material_wild = _rate(4, [45.0, 5.0, 45.0, 500.0, 0.0, 0.0])

    assert steady == other_material_wild


def test_a_layer_that_was_itself_laid_by_rate_is_not_a_reference() -> None:
    # It was laid blind from the current estimate: its ratio IS the estimate, and taking it back would be quoting oneself.
    real = [45.0, 72.0, 30.0, 72.0, 0.0, 0.0]  # layer 2 came out very thin, but by rate
    flags = np.array([False, False, True, False, False, False])

    with_flags = _rate(4, real, flags=flags)
    without = _rate(4, real)

    assert with_flags == (True, pytest.approx(45.0))  # layer 0 alone: A = 50 / 45
    assert without[1] == pytest.approx(50.0 / ((50.0 / 45.0 + 50.0 / 30.0) / 2))
    assert with_flags[1] != pytest.approx(without[1])


def test_a_flag_array_shorter_than_the_stack_flags_nothing_beyond_its_end() -> None:
    real = [45.0, 72.0, 30.0, 72.0, 0.0, 0.0]

    assert _rate(4, real, flags=np.array([False])) == _rate(4, real)
    # Layer 0 is flagged, layer 2 lies beyond the end of the flags: it is a reference, and only it (A = 50 / 30).
    assert _rate(4, real, flags=np.array([True])) == (True, pytest.approx(30.0))


@pytest.mark.parametrize("i_layer", [0, 1])
def test_a_layer_with_no_layer_of_its_material_before_it_has_no_rate(i_layer) -> None:
    assert _rate(i_layer, [45.0, 72.0, 45.0, 72.0, 45.0, 72.0]) == (False, 0.0)


def test_when_every_reference_was_laid_by_rate_or_has_no_thickness_there_is_no_rate() -> None:
    assert _rate(4, [45.0, 72.0, 45.0, 72.0, 0.0, 0.0], flags=np.array([True, False, True, False, False, False])) == (False, 0.0)
    assert _rate(4, [0.0, 72.0, 0.0, 72.0, 0.0, 0.0]) == (False, 0.0)  # nothing was deposited: no ratio to average


def test_a_rate_layer_is_laid_for_at_least_one_turn() -> None:
    nominal = NOMINAL_RATE.copy()
    nominal[4] = 0.01  # a hundredth of a nanometre: zero turns, rounded up to one

    assert _rate(4, [50.0, 80.0, 50.0, 80.0, 0.0, 0.0], nominal=nominal) == (True, pytest.approx(RATE_TURN_NM))


def test_the_thickness_of_a_rate_layer_is_rounded_to_a_whole_turn() -> None:
    nominal = NOMINAL_RATE.copy()
    nominal[4] = 50.075  # 400.6 turns at A = 1: rounded to the nearest turn, not cut down

    assert _rate(4, [50.0, 80.0, 50.0, 80.0, 0.0, 0.0], nominal=nominal) == (True, pytest.approx(401 * RATE_TURN_NM))
