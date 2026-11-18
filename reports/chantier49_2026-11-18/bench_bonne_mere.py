"""Chantier 49 : STRAT sur deux designs de la Bonne Mère a 90 couches, nominal et robuste, une graine STRAT par processus.

Composant (décision de 👤, 2026-11-18) : la Bonne Mère, 90 couches H800 Nb2O5 / SiO2 sur silice, face arrière incohérente.
Réglage STRAT : la configuration de fenêtre de la campagne STRAT à 90 couches du 23 octobre
(`reports/BONNE_MERE_strat_90c_2026-10-23/config_strat_90c_corridor0.010.json`, budgets et réglages spectraux de l'étude,
sans règles de Rate), où changent les multiplicateurs (ceux du design), le couloir d'indice (0,005, celui de l'étude) et
les graines. La fenêtre reçoit un fichier de fenêtre : un vidage des paramètres du worker n'y arrive pas (`wl_range`, par
exemple, se lit dans `wl_range_start` et `wl_range_end`) ; le banc vérifie à l'arrivée la plage, le substrat et les
épaisseurs. Le plan choisi est noté sur des graines disjointes, communes à tous les runs : SEEL, arrêts, couches au Rate,
blocs.

set PYTHONPATH=.;scripts && set CERTUS_BENCH_TIMEOUT_S=21600 && python reports/chantier49_2026-11-18/bench_bonne_mere.py --design DESIGN.json --seed 42 --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as bench  # noqa: E402

BASE = ROOT / "reports/BONNE_MERE_strat_90c_2026-10-23/config_strat_90c_corridor0.010.json"
STUDY = ROOT / "studies/bonne_mere/dossier_final/donnees/parametres_STRAT_effectifs.json"
HOLDOUT_SEEDS = (2026111801, 2026111802, 2026111803)
SUBSTRATE = "SiO2"


def strat_config(design: dict, seed: int) -> dict:
    from certus.utils.certus_strat_db import RobustMaterialDatabase
    from certus.utils.certus_strat_service import _PhysicsBridge
    from certus.workers.certus_strat_workers import _resolve_strat_indices_db_path

    cfg = json.loads(BASE.read_text(encoding="utf-8"))
    study = json.loads(STUDY.read_text(encoding="utf-8"))
    if design.get("order") != "substrate to incident air" or design.get("backside") is not True:
        raise ValueError("Expected a design written substrate first, with the incoherent back face")
    if design.get("materials") != [cfg["h_material_file"], cfg["l_material_file"]] or design.get("substrate_id") != 0:
        raise ValueError("Expected H800 Nb2O5 / SiO2 on silica (substrate id 0), as the study")
    idx = design["material_indices"]
    if idx != [i % 2 for i in range(len(idx))]:
        raise ValueError("STRAT alternates H then L from the substrate: the design must too")
    l0 = float(cfg["l0"])
    db = RobustMaterialDatabase(_resolve_strat_indices_db_path())  # the database and the lookup of the 23 October builder
    n_at_l0 = [float(_PhysicsBridge.get_refractive_index(name, l0, db_instance=db).real)
               for name in (cfg["h_material_file"], cfg["l_material_file"])]
    cfg.update(
        stack_multipliers=[4.0 * n_at_l0[i % 2] * float(t) / l0 for i, t in enumerate(design["thickness_nm"])],
        index_corridor=float(study["index_corridor"]),
        phase_a_seed=seed, robustness_seed=seed,
        consensus_seed_list=",".join(str(seed + k) for k in (-1, 0, 1)),
        show_plots=False, export_excel=False,
    )
    if cfg["substrate_choice"] != SUBSTRATE:
        raise ValueError("The base configuration is not on silica")
    return cfg


def holdout(design: dict, pre_calc_data: dict, params: dict, plan: dict, runs: int) -> dict:
    import numpy as np

    from certus.core.certus_strat_local_search import native_evaluator, nominal_level_index

    ep = np.asarray(pre_calc_data["p_thick_nominal"], dtype=np.float64)
    d = np.asarray(design["thickness_nm"], dtype=np.float64)
    if ep.shape != d.shape or not np.allclose(ep, d, rtol=1e-9, atol=0.0):
        raise RuntimeError("STRAT did not deposit the thicknesses of the design")
    if params.get("nSub_id") != SUBSTRATE:
        raise RuntimeError("The silica substrate did not reach STRAT")
    study_range = json.loads(STUDY.read_text(encoding="utf-8"))["wl_range"]
    if not np.allclose([float(x) for x in params["wl_range"]], study_range, rtol=0.0, atol=1e-9):
        raise RuntimeError(f"STRAT works on {params['wl_range']} nm, not on the study's {study_range}")
    evaluator = native_evaluator(params, ep.tolist(), pre_calc_data["clues_at_wl"], {}, thickness=True)
    level = nominal_level_index(params)
    scored = [evaluator(plan, s, runs) for s in HOLDOUT_SEEDS]
    rmse_by_level = [np.concatenate([seed[i][0] for seed in scored]) for i in range(len(scored[0]))]
    stopped_by_level = [np.concatenate([seed[i][1] for seed in scored]) for i in range(len(scored[0]))]
    if any(len(e) != len(HOLDOUT_SEEDS) * runs for e in rmse_by_level):
        raise RuntimeError("Invalid STRAT holdout sample")
    p95_by_level = [float(np.percentile(e, 95)) for e in rmse_by_level]
    rmse, stops = rmse_by_level[level], stopped_by_level[level]
    ok = ~stops & np.isfinite(rmse)
    return {
        "holdout_seeds": HOLDOUT_SEEDS, "draws_per_seed": runs, "noise_level_index": level,
        "seel_nm": float(2.0 * np.sqrt(max(p95_by_level))), "p95_by_level": p95_by_level,
        "stops_by_level": [int(s.sum()) for s in stopped_by_level],
        "rms_completed": float(np.sqrt(np.mean(rmse[ok] ** 2))) if ok.any() else float("nan"),
        "strategy_id": plan.get("strategy_id"), "blocks": len(plan["blocks"]),
        "rate_layers": len(plan.get("rate_layers") or []), "layers": len(ep),
        "max_rel_thickness_gap": float(np.max(np.abs(ep - d) / d)), "wl_range": [float(x) for x in params["wl_range"]],
        "index_corridor": float(params.get("index_corridor", float("nan"))),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=400)
    args = parser.parse_args()
    for path in (args.out, args.out.with_suffix(".strat.json"), args.out.with_suffix(".plan.json")):
        if path.exists():
            parser.error(f"Output already exists: {path}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from _artefact import ecrire_json
    from bench_codesign import replayable_plan

    bench.qapp()
    bench.autoanswer_dialogs()
    from certus.workers import certus_strat_workers as workers

    design = json.loads(args.design.read_text(encoding="utf-8"))
    cfg_path = args.out.with_suffix(".strat.json")
    cfg_path.write_text(json.dumps(strat_config(design, args.seed), indent=2), encoding="utf-8")
    os.environ["CERTUS_DESIGN_JSON"] = str(cfg_path.resolve())
    finalizer = workers._finalize_and_export_pipeline_results
    measured: dict = {}
    started = perf_counter()

    def capture(**kwargs):
        result = finalizer(**kwargs)
        plan = result["final_results"]["best_strategy"]
        provenance = {"design": args.design.name, "strat_seed": args.seed, "plan_seconds": perf_counter() - started}
        ecrire_json(args.out.with_suffix(".plan.json"), {**provenance, "plan": replayable_plan(plan)})
        print(f"STRAT plan selected in {provenance['plan_seconds']:.1f} s; scoring on disjoint seeds", flush=True)
        measured.update(provenance, **holdout(design, kwargs["pre_calc_data"], kwargs["params"], plan, args.runs))
        measured["total_seconds"] = perf_counter() - started
        ecrire_json(args.out, measured)
        return result

    workers._finalize_and_export_pipeline_results = capture
    bench.run_strat()
    if not measured or not args.out.is_file():
        raise RuntimeError("STRAT ended without a scored plan")
    print(f"RESULT seel_nm={measured['seel_nm']:.5f} stops={measured['stops_by_level']} rate_layers={measured['rate_layers']} "
          f"blocks={measured['blocks']} total_s={measured['total_seconds']:.0f}", flush=True)


if __name__ == "__main__":
    main()
