"""LE NOMBRE DE BLOCS PREDIT-IL LE PLANTAGE ? -- une campagne, des centaines de points.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_blocs_vs_plantage.py [composant] [mode]

👤 2026-08-17 : *« ce qui est important, c'est de trouver un chemin avec des blocs de longueurs
d'onde pour monitorer l'ensemble et en bonus avec compensation d'erreur »*.

🔴 CE QUE LES MESURES DU JOUR ONT DEJA FERME. La matrice statique (couche x lambda) ne predit
RIEN de la monitorabilite a un temoin, dans aucune de ses deux formulations :

    couches sans aucune lambda utilisable   0/99   0/75   0/48   0/35
    blocs MINIMUM pour couvrir                 1      2      1      1
    lambda communes du bloc unique            26      -     64     28
    plantage reel                           100 %    0 %    0 %    0 %

Le 99c se couvre en UN bloc avec 26 lambda au choix -- le plus facile des quatre par cette
mesure -- et c'est le seul qui plante. Trouver un CHEMIN n'est donc pas le probleme : il
existe trivialement partout. Ce qui manque est la COMPENSATION, que 👤 appelait un bonus et
qui est en realite tout le sujet.

## L'hypothese que cette sonde teste, et le mecanisme qui la rend plausible

Deux constats du depot, jamais rapproches :

    §24-21   MAX_LOOKBACK = 4 -- POEM ne rejoue que les 4 DERNIERES couches d'un bloc, quelle
             que soit sa longueur. La valeur d'un bloc long est plafonnee par construction.
    §24-44   zone favorable 4 a 7 blocs, optimum a 6. Sous 3 blocs : aveuglement spectral.
             Au-dela de 10 : perte de memoire.

D'ou la tension : un bloc LONG maximise la couverture en lambda et DETRUIT la compensation --
il ne se reancre jamais. Un bloc COURT compense bien mais perd ses ancres a chaque frontiere.
La couverture minimale du 99c, un seul bloc de 99 couches, serait donc le pire cas possible :
95 couches sans reancrage avec un lookback de 4.

    HYPOTHESE : a composant fixe, le taux de plantage decroit quand le nombre de blocs
    augmente, jusqu'a la zone 4-7, puis remonte.

## 🔑 CE QUE LA SONDE SERT A DECIDER -- l'esprit de STRAT, pas de la taxonomie

👤 2026-08-17 : *« attention de rester compatible avec l'esprit de strat.py : trouver la
meilleure strategie »*. §15 le grave : la meilleure strategie maximise P(le filtre sorti est
conforme), et un depot qui plante et un filtre hors spec sont le MEME echec.

La question n'est donc pas *« le nombre de blocs predit-il le plantage »* -- ca serait de la
taxonomie. C'est :

    LA RECHERCHE A-T-ELLE JAMAIS OFFERT une strategie dans la zone favorable ?

Si les ~487 strategies du 99c sont toutes a 1-3 blocs, le 100 % de plantage ne dit pas que le
composant est inmonitorable : il dit que la recherche n'a jamais propose ce qui aurait marche.
C'est exactement le motif du defaut 24-37 -- *la strategie n'est plus choisie, elle est
forcee*, et le resultat final n'en porte aucune trace. La colonne `strats` de la synthese est
donc la plus importante du tableau : elle mesure l'OFFRE, pas la performance.

⚠️ ET SI L'EFFET EXISTE, IL ENTRE COMME COUT, JAMAIS COMME COUPERET. §22 : les heuristiques de
la litterature sont des diagnostics, pas des filtres. §24-28 l'a mesure : chaque generateur
gagne dans au moins un regime et aucun dans tous -- la regle « celui-la ne gagne jamais »
aurait jete la gagnante dans 4 configurations sur 8. Un seuil sur le nombre de blocs
interdirait des strategies qui marchent.

## Pourquoi cette sonde plutot qu'un mecanisme de forcage

Forcer des couvertures a 4, 6, 8, 10 blocs demanderait d'injecter une structure dans le
pipeline. Inutile : un run genere DEJA des centaines de strategies de longueurs de blocs
variees, chacune avec son `crash_rate`. On lit la correlation au lieu de la fabriquer.

🔑 ET C'EST UNE COMPARAISON A GRAINE FIXEE. Le constat §24-46 du jour -- un verdict
d'intervalle n'est pas determine par une graine -- interdit de comparer des VALEURS ABSOLUES
entre graines. Il n'interdit pas de comparer des strategies ENTRE ELLES sous une meme
realisation de bruit, ce qui est exactement ce qu'on fait ici.

⚠️ Ce que la sonde ne peut PAS dire : si l'effet survit d'un composant a l'autre. Le §22
rappelle qu'une marge portait un signal qui CHANGEAIT DE SIGNE d'un empilement a l'autre.
Lancer sur le 99c d'abord, puis sur le 75c, avant toute conclusion generale.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    "99c": ("example/example_strat/JSON-strat-bandpass-5cav-99c.json", 99),
    "75c": ("example/example_strat/JSON-strat-random75.json", 75),
    "48c": ("example/example_strat/JSON-strat-example.json", 48),
    "35c": ("example/example_strat/JSON-strat-bandpass-3cav.json", 35),
}
SEED = 42
CRASH_TOL = 0.05


def _machine() -> str:
    import platform
    cpu = " ".join((platform.processor() or platform.machine() or "?").split())
    return f"{cpu} | {os.cpu_count()} threads"


def _commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def mesurer(nom: str, mode: str) -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    cfg, n_layers = COMPOSANTS[nom]
    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText(mode)

    over = {
        "show_plots": False, "robustness_seed": SEED,
        "monochromator_resolution_nm": 2.0, "search_resolution": False,
        "noise_layer_offset": 0, "noise_total_layers": n_layers,
        "execution_mode": mode,
    }
    _c = app.collect_params
    vus = {"n": 0}

    def collect(*a, **k):
        p = _c(*a, **k)
        p.update(over)
        vus["n"] += 1
        return p

    app.collect_params = collect
    app.run_workflow(23)
    res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None

    if vus["n"] < 2:
        return {"verdict": "SURCHARGES_NON_APPLIQUEES"}
    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    if not strats:
        return {"verdict": "ECHEC_RESULT_NONE"}

    lignes = []
    for s in strats:
        st = s.get("strategy", {}) or {}
        blocs = st.get("blocks", []) or []
        lignes.append({
            "id": st.get("id", s.get("id")),
            "origine": st.get("origin", st.get("origin_name")),
            "n_blocs": int(st.get("n_blocks", len(blocs))),
            "crash_rate": float(s.get("crash_rate", 1.0)),
            "score": float(s.get("robustness_score", 0.0) or 0.0),
            "lambdas": [b.get("wl") if isinstance(b, dict) else None for b in blocs][:24],
        })
    return {"verdict": "OK", "n_strats": len(lignes), "strategies": lignes}


def synthese(lignes: list[dict]) -> None:
    par = defaultdict(list)
    for r in lignes:
        par[r["n_blocs"]].append(r)
    print(f"\n{'n_blocs':>8} {'OFFERTES':>9} {'plantage moy':>13} {'plantage min':>13} "
          f"{'deposables':>11} {'meilleur score':>15}")
    print("-" * 74)
    for k in sorted(par):
        g = par[k]
        tx = [r["crash_rate"] for r in g]
        dep = [r for r in g if r["crash_rate"] < CRASH_TOL]
        sc = [r["score"] for r in dep] or [float("nan")]
        print(f"{k:>8} {len(g):>9} {100 * sum(tx) / len(tx):>12.2f}% {100 * min(tx):>12.2f}% "
              f"{len(dep):>11} {min(sc):>15.5f}")

    # 🔑 La lecture qui decide : la zone favorable a-t-elle ete EXPLOREE ?
    zone = [k for k in par if 4 <= k <= 7]
    n_zone = sum(len(par[k]) for k in zone)
    print(f"\nzone favorable 4-7 blocs (§24-44) : {n_zone} strategies offertes "
          f"sur {len(lignes)} ({100 * n_zone / max(len(lignes), 1):.1f} %)")
    if n_zone == 0:
        print("  🔴 ZERO. Un plantage total ne dirait alors RIEN du composant : la recherche")
        print("     n'a jamais propose la zone favorable. Motif du defaut 24-37.")
    else:
        dep_zone = sum(1 for k in zone for r in par[k] if r["crash_rate"] < CRASH_TOL)
        print(f"  deposables dans la zone : {dep_zone} / {n_zone}")


def main() -> int:
    nom = sys.argv[1] if len(sys.argv) > 1 else "99c"
    mode = sys.argv[2] if len(sys.argv) > 2 else "premium"
    if nom not in COMPOSANTS:
        print(f"composant inconnu : {nom}. Choix : {', '.join(COMPOSANTS)}")
        return 2

    print(f"composant {nom} | mode {mode} | graine {SEED} | machine {_machine()}")
    r = mesurer(nom, mode)
    r.update({"composant": nom, "mode": mode, "seed": SEED, "instrument": _commit(),
              "machine": _machine(), "stamp": datetime.now().isoformat(timespec="seconds")})

    if r["verdict"] != "OK":
        print(f"\n🔴 {r['verdict']} -- rien a analyser.")
        return 1

    print(f"\n{r['n_strats']} strategies evaluees.")
    synthese(r["strategies"])

    out = ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{SEED:03d}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
