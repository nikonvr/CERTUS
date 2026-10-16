"""Replay prefix winner and three fixed comparators on predeclared fresh and reused seeds."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
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
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    arguments = ["--worktree", str(args.worktree.resolve()), "--plans", str(args.plans.resolve()),
                 "--protocol", str(args.protocol.resolve()), "--reference-state", str(args.reference_state.resolve()),
                 "--output", str(args.output.resolve())]
    script = root / "scratch/rate_fixed_replay_confirmation_v5.py"
    sequence = ("control", "holdout_1212", "holdout_1313", "holdout_1414", "holdout_202", "holdout_303", "holdout_404", "holdout_505", "holdout_606", "holdout_707", "holdout_808", "holdout_909", "holdout_1010", "holdout_1111")
    if args.plan:
        print(json.dumps({"wait_for": str(args.trial_output), "sequence": sequence, "arguments": arguments}))
        return 0
    helper = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))
    resources = helper["limit_resources"](16)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    state_file = output / "etat.json"
    if state_file.exists():
        raise RuntimeError("Inspect the existing validation checkpoint before any restart")
    state = {"status": "waiting_for_trials", "pid": os.getpid(), "resources": resources, "runs": [],
             "replay_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
             "plans_sha256": hashlib.sha256(args.plans.read_bytes()).hexdigest(),
             "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
             "sequence": sequence, "current": None, "current_pid": None}

    def save() -> None:
        state["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
        helper["save"](state_file, state)

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
                if len(trial["runs"]) != trial["n_stages"]:
                    raise RuntimeError("Incomplete prefix trial checkpoint")
                break
            if trial["status"] == "failed":
                raise RuntimeError("The initial trials failed; do not start a replay")
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return 0
            time.sleep(15)
        for key in sequence:
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return 0
            if (hashlib.sha256(script.read_bytes()).hexdigest() != state["replay_sha256"]
                    or hashlib.sha256(args.plans.read_bytes()).hexdigest() != state["plans_sha256"]
                    or hashlib.sha256(args.protocol.read_bytes()).hexdigest() != state["protocol_sha256"]):
                raise RuntimeError("The prepared replay changed while waiting")
            print(f"START {key}", flush=True)
            started = time.monotonic()
            with (output / (key + ".log")).open("xb") as log:
                process = subprocess.Popen([sys.executable, str(script), *arguments, "--run", key], cwd=root, env=env,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
                state.update(status="running", current=key, current_pid=process.pid,
                             current_started=datetime.now(UTC).isoformat(timespec="seconds"))
                save()
                code = process.wait()
            if code:
                raise RuntimeError(f"Replay {key} exited {code}; its log and request are preserved")
            artifact = json.loads((output / (key + ".json")).read_text(encoding="utf-8"))
            if artifact["verdict"] != "OK" or artifact["plans_sha256"] != state["plans_sha256"] or artifact["protocol_sha256"] != state["protocol_sha256"]:
                raise RuntimeError("The replay did not validate the fixed plans and protocol")
            if artifact["script_sha256"] != state["replay_sha256"] or any(s.get("error") or s["num_runs"] != 300 for s in artifact["simulations"]):
                raise RuntimeError("Replay provenance or full-depth physical calls failed")
            rows = artifact["final_results"]["all_strategies_results"]
            state["runs"].append({"key": key, "seconds": time.monotonic() - started, "artifact": key + ".json",
                                  "plans": [{"name": row["strategy"]["nom"], "id": row["strategy"]["strategy_id"],
                                             "score": row["robustness_score"], "crash_rate": row["crash_rate"],
                                             "consensus": row["robustness_consensus_meta"]} for row in rows]})
            state.update(current=None, current_pid=None)
            save()
            print(f"DONE {key}", flush=True)
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
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    raise SystemExit(main())
