"""The sub-kernels cut out of `simulate_growth_kernel` (plan S5.1) each do what their name says.

The 1 190 lines of `simulate_growth_kernel` are being cut into named pieces, one per commit, each proved bit for bit on
the STRAT corpus of `scripts/c1_diff.py`. That proof says the kernel still returns the same bits; it does not say that a
piece does what its name promises, and the next person to touch one of them needs it read on its own, from Python, where
Numba compiles it as an ordinary function. One test group per piece, against the INDEPENDENT oracle
(`tests/oracle/tmm_reference.py`, never against the kernel: prohibition 7) or against rules worked out by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack, stack_matrix  # noqa: E402

from certus.physics.certus_strat_growth import (  # noqa: E402
    SCAN_NPTS_CURRENT,
    SCAN_NPTS_HISTORY,
    _fill_current_signal,
    _fill_history_signal,
    _resample_on_machine_grid,
    _stack_matrix,
    _stack_matrix_pair,
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
