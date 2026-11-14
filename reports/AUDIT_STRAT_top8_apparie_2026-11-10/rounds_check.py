"""Does `strat_local_search_rounds` reach the computation, and does the pipeline then give the plan the lab found?

A full `run_strat()` with the setting posed where scripts/probe_blocs_vs_plantage.py poses its overrides: on what
`collect_params` returns. Nothing else is touched. The run listens on what `run_local_search` returns and compares the
refined plan with the plan `F3` of rounds_lab.py (same base seed, same seed step): they must be the same plan.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/rounds_check.py          (4 rounds allowed)
    ROUNDS_CHECK=1 python reports/AUDIT_STRAT_top8_apparie_2026-11-10/rounds_check.py   (the default, for the replay)

Writes rounds_check_meta_<rounds>.json next to this file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ls_lab  # noqa: E402  (sets the console encoding and the scripts path)

ROUNDS = int(os.environ.get("ROUNDS_CHECK", "4"))
SEEN: dict = {}


def shape(plan: dict) -> tuple:
    """What makes two plans the same deposition: the blocks and the Rate layers."""
    blocks = [(int(b["start"]), int(b["end"]), float(b["wavelength"])) for b in plan.get("blocks") or []]
    return blocks, sorted(int(k) for k in plan.get("rate_layers") or [])


def main() -> None:
    import bench_examples as B
    from _artefact import avec_provenance

    B.qapp()
    B.autoanswer_dialogs(True)
    import certus.workers.certus_strat_workers_local_search as LSW
    from CERTUS_STRAT import CertusStratApp

    collect = CertusStratApp.collect_params

    def collect_with_rounds(self, *a, **kw):
        params = collect(self, *a, **kw)
        if ROUNDS != 1:  # 1 is the default: nothing is posed, the configuration is the example's
            params["strat_local_search_rounds"] = ROUNDS
        return params

    CertusStratApp.collect_params = collect_with_rounds
    original = LSW.run_local_search

    def listening(rows, pre_calc_data, params, shared_clues_info, ranker):
        SEEN["setting_received"] = params.get("strat_local_search_rounds", "absent")
        out = original(rows, pre_calc_data, params, shared_clues_info, ranker)
        try:
            new_rows, report, _ranker = out
            SEEN["report"] = ls_lab.jsonable(report)
            last = new_rows[-1].get("strategy") if new_rows and isinstance(new_rows[-1], dict) else None
            if isinstance(last, dict) and last.get("origin") == "LOCAL_SEARCH":
                SEEN["plan"] = ls_lab.jsonable(last)
        except Exception as exc:  # a probe never kills the run
            B.emit(f"ROUNDS_CHECK_FAILED={exc!r}")
        return out

    LSW.run_local_search = listening
    B.emit(f"rounds check installed: strat_local_search_rounds={ROUNDS}")
    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")

    report, plan = SEEN.get("report") or {}, SEEN.get("plan")
    further = [bool(r.get("accepted")) for r in report.get("rounds") or []]
    B.emit(
        f"ROUNDS_CHECK setting_received={SEEN.get('setting_received')} first_round_accepted={report.get('accepted')} "
        f"further_rounds_accepted={further}"
    )
    lab = HERE / "rounds_lab_meta.json"
    if plan is not None and lab.is_file():
        plans = json.loads(lab.read_text(encoding="utf-8"))["plans"]
        same = {name: shape(plan) == shape(other) for name, other in plans.items()}
        B.emit(
            f"ROUNDS_CHECK refined plan: {len(plan['blocks'])} blocks, {len(plan.get('rate_layers') or [])} Rate layers; "
            f"same plan as the lab's: {[name for name, ok in same.items() if ok] or 'none'}"
        )
    meta = {
        "rounds_asked": ROUNDS,
        "setting_received": SEEN.get("setting_received"),
        "result": val,
        "run_s": run,
        "further_rounds_accepted": further,
        "report": report,
        "plan": plan,
    }
    (HERE / f"rounds_check_meta_{ROUNDS}.json").write_text(
        json.dumps(avec_provenance(meta), indent=1), encoding="utf-8"
    )
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
