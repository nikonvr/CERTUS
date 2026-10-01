"""The three stages that end `_parallel_block_worker` are functions of their own (audit v2, plan S5.2).

`_parallel_block_worker` ran one block count of the STRAT search in a worker process: 369 lines in one `try`. Its last three stages come out, each pinned here with the simulator replaced by a fake that
records what it was asked:

    _screen_inherited_strategies    keeps the inherited plans that have this block count and respect the block contract, simulates them, returns the best `k_keep`
    _confirm_unique_survivors       drops the survivors with the same signature (the mined ones win), confirms the rest with the full Monte Carlo budget
    _publish_best_strategy          finds the most robust result and puts it on the live queue, without ever letting the queue break the worker
"""

from __future__ import annotations

import logging

import pytest

from certus.workers import certus_strat_workers as workers


def plan(n_blocks: int, wavelength: float = 500.0, tag: str = "") -> dict:
    return {"n_blocks": n_blocks, "blocks": [{"start": k, "end": k + 1, "wavelength": wavelength + k} for k in range(n_blocks)], "id": tag}


def result(strategy: dict, score: float) -> dict:
    return {"strategy": strategy, "robustness_score": score}


class Simulator:
    """Stands for `run_final_simulation_block`: records its calls and answers with the scores given per strategy tag."""

    def __init__(self, scores: dict[str, float], answer_key: str = "all_strategies_results") -> None:
        self.scores = scores
        self.answer_key = answer_key
        self.calls: list[dict] = []

    def __call__(self, context, params, **kwargs):
        self.calls.append({"strategies": list(context["all_strategies"]), "kwargs": kwargs, "context": context})
        return {self.answer_key: [result(s, self.scores[s["id"]]) for s in context["all_strategies"]]}


@pytest.fixture
def stats(monkeypatch):
    seen: list[tuple] = []
    monkeypatch.setattr(workers, "_emit_stat", lambda kind, n: seen.append((kind, n)))
    return seen


def install(monkeypatch, simulator: Simulator, valid=lambda strategy: True):
    monkeypatch.setattr(workers, "run_final_simulation_block", simulator)
    monkeypatch.setattr(workers, "_validate_strategy_blocks_contract", lambda s, n_layers, expected_n_blocks: (valid(s), ""))


# --- _screen_inherited_strategies ----------------------------------------------------------------------------------------------------


def test_no_inherited_plan_means_no_simulation(monkeypatch, stats):
    sim = Simulator({})
    install(monkeypatch, sim)
    assert workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 5, []) == []
    assert workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 5, None) == []
    assert sim.calls == []
    assert stats == []


def test_only_plans_with_this_block_count_that_respect_the_contract_are_simulated(monkeypatch, stats):
    plans = [plan(3, tag="a"), plan(2, tag="wrong count"), plan(3, tag="b"), plan(3, tag="breaks the contract")]
    sim = Simulator({"a": 0.2, "b": 0.1})
    install(monkeypatch, sim, valid=lambda s: s["id"] != "breaks the contract")
    workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 5, plans)
    assert [s["id"] for s in sim.calls[0]["strategies"]] == ["a", "b"]
    assert stats == [("MS", 2)]


def test_the_simulation_is_a_screening_without_variants_and_works_on_a_copy_of_the_context(monkeypatch, stats):
    context = {"num_layers": 9, "marker": 1}
    sim = Simulator({"a": 0.2})
    install(monkeypatch, sim)
    workers._screen_inherited_strategies(3, context, {"p": 1}, 12, 5, [plan(3, tag="a")])
    assert sim.calls[0]["kwargs"] == {"num_runs": 12, "expand_variants": False}
    assert sim.calls[0]["context"] is not context
    assert "all_strategies" not in context


def test_the_best_k_keep_by_robustness_come_back_best_first(monkeypatch, stats):
    plans = [plan(3, tag=t) for t in "abcd"]
    sim = Simulator({"a": 0.4, "b": 0.1, "c": 0.3, "d": 0.2})
    install(monkeypatch, sim)
    kept = workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 2, plans)
    assert [r["strategy"]["id"] for r in kept] == ["b", "d"]


def test_a_simulation_that_answers_nothing_keeps_nothing(monkeypatch, stats):
    install(monkeypatch, Simulator({"a": 0.1}, answer_key="something else"))
    assert workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 5, [plan(3, tag="a")]) == []


def test_when_no_plan_is_valid_nothing_is_counted_or_simulated(monkeypatch, stats):
    sim = Simulator({})
    install(monkeypatch, sim, valid=lambda s: False)
    assert workers._screen_inherited_strategies(3, {"num_layers": 9}, {}, 10, 5, [plan(3, tag="a")]) == []
    assert sim.calls == []
    assert stats == []


