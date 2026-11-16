"""The Urbach tail of the TLU model joins the Tauc-Lorentz absorption where it is anchored (audit 2026-11-15, L1-m6; D71).

The tail is anchored at Eg + delta (delta = 0.01 eV) but replaced the Tauc-Lorentz part only below Eg: eps2 fell from
1.9e-4 at Eg to 2.3e-8 just above it, then rose again up to Eg + delta: a jump of a factor 8000 and a dip, in the model
and in its gradient. Both now switch at Eg + delta, where the two parts are equal (owner's decision of 2026-11-16).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_optical_models import epsilon2_TLU_array
from certus.physics.gradient_analytic import _compute_epsilon2_gradient_kernel

Eg, A, E0, C, Eu = 3.0, 100.0, 4.0, 1.0, 0.05
DELTA = 0.01


def test_eps2_is_continuous_and_rising_across_the_edge() -> None:
    E = np.linspace(Eg - 0.05, Eg + 0.05, 2001)
    eps2 = epsilon2_TLU_array(E, Eg, A, E0, C, Eu)
    assert np.all(np.diff(eps2) >= -1e-15), "eps2 is not monotone across the edge"
    jumps = np.abs(np.diff(eps2)) / np.maximum(eps2[1:], 1e-300)
    assert float(np.max(jumps)) < 0.01, "eps2 jumps across the edge"


def test_the_two_parts_meet_at_the_anchor() -> None:
    below, above = epsilon2_TLU_array(np.array([Eg + DELTA - 1e-9, Eg + DELTA + 1e-9]), Eg, A, E0, C, Eu)
    assert below == pytest.approx(above, rel=1e-5)


def test_the_gradient_kernel_returns_the_same_eps2() -> None:
    E = np.linspace(Eg - 0.05, Eg + 0.05, 401)
    np.testing.assert_allclose(_compute_epsilon2_gradient_kernel(E, Eg, A, E0, C, Eu)[0], epsilon2_TLU_array(E, Eg, A, E0, C, Eu), rtol=1e-12)


def test_far_from_the_edge_nothing_changes() -> None:
    E = np.array([1.0, 2.0, 3.5, 5.0])
    expected = np.where(
        E > Eg,
        A * E0 * C * (E - Eg) ** 2 / (E * ((E * E - E0 * E0) ** 2 + C * C * E * E)),
        epsilon2_TLU_array(E, Eg, A, E0, C, Eu),
    )
    np.testing.assert_allclose(epsilon2_TLU_array(E, Eg, A, E0, C, Eu), expected, rtol=1e-13)
