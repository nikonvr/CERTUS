"""PILOTE DU LOT DE 10 A 12 H -- grille resolution x epaisseur optique, puis exploration elargie.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --heures 12
    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --heures 10
    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --etat

👤 2026-08-17 : *« j'aimerai avoir 10 h pour lancer un batch [...] avec de la valeur ajoutee dans
la comprehension slit 1 nm vs 2 nm et 75c dans toutes ses variantes »*, puis *« j'aimerai aussi
que dans strat certains parametres soient augmentes pour tester plus »*.

## Ce que le lot mesure

Une grille RESOLUTION x EPAISSEUR OPTIQUE sur les quatre variantes d'echelle du random75 :
75 couches, structure et materiaux identiques, seule l'epaisseur optique varie.

    Somme QWOT     5 nm   2 nm   1 nm   0,5 nm
    x0,5    57,4    oui    oui    oui    oui
    x1     114,9    oui    oui    oui    oui
    x1,5   172,3     -     oui    oui    oui
    x2     229,8     -     oui    oui    oui

Le 5 nm n'est teste que sur les deux MINCES : sur x1,5 et x2 la courbure le condamne d'avance
(res_lim mesuree a 0,767 et 1,033 nm, `probe_resolution_exigee.py`).

🔒 LA GRILLE EST EXACTE PAR CONSTRUCTION. Le facteur de bruit de la fente multiplie
l'ECHANTILLON, jamais la graine -- contrainte C2, `certus_strat_robustness.py:192`. Deux
resolutions voient donc les MEMES tirages, a l'amplitude pres, et l'ecart entre deux cellules
est attribuable a la resolution seule.

## La prediction que la grille teste, et elle est falsifiable

    biais de fente  ~ B^2        2 nm -> 1 nm : biais / 4
    bruit de lecture             2 nm -> 1 nm : bruit x2   (RESOLUTION_NOISE_FACTOR)

    mince (Somme QWOT faible)  limite par le BRUIT  -> optimum vers la fente LARGE
    epais (Somme QWOT fort)    limite par le BIAIS  -> optimum vers la fente FINE

📏 Deja mesure et coherent : sur x0,5, affiner AGGRAVE -- 48 % a 2 nm, 84 % a 1 nm, 94 % a
0,5 nm. Si l'optimum se deplace vers le fin quand Somme QWOT croit, on tient un mecanisme et une
regle d'atelier : choisir la fente selon l'epaisseur optique totale.

## Pourquoi DEUX phases et pas une

Phase 1 fait varier la RESOLUTION a exploration constante. Phase 2 fait varier l'EXPLORATION a
resolution fixee. Les melanger rendrait un eventuel succes inattribuable -- contrainte C3.

Phase 2 elargit ce qui est GENERE et RETENU (dp_top_k 20 -> 100, limites de candidates x4),
jamais la profondeur d'EVALUATION : `robustness_num_runs` et `n_screen_runs` restent intacts,
sinon les taux de plantage cesseraient d'etre comparables a la grille.

## Les garde-fous

  REPRENABLE       un fichier par cellule ; une cellule deja mesuree n'est jamais relancee
  BUDGET RESPECTE  aucune cellule n'est ENGAGEE s'il ne reste pas sa duree estimee
  ORDONNE          par valeur d'information : si le lot est coupe, l'essentiel est deja acquis
  PAS DE SILENCE   un banc qui deborde rend ECHEC_RESULT_NONE, visible, pas un faux resultat
  PHASE 2 PLAFONNEE son plafond est cale sur le temps restant : si elle deborde, elle est
                   perdue SEULE, la grille est acquise
  10 H OU 12 H     la liste est plus longue que 10 h et le budget coupe tout seul. A 10 h :
                   les 9 cellules de grille + la phase 2 (9,2 h). A 12 h : + les trois
                   cellules de consolidation (11,5 h). Un seul pilote pour les deux.

⚠️ GRAINE UNIQUE (42). La mesure du 2026-08-17 a montre qu'un verdict marginal bascule avec la
graine (§24-46). Toute cellule qui ressortira marginale devra etre rejouee a une seconde graine.

⚠️ MODE FAST. Toute cellule qui rendrait des DEPOSABLES doit etre rejouee en PREMIUM avant
publication -- regle du §8. Ce n'est pas dans ce lot.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import sys
import threading
import time
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

PY = sys.executable
SONDE = "scripts/probe_blocs_vs_plantage.py"
SEED = 42

#: (composant, mode, resolution_nm, elargi, graine, minutes estimees, pourquoi)
#: 🔑 L'ORDRE EST L'ORDRE D'EXECUTION, par valeur d'information DECROISSANTE, et la liste est
#: volontairement PLUS LONGUE que 10 h. Le garde-fou de budget coupe tout seul : le meme
#: pilote sert donc a 10 h comme a 12 h, et c'est le budget qui decide ou s'arreter.
#:
#:   a 10 h : les 9 cellules de grille + la PHASE 2 (555 min)
#:   a 12 h : + les trois cellules de consolidation (690 min)
#:
#: 🔴 LA PHASE 2 EST EN POSITION 10, PAS EN DERNIER, et c'est delibere : placee apres les
#: cellules de consolidation elle ne tournerait jamais a 10 h, alors qu'elle repond a une
#: demande explicite de 👤.
#:
#: 🔑 ET UNE VARIATION NE PRECEDE JAMAIS SA REFERENCE. Un « 5 nm sur x0,5 » lu sans le 2 nm de
#: la meme sonde ne se compare qu'a un echantillon BIAISE par la recherche de fente : le lot
#: coupe juste apres rendrait un chiffre ininterpretable. La colonne 2 nm des trois autres
#: variantes est produite par le run du 2026-08-17 au soir (75c, x1,5, x2 en fast) ; x0,5 est
#: le seul trou, et c'est pourquoi il est comble AVANT qu'on le fasse varier.
CELLULES = [
    ("r75x2", "fast", 1.0, False, 42, 45, "LA question -- 1 nm n'a jamais ete evalue sur x2"),
    ("r75x2", "fast", 0.5, False, 42, 45, "second point de la courbe sur le cas dur"),
    ("r75x0.5", "fast", 2.0, False, 42, 45, "REFERENCE PROPRE du mince -- avant sa variation"),
    ("r75x0.5", "fast", 5.0, False, 42, 45, "le bonus de bruit /1,5 sur le cas mince"),
    ("r75x1.5", "fast", 1.0, False, 42, 45, "le point limite -- 1 deposable sur 704 a 2 nm"),
    ("75c", "fast", 1.0, False, 42, 45, "le composant qui PASSE -- 1 nm le degrade-t-il ?"),
    ("75c", "fast", 5.0, False, 42, 45, "et une fente large l'ameliore-t-elle ?"),
    ("75c", "fast", 0.5, False, 42, 45, "colonne x1 complete"),
    ("r75x1.5", "fast", 0.5, False, 42, 45, "colonne x1,5 complete"),
    ("r75x2", "deep", 1.0, True, 42, 150, "PHASE 2 -- recherche x5 plus large, resolution fixee"),
    # --- CONSOLIDATION : ne tourne qu'a 12 h ---
    ("r75x0.5", "fast", 1.0, False, 42, 45, "cellule PROPRE la ou on n'a qu'un echantillon biaise"),
    ("r75x0.5", "fast", 0.5, False, 42, 45, "idem, et complete la colonne mince"),
    ("r75x2", "fast", 1.0, False, 77, 45, "SECONDE GRAINE sur la cellule de tete (§24-46)"),
]

# 🔑 POURQUOI x0,5 A 1 nm ET 0,5 nm SONT EN CONSOLIDATION ET NON EN TETE. Le run a recherche
# de fente du 2026-08-17 en donne DEJA la tendance sur ce composant :
#
#     0,50 nm  bruit x5   367 strategies   plantage min 94,00 %
#     1,00 nm  bruit x2    54 strategies   plantage min 84,00 %
#     2,00 nm  bruit x1   375 strategies   plantage min 48,00 %
#
# Affiner AGGRAVE, monotonement. ⚠️ Mais ce sont des echantillons BIAISES -- seules les
# strategies dont les lambda toleraient la largeur ont ete retenues -- donc ils ne valent pas
# une cellule propre. D'ou leur presence en consolidation : la tendance est acquise, la mesure
# propre ne l'est pas.
#
# 🔴 ET LA SECONDE GRAINE EST LA POUR UNE RAISON MESUREE, pas par principe. §24-46 : le meme
# intervalle rend 0/452 deposables a la graine 42 et 70/521 a la graine 77. Un verdict marginal
# sur une seule graine n'etablit rien. Elle porte sur x2 a 1 nm parce que c'est la cellule dont
# le resultat changerait le plus de choses.


#: LA SUITE -- enchainee automatiquement si le lot principal finit AVANT 08:00 (👤, 2026-08-18 :
#: *« si cela se termine avant 8h, enchaine automatiquement sur d'autres actions pour ne pas
#: perdre de temps »*).
#:
#: 🔑 ELLE EST AUTO-REPARANTE. Les cellules que le lot principal aurait refusees faute de temps
#: y figurent aussi : le garde-fou « fichier deja la » les saute si elles ont tourne, et les
#: rattrape sinon. On n'a donc pas a savoir ou le lot principal s'est arrete.
#:
#: 🔴 LA CELLULE DE TETE EST x1,75, ET C'EST LE POINT LE PLUS INFORMATIF DU CHANTIER. La grille
#: du 17 au soir a montre que passer a 1 nm DEGRADE x1,5 (30 % contre 0 %) et AMELIORE x2 (38 %
#: contre 100 %) : le signe s'inverse donc entre 172,3 et 229,8 quarts d'onde. x1,75 vaut 201,1.
#: Un seul point, et l'intervalle de bascule est divise par deux.
CELLULES_SUITE = [
    ("r75x1.75", "fast", 2.0, False, 42, 40, "REFERENCE du nouveau point -- avant sa variation"),
    ("r75x1.75", "fast", 1.0, False, 42, 40, "LA BASCULE -- 1 nm gagne-t-il deja a 201 QWOT ?"),
    ("r75x2", "fast", 1.0, False, 77, 40, "2e graine -- sautee si le lot principal l'a faite"),
    ("r75x0.5", "fast", 1.0, False, 42, 40, "rattrapage : colonne mince, idem"),
    ("r75x0.5", "fast", 0.5, False, 42, 40, "rattrapage : colonne mince, idem"),
    ("r75x2", "fast", 1.0, False, 101, 40, "3e graine sur le resultat de tete (§24-46)"),
    ("75c", "premium", 5.0, False, 42, 60, "§8 -- la fente large rejouee en PREMIUM"),
    ("r75x1.75", "fast", 0.5, False, 42, 40, "complete la ligne x1,75"),
]

# 🔴 POURQUOI LE PREMIUM SUR 75c A 5 nm, ET PAS AILLEURS. §8 : « un SEEL retenu sous FAST se
# rejoue en PREMIUM avant publication ». La grille a produit un resultat publiable -- la fente
# large donne PLUS de deposables (289 contre 241) et un PLUS MAUVAIS SEEL (0,310 contre 0,272),
# donc les deux colonnes classent a l'envers l'une de l'autre. C'est cette cellule-la qui porte
# l'affirmation, c'est donc elle qu'il faut confirmer, et aucune autre.


#: LA CAMPAGNE ELARGIE -- 👤 « ok go », 2026-08-18, apres la mesure de x1,75.
#:
#: 🔑 CE QU'ELLE TESTE, ET C'EST LA QUESTION DU CHANTIER. Sur les 5 points de la serie mesures
#: au meme protocole (fast, 2 nm, graine 42), la correlation de rang avec le nombre de
#: strategies deposables vaut :
#:
#:     Somme QWOT -- la propriete du DESIGN         rho = +0,103    (rien)
#:     OFFERTES   -- ce que la RECHERCHE propose    rho = +0,975    (presque parfait)
#:
#: Et la phase 2 a donne la fleche causale sur x2 : meme design, meme graine, recherche elargie,
#: 0 -> 254 deposables. D'ou la these : la « barriere » de la serie d'echelle mesurait la
#: RECHERCHE, pas la physique.
#:
#: 🔴 LES DEUX PREMIERES CELLULES SONT DES TESTS FALSIFIABLES, et le critere est ecrit AVANT :
#:
#:   x0,5 a 1 nm elargi   il echoue vraiment (28 % de plantage, 0 deposable sur 375).
#:                        THESE CONFIRMEE si l'elargissement rend des deposables.
#:                        THESE REFUTEE   s'il reste a 0 -- alors x0,5 echoue pour une raison
#:                        physique, et la barriere existe du cote mince.
#:
#:   x1,5 a 2 nm elargi   il rend 1 deposable sur 440 alors que x1,75, PLUS EPAIS, en rend 282.
#:                        THESE CONFIRMEE si l'elargissement le porte a des centaines.
#:                        THESE REFUTEE   s'il reste marginal.
#:
#: ⚠️ Une cellule elargie coute ~2 h 40 (mesure : 157 min sur x2). C'est le prix de la reponse.
# 🔴🔴 LE CONTROLE QUI MANQUAIT, ET IL PASSE EN TETE. Le 2026-08-18 j'ai ecrit dans QUATRE
# fichiers -- dont la page commerciale -- que « deep rend 0 deposable et extreme en rend 254 ».
# C'EST NON MESURE : le run a 0 est en FAST. `deep` seul a 1 nm sur x2 n'existe pas.
#
# Tant qu'il n'existe pas, on ne sait pas si le mode `extreme` etait NECESSAIRE ou si `deep`
# aurait suffi -- et un mode nomme qui ne sert a rien est pire qu'un mode absent. C'est la
# question de 👤 : « penses-tu qu'il soit optimal ? ». On ne peut pas y repondre sans ce point.
#
#   deep seul rend 0 deposable   -> extreme est necessaire, et l'affirmation devient mesuree
#   deep seul rend des centaines -> extreme est INUTILE ici, et le JSON doit dire `deep`
CELLULES_ELARGI = [
    ("r75x2", "deep", 1.0, False, 42, 120, "LE CONTROLE -- extreme etait-il seulement NECESSAIRE ?"),
    ("r75x0.5", "deep", 1.0, True, 42, 160, "LA DECISIVE -- l'elargissement sauve-t-il le mince ?"),
    ("99c", "deep", 1.0, True, 42, 300, "LE 99c EN ELARGI -- son verdict n'a jamais ete reteste"),
    ("r75x1.5", "deep", 2.0, True, 42, 160, "PREDICTION FALSIFIABLE -- 1 deposable doit exploser"),
    # 🔴 RETIREE LE 2026-08-18 PAR SON PROPRE CRITERE. La cellule « dp_top_k 100 -> 200 » a ete
    # ecrite parce que je croyais le faisceau de la DP « le levier le plus en amont sur l'offre ».
    # 📏 `probe_destructif_dp_top_k.py` sur le 35c, critere ecrit AVANT (effondrement >= 5x) :
    #
    #     dp_top_k =   1  -> la DP recoit [1]   sur 24 appels -> 250 strategies
    #     dp_top_k = 100  -> la DP recoit [100] sur 24 appels -> 304 strategies   facteur 1,22x
    #
    # Le cablage est PROUVE -- la DP recoit bien la valeur -- mais multiplier le faisceau par 100
    # ne bouge l'offre que de 22 %. Elle est produite par les generateurs de VARIANTES (RATE, SYM,
    # ELITE, fusions), pas par la largeur de la DP. 240 min pour ca : non.
    #
    # 🔑 CE QUI PREND SA PLACE, et qui vaut bien plus : le 99c en recherche ELARGIE. Ses 751
    # strategies a 100 % de plantage viennent TOUTES de la recherche standard, a 2 nm -- exactement
    # la configuration ou x2 paraissait impossible et ne l'etait pas. Le verdict « non monitorable
    # a un temoin » n'a donc jamais ete teste autrement que dans le regime qui s'est revele faux.
    ("r75x2", "deep", 1.0, True, 77, 160, "2e graine sur la percee du 2026-08-18"),
    ("r75x0.5", "deep", 2.0, True, 42, 160, "controle : le mince a la fente nominale"),
]


#: LA MATRICE `extreme` x MULTIFENTES SUR TOUS LES COMPOSANTS
#:
#: 👤 2026-08-18 : *« je veux absolument tester extreme multifentes sur tous les problemes :
#: 35c 48c 75cmulticonfig, 99c -- et savoir si le SEEL est ameliore ou pas »*.
#:
#: 🔴 POURQUOI DEUX MODES ET PAS SEULEMENT `extreme`. La question posee est « le SEEL est-il
#: AMELIORE », donc COMPARATIVE. Un SEEL d'extreme seul ne se compare a rien, et le comparer aux
#: cellules `fast` deja mesurees serait exactement l'erreur du 2026-08-18 au matin : j'ai compare
#: fast a extreme et attribue a l'elargissement ce qui revenait au mode `deep`. Contrainte C3.
#: Chaque cellule `extreme` a donc sa JUMELLE `deep` a fente identique -- c'est ce qui fait passer
#: 32 cellules a 64, et c'est ce qui rend la reponse valide.
#:
#: 🔑 L'ORDRE. Pour chaque composant on joue d'abord sa fente de REFERENCE -- celle ou il donne
#: son meilleur resultat connu -- dans les deux modes. C'est la question directe, et elle est
#: repondue composant par composant meme si le lot est coupe tot. Les trois autres fentes suivent.
#:
#: 📏 Cout estime a partir de la seule mesure disponible : 75 couches en `deep` = ~180 min solo
#: (239 min mesurees a deux cellules de front, / 1,33). On extrapole en 2,4 min par couche, et
#: `extreme` a ~1,2x le cout de `deep`. ⚠️ CES DEUX FACTEURS SONT DES EXTRAPOLATIONS : la seule
#: calibration reelle porte sur 75 couches, et mes estimations se sont deja trompees d'un facteur
#: 2 sur ce lot. Le budget tronquera, c'est son role.
_MATRICE_COMPOSANTS = [
    # (nom, couches, fente de REFERENCE -- ou il donne son meilleur resultat connu)
    ("35c", 35, 2.0),        # jamais mesure ailleurs qu'a la fente nominale
    ("48c", 48, 2.0),        # le juge de paix, idem
    ("75c", 75, 2.0),        # SEEL 0,272 -- le meilleur du depot
    ("r75x1.75", 75, 2.0),   # 282 deposables, SEEL 0,528
    ("r75x1.5", 75, 2.0),    # 1 seul deposable : le point le plus marginal
    ("r75x2", 75, 1.0),      # la percee : deep 277 deposables, SEEL 0,625
    ("r75x0.5", 75, 1.0),    # 28 % de plantage, aucun deposable a ce jour
    ("99c", 99, 1.0),        # 🔴 tout QWOT : conclusions SUR lui, jamais A PARTIR de lui
]
_MATRICE_FENTES = (5.0, 2.0, 1.0, 0.5)

#: 🔴🔴 MATRICE ARRETEE LE 2026-08-19 APRES LA PASSE DE REFERENCE PARTIELLE.
#: 👤 : « penses-tu qu'on en tire quelque chose d'interessant de continuer ? » puis
#: « on coupe maintenant et tu consignes tout proprement ».
#:
#: 5 configurations mesurees (x2, 35c, 48c, x0,5, 99c) : ZERO amelioration de SEEL sur AUCUNE,
#: y compris les deux configurations BARRIERE (deep trouve 0 deposable) ou extreme aurait ete le
#: plus utile. Les cellules restantes de la passe de reference (75c, x1,75, x1,5) portaient sur
#: des composants ou `deep` trouve DEJA des centaines de deposables -- les moins susceptibles
#: d'apporter de l'information. Detail : docs/CHANTIER_PREDICTIBILITE.md §4quater-bis.
#:
#: `--matrice` reste fonctionnel et reprenable si la question est rouverte, mais elle ne doit
#: PAS etre relancee sans une raison neuve : la question posee a recu sa reponse.


def _matrice() -> list[tuple]:
    """Les 64 cellules, fente de reference d'abord, puis les autres."""
    out = []
    for passe in ("reference", "autres"):
        for nom, n, ref in _MATRICE_COMPOSANTS:
            fentes = [ref] if passe == "reference" else [f for f in _MATRICE_FENTES if f != ref]
            for res in fentes:
                for elargi in (False, True):          # deep puis extreme, la paire
                    mn = round(2.4 * n * (1.2 if elargi else 1.0))
                    quoi = "extreme" if elargi else "deep   "
                    out.append((nom, "deep", res, elargi, 42, mn,
                                f"{quoi} @ {res:g} nm"
                                + ("  [FENTE DE REFERENCE]" if passe == "reference" else "")))
    return out


