"""The METAL BILAYER beam analysis, and the analytic gradient it runs on.

The analytic gradient (compute_metal_bilayer_gradient_analytic) sliced each spline family
with num_knots + 1 values, while the bilayer objective, its bounds and the optimum handed
to the beam hold num_knots. Every scan step of the beam then raised ValueError inside the
spline evaluation; the worker caught it, logged "Error at ...", and kept the optimum alone.
The beam reported a thickness and an index of zero spread -- a result that looked real.
Measured on the example before the fix: 20 scan steps raised, 1 solution kept.

Both tests use the example of the module and one real BILAYER optimum of it, frozen below.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

from gradient_harness import check_gradient  # noqa: E402

from certus.metal.certus_metal_bilayer_physics import _build_bilayer_bounds  # noqa: E402
from certus.physics.gradient_metal import compute_metal_bilayer_gradient_analytic  # noqa: E402
from certus.utils.certus_data import load_spectrum_columns  # noqa: E402
from certus_physics import (  # noqa: E402
    calculate_reflectance_bilayer_vectorized,
    get_nk_cauchy_simple,
    get_nk_from_spline,
    get_nk_si,
)

NUM_KNOTS = 4
MIN_KNOT_DIST = 20.0
#: One BILAYER optimization of the example (JSON-metal-bilayer-example.json), frozen:
#: [eM, eL, n_inf, A, n x 4, k x 4, lambda x 2] -- the layout of the bilayer objective.
X_OPT = np.array([float.fromhex(h) for h in (
    "0x1.55f7884a4abc5p+3 0x1.be62042bb5b0ap+9 0x1.70199844541bdp+0 0x1.1ebfd2ecc7524p+12 "
    "0x1.1c193340b3684p+1 0x1.687bcb7a74005p+1 0x1.90e47329c9c46p+1 0x1.af011bb157957p+1 "
    "0x1.95f4856174c7dp+0 0x1.8ef4c5a5fe49dp+0 0x1.6cb3d97aee381p+0 0x1.58fa6952420abp+0 "
    "0x1.ea9040a4de3d0p+8 0x1.3ba64c9752ff9p+9"
).split()])
#: Its objective value (reflectance MSE plus the objective's smoothing penalty).
FUN_OPT = float.fromhex("0x1.45f76dd858457p-18")


def _example() -> tuple[np.ndarray, np.ndarray]:
    """The BILAYER example spectrum, within the wavelength filter of its configuration."""
    res = load_spectrum_columns(
        str(ROOT / "example" / "example_metal_bilayer" / "CSV-metal-example.csv"),
        max_columns=2,
        normalise_percent=True,
        sort_ascending=True,
        column_roles={0: "lambda", 1: "R"},
    )
    lam = np.asarray(res.x, dtype=np.float64)
    keep = (lam >= 350.0) & (lam <= 880.0)
    return (
        np.ascontiguousarray(lam[keep]),
        np.ascontiguousarray(np.asarray(res.y_columns["R"], dtype=np.float64)[keep]),
    )


def _params() -> dict:
    """The bounds of JSON-metal-bilayer-example.json, as the application reads them."""
    return {
        "num_knots": NUM_KNOTS,
        "eM_min": 10.0,
        "eM_max": 30.0,
        "eL_nominal": 900.0,
        "eL_variation": 20.0,
        "n_infini_bounds": (1.42, 1.44),
        "A_diel_bounds": (0.0, 10000.0),
        "nk_min": 1.0,
        "nk_max": 5.0,
        "min_knot_dist": MIN_KNOT_DIST,
    }


@pytest.mark.unit
def test_the_gradient_reads_x_like_the_bilayer_objective() -> None:
    lam, r_target = _example()
    assert X_OPT.size == len(_build_bilayer_bounds(_params(), l_array=lam, include_eM=True)), (
        "the frozen optimum is not in the layout of the bilayer objective"
    )
    n_sub = get_nk_si(lam)

    cost, grad = compute_metal_bilayer_gradient_analytic(X_OPT, NUM_KNOTS, lam, r_target, MIN_KNOT_DIST, n_sub)
    grad = np.asarray(grad)
    assert grad.shape == X_OPT.shape, "the gradient does not cover the parameter vector"

    # Its cost is the reflectance MSE of the SAME stack the objective builds from x: the spline
    # of num_knots values per family on [l_min, inner lambdas, l_max], Cauchy SiO2, Si substrate.
    k0 = 4 + 2 * NUM_KNOTS
    knots = np.concatenate(([lam.min()], np.sort(X_OPT[k0:]), [lam.max()]))
    n, k = get_nk_from_spline(X_OPT[4:k0], knots, lam, use_cache=False)
    reflectance = calculate_reflectance_bilayer_vectorized(
        lam, n - 1j * k, float(X_OPT[0]), float(X_OPT[1]), get_nk_cauchy_simple(lam, X_OPT[2], X_OPT[3]) + 0j, n_sub
    )
    assert cost == pytest.approx(float(np.mean((reflectance - r_target) ** 2)), rel=1e-9)

    # And the gradient is the derivative of that cost, family by family (standard of
    # tests/oracle/test_metal_gradient_vs_fd.py: the lambda gradients are themselves FD).
    check_gradient(
        lambda p: compute_metal_bilayer_gradient_analytic(p, NUM_KNOTS, lam, r_target, MIN_KNOT_DIST, n_sub),
        X_OPT,
        step=1e-6,
        rtol=2e-3,
        blocks=[(0, 2), (2, 4), (4, 4 + NUM_KNOTS), (4 + NUM_KNOTS, k0), (k0, X_OPT.size)],
        label="gradient metal bicouche, exemple",
    )


class _ScanErrors(logging.Handler):
    """Counts the scan steps the beam worker reports as failed ("Error at ...")."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage().startswith("Error at"):
            self.messages.append(record.getMessage())


@pytest.mark.unit
def test_the_beam_keeps_more_than_the_optimum_on_the_example(qapp) -> None:
    from certus.metal.certus_metal_bilayer_app import BeamAnalysisWorker

    lam, r_target = _example()
    params = _params() | {"target_lambda": lam, "target_r": r_target}
    stats: dict = {}
    errors = _ScanErrors()
    worker_logger = logging.getLogger("CertusMetal")
    worker_logger.addHandler(errors)
    try:
        # The application scans every 0.5 nm; 2 nm keeps the test short on the same path.
        worker = BeamAnalysisWorker(params, X_OPT.copy(), FUN_OPT, step_nm=2.0, mse_tolerance=0.2)
        worker.finished.connect(stats.update)
        worker.error.connect(lambda message: stats.update(error=message))
        worker.run()
    finally:
        worker_logger.removeHandler(errors)

    assert "error" not in stats, stats.get("error")
    assert not errors.messages, f"{len(errors.messages)} scan step(s) raised, first: {errors.messages[0]}"
    assert stats["count"] > 1, "the beam kept the optimum alone: its spread would read as zero uncertainty"
    assert stats["eM_max"] > stats["eM_min"]
