"""SERIE D'ECHELLE : le meme empilement aleatoire de 75 couches, a 4 echelles d'epaisseur.

    .venv\\Scripts\\python.exe scripts\\serie_echelle_r75.py --facteur 0.5
    .venv\\Scripts\\python.exe scripts\\serie_echelle_r75.py --etat

👤 2026-08-15 : *« je te propose de tester 2 75c supplementaires. L'un avec toutes les
epaisseurs x2, l'autre avec toutes les epaisseurs /2. Histoire de comprendre les choses... »*
puis *« voire meme aussi avec un facteur 1.5 »*.

🔑 CE QUE CETTE SERIE ISOLE, ET C'EST SA RAISON D'ETRE. On garde CONSTANTS le nombre de
couches (75), l'absence de structure, le motif relatif des epaisseurs et la graine. On ne fait
varier QU'UNE chose : l'echelle. C'est donc le seul dispositif du projet qui separe
l'EPAISSEUR OPTIQUE du NOMBRE DE COUCHES -- deux grandeurs que tous les autres composants font
varier ensemble.

    facteur   epaisseur totale   couche la plus fine   ce que ca teste
    x0.5           5.0 um              17.2 nm         des couches tres minces
    x1.0 (ref)     9.99 um             34.4 nm         MESURE : 0 % de plantage, SEEL 0,272 nm
    x1.5          14.98 um             51.6 nm         entre les deux
    x2.0          19.98 um             68.8 nm         PLUS epais que le 99c (9,10 um)

🔴🔴 UNE PREDICTION FAUSSE A ETE ECRITE ICI LE 2026-08-15 ET ELLE EST CONSERVEE COMME GARDE-FOU.

Elle disait : *« diviser par deux met des couches sous le quart d'onde, certaines ne traversent
AUCUN extremum et n'offrent aucun point d'arret optique ; donc x0.5 est le plus dur »*, et
comptait **59 couches sur 75 sous 1 QWOT** comme si c'etait un compte de couches muettes.

👤 a corrige : *« le TP c'est lorsque l'admittance devient reelle, et cela n'a rien a voir avec
une couche QWOT »*. **Mesure** (`scripts/probe_turning_points.py`) :

    comptage NAIF  « couches sous 1 QWOT a lambda_0 »   :  59 / 75
    comptage JUSTE « couches sans AUCUN turning point » :   1 / 75      <- facteur 59

Le x0.5 offre en fait un point d'arret sur **49 des 61** lambda candidates par couche
(mediane). L'argument etait faux, donc la prediction qu'il portait ne vaut rien.
🔑 Voir `docs/QWOT_ET_TURNING_POINT.md` avant d'ecrire quoi que ce soit sur ce sujet.

**Il n'y a donc PLUS de prediction engagee sur cette serie**, et c'est preferable a une
prediction fondee sur un raisonnement refute. Ce que la serie mesure reste net : a nombre de
couches, structure et graine CONSTANTS, la faisabilite depend-elle de l'echelle des epaisseurs ?

⚠️ CE SONT QUATRE FILTRES DIFFERENTS, pas quatre versions d'un meme filtre. Le spectre
nominal change avec l'echelle, donc chaque SEEL est mesure contre SA propre cible. C'est
legitime -- le SEEL est une erreur d'epaisseur equivalente par couche, pas un ecart spectral
absolu -- mais on ne compare PAS ces SEEL comme on comparerait deux strategies sur un meme
composant. Ce qui se compare d'un facteur a l'autre, c'est la FAISABILITE (plantage, nombre
de strategies deposables), et l'ordre de grandeur du SEEL.

Meme protocole que tout le reste du 2026-08-15 : fast, fente 2 nm, graine 42, verre NU.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SRC = ROOT / "example" / "example_strat" / "JSON-strat-random75.json"
CACHE = ROOT / "reports" / "serie_echelle_r75"
SEED = 42
CRASH_TOL = 0.05
FACTEURS = (0.5, 1.5, 2.0)

#: 🔴 Le x1.0 n'est PAS refait ici. Il est deja mesure, avec exactement ce protocole, et
#: refaire une mesure qu'on a deja c'est se donner deux chances d'obtenir le chiffre qui
#: arrange. Reference : reports/controle_random75/REFERENCE_0_75.json
REF_X1 = {"facteur": 1.0, "verdict": "DEPOSABLE", "n_strats": 662, "n_deposables": 241,
          "crash_min": 0.0, "rmse": 0.01855, "seel": 0.272,
          "source": "reports/controle_random75/REFERENCE_0_75.json"}


def config(facteur: float) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    d = json.loads(SRC.read_text(encoding="utf-8"))
    d["stack_multipliers"] = [float(m) * facteur for m in d["stack_multipliers"]]
    d["execution_mode"] = "fast"
    d["search_resolution"] = False
    d["monochromator_resolution_nm"] = 2.0
    d["_description"] = (f"random75 avec TOUTES les epaisseurs x{facteur}. "
                         f"Serie d'echelle du 2026-08-15 : isole l'epaisseur optique du "
                         f"nombre de couches. 👤 : « histoire de comprendre les choses ».")
    out = CACHE / f"cfg_x{facteur:g}.json"
    out.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def geometrie(facteur: float) -> dict:
    """Ce que l'echelle fait aux epaisseurs -- calcule, pas suppose."""
    d = json.loads(SRC.read_text(encoding="utf-8"))
    l0, nH, nL = float(d["l0"]), 2.3192, 1.4832
    th = [(float(m) * facteur * l0) / (4.0 * (nH if i % 2 == 0 else nL))
          for i, m in enumerate(d["stack_multipliers"])]
    qwot = [float(m) * facteur for m in d["stack_multipliers"]]
    return {"epaisseur_um": round(sum(th) / 1000.0, 2),
            "plus_fine_nm": round(min(th), 1), "plus_epaisse_nm": round(max(th), 1),
            "qwot_min": round(min(qwot), 3), "qwot_max": round(max(qwot), 3),
            # 🔑 une couche sous 1 QWOT ne traverse aucun extremum : aucun point d'arret.
            "couches_sous_1_qwot": int(sum(1 for q in qwot if q < 1.0))}


