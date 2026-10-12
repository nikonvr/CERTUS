"""k of a Tauc-Lorentz-Urbach film is exact where e2 is far below e1 (D71).

k was sqrt((|eps| - e1) / 2): a difference of two numbers equal to the last bit as soon as e2 < ~1e-7, so k came back as 0 or a few
per mille off. 2nk = e2 gives it without the difference.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_optical_models import epsilon_to_nk


@pytest.mark.parametrize("e2", [1e-12, 1e-10, 1e-8, 1e-6, 1e-4])
def test_k_is_e2_over_2n_far_below_the_gap(e2) -> None:
    e1 = np.array([4.0, 5.5, 2.2])
    e2s = np.full(3, e2)
    n, k, _ = epsilon_to_nk(e1, e2s, 0.5, 15.0, 15.0)

    assert np.allclose(k, e2s / (2.0 * n), rtol=1e-12, atol=0.0)


def test_n_and_k_square_back_to_the_permittivity() -> None:
    e1 = np.array([1.5, 4.0, 6.0, 9.0])
    e2 = np.array([0.0, 1e-9, 0.3, 2.5])
    n, k, _ = epsilon_to_nk(e1, e2, 0.5, 15.0, 15.0)

    assert np.allclose(n * n - k * k, e1, rtol=1e-12)
    assert np.allclose(2.0 * n * k, e2, rtol=1e-9, atol=1e-18)


def test_k_stays_positive_for_a_negative_e2_and_for_a_negative_e1() -> None:
    _n, k, _ = epsilon_to_nk(np.array([4.0, -2.0]), np.array([-1e-3, 0.5]), 0.0, 15.0, 15.0)

    assert np.all(k >= 0.0)
