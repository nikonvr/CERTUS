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
from tmm_reference import stack_matrix  # noqa: E402

from certus.physics.certus_strat_growth import _stack_matrix, _stack_matrix_pair  # noqa: E402

pytestmark = pytest.mark.kernels

N_EVEN, N_ODD = 2.35, 1.46


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
