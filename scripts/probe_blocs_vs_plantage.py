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

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    "99c": ("example/example_strat/JSON-strat-bandpass-5cav-99c.json", 99),
    "75c": ("example/example_strat/JSON-strat-random75.json", 75),
    "48c": ("example/example_strat/JSON-strat-example.json", 48),
    "35c": ("example/example_strat/JSON-strat-bandpass-3cav.json", 35),
    # 🟢 LA VARIANTE LIVREE QUI FAIT PASSER r75x2 A LA FENTE NOMINALE DE 2 nm.
    #
    # 📏 Mesure du 2026-08-21 : 72 strategies deposables, meilleur SEEL 0,5697, plantage
    # 1,00 %, graine 42 -- la ou le meme composant a 2 nm rendait ZERO deposable sur 1617.
    # Elle ne differe du fichier de base que par la fente (2,0 au lieu de 1,0) et par
    # `injected_strategies`, qui verse des plans de surveillance connus dans la population.
    #
    # 🔴 ELLE EST UN COMPOSANT A PART, ET C'EST DELIBERE. Ecrire ces deux cles dans le
    # fichier de base aurait change SILENCIEUSEMENT toutes les mesures futures qui le citent
    # -- et le depot en compte beaucoup. Le fichier de base reste INTACT.
    "r75x2-2nm": ("example/example_strat/JSON-strat-random75-x2-fabricable-2nm.json", 75),
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
    # 🔑 AJOUTE LE 2026-08-18 pour LOCALISER la bascule. La grille du 17 au soir a mesure
    # que 1 nm degrade x1,5 (30 % contre 0 %) et AMELIORE x2 (38 % contre 100 %) : le signe
    # s'inverse donc entre 172,3 et 229,8 quarts d'onde. x1,75 vaut 201,1 -- le milieu.
    "r75x1.75": ("reports/serie_echelle_r75/cfg_x1.75.json", 75),
    "r75x2": ("reports/serie_echelle_r75/cfg_x2.json", 75),
}
SEED = 42
CRASH_TOL = 0.05

#: Coupures du balayage de queue (8e argument = 2). Bornees par la mesure du 2026-08-19 :
#: sur les 10 runs du x2 la couche critique dominante est la 32 a 2 nm et la 35 ailleurs, et
#: 59 a 74 % des couches critiques sont AVANT la couche 40 -- d'ou un balayage des la 28.
#: 📏 Mesure du 2026-08-19 : le SEEL s'AMELIORE quand la coupure recule (0,814 a
#: i=28, 0,689 a i=52). L'optimum est donc au-dela de 52 -- ce balayage cherche ou
#: il se retourne.
#: 📏 Optimum encadre le 2026-08-19 : SEEL 0,689 a i=52, 0,701 a 55, 0,735 a 58, et ECHEC
#: complet des 61. On resserre autour du point de retournement.
#: 🔴 SURCHARGEABLE PAR `CERTUS_TAIL_CUTS` -- ajoute le 2026-08-19 apres avoir ECRASE un
#: artefact. Les coupures etaient une constante de module : changer la liste et relancer
#: reproduisait le MEME nom de fichier, et la campagne 28-52 a ete perdue ainsi. Le suffixe
#: du nom porte deja `_tail{min}-{max}`, donc piloter les coupures par l'environnement suffit
#: a rendre les cellules d'un batch mutuellement non destructrices.
#:     set CERTUS_TAIL_CUTS=46,49,52,55,58,61,64
TAIL_CUTS = [int(_c) for _c in os.environ.get("CERTUS_TAIL_CUTS", "46,49,52,55").split(",")
             if _c.strip()]

