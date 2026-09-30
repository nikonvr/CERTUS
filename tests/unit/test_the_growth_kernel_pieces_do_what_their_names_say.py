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
    SCAN_NPTS_HISTORY,
    _fill_history_signal,
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
