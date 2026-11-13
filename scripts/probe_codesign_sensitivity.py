"""SONDE CO-CONCEPTION : sous le MEME plan de controle, le depot depend-il du detail du design ?

    python scripts/probe_codesign_sensitivity.py [--config FICHIER] [--runs 300] [--budget-s 600] [--out FICHIER.json]

## POURQUOI

Audit du 2026-11-13 (reports/codesign_audit_2026-11-13) : peut-on co-concevoir le design et la strategie de controle ?
Deux chiffres manquaient, et sans eux l'audit n'est qu'une opinion :

1. LE COUT d'une evaluation « design + plan -> erreur de depot » (l'evaluateur de la recherche locale de STRAT,
   `certus/core/certus_strat_local_search.py::native_evaluator`) ;
2. LE SIGNAL : a plan de controle fige, retoucher une couche de 1 % change-t-il l'erreur de depot plus que le bruit de
   la comparaison ? S'il ne change rien, il n'y a rien a co-concevoir.

## CE QU'ELLE FAIT

Elle laisse STRAT tourner sur le fichier (pipeline complet, recherche locale comprise), intercepte la fin de la recherche
locale pour disposer du plan gagnant et des donnees partagees, puis evalue ce plan :

- sur le design nominal, deux fois sur la meme graine (controle : l'ecart doit etre nul, C2) ;
- couche par couche, a +1 % et -1 % d'epaisseur (`--step-pct`), tant que le budget de temps le permet ;
- sur des retouches globales aleatoires (sigma 0,5 %, graine fixe).

Les tirages sont une fonction pure de la graine (C2) : chaque design voit la meme realisation, la comparaison est
APPARIEE (`paired_delta` : moyenne et erreur type de rmse^2(retouche) - rmse^2(nominal)).

## CE QU'ELLE NE DIT PAS

🔴 Sans cibles dans le fichier, le RMSE de STRAT se mesure contre le spectre nominal DU DESIGN EVALUE : la sonde mesure
donc l'erreur de PRODUCTION de chaque design, pas sa performance contre un cahier des charges. Elle rapporte a cote le
deplacement du spectre nominal (`nominal_shift_rms`), pour que les deux se comparent.
🔴 Le plan n'est pas re-optimise pour le design retouche : c'est une borne PESSIMISTE de ce qu'une co-conception gagnerait.
🔴 Une graine, un composant : aucune generalite (CLAUDE.md §4).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

#: Graine de la sonde, ajoutee a celle du fichier : disjointe de celles de la recherche locale (7_000_003...).
PROBE_SEED_OFFSET = 7_300_003


def _mesurer(sortie, pre_calc_data, params, shared_clues_info, runs: int, budget_s: float, step_pct: float) -> dict:
    import numpy as np

    from certus.core.certus_strat_local_search import native_evaluator, nominal_level_index, paired_delta, stops
    from certus.core.certus_strat_robustness import _prepare_robustness_nominal_optics
    from certus.utils.certus_data import SharedIndicesWorker

    rows, report, ranker = sortie
    plan = ranker(list(rows))[0]["strategy"]
    nominal = np.asarray(pre_calc_data["p_thick_nominal"], dtype=np.float64)
    grid_dyn = pre_calc_data.get("full_dynamics_grid", {})
    seed = int(params.get("robustness_seed") or 42) + PROBE_SEED_OFFSET
    level = nominal_level_index(params)
    out: dict = {
        "layers": len(nominal),
        "runs": runs,
        "seed": seed,
        "noise_level_index": level,
        "has_targets": bool(params.get("targets")),
        "local_search_accepted": bool((report or {}).get("accepted")),
        "plan_blocks": len(plan.get("blocks") or []),
        "plan_rate_layers": len(plan.get("rate_layers") or []),
        "step_pct": step_pct,
    }
    with SharedIndicesWorker(shared_clues_info) as clues:
        t_nom_ref = np.asarray(_prepare_robustness_nominal_optics(
            params=params, p_thick_nominal=list(nominal), opti_results={"clues_at_wl": clues})[4], dtype=np.float64)

        def evaluer(epaisseurs: np.ndarray):
            t0 = time.perf_counter()
            ev = native_evaluator(params, list(epaisseurs), clues, grid_dyn)
            t1 = time.perf_counter()
            res = ev(plan, seed, runs)
            return res, t1 - t0, time.perf_counter() - t1

        def decalage_nominal(epaisseurs: np.ndarray) -> float:
            t_nom = np.asarray(_prepare_robustness_nominal_optics(
                params=params, p_thick_nominal=list(epaisseurs), opti_results={"clues_at_wl": clues})[4], dtype=np.float64)
            return float(np.sqrt(np.mean((t_nom - t_nom_ref) ** 2)))

        ref, t_fab, t_eval = evaluer(nominal)
        ref2, _, t_eval2 = evaluer(nominal)
        rmse_ref, stopped_ref = ref[level]
        ok = ~stopped_ref
        out["baseline"] = {
            "mean_rmse2": float(np.mean(rmse_ref[ok] ** 2)) if np.any(ok) else None,
            "rmse": float(np.sqrt(np.mean(rmse_ref[ok] ** 2))) if np.any(ok) else None,
            "stops_all_levels": stops(ref),
            "factory_s": round(t_fab, 4),
            "evaluate_s": round(t_eval, 4),
            "evaluate_again_s": round(t_eval2, 4),
            # 🔒 Le controle C2 : meme design, meme graine -> meme realisation. Un ecart non nul invaliderait tout l'apparie.
            "same_seed_delta": paired_delta(ref, ref2, level)[0],
        }
        base2 = out["baseline"]["mean_rmse2"] or float("nan")

        def ligne(epaisseurs: np.ndarray) -> dict:
            ev, _, dt = evaluer(epaisseurs)
            delta, se = paired_delta(ref, ev, level)
            return {
                "delta_rmse2": delta, "se": se,
                "rel": delta / base2 if base2 else None,
                "z": (delta / se) if se and np.isfinite(se) and se > 0 else None,
                "stops_all_levels": stops(ev),
                "nominal_shift_rms": decalage_nominal(epaisseurs),
                "evaluate_s": round(dt, 4),
            }

        debut = time.perf_counter()
        couches = []
        for i in range(len(nominal)):
            if time.perf_counter() - debut > budget_s:
                break
            for signe in (+1.0, -1.0):
                e = nominal.copy()
                e[i] *= 1.0 + signe * step_pct / 100.0
                couches.append({"layer": i, "thickness_nm": float(nominal[i]), "sign": signe, **ligne(e)})
        out["per_layer"] = couches
        out["per_layer_complete"] = len(couches) == 2 * len(nominal)

        rng = np.random.default_rng(20261113)
        globales = []
        for k in range(8):
            if time.perf_counter() - debut > 1.25 * budget_s:
                break
            e = nominal * (1.0 + 0.005 * rng.standard_normal(len(nominal)))
            globales.append({"draw": k, **ligne(e)})
        out["global_sigma_0p5pct"] = globales
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Sonde co-conception : sensibilite du depot au design, a plan fige.")
    ap.add_argument("--config", type=Path, default=ROOT / "example" / "example_strat" / "JSON-strat-example-fast.json")
    ap.add_argument("--runs", type=int, default=300, help="tirages par evaluation (defaut 300, comme la recherche locale)")
    ap.add_argument("--budget-s", type=float, default=600.0, help="temps accorde aux retouches couche par couche")
    ap.add_argument("--step-pct", type=float, default=1.0, help="retouche d'une couche, en %% de son epaisseur")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if not a.config.is_file():
        print(f"🔴 fichier introuvable : {a.config}")
        return 2
    os.environ["CERTUS_DESIGN_JSON"] = str(a.config)

    import bench_examples as be  # pose la plateforme offscreen ; apres CERTUS_DESIGN_JSON
    from _artefact import ecrire_json

    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    import certus.workers.certus_strat_workers_local_search as ls

    mesure: dict = {}
    d_origine = ls.run_local_search

    def intercepte(rows, pre_calc_data, params, shared_clues_info, ranker):
        sortie = d_origine(rows, pre_calc_data, params, shared_clues_info, ranker)
        try:
            mesure.update(_mesurer(sortie, pre_calc_data, params, shared_clues_info, a.runs, a.budget_s, a.step_pct))
        except Exception as exc:  # la sonde ne doit pas casser le run qu'elle observe ; l'echec est DIT plus bas
            mesure["error"] = f"{type(exc).__name__}: {exc}"
            mesure["traceback"] = traceback.format_exc()
        return sortie

    ls.run_local_search = intercepte
    setup, run, val = be.run_strat()
    print(f"STRAT : setup {setup:.1f} s, run {run:.1f} s, RESULT={val}")
    if not mesure:
        print("🔴 la recherche locale n'a pas ete appelee (strat_local_search coupe ?) : RIEN n'est mesure.")
        return 1
    if "error" in mesure:
        print(f"🔴 la sonde a echoue : {mesure['error']}\n{mesure.get('traceback', '')}")
        return 1
    mesure.update({"config": a.config.name, "strat_run_s": round(run, 1), "strat_result": val})
    b = mesure["baseline"]
    print(f"design {mesure['layers']} couches · plan {mesure['plan_blocks']} blocs · cibles dans le fichier : {mesure['has_targets']}")
    print(f"evaluation : fabrique {b['factory_s']} s + {b['evaluate_s']} s ({a.runs} tirages) · "
          f"controle meme graine : delta = {b['same_seed_delta']:.3e} (attendu 0)")
    print(f"nominal : rmse {b['rmse']:.6g} · arrets {b['stops_all_levels']}")
    lignes = [x for x in mesure["per_layer"] if x["z"] is not None]
    if lignes:
        nets = [x for x in lignes if abs(x["z"]) >= 3.0]
        meilleur = min(lignes, key=lambda x: x["rel"])
        pire = max(lignes, key=lambda x: x["rel"])
        print(f"couche par couche (+-{a.step_pct:g} %) : {len(lignes)} retouches, {len(nets)} a |z| >= 3 · "
              f"complet : {mesure['per_layer_complete']}")
        print(f"  meilleure : couche {meilleur['layer'] + 1} ({meilleur['sign']:+.0f}) rmse^2 {100 * meilleur['rel']:+.1f} % "
              f"(z {meilleur['z']:+.1f}, spectre nominal deplace de {meilleur['nominal_shift_rms']:.2e})")
        print(f"  pire      : couche {pire['layer'] + 1} ({pire['sign']:+.0f}) rmse^2 {100 * pire['rel']:+.1f} % (z {pire['z']:+.1f})")
    for g in mesure["global_sigma_0p5pct"]:
        if g["rel"] is not None:
            print(f"  globale {g['draw']} : rmse^2 {100 * g['rel']:+.1f} % (z {g['z'] if g['z'] is None else round(g['z'], 1)}, "
                  f"arrets {g['stops_all_levels']}, spectre nominal deplace de {g['nominal_shift_rms']:.2e})")
    if a.out:
        ecrit = ecrire_json(a.out.resolve(), mesure, racine=ROOT)
        print(f"consigne dans {ecrit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
