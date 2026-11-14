"""Local-search lab: in STRAT's own production context, try three ways of pushing the final local search further.

It runs the bench's `run_strat()` and listens on `joint_local_search` as the worker calls it, so every variant gets
the production evaluators, configuration and seeds, with nothing rebuilt by hand. The production call goes first and
its result is returned untouched: the run's own outcome must come out as without the lab (RESULT and the ranking are
the replay check against capture.out).

Variants, each one `joint_local_search` call with the production evaluators and seeds:
  A_round2     restart from the plan production accepted: has the search converged after its two passes?
  D_level_max  the search judges at the highest noise level, the one that decides the score, instead of the nominal one
  B_other      another start: the best crash-free plan whose head wavelength is at least 20 nm away
  A2_round3    a third round, from A's plan when A was accepted
Every plan is then judged on HOLDOUT seeds that no search, check or confirmation ever saw, under the configured index
corridor (the guard's evaluator) and under the search corridor. The per-draw RMSE and stops are saved for a paired
analysis.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/ls_lab.py

Writes ls_lab_draws.npz and ls_lab_meta.json next to this file. Changes no behaviour of CERTUS.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

#: The search uses base + 7_000_003, the check 7_100_003/011, the confirmation 7_200_003/011.
HOLDOUT_OFFSETS = (7_300_003, 7_300_011, 7_300_019, 7_300_027)
HOLDOUT_RUNS = 1000
BUDGET_S = float(os.environ.get("LS_LAB_BUDGET_S", "3300"))  # no new variant starts past this
HEAD_GAP_NM = 20.0
LAB: dict = {"done": False, "rows": None}


def jsonable(x, depth: int = 0):
    """`x` as JSON-ready data; large arrays and unknown objects become a short description."""
    import numpy as np

    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, np.generic):
        return x.item()
    if depth > 8:
        return "<deep>"
    if isinstance(x, np.ndarray):
        return x.tolist() if x.size <= 5000 else f"<array {x.shape}>"
    if isinstance(x, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in x.items()}
    if isinstance(x, (set, frozenset)):
        try:
            x = sorted(x)
        except TypeError:
            x = list(x)
    if isinstance(x, (list, tuple)):
        return [jsonable(v, depth + 1) for v in x]
    return repr(x)[:120]


def other_start(rows, start: dict):
    """The best crash-free ranked plan whose head wavelength is at least HEAD_GAP_NM from the start's: (score, plan) or None."""
    head = float((start.get("blocks") or [{}])[0].get("wavelength", 0.0))
    best = None
    for r in rows or []:
        st = r.get("strategy") if isinstance(r, dict) else None
        if not isinstance(st, dict) or not st.get("blocks"):
            continue
        try:
            score, crash = float(r.get("robustness_score", math.inf)), float(r.get("crash_rate", 1.0))
            gap = abs(float(st["blocks"][0].get("wavelength", 0.0)) - head)
        except TypeError, ValueError:
            continue
        if math.isfinite(score) and crash == 0.0 and gap >= HEAD_GAP_NM and (best is None or score < best[0]):
            best = (score, st)
    return best


def pooled_seel(rmse) -> float:
    """SEEL of (seeds, levels, draws): the draws of the seeds pooled, then 2*sqrt(max over levels of the P95)."""
    import numpy as np

    pooled = rmse.transpose(1, 0, 2).reshape(rmse.shape[1], -1)
    return 2.0 * float(np.sqrt(np.percentile(pooled, 95, axis=1).max()))


