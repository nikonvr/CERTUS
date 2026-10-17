"""Wait for the local refinement, verify the adapter, then run one native scientific search."""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wait-output", type=Path, required=True)
    parser.add_argument("--wait-state", type=Path)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--joint-budget", type=int, default=480)
    parser.add_argument("--prefix-budget", type=int, default=0)
    parser.add_argument("--rate-budget", type=int, default=120)
    parser.add_argument("--elite-rounds", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    helper = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))
    resources = helper["limit_resources"](16)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    state_file = output / "controller.json"
    if state_file.exists():
        raise RuntimeError("Inspect the existing native controller before any restart")
    inputs = [root / "scratch" / name for name in ("rate_native_prefix_probe.py", "rate_joint_native_candidates.py",
              "verify_rate_native_prefix_adapter.py", "rate_prefix_native_candidates.py", "campagne_a2_runner.py")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    state = {"status": "waiting_for_refinement", "pid": os.getpid(), "resources": resources,
             "script_sha256": hashes, "current_pid": None, "joint_budget": args.joint_budget, "prefix_budget": args.prefix_budget, "seed": 101,
             "rate_budget": args.rate_budget, "elite_rounds": args.elite_rounds}
    env = os.environ.copy()
    env.update(PYTHON_CPU_COUNT="16", PYTHONUTF8="1", PYTHONUNBUFFERED="1", QT_QPA_PLATFORM="offscreen")
    for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "15"

    def save():
        state["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
        helper["save"](state_file, state)

    def run(label, arguments):
        with (output / (label + ".log")).open("xb") as stream:
            process = subprocess.Popen([sys.executable, *arguments], cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
            state.update(status=label, current_pid=process.pid, current_started=datetime.now(UTC).isoformat(timespec="seconds"))
            save()
            code = process.wait()
        state["current_pid"] = None
        save()
        if code:
            raise RuntimeError(f"{label} exited {code}; log and artifacts preserved")

    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        save()
        while True:
            previous = json.loads((args.wait_state or args.wait_output / "etat.json").read_text())
            if previous["status"] == "complete" and not previous.get("current_pid") and not (args.wait_output / ".running").exists():
                if "n_stages" in previous and len(previous["runs"]) != previous["n_stages"]:
                    raise RuntimeError("Incomplete refinement marked as complete")
                state["previous_best"] = previous.get("best")
                break
            if previous["status"] == "failed":
                raise RuntimeError("The refinement controller failed; native measurement not started")
            if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
                state["status"] = "deadline_reached"
                return
            time.sleep(15)
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != hashes[str(p)] for p in inputs):
            raise RuntimeError("Prepared native sources changed while waiting")
        run("verification", [str(root / "scratch/verify_rate_native_prefix_adapter.py"), "--worktree", str(args.worktree.resolve()),
                             "--output", str(output / "adapter_verification.json")])
        if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
            state["status"] = "deadline_reached"
            return
        key = f"prefix_{args.prefix_budget}_joint_{args.joint_budget}_rate{args.rate_budget}_rounds{args.elite_rounds or 'default'}_s101"
        state["measurement_key"] = key
        arguments = [str(root / "scratch/rate_native_prefix_probe.py"), "--worktree", str(args.worktree.resolve()),
                     "--output", str(output / key), "--reference-state", str(args.reference_state.resolve()),
                     "--joint-budget", str(args.joint_budget), "--prefix-budget", str(args.prefix_budget), "--rate-budget", str(args.rate_budget), "--seed", "101"]
        if args.elite_rounds is not None:
            arguments += ["--elite-rounds", str(args.elite_rounds)]
        run("measurement", arguments)
        state["status"] = "complete"
    except BaseException as error:
        state.update(status="failed", error=str(error))
        raise
    finally:
        save()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
