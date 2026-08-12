"""The index corridor must be normalised over ONE interval, supplied by ONE caller.

Defects 17-20 and 17-25. Both produced plausible numbers rather than errors, which is
why they survived so long:

  * `validate_wavelengths_batch` deduced its own normalisation span from
    `candidate_wls` -- a list FILTERED PER LAYER. The domain of u(lambda) therefore
    changed from layer to layer, so a single draw (a, b) represented a different
    dispersion curve at every layer, and Phase A perturbed the index differently from
    Phase B. 12.2 forbids the two stages modelling different machines.

  * `simulate_stack_robustness_batch` silently degraded to
    `corridor_wl_range(layer_wavelengths, layer_wavelengths)` when the envelope was
    omitted -- i.e. straight back to the monitoring-span normalisation corrected on
    2026-08-10, the one that let |u| reach 2.1 and invalidated every corridor figure
    measured before that date.

🔴 These tests must FAIL on the pre-fix code. Copy them into the baseline worktree and
check that they do -- a test that passes before the fix proves nothing (20, control 2).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus_physics import corridor_wl_range, validate_wavelengths_batch
from certus.physics.certus_strat_batch import simulate_stack_robustness_batch

SPECTRAL = np.array([400.0, 700.0], dtype=np.float64)


def test_envelope_covers_both_grids_and_is_symmetric():
    """u(lambda) stays in [-1, 1] over the whole spectral grid, monitoring included."""
    monitor = np.array([480.0, 620.0], dtype=np.float64)
    lo, hi = corridor_wl_range(SPECTRAL, monitor)
    assert (lo, hi) == (400.0, 700.0)
    for wl in (400.0, 480.0, 545.0, 620.0, 700.0):
        u = (2.0 * wl - (lo + hi)) / (hi - lo)
        assert -1.0 <= u <= 1.0, f"u({wl}) = {u} sort du corridor"


def test_envelope_takes_monitoring_wavelengths_outside_the_spectral_grid():
    """13 warns that a monitoring lambda can fall outside the scoring grid."""
    monitor = np.array([380.0, 720.0], dtype=np.float64)
    assert corridor_wl_range(SPECTRAL, monitor) == (380.0, 720.0)


#: 🔴 THE FIXTURE MATTERS MORE THAN THE ASSERTION HERE.
#:
#: A first version of this file left `runs_history` at zero -- i.e. "the previous
#: layers were never deposited". Every candidate then returned the crash sentinel
#: (1e6), and the equality assertion passed by comparing two sentinels. It tested
#: nothing while looking perfectly healthy: control 4 of 20, in a test file.
#: The history must therefore be the NOMINAL deposit, so the layer actually
#: terminates and the returned P95 is a real number.
QWOT_500 = np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64)
I_LAYER = 2


def _phase_a(cands: np.ndarray, corridor: float, lo: float, hi: float) -> np.ndarray:
    cands = np.asarray(cands, dtype=np.float64)
    n = len(cands)
    history = np.tile(QWOT_500[:I_LAYER], (4, 1))
    return validate_wavelengths_batch(
        cands,
        np.full(n, 2.35 + 0j, dtype=np.complex128),
        np.full(n, 1.46 + 0j, dtype=np.complex128),
        np.full(n, 1.52 + 0j, dtype=np.complex128),
        history,
        QWOT_500,
        I_LAYER,
        1.0,
        np.zeros(4, dtype=np.float64),
        2.0,
        0,
        None,
        1.0,
        0.0,
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        True,
        1,
        corridor,
        12345,
        lo,
        hi,
    )


def test_the_fixture_actually_simulates_something():
    """Guard on the guard: if this ever returns the sentinel, every test below is void."""
    res = _phase_a(np.array([530.0, 540.0, 550.0]), 0.005, 400.0, 700.0)
    assert np.all(res[:, 0] < 1e5), (
        f"le montage plante ({res[:, 0]}) : les assertions suivantes compareraient "
        "des sentinelles et passeraient sans rien tester"
    )


def test_phase_a_normalisation_no_longer_depends_on_the_candidate_span():
    """The SAME wavelength must see the SAME perturbation, whatever else was offered.

    This is the defect in one line, and it is worth 3.2 % on this case. Measured on
    the pre-fix code, layer 2, corridor 0.005, at 540 nm:

        candidates 530-550 (span  20 nm)  ->  P95 = 0.453799477357
        candidates 440-660 (span 220 nm)  ->  P95 = 0.439359811210

    Same wavelength, same seed, same stack. The only thing that differed was what else
    happened to be on the candidate list -- which is not physics.
    """
    lo, hi = corridor_wl_range(SPECTRAL, np.array([450.0, 700.0], dtype=np.float64))
    narrow = _phase_a(np.array([530.0, 540.0, 550.0]), 0.005, lo, hi)
    wide = _phase_a(np.array([440.0, 540.0, 660.0]), 0.005, lo, hi)
    # index 1 is 540.0 nm in both calls
    assert narrow[1, 0] == pytest.approx(wide[1, 0], rel=1e-12, abs=1e-12), (
        "540 nm ne voit pas la meme perturbation selon les autres candidates offertes : "
        "la normalisation depend encore de candidate_wls"
    )


def test_phase_a_refuses_an_active_corridor_without_an_envelope():
    """Silence was the bug. An omitted envelope must raise, not fall back."""
    with pytest.raises(ValueError, match="corridor_lo/corridor_hi"):
        _phase_a(np.array([530.0, 540.0, 550.0]), 0.005, 0.0, 0.0)


def test_phase_a_neutral_path_is_untouched_by_the_envelope():
    """C1: at corridor 0 the envelope is never read, so it cannot change a bit."""
    a = _phase_a(np.array([530.0, 540.0, 550.0]), 0.0, 0.0, 0.0)
    b = _phase_a(np.array([530.0, 540.0, 550.0]), 0.0, 400.0, 700.0)
    assert np.array_equal(a, b, equal_nan=True)


def _phase_b(corridor: float, lo: float, hi: float):
    n_layers, n_runs = 3, 2
    return simulate_stack_robustness_batch(
        np.array([100.0, 90.0, 110.0], dtype=np.float64),
        np.array([545.0, 545.0, 545.0], dtype=np.float64),
        np.full(n_layers, 2.35 + 0j, dtype=np.complex128),
        np.full(n_layers, 1.46 + 0j, dtype=np.complex128),
        np.full(n_layers, 1.52 + 0j, dtype=np.complex128),
        np.zeros((n_runs, n_layers), dtype=np.float64),
        1.0,
        2.0,
        0,
        np.zeros(n_layers, dtype=np.float64),  # signal_noise_scale is PER LAYER
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        True,
        1,
        corridor,
        7,
        lo,
        hi,
    )


def test_phase_b_refuses_an_active_corridor_without_an_envelope():
    """The silent degradation of 17-25 reinstalled a corrected bug. It must raise."""
    with pytest.raises(ValueError, match="corridor_lo/corridor_hi"):
        _phase_b(0.005, 0.0, 0.0)


def test_phase_b_neutral_path_is_untouched_by_the_envelope():
    """C1 again, on the growth side."""
    a, da, *_ = _phase_b(0.0, 0.0, 0.0)
    b, db, *_ = _phase_b(0.0, 400.0, 700.0)
    assert np.array_equal(a, b, equal_nan=True)
    assert np.array_equal(da, db, equal_nan=True)
