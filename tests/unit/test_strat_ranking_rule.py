"""The 👤 ranking rule of 14: quantised SEEL (0.01 nm resolution), then yield, then critical margin.

    1. SEEL, quantised to its equivalence class (0.01 nm)   ascending
    2. yield = 1 - crash rate                               descending
    3. margin of the critical layer                         descending
"""

from __future__ import annotations

from certus.core.certus_strat_ranking import rank_key_seel_yield_margin

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


# --- the final order of a run: one step of SEEL is an equality, then the yield decides (D20) ---------------------------------


def _row(seel_nm: float, crash: float, margin: float = 1.0, sid: int = 0) -> dict:
    score = (seel_nm / 2.0) ** 2 if seel_nm == seel_nm and seel_nm != float("inf") else float("inf")
    return {"strategy": {"strategy_id": sid, "blocks": []}, "robustness_score": score, "crash_rate": crash,
            "critical_layer": {"margin_in_A": margin}, "results_per_noise": []}


def _seels(rows: list[dict]) -> list[float]:
    return [round(2.0 * (r["robustness_score"] ** 0.5), 4) if r["robustness_score"] != float("inf") else float("inf") for r in rows]


def test_within_one_step_of_the_best_seel_the_yield_decides():
    """The dichroic in `fast` mode, 2026-10-04: 0.1843 nm at 2 % crashes against 0.1892 nm at 0 %; fixed bins put them in 18 and 19."""
    from certus.core.certus_strat_ranking import order_by_the_ranking_rule

    ordered = order_by_the_ranking_rule([_row(0.1843, 0.02, sid=1), _row(0.1892, 0.0, sid=2)])
    assert [r["strategy"]["strategy_id"] for r in ordered] == [2, 1]


def test_two_steps_apart_the_seel_decides_whatever_the_yield():
    from certus.core.certus_strat_ranking import order_by_the_ranking_rule

    ordered = order_by_the_ranking_rule([_row(0.19, 0.0, sid=2), _row(0.17, 0.04, sid=1)])
    assert [r["strategy"]["strategy_id"] for r in ordered] == [1, 2]


def test_the_class_is_measured_from_its_best_member():
    """0.178 is within a step of 0.170, 0.186 is not (0.016): two classes, the yield decides inside the first one only."""
    from certus.core.certus_strat_ranking import order_by_the_ranking_rule

    ordered = order_by_the_ranking_rule([_row(0.186, 0.0, sid=3), _row(0.170, 0.04, sid=1), _row(0.178, 0.0, sid=2)])
    assert [r["strategy"]["strategy_id"] for r in ordered] == [2, 1, 3]


def test_at_equal_yield_the_larger_margin_comes_first_and_then_the_raw_score():
    from certus.core.certus_strat_ranking import order_by_the_ranking_rule

    ordered = order_by_the_ranking_rule(
        [_row(0.171, 0.0, margin=0.4, sid=1), _row(0.175, 0.0, margin=1.8, sid=2), _row(0.173, 0.0, margin=1.8, sid=3)]
    )
    assert [r["strategy"]["strategy_id"] for r in ordered] == [3, 2, 1]


def test_strategies_without_a_finite_score_come_last_in_their_order():
    from certus.core.certus_strat_ranking import order_by_the_ranking_rule

    rows = [_row(float("inf"), 1.0, sid=9), _row(0.2, 0.0, sid=1), _row(float("inf"), 0.5, sid=8)]
    assert [r["strategy"]["strategy_id"] for r in order_by_the_ranking_rule(rows)] == [1, 9, 8]


def test_a_run_shows_and_exports_its_strategies_in_the_order_of_the_rule():
    """The full pipeline sorted its final list by the raw score: the rule of 👤 reached no table, no export, no `best_strategy`."""
    import logging

    from certus.workers.certus_strat_workers import _finalize_and_export_pipeline_results

    shown: list[list] = []

    class _Signal:
        def emit(self, *args):
            shown.append(list(args[0]))

    class _Signals:
        show_strategies_table = _Signal()

    rows = [_row(0.1843, 0.02, sid=1), _row(0.1892, 0.0, sid=2)]
    out = _finalize_and_export_pipeline_results(
        rows, {}, {}, {"logger": logging.getLogger("test"), "show_plots": False, "export_excel": False}, _Signals(), None
    )
    assert [r["strategy"]["strategy_id"] for r in shown[0]] == [2, 1]
    assert out["final_results"]["best_strategy"]["strategy_id"] == 2
