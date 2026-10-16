"""After the native search, replay its winner against fixed references on predeclared seeds."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import math
import os
import runpy
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--native-output", type=Path, required=True)
    parser.add_argument("--measurement-key", default="joint_480_s101")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    native = args.native_output.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    helper = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))
    resources = helper["limit_resources"](16)
    replay = root / "scratch/rate_fixed_replay_confirmation_v3.py"
    state_file = output / "etat.json"
    if state_file.exists():
        raise RuntimeError("Inspect the existing confirmation before any restart")
    hashes = {"replay": hashlib.sha256(replay.read_bytes()).hexdigest(),
              "protocol": hashlib.sha256(args.protocol.read_bytes()).hexdigest()}
    sequence = ("control", "holdout_202", "holdout_303", "holdout_404", "holdout_505", "holdout_606", "holdout_707", "holdout_808", "holdout_909")
    state = {"status": "waiting_for_native", "pid": os.getpid(), "resources": resources,
             "hashes": hashes, "sequence": sequence, "runs": [], "current": None, "current_pid": None}
    env = os.environ.copy()
    env.update(PYTHON_CPU_COUNT="16", PYTHONUTF8="1", PYTHONUNBUFFERED="1", QT_QPA_PLATFORM="offscreen")
    for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "15"

    def save():
        state["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
        helper["save"](state_file, state)

    process = None
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        save()
        while True:
            previous = json.loads((native / "controller.json").read_text())
            if previous["status"] == "complete" and not previous.get("current_pid"):
                break
            if previous["status"] == "failed":
                raise RuntimeError("Native controller failed; confirmation not started")
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return
            time.sleep(15)
        measurement = native / args.measurement_key
        measured = json.loads((measurement / "etat.json").read_text())
        if measured["status"] != "complete" or (measurement / ".running").exists():
            raise RuntimeError("The native scientific artifact is not complete")
        artifact_path = Path(measured["artifact"])
        artifact = json.loads(artifact_path.read_text())
        if artifact["verdict"] != "OK" or artifact["native_joint_adapter"]["script_sha256"] != measured["script_sha256"]:
            raise RuntimeError("Native adapter provenance failed")
        spec = importlib.util.spec_from_file_location("native_summary", root / "scripts/resumer_artefact_sonde.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        summary = module.resumer(artifact)
        best = summary["meilleur"]
        if best is None or not math.isfinite(best["score"]):
            raise RuntimeError("No depositable native winner")
        pair = json.loads((root / "reports/STRAT_Rate_validation_joint_2026-10-13/refinement_pair.json").read_text())
        winner = {"nom": f"native_{args.measurement_key}", "blocks": best["blocs"], "rate_layers": best.get("rate_layers") or [],
                  "monochromator_resolution_nm": best["resolution_nm"], "source_strategy_id": 9_900_000,
                  "source_original_strategy_id": best["id"], "expected_score_fixed_point": best["score"],
                  "source_artifact": str(artifact_path), "source_artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                  "replay_id_reason": "distinct replay identity; original native ID retained and fixed point checked; C2 worlds must be identity-independent"}
        plans = output / "plans.json"
        fixed = pair["plans"]
        equivalent = next((p for p in fixed if p["blocks"] == winner["blocks"] and p.get("rate_layers", []) == winner["rate_layers"]
                           and p.get("monochromator_resolution_nm") == winner["monochromator_resolution_nm"]), None)
        if equivalent is not None:
            if not math.isclose(equivalent["expected_score_fixed_point"], winner["expected_score_fixed_point"], rel_tol=1e-7, abs_tol=1e-10):
                raise RuntimeError("The native winner has the same geometry but a different fixed-point score")
            state["native_same_plan_as"] = equivalent["source_strategy_id"]
        else:
            fixed.append(winner)
        with plans.open("x", encoding="utf-8") as stream:
            json.dump({"plans": fixed}, stream, ensure_ascii=False, indent=2)
        state.update(native_summary=summary, plans_sha256=hashlib.sha256(plans.read_bytes()).hexdigest())
        for key in sequence:
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return
            if hashlib.sha256(replay.read_bytes()).hexdigest() != hashes["replay"] or hashlib.sha256(args.protocol.read_bytes()).hexdigest() != hashes["protocol"]:
                raise RuntimeError("Prepared confirmation changed while waiting")
            with (output / (key + ".log")).open("xb") as stream:
                process = subprocess.Popen([sys.executable, str(replay), "--worktree", str(args.worktree.resolve()),
                                            "--plans", str(plans), "--protocol", str(args.protocol.resolve()),
                                            "--reference-state", str(args.reference_state.resolve()), "--output", str(output), "--run", key],
                                           cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
                state.update(status="running", current=key, current_pid=process.pid)
                save()
                code = process.wait()
            state["current_pid"] = None
            if code:
                raise RuntimeError(f"Confirmation {key} exited {code}; log and result preserved")
            result_path = output / (key + ".json")
            result = json.loads(result_path.read_text())
            if result["verdict"] != "OK" or result["plans_sha256"] != state["plans_sha256"] or result["protocol_sha256"] != hashes["protocol"] or result["script_sha256"] != hashes["replay"]:
                raise RuntimeError("Confirmation artifact, plan, protocol or replay provenance failed")
            simulations = result["simulations"]
            if any(s.get("error") or s["num_runs"] != 300 for s in simulations):
                raise RuntimeError("Incomplete or failed full-depth simulation")
            rows = result["final_results"]["all_strategies_results"]
            state["runs"].append({"run": key, "artifact": str(result_path), "setting": result["setting"],
                                  "plans": [{"id": r["strategy"]["source_strategy_id"], "name": r["strategy"]["nom"],
                                             "score": r["robustness_score"], "seel": 2*math.sqrt(r["robustness_score"])} for r in rows],
                                  "max_observed_crash_rate": max(s.get("crash_rate") or 0 for s in simulations)})
            state["current"] = None
            save()
        state["status"] = "complete"
    except BaseException as error:
        state.update(status="failed", error=str(error))
        if process is None or process.poll() is not None:
            state["current_pid"] = None
        raise
    finally:
        save()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
