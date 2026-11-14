"""DESIGN weighs each target band by its own width in ln(lambda), whatever the gap between two bands.

The spectral weights are the trapezoidal widths of each point in ln(lambda). DESIGN lays one grid over the union of its
targets: between two separate bands, the point beside the gap took half of the gap as its width. Measured on
2026-11-13 with the grid of `_get_optim_wls` (108 points per target): 400-500 and 1000-1100 nm, the two points beside
the gap held 68.6 % of the total weight, so the optimizer worked almost only at 500 and 1000 nm.
`spectral_rmse_weights_banded` cuts the grid at such a gap; one band, or bands that touch, keep the very same weights.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.domain.spectral_weights import spectral_rmse_weights, spectral_rmse_weights_banded
from certus_physics import Target, prepare_targets_vectorized


def grid(bands: list[tuple[float, float]], points: int = 108) -> np.ndarray:
    """The grid of `_get_optim_wls`: per band, uniform in wavenumber, then the sorted union."""
    return np.unique(np.concatenate([1.0 / np.linspace(1.0 / hi, 1.0 / lo, points) for lo, hi in bands]))


def band_share(weights: np.ndarray, lam: np.ndarray, lo: float, hi: float) -> float:
    inside = (lam >= lo) & (lam <= hi)
    return float(weights[inside].sum() / weights.sum())


@pytest.mark.parametrize("bands", [[(400.0, 500.0), (600.0, 700.0)], [(400.0, 500.0), (1000.0, 1100.0)]])
def test_the_points_beside_a_gap_weigh_like_their_neighbours(bands):
    lam = grid(bands)
    targets = [Target(lmin=lo, lmax=hi, tmin=0.5, tmax=0.5, w=1.0, on=True) for lo, hi in bands]
    _vals, weights = prepare_targets_vectorized(lam, targets)
    edge = int(np.flatnonzero(lam <= bands[0][1])[-1])  # last point of the first band, then first of the second
    assert weights[edge] < 1.05 * weights[edge - 1]
    assert weights[edge + 1] < 1.05 * weights[edge + 2]
    widths = [np.log(hi / lo) for lo, hi in bands]
    for (lo, hi), width in zip(bands, widths, strict=True):
        assert band_share(weights, lam, lo, hi) == pytest.approx(width / sum(widths), rel=0.02)


def test_the_weights_still_sum_to_the_number_of_points():
    lam = grid([(400.0, 500.0), (1000.0, 1100.0)])
    assert spectral_rmse_weights_banded(lam, [(400.0, 500.0), (1000.0, 1100.0)]).sum() == pytest.approx(lam.size, rel=1e-12)


@pytest.mark.parametrize(
    ("lam", "bands"),
    [
        (grid([(400.0, 1200.0)]), [(400.0, 1200.0)]),
        (grid([(400.0, 500.0), (500.0, 600.0)]), [(400.0, 500.0), (500.0, 600.0)]),
        (np.array([400.0, 490.0, 510.0, 600.0]), [(400.0, 500.0), (500.0, 600.0)]),
        (grid([(400.0, 550.0), (500.0, 600.0)]), [(400.0, 550.0), (500.0, 600.0)]),
        (np.linspace(300.0, 900.0, 301), [(400.0, 500.0), (700.0, 800.0)]),
    ],
    ids=["one band", "adjacent bands", "unsampled shared bound", "overlapping bands", "points in the gap"],
)
def test_a_grid_without_a_bare_gap_keeps_the_very_same_weights(lam, bands):
    np.testing.assert_array_equal(spectral_rmse_weights_banded(lam, bands), spectral_rmse_weights(lam))


def test_a_target_of_one_wavelength_weighs_like_a_typical_point():
    lam = np.concatenate((grid([(400.0, 500.0)], 50), [800.0]))
    weights = spectral_rmse_weights_banded(lam, [(400.0, 500.0), (800.0, 800.0)])
    assert weights[-1] == pytest.approx(np.median(weights[:-1]), rel=1e-12)


def test_the_order_of_the_grid_does_not_matter():
    lam = grid([(400.0, 500.0), (1000.0, 1100.0)])
    bands = [(400.0, 500.0), (1000.0, 1100.0)]
    np.testing.assert_array_equal(spectral_rmse_weights_banded(lam[::-1], bands), spectral_rmse_weights_banded(lam, bands)[::-1])


def test_an_oblique_group_weighs_its_separate_targets_by_their_own_width():
    from certus.core.certus_design_worker_utils import optim_oblique_config_weights

    lam = grid([(400.0, 500.0), (1000.0, 1100.0)])
    first = np.flatnonzero(lam <= 500.0)
    second = np.flatnonzero(lam >= 1000.0)
    config = {"wls_config": lam, "targets": [{"local_positions": first}, {"local_positions": second}]}
    np.testing.assert_array_equal(
        optim_oblique_config_weights(config), spectral_rmse_weights_banded(lam, [(400.0, 500.0), (1000.0, 1100.0)])
    )