#: 🔑 RATE CHIRURGICAL (8e argument = 4). Cibles MESUREES sur x2 a 2 nm : les couches 32, 39 et
#: 35 portent 73 % des couches critiques, et 100 % de leurs echecs sont « niveau d'arret hors
#: d'atteinte » -- de la derive accumulee, pas un defaut de signal. On franchit ces couches-la
#: en boucle ouverte et on laisse POEM se reancrer juste apres, ce que le noyau autorise
#: pleinement des lors que la couche suivante a ses deux points tournants (verifie le 19/08).
RATE_SETS = [
    [32],                        # la dominante seule -- 47 % des couches critiques
    [32, 35],
    [32, 35, 39],                # les trois dominantes -- 73 %
    [31, 32, 33],                # une fenetre courte autour de la dominante
    [34, 35, 36],
    [31, 32, 33, 34, 35, 36],    # la zone continue
    [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
]

#: PROFIL D'EXPLORATION ELARGIE -- il elargit ce qui est GENERE et RETENU, jamais la profondeur
#: d'EVALUATION. `robustness_num_runs` et `n_screen_runs` restent intacts : ce sont des
#: profondeurs de NOTATION, et les changer rendrait les taux de plantage incomparables avec les
#: cellules standard. §19 interdit en outre de descendre `n_screen_runs`.
#:
#: 📏 Les valeurs de depart sont celles de `JSON-strat-random75.json`, verifiees le 2026-08-17 :
#: 3000 / 50 / 20 / 5 / 10 / 5 / 300. Les sept noms sont lus par `certus_strat_workers.py` --
#: controle fait avant de lancer, parce que ce depot a trois precedents de parametre pose,
#: journalise, et lu par personne (`fast_auto_blocks`, `machine_sampling_dd`, `dp_yield_weight`).
ELARGISSEMENT = {
    "execution_mode": "deep",          # dp_top_k 20 -> 100
    "mining_candidates_limit": 12000,  # x4
    "phase_a_keep_limit": 200,         # x4
    "top_k_parents": 80,               # x4
    "max_fusions_per_parent": 15,      # x3
    "k_keep_survivors": 40,            # x4
    "screening_keep_top_k": 20,        # x4
    # 🔴🔴 CE PARAMETRE EST INERTE -- MESURE LE 2026-08-18, ET J'AVAIS ECRIT LE CONTRAIRE ICI.
    # Le commentaire precedent affirmait que sans lui « l'elargissement serait tronque en
    # silence ». C'est FAUX : `grep -rn strategy_phase_timeout certus/core certus/workers` rend
    # ZERO. Il est pose par collect_params, affiche dans un widget, enregistre dans les JSON, et
    # AUCUNE ligne de calcul ne le lit. Quatrieme cas du motif §24, apres fast_auto_blocks,
    # machine_sampling_dd et dp_yield_weight.
    #
    # 🔑 On le laisse quand meme, pour deux raisons : il est ecrit dans le bloc `config` de
    # l'artefact, donc il documente l'INTENTION du run ; et le jour ou il sera rebranche, les
    # runs elargis auront la bonne valeur. Mais il ne faut RIEN lui attribuer.
    #
    # ⚠️ Les vrais bornages sont ailleurs et CODES EN DUR : `timeout=30.0` passe a la DP
    # (certus_strat_ranking.py:410 -- lui aussi inerte, la fonction ne lit jamais son argument),
    # et `concurrent.futures.wait(futures, timeout=600)` (certus_strat_workers.py:1402), qui
    # n'ampute pas les resultats -- `shutdown(wait=True)` attend -- mais qui CESSE DE JOURNALISER
    # les exceptions au-dela de 600 s. Sur une cellule de 157 min, une erreur tardive est donc
    # muette.
    "strategy_phase_timeout": 10800,
}


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
            resolution_nm: float = 2.0, elargi: bool = False, seed: int = SEED,
            par_swing: int = 0) -> dict:
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
        # 🔑 RATE PAR BESOIN -- inactif par defaut, docs/CHANTIER_RATE.md.
        # Ajoute aux candidates Rate les couches dont le swing de croissance est
        # sous `dynamics_threshold`, EN PLUS des frontieres de bloc. 📏 Mesure du
        # 2026-08-19 : n'agit que sur le 75c (5 couches sur 75), inerte sur 35c,
        # 48c et 99c ou aucune couche n'est sous le seuil.
        # 🔴 par_swing == 3 exige AUSSI le contexte de swing : sans lui `swing_ctx` vaut None
        # et la regle d'exception est sautee EN SILENCE. C'est ce qui a fait qu'un run de
        # 56 min a rendu un doublon exact du run sans exception, le 2026-08-19.
        "rate_by_swing": par_swing in (1, 3, 5),
        "rate_tail_sweep": TAIL_CUTS if par_swing in (2, 3, 5) else [],
        "rate_layer_sets": RATE_SETS if par_swing == 4 else [],
        "rate_tail_keep_optical": 4 if par_swing == 3 else 0,
        "execution_mode": mode,
    }
    # 🔴 LE TRIPLET DE GRAINES DU CONSENSUS -- ajoute le 2026-08-19, et c'est le VERROU de
    # toute affirmation sur le classement.
    #
    # Mesure du jour : `robustness_seed` NE TOUCHE PAS le score. `_resolve_consensus_seeds`
    # (`certus_strat_consensus.py:111`) fait gagner la liste explicite, et `base_seed` n'est
    # consulte qu'en son absence. Les 4 composants portent `consensus_seed_list =
    # 41,42,43,44,45` tronquee a `consensus_num_seeds = 3`, donc TOUS les runs -- graine 42
    # comme graine 77 -- rescorent sur `[41,42,43]`. 📏 Verifie : les scores de deux graines
    # different de 3,2e-11, l'ordre de la gigue de recompilation.
    #
    # 🔑 CONSEQUENCE : la dispersion du SEEL n'a JAMAIS ete mesuree, et sans elle aucun
    # classement de coupures n'est defendable. Ce reglage est la seule facon de la sonder.
    #     set CERTUS_CONSENSUS_SEEDS=51,52,53
    _cs = os.environ.get("CERTUS_CONSENSUS_SEEDS", "").strip()
    if _cs:
        over["consensus_seed_list"] = _cs
    if elargi:
        over.update(ELARGISSEMENT)
    if int(elargi) >= 2:
        # 🔑 NIVEAU 2 -- le balayage de dp_top_k, 👤 2026-08-18 : « penses-tu qu'augmenter le
        # dp_top_k peut encore plus aider ? ». C'est le levier le plus EN AMONT : la DP k-best
        # est appelee PAR nombre de blocs et rend `top_k` groupements chacune, donc dp_top_k
        # multiplie directement ce qui entre en Phase B.
        #
        # 🔴 ET ON NE PEUT PAS REPONDRE SANS LE MESURER. La seule paire disponible -- fast k=20
        # contre premium k=40 sur x2 -- rend x1,61 d'offre pour x2 de k, donc SOUS-lineaire ; mais
        # elle est confondue, fast -> premium change six parametres. Le niveau 2 ne change QUE
        # dp_top_k par rapport au niveau 1, et se compare donc directement aux 254 deposables.
        #
        # ⚠️ Effet de bord connu, §24-45 : le bonus block-aware de Phase A agit en faisant
        # franchir la troncature dp_top_k aux lambda stables. Plus top_k est large, MOINS ce bonus
        # change quoi que ce soit. Elargir le faisceau desactive donc progressivement un mecanisme
        # -- ce qui n'est ni bon ni mauvais a priori, et n'a jamais ete mesure.
        over["dp_top_k"] = 200

    # 🔴 LES SURCHARGES GENERIQUES GAGNENT SUR TOUT LE RESTE, et c'est voulu : elles
    # sont l'instrument d'essai, le reste est le protocole de reference.
    _sur, _tag = _surcharges_env()
    if _sur:
        over.update(_sur)
        print(f"  surcharges [{_tag}] : {_sur}", flush=True)


    _c = app.collect_params
    vus = {"n": 0}
    # 🔴 §24-7 A NOUVEAU, ET SUR MA PROPRE SONDE. Le bloc `config` consignait les sept reglages
    # d'exploration et la fente, mais JAMAIS la profondeur Monte-Carlo. Or un `crash_min` ne se
    # lit qu'avec son N : 4,00 % vaut 2/50 en `fast` et 6/150 en `premium`, et c'est la
    # granularite minimale au-dessus de zero, pas une mesure. Le nom de fichier porte le mode,
    # d'ou la profondeur se DEDUIT par une table qui vit dans certus_strat_ui_state.py et qui
    # peut changer. Une deduction n'est pas une consignation : on enregistre la valeur resolue.
    profondeur: dict = {}

    def collect(*a, **k):
        p = _c(*a, **k)
        p.update(over)
        vus["n"] += 1
        for _k in ("robustness_num_runs", "n_screen_runs", "dp_top_k", "consensus_num_runs"):
            _v = p.get(_k)
            if _v is not None:
                profondeur[_k] = _v
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
            "id": st.get("strategy_id", st.get("id", s.get("id"))),
            "origine": st.get("origin", st.get("origin_name")),
            "n_blocs": int(st.get("n_blocks", len(blocs))),
            "crash_rate": float(s.get("crash_rate", 1.0)),
            "score": float(s.get("robustness_score", 0.0) or 0.0),
            # 🔴 LA CLE EST `wavelength`, PAS `wl` -- corrige le 2026-08-20, et l'erreur coutait
            # LE LIVRABLE. `_build_layer_wavelengths_from_strategy` (certus_strat_robustness.py:
            # 2855) lit `block["wavelength"]` : c'est le nom qui fait foi. Avec `wl`, le champ
            # sortait `[None, None, ...]` -- de la BONNE LONGUEUR, donc l'artefact avait l'air
            # complet. 📏 Trouve en repondant a 👤 « quelle est la meilleure strategie ? » : on
            # savait son SEEL, son plantage et son nombre de blocs, et on ne pouvait pas dire
            # A QUELLES LAMBDA surveiller. Tous les artefacts anterieurs sont muets la-dessus.
            # ⚠️ Plus de troncature a 24 : sur une strategie couche-par-couche elle coupait 51
            # blocs sur 75, donc rendait le plan inutilisable meme une fois la cle corrigee.
            "lambdas": [b.get("wavelength", b.get("wl")) if isinstance(b, dict) else None
                        for b in blocs],
            "blocs": [{"start": b.get("start"), "end": b.get("end"),
                       "wavelength": b.get("wavelength", b.get("wl"))}
                      for b in blocs if isinstance(b, dict)],
            # 🔑 La marge sur la trajectoire ACCUMULEE, en unites de A -- la seule grandeur
            # du projet validee comme predicteur de plantage depuis le signal (§24-41).
            # Sparse : une couche absente a une marge >= 5 A, donc sereine.
            "margin_by_layer": s.get("margin_by_layer") or {},
            # 🔴 LES COUCHES PILOTEES EN RATE, ET L'ARTEFACT ETAIT MUET DESSUS. 👤 le
            # 2026-08-22 : « pour le rate, il faut absolument savoir dans quelles couches il a
            # ete introduit ».
            #
            # 🔑 CE N'EST PAS UN CONFORT, C'EST CE QUI REND UN CHIFFRE LISIBLE. Le Rate est ON
            # PAR DEFAUT depuis le 2026-08-12, donc TOUTE gagnante peut en porter -- et « SEEL
            # 0,4255 en pur optique » et « SEEL 0,4255 avec une couche au quartz » ne sont pas
            # la meme promesse pour l'atelier : en mode Rate il n'y a AUCUNE compensation
            # d'erreur, l'ecart part en boucle ouverte vers la couche suivante.
            #
            # 📏 Constate le 2026-08-22 sur `r75x1.5` et `r75x1.75` : impossible de dire si les
            # gagnantes reposaient sur une couche Rate. Le noyau pose pourtant `rate_layers`
            # depuis toujours ; il ne franchissait simplement pas la sortie.
            # « Un instrument dont la sortie n'atteint pas le resultat n'est pas un instrument. »
            #
            # Liste VIDE = pur optique. C'est une distinction, pas une absence de donnee.
            "rate_layers": sorted(int(x) for x in (st.get("rate_layers") or [])),
            # 🔴 LE DRAPEAU QUI MANQUAIT AUX ARTEFACTS. `crash_eliminated` est pose par
            # `_filter_finite_robustness_scores` sur toute strategie dont le score a ete
            # REMPLACE par un repli. Sans lui, un artefact ne porte que des scores finis
            # meme quand tout plante, et un classement de replis ressemble trait pour trait
            # a un classement -- ce qui a coute deux jours le 2026-08-20.
            "crash_eliminated": bool(s.get("crash_eliminated", False)),
            # 🔑 Le taux par NIVEAU de bruit. `crash_rate` est le MAX sur les trois, et la
            # tolerance de 5 % s'y applique -- donc un rejet peut venir du 2x, qui est deux
            # fois le bruit mesure de la machine. Sans ce champ, aucun artefact ne permet de
            # savoir si une strategie rejetee etait fabricable au bruit REEL.
            "crash_rates_by_noise": s.get("crash_rates_by_noise") or {},
            "critical_layer": s.get("critical_layer") or {},
            # 🔑 LA FENTE QUE CETTE STRATEGIE A CHOISIE, et son prix en bruit. Sans ce champ on
            # saurait SI la recherche de fente aide, jamais A QUELLE LARGEUR -- soit la moitie
            # de la reponse a la question de 👤. Le bonus/malus est documente : /1,5 a 5 nm,
            # x1 a 2 nm, x2 a 1 nm, x5 a 0,5 nm. Une strategie qui descend a 1 nm PAIE le x2 ;
            # si elle gagne quand meme, c'est que la finesse spectrale valait le bruit.
            "resolution_nm": s.get("monochromator_resolution_nm"),
            "resolution_noise_factor": s.get("resolution_noise_factor"),
        })
    return {"verdict": "OK", "n_strats": len(lignes), "strategies": lignes,
            "profondeur": dict(profondeur)}


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


