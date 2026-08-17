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
    # 🔑 LA SERIE D'ECHELLE DU RANDOM75 -- la seule EXPERIENCE CONTROLEE du projet.
    # 75 couches, structure, materiaux, substrat et grille IDENTIQUES : seule l'epaisseur
    # optique varie. Elle est donc le seul endroit ou l'issue varie CONTINUMENT avec une
    # variable controlee, et c'est ce qui en fait le jeu de calibration d'un predicteur.
    #
    #   facteur  epaisseur  QWOT         < 1 QWOT  verdict   deposables  crash_min  SEEL
    #   x0,5      4,99 um   0,25 - 1,24    59      ECHOUE       0/375      48 %      -
    #   x1        9,99 um   ~0,50 - 2,48    -      passe      241/662       0 %    0,272
    #   x1,5     14,98 um   0,76 - 3,72     3      limite       1/704       0 %    0,63
    #   x2       19,98 um   1,01 - 4,96     0      ECHOUE       0/404     100 %      -
    #
    # Echec -> succes -> limite -> echec a nombre de couches et structure CONSTANTS. Donc ni
    # la longueur ni la structure ne gouvernent : c'est l'epaisseur optique par couche,
    # autrement dit COMBIEN DE POINTS TOURNANTS chaque couche traverse. Mecanisme a deux
    # bords, exactement ce que §27 annoncait sans l'avoir mesure :
    #   trop mince -> la couche ne complete pas un quart d'onde -> PAS d'extremum, pas d'ancre
    #   trop epais -> plusieurs extrema par couche -> le comptage decroche
    # Les deux echecs portent des crash_min DIFFERENTS (48 % contre 100 %), donc probablement
    # deux causes differentes. `margin_by_layer` est ventile par cause : c'est ce qui
    # confirmera -- ou refutera -- le mecanisme a deux bords.
    #
    # ⚠️ x1,5 rend 1 deposable sur 704. C'est le regime marginal ou §24-46 a mesure que la
    # GRAINE retourne le verdict (0/452 -> 70/521). Deux graines au moins sur les points
    # marginaux avant toute conclusion.
    "r75x0.5": ("reports/serie_echelle_r75/cfg_x0.5.json", 75),
    "r75x1.5": ("reports/serie_echelle_r75/cfg_x1.5.json", 75),
    "r75x2": ("reports/serie_echelle_r75/cfg_x2.json", 75),
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


def mesurer(nom: str, mode: str, cherche_fente: bool = False) -> dict:
    """Un run complet, et `cherche_fente` est le parametre qui manquait.

    🔴 DEFAUT TROUVE LE 2026-08-17. `mesurer()` de campagne_intervalles.py force
    `search_resolution: False` et pinne 2 nm, et mes sondes en avaient herite. Or 👤 a pose le
    2026-08-12 que « la fente est systematiquement cherchee, c'est un PREREQUIS », et
    certus_strat_robustness.py:868 designe explicitement `search_resolution: false` comme
    « the historical path ». Le 99c porte d'ailleurs `search_resolution = 1` dans sa config.

    Donc toute la campagne des intervalles ET mes 751 strategies ont tourne dans le regime que
    👤 avait ecarte : une machine ou l'operateur n'a pas le droit de toucher a la fente.

    📏 Mesure du 2026-08-12 citee dans le meme docstring : la regle `slit <= res_limit` rejette
    **14 % des paires (couche, lambda) a 2 nm contre 2 % a 1 nm** -- facteur 7. Et l'effet
    interessant n'est pas le choix a quatre valeurs, c'est que « la fente change QUELLES
    LONGUEURS D'ONDE SONT BONNES ».

    ⚠️ Le defaut reste `False` pour que les runs anterieurs restent comparables : changer le
    defaut casserait la comparaison avec les 751 strategies deja consignees.
    """
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
        "monochromator_resolution_nm": 2.0, "search_resolution": bool(cherche_fente),
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
            # 🔑 La marge sur la trajectoire ACCUMULEE, en unites de A -- la seule grandeur
            # du projet validee comme predicteur de plantage depuis le signal (§24-41).
            # Sparse : une couche absente a une marge >= 5 A, donc sereine.
            "margin_by_layer": s.get("margin_by_layer") or {},
            "critical_layer": s.get("critical_layer") or {},
        })
    return {"verdict": "OK", "n_strats": len(lignes), "strategies": lignes}


