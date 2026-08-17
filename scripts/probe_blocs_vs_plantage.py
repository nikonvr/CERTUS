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

🔴 CETTE HYPOTHESE EST REFUTEE -- mesure du 2026-08-17, 99c complet, 751 strategies :

    n_blocs      1     4     6    19    99
    plantage  100 % 100 % 100 % 100 % 100 %      zone 4-7 : 184 offertes, 0 deposable

La zone favorable A ete exploree, un quart de l'offre, et ne donne rien. Et la strategie a
99 blocs -- qui se reancre a CHAQUE couche, donc compensation maximale possible -- plante
aussi a 100 %. Ni les blocs trop longs ni les blocs trop nombreux n'expliquent quoi que ce
soit : l'echec est INDEPENDANT de la structure en blocs.

Ce n'est pas non plus un defaut d'offre de la recherche : elle a propose de 1 a 19 blocs plus
une a 99. Le motif du defaut 24-37 ne s'applique pas ici.

⚠️ Le 99c est toutefois une CONFIGURATION SINGULIERE pour POEM (tout QWOT), et sa reponse
100 % PLATE ne discrimine rien. La sonde garde donc son interet sur la serie d'echelle, ou
l'issue varie.

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
    # 🔴 FIN / EPAIS SE DEFINIT EN EPAISSEUR OPTIQUE, JAMAIS MECANIQUE (👤, 2026-08-17). La
    # finesse spectrale est gouvernee par la phase accumulee, donc par n*d et non par d. La
    # mesure propre est la SOMME DES QWOT : sans unite, sans indice, sans l0.
    #
    #   facteur  Somme QWOT  ep.OPTIQUE  QWOT/couche  <1QWOT  verdict  deposables  crash  SEEL
    #   x0,5           57,4     9,09 um  0,25 - 1,24     59   ECHOUE      0/375    48 %     -
    #   x1            114,9    18,18 um  0,50 - 2,48      -   passe     241/662     0 %  0,272
    #   x1,5          172,3    27,27 um  0,76 - 3,72      3   limite      1/704     0 %  0,63
    #   x2            229,8    36,36 um  1,01 - 4,96      0   ECHOUE      0/404   100 %     -
    #
    # Sur CETTE serie optique et mecanique sont proportionnelles (rapport 1,82, l'indice moyen
    # effectif), donc l'ordre est inchange -- mais une conclusion libellee en micrometres
    # mecaniques ne se generaliserait PAS a d'autres materiaux.
    #
    # Echec -> succes -> limite -> echec a nombre de couches et structure CONSTANTS. Donc ni
    # le nombre de couches ni la structure ne gouvernent. Reste l'epaisseur optique, et il faut
    # distinguer DEUX grandeurs :
    #   Somme QWOT (total)  -> l'espacement des oscillations spectrales, donc la RESOLUTION
    #                          SPECTRALE exigee du monochromateur
    #   QWOT par couche     -> le nombre de points tournants traverses pendant la croissance
    #
    # 🔴 ET NE PAS DEDUIRE "sous 1 QWOT donc pas de point tournant" -- c'est le comptage NAIF
    # que §14 designe comme l'erreur la plus couteuse du projet, et je l'ai commise le
    # 2026-08-17. Le depart d'un point tournant est decale d'une phase 1/2 arctan(R/Q) fixee par
    # l'empilement du dessous : une couche sous 1 QWOT peut parfaitement traverser un extremum.
    # Mesure sur x0,5 : UNE couche sur 75 sans lambda admissible, pas 59. Le taux de 48 % de
    # x0,5 n'est donc PAS explique par une absence d'ancre.
    #
    # Les deux echecs portent des crash_min differents (48 % contre 100 %), mais leur cause
    # DOMINANTE est la meme -- CRASH_LEVEL_UNREACHABLE des deux cotes (mesure 2026-08-17).
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


