"""Chantier 49 : note un plan STRAT déjà choisi, sans refaire la recherche.

Les deux runs de la graine 42 ont fini STRAT et consigné leur plan (`runs/*.plan.json`), puis le contrôle d'arrivée du
banc les a refusés à tort : la table de couches de STRAT relit six décimales de QWOT, d'où un écart d'épaisseur de
l'ordre de 1e-5 nm que la tolérance relative de 1e-9 ne laissait pas passer. Ce script ouvre la vraie fenêtre STRAT
sur le même fichier de fenêtre (`runs/*.strat.json`), garde les paramètres du worker, et remplace la seule recherche
par : épaisseurs nominales et indices (`calculate_nominal_properties`, `precompute_clues_and_matrices`, comme la
phase prérequise), puis
  1. le rejeu, graines 41, 42, 43 à 300 tirages, à comparer aux P95 de la feuille « Robustness Best Strategy » du
     rapport de STRAT : s'ils coïncident, paramètres et plan sont ceux du run ;
  2. la notation sur les graines disjointes du banc (`bench_bonne_mere.holdout`).

set PYTHONPATH=.;scripts && python reports/chantier49_2026-11-18/rescore_plan.py --design DESIGN.json --run runs/nominal_s42 --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import bench_bonne_mere as bbm  # noqa: E402
import bench_examples as bench  # noqa: E402

REPLAY_SEEDS = (41, 42, 43)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path, help="run prefix: <run>.strat.json and <run>.plan.json")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=400)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"Output already exists: {args.out}")

    import numpy as np
    from _artefact import ecrire_json

    bench.qapp()
    bench.autoanswer_dialogs()
    from certus.core.certus_strat_config import precompute_clues_and_matrices
    from certus.core.certus_strat_local_search import native_evaluator
    from certus.utils.certus_strat_service import calculate_nominal_properties
    from certus.workers import certus_strat_workers_pipeline as pipeline

    design = json.loads(args.design.read_text(encoding="utf-8"))
    saved = json.loads(args.run.with_suffix(".plan.json").read_text(encoding="utf-8"))
    plan = saved["plan"]
    os.environ["CERTUS_DESIGN_JSON"] = str(args.run.with_suffix(".strat.json").resolve())
    measured: dict = {}

    def rescore(_self, worker) -> None:
        started = perf_counter()
        params = worker.params
        nominal, _ = calculate_nominal_properties(params)
        ep = list(nominal["physical_thicknesses_nominal"])
        clues, _, _ = precompute_clues_and_matrices(params, ep, params["logger"])
        evaluator = native_evaluator(params, ep, clues, {}, thickness=False)
        replay = {}
        for seed in REPLAY_SEEDS:
            levels = evaluator(plan, seed, int(params["robustness_num_runs"]))
            replay[str(seed)] = [float(np.percentile(level[0], 95)) for level in levels]
        measured.update(
            run=args.run.name, design=args.design.name, robustness_num_runs=int(params["robustness_num_runs"]), replay_p95_by_seed=replay,
            **bbm.holdout(design, {"p_thick_nominal": ep, "clues_at_wl": clues}, params, plan, args.runs),
        )
        measured["rescore_seconds"] = perf_counter() - started
        ecrire_json(args.out, measured)

    pipeline.FullPipelineStrategy.execute = rescore
    bench.run_strat()
    if not measured:
        raise RuntimeError("Rescoring did not run")
    print(f"REPLAY {json.dumps(measured['replay_p95_by_seed'])}", flush=True)
    print(f"RESULT seel_nm={measured['seel_nm']:.5f} stops={measured['stops_by_level']} "
          f"max_rel_thickness_gap={measured['max_rel_thickness_gap']:.3g}", flush=True)


if __name__ == "__main__":
    main()
