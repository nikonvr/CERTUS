"""The 👤 ranking rule of 14: quantised SEEL (0.01 nm resolution), then yield, then critical margin.

    1. SEEL, quantised to its equivalence class (0.01 nm)   ascending
    2. yield = 1 - crash rate                               descending
    3. margin of the critical layer                         descending
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_ranking import (
    SEEL_RESOLUTION_NM,
    rank_key_seel_yield_margin,
    seel_equivalence_half_width,
)


# --------------------------------------------------------------------------- #
# The half-width: two limits (0.005 nm measurement limit and statistical limit).
# --------------------------------------------------------------------------- #

def test_the_measurement_limit_governs_small_seel():
    """At 0.05 nm the 0.005 nm half-width is wider than the 6 % statistical noise."""
    assert seel_equivalence_half_width(0.05) == pytest.approx(SEEL_RESOLUTION_NM)


def test_the_statistical_limit_takes_over_for_large_seel():
    """At 1.1 nm the +/-6 % noise (0.066 nm) is wider than the 0.005 nm measurement limit."""
    assert seel_equivalence_half_width(1.1) == pytest.approx(0.066)
    assert seel_equivalence_half_width(1.1) > SEEL_RESOLUTION_NM


def test_the_half_width_never_falls_below_either_limit():
    for seel in (0.0, 0.05, 0.1, 0.17, 0.3, 0.48, 1.1, 5.0, 30.0):
        h = seel_equivalence_half_width(seel)
        assert h >= SEEL_RESOLUTION_NM
        assert h >= 0.06 * seel - 1e-12


# --------------------------------------------------------------------------- #
# The rule itself.
# --------------------------------------------------------------------------- #

def test_two_seel_inside_one_bin_are_declared_equal():
    """Two SEEL inside the same 0.01 nm bin (e.g. 0.171 and 0.174 nm) have the same key."""
    a = rank_key_seel_yield_margin(0.171, crash_rate=0.0, critical_margin_in_A=1.0)
    b = rank_key_seel_yield_margin(0.174, crash_rate=0.0, critical_margin_in_A=1.0)
    assert a[0] == b[0], "deux SEEL dans une même classe doivent avoir la même clé"


def test_a_genuinely_better_seel_still_wins():
    """Quantising at 0.01 nm distinguishes different SEEL values: 0.17 nm beats 0.48 nm."""
    good = rank_key_seel_yield_margin(0.17, 0.0, 1.0)
    bad = rank_key_seel_yield_margin(0.48, 0.0, 1.0)
    assert good < bad


def test_yield_breaks_the_tie_before_the_margin():
    """A finished run beats a crashed run even if the margin is higher."""
    finishes = rank_key_seel_yield_margin(0.17, crash_rate=0.00, critical_margin_in_A=0.1)
    crashes = rank_key_seel_yield_margin(0.17, crash_rate=0.05, critical_margin_in_A=1.9)
    assert finishes < crashes, (
        "le rendement doit départager AVANT la marge : une stratégie qui va au bout "
        "l'emporte sur une stratégie plus confortable qui plante"
    )


def test_the_margin_breaks_the_tie_when_yield_cannot():
    """When two strategies are tied in SEEL and yield, the critical margin breaks the tie."""
    safe = rank_key_seel_yield_margin(0.17, 0.0, critical_margin_in_A=1.8)
    exposed = rank_key_seel_yield_margin(0.17, 0.0, critical_margin_in_A=0.4)
    assert safe < exposed


def test_beyond_two_A_nothing_distinguishes_impossible_from_impossible():
    """Beyond 2 A margin, perturbations are impossible to reach (clamped)."""
    a = rank_key_seel_yield_margin(0.17, 0.0, critical_margin_in_A=2.5)
    b = rank_key_seel_yield_margin(0.17, 0.0, critical_margin_in_A=40.0)
    assert a == b


def test_the_rule_actually_reorders_a_measured_case():
    """Within a tied SEEL bin, the strategy with the best margin comes first."""
    cloud = [
        {"id": 2228, "seel": 0.17, "crash": 0.0, "margin": 0.4},
        {"id": 2218, "seel": 0.17, "crash": 0.0, "margin": 0.9},
        {"id": 9208, "seel": 0.17, "crash": 0.0, "margin": 1.7},
        {"id": 2226, "seel": 0.17, "crash": 0.0, "margin": 0.2},
    ]
    ordered = sorted(
        cloud, key=lambda s: rank_key_seel_yield_margin(s["seel"], s["crash"], s["margin"])
    )
    assert [s["id"] for s in ordered] == [9208, 2218, 2228, 2226]