CELLULES_MATRICE = _matrice()


def _sortie(nom: str, mode: str, res: float, elargi: bool, graine: int) -> Path:
    suf = (("" if res == 2.0 else f"_res{res:g}")
           + ("" if not elargi else "_large" if int(elargi) == 1 else f"_large{int(elargi)}"))
    return ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{graine:03d}{suf}.json"


def etat(cellules=None) -> int:
    print("=" * 92)
    print("GRILLE RESOLUTION x EPAISSEUR OPTIQUE -- etat")
    print("=" * 92)
    reste = 0
    cumul = 0
    for nom, mode, res, elargi, graine, mn, pourquoi in (cellules or CELLULES):
        f = _sortie(nom, mode, res, elargi, graine)
        cumul += mn
        if f.exists():
            marque, note = "[FAIT]", f.name
        else:
            marque, note = "[    ]", f"~{mn} min -- {pourquoi}"
            reste += mn
        g = f"g{graine}" if graine != SEED else "    "
        print(f"  {marque} {nom:<9} {mode:<7} {res:>4g} nm  {'elargi' if elargi else '      '} "
              f"{g}  {cumul / 60:>4.1f}h  {note}")
    print(f"\n  reste a mesurer : {reste} min ({reste / 60:.1f} h)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heures", type=float, default=10.0,
                    help="budget d'horloge. Aucune cellule n'est ENGAGEE s'il ne reste pas sa "
                         "duree estimee -- mieux vaut une cellule non lancee qu'une tronquee")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--suite", action="store_true",
                    help="joue CELLULES_SUITE au lieu de la grille -- enchainement du 2026-08-18")
    ap.add_argument("--elargi", action="store_true",
                    help="joue CELLULES_ELARGI -- la campagne decisive du 2026-08-18")
    ap.add_argument("--matrice", action="store_true",
                    help="joue CELLULES_MATRICE -- extreme x multifentes x tous les composants, "
                         "avec la jumelle `deep` de chaque cellule (👤, 2026-08-18)")
    ap.add_argument("--parallele", type=int, default=1,
                    help="cellules menees de front (defaut 1). Voir le bloc PARALLELISME du "
                         "docstring avant de monter au-dessus de 2.")
    args = ap.parse_args()
    cellules = (CELLULES_MATRICE if args.matrice
                else CELLULES_ELARGI if args.elargi
                else CELLULES_SUITE if args.suite else CELLULES)
    if args.etat:
        return etat(cellules)

    budget_s = args.heures * 3600.0
    t0 = time.perf_counter()
    faits = sautes = refuses = 0

    print("=" * 92)
    quoi = (" (MATRICE)" if args.matrice else " (ELARGI)" if args.elargi
            else " (SUITE)" if args.suite else "")
    print(f"LOT{quoi} : budget {args.heures:g} h | "
          f"graine {SEED} | {len(cellules)} cellules")
    print("=" * 92, flush=True)

    verrou = threading.Lock()

    def _joue(cellule) -> str:
        nom, mode, res, elargi, graine, mn, pourquoi = cellule
        f = _sortie(nom, mode, res, elargi, graine)
        if f.exists():
            with verrou:
                print(f"  [SAUTE] {nom} {mode} {res:g} nm g{graine} -- deja mesure ({f.name})",
                      flush=True)
            return "saute"

        ecoule = time.perf_counter() - t0
        restant = budget_s - ecoule
        # 🔑 LE SEUIL EST MAJORE PAR LE PARALLELISME. A N cellules de front chacune avance moins
        # vite, donc engager sur l'estimation mono-cellule tronquerait les dernieres. Le facteur
        # 0,45 par cellule supplementaire suppose un partage imparfait -- il sera remesure des
        # que la premiere paire aura tourne, et il est volontairement PESSIMISTE.
        besoin = mn * 60.0 * (1.0 + 0.45 * (args.parallele - 1))
        if restant < besoin:
            with verrou:
                print(f"  [REFUSE] {nom} {mode} {res:g} nm g{graine} -- il reste "
                      f"{restant / 60:.0f} min pour ~{besoin / 60:.0f} min. Non engagee "
                      "plutot que tronquee.", flush=True)
            return "refuse"

        # 🔴 Le plafond du banc est cale sur le temps restant, jamais au-dela. Une cellule qui
        # deborderait rendrait ECHEC_RESULT_NONE -- visible -- au lieu d'entamer les suivantes.
        #
        # 🔑 LE PLAFOND EN DUR SUIT DESORMAIS L'ESTIMATION DE LA CELLULE (👤, 2026-08-18 :
        # *« j'aimerai bien que le 99c passe dans tous les cas, donc avec un time out
        # genereux »*). Il valait 21 600 s -- 6 h -- pour toutes les cellules indifferemment.
        # Or le 99c en elargi est estime a 300 min, et si la contention le porte au-dela de 6 h
        # il serait TUE par ce plafond apres des heures de calcul, pour rendre un
        # ECHEC_RESULT_NONE. On donne donc QUATRE fois l'estimation, avec 6 h de plancher : une
        # cellule a 300 min obtient 20 h de marge au lieu de 6.
        #
        # ⚠️ Ce n'est pas un blanc-seing : `restant * 0.9` reste la contrainte reellement
        # active, et elle est bornee par le budget. Le plafond en dur n'est la que pour eviter
        # qu'une cellule partie de travers ne mange tout le reste.
        plafond = int(min(max(21600, mn * 60 * 4), max(600, restant * 0.9)))
        env = dict(os.environ, CERTUS_BENCH_TIMEOUT_S=str(plafond), PYTHONUTF8="1")

        with verrou:
            print("\n" + "=" * 92)
            print(f"  {nom} | {mode} | {res:g} nm | graine {graine} | "
                  f"{'ELARGI' if elargi else 'standard'} | plafond {plafond} s | "
                  f"ecoule {ecoule / 3600:.1f} h")
            print(f"  pourquoi : {pourquoi}")
            print("=" * 92, flush=True)

        t1 = time.perf_counter()
        r = subprocess.run(
            [PY, SONDE, nom, mode, "0", "0", str(res), str(int(elargi)), str(graine)],
            env=env, cwd=str(ROOT), capture_output=True, text=True,
            # 🔴 SANS CECI LE FIL DE LECTURE MEURT. subprocess decode la sortie de l'enfant
            # avec l'encodage de la LOCALE -- cp1252 sur cette machine -- et les sondes ecrivent
            # des emoji. Le fil leve UnicodeDecodeError, `r.stdout` revient vide, et le journal
            # perd le resume de la cellule. Les ARTEFACTS, eux, sont ecrits par l'enfant et
            # restent intacts : le defaut coute de la lisibilite, jamais une mesure.
            encoding="utf-8", errors="replace",
        )
        dt = time.perf_counter() - t1
        with verrou:
            # 🔑 En parallele les sorties s'entrelacent : on rappelle DE QUI on parle.
            print(f"\n  --- {nom} | {mode} | {res:g} nm | g{graine} ---", flush=True)
            for ligne in (r.stdout or "").splitlines():
                if any(k in ligne for k in ("strategies evaluees", "fente nm", "deposables",
                                            "CONTRAINTE COMMUNE", "aucune couche contrainte",
                                            "consigne", "ECHEC_", "une seule fente", "%")):
                    print(f"    {ligne}", flush=True)
            etat_txt = "OK" if f.exists() else "🔴 AUCUN FICHIER PRODUIT"
            print(f"    -> {etat_txt} en {dt / 60:.0f} min (code {r.returncode})", flush=True)
            if not f.exists() and r.stderr:
                print("    stderr :", (r.stderr or "").strip().splitlines()[-3:], flush=True)
        return "fait"

    if args.parallele > 1:
        print(f"  🔀 {args.parallele} cellules de front. 📏 Mesure du 2026-08-18 : une cellule "
              f"SEULE ne consomme que ~4,3 coeurs sur {os.cpu_count()}, parce que "
              "certus_strat_robustness.py:1276 pose max_workers = cpu_count()//2 -- le nombre de "
              "coeurs PHYSIQUES. Les fils d'hyperthreading dorment ; on les remplit sans toucher "
              "une ligne de certus/.\n", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallele) as ex:
            issues = list(ex.map(_joue, cellules))
    else:
        issues = [_joue(c) for c in cellules]
    faits = issues.count("fait")
    sautes = issues.count("saute")
    refuses = issues.count("refuse")

    ecoule = (time.perf_counter() - t0) / 3600.0
    print(f"\n{'=' * 92}")
    print(f"LOT TERMINE en {ecoule:.1f} h -- {faits} mesurees, {sautes} sautees, "
          f"{refuses} non engagees faute de temps")
    print("=" * 92)
    print("\n  Lire la grille :")
    print("    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --etat")
    print("\n  ⚠️ Toute cellule rendant des DEPOSABLES doit etre rejouee en PREMIUM avant")
    print("     publication (§8), et toute cellule MARGINALE a une seconde graine (§24-46).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
