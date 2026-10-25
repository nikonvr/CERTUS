"""The operator's Rate rules reach every evaluated plan and the local search, and change nothing when unset.

Rules of the owner for the 90-layer Bonne Mere strategy (2026-10-24): no Rate before layer 10, Rate only if n.d <= 50 nm,
75 % of the layers optical. Before, STRAT had no such setting and laid 61 of the 90 layers by Rate.
"""

from __future__ import annotations

import logging

import numpy as np

import certus.core.certus_strat_robustness as robustness
from certus.core.certus_strat_local_search import LocalSearchConfig, candidates

N_LAYERS = 10
L0 = 550.0
# n(l0).d = multiplier . l0 / 4: layers 3, 5, 7 are thin (27.5, 41.25, 13.75 nm), the others 137.5 nm
MULTIPLIERS = [1.0, 1.0, 1.0, 0.2, 1.0, 0.3, 1.0, 0.1, 1.0, 1.0]
RULED = {"stack_string": ",".join(str(m) for m in MULTIPLIERS), "l0": L0,
         "rate_min_layer": 4, "rate_max_optical_thickness_nm": 50.0}


def _plan(rate_layers):
    return {"strategy_id": 1, "blocks": [{"start": k, "end": k + 1, "wavelength": 600.0} for k in range(N_LAYERS)],
            "rate_layers": list(rate_layers)}


def test_the_rules_keep_only_the_allowed_rate_layers() -> None:
    from certus.core.certus_strat_rate_rules import optical_thicknesses_nm, rate_rules_from_params, sanitize_rate_layers

    ot = optical_thicknesses_nm(RULED)
    kept, converted = sanitize_rate_layers([2, 3, 5, 6, 7], rate_rules_from_params(RULED), ot)
    assert (kept, converted) == ([5, 7], [2, 3, 6])  # 2 and 3 before layer 4, 6 too thick


def test_over_the_share_the_thickest_rate_layers_go_optical_first() -> None:
    from certus.core.certus_strat_rate_rules import optical_thicknesses_nm, rate_rules_from_params, sanitize_rate_layers

    params = {**RULED, "rate_min_layer": 0, "rate_max_optical_thickness_nm": 0, "rate_max_fraction": 0.2}  # at most 2 of 10
    kept, converted = sanitize_rate_layers([3, 5, 7, 9], rate_rules_from_params(params), optical_thicknesses_nm(params))
    assert (kept, converted) == ([3, 7], [5, 9])


def test_every_plan_the_pool_evaluates_obeys_the_rules(monkeypatch) -> None:
    seen = []

    def fake_task(strategy, _idx, noise_levels, *_args, **_kwargs):
        seen.append(list(strategy["rate_layers"]))
        return {"strategy": dict(strategy), "strategy_id": strategy["strategy_id"], "robustness_score": 0.01, "crash_rate": 0.0,
                "results_per_noise": [{"noise_level": lv, "thicknesses_all": [[100.0] * N_LAYERS]} for lv in noise_levels]}

    monkeypatch.setattr(robustness, "_test_strategy_robustness_task", fake_task)
    monkeypatch.setattr(robustness, "_calculate_strategy_spectral_resolution", lambda *a, **k: (2.0, -1, 0.0))
    plan = _plan([2, 5, 6, 7])
    out = robustness._execute_robustness_tasks(
        [plan], [0.05], 1, [100.0] * N_LAYERS, {}, {}, np.array([550.0]), np.array([2.3]), np.array([1.5]), np.array([1.5]),
        np.array([0.9]), {}, dict(RULED), logging.getLogger("rules"))
    assert seen == [[5, 7]]
    assert out[0]["strategy"]["rate_layers"] == [5, 7]
    assert plan["rate_rules_converted"] == [2, 6]


def test_without_rules_the_pool_leaves_the_plans_untouched(monkeypatch) -> None:
    seen = []

    def fake_task(strategy, _idx, noise_levels, *_args, **_kwargs):
        seen.append(dict(strategy))
        return {"strategy": dict(strategy), "strategy_id": strategy["strategy_id"], "robustness_score": 0.01, "crash_rate": 0.0,
                "results_per_noise": [{"noise_level": lv, "thicknesses_all": [[100.0] * N_LAYERS]} for lv in noise_levels]}

    monkeypatch.setattr(robustness, "_test_strategy_robustness_task", fake_task)
    monkeypatch.setattr(robustness, "_calculate_strategy_spectral_resolution", lambda *a, **k: (2.0, -1, 0.0))
    plan = _plan([2, 5, 6, 7])
    robustness._execute_robustness_tasks(
        [plan], [0.05], 1, [100.0] * N_LAYERS, {}, {}, np.array([550.0]), np.array([2.3]), np.array([1.5]), np.array([1.5]),
        np.array([0.9]), {}, {"stack_string": RULED["stack_string"], "l0": L0}, logging.getLogger("rules"))
    assert seen == [_plan([2, 5, 6, 7])]


def test_the_local_search_offers_rate_only_where_the_rules_allow_it() -> None:
    grid = tuple(float(w) for w in range(450, 751, 10))
    cfg = LocalSearchConfig(grid=grid, rate_allowed=frozenset({5, 7}), rate_cap=2)
    labels = lambda plan, k: [label for label, _ in candidates(plan, k, cfg)]  # noqa: E731
    assert "L6 Rate" not in labels(_plan([]), 6)
    assert "L5 Rate" in labels(_plan([]), 5)
    assert "L7 Rate" not in labels(_plan([3, 5]), 7)  # the cap of 2 is reached


