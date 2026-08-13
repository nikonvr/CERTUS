"""The crash gate on a CONFIDENCE BOUND rather than on a point estimate -- correctif 2.

🔴 THE DEFECT. `crash_rate >= CRASH_RATE_TOLERANCE` compares an ESTIMATED rate to a FIXED
threshold, so its verdict depends on how many draws produced the estimate.

📏 Measured 2026-08-13 -- probability that a strategy is REJECTED, by its TRUE rate:

        true rate      N=50     N=150    N=300    N=500
        3 % (good)    18.9 %    8.3 %    3.9 %    1.0 %      <- rejected WRONGLY
        7 % (bad)     68.9 %   83.1 %   93.5 %   97.2 %

    A filter whose verdict changes with depth is not a filter, it is a sampler.

🔒 The 5 % tolerance does NOT move: it is the physicist's "95 % of depositions complete".
It is the estimator that was wrong, never the value.

⚠️ THIS CHANGES EVERY RESULT, so it is INACTIVE by default and must be armed explicitly --
constraint C1 for the neutral path, and C3 for measuring it alone.
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_robustness import (
    CRASH_GATE_CONFIDENCE_KEY,
    CRASH_RATE_TOLERANCE,
    _crash_gate_rejects,
    crash_rate_lower_bound,
)


# --------------------------------------------------------------------------- #
# C1: the inactive path is the historical one, exactly
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("params", [{}, {CRASH_GATE_CONFIDENCE_KEY: 0.0},
                                    {CRASH_GATE_CONFIDENCE_KEY: None},
                                    {CRASH_GATE_CONFIDENCE_KEY: "pas un nombre"}])
@pytest.mark.parametrize("n_crash,n_runs", [(0, 150), (7, 150), (8, 150), (30, 150),
                                            (1, 10), (2, 25), (3, 50)])
def test_inactive_gate_is_the_historical_comparison(params, n_crash, n_runs):
    """🔴 C1. Absent, zero, null or unreadable -- all fall back on the point estimate.

    An unreadable value must NOT arm the bound: silently switching the gate on because
    someone typed a word is precisely the failure this repository keeps paying for.
    """
    rate = n_crash / n_runs
    assert _crash_gate_rejects(n_crash, n_runs, rate, params) == (rate >= CRASH_RATE_TOLERANCE)


def test_a_confidence_outside_zero_one_does_not_arm_the_bound():
    """1.0 would mean absolute certainty, which no finite sample gives."""
    for conf in (-0.5, 1.0, 2.0):
        assert _crash_gate_rejects(8, 150, 8 / 150,
                                   {CRASH_GATE_CONFIDENCE_KEY: conf}) is True   # 5.33 % >= 5 %


# --------------------------------------------------------------------------- #
# The bound itself
# --------------------------------------------------------------------------- #

def test_zero_crashes_gives_a_zero_bound_however_many_draws():
    """🔑 The whole point: no number of crash-free draws ever proves a positive rate.

    So a strategy that never crashed is NEVER rejected -- at any depth. That is the
    property the point-estimate gate could not have, since 0/N is also 0 there but the
    threshold could still be crossed by a single unlucky draw at the next depth.
    """
    for n in (10, 25, 50, 150, 300, 500, 5000):
        assert crash_rate_lower_bound(0, n, 0.95) == 0.0


def test_all_crashes_gives_a_bound_of_one():
    assert crash_rate_lower_bound(50, 50, 0.95) == 1.0


def test_the_bound_is_below_the_point_estimate_and_rises_with_depth():
    """At equal RATE, more draws means more evidence, so a tighter lower bound."""
    prev = -1.0
    for n in (50, 150, 300, 500, 2000):
        b = crash_rate_lower_bound(round(0.10 * n), n, 0.95)
        assert b < 0.10, "la borne INFERIEURE doit rester sous le taux observe"
        assert b > prev, "a taux egal, plus de tirages => borne plus serree"
        prev = b


def test_the_bound_matches_a_known_clopper_pearson_value():
    """Guard against an inverted parameterisation, which would silently flip the gate.

    2 crashes out of 25 at 95 % one-sided: the exact lower bound is 0.0144 (4 decimals),
    i.e. FAR below the 5 % tolerance -- which is exactly why the historical gate, which
    read 8 %, was rejecting on evidence it did not have.
    """
    assert crash_rate_lower_bound(2, 25, 0.95) == pytest.approx(0.0144, abs=5e-4)


# --------------------------------------------------------------------------- #
# What the armed gate actually changes
# --------------------------------------------------------------------------- #

def test_the_armed_gate_no_longer_kills_a_strategy_on_one_unlucky_screening_draw():
    """🔴 THE CASE THAT MOTIVATED THIS. At `n_screen = 10`, `1/10 = 10 % >= 5 %`, so a
    SINGLE crash was fatal -- and since the 2026-08-13 inheritance fix, a strategy killed
    at screening is lost to the whole search, not merely to the ranking.

    One crash out of ten is no evidence at all that the true rate exceeds 5 %.
    """
    armed = {CRASH_GATE_CONFIDENCE_KEY: 0.95}
    assert _crash_gate_rejects(1, 10, 0.10, {}) is True, "porte historique : elle tuait"
    assert _crash_gate_rejects(1, 10, 0.10, armed) is False, "porte armee : elle ne tue plus"


def test_the_armed_gate_still_rejects_a_genuinely_bad_strategy_when_the_evidence_is_there():
    """It must not become a rubber stamp: with enough draws, a bad rate is still caught."""
    armed = {CRASH_GATE_CONFIDENCE_KEY: 0.95}
    assert _crash_gate_rejects(60, 300, 0.20, armed) is True     # 20 %, borne ~16 %
    assert _crash_gate_rejects(300, 300, 1.0, armed) is True     # 100 %


def test_the_armed_gate_is_MORE_permissive_never_less():
    """🔑 The direction is a property, not a coincidence, and a reviewer must be able to
    rely on it: the bound is always below the point estimate, so anything the armed gate
    rejects would also have been rejected by the historical one. The correctif can only
    ADD strategies to the ranking, never remove one."""
    armed = {CRASH_GATE_CONFIDENCE_KEY: 0.95}
    for n_runs in (10, 25, 50, 150, 300, 500):
        for n_crash in range(0, n_runs + 1, max(1, n_runs // 20)):
            rate = n_crash / n_runs
            if _crash_gate_rejects(n_crash, n_runs, rate, armed):
                assert _crash_gate_rejects(n_crash, n_runs, rate, {}), (
                    f"{n_crash}/{n_runs} : la porte armee rejette ce que l'historique gardait"
                )


def test_the_tolerance_itself_is_untouched():
    """🔒 5 % is 👤's specification, not a tuning knob. Only the estimator changed."""
    assert CRASH_RATE_TOLERANCE == 0.05