def mesurer(nom: str, mode: str, cherche_fente: bool = False, min_tp: int = 0,
            resolution_nm: float = 2.0, elargi: bool = False, seed: int = SEED) -> dict:
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
        # 🔑 La graine est exposee depuis le 2026-08-17 : §24-46 a mesure qu'un verdict
        # marginal BASCULE avec elle (0/452 -> 70/521 sur le meme intervalle). Une cellule
        # marginale jugee sur une seule graine n'etablit rien.
        "show_plots": False, "robustness_seed": int(seed),
        # 🔑 LA RESOLUTION DE BASE DU RUN. Le code n'ecarte JAMAIS la fente propre du run
        # ("THE RUN'S OWN SLIT IS NEVER SKIPPED"), donc la fixer ici est le seul moyen de
        # faire evaluer TOUTES les strategies a cette largeur. Les variantes, elles, sont
        # filtrees par la courbure -- c'est ainsi que 1 nm n'avait JAMAIS ete essaye sur x2.
        #
        # 📏 Le biais de fente va en B^2 (bias = T'' . B^2/24), le bruit suit
        # RESOLUTION_NOISE_FACTOR : passer de 2 a 1 nm divise le biais par 4 et multiplie le
        # bruit par 2. Sur un empilement a fort swing dont l'echec est LEVEL_UNREACHABLE,
        # l'arbitrage penche donc vers la fente fine -- l'inverse de x0,5.
        #
        # 🔒 Et la comparaison est propre par construction : le facteur de bruit multiplie
        # l'ECHANTILLON, jamais la graine (contrainte C2, certus_strat_robustness.py:192).
        # Deux resolutions voient donc les MEMES tirages, a l'amplitude pres.
        "monochromator_resolution_nm": float(resolution_nm),
        "search_resolution": bool(cherche_fente),
        "noise_layer_offset": 0, "noise_total_layers": n_layers,
        # 🔒 EXIGENCE D'UN POINT TOURNANT -- inactif a 0, donc chemin d'avant mot pour mot.
        # Accepte un ENTIER : le minimum de points tournants exige par couche. Un reglage
        # destructif (999) doit vider la selection -- c'est la seule facon de prouver SANS
        # CIRCULARITE que le parametre atteint le calcul, comme machine_sampling_dd ne le
        # faisait pas. La ligne de log [TP] compte les rejets par couche.
        "require_turning_point": int(min_tp),
        "execution_mode": mode,
    }
    if elargi:
        # 🔑 PROFIL D'EXPLORATION ELARGIE -- il elargit ce qui est GENERE et RETENU, jamais
        # la profondeur d'EVALUATION. `robustness_num_runs` et `n_screen_runs` restent
        # intacts : ce sont des profondeurs de notation, et les changer rendrait les taux de
        # plantage incomparables avec la grille. §19 interdit en outre de descendre
        # n_screen_runs.
        over.update({
            "execution_mode": "deep",          # dp_top_k 20 -> 100
            "mining_candidates_limit": 12000,  # x4
            "phase_a_keep_limit": 200,         # x4
            "top_k_parents": 80,               # x4
            "max_fusions_per_parent": 15,      # x3
            "k_keep_survivors": 40,            # x4
            "screening_keep_top_k": 20,        # x4
            # 🔴 SANS CETTE LIGNE L'ELARGISSEMENT SERAIT TRONQUE EN SILENCE. Le defaut vaut
            # 300 s : une phase qui deborde est coupee, et le run rend un resultat plausible
            # sur une exploration amputee. C'est le mode de defaillance que ce depot paie
            # depuis le debut.
            "strategy_phase_timeout": 3600,
        })

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
            # 🔑 LA FENTE QUE CETTE STRATEGIE A CHOISIE, et son prix en bruit. Sans ce champ on
            # saurait SI la recherche de fente aide, jamais A QUELLE LARGEUR -- soit la moitie
            # de la reponse a la question de 👤. Le bonus/malus est documente : /1,5 a 5 nm,
            # x1 a 2 nm, x2 a 1 nm, x5 a 0,5 nm. Une strategie qui descend a 1 nm PAIE le x2 ;
            # si elle gagne quand meme, c'est que la finesse spectrale valait le bruit.
            "resolution_nm": s.get("monochromator_resolution_nm"),
            "resolution_noise_factor": s.get("resolution_noise_factor"),
        })
    return {"verdict": "OK", "n_strats": len(lignes), "strategies": lignes}