def _surcharges_env() -> tuple[dict, str]:
    """Surcharges generiques `cle=valeur` par variable d'environnement, plus leur ETIQUETTE.

        set CERTUS_PROBE_OVERRIDES=crash_gate_confidence=0.95,elite_stop_on_no_gain=0
        set CERTUS_PROBE_TAG=cgc95

    🔑 POURQUOI CE MECANISME. Les leviers qui decident aujourd'hui -- crash_gate_confidence,
    elite_stop_on_no_gain, elite_wl_neighbor_span, elite_max_candidates -- sont tous ROUTES
    depuis le JSON (`certus_strat_ui_state.py`) et aucun n'est atteignable par les huit
    arguments positionnels de cette sonde. Sans cela, chaque essai demanderait un fichier de
    configuration de plus, et le §24-7 s'appliquerait a chacun.

    🔴 L'ETIQUETTE EST OBLIGATOIRE DES QU'IL Y A UNE SURCHARGE, et la sonde REFUSE de tourner
    sans elle. Deux runs qui ne differeraient que par une surcharge produiraient sinon le MEME
    nom de fichier : `scripts/_artefact.py` renommerait plutot que d'ecraser, mais on se
    retrouverait avec deux artefacts horodates indiscernables sur le fond. Ce depot a deja
    perdu les coupures 28-52 exactement ainsi.

    Les valeurs sont converties : entier, puis flottant, puis `true`/`false`, sinon chaine.
    """
    brut = os.environ.get("CERTUS_PROBE_OVERRIDES", "").strip()
    tag = os.environ.get("CERTUS_PROBE_TAG", "").strip()
    if not brut:
        return {}, ""
    if not tag:
        raise SystemExit(
            "🔴 CERTUS_PROBE_OVERRIDES est pose sans CERTUS_PROBE_TAG. L'etiquette entre dans "
            "le nom de l'artefact : sans elle, deux configurations differentes rendraient deux "
            "fichiers indiscernables. Pose une etiquette courte, par exemple cgc95."
        )
    if not tag.replace("_", "").replace("-", "").isalnum():
        raise SystemExit(f"🔴 CERTUS_PROBE_TAG={tag!r} : lettres, chiffres, - et _ seulement.")
    out: dict = {}
    for morceau in brut.split(","):
        morceau = morceau.strip()
        if not morceau:
            continue
        if "=" not in morceau:
            raise SystemExit(f"🔴 surcharge malformee : {morceau!r} (attendu cle=valeur)")
        k, _, v = morceau.partition("=")
        k, v = k.strip(), v.strip()
        if v.lstrip("-").isdigit():
            out[k] = int(v)
        elif v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        else:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out, tag