def test_the_local_search_scans_the_whole_grid_of_a_layer_the_rules_laid_optically() -> None:
    grid = tuple(float(w) for w in range(450, 751, 10))
    cfg = LocalSearchConfig(grid=grid, repair_layers=frozenset({6}))
    wavelengths = {label.split("@")[1] for label, _ in candidates(_plan([]), 6, cfg) if "optical@" in label}
    assert len(wavelengths) == len(grid) - 1  # every grid wavelength but the current 600 nm


def test_with_final_only_the_pool_leaves_the_plans_free(monkeypatch) -> None:
    seen = []

    def fake_task(strategy, _idx, noise_levels, *_args, **_kwargs):
        seen.append(list(strategy["rate_layers"]))
        return {"strategy": dict(strategy), "strategy_id": strategy["strategy_id"], "robustness_score": 0.01, "crash_rate": 0.0,
                "results_per_noise": [{"noise_level": lv, "thicknesses_all": [[100.0] * N_LAYERS]} for lv in noise_levels]}

    monkeypatch.setattr(robustness, "_test_strategy_robustness_task", fake_task)
    monkeypatch.setattr(robustness, "_calculate_strategy_spectral_resolution", lambda *a, **k: (2.0, -1, 0.0))
    robustness._execute_robustness_tasks(
        [_plan([2, 5, 6, 7])], [0.05], 1, [100.0] * N_LAYERS, {}, {}, np.array([550.0]), np.array([2.3]), np.array([1.5]),
        np.array([1.5]), np.array([0.9]), {}, {**RULED, "rate_rules_final_only": True}, logging.getLogger("rules"))
    assert seen == [[2, 5, 6, 7]]


def test_the_final_search_lays_each_forbidden_layer_optically_at_its_best_wavelength() -> None:
    from certus.core.certus_strat_local_search import joint_local_search, wavelength_of

    best = {2: 520.0, 6: 680.0}

    def evaluate(plan, _seed, runs):
        rate = set(plan["rate_layers"])
        err = sum(0.0 if k in rate else abs(wavelength_of(plan, k) - w) / 100.0 for k, w in best.items())
        rmse = np.full(runs, 0.01 + err)
        return [(rmse, np.zeros(runs, dtype=bool))] * 3

    grid = tuple(float(w) for w in range(450, 751, 10))
    cfg = LocalSearchConfig(grid=grid, passes=0, search_runs=8, check_runs=8, rate_allowed=frozenset({5, 7}))
    plan, report = joint_local_search(_plan([2, 5, 6, 7]), evaluate, N_LAYERS, cfg, 1, (2,), convert=(2, 6))
    assert plan["rate_layers"] == [5, 7]
    assert (wavelength_of(plan, 2), wavelength_of(plan, 6)) == (520.0, 680.0)
    assert report["rule_conversions"] == ["L2 optical@520", "L6 optical@680"]


def test_the_free_stage_runs_before_the_forbidden_layers_are_converted(monkeypatch) -> None:
    """As by hand: the free search stage first, then the forbidden Rate layers of its winner are laid optically."""
    import certus.core.certus_strat_ranking as ranking
    import certus.core.certus_strat_robustness as robustness
    import certus.workers.certus_strat_workers_local_search as wls

    calls = []

    def fake_joint(start, _evaluate, _n, cfg, *_args, convert=(), **_kwargs):
        calls.append({"start_rate": list(start["rate_layers"]), "convert": tuple(convert), "allow_rate": cfg.allow_rate})
        if not convert:  # the free stage finds Rate layers the rules forbid
            return {**start, "rate_layers": [2, 6, 7]}, {"accepted": True, "changes": []}
        return {**start, "rate_layers": [7]}, {"accepted": True, "changes": []}

    class NoClues:
        def __init__(self, _info) -> None:
            pass

        def __enter__(self):
            return None

        def __exit__(self, *_exc) -> bool:
            return False

    monkeypatch.setattr(wls, "SharedIndicesWorker", NoClues)
    monkeypatch.setattr(wls, "joint_local_search", fake_joint)
    monkeypatch.setattr(wls, "native_evaluator", lambda *_a, **_k: None)
    monkeypatch.setattr(wls, "search_params", lambda _p: {"index_corridor": 0.0})
    monkeypatch.setattr(wls, "nominal_level_index", lambda _p: 0)
    monkeypatch.setattr(ranking, "_resolve_monitoring_wavelength_grid", lambda *_a, **_k: [550.0])
    monkeypatch.setattr(robustness, "run_final_simulation_block",
                        lambda ctx, *_a, **_k: {"all_strategies_results": [{"strategy": ctx["all_strategies"][0]}]})
    params = {**RULED, "rate_rules_final_only": True, "logger": logging.getLogger("rules")}
    pre = {"p_thick_nominal": [100.0] * N_LAYERS, "all_wls": [550.0], "nominal_matrix_cache": {}}
    wls.run_local_search([{"strategy": _plan([2, 5])}], pre, params, {}, lambda rows: rows)
    assert len(calls) == 2
    assert calls[0]["convert"] == ()
    assert calls[1]["start_rate"] == [2, 6, 7]
    assert calls[1]["convert"] == (2, 6)
