"""The oblique PLATE kernels read the substrate as transparent, and say so when it matters.

The oblique kernels of `certus/physics` that end on a semi-infinite substrate (the spectrum of a front
stack and the analytic gradient of DESIGN's objective built from it) read the complex substrate:
`tests/oracle/test_oblique_absorbing_substrate.py`. The ones that build an incoherent plate with a back
side (the substrate is then the middle medium: internal reflections, and the loss along the plate) keep
the real part of the index and drop the absorption: « transparent exit approximation », written in a
comment of one kernel and nowhere the operator could see it. For a dielectric it costs less than 1e-3 on
R; for a substrate that absorbs it costs up to 0.25 (an index of 1.7 - 1.11i at 30 degrees: 0.22 on R
under a layer of 2.3 x 100 nm, measured against `tests/oracle/tmm_reference.py`). The spectrum on screen and the objective agree with
one another, both wrong in the same way, so nothing looks off.

Until the plate kernels take the complex substrate too, each of their entry points says it once per
process, in the log and as a warning, when the substrate absorbs beyond
`OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX`. The entry points that read the absorption, and normal incidence,
are not concerned.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pytest

WLS = np.array([500.0, 600.0, 700.0])
ABSORBING = np.full(3, complex(1.7, -1.11))
TRANSPARENT = np.full(3, complex(1.52, 0.0))
LAYERS = np.full((3, 1), complex(2.3, 0.0))
THICKNESS = np.array([100.0])


@pytest.fixture(autouse=True)
def _say_it_again(monkeypatch):
    import certus.physics.certus_oblique_substrate as module

    monkeypatch.setattr(module, "_reported", False)


def _entry_points(n_sub, angle=45.0):
    from certus.physics.certus_tmm_oblique import (
        calc_spectrum_full_oblique_exact,
        calc_spectrum_oblique_backside_vectorized,
        calc_spectrum_oblique_vectorized,
    )
    from certus.physics.gradient_oblique import (
        compute_oblique_backside_bundle_analytic,
        compute_oblique_gradient_contrib_analytic,
        compute_oblique_rt_and_grads_analytic,
    )
    from certus.workers.certus_design_worker_utils import optim_calc_oblique_selected

    var = np.array([0], dtype=np.int64)
    back = np.zeros((3, 0), dtype=np.complex128)

    def selected(has_back_calc):
        return optim_calc_oblique_selected(
            WLS,
            LAYERS,
            THICKNESS,
            n_sub,
            angle,
            "s",
            has_back_calc=has_back_calc,
            has_back_stack=has_back_calc,
            d_back=np.zeros(0),
            n_back_T=back,
            calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
            calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
            calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
        )

    return {
        "spectrum": lambda: calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, n_sub, angle, "s"),
        "spectrum with backside": lambda: calc_spectrum_oblique_backside_vectorized(
            WLS, LAYERS, THICKNESS, n_sub, angle, "p"
        ),
        "selected by the optimizer, with a back side": lambda: selected(True),
        "selected by the optimizer, front only": lambda: selected(False),
        "gradient contribution": lambda: compute_oblique_gradient_contrib_analytic(
            THICKNESS, LAYERS, n_sub, WLS, np.full(3, 0.5), np.ones(3), angle, True, True, var
        ),
        "R, T and gradients": lambda: compute_oblique_rt_and_grads_analytic(
            THICKNESS, LAYERS, n_sub, WLS, var, angle, True, False
        ),
        "backside bundle": lambda: compute_oblique_backside_bundle_analytic(
            THICKNESS, LAYERS, n_sub, WLS, var, angle, True, None, None
        ),
    }


#: The plate kernels: they read the real part of the substrate, and say it.
PLATE_ENTRY_POINTS = [
    "spectrum with backside",
    "selected by the optimizer, with a back side",
    "R, T and gradients",
    "backside bundle",
]

#: The kernels that end on a semi-infinite substrate: they read its absorption.
FRONT_ENTRY_POINTS = [
    "spectrum",
    "selected by the optimizer, front only",
    "gradient contribution",
]


@pytest.mark.parametrize("name", PLATE_ENTRY_POINTS)
def test_an_absorbing_substrate_is_reported_by_every_plate_entry_point(name) -> None:
    call = _entry_points(ABSORBING)[name]

    with pytest.warns(UserWarning, match="substrate is read as transparent"):
        call()


@pytest.mark.parametrize("name", FRONT_ENTRY_POINTS)
def test_an_absorbing_substrate_read_by_the_front_kernels_is_not_reported(name) -> None:
    call = _entry_points(ABSORBING)[name]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        call()


@pytest.mark.parametrize("name", PLATE_ENTRY_POINTS + FRONT_ENTRY_POINTS)
def test_a_transparent_substrate_is_not_reported(name) -> None:
    call = _entry_points(TRANSPARENT)[name]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        call()


def test_a_substrate_at_the_bound_is_not_reported() -> None:
    from certus.physics.certus_oblique_substrate import OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX

    call = _entry_points(np.full(3, complex(3.5, -OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX)))["spectrum with backside"]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        call()


def test_normal_incidence_reads_the_complex_index_and_is_not_reported() -> None:
    call = _entry_points(ABSORBING, angle=0.0)["spectrum"]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        call()


def test_it_is_said_once_per_process_in_the_log_and_as_a_warning() -> None:
    calls = _entry_points(ABSORBING)
    lines: list[str] = []

    class Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    # The test session keeps the application logger at CRITICAL: lower it for the length of the call.
    logger = logging.getLogger("CERTUS")
    handler = Handler(logging.WARNING)
    level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            calls["spectrum with backside"]()
            calls["backside bundle"]()
            calls["R, T and gradients"]()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)

    assert len([w for w in caught if "transparent" in str(w.message)]) == 1
    [line] = [line for line in lines if "transparent" in line]
    assert "1.11" in line