# --- _confirm_unique_survivors -------------------------------------------------------------------------------------------------------


def test_survivors_with_the_same_signature_are_dropped_and_the_first_one_wins(monkeypatch):
    mined = [result(plan(2, 500.0, "mined"), 0.3)]
    inherited = [result(plan(2, 500.0, "inherited twin"), 0.2), result(plan(2, 650.0, "other"), 0.25)]
    sim = Simulator({"mined": 0.31, "other": 0.26})
    install(monkeypatch, sim)
    final, unique = workers._confirm_unique_survivors(2, {"num_layers": 9}, {}, 10, 100, logging.getLogger("t"), mined, inherited)
    assert [r["strategy"]["id"] for r in unique] == ["mined", "other"]
    assert [s["id"] for s in sim.calls[0]["strategies"]] == ["mined", "other"]
    assert [r["strategy"]["id"] for r in final] == ["mined", "other"]


def test_the_confirmation_runs_with_the_larger_of_the_two_budgets(monkeypatch):
    sim = Simulator({"a": 0.1})
    install(monkeypatch, sim)
    survivors = [result(plan(2, tag="a"), 0.1)]
    workers._confirm_unique_survivors(2, {"num_layers": 9}, {}, n_screen=10, n_full=100, logger=logging.getLogger("t"), survivors_dp=survivors, survivors_inherited=[])
    workers._confirm_unique_survivors(2, {"num_layers": 9}, {}, n_screen=200, n_full=50, logger=logging.getLogger("t"), survivors_dp=survivors, survivors_inherited=[])
    assert [c["kwargs"]["num_runs"] for c in sim.calls] == [100, 200]


def test_without_survivors_there_is_no_confirmation_pass(monkeypatch):
    sim = Simulator({})
    install(monkeypatch, sim)
    assert workers._confirm_unique_survivors(2, {"num_layers": 9}, {}, 10, 100, logging.getLogger("t"), [], []) == ([], [])
    assert sim.calls == []


def test_a_confirmation_that_answers_nothing_gives_no_result_but_the_survivors_are_still_returned(monkeypatch):
    install(monkeypatch, Simulator({"a": 0.1}, answer_key="nope"))
    survivors = [result(plan(2, tag="a"), 0.1)]
    final, unique = workers._confirm_unique_survivors(2, {"num_layers": 9}, {}, 10, 100, logging.getLogger("t"), survivors, [])
    assert final == []
    assert unique == survivors


# --- _publish_best_strategy ----------------------------------------------------------------------------------------------------------


class Queue:
    def __init__(self, broken: bool = False) -> None:
        self.items: list[dict] = []
        self.broken = broken

    def put(self, item) -> None:
        if self.broken:
            raise OSError("queue closed")
        self.items.append(item)


def test_the_most_robust_result_is_returned_and_put_on_the_queue():
    q = Queue()
    results = [result(plan(2, tag="a"), 0.4), result(plan(2, tag="b"), 0.1), result(plan(2, tag="c"), 0.3)]
    best = workers._publish_best_strategy(2, logging.getLogger("t"), q, results)
    assert best["strategy"]["id"] == "b"
    assert q.items == [{"strategy": results[1]["strategy"], "robustness_score": 0.1, "n_blk": 2, "block_number": 2}]


def test_without_a_queue_the_best_is_found_and_nothing_is_put():
    results = [result(plan(2, tag="a"), 0.4), result(plan(2, tag="b"), 0.1)]
    assert workers._publish_best_strategy(2, logging.getLogger("t"), None, results)["strategy"]["id"] == "b"


def test_a_broken_queue_is_logged_and_never_breaks_the_worker(caplog):
    results = [result(plan(2, tag="a"), 0.4)]
    with caplog.at_level(logging.ERROR):
        best = workers._publish_best_strategy(2, logging.getLogger("t"), Queue(broken=True), results)
    assert best is not None
    assert any("Failed to put into live_queue" in r.getMessage() for r in caplog.records)


def test_no_result_means_no_best_and_nothing_is_put():
    q = Queue()
    assert workers._publish_best_strategy(2, logging.getLogger("t"), q, []) is None
    assert q.items == []


def test_the_worker_calls_the_three_stages_in_order():
    import inspect

    source = inspect.getsource(workers._parallel_block_worker)
    positions = [source.index(name + "(") for name in ("_screen_inherited_strategies", "_confirm_unique_survivors", "_publish_best_strategy")]
    assert positions == sorted(positions)
