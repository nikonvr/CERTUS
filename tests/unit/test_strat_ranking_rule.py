"""The 👤 ranking rule of 14: quantised SEEL, then yield, then critical margin.

    1. SEEL, quantised to its equivalence class   ascending
    2. yield = 1 - crash rate                     descending
    3. margin of the critical layer               descending

🔴 WHY IT REPLACES A CONTINUOUS SORT. `fit_alpha` is 1.0, so SEEL = k . RMSE with k a
constant: ordering on the continuous SEEL reproduces the RMSE order exactly -- a sort
that sorts nothing. And 17-26 measured that at N = 150 the eight best strategies lie
within 2 sigma of one another and all read 0.3 nm. The continuous ranking separates
noise; the quantised one says "equal", which is the true statement.
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_ranking import (
    rank_key_seel_yield_margin,
    seel_equivalence_half_width,
)


# --------------------------------------------------------------------------- #
# The half-width: two limits, the coarser one wins.
# --------------------------------------------------------------------------- #

def test_the_measurement_limit_governs_small_seel():
    """At 0.3 nm the 0.05 nm half-width is wider than the 6 % statistical noise."""
    assert seel_equivalence_half_width(0.3) == pytest.approx(0.05)


def test_the_statistical_limit_takes_over_for_large_seel():
    """📏 At 1.1 nm a fixed 0.05 nm bin is +/-4.4 %, NARROWER than the +/-6 % noise.

    Keeping the fixed step there would separate strategies the measurement cannot
    separate -- the exact failure quantisation exists to prevent.
    """
    assert seel_equivalence_half_width(1.1) == pytest.approx(0.066)
    assert seel_equivalence_half_width(1.1) > 0.05


def test_the_half_width_never_falls_below_either_limit():
    for seel in (0.0, 0.1, 0.3, 0.6, 1.1, 5.0, 30.0):
        h = seel_equivalence_half_width(seel)
        assert h >= 0.05
        assert h >= 0.06 * seel - 1e-12


# --------------------------------------------------------------------------- #
# The rule itself.
# --------------------------------------------------------------------------- #

def test_two_seel_inside_one_bin_are_declared_equal():
    """The whole point: 0.28 and 0.32 nm are one measurement, not two."""
    a = rank_key_seel_yield_margin(0.28, crash_rate=0.0, critical_margin_in_A=1.0)
    b = rank_key_seel_yield_margin(0.32, crash_rate=0.0, critical_margin_in_A=1.0)
    assert a[0] == b[0], "deux SEEL dans une meme classe doivent avoir la meme cle"


def test_a_genuinely_better_seel_still_wins():
    """Quantising must not flatten everything -- 0.3 nm beats 0.9 nm."""
    good = rank_key_seel_yield_margin(0.3, 0.0, 1.0)
    bad = rank_key_seel_yield_margin(0.9, 0.0, 1.0)
    assert good < bad


def test_yield_breaks_the_tie_before_the_margin():
    """👤 8: a crashed run and an out-of-spec filter are the same failure."""
    finishes = rank_key_seel_yield_margin(0.3, crash_rate=0.00, critical_margin_in_A=0.1)
    crashes = rank_key_seel_yield_margin(0.3, crash_rate=0.05, critical_margin_in_A=1.9)
    assert finishes < crashes, (
        "le rendement doit departager AVANT la marge : une strategie qui va au bout "
        "l'emporte sur une strategie plus confortable qui plante"
    )


def test_the_margin_breaks_the_tie_when_yield_cannot():
    """The case that actually occurs: every tied strategy reads 0/150 crashes.

    0 out of 150 says p < 2 % and nothing more, so the yield is silent here. The
    margin is the only one of the three still able to discriminate.
    """
    safe = rank_key_seel_yield_margin(0.3, 0.0, critical_margin_in_A=1.8)
    exposed = rank_key_seel_yield_margin(0.3, 0.0, critical_margin_in_A=0.4)
    assert safe < exposed


def test_beyond_two_A_nothing_distinguishes_impossible_from_impossible():
    """🔴 The draws are BOUNDED: past the largest possible perturbation, p = 0 exactly.

    A23 fixes the reporting rule -- beyond 2 A one writes "impossible", never a
    probability. Ordering by margin there would rank two impossibilities.
    """
    a = rank_key_seel_yield_margin(0.3, 0.0, critical_margin_in_A=2.5)
    b = rank_key_seel_yield_margin(0.3, 0.0, critical_margin_in_A=40.0)
    assert a == b


def test_the_rule_actually_reorders_a_measured_case():
    """The eight-strategy cloud of 17-26: same SEEL, so the order comes from elsewhere.

    Scores +0.0 %, +6.5 %, +9.9 %, +11.0 % -- all inside the noise, all 0.3 nm. The
    continuous sort keeps them in score order; this rule sorts them on what is actually
    measurable, and the strategy with the best margin comes first even though its score
    is the worst of the four.
    """
    cloud = [
        {"id": 2228, "seel": 0.3, "crash": 0.0, "margin": 0.4},
        {"id": 2218, "seel": 0.3, "crash": 0.0, "margin": 0.9},
        {"id": 9208, "seel": 0.3, "crash": 0.0, "margin": 1.7},
        {"id": 2226, "seel": 0.3, "crash": 0.0, "margin": 0.2},
    ]
    ordered = sorted(
        cloud, key=lambda s: rank_key_seel_yield_margin(s["seel"], s["crash"], s["margin"])
    )
    assert [s["id"] for s in ordered] == [9208, 2218, 2228, 2226]
