"""The STRAT bench writes the best ELITE score next to RESULT (chantier 7, owner decision 2026-11-20).

`RESULT` is the score of the first-ranked plan, and since the local search the first plan is often its refined plan,
kept or refused by a check on two fresh seeds: on the benches of 2026-11-20 that binary verdict alone moved the 35c and
36c benchmarks by -29 % and +12 % (reports/nuit_2026-11-19/bilan_6_ecarts_35c_36c.md), while the best ELITE plan moved
by -9 % and -1 %. `STRAT_BEST_ELITE` is the score of the best ELITE plan that was not crash-eliminated.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_examples_best_elite", ROOT / "scripts" / "bench_examples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(origin: str, score: float, eliminated: bool = False) -> dict:
    return {"strategy": {"strategy_id": 1, "origin": origin, "blocks": []}, "robustness_score": score,
            "crash_rate": 0.0, "crash_eliminated": eliminated}


def test_the_ranking_dump_writes_the_best_elite_score(monkeypatch) -> None:
    bench = _bench()
    lines: list[str] = []
    monkeypatch.setattr(bench, "emit", lines.append)
    bench.dump_strat_ranking([
        _row("LOCAL_SEARCH", 0.030029),
        _row("ELITE", 0.054555),
        _row("RATE_L17(from 900450884)", 0.050000),
        _row("ELITE", 0.040000, eliminated=True),
        _row("ELITE", 0.056033),
    ])

    assert "STRAT_BEST_ELITE=0.054555" in lines


def test_no_elite_plan_writes_no_line(monkeypatch) -> None:
    bench = _bench()
    lines: list[str] = []
    monkeypatch.setattr(bench, "emit", lines.append)
    bench.dump_strat_ranking([_row("LOCAL_SEARCH", 0.03)])

    assert not [line for line in lines if line.startswith("STRAT_BEST_ELITE")]