def main() -> int:
    nom = sys.argv[1] if len(sys.argv) > 1 else "99c"
    mode = sys.argv[2] if len(sys.argv) > 2 else "premium"
    fente = bool(int(sys.argv[3])) if len(sys.argv) > 3 else False
    min_tp = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    res_nm = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
    elargi = int(sys.argv[6]) if len(sys.argv) > 6 else 0   # 0 / 1 / 2
    graine = int(sys.argv[7]) if len(sys.argv) > 7 else SEED
    # 0=rien · 1=swing seul · 2=queue seule · 3=queue+swing+exception · 4=chirurgical
    # 🔴 5=queue+swing SANS exception -- le CONTROLE de 3, ajoute le 2026-08-20. Sans lui,
    # comparer 3 a 2 fait varier DEUX drapeaux a la fois (erreur n° 3 du §5), et `by_swing`
    # n'est pas inerte sur r75x2 : il y ajoute 26 origines (RATE_L47, RATE_L65).
    par_swing = int(sys.argv[8]) if len(sys.argv) > 8 else 0
    if nom not in COMPOSANTS:
        print(f"composant inconnu : {nom}. Choix : {', '.join(COMPOSANTS)}")
        return 2

    print(f"composant {nom} | mode {mode} | graine {graine} | require_turning_point={min_tp} "
          f"| fente {res_nm:g} nm | elargi {int(elargi)} | machine {_machine()}")
    r = mesurer(nom, mode, fente, min_tp, res_nm, elargi, graine, par_swing)
    # 🔴 LA CONFIGURATION EFFECTIVE EST CONSIGNEE DANS L'ARTEFACT, PAS SEULEMENT DANS LE NOM.
    # §24-7 : « un run qui ne consigne pas sa configuration n'est comparable a rien » -- deux
    # artefacts ont deja ete perdus ainsi dans ce depot. Le nom de fichier portait la fente,
    # mais par ABSENCE de suffixe a 2 nm : un artefact nominal ne disait donc rien de la
    # machine sur laquelle il avait tourne. Et le profil ELARGI, qui change sept parametres
    # d'exploration, n'etait trace nulle part ailleurs que par un « _large » dans le nom.
    r.update({"composant": nom, "mode": mode, "seed": graine, "instrument": _commit(),
              "machine": _machine(), "stamp": datetime.now().isoformat(timespec="seconds"),
              "config": {"monochromator_resolution_nm": res_nm,
                         "search_resolution": bool(fente),
                         "require_turning_point": int(min_tp),
                         "exploration_elargie": bool(elargi),
                         "exploration_niveau": int(elargi),
                         # 🔴 CE BLOC MENTAIT : il enregistrait `[]` pour par_swing == 3
                         # alors que le run tournait bien avec les coupures (§24-7).
                         "rate_by_swing": par_swing in (1, 3, 5),
                         "rate_tail_sweep": TAIL_CUTS if par_swing in (2, 3, 5) else [],
                         "rate_layer_sets": RATE_SETS if par_swing == 4 else [],
                         "rate_tail_keep_optical": 4 if par_swing == 3 else 0,
                         # 🔴 §24-7 : sans lui, deux runs a triplets differents seraient
                         # indiscernables dans les artefacts -- exactement la mesure
                         # qu'on cherche a faire.
                         "consensus_seed_list": os.environ.get("CERTUS_CONSENSUS_SEEDS", "")
                                                or "(defaut du JSON)",
                         # 🔴 §24-7 : une surcharge non consignee rend le run
                         # incomparable a quoi que ce soit.
                         "overrides": _surcharges_env()[0] or None,
                         "overrides_tag": _surcharges_env()[1] or None,
                         "elargissement": ({**ELARGISSEMENT, "dp_top_k": 200}
                                           if int(elargi) >= 2 else
                                           dict(ELARGISSEMENT) if elargi else None)}})

    # 🔴 L'ARTEFACT S'ECRIT AVANT LA SYNTHESE, ET C'EST UNE LECON PAYEE.
    #
    # 📏 Le 2026-08-21, un print de pastille rouge dans `synthese()` a leve
    # UnicodeEncodeError sur une console cp1252 -- APRES cinquante minutes de calcul et
    # AVANT l'ecriture. La mesure a ete perdue en entier, pour un caractere d'affichage.
    #
    # 🔑 La regle qui en sort : un AFFICHAGE ne doit jamais pouvoir detruire une MESURE.
    # L'ordre est donc consigner, PUIS raconter -- et la narration est enveloppee, parce que
    # la protection de console reduit le risque sans l'annuler : un IndexError dans un
    # tableau de synthese aurait exactement le meme effet.
    #
    # ⚠️ On consigne AUSSI quand le verdict n'est pas OK. Un run rate porte de l'information
    # -- sa configuration, ses compteurs -- et c'est precisement ce que §24-7 reclamait.
    _tag_nom = _surcharges_env()[1]
    suffixe = ((f"_{_tag_nom}" if _tag_nom else "") + ("_fente" if fente else "") + (f"_tp{min_tp}" if min_tp else "")
                + ("" if res_nm == 2.0 else f"_res{res_nm:g}")
                + ("" if not elargi else "_large" if int(elargi) == 1 else f"_large{int(elargi)}")
                # 🔴 LES COUPURES ENTRENT DANS LE NOM. Sans elles, changer TAIL_CUTS ecrase
                # l'artefact precedent : les coupures 28-52 ont ete perdues ainsi.
                + ("" if not par_swing else "_swing" if par_swing == 1
                   else "_chirurgical" if par_swing == 4
                   else f"_tail{min(TAIL_CUTS)}-{max(TAIL_CUTS)}"
                        + ("k" if par_swing == 3 else "s" if par_swing == 5 else ""))
                # 🔴 LE TRIPLET DE CONSENSUS ENTRE DANS LE NOM, pour la meme raison que les
                # coupures : trois runs qui ne different QUE par lui s'ecraseraient l'un
                # l'autre, et la mesure de dispersion -- qui est justement leur objet --
                # serait perdue sans le moindre message.
                + ("" if not os.environ.get("CERTUS_CONSENSUS_SEEDS", "").strip()
                   else "_cons" + os.environ["CERTUS_CONSENSUS_SEEDS"].strip().replace(",", "-")))
    out = ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{graine:03d}{suffixe}.json"

    # 🔴 CETTE SONDE N'ECRASE PLUS JAMAIS UN ARTEFACT EXISTANT, ET C'EST UN INTERDIT DU
    # PROJET. `CLAUDE.md` interdit 3 : `reports/` porte les resultats scientifiques, seuls
    # 33 fichiers sur 226 sont suivis par git, les 193 autres sont IRRECUPERABLES.
    #
    # 📏 Le defaut a deja coute des artefacts a ce projet -- « les coupures 28-52 ont ete
    # perdues ainsi », consigne plus haut dans ce meme fichier a propos de TAIL_CUTS. Et il
    # a failli recommencer le 2026-08-20 : le run de diagnostic prevu produisait exactement
    # `blocs_vs_plantage_r75x2_deep_s042.json`, soit le nom de la REFERENCE de 8,26 Mo
    # servant au controle C1 -- on aurait detruit la mesure a laquelle on voulait comparer,
    # SANS LE MOINDRE MESSAGE.
    #
    # 🔑 Renommer plutot que refuser : un run de deux heures qui aboutit ne doit pas perdre
    # son resultat parce qu'un homonyme existe. L'horodatage rend la collision impossible,
    # et la ligne imprimee dit ce qui s'est passe au lieu de le taire.
    if out.exists():
        garde = out.with_name(f"{out.stem}_{datetime.now():%Y%m%d_%H%M%S}{out.suffix}")
        print(f"\n🟠 {out.name} EXISTE DEJA ({out.stat().st_size} octets, "
              f"{datetime.fromtimestamp(out.stat().st_mtime):%Y-%m-%d %H:%M}).")
        print(f"   L'artefact precedent est CONSERVE. Le nouveau va dans {garde.name}.")
        out = garde
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")

    # 🔒 La synthese ne peut plus rien couter : l'artefact est deja sur le disque.
    try:
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

    except Exception as exc:  # noqa: BLE001 -- volontaire, voir le bandeau ci-dessus
        print(f"\n🟠 la synthese a echoue ({type(exc).__name__}: {exc}).")
        print(f"   🟢 LA MESURE EST SAUVE : {out.relative_to(ROOT)}")
        print("   Relis-la avec un lecteur d'artefact ; il n'y a rien a relancer.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.exit(main())
