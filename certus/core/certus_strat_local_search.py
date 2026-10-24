"""Joint paired local search over (monitoring mode, wavelength), layer by layer, on a finished STRAT plan.

WHY THIS EXISTS. The Bonne Mere study, then r75 / r75x0.5 / r75x2 (reports/STRAT_r75_leviers_bonne_mere_2026-10-20):
every lever that generalises is LOCAL and PAIRED -- change the wavelength of one layer, or its mode (Rate <-> optical),
keep the change when the paired mean RMSE^2 at the nominal noise drops and no stop is added. Searched jointly, they
beat the STRAT winner on all three designs (holdout SEEL 0.2455 -> 0.2132, 0.4376 -> 0.3467, 0.5411 -> 0.4729 nm) and
every lever taken alone. Global rules (thin layers in Rate, all-optical, a common head wavelength, a projected target)
lose.

THE STAGE. Starting from the winner, `passes` sweeps from the substrate to the air; for each layer the candidates are
  optical layer: its wavelength +- span_nm on the control grid, step step_nm, or monitored by Rate;
  Rate layer:    monitored optically at every step_nm of the control grid.
The best candidate is kept at once when, on the search seed, it adds no stop over the noise levels and lowers the
paired mean RMSE^2 at the nominal level. Draws are a pure function of the seed (C2): every candidate sees the same
realisation, so the comparison is paired.

THE HARDENED CHECK. The search seed is small (300 draws) and visited thousands of times; on r75x2 the plan it froze
showed 2 stops in 9 000 holdout draws for 0 at the search. So the frozen plan is judged once against the start on
`check_seeds` it never saw (check_runs draws each): it is kept only with no more stops, a paired gain beyond two
standard errors and a P95 score (max over levels) not above the start's.

THE FALLBACK. All or nothing threw good searches away: r75x0.5, bench seed 101 (A5, 2026-10-21), check at +-0.010:
RMSE^2 -62 %, P95 0.0503 -> 0.0358, but 19 stops in 6 000 draws for 0, so the winner came back unchanged. Stops that
rare are invisible at 300 draws and usually enter with a few late changes. When the final plan is refused, up to
MAX_FALLBACK_PLANS intermediate plans of the search (the plan after k kept changes) are judged on the same check
draws; the best admissible one must pass the same rule again on `confirm_seeds`, because choosing among several on
the check draws tunes the choice to them. Otherwise the start is returned unchanged.

ON BY DEFAULT since 2026-10-20 (`strat_local_search`, owner decision after the deep benches): a deliberate C1 break,
like the slit bias; `strat_local_search: false` in the configuration gives the former path back.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np


def is_armed(params: dict[str, Any]) -> bool:
    """Whether the pipeline runs the stage. On by default (owner, 2026-10-20)."""
    return bool(params.get("strat_local_search", True))


#: Seeds of the stage, offsets of `robustness_seed`: disjoint from the ranking seed, so the stage neither reuses nor
#: biases the draws the winner was ranked on.
SEARCH_SEED_OFFSET: int = 7_000_003
CHECK_SEED_OFFSETS: tuple[int, ...] = (7_100_003, 7_100_011)
#: Seeds that confirm an intermediate plan chosen on the check seeds (the choice is tuned to those draws).
CONFIRM_SEED_OFFSETS: tuple[int, ...] = (7_200_003, 7_200_011)
#: At most this many intermediate plans are re-judged when the check refuses the final one.
MAX_FALLBACK_PLANS: int = 12

#: Index uncertainty the stage searches and checks under: twice the nominal +-0.005 (decided 2026-10-20). Measured on
#: 75c / r75x0.5 / r75x2: plans searched at +-0.005 stop at +-0.010 (175 and 230 stops in 9 000 on 75c and r75x2);
#: searched at +-0.010 they stop 0 and 10 times, for a SEEL cost at +-0.005 of +1.0 %, +11.4 % and -3.5 %. Never below
#: the configured corridor. The winner is still ranked and reported under the configured corridor.
SEARCH_INDEX_CORRIDOR: float = 0.010


def search_params(params: dict[str, Any]) -> dict[str, Any]:
    """The parameters the stage searches and checks with: the configured ones under the search index uncertainty."""
    out = dict(params)
    out["index_corridor"] = max(SEARCH_INDEX_CORRIDOR, float(params.get("index_corridor", 0.0) or 0.0))
    return out

#: One evaluation: per noise level, (rmse per draw, stopped per draw).
Evaluation = list[tuple[np.ndarray, np.ndarray]]


@dataclass(frozen=True)
class LocalSearchConfig:
    """Settings of the stage. The defaults are the measured protocol."""

    grid: tuple[float, ...]
    nominal_level: int = 1
    passes: int = 2
    search_runs: int = 300
    check_runs: int = 1000
    span_nm: float = 60.0
    step_nm: float = 10.0
    allow_rate: bool = True
    rate_min_layer: int = 2
    #: The operator's Rate rules (certus_strat_rate_rules): layers allowed in Rate (None: all), largest Rate count (None: no
    #: cap), and the layers the rules laid optically, whose whole wavelength grid is scanned.
    rate_allowed: frozenset[int] | None = None
    rate_cap: int | None = None
    repair_layers: frozenset[int] = frozenset()


def wavelength_of(plan: dict[str, Any], layer: int) -> float | None:
    """The wavelength of the block that holds the layer, or None outside every block."""
    for blk in plan.get("blocks") or []:
        if int(blk["start"]) <= layer < int(blk["end"]):
            return float(blk["wavelength"])
    return None


def with_wavelength(plan: dict[str, Any], layer: int, wavelength: float) -> dict[str, Any]:
    """A copy of the plan where the layer is a block of its own at `wavelength`; its neighbours keep theirs."""
    blocks = []
    for blk in plan.get("blocks") or []:
        start, end, wl = int(blk["start"]), int(blk["end"]), float(blk["wavelength"])
        if start <= layer < end:
            if start < layer:
                blocks.append({"start": start, "end": layer, "wavelength": wl})
            blocks.append({"start": layer, "end": layer + 1, "wavelength": float(wavelength)})
            if layer + 1 < end:
                blocks.append({"start": layer + 1, "end": end, "wavelength": wl})
        else:
            blocks.append({"start": start, "end": end, "wavelength": wl})
    out = dict(plan)
    out["blocks"] = blocks
    return out


def _snap(grid: np.ndarray, values: np.ndarray) -> list[float]:
    """Nearest control-grid wavelength of each value, without duplicates, in increasing order."""
    idx = np.abs(grid[np.newaxis, :] - values[:, np.newaxis]).argmin(axis=1)
    return sorted({float(grid[i]) for i in idx})


def candidates(plan: dict[str, Any], layer: int, cfg: LocalSearchConfig) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every (label, plan) the stage tries for one layer."""
    grid = np.asarray(cfg.grid, dtype=np.float64)
    rate = set(int(r) for r in plan.get("rate_layers") or [])
    if layer in rate or layer in cfg.repair_layers:
        targets = np.arange(grid[0], grid[-1] + 1e-9, cfg.step_nm)
        wl0 = None if layer in rate else wavelength_of(plan, layer)
        for wl in _snap(grid, targets):
            if wl == wl0:
                continue
            out = with_wavelength(plan, layer, wl)
            out["rate_layers"] = sorted(rate - {layer})
            yield f"L{layer} optical@{wl:g}", out
        if layer in rate:
            return
    wl0 = wavelength_of(plan, layer)
    if wl0 is None:
        return
    if layer not in cfg.repair_layers:
        offsets = np.arange(-cfg.span_nm, cfg.span_nm + 1e-9, cfg.step_nm)
        for wl in _snap(grid, wl0 + offsets):
            if wl != wl0:
                yield f"L{layer} {wl0:g}->{wl:g}", with_wavelength(plan, layer, wl)
    if (cfg.allow_rate and layer >= cfg.rate_min_layer and (cfg.rate_allowed is None or layer in cfg.rate_allowed)
            and (cfg.rate_cap is None or len(rate) < cfg.rate_cap)):
        out = dict(plan)
        out["rate_layers"] = sorted(rate | {layer})
        yield f"L{layer} Rate", out


