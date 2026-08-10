"""The index corridor must reach the SCORING path, not only the growth path.

Before this, `compute_batch_rmse` evaluated the finished filter at the NOMINAL
indices. The deposited filter really carries the perturbed index, so scoring it at
the nominal one measures a filter that was never made -- and hides the CROSSED mode
entirely, which is the one the physicist calls uncompensable, because it only shows
up in the final spectrum.

Every test here fails on the code before that change: the corridor arguments did not
exist, and the result was independent of them by construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus_physics import compute_batch_rmse, corridor_wl_range

#: A small but non-degenerate case: 6 layers, a spectral grid wide enough that the
#: linear term of delta_M(lambda) actually varies across it.
N_LAYERS = 6
WLS = np.linspace(450.0, 650.0, 41)
MONITOR_WLS = np.array([480.0, 520.0, 560.0, 600.0, 620.0, 640.0])


def _case():
    n_h, n_l, n_sub = 2.35 + 0j, 1.46 + 0j, 1.52 + 0j
    thick = np.array([[95.0, 120.0, 88.0, 130.0, 92.0, 118.0]], dtype=np.float64)
    n_layers_flat = np.empty((WLS.size, N_LAYERS), dtype=np.complex128)
    for i in range(WLS.size):
        for j in range(N_LAYERS):
            n_layers_flat[i, j] = n_h if j % 2 == 0 else n_l
    n_sub_arr = np.full(WLS.size, n_sub, dtype=np.complex128)
    target = np.full(WLS.size, 0.5, dtype=np.float64)
    return thick, n_layers_flat, n_sub_arr, target


def _rmse(corridor: float, seed: int = 12345, *, lo: float | None = None, hi: float | None = None):
    thick, n_flat, n_sub, target = _case()
    if lo is None or hi is None:
        lo, hi = corridor_wl_range(WLS, MONITOR_WLS)
    return compute_batch_rmse(
        thick, WLS,
        np.empty(0, dtype=np.complex128), np.empty(0, dtype=np.complex128),
        n_sub, target, n_flat, None,
        corridor, seed, lo, hi,
    )[0]


def test_corridor_zero_is_bit_identical_to_the_legacy_call():
    """C1: the neutral path must return the very same bits as before the parameter.

    Compared with the call that omits the new arguments entirely, which is the exact
    signature every existing caller used.
    """
    thick, n_flat, n_sub, target = _case()
    legacy = compute_batch_rmse(
        thick, WLS,
        np.empty(0, dtype=np.complex128), np.empty(0, dtype=np.complex128),
        n_sub, target, n_flat, None,
    )[0]
    assert _rmse(0.0) == legacy, "corridor = 0 must not move a single bit"
    assert _rmse(0.0).hex() == legacy.hex()


def test_corridor_changes_the_score():
    """Trap 1: a parameter whose value does not change the result does not reach it."""
    base = _rmse(0.0)
    perturbed = _rmse(0.005)
    assert perturbed != base, "the corridor never reached the scoring path"


def test_effect_grows_with_the_corridor():
    """A wider corridor must move the score further. Otherwise it is an artifact."""
    base = _rmse(0.0)
    small = abs(_rmse(0.001) - base)
    large = abs(_rmse(0.010) - base)
    assert large > small > 0.0, f"not monotonic: {small=} {large=}"


def test_draw_is_a_pure_function_of_the_seed():
    """C2: same seed, same draw. Two different seeds must give two different filters."""
    assert _rmse(0.005, seed=111) == _rmse(0.005, seed=111)
    assert _rmse(0.005, seed=111) != _rmse(0.005, seed=222)


def test_normalisation_range_is_not_ignored():
    """The lambda normalisation must actually enter delta_M(lambda).

    If it were dropped, a wider or narrower [lo, hi] would produce the same number --
    and growth and scoring could then silently apply two different dispersion curves
    to the same material, which is what `corridor_wl_range` exists to prevent.
    """
    narrow = _rmse(0.005, lo=500.0, hi=600.0)
    wide = _rmse(0.005, lo=300.0, hi=900.0)
    assert narrow != wide


@pytest.mark.parametrize("corridor", [0.001, 0.0025, 0.005, 0.010])
def test_result_stays_finite_and_physical(corridor: float):
    value = _rmse(corridor)
    assert np.isfinite(value)
    assert value >= 0.0


def test_envelope_encloses_both_grids():
    """The corridor must hold everywhere the index is USED, not only where it is watched.

    Normalising over the monitoring wavelengths alone lets |u| exceed 1 on the rest of
    the spectrum, so |delta| exceeds delta_max there. Measured on the reference winner,
    whose two monitoring wavelengths sit 13 nm apart on a 300 nm grid, the overshoot
    reaches x21 -- and it is worst for strategies that GROUP their wavelengths, which
    biases the ranking by an artefact pointing the same way as the physics.
    """
    grid = np.linspace(400.0, 700.0, 301)
    grouped = np.array([531.0, 544.0])
    assert corridor_wl_range(grid, grouped) == (400.0, 700.0)

    # A monitoring wavelength outside the scoring grid must widen the envelope:
    # 13 records that clues_at_wl overflows the range, so this is not hypothetical.
    outside = np.array([380.0, 720.0])
    assert corridor_wl_range(grid, outside) == (380.0, 720.0)


def test_grouped_and_spread_strategies_get_the_same_corridor():
    """Two strategies must receive the same index perturbation, whatever their lambdas.

    This is the defect the envelope fixes: with the monitoring span alone, a grouped
    strategy was handed an effective corridor up to 21x wider than a spread one.
    """
    grid = np.linspace(400.0, 700.0, 301)
    grouped = corridor_wl_range(grid, np.array([531.0, 544.0]))
    spread = corridor_wl_range(grid, np.array([450.0, 650.0]))
    assert grouped == spread
