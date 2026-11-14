"""Rounds lab: how far does restarting the local search from its own accepted plan go, and with which seeds?

ls_lab.py measured that a second and a third round still improve the plan on holdout seeds. Here two chains start
from the plan production accepted, one round at a time, each round one `joint_local_search` call with the production
evaluators:
  S<r>  same seeds every round: the production search, check and confirmation seeds (S2 and S3 replay ls_lab's
        A_round2 and A2_round3)
  F<r>  fresh seeds every round: the three kinds of seeds shifted by SEED_STEP * (r - 1)
A chain stops at the first round the check refuses or that keeps no change. Every accepted plan is judged on the same
holdout seeds as ls_lab.py, under the configured index corridor and under the search corridor.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/rounds_lab.py

Writes rounds_lab_draws.npz and rounds_lab_meta.json next to this file. Changes no behaviour of CERTUS.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ls_lab  # noqa: E402  (sets the console encoding and the scripts path)

MAX_ROUND = int(os.environ.get("ROUNDS_LAB_MAX_ROUND", "7"))
BUDGET_S = float(os.environ.get("ROUNDS_LAB_BUDGET_S", "4200"))  # no new round starts past this
SEED_STEP = 16  # the check seeds of production are 8 apart; holdout offsets start 100 000 further


def run_rounds(
    B,
    jls,
    start,
    evaluate,
    n_layers,
    cfg,
    search_seed,
    check_seeds,
    confirm_seeds,
    guard,
    sensitivity,
    convert,
    prod_plan,
    prod_report,
) -> None:
    import numpy as np
    from _artefact import avec_provenance

    from certus.core.certus_strat_local_search import SEARCH_SEED_OFFSET

    t0 = time.perf_counter()

    def say(msg: str) -> None:
        B.emit(f"[ROUNDS] {msg}")

    say(
        f"guard={'yes' if guard is not None else 'NO'} convert={list(convert)} search_seed={search_seed} "
        f"check={list(check_seeds)} confirm={list(confirm_seeds)} passes={cfg.passes} max_round={MAX_ROUND}"
    )
    plans = {"start": copy.deepcopy(start), "prod": copy.deepcopy(prod_plan)}
    reports = {"prod": prod_report}
    timings: dict[str, float] = {}
    seeds_used: dict[str, dict] = {}
    chains = {"S": copy.deepcopy(prod_plan), "F": copy.deepcopy(prod_plan)} if prod_report.get("accepted") else {}
    stopped_at: dict[str, str] = {}
    for round_no in range(2, MAX_ROUND + 1):
        for chain in ("S", "F"):
            if chain not in chains:
                continue
            if time.perf_counter() - t0 > BUDGET_S:
                stopped_at.setdefault(chain, f"budget before round {round_no}")
                continue
            shift = SEED_STEP * (round_no - 1) if chain == "F" else 0
            name = f"{chain}{round_no}"
            used = {
                "search": search_seed + shift,
                "check": [s + shift for s in check_seeds],
                "confirm": [s + shift for s in confirm_seeds],
            }
            t = time.perf_counter()
            plan, rep = jls(
                copy.deepcopy(chains[chain]),
                evaluate,
                n_layers,
                cfg,
                used["search"],
                tuple(used["check"]),
                lambda m, name=name: B.emit(f"[ROUNDS {name}] {m}"),
                tuple(used["confirm"]),
                guard,
                sensitivity,
            )
            timings[name], reports[name], seeds_used[name] = time.perf_counter() - t, rep, used
            say(
                f"{name}: accepted={bool(rep.get('accepted'))} changes={len(rep.get('changes', []))} "
                f"kept={rep.get('fallback_changes', len(rep.get('changes', [])) if rep.get('accepted') else 0)} "
                f"in {timings[name]:.0f} s"
            )
            if rep.get("accepted"):
                chains[chain] = plans[name] = copy.deepcopy(plan)
            else:
                stopped_at[chain] = f"round {round_no} refused or without change"
                del chains[chain]
    say(f"chains stopped: {stopped_at or 'at the last round allowed'}")

    base_seed = search_seed - SEARCH_SEED_OFFSET
    seeds = [base_seed + o for o in ls_lab.HOLDOUT_OFFSETS]
    evaluators = {"search": evaluate} | ({"configured": guard} if guard is not None else {})
    draws: dict = {}
    for name, plan in plans.items():
        for corr, fn in evaluators.items():
            evs = [fn(plan, s, ls_lab.HOLDOUT_RUNS) for s in seeds]
            draws[f"{name}__{corr}__rmse"] = np.array(
                [[np.asarray(lv[0], dtype=np.float64) for lv in ev] for ev in evs]
            )
            draws[f"{name}__{corr}__stopped"] = np.array([[np.asarray(lv[1], dtype=bool) for lv in ev] for ev in evs])
    summary: dict = {}
    for corr in evaluators:
        for name, plan in plans.items():
            rm, st = draws[f"{name}__{corr}__rmse"], draws[f"{name}__{corr}__stopped"]
            p95 = np.percentile(rm.transpose(1, 0, 2).reshape(rm.shape[1], -1), 95, axis=1)
            summary[f"{name}__{corr}"] = {
                "seel_nm": ls_lab.pooled_seel(rm),
                "stops": int(st.sum()),
                "draws": int(st.size),
                "p95_by_level": p95.tolist(),
                "blocks": len(plan.get("blocks") or []),
                "rate_layers": len(plan.get("rate_layers") or []),
            }
            say(
                f"holdout {corr:10s} {name:6s} SEEL {ls_lab.pooled_seel(rm):.4f} nm | stops {int(st.sum())}/{st.size} | "
                f"P95/level {np.round(p95, 5).tolist()} | blocks {len(plan.get('blocks') or [])} | "
                f"Rate layers {len(plan.get('rate_layers') or [])}"
            )
    np.savez_compressed(HERE / "rounds_lab_draws.npz", **draws)
    meta = {
        "holdout": {"seeds": seeds, "runs": ls_lab.HOLDOUT_RUNS, "base_seed": base_seed},
        "seed_step": SEED_STEP,
        "seeds_used": seeds_used,
        "stopped_at": stopped_at,
        "max_round": MAX_ROUND,
        "cfg": ls_lab.jsonable(dataclasses.asdict(cfg)),
        "guard": guard is not None,
        "timings_s": timings,
        "summary": summary,
        "plans": ls_lab.jsonable(plans),
        "reports": ls_lab.jsonable(reports),
    }
    (HERE / "rounds_lab_meta.json").write_text(json.dumps(avec_provenance(meta), indent=1), encoding="utf-8")
    say(f"written rounds_lab_draws.npz rounds_lab_meta.json in {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    ls_lab.run_lab = run_rounds  # ls_lab.install() looks the lab up at call time
    ls_lab.main()
