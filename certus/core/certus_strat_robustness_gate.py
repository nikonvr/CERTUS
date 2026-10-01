"""CERTUS STRAT ROBUSTNESS - the crash-rate gate and the filter of finite robustness scores (moved out of certus_strat_robustness.py, S5.2)."""

from typing import Any

import numpy as np

# Non-terminating deposition rate beyond which a strategy is ELIMINATED.
#
# A non-terminating deposition is a lost run in the cleanroom, not a quality
# compromise: the strategy is removed from the ranking instead of being penalized. Below
# the threshold, the randomness is deemed acceptable given the potential spectral gain.
#
# rmse_p95 CANNOT replace this check: being a 95th percentile, it is
# structurally blind to any event occurring in less than 5% of the runs.
CRASH_RATE_TOLERANCE = 0.05


def _filter_finite_robustness_scores(
    strategies_results: list[dict[str, Any]],
    *,
    logger,
) -> list[dict[str, Any]]:
    """Keep only strategies with finite robustness score.

    🔴 WITH A MANDATORY FALLBACK: this filter must NEVER return an empty list.

    Crash rate COMPOSES across stack height. On 48 layers, holding 5% at strategy
    level requires 1 - (1 - 0.05)^(1/48) = 0.107% per layer. It is a cliff, not a continuous ranking:
    either all strategies pass, or none.

    Measurement on 48-layer dichroic pass-band filter:
        mined strategies .................. 240
        valid after contract .............. 240
        crash_rate ......... min 0.833  median 1.000
        survivors ........................   0   <- STRAT returned NOTHING

    Returning an empty list propagates `all_strategies_results = []` up to the runner,
    displaying RESULT=None. It is better to return the least risky strategy with explicit reporting.
    """
    filtered_results: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in strategies_results:
        score = float(item.get("robustness_score", np.inf))
        if np.isfinite(score):
            filtered_results.append(item)
        else:
            rejected.append(item)

    # 🔴 THIS LINE WAS EMITTED PER STRATEGY, AND IT FIRED 11 028 TIMES ON A SINGLE RUN
    # (measured on 2026-08-24, `reports/hysteresis05_2026-08-24/`). It is now AGGREGATED.
    #
    # 🔑 WHY AGGREGATE HERE AND THRESHOLD BELOW -- it is not the same case. When survivors
    # remain, the function returns ONLY `filtered_results`: strategies with a non-finite
    # score are dropped and NEVER reach the artefact. Their number is therefore recoverable
    # nowhere else, and a threshold would lose it for good. One line per call keeps it
    # whole.
    if rejected:
        ids = [str(it.get("strategy", {}).get("strategy_id", "?")) for it in rejected[:5]]
        if len(strategies_results) == 1:
            logger.debug(
                f"[ROBUSTNESS] 1 strategy dropped for a NON-FINITE score -- id: {ids[0]}"
            )
        else:
            logger.warning(
                f"[ROBUSTNESS] {len(rejected)} strategy(ies) dropped for a NON-FINITE score"
                f" -- ids: {', '.join(ids)}{' ...' if len(rejected) > 5 else ''}"
            )

    if filtered_results or not rejected:
        return filtered_results

    # No survivor: we re-rank the eliminated ones by increasing risk and we
    # return a finite score to them, otherwise they would be lost later.
    def _fallback_key(it: dict[str, Any]) -> tuple[float, float]:
        return (float(it.get("crash_rate", 1.0)), _worst_finite_rmse(it))

    rejected.sort(key=_fallback_key)
    best_crash = float(rejected[0].get("crash_rate", 1.0))

    # 🔴 THESE TWO MESSAGES ARE ABOUT A RANKING DEPRIVED OF SIGNAL. A ranking of ONE
    # element is not a ranking: at `len(rejected) == 1` the statement is vacuously true and
    # says nothing. The threshold is therefore not a chosen number, it is the definition of
    # what the message is about.
    #
    # 📏 Measured on 2026-08-24 over a whole run (`reports/hysteresis05_2026-08-24/`):
    #
    #     2400 emissions at n = 1   ·   7 at n = 2   ·   3 at n = 601   ·   3 elsewhere
    #
    # i.e. 2400 ERROR lines out of 2440 that concerned a population of ONE strategy, and
    # THREE informative lines drowned among them. A `grep ERROR` no longer returned
    # anything -- which also neutralised the guards placed elsewhere, including the
    # winner's-curse one (`certus_strat_workers.py`).
    #
    # 🔑 AND NOTHING IS LOST: the n = 1 case is already recorded per strategy in the
    # artefact, through `crash_eliminated` set just below -- 4051 out of 4454 in
    # `blocs_vs_plantage_r75x2_deep_s404.json`. The line duplicated durable data.
    # That is also what rules out an aggregated counter here: it would return
    # `sum(crash_eliminated)`, a number that can already be computed.
    parle = len(rejected) >= 2
    if parle:
        logger.error(
            f"[ROBUSTNESS] 🔴 NONE of the {len(rejected)} strategies holds under "
            f"{CRASH_RATE_TOLERANCE:.0%} of non-terminating depositions. The rate compounds "
            f"over the height of the stack: the best candidate crashes in "
            f"{best_crash:.1%} of the draws. We still return the ranking by increasing "
            f"risk — but NONE of these strategies is usable as is, and "
            f"the component likely requires another monitoring paradigm."
        )
    for item in rejected:
        item["robustness_score"] = _worst_finite_rmse(item)
        item["crash_eliminated"] = True

    # 🔴 THE DEGENERATE REGIME IS ANNOUNCED, AND IT WAS NOT.
    #
    # When ALL strategies are eliminated, all returned scores are FALLBACKS
    # (`_worst_finite_rmse`). The ranking that follows therefore sorts fallback values, and
    # `crash_rate` is CONSTANT -- the first two sort keys carry no information. Yet this
    # ranking is what picks the ELITE PARENTS, whose mutation decides everything.
    #
    # 📏 Measured on 2026-08-21: on `r75x2` at 2 nm, seed 42, all 1617 strategies are in
    # that case, and NOTHING said so. It took two days to notice -- not because it was
    # hidden, but because an artefact carries ONLY finite scores even when everything
    # crashes, and a ranking of fallbacks looks exactly like a ranking.
    #
    # 🔑 SAME THRESHOLD AS ABOVE, AND FOR THE SAME REASON: this message describes a RANKING
    # without signal. On a single strategy there is no ranking, hence nothing to announce.
    if parle:
        logger.warning(
            f"   [REGIME] 🔴 DEGENERATE: the {len(rejected)} returned strategies carry a "
            f"FALLBACK score, and their crash_rate is constant. The ranking that follows -- "
            f"hence the choice of the ELITE PARENTS -- has no signal in its first two keys. "
            f"`use_margin_ranking` is the only informative key in this regime."
        )
    return rejected


