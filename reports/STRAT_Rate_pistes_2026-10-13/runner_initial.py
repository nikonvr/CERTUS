"""Run explicit Rate experiments sequentially after A2 saves its current measurement."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DEADLINE = datetime(2026, 10, 14, 7, tzinfo=UTC)
SOURCE_FILES = ("certus/core/certus_strat_consensus.py", "certus/core/certus_strat_robustness_rate.py")
ARGUMENTS = ["r75x0.5", "deep", "0", "0", "2", "0", "101", "0"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plan-file", required=True, type=Path)
    parser.add_argument("--a2-output", required=True, type=Path)
    parser.add_argument("--reference-output", required=True, type=Path)
    parser.add_argument("--wait-a2", action="store_true")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan_file.read_text(encoding="utf-8"))
    keys = [run["key"] for run in plan]
    if len(keys) != len(set(keys)) or any(not key.replace("_", "").isalnum() for key in keys):
        raise ValueError("Experiment keys must be unique filename-safe identifiers")
    if args.plan:
        for run in plan:
            print(json.dumps({"key": run["key"], "overrides": run["overrides"], "arguments": ARGUMENTS}))
        return 0
    helper = runpy.run_path(str(Path(__file__).with_name("campagne_a2_runner.py")))
    resources = helper["limit_resources"](16)
    save = helper["save"]
    worktree, output = args.worktree.resolve(), args.output.resolve()
    a2_output = args.a2_output.resolve()
    reference = json.loads((args.reference_output / "etat.json").read_text(encoding="utf-8"))
    if reference["status"] != "complete":
        raise RuntimeError("The reference pair is incomplete")
    baseline = next(run["summary"] for run in reference["runs"] if run["variant"] == "actuel")
    expected_sources = reference["source_sha256"]
    expected_commit = reference["commit"]
    spec = importlib.util.spec_from_file_location("rate_pistes_summary", worktree / "scripts/resumer_artefact_sonde.py")
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)

    def fingerprints() -> dict[str, str]:
        return {name: hashlib.sha256((worktree / name).read_bytes()).hexdigest() for name in SOURCE_FILES}

    def check_sources() -> None:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, encoding="utf-8").strip()
        modified = set(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=worktree, encoding="utf-8").splitlines())
        if commit != expected_commit or modified != set(SOURCE_FILES) or fingerprints() != expected_sources:
            raise RuntimeError("The frozen source snapshot differs from the reference")

    check_sources()
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / "etat.json"
    state = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"runs": []}
    if state.get("current_pid"):
        raise RuntimeError("Unreconciled current run: inspect its process and artifact before resuming")
    completed = {run["key"]: run for run in state["runs"]}
    for run in plan:
        if run["key"] in completed and completed[run["key"]]["overrides"] != run["overrides"]:
            raise RuntimeError("A completed experiment cannot change its parameters")
    state.update(status="waiting_for_a2", pid=os.getpid(), resources=resources, commit=expected_commit,
                 source_sha256=expected_sources, reference=str(args.reference_output.resolve()), plan=plan,
                 deadline_utc=DEADLINE.isoformat(), current=None, current_pid=None)
    state.pop("error", None)
    lock = output / ".running"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))

    def report() -> None:
        lines = ["# Rate : essais successifs sur r75x0.5 (2026-10-13)", "",
                 f"État : `{state['status']}` ; {len(state['runs'])} essai(s) sauvegardé(s).",
                 "Graine 101, mode deep, mêmes sources que le A/B ; paramètres effectifs et SHA256 dans `etat.json`.",
                 "16 processeurs logiques, affinité 0xffff, priorité normale, 15 threads de bibliothèque ; une mesure à la fois.",
                 "A2 sauvegarde son calcul courant avant les essais ; sa reprise est conservée.", "",
                 "| essai | surcharges | meilleur SEEL nm | écart à la référence | déposables | durée min |",
                 "|---|---|---:|---:|---:|---:|",
                 f"| référence A/B | équilibrage désactivé, budget 120 | {baseline['meilleur_seel']:.6f} | — | {baseline['deposables']} | 46,75 |"]
        for run in state["runs"]:
            data = run["summary"]
            score = data["meilleur_seel"]
            delta = "—" if score is None else f"{100 * (score / baseline['meilleur_seel'] - 1):+.2f} %"
            seel_text = "aucun" if score is None else f"{score:.6f}"
            minutes = "reprise" if run.get("seconds") is None else f"{run['seconds'] / 60:.2f}"
            overrides = ", ".join(f"{key}={value}" for key, value in run["overrides"].items())
            lines.append(f"| {run['key']} | `{overrides}` | {seel_text} | {delta} | {data['deposables']} | {minutes} |")
        for run in state["runs"]:
            data = run["summary"]
            lines += ["", f"Artefact `{run['key']}` : [{run['artifact']}]({output.name}/{run['artifact']})."]
            if data["meilleur"]:
                lines += [summary.forme_du_plan(data["meilleur"], data["n_couches"])]
        lines += ["", "Un seul composant et une graine de recherche ; un gain exige un contrôle indépendant.",
                  "Profondeurs conservées : 300 tirages complets, 50 au screening, consensus à 300.",
                  "Les durées comprennent des états de cache différents ; elles ne prouvent pas seules un gain de vitesse.",
                  "Aucun défaut modifié et aucun commit. Suite complète du code expérimental antérieur encore à faire."]
        if state.get("error"):
            lines += ["", f"Erreur : `{state['error']}`."]
        report_path = output.parent / (output.name + ".md")
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(report_path)

    def checkpoint() -> None:
        state["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
        save(status_path, state)
        report()

    env = os.environ.copy()
    for key in ("CERTUS_PROBE_OVERRIDES", "CERTUS_PROBE_TAG", "CERTUS_CONSENSUS_SEEDS", "CERTUS_RATE_SETS", "CERTUS_TAIL_CUTS", "CERTUS_DESIGN_JSON", "CERTUS_CONFIG_DIR", "_CERTUS_NUMBA_CONFIGURED", "NUMBA_CACHE_DIR", "NUMBA_THREADING_LAYER"):
        env.pop(key, None)
    env.update(CERTUS_BENCH_TIMEOUT_S="21600", QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHON_CPU_COUNT="16")
    for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "15"
    env["CERTUS_CONFIG_DIR"] = str(worktree / "scratch/rate_batch_preferences")
    process = None
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        checkpoint()
        while True:
            a2_state = json.loads((a2_output / "etat.json").read_text(encoding="utf-8"))
            if a2_state["status"] == "paused" and not a2_state.get("current_pid") and not (a2_output / ".running").exists():
                break
            if not args.wait_a2 or a2_state["status"] not in ("finishing_current", "running", "paused"):
                raise RuntimeError("A2 is not safely paused")
            if datetime.now(UTC) >= DEADLINE:
                state["status"] = "deadline_reached"
                return 0
            time.sleep(15)
        if (args.reference_output / ".running").exists():
            raise RuntimeError("The reference pair is still running")
        for run in plan:
            if run["key"] in completed:
                continue
            if datetime.now(UTC) >= DEADLINE:
                state["status"] = "deadline_reached"
                return 0
            check_sources()
            tag = "rate_pistes_" + run["key"]
            prefix = "blocs_vs_plantage_r75x0.5_deep_s101_" + tag
            existing = list((worktree / "reports").glob(prefix + "*.json"))
            seconds = None
            if not existing:
                run_env = env.copy()
                overrides = ",".join(f"{key}={str(value).lower()}" for key, value in run["overrides"].items())
                run_env.update(CERTUS_PROBE_OVERRIDES=overrides, CERTUS_PROBE_TAG=tag)
                print(f"START {run['key']} {overrides}", flush=True)
                started = time.monotonic()
                with (output / (run["key"] + ".log")).open("ab") as log:
                    process = subprocess.Popen([sys.executable, "scripts/probe_blocs_vs_plantage.py", *ARGUMENTS], cwd=worktree, env=run_env,
                                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS)
                    state.update(status="running", current=run["key"], current_pid=process.pid, current_overrides=run["overrides"],
                                 current_started=datetime.now(UTC).isoformat(timespec="seconds"))
                    checkpoint()
                    code = process.wait()
                if code:
                    raise RuntimeError(f"{run['key']} exited {code}; see its log")
                seconds = time.monotonic() - started
                existing = list((worktree / "reports").glob(prefix + "*.json"))
            if len(existing) != 1:
                raise RuntimeError(f"Expected one artifact, got {len(existing)}")
            artifact = json.loads(existing[0].read_text(encoding="utf-8"))
            prov, config = artifact.get("provenance") or {}, artifact.get("config") or {}
            if artifact.get("verdict") != "OK" or prov.get("git_commit") != expected_commit or prov.get("git_dirty") is not True or prov.get("numba_cache_keyed") is not True:
                raise RuntimeError("Invalid frozen measurement provenance")
            if config.get("overrides") != run["overrides"] or config.get("overrides_tag") != tag or config.get("elite_rate_moves") is not True:
                raise RuntimeError("The expected overrides did not reach the probe")
            if artifact.get("seed") != 101 or artifact.get("composant") != "r75x0.5" or artifact.get("mode") != "deep" or artifact.get("profondeur") != {"robustness_num_runs": 300, "n_screen_runs": 50, "dp_top_k": 100, "consensus_num_runs": 300}:
                raise RuntimeError("The shared seed, example or scoring depths changed")
            log_text = (output / (run["key"] + ".log")).read_text(encoding="utf-8", errors="replace")
            if "[balanced families]" in log_text and not run["overrides"].get("elite_rate_balanced_moves"):
                raise RuntimeError("Balancing unexpectedly active")
            if "elite_rounds" in run["overrides"] and f"Round 1/{run['overrides']['elite_rounds']}" not in log_text:
                raise RuntimeError("The requested round ceiling was not routed")
            if "elite_rate_max_candidates" in run["overrides"] and config.get("elite_rate_max_candidates") != run["overrides"]["elite_rate_max_candidates"]:
                raise RuntimeError("The requested Rate ceiling was not routed")
            check_sources()
            target = output / existing[0].name
            if target.exists():
                if target.read_bytes() != existing[0].read_bytes():
                    raise RuntimeError("Existing artifact differs; refusing overwrite")
            else:
                temporary = target.with_suffix(".tmp")
                shutil.copy2(existing[0], temporary)
                temporary.replace(target)
            state["runs"].append({**run, "artifact": target.name, "seconds": seconds, "arguments": ARGUMENTS,
                                  "summary": summary.resumer(artifact), "source_sha256": expected_sources})
            state.update(current=None, current_pid=None)
            checkpoint()
            print(f"DONE {run['key']} SEEL={state['runs'][-1]['summary']['meilleur_seel']}", flush=True)
        state["status"] = "complete"
        return 0
    except BaseException as error:
        state.update(status="failed", error=str(error))
        if process is None or process.poll() is not None:
            state.update(current_pid=None)
        raise
    finally:
        try:
            checkpoint()
        finally:
            lock.unlink(missing_ok=True)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    raise SystemExit(main())