def stops(ev: Evaluation) -> int:
    """Stopped draws over every noise level."""
    return int(sum(int(np.count_nonzero(stopped)) for _rmse, stopped in ev))


def paired_delta(ref: Evaluation, new: Evaluation, level: int) -> tuple[float, float]:
    """Mean and standard error of rmse^2(new) - rmse^2(ref) at one level, over the draws both complete."""
    (r_ref, s_ref), (r_new, s_new) = ref[level], new[level]
    both = ~s_ref & ~s_new
    if not np.any(both):
        return float("inf"), float("inf")
    d = r_new[both] ** 2 - r_ref[both] ** 2
    se = float(d.std(ddof=1) / np.sqrt(d.size)) if d.size > 1 else float("inf")
    return float(d.mean()), se


def p95_score(ev: Evaluation) -> float:
    """STRAT's score functional: P95 of the rmse, max over the noise levels."""
    return max(float(np.percentile(rmse, 95)) for rmse, _stopped in ev)


def _concat(evs: list[Evaluation]) -> Evaluation:
    return [(np.concatenate([e[i][0] for e in evs]), np.concatenate([e[i][1] for e in evs])) for i in range(len(evs[0]))]


def joint_local_search(
    start: dict[str, Any],
    evaluate: Callable[[dict[str, Any], int, int], Evaluation],
    n_layers: int,
    cfg: LocalSearchConfig,
    search_seed: int,
    check_seeds: tuple[int, ...],
    log: Callable[[str], None] = lambda _msg: None,
    confirm_seeds: tuple[int, ...] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the stage; return (plan, report). The plan is `start` itself when the check refuses the search."""
    current = copy.deepcopy(start)
    cur_ev = evaluate(current, search_seed, cfg.search_runs)
    kept: list[str] = []
    history: list[dict[str, Any]] = []  # the plan after each kept change
    n_eval = 1
    for pass_no in range(1, cfg.passes + 1):
        for layer in range(n_layers):
            best: tuple[float, str, dict[str, Any], Evaluation] | None = None
            for label, plan in candidates(current, layer, cfg):
                ev = evaluate(plan, search_seed, cfg.search_runs)
                n_eval += 1
                if stops(ev) > stops(cur_ev):
                    continue
                d, _se = paired_delta(cur_ev, ev, cfg.nominal_level)
                if d < 0.0 and (best is None or d < best[0]):
                    best = (d, label, plan, ev)
            if best is not None:
                current, cur_ev = best[2], best[3]
                kept.append(best[1])
                history.append(current)
        log(f"[LOCAL-SEARCH] pass {pass_no}: {len(kept)} changes, {len(current.get('rate_layers') or [])} Rate layers, "
            f"{n_eval} evaluations")
    report: dict[str, Any] = {"changes": kept, "evaluations": n_eval, "search_seed": search_seed,
                              "check_seeds": list(check_seeds), "accepted": False}
    if not kept:
        log("[LOCAL-SEARCH] no change kept: the winner is already a local optimum")
        return start, report
    ref = _concat([evaluate(start, s, cfg.check_runs) for s in check_seeds])
    new = _concat([evaluate(current, s, cfg.check_runs) for s in check_seeds])
    ok, verdict = _judge(ref, new, cfg)
    report.update(verdict)
    report["accepted"] = ok
    log(f"[LOCAL-SEARCH] check on {len(check_seeds)} fresh seeds: dRMSE2 {100 * verdict['check_relative_gain']:+.1f} % "
        f"(SE {100 * verdict['check_relative_se']:.1f} %), stops {stops(ref)} -> {stops(new)}, "
        f"P95 {p95_score(ref):.5f} -> {p95_score(new):.5f}: {'kept' if ok else 'refused'}")
    if ok:
        return current, report
    if not confirm_seeds or len(history) < 2:
        log("[LOCAL-SEARCH] winner unchanged")
        return start, report
    picks = sorted({round(i * (len(history) - 1) / (MAX_FALLBACK_PLANS - 1)) for i in range(MAX_FALLBACK_PLANS)} - {len(history) - 1})
    best_k: tuple[float, int] | None = None
    for k in picks:
        ok_k, v_k = _judge(ref, _concat([evaluate(history[k], s, cfg.check_runs) for s in check_seeds]), cfg)
        if ok_k and (best_k is None or v_k["check_relative_gain"] < best_k[0]):
            best_k = (v_k["check_relative_gain"], k)
    report["fallback_tried"] = len(picks)
    if best_k is None:
        log(f"[LOCAL-SEARCH] none of {len(picks)} intermediate plans passes the check: winner unchanged")
        return start, report
    k = best_k[1]
    ref_c = _concat([evaluate(start, s, cfg.check_runs) for s in confirm_seeds])
    ok_c, v_c = _judge(ref_c, _concat([evaluate(history[k], s, cfg.check_runs) for s in confirm_seeds]), cfg)
    report.update(fallback_changes=k + 1, confirm_seeds=list(confirm_seeds),
                  confirm={key.replace("check_", ""): val for key, val in v_c.items()}, accepted=ok_c)
    log(f"[LOCAL-SEARCH] fallback: the plan after {k + 1} of {len(history)} changes, check dRMSE2 {100 * best_k[0]:+.1f} %; "
        f"confirmation dRMSE2 {100 * v_c['check_relative_gain']:+.1f} %, stops {v_c['check_stops'][0]} -> {v_c['check_stops'][1]}: "
        f"{'kept' if ok_c else 'refused, winner unchanged'}")
    return (history[k], report) if ok_c else (start, report)


def _judge(ref: Evaluation, new: Evaluation, cfg: LocalSearchConfig) -> tuple[bool, dict[str, Any]]:
    """The check rule: no more stops, a paired gain beyond two standard errors, a P95 score not above the reference."""
    d, se = paired_delta(ref, new, cfg.nominal_level)
    base = float(np.mean(ref[cfg.nominal_level][0][~ref[cfg.nominal_level][1]] ** 2))
    verdict = {"check_relative_gain": d / base if base > 0 else float("nan"),
               "check_relative_se": se / base if base > 0 else float("nan"),
               "check_stops": (stops(ref), stops(new)), "check_p95": (p95_score(ref), p95_score(new))}
    return bool(stops(new) <= stops(ref) and d < -2.0 * se and p95_score(new) <= p95_score(ref)), verdict


def nominal_level_index(params: dict[str, Any]) -> int:
    """Index of the nominal noise level (factor 1) in `robustness_noise_factors`, else the middle level."""
    from certus.core.certus_strat_robustness_noise import _parse_noise_factors

    factors = list(_parse_noise_factors(params.get("robustness_noise_factors", [0.5, 1.0, 2.0])))
    return factors.index(1.0) if 1.0 in factors else len(factors) // 2


def native_evaluator(
    params: dict[str, Any], p_thick_nominal: list[float], clues_at_wl: Any, full_dyn_grid: dict[str, Any]
) -> Callable[[dict[str, Any], int, int], Evaluation]:
    """evaluate(plan, seed, runs) through STRAT's own robustness task, set up as `run_final_simulation_block` does."""
    from certus.core.certus_strat_robustness import (
        _attach_slit_profiles,
        _precompute_layer_index_matrix,
        _prepare_robustness_nominal_optics,
    )
    from certus.core.certus_strat_robustness_noise import _resolve_robustness_noise_levels
    from certus.core.certus_strat_robustness_task import _test_strategy_robustness_task
    from certus.utils.certus_exclusions import filter_params_for_gui
    from certus_physics import CRASH_SENTINEL_MIN

    nominal = list(p_thick_nominal)
    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params=params, p_thick_nominal=nominal, opti_results={"clues_at_wl": clues_at_wl})
    matrix = _precompute_layer_index_matrix(nH_arr, nL_arr, len(nominal))
    levels = _resolve_robustness_noise_levels(params)
    logger = params["logger"]

    def evaluate(plan: dict[str, Any], seed: int, runs: int) -> Evaluation:
        seeded = dict(params)
        seeded["robustness_seed"] = int(seed)
        strategy = copy.deepcopy(plan)
        _attach_slit_profiles([strategy], nominal, seeded, logger)
        res = _test_strategy_robustness_task(strategy, 0, levels, int(runs), nominal, clues_at_wl, filter_params_for_gui(seeded),
                                             wl_arr, nH_arr, nL_arr, nSub_arr, T_nom, full_dyn_grid,
                                             compute_layer_profile=False, n_layers_matrix_precomp=matrix)
        return [(np.asarray(lv["rmse_all"], dtype=np.float64),
                 np.any(np.asarray(lv["thicknesses_all"], dtype=np.float64) > CRASH_SENTINEL_MIN, axis=1))
                for lv in res["results_per_noise"]]

    return evaluate
