"""The tabulated indices of RE follow Macleod's n - ik, like every stack kernel (CLAUDE.md, interdit 6).

    AGAINST THE INDEPENDENT REFERENCE: an absorbing tabulated layer at 45 deg, s and p, gives the R and T of
        tests/oracle/tmm_reference.py; with n + ik, T was off by up to 0.29 and R + T reached 1.12
    THE SIGN: k >= 0 in the table, a non-positive imaginary part in the index
    A TABLE WITHOUT ABSORPTION gives the same bits as before: its zero imaginary part stays +0.0
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.utils.certus_re_helpers import TabularMaterial, _re_calc_spectrum_for_config
from tests.oracle import tmm_reference as ref

WLS = np.linspace(500.0, 700.0, 9)


def _absorbing() -> TabularMaterial:
    return TabularMaterial(np.array([400.0, 800.0]), np.array([2.0, 2.0]), np.array([0.05, 0.05]), l0_ref=600.0)


@pytest.mark.parametrize("pol", ["s", "p"])
def test_an_absorbing_tabulated_layer_matches_the_reference_at_45_degrees(pol):
    n_layers = np.column_stack([_absorbing().get_nk(WLS), np.full(WLS.size, 1.46 + 0j)])
    R, T = _re_calc_spectrum_for_config(
        WLS, n_layers, np.array([200.0, 120.0]), np.full(WLS.size, 1.5 + 0j), 45.0, pol, False
    )
    expected = np.array(
        [ref.rt_stack_oblique(w, [2.0 - 0.05j, 1.46 + 0j], [200.0, 120.0], 45.0, pol == "s", 1.0 + 0j, 1.5 + 0j) for w in WLS]
    )
    assert R == pytest.approx(expected[:, 0], abs=1e-12)
    assert T == pytest.approx(expected[:, 1], abs=1e-12)
    assert np.all(R + T <= 1.0)


def test_the_tabulated_index_has_a_non_positive_imaginary_part():
    assert np.all(_absorbing().get_nk(WLS).imag == -0.05)


def test_a_table_without_absorption_keeps_a_positive_zero():
    nk = TabularMaterial(np.array([400.0, 800.0]), np.array([1.46, 1.45]), None, l0_ref=600.0).get_nk(WLS)
    assert not np.any(np.signbit(nk.imag))
