"""The final joint (mode, wavelength) local search keeps only what wins, never adds a stop, and gives the winner back
when fresh draws do not confirm it (`certus/core/certus_strat_local_search.py`, `strat_local_search`, on by default).

The evaluator is synthetic and paired like STRAT's (draws a pure function of the seed, C2): each layer has a best
wavelength, a few wavelengths make the draws stop, and Rate costs a fixed amount per layer.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from certus.core.certus_strat_local_search import (
    LocalSearchConfig,
    candidates,
    is_armed,
    joint_local_search,
    search_params,
    stops,
    wavelength_of,
    with_wavelength,
)

GRID = tuple(float(w) for w in range(450, 752, 2))
BEST = {0: 500.0, 1: 520.0, 2: 610.0, 3: 640.0, 4: 700.0, 5: 470.0}
STOP_AT = {(3, 600.0)}  # layer 3 monitored at 600 nm stops every draw


def _plan() -> dict:
    return {"strategy_id": 7, "blocks": [{"start": 0, "end": 6, "wavelength": 560.0}], "rate_layers": [4],
            "witness_reset_layers": [], "monochromator_resolution_nm": 2.0}


def _evaluator(rate_cost: float = 4.0, trap: bool = False):
    """trap: on search seeds (< 100) only, layer 2 at 650 nm looks better than its best wavelength; it is really worse."""
    def evaluate(plan, seed, runs):
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, 1.0, size=(3, runs))
        err = 1.0
        stopped = np.zeros(runs, dtype=bool)
        for k in range(6):
            if k in plan["rate_layers"]:
                err += rate_cost
            else:
                wl = wavelength_of(plan, k)
                err += ((wl - BEST[k]) / 40.0) ** 2
                if (k, wl) in STOP_AT:
                    stopped[:] = True
        if trap and seed < 100 and wavelength_of(plan, 2) == 650.0 and 2 not in plan["rate_layers"]:
            err -= 2.0  # an illusion seen on the search seed only; the real cost of 650 nm is (40/40)^2 = 1
        return [(np.abs(err * (1.0 + 0.1 * noise[i])), stopped.copy()) for i in range(3)]
    return evaluate


def _cfg(**kw) -> LocalSearchConfig:
    return LocalSearchConfig(grid=GRID, search_runs=200, check_runs=400, **kw)


def test_the_search_moves_every_layer_towards_its_best_wavelength_and_the_check_keeps_it() -> None:
    plan, report = joint_local_search(_plan(), _evaluator(), 6, _cfg(), 11, (101, 102))
    assert report["accepted"]
    assert plan["rate_layers"] == []  # Rate costs more than any wavelength error here
    for k, best in BEST.items():
        assert abs(wavelength_of(plan, k) - best) <= 10.0, (k, wavelength_of(plan, k))


def test_a_candidate_that_adds_a_stop_is_never_kept() -> None:
    plan, _report = joint_local_search(_plan(), _evaluator(), 6, _cfg(), 11, (101, 102))
    assert wavelength_of(plan, 3) != 600.0
    assert stops(_evaluator()(plan, 5, 50)) == 0


def test_the_winner_comes_back_unchanged_when_fresh_draws_refuse_the_search() -> None:
    start = {"strategy_id": 1, "blocks": [{"start": k, "end": k + 1, "wavelength": BEST[k]} for k in range(6)], "rate_layers": []}
    plan, report = joint_local_search(start, _evaluator(trap=True), 6, _cfg(), 11, (101, 102))
    assert report["changes"] == ["L2 610->650"]  # the search fell for it
    assert not report["accepted"]
    assert plan is start


def test_a_local_optimum_is_returned_as_is() -> None:
    start = {"strategy_id": 1, "blocks": [{"start": k, "end": k + 1, "wavelength": BEST[k]} for k in range(6)], "rate_layers": []}
    plan, report = joint_local_search(start, _evaluator(), 6, _cfg(step_nm=2.0, span_nm=2.0), 11, (101, 102))
    assert plan is start
    assert report["changes"] == []


def test_candidates_stay_on_the_control_grid_and_respect_the_rate_rules() -> None:
    plan = _plan()
    grid = set(GRID)
    labels = [lab for lab, _p in candidates(plan, 2, _cfg(step_nm=5.0))]
    assert all(float(lab.split("->")[1]) in grid for lab in labels if "->" in lab)
    assert any(lab.endswith("Rate") for lab in labels)
    assert not any(lab.endswith("Rate") for lab, _p in candidates(plan, 1, _cfg()))  # below RATE_MIN_LAYER
    assert not any(lab.endswith("Rate") for lab, _p in candidates(plan, 2, _cfg(allow_rate=False)))
    to_optical = list(candidates(plan, 4, _cfg()))
    assert to_optical
    assert all(4 not in p["rate_layers"] for _lab, p in to_optical)


def test_changing_one_layer_leaves_its_neighbours_on_their_wavelength() -> None:
    plan = with_wavelength(_plan(), 2, 610.0)
    assert [wavelength_of(plan, k) for k in range(6)] == [560.0, 560.0, 610.0, 560.0, 560.0, 560.0]
    assert plan["blocks"] == [{"start": 0, "end": 2, "wavelength": 560.0}, {"start": 2, "end": 3, "wavelength": 610.0},
                              {"start": 3, "end": 6, "wavelength": 560.0}]


def test_the_pipeline_runs_the_stage_by_default_and_a_configuration_can_turn_it_off() -> None:
    """On by default since 2026-10-20 (owner); `strat_local_search: false` gives the former path back."""
    assert is_armed({})
    assert not is_armed({"strat_local_search": False})
    root = Path(__file__).resolve().parents[2]
    pipeline = (root / "certus" / "workers" / "certus_strat_workers_pipeline.py").read_text(encoding="utf-8")
    assert "if is_armed(worker.params):" in pipeline
    # the report goes into `final_results`, the dict the probe and the exports read, not onto the result object
    ui = (root / "certus" / "ui" / "certus_strat_ui_state.py").read_text(encoding="utf-8")
    assert '"strat_local_search": _config_flag_default(getattr(self, "_loaded_config", {}), "strat_local_search", True)' in ui


def test_the_stage_searches_under_twice_the_nominal_index_uncertainty_never_less_than_configured() -> None:
    """Decided 2026-10-20: searched at +-0.010, plans stop 0 and 10 times instead of 175 and 230 at +-0.010."""
    assert search_params({"index_corridor": 0.005})["index_corridor"] == 0.010
    assert search_params({"index_corridor": 0.02})["index_corridor"] == 0.02
    assert search_params({"index_corridor": 0.005, "robustness_seed": 3})["robustness_seed"] == 3
    root = Path(__file__).resolve().parents[2]
    worker = (root / "certus" / "workers" / "certus_strat_workers_local_search.py").read_text(encoding="utf-8")
    assert "native_evaluator(search_params(params)," in worker


@pytest.mark.parametrize("outcome", ["disabled", "accepted", "refused"])
def test_full_pipeline_emits_the_legacy_payload_with_the_local_search_report(monkeypatch, outcome):
    """Exercise the real worker boundary without running the numerical search or Qt threads."""
    from certus.core.certus_strat_workers_dto import WorkerThreadResult
    from certus.workers import certus_strat_workers as workers
    from certus.workers import certus_strat_workers_local_search as local_search
    from certus.workers import certus_strat_workers_pipeline as pipeline

    report = None if outcome == "disabled" else {"accepted": outcome == "accepted", "changes": []}
    strategies = [{"robustness_score": 0.125, "crash_rate": 0.0}]
    payload = WorkerThreadResult.for_step_23(
        opti_results={}, final_results={"all_strategies_results": strategies},
    ).to_legacy_dict()
    final_results = payload["final_results"]
    pre_calc = {
        "num_layers": 2, "raw_results_sq": {}, "raw_results_thickness": {},
        "p_thick_nominal": [10.0, 20.0], "clues_at_wl": {}, "nominal_matrix_cache": None, "all_wls": [],
    }
    worker = SimpleNamespace(
        params={"logger": MagicMock(), "nH_id": "H", "nL_id": "L", "nSub_id": "S", "l0": 550.0,
                "strat_local_search": outcome != "disabled"},
        signals=MagicMock(), timing_logger=None,
    )
    monkeypatch.setattr(pipeline, "APP_CONTEXT", {})
    monkeypatch.setattr(pipeline, "QThread", MagicMock)
    monkeypatch.setattr(pipeline, "QMetaObject", MagicMock())
    monkeypatch.setattr(pipeline, "SharedIndicesManager", MagicMock())
    monkeypatch.setattr(pipeline, "SharedArrayManager", MagicMock())
    monkeypatch.setattr(pipeline, "_init_stats_queue", MagicMock())
    monkeypatch.setattr(pipeline, "_compute_blocks_range_for_params", lambda *_args, **_kw: [1])
    monkeypatch.setattr(workers, "StatsConsumerWorker", MagicMock())
    monkeypatch.setattr(workers, "LiveFeedMonitor", MagicMock())
    monkeypatch.setattr(workers, "_execute_nucleation_and_cost_mapping", lambda **_kw: (pre_calc, [], {}, {}))
    monkeypatch.setattr(workers, "_run_phaseB_parallel_execution", lambda **_kw: strategies)
    finalize = MagicMock(return_value=payload)
    monkeypatch.setattr(workers, "_finalize_and_export_pipeline_results", finalize)
    search = MagicMock(return_value=(strategies, report, object()))
    monkeypatch.setattr(local_search, "run_local_search", search)

    pipeline.FullPipelineStrategy().execute(worker)

    worker.signals.finished.emit.assert_called_once_with(payload)
    assert worker.signals.finished.emit.call_args.args[0] is payload
    assert payload["final_results"] is final_results
    assert final_results["all_strategies_results"] is strategies
    if outcome == "disabled":
        search.assert_not_called()
        assert "strat_local_search" not in final_results
        assert "ranker" not in finalize.call_args.kwargs
    else:
        search.assert_called_once()
        assert final_results["strat_local_search"] is report


def test_when_the_final_plan_is_refused_an_intermediate_plan_confirmed_on_other_seeds_is_kept() -> None:
    """A5, r75x0.5 seed 101: a late change made the check stop (19 in 6 000) and threw the whole search away."""
    base = _evaluator()

    def evaluate(plan, seed, runs):
        ev = base(plan, seed, runs)
        if seed >= 100 and wavelength_of(plan, 5) != 560.0:  # the change of the last layer stops rarely, unseen at search
            ev = [(r, s.copy()) for r, s in ev]
            ev[0][1][0] = True
        return ev

    start = _plan()
    plan, report = joint_local_search(start, evaluate, 6, _cfg(passes=1), 11, (101, 102), confirm_seeds=(201, 202))
    assert report["check_stops"][1] > report["check_stops"][0]  # the final plan is refused
    assert report["accepted"]
    assert report["fallback_changes"] < len(report["changes"])
    assert wavelength_of(plan, 5) == 560.0
    assert stops(evaluate(plan, 201, 400)) == 0


def test_without_confirmation_seeds_a_refused_search_gives_the_winner_back() -> None:
    base = _evaluator()

    def evaluate(plan, seed, runs):
        ev = base(plan, seed, runs)
        if seed >= 100 and wavelength_of(plan, 5) != 560.0:
            ev = [(r, s.copy()) for r, s in ev]
            ev[0][1][0] = True
        return ev

    start = _plan()
    plan, report = joint_local_search(start, evaluate, 6, _cfg(passes=1), 11, (101, 102))
    assert not report["accepted"]
    assert plan is start