def mur(lignes: list[dict]) -> None:
    """Existe-t-il une couche qu'AUCUNE strategie ne parvient a rendre sereine ?

    Une couche absente du profil sparse d'une strategie a une marge >= 5 A : cette strategie
    la rend sereine, donc la couche n'est pas un mur. Un mur est une couche CONTRAINTE PAR
    TOUTES les strategies, dont la MEILLEURE marge sur l'ensemble reste basse. C'est la forme
    d'une condition necessaire violee : toute strategie doit deposer cette couche.
    """
    n = len(lignes)
    par_cause: dict[str, dict[int, list[float]]] = {}
    for r in lignes:
        for cause, hits in (r["margin_by_layer"] or {}).items():
            d = par_cause.setdefault(cause, {})
            for k, v in hits.items():
                d.setdefault(int(k), []).append(float(v))

    if not par_cause:
        print("\n  ⚠️ aucun profil de marge remonte -- rien a conclure (champ absent ?)")
        return

    for cause, d in sorted(par_cause.items()):
        partout = {i: v for i, v in d.items() if len(v) == n}
        print(f"\n  cause « {cause} » : {len(d)} couches contraintes au moins une fois, "
              f"{len(partout)} contraintes par les {n} strategies")
        if not partout:
            print("    🟢 aucune couche contrainte partout : pas de mur pour cette cause.")
            continue
        classe = sorted(partout.items(), key=lambda kv: max(kv[1]))
        print(f"    {'couche':>7} {'MEILLEURE marge':>16} {'pire':>8} {'mediane':>9}")
        for i, vs in classe[:12]:
            vs_tri = sorted(vs)
            print(f"    {i:>7} {max(vs):>15.3f}A {min(vs):>7.3f}A "
                  f"{vs_tri[len(vs_tri) // 2]:>8.3f}A")
        pire = classe[0]
        print(f"    🔴 MUR CANDIDAT : couche {pire[0]} -- meilleure marge {max(pire[1]):.3f} A "
              f"sur les {n} strategies.")
        print("       Aucune strategie ne la rend sereine, et toutes doivent la deposer.")

    crit: dict[str, int] = {}
    for r in lignes:
        cl = r["critical_layer"] or {}
        k = f"couche {cl.get('layer')} / {cl.get('cause')}"
        crit[k] = crit.get(k, 0) + 1
    print(f"\n  couche CRITIQUE la plus fréquente sur {n} strategies :")
    for k, c in sorted(crit.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    {c:>5} fois ({100 * c / n:>5.1f} %)  {k}")


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
    fente = bool(int(sys.argv[3])) if len(sys.argv) > 3 else False
    if nom not in COMPOSANTS:
        print(f"composant inconnu : {nom}. Choix : {', '.join(COMPOSANTS)}")
        return 2

    print(f"composant {nom} | mode {mode} | graine {SEED} | machine {_machine()}")
    r = mesurer(nom, mode, fente)
    r.update({"composant": nom, "mode": mode, "seed": SEED, "instrument": _commit(),
              "machine": _machine(), "stamp": datetime.now().isoformat(timespec="seconds")})

    if r["verdict"] != "OK":
        print(f"\n🔴 {r['verdict']} -- rien a analyser.")
        return 1

    print(f"\n{r['n_strats']} strategies evaluees.")
    synthese(r["strategies"])
    print("\n" + "=" * 74)
    print("Y A-T-IL UNE COUCHE QU'AUCUNE STRATEGIE NE REND SEREINE ?")
    print("=" * 74)
    mur(r["strategies"])

    suffixe = "_fente" if fente else ""
    out = ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{SEED:03d}{suffixe}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