def run_lab(
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
        B.emit(f"[LAB] {msg}")

    say(f"cfg={cfg}")
    say(
        f"guard={'yes' if guard is not None else 'NO'} convert={list(convert)} search_seed={search_seed} "
        f"check={list(check_seeds)} confirm={list(confirm_seeds)} n_layers={n_layers}"
    )
    plans = {"start": copy.deepcopy(start), "prod": copy.deepcopy(prod_plan)}
    reports = {"prod": prod_report}
    accepted = {"start": None, "prod": bool(prod_report.get("accepted"))}
    timings: dict[str, float] = {}

    def variant(name: str, start_plan: dict, cfg_v, convert_v=()) -> dict | None:
        if time.perf_counter() - t0 > BUDGET_S:
            say(f"{name}: not started, budget of {BUDGET_S:.0f} s spent")
            return None
        t = time.perf_counter()
        plan, rep = jls(
            copy.deepcopy(start_plan),
            evaluate,
            n_layers,
            cfg_v,
            search_seed,
            check_seeds,
            lambda m: B.emit(f"[LAB {name}] {m}"),
            confirm_seeds,
            guard,
            sensitivity,
            convert=convert_v,
        )
        timings[name] = time.perf_counter() - t
        plans[name], reports[name], accepted[name] = copy.deepcopy(plan), rep, bool(rep.get("accepted"))
        say(
            f"{name}: accepted={accepted[name]} changes={len(rep.get('changes', []))} "
            f"evaluations={rep.get('evaluations')} in {timings[name]:.0f} s"
        )
        return plan if accepted[name] else None

    n_levels = len(evaluate(start, search_seed, 8))
    top_level = n_levels - 1
    a_plan = variant("A_round2", prod_plan, cfg) if accepted["prod"] else None
    if top_level != cfg.nominal_level:
        variant("D_level_max", start, dataclasses.replace(cfg, nominal_level=top_level), convert)
    other = None if convert else other_start(LAB["rows"], start)
    if other is not None:
        say(
            f"B_other starts from id={other[1].get('strategy_id')} origin={other[1].get('origin')} score={other[0]:.6f} "
            f"blocks={len(other[1]['blocks'])} head={other[1]['blocks'][0].get('wavelength')}"
        )
        plans["B_start"], accepted["B_start"] = copy.deepcopy(other[1]), None
        variant("B_other", other[1], cfg)
    else:
        say("B_other: no other start found (or the operator's Rate rules are converting)")
    if a_plan is not None:
        variant("A2_round3", a_plan, cfg)

    base_seed = search_seed - SEARCH_SEED_OFFSET
    seeds = [base_seed + o for o in HOLDOUT_OFFSETS]
    evaluators = {"search": evaluate} | ({"configured": guard} if guard is not None else {})
    draws: dict = {}
    for name, plan in plans.items():
        for corr, fn in evaluators.items():
            evs = [fn(plan, s, HOLDOUT_RUNS) for s in seeds]
            draws[f"{name}__{corr}__rmse"] = np.array(
                [[np.asarray(lv[0], dtype=np.float64) for lv in ev] for ev in evs]
            )
            draws[f"{name}__{corr}__stopped"] = np.array([[np.asarray(lv[1], dtype=bool) for lv in ev] for ev in evs])
    summary: dict = {}
    lvl = cfg.nominal_level
    for corr in evaluators:
        ref, ref_st = draws[f"prod__{corr}__rmse"], draws[f"prod__{corr}__stopped"]
        for name in plans:
            rm, st = draws[f"{name}__{corr}__rmse"], draws[f"{name}__{corr}__stopped"]
            both = ~st[:, lvl, :] & ~ref_st[:, lvl, :]
            d = rm[:, lvl, :][both] ** 2 - ref[:, lvl, :][both] ** 2
            scale = float(np.mean(ref[:, lvl, :][both] ** 2))
            rel, se = float(d.mean()) / scale, float(d.std(ddof=1) / np.sqrt(d.size)) / scale
            p95 = np.percentile(rm.transpose(1, 0, 2).reshape(rm.shape[1], -1), 95, axis=1)
            summary[f"{name}__{corr}"] = {
                "seel_nm": pooled_seel(rm),
                "stops": int(st.sum()),
                "draws": int(st.size),
                "p95_by_level": p95.tolist(),
                "d_rmse2_vs_prod": rel,
                "d_rmse2_se": se,
            }
            say(
                f"holdout {corr:10s} {name:12s} accepted={accepted.get(name)!s:5s} SEEL {pooled_seel(rm):.4f} nm | "
                f"stops {int(st.sum())}/{st.size} | P95/level {np.round(p95, 5).tolist()} | "
                f"dRMSE2 vs prod at level {lvl}: {rel:+.1%} (SE {se:.1%})"
            )
    np.savez_compressed(HERE / "ls_lab_draws.npz", **draws)
    meta = {
        "holdout": {"seeds": seeds, "runs": HOLDOUT_RUNS, "base_seed": base_seed},
        "search_seed": search_seed,
        "check_seeds": list(check_seeds),
        "confirm_seeds": list(confirm_seeds),
        "cfg": jsonable(dataclasses.asdict(cfg)),
        "top_level": top_level,
        "n_levels": n_levels,
        "guard": guard is not None,
        "convert": list(convert),
        "accepted": accepted,
        "timings_s": timings,
        "summary": summary,
        "plans": jsonable(plans),
        "reports": jsonable(reports),
    }
    (HERE / "ls_lab_meta.json").write_text(json.dumps(avec_provenance(meta), indent=1), encoding="utf-8")
    say(f"written ls_lab_draws.npz ls_lab_meta.json in {time.perf_counter() - t0:.0f} s")


def install(B) -> None:
    import certus.workers.certus_strat_workers_local_search as LSW

    original_run, original_jls = LSW.run_local_search, LSW.joint_local_search

    def listening_run(rows, pre_calc_data, params, shared_clues_info, ranker):
        LAB["rows"] = rows  # read only, for the other start
        return original_run(rows, pre_calc_data, params, shared_clues_info, ranker)

    def listening_jls(
        start,
        evaluate,
        n_layers,
        cfg,
        search_seed,
        check_seeds,
        log=lambda _m: None,
        confirm_seeds=(),
        evaluate_guard=None,
        layer_sensitivity=None,
        convert=(),
    ):
        plan, report = original_jls(
            start,
            evaluate,
            n_layers,
            cfg,
            search_seed,
            check_seeds,
            log,
            confirm_seeds,
            evaluate_guard,
            layer_sensitivity,
            convert=convert,
        )
        if not LAB["done"]:
            LAB["done"] = True
            try:  # the lab never changes what production returns
                run_lab(
                    B,
                    original_jls,
                    start,
                    evaluate,
                    n_layers,
                    cfg,
                    search_seed,
                    check_seeds,
                    confirm_seeds,
                    evaluate_guard,
                    layer_sensitivity,
                    convert,
                    plan,
                    report,
                )
            except Exception:
                B.emit("LAB_FAILED\n" + traceback.format_exc())
        return plan, report

    LSW.run_local_search, LSW.joint_local_search = listening_run, listening_jls


def main() -> None:
    import bench_examples as B

    B.qapp()
    B.autoanswer_dialogs(True)
    install(B)
    B.emit("local-search lab installed")
    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")
    if not LAB["done"]:
        B.emit("LAB_NEVER_CALLED")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
