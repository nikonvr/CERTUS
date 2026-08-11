"""The two counting margins -- A23 stage 2.

`turning_point_margins` answers "how close did the turning-point COUNT come to being
wrong", in both directions and in transmission units:

  * missed      = smallest ripple between consecutive extrema  -  hysteresis
  * fabricated  = hysteresis  -  largest excursion that did NOT emit

🔑 WHY A MARGIN RATHER THAN A RATE. At 150 draws, 0 crashes says p < 2 % and nothing
more, and every strategy on this stack reads 0. A margin is continuous and defined even
when nothing failed, so it separates strategies a rate cannot.

🔴 THIS FILE EXISTS BECAUSE THE FUNCTION WAS WRONG FOUR TIMES, and each version looked
perfectly reasonable while measuring nothing:

  1. the trailing segment was read as a near-fabrication, giving a NEGATIVE margin --
     an excursion that crossed the threshold without emitting, which cannot happen;
  2. the detector's half-reset extremes were reused, leaving a stale extreme in the
     excursion so the fabrication margin returned its sentinel on EVERY input;
  3. the ripple was measured as the segment span at the moment of emission, which is
     ~= hysteresis BY CONSTRUCTION, so the missed margin read ~0 whether the ripple was
     1.2x or 100x the threshold;
  4. a single `n_emit == 0` guard killed the fabrication case that matters most -- a
     signal too flat to emit anything is exactly where noise is closest to inventing
     an extremum.

None of the four was caught by a plausible-looking value. All four were caught by
SWEEPING the quantity the margin is supposed to track and checking it moves. That is
Trap 1 applied to an instrument instead of a result, and it is why these tests sweep.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from certus.physics.certus_strat_growth import turning_point_margins

A = 5e-4                      # reading noise amplitude, 9bis-2
HY = 1.66 * A                 # configured hysteresis
SENTINEL = 1e17               # anything above this means "no constraint"


def _sine(peak_to_peak_in_A: float, n: int = 900, periods: float = 3.0) -> np.ndarray:
    x = np.linspace(0.0, 2.0 * np.pi * periods, n)
    return 0.5 + (peak_to_peak_in_A * A / 2.0) * np.sin(x)


# --------------------------------------------------------------------------- #
# The sweeps. These are the tests; the point cases below only pin the edges.
# --------------------------------------------------------------------------- #

def test_missed_margin_grows_with_the_ripple():
    """Defect 3: it used to be ~0 for every amplitude. It must TRACK the ripple."""
    # ⚠️ TWO TRAPS IN CHOOSING THE SWEEP, and both were walked into.
    #
    # 1. Every amplitude must EXCEED the threshold. Below it nothing is emitted and the
    #    sentinel is the CORRECT answer -- a first version swept from 1.2 A, under the
    #    1.66 A threshold, and read the sentinel as a failure.
    # 2. There is a genuine REGIME CHANGE around 2 x hysteresis, and it is a property of
    #    the signal, not a bug. The array does not start on an extremum, so the opening
    #    half-swing is a ripple of its own. Below ~3.3 A that half-swing (< 1.66 A) does
    #    not emit and the ripples measured are full peak-to-peak; above it, it emits and
    #    becomes the SMALLEST ripple, so the margin halves. Sweeping across the
    #    transition gives 0.34, 1.34, 0.84 -- non-monotonic, and correctly so.
    #    The sweep therefore stays inside one regime.
    got = [turning_point_margins(_sine(k), 900, HY)[0] / A for k in (5.0, 10.0, 20.0, 50.0, 100.0)]
    assert all(v < SENTINEL for v in got), f"une amplitude n'a rien emis : {got}"
    assert all(b > a for a, b in pairwise(got)), (
        f"la marge de manque ne croit pas avec l'ondulation : {got}"
    )
    assert got[-1] == pytest.approx(100.0 / 2 - 1.66, abs=0.05), f"echelle : {got}"


def test_fabrication_margin_shrinks_as_noise_approaches_the_threshold():
    """Defect 2 and 4: it used to return its sentinel whatever the input."""
    rng = np.random.default_rng(7)
    base = rng.uniform(-1.0, 1.0, 800)
    got = []
    for amp in (0.2, 0.5, 0.8, 0.95):
        _, fab = turning_point_margins(0.5 + amp * HY * base / 2.0, 800, HY)
        assert fab < SENTINEL, f"sentinelle a {amp} x le seuil : la marge ne mesure rien"
        got.append(fab / A)
    assert all(b < a for a, b in pairwise(got)), (
        f"la marge de fabrication ne decroit pas quand le bruit grossit : {got}"
    )
    assert got[-1] < 0.2, f"a 0,95 x le seuil on doit fremir : {got[-1]:.2f} A"


def test_a_margin_is_never_negative_without_a_real_crossing():
    """Defect 1: a negative fabrication margin is arithmetically impossible.

    It would mean an excursion exceeded the threshold and did not emit.
    """
    for k in (0.5, 1.2, 5.0, 50.0):
        missed, fab = turning_point_margins(_sine(k), 900, HY)
        if fab < SENTINEL:
            assert fab >= 0.0, f"marge de fabrication negative ({fab / A:.2f} A) a {k} A"


# --------------------------------------------------------------------------- #
# Edges. A sentinel must mean "no constraint to measure", never "safe".
# --------------------------------------------------------------------------- #

def test_a_perfectly_flat_signal_has_no_ripple_but_maximal_fabrication_margin():
    missed, fab = turning_point_margins(np.full(800, 0.5), 800, HY)
    assert missed > SENTINEL, "aucune ondulation a mesurer : ce doit etre la sentinelle"
    assert fab == pytest.approx(HY), "un signal plat est a la distance MAXIMALE de fabriquer"


def test_a_disabled_threshold_constrains_nothing():
    missed, fab = turning_point_margins(_sine(10.0), 900, 0.0)
    assert missed > SENTINEL and fab > SENTINEL


def test_a_single_extremum_gives_no_ripple():
    """One extremum is not a ripple: it takes two to have a distance between them."""
    # The final fall must stay BELOW the threshold, or it emits a second extremum --
    # 0.001 did, being above 1.66 A = 8.3e-4.
    s = np.concatenate([np.linspace(0.40, 0.60, 60), np.linspace(0.60, 0.5996, 40)])
    missed, _ = turning_point_margins(s, len(s), HY)
    assert missed > SENTINEL


def test_too_short_an_array_is_refused_rather_than_guessed():
    assert turning_point_margins(np.array([0.5]), 1, HY) == (1e18, 1e18)