def mesurer(facteur: float) -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    t0 = time.perf_counter()
    row: dict = {"facteur": facteur, "verdict": "?", "n_strats": 0, "n_deposables": 0,
                 "crash_min": None, "rmse": None, "seel": None,
                 "geometrie": geometrie(facteur),
                 "stamp": datetime.now().isoformat(timespec="seconds")}
    try:
        cfg = config(facteur)
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText("fast")

        over = {"show_plots": False, "robustness_seed": SEED,
                "monochromator_resolution_nm": 2.0, "search_resolution": False}
        _c = app.collect_params
        vus = {"n": 0}

        def collect(*ar, **kw):
            p = _c(*ar, **kw)
            p.update(over)
            vus["n"] += 1
            return p

        app.collect_params = collect
        app.run_workflow(23)
        res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None
        row["run_s"] = round(time.perf_counter() - t0, 1)

        # 🔴 Erreur n.5 : le banc rend None sous charge et ca RESSEMBLE a un resultat.
        if vus["n"] < 2:
            row["verdict"] = "SURCHARGES_NON_APPLIQUEES"
            return row
        strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
        if not strats:
            row["verdict"] = "ECHEC_RESULT_NONE"
            return row

        taux = [float(s.get("crash_rate", 1.0)) for s in strats]
        ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
        ok.sort(key=lambda s: float(s.get("robustness_score", 1e18)))
        row.update({"n_strats": len(strats), "n_deposables": len(ok),
                    "crash_min": round(min(taux) * 100, 2),
                    "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE"})
        if ok:
            sc = float(ok[0].get("robustness_score", 0.0))
            row["rmse"] = sc
            row["seel"] = round(2.0 * math.sqrt(sc), 3) if sc > 0 else None
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:300]
        row["run_s"] = round(time.perf_counter() - t0, 1)
    return row


def etat() -> int:
    print("=" * 78)
    print("SERIE D'ECHELLE SUR LE 75 COUCHES ALEATOIRE")
    print("=" * 78)
    print("\n  facteur  epaisseur  + fine   <1 QWOT   verdict          deposables  plantage   SEEL")
    lignes = [REF_X1 | {"geometrie": geometrie(1.0), "run_s": 1327.3}]
    for f in FACTEURS:
        p = CACHE / f"x{f:g}.json"
        if p.exists():
            lignes.append(json.loads(p.read_text(encoding="utf-8")))
    for r in sorted(lignes, key=lambda x: x["facteur"]):
        g = r["geometrie"]
        s = f"{r['seel']:.3f}" if r.get("seel") else "  -  "
        tag = "(ref)" if r["facteur"] == 1.0 else "     "
        print(f"  x{r['facteur']:<4g}{tag} {g['epaisseur_um']:6.2f} um  {g['plus_fine_nm']:5.1f}   "
              f"{g['couches_sous_1_qwot']:5d}    {r['verdict']:<16s} {r['n_deposables']:5d}/"
              f"{r['n_strats']:<5d} {r['crash_min']:5.1f} %  {s}")
    manque = [f for f in FACTEURS if not (CACHE / f"x{f:g}.json").exists()]
    if manque:
        print(f"\n  en attente : {', '.join('x%g' % f for f in manque)}")
    else:
        print("\n  serie complete.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facteur", type=float, help="0.5, 1.5 ou 2.0")
    ap.add_argument("--etat", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    if args.etat or args.facteur is None:
        return etat()

    f = args.facteur
    dest = CACHE / f"x{f:g}.json"
    if dest.exists():
        sys.stderr.write(f"x{f:g} deja mesure, rien a faire.\n")
        return 0
    g = geometrie(f)
    sys.stderr.write(f"x{f:g} : {g['epaisseur_um']} um, la plus fine {g['plus_fine_nm']} nm, "
                     f"{g['couches_sous_1_qwot']} couches sous 1 QWOT\n")
    row = mesurer(f)
    dest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stderr.write(f"x{f:g} : {row['verdict']} | {row['n_deposables']}/{row['n_strats']} "
                     f"deposables | plantage min {row['crash_min']} % | SEEL {row.get('seel')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