#: Confidence level of the crash gate, as a JSON key. 🔴 DEFAULT 0.0 = INACTIVE, and the
#: inactive path is the historical point-estimate comparison, bit for bit -- constraint C1.
#: A value in (0, 1) switches the gate to a Clopper-Pearson LOWER bound at that level.
CRASH_GATE_CONFIDENCE_KEY = "crash_gate_confidence"


def crash_rate_lower_bound(n_crash: int, n_runs: int, confidence: float) -> float:
    """One-sided Clopper-Pearson LOWER bound on the crash probability.

    "Given `n_crash` crashes out of `n_runs` draws, the true rate is above this value
    with probability `confidence`." Exact, not normal-approximate: at these counts the
    normal approximation is not merely imprecise, it is invalid -- 0 crashes out of 50
    would give a bound of exactly 0 with a zero standard error.

    Returns 0.0 for `n_crash == 0`, which is correct and is the whole point: no number
    of crash-free draws ever proves a positive rate.
    """
    if n_crash <= 0 or n_runs <= 0:
        return 0.0
    if n_crash >= n_runs:
        return 1.0
    from scipy.stats import beta

    return float(beta.ppf(1.0 - confidence, n_crash, n_runs - n_crash + 1))


def _crash_gate_rejects(
    n_crash: int, n_runs: int, crash_rate: float, params: dict[str, Any]
) -> bool:
    """Does this strategy fail the crash gate?

    🔴 THE DEFECT THIS EXISTS TO FIX. The historical gate compares an ESTIMATED rate to
    a FIXED threshold: `crash_rate >= 0.05`. Its verdict therefore depends on how many
    draws produced the estimate, and it does so invisibly.

    📏 Measured 2026-08-13 -- probability that a strategy is REJECTED, by its TRUE rate:

              true rate     N=50     N=150    N=300    N=500
              3 % (good)   18.9 %    8.3 %    3.9 %    1.0 %     <- rejected WRONGLY
              7 % (bad)    68.9 %   83.1 %   93.5 %   97.2 %

    At 50 draws nearly a third of the strategies that truly crash 7 % of the time slip
    through, and one good strategy in five at 3 % is thrown away by bad luck. Worse, at
    screening depth the granularity bites: with 10 draws, `1/10 = 10 % >= 5 %`, so a
    SINGLE crash is fatal -- and one column does not improve with depth at all, because
    3 % is too close to 5 % for counting to settle it.

        A filter whose verdict changes with depth is not a filter, it is a sampler.

    🟢 THE FIX. Reject only when one is CONFIDENT the true rate exceeds the tolerance,
    i.e. when the lower confidence bound clears it. Three consequences, all wanted:

      - a good strategy is NEVER rejected by bad luck, at any depth;
      - a shallow run rejects little, which is HONEST -- it does not know;
      - the gate tightens on its own as depth grows, with no change of rule.

    🔒 THE 5 % TOLERANCE DOES NOT MOVE. It is the physicist's "95 % of depositions
    complete". It is the ESTIMATOR that was wrong, never the value.

    ⚠️ INACTIVE BY DEFAULT (C1). With `crash_gate_confidence` absent or 0, this is the
    historical comparison, bit for bit. Set it to 0.95 to arm the bound.
    """
    try:
        conf = float(params.get(CRASH_GATE_CONFIDENCE_KEY, 0.0) or 0.0)
    except ValueError, TypeError:
        conf = 0.0
    if not (0.0 < conf < 1.0):
        return crash_rate >= CRASH_RATE_TOLERANCE
    return crash_rate_lower_bound(n_crash, n_runs, conf) >= CRASH_RATE_TOLERANCE


def _worst_finite_rmse(item: dict[str, Any]) -> float:
    """Worst finite RMSE on the noise levels, to re-rank an eliminated one."""
    worst = 0.0
    for r in item.get("results_per_noise", []) or []:
        val = float(r.get("rmse_p95", r.get("rmse_mean", 0.0)) or 0.0)
        if np.isfinite(val) and val > worst:
            worst = val
    return worst
