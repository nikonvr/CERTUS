"""Wait for the existing bounded controller, then finish the already authorized A2 cells."""

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
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-controller-pid", type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    worktree, campaign, output = args.worktree.resolve(), args.campaign.resolve(), args.output.resolve()
    if not campaign.is_relative_to(root / "reports") or not output.is_relative_to(root / "reports"):
        raise ValueError("Campaign and continuation outputs must stay within reports")
    helper_path = root / "scratch/campagne_a2_runner.py"
    helper_hash = "77e26f57341c198830e5ed8b19e072b94285eb24f5ed2cdd2e78dadf378f7e51"
    if hashlib.sha256(helper_path.read_bytes()).hexdigest() != helper_hash:
        raise RuntimeError("The original A2 helper changed; inspect before resuming")
    helper = runpy.run_path(str(helper_path))
    resources = helper["limit_resources"](16)
    expected = {f"{name}_{mode}_s{seed:03d}_{variant}" for name, mode, _slit, seed in helper["CELLS"] for variant in ("avec", "sans")}
    output.mkdir(parents=True, exist_ok=True)
    state_file, lock = output / "etat.json", output / ".running"
    if state_file.exists():
        raise RuntimeError("Inspect the existing continuation state before restarting")
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    state = {"status": "waiting_for_previous", "pid": os.getpid(), "previous_controller_pid": args.previous_controller_pid,
             "resources": resources, "helper_sha256": helper_hash, "expected_runs": len(expected), "current_pid": None,
             "authorization": "User explicitly requested finishing the remaining batches on 2026-10-14; A2 continues beyond the old09h boundary"}

    def save():
        state["updated_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
        helper["save"](state_file, state)

    process = None
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        save()
        # The Windows handle identifies this exact process even if its PID is later reused.
        try:
            previous_code = helper["wait_for_existing_process"](args.previous_controller_pid)
        except OSError as error:
            if getattr(error, "winerror", None) not in (87, 1168):
                raise
            previous_code = None
        previous = json.loads((campaign / "etat.json").read_text(encoding="utf-8"))
        keys = [r["key"] for r in previous["runs"]]
        if len(keys) != len(set(keys)) or not set(keys).issubset(expected):
            raise RuntimeError("Invalid or duplicated A2 checkpoint identities")
        if previous_code not in (None, 0) or previous["status"] not in ("deadline_reached", "paused", "complete") or previous.get("current_pid"):
            raise RuntimeError("Previous A2 controller did not release a successful idle checkpoint")
        helper["save"](output / "checkpoint_before_resume.json", previous)
        campaign_lock = campaign / ".running"
        for _ in range(20):
            if not campaign_lock.exists():
                break
            time.sleep(0.25)
        if len(keys) == len(expected):
            state.update(status="complete", completed=len(keys))
            return 0
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, encoding="utf-8").strip()
        if commit != previous["commit"]:
            raise RuntimeError("A2 worktree commit changed")
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=worktree, check=True)
        if hashlib.sha256(helper_path.read_bytes()).hexdigest() != helper_hash:
            raise RuntimeError("The original A2 helper changed while waiting")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        inventory_command = (
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and "
            "$_.CommandLine -match 'probe_blocs|rate_fixed_replay|rate_native_.*probe|campagne_a2' } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        inventory_text = subprocess.check_output([str(powershell), "-NoProfile", "-Command", inventory_command],
                                                encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW).strip()
        inventory = json.loads(inventory_text) if inventory_text else []
        if isinstance(inventory, dict):
            inventory = [inventory]
        active = [p for p in inventory if p["ProcessId"] != os.getpid()]
        if active:
            state["other_active_processes"] = active
            raise RuntimeError("Another scientific process or A2 controller is active; continuation not started")
        if campaign_lock.exists():
            if campaign_lock.read_text(encoding="utf-8").strip() != str(args.previous_controller_pid):
                raise RuntimeError("Another controller owns the campaign lock")
            archived_lock = output / "stale_previous_lock.txt"
            if archived_lock.exists():
                raise FileExistsError(archived_lock)
            campaign_lock.rename(archived_lock)
            state["reconciled_previous_lock"] = str(archived_lock)
        env = os.environ.copy()
        env.update(PYTHON_CPU_COUNT="16", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        arguments = ["--worktree", str(worktree), "--output", str(campaign), "--logical-cpus", "16"]
        with (output / "campaign.log").open("xb") as stream:
            process = subprocess.Popen([sys.executable, str(helper_path), *arguments], cwd=root, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
            state.update(status="running_campaign", current_pid=process.pid, completed_before_resume=len(keys),
                         arguments=arguments, commit=commit)
            save()
            code = process.wait()
        state["current_pid"] = None
        final = json.loads((campaign / "etat.json").read_text(encoding="utf-8"))
        final_keys = [r["key"] for r in final["runs"]]
        if code or final["status"] != "complete" or len(final_keys) != len(expected) or set(final_keys) != expected or final.get("current_pid"):
            raise RuntimeError("A2 has not completed all24 expected cells; checkpoint and logs preserved")
        state.update(status="complete", completed=len(final_keys), checkpoint=str(campaign / "etat.json"))
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
