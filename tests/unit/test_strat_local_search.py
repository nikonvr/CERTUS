"""The final joint (mode, wavelength) local search keeps only what wins, never adds a stop, and gives the winner back
when fresh draws do not confirm it (`certus/core/certus_strat_local_search.py`, `strat_local_search`, off by default).

The evaluator is synthetic and paired like STRAT's (draws a pure function of the seed, C2): each layer has a best
wavelength, a few wavelengths make the draws stop, and Rate costs a fixed amount per layer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

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
    assert 'final_result_dict.final_results["strat_local_search"] = ls_report' in pipeline
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
