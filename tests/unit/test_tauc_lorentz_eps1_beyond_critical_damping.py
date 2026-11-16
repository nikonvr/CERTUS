"""The Tauc-Lorentz closed form of eps1 (Jellison-Modine) holds for C >= 2 E0 too (overdamped oscillator).

alpha = sqrt(4 E0^2 - C^2) is imaginary there. The kernels clamped 4 E0^2 - C^2 at 1e-12 instead, and eps1 came out
wrong without a word: 0.41 off Kramers-Kronig at Eg 1.331, E0 3.074, C 7, the gap seen once on an H800 fit
(ETAT section 5). INDEX lets C reach 10 eV with E0 down to about 1.6 eV, so a fit can land there.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tauc_lorentz_kernels_match_kramers_kronig_and_finite_differences import kramers_kronig_eps1  # noqa: E402

from certus.physics.certus_optical_models import epsilon1_TL_analytic  # noqa: E402
from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel  # noqa: E402

# (Eg, A, E0, C, eps_inf), all with C > 2 E0
OVERDAMPED = {
    "H800 gap": (1.331, 10.0, 3.074, 7.0, 4.276),
    "strong": (1.331, 300.0, 3.074, 10.0, 4.276),
    "just over": (2.5, 50.0, 3.2, 6.45, 2.0),
    "low E0": (0.8, 100.0, 1.6, 9.0, 1.5),
}
ENERGIES = np.array([0.25, 0.6, 1.0, 1.3, 2.0, 3.5, 6.0])


@pytest.mark.parametrize("name", sorted(OVERDAMPED))
def test_eps1_matches_kramers_kronig_when_c_exceeds_twice_e0(name: str) -> None:
    Eg, A, E0, C, eps_inf = OVERDAMPED[name]
    closed = epsilon1_TL_analytic(ENERGIES, Eg, A, E0, C, eps_inf)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kk = np.maximum(np.array([kramers_kronig_eps1(e, Eg, A, E0, C, eps_inf) for e in ENERGIES]), 1.0)

    np.testing.assert_allclose(closed, kk, rtol=2e-5, atol=1e-6)


@pytest.mark.parametrize("name", sorted(OVERDAMPED))
def test_the_gradient_kernel_agrees_with_eps1_and_its_finite_differences(name: str) -> None:
    Eg, A, E0, C, eps_inf = OVERDAMPED[name]
    grad = _compute_epsilon1_gradient_kernel(ENERGIES, Eg, A, E0, C, eps_inf)
    np.testing.assert_allclose(grad[0], epsilon1_TL_analytic(ENERGIES, Eg, A, E0, C, eps_inf), rtol=1e-12)

    params = [Eg, A, E0, C, eps_inf]
    for row, index in ((1, 0), (2, 1), (3, 2), (4, 3), (6, 4)):
        h = 1e-5 * max(abs(params[index]), 1.0)
        up, down = list(params), list(params)
        up[index] += h
        down[index] -= h
        fd = (epsilon1_TL_analytic(ENERGIES, *up) - epsilon1_TL_analytic(ENERGIES, *down)) / (2.0 * h)
        np.testing.assert_allclose(grad[row], fd, rtol=1e-4, atol=1e-6, err_msg=f"row {row}")
