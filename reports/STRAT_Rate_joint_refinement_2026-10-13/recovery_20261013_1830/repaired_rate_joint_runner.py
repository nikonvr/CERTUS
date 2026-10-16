"""Measure deterministic mixed-plan neighbors sequentially, retaining anchors, rejects and checkpoints."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import runpy
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    stages = [{"key": "anchor_control", "mode": "control", "plans": proposals["anchors"]}]
    stages.extend({"key": f"batch_{start//10+1:03d}", "mode": "search",
                   "plans": proposals["anchors"] + proposals["proposals"][start:start+10]}
                  for start in range(0, len(proposals["proposals"]), 10))
    if args.plan:
        print(json.dumps({"stages": len(stages), "proposals": proposals["n_proposals"], "families": proposals["families"],
                          "batch_limit": 10, "anchors_per_batch": len(proposals["anchors"]),
                          "search_seed": proposals["search_seed"], "consensus_seeds": proposals["consensus_seeds"]}))
        return 0
    helper = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))
    resources = helper["limit_resources"](16)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    replay = root / "scratch/rate_fixed_replay.py"
    hashes = {"replay": hashlib.sha256(replay.read_bytes()).hexdigest(),
              "proposals": hashlib.sha256(args.proposals.read_bytes()).hexdigest(),
              "protocol": hashlib.sha256(args.protocol.read_bytes()).hexdigest()}
    state_path = output / "etat.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"runs": [], "hashes": hashes}
    if state["hashes"] != hashes or state.get("current_pid"):
        raise RuntimeError("Changed inputs or unreconciled process; inspect the checkpoint before resuming")
    incumbent = proposals["anchors"][1]
    state.setdefault("best", {"id": incumbent["source_strategy_id"], "name": incumbent["nom"], "move": {"kind": "incumbent"},
                              "eligible": True, "score": incumbent["expected_score_fixed_point"], "crash_rate": 0.0,
                              "artifact": incumbent["source_artifact"]})
    completed = {run["key"]: run for run in state["runs"]}
    state.update(status="waiting_for_budget360", pid=os.getpid(), resources=resources, current=None, current_pid=None,
                 n_proposals=proposals["n_proposals"], n_stages=len(stages))
    state.pop("error", None)
    lock = output / ".running"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    report_path = output.parent / (output.name + ".md")

    def save() -> None:
        state["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
        helper["save"](state_path, state)
        scored = sum(len(run.get("results", [])) for run in state["runs"])
        baseline = next(plan["expected_score_fixed_point"] for plan in proposals["anchors"] if plan["nom"] == "reference_rate_s101")
        lines = ["# Rate : voisinage conjoint fenêtre/λ (2026-10-13)", "",
                 f"État : `{state['status']}` ; {len(state['runs'])}/{len(stages)} étapes sauvegardées ; {scored}/{proposals['n_proposals']} propositions notées.",
                 "Graine de recherche 101, consensus 41/42/43 ; 300 tirages complets et 300 par graine de consensus.",
                 "16 processeurs logiques, affinité 0xffff, priorité normale, 15 threads de bibliothèque ; une mesure à la fois.",
                 "Deux ancres reproduites dans chaque groupe ; consensus incomplets exclus, rejets conservés.", ""]
        best = state.get("best")
        if best:
            lines += [f"Meilleur résultat provisoire : **{2*math.sqrt(best['score']):.6f} nm** ({100*(math.sqrt(best['score']/baseline)-1):+.2f} % contre la référence).",
                      f"Plan `{best['name']}`, mouvement `{best['move']}`, artefact `{best['artifact']}`."]
        lines += ["", "Aucun gain indépendant établi pour ce voisinage. Aucun défaut scientifique modifié, aucun commit.",
                  "Les durées incluent le démarrage et le cache ; elles ne prouvent pas une accélération de code."]
        if state.get("error"):
            lines += ["", f"Échec conservé : `{state['error']}`."]
        helper["save_text"](report_path, "\n".join(lines) + "\n")

    env = os.environ.copy()
    env.update(PYTHON_CPU_COUNT="16", PYTHONUTF8="1", PYTHONUNBUFFERED="1", QT_QPA_PLATFORM="offscreen")
    for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "15"
    process = None
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        save()
        while True:
            trial = json.loads((args.trial_output / "etat.json").read_text(encoding="utf-8"))
            if trial["status"] == "complete" and not trial.get("current_pid") and not (args.trial_output / ".running").exists():
                if "budget_360" not in {run["key"] for run in trial["runs"]}:
                    raise RuntimeError("Budget 360 has no saved result")
                break
            if trial["status"] == "failed":
                raise RuntimeError("Budget trial failed; no joint measurement started")
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return 0
            time.sleep(15)
        for stage in stages:
            if stage["key"] in completed:
                continue
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return 0
            if (hashlib.sha256(replay.read_bytes()).hexdigest() != hashes["replay"] or
                    hashlib.sha256(args.proposals.read_bytes()).hexdigest() != hashes["proposals"] or
                    hashlib.sha256(args.protocol.read_bytes()).hexdigest() != hashes["protocol"]):
                raise RuntimeError("The frozen replay, proposals or protocol changed")
            stage_path = output / stage["key"]
            stage_path.mkdir(exist_ok=True)
            attempt = 1
            while (stage_path / f"attempt_{attempt:02d}").exists():
                attempt += 1
            attempt_path = stage_path / f"attempt_{attempt:02d}"
            attempt_path.mkdir()
            plans_file = attempt_path / "plans.json"
            plans_file.write_text(json.dumps({"plans": stage["plans"]}, ensure_ascii=False, indent=2), encoding="utf-8")
            arguments = ["--worktree", str(args.worktree.resolve()), "--plans", str(plans_file),
                         "--protocol", str(args.protocol.resolve()), "--reference-state", str(args.reference_state.resolve()),
                         "--output", str(attempt_path), "--run", stage["mode"]]
            if stage["mode"] == "search":
                arguments += ["--validated-control", completed["anchor_control"]["artifact"]]
            print(f"START {stage['key']} attempt {attempt}", flush=True)
            started = time.monotonic()
            with (attempt_path / "measurement.log").open("xb") as stream:
                process = subprocess.Popen([sys.executable, str(replay), *arguments], cwd=root, env=env,
                                           stdout=stream, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
                state.update(status="running", current=stage["key"], current_pid=process.pid,
                             current_attempt=str(attempt_path), current_started=datetime.now(UTC).isoformat(timespec="seconds"))
                save()
                code = process.wait()
            if code:
                raise RuntimeError(f"{stage['key']} exited {code}; attempt {attempt} is preserved")
            artifact_path = attempt_path / (stage["mode"] + ".json")
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            if (artifact["verdict"] != "OK" or artifact["script_sha256"] != hashes["replay"] or artifact["protocol_sha256"] != hashes["protocol"] or
                    artifact["plans_sha256"] != hashlib.sha256(plans_file.read_bytes()).hexdigest()):
                raise RuntimeError("Invalid replay verdict, source or protocol")
            rows = {row["strategy"]["strategy_id"]: row for row in artifact["final_results"]["all_strategies_results"]}
            eligible = set(artifact.get("search_eligible_ids", []))
            results = []
            for plan in stage["plans"][len(proposals["anchors"]):]:
                sid = plan["source_strategy_id"]
                row = rows.get(sid)
                item = {"id": sid, "name": plan["nom"], "move": plan["move"], "eligible": sid in eligible,
                        "score": row.get("robustness_score") if row else None,
                        "crash_rate": row.get("crash_rate") if row else None, "artifact": str(artifact_path)}
                results.append(item)
                if item["eligible"] and (state.get("best") is None or item["score"] < state["best"]["score"]):
                    state["best"] = item
            run = {"key": stage["key"], "artifact": str(artifact_path), "attempt": attempt,
                   "seconds": time.monotonic()-started, "results": results, "rejected": artifact.get("search_rejected", [])}
            state["runs"].append(run)
            completed[stage["key"]] = run
            state.update(current=None, current_pid=None)
            save()
            print(f"DONE {stage['key']} scored={len(results)}", flush=True)
        state["status"] = "complete"
        return 0
    except BaseException as error:
        state.update(status="failed", error=str(error))
        if process is None or process.poll() is not None:
            state["current_pid"] = None
        raise
    finally:
        try:
            save()
        finally:
            lock.unlink(missing_ok=True)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    raise SystemExit(main())