def par_fente(lignes: list[dict]) -> None:
    """La fente change-t-elle l'issue, et a quelle largeur ?

    👤 2026-08-17 : « un filtre trop epais a des pics en transmission et peut-etre que le filtre
    serait monitorable en resolution 1 nm et pas 2 nm ». Cette ventilation est la reponse
    directe. Le prix est documente : /1,5 a 5 nm, x1 a 2 nm, x2 a 1 nm, x5 a 0,5 nm -- descendre
    en largeur ACHETE de la finesse spectrale et PAIE du bruit.
    """
    par: dict[float, list[dict]] = defaultdict(list)
    for r in lignes:
        par[float(r.get("resolution_nm") or 0.0)].append(r)
    if len(par) <= 1:
        seule = next(iter(par), 0.0)
        print(f"\n  une seule fente presente : {seule} nm -- la recherche de fente est INACTIVE.")
        return
    print(f"\n  {'fente nm':>9} {'x bruit':>8} {'OFFERTES':>9} {'plantage moy':>13} "
          f"{'plantage min':>13} {'deposables':>11} {'meilleur score':>15}")
    print("  " + "-" * 82)
    for f in sorted(par):
        g = par[f]
        tx = [r["crash_rate"] for r in g]
        dep = [r for r in g if r["crash_rate"] < CRASH_TOL]
        sc = [r["score"] for r in dep] or [float("nan")]
        fac = g[0].get("resolution_noise_factor")
        print(f"  {f:>9.2f} {(fac if fac is not None else float('nan')):>8.2f} {len(g):>9} "
              f"{100 * sum(tx) / len(tx):>12.2f}% {100 * min(tx):>12.2f}% {len(dep):>11} "
              f"{min(sc):>15.5f}")
    gagnantes = [r for r in lignes if r["crash_rate"] < CRASH_TOL]
    if gagnantes:
        f_gag: dict[float, int] = defaultdict(int)
        for r in gagnantes:
            f_gag[float(r.get("resolution_nm") or 0.0)] += 1
        print(f"\n  🔑 les {len(gagnantes)} strategies DEPOSABLES choisissent :")
        for f, c in sorted(f_gag.items()):
            print(f"       {c:>5} a {f} nm")
    else:
        print("\n  aucune strategie deposable, quelle que soit la fente.")


def contraintes_communes(lignes: list[dict]) -> None:
    """Existe-t-il une couche dont la marge reste basse pour TOUTES les strategies evaluees ?

    Une couche absente du profil sparse d'une strategie y a une marge >= 5 A : cette strategie
    la laisse hors contrainte, et la couche ne peut donc pas etre commune a toutes. Ce qu'on
    cherche est une couche CONTRAINTE PAR TOUTES les strategies, dont la plus grande marge sur
    l'ensemble reste basse. C'est la forme d'une condition necessaire violee : toute strategie
    doit deposer cette couche, donc aucune ne la contourne.

    🔒 VOCABULAIRE (👤, 2026-08-17). Cette notion n'a PAS de nom court : `critical_layer` est
    deja pris par le code pour autre chose -- la couche qui cede en premier POUR UNE strategie
    donnee. On ecrit donc la description en toutes lettres, « une couche dont la marge reste
    sous le seuil pour toutes les strategies evaluees », plutot que d'inventer un terme.
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
            print("    🟢 aucune couche contrainte par toutes les strategies, pour cette cause.")
            continue
        classe = sorted(partout.items(), key=lambda kv: max(kv[1]))
        print(f"    {'couche':>7} {'MEILLEURE marge':>16} {'pire':>8} {'mediane':>9}")
        for i, vs in classe[:12]:
            vs_tri = sorted(vs)
            print(f"    {i:>7} {max(vs):>15.3f}A {min(vs):>7.3f}A "
                  f"{vs_tri[len(vs_tri) // 2]:>8.3f}A")
        pire = classe[0]
        print(f"    🔴 CONTRAINTE COMMUNE AUX {n} STRATEGIES : couche {pire[0]}, plus grande "
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
    min_tp = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    res_nm = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
    elargi = bool(int(sys.argv[6])) if len(sys.argv) > 6 else False
    graine = int(sys.argv[7]) if len(sys.argv) > 7 else SEED
    if nom not in COMPOSANTS:
        print(f"composant inconnu : {nom}. Choix : {', '.join(COMPOSANTS)}")
        return 2

    print(f"composant {nom} | mode {mode} | graine {graine} | require_turning_point={min_tp} "
          f"| fente {res_nm:g} nm | elargi {int(elargi)} | machine {_machine()}")
    r = mesurer(nom, mode, fente, min_tp, res_nm, elargi, graine)
    r.update({"composant": nom, "mode": mode, "seed": graine, "instrument": _commit(),
              "machine": _machine(), "stamp": datetime.now().isoformat(timespec="seconds")})

    if r["verdict"] != "OK":
        print(f"\n🔴 {r['verdict']} -- rien a analyser.")
        return 1

    print(f"\n{r['n_strats']} strategies evaluees.")
    synthese(r["strategies"])
    print("\n" + "=" * 74)
    print("LA FENTE CHANGE-T-ELLE L'ISSUE, ET A QUELLE LARGEUR ?")
    print("=" * 74)
    par_fente(r["strategies"])
    print("\n" + "=" * 74)
    print("UNE COUCHE RESTE-T-ELLE CONTRAINTE POUR TOUTES LES STRATEGIES ?")
    print("=" * 74)
    contraintes_communes(r["strategies"])

    suffixe = (("_fente" if fente else "") + (f"_tp{min_tp}" if min_tp else "")
                + ("" if res_nm == 2.0 else f"_res{res_nm:g}")
                + ("_large" if elargi else ""))
    out = ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{graine:03d}{suffixe}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
