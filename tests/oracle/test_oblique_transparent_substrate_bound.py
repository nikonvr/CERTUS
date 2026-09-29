"""What the oblique plate kernels lose by reading the substrate as transparent, against the oracle.

`OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX` is the absorption above which the plate kernels (the ones that
build an incoherent plate with a back side) say that they ignore the substrate's. This file ties it to
a measure instead of a feeling: below it the error on R stays under 1e-3 for every angle and both
polarizations, above it (a metal) the error is one or two orders of magnitude larger, which is what
the warning is for.

`tests/oracle/tmm_reference.py` reads the complex substrate (Macleod, chap. 2.10). The kernel measured
here is `compute_oblique_rt_and_grads_analytic` in its forward direction (air -> stack -> substrate),
the one the plate combination starts from; it receives the same index and keeps its real part. The
kernels that end on a semi-infinite substrate (`calc_spectrum_oblique_vectorized`, the gradient
contribution) read the complex index and agree with the oracle to 1e-12:
`test_oblique_absorbing_substrate.py`.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from tmm_reference import rt_stack_oblique

ANGLES = (20.0, 45.0, 60.0, 80.0)
NO_LAYERS = np.zeros((1, 0), dtype=np.complex128)


def _worst_error_on_r(n: float, k: float) -> float:
    from certus.physics.gradient_oblique import compute_oblique_rt_and_grads_analytic

    worst = 0.0
    with warnings.catch_warnings():
        # The kernel says that it reads the real part: that is what is measured here.
        warnings.simplefilter("ignore")
        for angle in ANGLES:
            for polarization in ("s", "p"):
                r, _t, _dr, _dt = compute_oblique_rt_and_grads_analytic(
                    np.zeros(0),
                    NO_LAYERS,
                    np.array([complex(n, -k)]),
                    np.array([600.0]),
                    np.zeros(0, dtype=np.int64),
                    angle,
                    polarization == "s",
                    False,
                )
                r_ref, _ = rt_stack_oblique(
                    600.0, np.zeros(0, dtype=np.complex128), np.zeros(0), angle, polarization == "s", 1 + 0j, complex(n, -k)
                )
                worst = max(worst, abs(float(r[0]) - r_ref))
    return worst


@pytest.mark.parametrize("n", [1.5, 2.5, 3.5, 4.5])
def test_below_the_bound_the_transparent_reading_costs_less_than_1e_3(n) -> None:
    from certus.physics.certus_oblique_substrate import OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX

    assert _worst_error_on_r(n, OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX) < 1e-3


def test_a_metal_like_substrate_is_far_beyond_the_bound() -> None:
    assert _worst_error_on_r(1.7, 1.11) > 0.05


def test_a_lossless_substrate_is_read_exactly() -> None:
    assert _worst_error_on_r(1.52, 0.0) < 1e-12
