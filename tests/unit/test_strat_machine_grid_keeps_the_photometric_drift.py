"""D54: on the machine grid without smoothing, the photometric drift still distorts the readings.

`simulate_growth_kernel` applied the drift (gain, offset, curvature) to the readings on the coarse grid, and on the fine
grid only inside the smoothing branch: with `machine_sampling_dd > 0` and `smoothing_window == 1` the readings carried
none, while the inversion of the stop still did. Measured on 2026-10-06, one layer, curvature at its specified
amplitude: the coarse grid stopped at 52.523 nm instead of 53.190, the fine grid at 54.407 -- the other way -- and its
level margin did not move. Now both stop at 52.52 nm and both margins move alike.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_growth import PHOTOMETRIC_CURVATURE_AMP, simulate_growth_kernel

QWOT_500 = np.array([53.19, 85.62, 53.19, 85.62, 53.19, 85.62], dtype=np.float64)


def _grow(curv: float, dd: float, smoothing: int = 1) -> tuple:
    return simulate_growth_kernel(
        QWOT_500, 4, np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64), 540.0,
        2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
        1.0, 0.0, 2.0, 0, 0, 0.0, 0, 0, 0.0,
        1.0, 0.0, curv, True, smoothing, -1.0, -1.0, False, None, 0, dd,
    )  # fmt: skip


def test_the_curvature_moves_the_machine_grid_as_it_moves_the_coarse_grid():
    coarse = _grow(PHOTOMETRIC_CURVATURE_AMP, 0.0)[0]
    fine = _grow(PHOTOMETRIC_CURVATURE_AMP, 0.125)[0]

    assert fine == pytest.approx(coarse, abs=0.01)  # the two grids sample the same signal, 0.125 nm apart at most


def test_the_curvature_reaches_the_readings_of_the_machine_grid():
    margin_flat = _grow(0.0, 0.125)[2]
    margin_curved = _grow(PHOTOMETRIC_CURVATURE_AMP, 0.125)[2]

    assert margin_curved != pytest.approx(margin_flat, rel=1e-6)
