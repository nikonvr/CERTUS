"""Run the real full STRAT probe with one temporary, explicitly fingerprinted ELITE adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--joint-budget", type=int, default=0)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    if args.joint_budget < 0:
        raise ValueError("The joint budget must be non-negative")
    root = Path(__file__).resolve().parents[1]
    worktree, output = args.worktree.resolve(), args.output.resolve()
    probe_arguments = ["r75x0.5", "deep", "0", "0", "2", "0", str(args.seed), "0"]
    if args.plan:
        print(json.dumps({"arguments": probe_arguments, "joint_budget": args.joint_budget,
                          "legacy_order_and_budget": "unchanged", "screen_and_full_caps": "unchanged",
                          "path": "real full probe; extra joint moves through the original candidate factory"}))
        return 0
    if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
        raise RuntimeError("The deadline forbids a new measurement")
    for name in ("STRAT_ELITE_couches_Rate_autres_composants_2026-10-13", "STRAT_Rate_equilibre_AB_2026-10-13",
                 "STRAT_Rate_pistes_2026-10-13", "STRAT_Rate_joint_window_2026-10-13", "STRAT_Rate_joint_refinement_2026-10-13"):
        if (root / "reports" / name / ".running").exists():
            raise RuntimeError(f"Another measurement controller owns {name}")
    reference = json.loads(args.reference_state.read_text(encoding="utf-8"))

    def check_sources():
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, encoding="utf-8").strip()
        changed = set(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=worktree, encoding="utf-8").splitlines())
        hashes = {name: hashlib.sha256((worktree / name).read_bytes()).hexdigest() for name in reference["source_sha256"]}
        if commit != reference["commit"] or changed != set(hashes) or hashes != reference["source_sha256"]:
            raise RuntimeError("Source snapshot differs from the measured reference")
        return hashes

    sources = check_sources()
    helper = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))
    resources = helper["limit_resources"](16)
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "etat.json"
    if state_path.exists():
        raise RuntimeError("Inspect the existing native measurement before any restart")
    lock = output / ".running"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    generator_path = root / "scratch/rate_joint_native_candidates.py"
    script_hashes = {"adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "generator": hashlib.sha256(generator_path.read_bytes()).hexdigest(),
                     "controller_helper": hashlib.sha256((root / "scratch/campagne_a2_runner.py").read_bytes()).hexdigest()}
    trace = []
    state = {"status": "running", "pid": os.getpid(), "started": datetime.now(UTC).isoformat(), "resources": resources,
             "arguments": probe_arguments, "joint_budget": args.joint_budget, "source_sha256": sources,
             "script_sha256": script_hashes, "overrides": "elite_rate_balanced_moves=false"}
    tag = f"rate_native_joint{args.joint_budget}_s{args.seed}_v1"
    native_artifact = worktree / "reports" / f"blocs_vs_plantage_r75x0.5_deep_s{args.seed:03d}_{tag}.json"
    if native_artifact.exists():
        raise RuntimeError("The proposed tagged artifact already exists; choose a new attempt")
    try:
        helper["save"](state_path, state)
        for key in ("CERTUS_CONSENSUS_SEEDS", "CERTUS_RATE_SETS", "CERTUS_TAIL_CUTS", "CERTUS_DESIGN_JSON", "NUMBA_CACHE_DIR",
                    "_CERTUS_NUMBA_CONFIGURED", "NUMBA_THREADING_LAYER"):
            os.environ.pop(key, None)
        os.environ.update(PYTHON_CPU_COUNT="16", PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen", CERTUS_BENCH_TIMEOUT_S="21600",
                          CERTUS_PROBE_OVERRIDES="elite_rate_balanced_moves=false", CERTUS_PROBE_TAG=tag,
                          CERTUS_CONFIG_DIR=str(worktree / "scratch/rate_batch_preferences"))
        for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ[key] = "15"
        os.chdir(worktree)
        sys.path[:0] = [str(worktree), str(worktree / "scripts")]
        import bench_examples as bx

        bx.qapp()
        bx.autoanswer_dialogs(True)
        import _artefact

        import certus.core.certus_strat_consensus as consensus
        from certus.utils.certus_strat_context import _plan_signature

        real_factory = consensus._generate_elite_candidate_strategies
        real_provenance = _artefact.avec_provenance
        extend_factory = runpy.run_path(str(generator_path))["extend_factory"]

        def generate(*factory_args, **factory_kwargs):
            candidates, cursor, event = extend_factory(real_factory, consensus, _plan_signature, factory_args, factory_kwargs, args.joint_budget)
            if event is not None:
                trace.append(event)
            return candidates, cursor

        def provenance(data):
            enriched = real_provenance(data)
            if isinstance(enriched, dict):
                enriched = {**enriched, "native_joint_adapter": {**state, "n_generator_calls": len(trace),
                                                               "joint_offered": sum(t["joint_count"] for t in trace),
                                                               "legacy_preserved_before_joint_candidates": True}}
            return enriched

        sys.argv = [str(worktree / "scripts/probe_blocs_vs_plantage.py"), *probe_arguments]
        with patch.object(consensus, "_generate_elite_candidate_strategies", generate), patch.object(_artefact, "avec_provenance", provenance):
            try:
                runpy.run_path(sys.argv[0], run_name="__main__")
            except SystemExit as ended:
                if ended.code not in (None, 0):
                    raise RuntimeError(f"Native probe exited {ended.code}") from ended
        check_sources()
        artifact = json.loads(native_artifact.read_text(encoding="utf-8"))
        if artifact["verdict"] != "OK" or artifact["native_joint_adapter"]["script_sha256"] != script_hashes:
            raise RuntimeError("Invalid native artifact verdict or adapter provenance")
        with (output / native_artifact.name).open("xb") as stream:
            stream.write(native_artifact.read_bytes())
        state.update(status="complete", artifact=str(output / native_artifact.name))
        return 0
    except BaseException:
        state.update(status="failed", error=traceback.format_exc())
        raise
    finally:
        try:
            helper["save"](output / "generated_candidates.json", {"script_sha256": script_hashes, "calls": trace})
            state["updated"] = datetime.now(UTC).isoformat()
            helper["save"](state_path, state)
        finally:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
