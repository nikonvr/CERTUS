"""Replay complete mixed plans through the external evaluation path, without generating children.

Prepared experiment only: its reference fixed point must pass before any holdout.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import runpy
import subprocess
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--reference-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", choices=("control", "holdout_202", "holdout_303", "holdout_404", "holdout_505", "holdout_606", "holdout_707", "search"), required=True)
    parser.add_argument("--validated-control", type=Path)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    worktree = args.worktree.resolve()
    plans_file, protocol_file = args.plans.resolve(), args.protocol.resolve()
    reference_file, output = args.reference_state.resolve(), args.output.resolve()
    raw = json.loads(plans_file.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    setting = protocol["control"] if args.run in ("control", "search") else next(
        item for item in protocol["holdouts"] if item["robustness_seed"] == int(args.run.split("_")[1])
    )
    if args.plan:
        print(json.dumps({"run": args.run, "setting": setting, "plans": [p["nom"] for p in raw["plans"]],
                          "depths": protocol["depths"], "path": "ExternalEvaluationStrategy",
                          "expand_variants": False, "elite_generation": False}))
        return 0
    if datetime.now(UTC) >= datetime(2026, 10, 14, 7, tzinfo=UTC):
        raise RuntimeError("The deadline forbids a new measurement")
    for name in ("STRAT_ELITE_couches_Rate_autres_composants_2026-10-13",
                 "STRAT_Rate_equilibre_AB_2026-10-13", "STRAT_Rate_pistes_2026-10-13"):
        if (root / "reports" / name / ".running").exists():
            raise RuntimeError(f"Another measurement controller owns {name}")
    output.mkdir(parents=True, exist_ok=True)
    if args.run not in ("control", "search"):
        control = json.loads((output / "control.json").read_text(encoding="utf-8"))
        if control["verdict"] != "OK" or control["plans_sha256"] != hashlib.sha256(plans_file.read_bytes()).hexdigest():
            raise RuntimeError("These exact plans have no passing reference control")
    reference = json.loads(reference_file.read_text(encoding="utf-8"))

    def check_sources() -> dict[str, str]:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, encoding="utf-8").strip()
        changed = set(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=worktree, encoding="utf-8").splitlines())
        hashes = {name: hashlib.sha256((worktree / name).read_bytes()).hexdigest() for name in reference["source_sha256"]}
        if commit != reference["commit"] or changed != set(hashes) or hashes != reference["source_sha256"]:
            raise RuntimeError("Source snapshot differs from the measured reference")
        return hashes

    sources = check_sources()
    if args.run == "search":
        if args.validated_control is None:
            raise RuntimeError("Search requires a passing fixed-point control")
        trusted = json.loads(args.validated_control.read_text(encoding="utf-8"))
        if trusted["verdict"] != "OK" or trusted["source_sha256"] != sources or trusted["setting"] != setting:
            raise RuntimeError("The search anchors have no matching validated context")
        trusted_plans = {p["source_strategy_id"]: p for p in trusted["plans"]}
        anchors = [p for p in raw["plans"] if "expected_score_fixed_point" in p]
        if len(anchors) < 2:
            raise RuntimeError("Both measured anchors must be present in every search batch")
        for anchor in anchors:
            previous = trusted_plans.get(anchor["source_strategy_id"], {})
            if any(anchor.get(key) != previous.get(key) for key in ("blocks", "rate_layers", "monochromator_resolution_nm", "witness_reset_layers", "expected_score_fixed_point")):
                raise RuntimeError(f"Search anchor changed: {anchor['nom']}")
    resources = runpy.run_path(str(root / "scratch/campagne_a2_runner.py"))["limit_resources"](16)
    lock = output / ".running"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    request = {"status": "running", "pid": os.getpid(), "run": args.run, "setting": setting,
               "plans_sha256": hashlib.sha256(plans_file.read_bytes()).hexdigest(), "resources": resources,
               "source_sha256": sources, "started": datetime.now(UTC).isoformat()}
    request_path = output / (f"request_{args.run}_{datetime.now(UTC):%Y%m%d_%H%M%S}.json")
    try:
        with request_path.open("x", encoding="utf-8") as stream:
            json.dump(request, stream, ensure_ascii=False, indent=2)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ[key] = "15"
        for key in ("NUMBA_CACHE_DIR", "_CERTUS_NUMBA_CONFIGURED", "NUMBA_THREADING_LAYER"):
            os.environ.pop(key, None)
        os.environ["CERTUS_CONFIG_DIR"] = str(worktree / "scratch/rate_batch_preferences")
        os.chdir(worktree)
        sys.path[:0] = [str(worktree), str(worktree / "scripts")]
        import bench_examples as bx

        bx.qapp()  # Windows requires Qt before the numerical libraries.
        bx.autoanswer_dialogs(True)
        import numpy as np
        from _artefact import avec_provenance
        from _composant import charger_configuration
        from probe_blocs_vs_plantage import _rmse_par_bruit

        import certus.core.certus_strat_robustness as robustness
        import certus.workers.certus_strat_workers_external as external
        from certus.core.certus_strat_consensus import _resolve_consensus_ranking_params
        from certus.core.certus_strat_robustness import run_final_simulation_block
        from certus.utils.certus_data import SharedIndicesManager, SharedIndicesWorker
        from certus.utils.certus_exclusions import filter_params_for_serialization
        from certus.utils.certus_strat_context import _validate_strategy_blocks_contract
        from certus.workers.certus_strat_workers import StratTask, WorkerThread
        from CERTUS_STRAT import CertusStratApp

        app = CertusStratApp()
        bx.attach_console_logging(app)
        design = worktree / "reports/serie_echelle_r75/cfg_x0.5.json"
        charger_configuration(app, design)
        app.widgets["execution_mode"].setCurrentText("deep")
        params = app.collect_params()
        params.update(show_plots=False, export_excel=False, execution_mode="deep", search_resolution=False,
                      monochromator_resolution_nm=2.0, noise_layer_offset=0, noise_total_layers=75,
                      require_turning_point=0, robustness_seed=setting["robustness_seed"],
                      consensus_seed_list=setting["consensus_seed_list"], ablation_profile=False)
        for key, value in protocol["depths"].items():
            if params.get(key) != value:
                raise RuntimeError(f"Scoring depth changed: {key}={params.get(key)}, expected {value}")
        plans = []
        for i, plan in enumerate(raw["plans"]):
            strategy = copy.deepcopy(plan)
            strategy.update(strategy_id=plan.get("source_strategy_id", 9_500_000 + i),
                            n_blocks=len(plan["blocks"]), origin=f"FIXED_REPLAY({plan['nom']})")
            valid, reason = _validate_strategy_blocks_contract(strategy, 75)
            if not valid:
                raise ValueError(f"Invalid mixed plan {plan['nom']}: {reason}")
            plans.append(strategy)
        params["loaded_strategies"] = plans
        cfg = _resolve_consensus_ranking_params(params, num_runs=300)
        if not cfg["enabled"] or cfg["seeds"] != setting["consensus_seed_list"] or cfg["num_runs"] != 300 or cfg["top_k"] < len(plans):
            raise RuntimeError(f"Consensus routing cannot score every fixed plan: {cfg}")
        worker = WorkerThread(StratTask.EXTERNAL_EVALUATION, params=params)
        box = {}
        simulations = []
        simulation_lock = threading.Lock()
        real_task = robustness._test_strategy_robustness_task

        def record_task(*task_args, **task_kwargs):
            try:
                result = real_task(*task_args, **task_kwargs)
            except Exception:
                if args.run == "search":
                    with simulation_lock:
                        simulations.append({"id": task_args[0]["strategy_id"], "seed": task_args[6].get("robustness_seed"),
                                            "num_runs": task_args[3], "error": traceback.format_exc()})
                raise
            if args.run == "search":
                observed = {"id": task_args[0]["strategy_id"], "seed": task_args[6].get("robustness_seed"),
                            "num_runs": task_args[3], "score": result.get("robustness_score"),
                            "crash_rate": result.get("crash_rate"), "crash_rates_by_noise": result.get("crash_rates_by_noise"),
                            "rmse_par_bruit": _rmse_par_bruit(result)}
                with simulation_lock:
                    simulations.append(observed)
            return result

        def keep_fixed_plans(*, strategies_results, ctx, apply_consensus_fn):
            ctx.logger.info("[FIXED-REPLAY] ELITE generation skipped; physical scoring and consensus unchanged.")
            return strategies_results

        def evaluate_fixed(opti_results, actual_params, num_runs):
            # Full-pipeline workers receive clues through this float32 transport.
            # Reuse it exactly; direct clues made both fixed-point scores drift.
            with SharedIndicesManager(opti_results["clues_at_wl"]) as manager, SharedIndicesWorker(manager.get_context_info()) as shared_clues:
                context = {**opti_results, "clues_at_wl": shared_clues}
                result = run_final_simulation_block(context, actual_params, num_runs, expand_variants=False)
            box["final_results"] = result
            return result

        started = time.monotonic()
        worker._execute_nominal_analysis_auto()
        with patch.object(external, "run_final_simulation_block", evaluate_fixed), patch(
            "certus.core.certus_strat_consensus._apply_elite_refinement_if_enabled", keep_fixed_plans
        ), patch.object(robustness, "_test_strategy_robustness_task", record_task):
            external.ExternalEvaluationStrategy().execute(worker)
        rows = box["final_results"]["all_strategies_results"]
        errors = [f"Simulation failed: id={item['id']} seed={item['seed']}" for item in simulations if item.get("error")]
        rejected = []
        eligible_ids = []
        by_id = {row["strategy"]["strategy_id"]: row for row in rows}
        if len(rows) != len(by_id) or (args.run != "search" and len(rows) != len(plans)):
            errors.append("The fixed plan count or identifiers changed")
        for original in plans:
            row = by_id.get(original["strategy_id"])
            if row is None:
                if args.run == "search" and "expected_score_fixed_point" not in original:
                    rejected.append({"id": original["strategy_id"], "reason": "base score non-finite"})
                else:
                    errors.append(f"Missing fixed plan {original['nom']}")
                continue
            errors.extend(
                f"Metadata changed: {original['nom']} {key}"
                for key in ("blocks", "rate_layers", "monochromator_resolution_nm", "witness_reset_layers")
                if row["strategy"].get(key) != original.get(key)
            )
            meta = row.get("robustness_consensus_meta") or {}
            if meta.get("seeds") != setting["consensus_seed_list"] or meta.get("n_samples") != len(setting["consensus_seed_list"]):
                if args.run == "search" and "expected_score_fixed_point" not in original:
                    rejected.append({"id": original["strategy_id"], "reason": "incomplete consensus"})
                else:
                    errors.append(f"Incomplete consensus: {original['nom']}")
            else:
                if math.isfinite(row.get("robustness_score", math.inf)):
                    eligible_ids.append(original["strategy_id"])
        if args.run == "search":
            base_ids = {item["id"] for item in simulations if item["seed"] == setting["robustness_seed"]}
            if base_ids != {plan["strategy_id"] for plan in plans} or any(item["num_runs"] != 300 for item in simulations):
                errors.append("The search did not evaluate every offered plan at full depth")
        if args.run in ("control", "search"):
            for i, original in enumerate(plans):
                expected = original.get("expected_score_fixed_point", raw.get("expected_score_fixed_point") if i == 0 else None)
                if expected is None:
                    if args.run != "search":
                        errors.append(f"No fixed point expectation for {original['nom']}")
                    continue
                actual = by_id.get(original["strategy_id"], {}).get("robustness_score", math.inf)
                if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-10):
                    errors.append(f"Fixed point failed: {original['nom']} {actual} vs {expected}")
        check_sources()
        artifact = avec_provenance({"verdict": "FAILED_REPLAY" if errors else "OK", "errors": errors,
                                   "run": args.run, "setting": setting, "depths": protocol["depths"],
                                   "resources": resources, "source_sha256": sources,
                                   "plans_sha256": hashlib.sha256(plans_file.read_bytes()).hexdigest(),
                                   "protocol_sha256": hashlib.sha256(protocol_file.read_bytes()).hexdigest(),
                                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                   "design_sha256": hashlib.sha256(design.read_bytes()).hexdigest(),
                                   "parameters": filter_params_for_serialization(worker.params),
                                   "generation_disabled": ["rate/slit expansion", "Rate rescue", "ELITE"],
                                   "clues_transport": "SharedIndicesManager/Worker (float32), as full-pipeline workers",
                                   "ablation_profile": False, "seconds": time.monotonic() - started,
                                   "plans": plans, "final_results": box["final_results"]})
        if args.run == "search":
            artifact.update(search_eligible_ids=eligible_ids, search_rejected=rejected,
                            simulations=sorted(simulations, key=lambda item: (item["id"], item["seed"])))

        def convert(value):
            if isinstance(value, np.ndarray):
                return value.tolist()
            if isinstance(value, np.generic):
                return value.item()
            raise TypeError(f"Unsupported artifact value: {type(value).__name__}")

        from _artefact import chemin_libre

        target, _ = chemin_libre(output / (args.run + ".json"))
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=convert), encoding="utf-8")
        temporary.replace(target)
        bx.emit(f"FIXED_REPLAY={artifact['verdict']} artifact={target} errors={errors}")
        request.update(status="failed" if errors else "complete", artifact=str(target), errors=errors)
        return 1 if errors else 0
    except BaseException:
        request.update(status="failed", error=traceback.format_exc())
        raise
    finally:
        try:
            if request_path.exists():
                temporary = request_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(request_path)
        finally:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
