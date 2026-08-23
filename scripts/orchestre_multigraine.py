"""ORCHESTRATEUR MULTI-REALISATION -- chercher sur K graines dans un BUDGET DE TEMPS.

    python scripts/orchestre_multigraine.py r75x2 --budget 2h
    python scripts/orchestre_multigraine.py r75x2 --budget nuit --objectif meilleur

## POURQUOI CE FICHIER EXISTE

Sur `r75x2` a 2 nm, une graine trouve ou ne trouve pas, et c'est proche d'une loterie. Mesure
du 2026-08-22, sept graines NUES, plage complete, aucune surcharge :

    42 -> 0/1617     77 -> 547/2231 ✅     101 -> 0/1630     202 -> 0/1646
   303 -> 0/1680    404 -> 372/2016 ✅     505 -> 311/1995 ✅

🔑 Le mecanisme est mesure et n'a rien de vague (§3 de REPRENDRE_ICI) : hors ELITE il n'y a
rien ; la generation d'ELITE est DETERMINISTE ; le seul point de divergence des graines est le
criblage Monte-Carlo, dont les survivants deviennent les PARENTS d'ELITE. Et le paysage est une
FALAISE -- 100 % de plantage ou deposable, rien entre les deux. La graine decide donc quels
parents ELITE recoit, et si un descendant atterrit de l'autre cote.

**La reponse produit est donc de rejouer la meme recherche sur K realisations.** Ce fichier
est l'orchestration de cela, par-dessus des briques qui existent toutes deja.

## 🔴 POURQUOI UN BUDGET DE TEMPS, ET PAS UN `K` A COCHER

`K` utile depend de `p`, et **`p` est inconnu sur un composant neuf.** Nos 3/7 valent pour
`r75x2` a 2 nm -- un empilement, une fente. §8.2bis interdit d'en tirer une generalite. Une
case « multi-graines, K=4 » promettrait donc une couverture que le logiciel ne peut pas tenir.

Un budget, lui, est robuste a l'ignorance de `p` : on cherche tant qu'il reste du temps, et on
rapporte ce qu'on a trouve ET ce qu'on n'a pas eu le temps d'essayer.

## LES QUATRE REGLES DU DEPOT QUE CE FICHIER APPLIQUE

1. 🔒 **LA NOTATION FINALE EST SUR UNE GRAINE DISJOINTE** des graines de generation. Noter sur
   une graine qui a servi a trouver, c'est la MALEDICTION DU VAINQUEUR -- mesuree a **+12,9 %**
   le 2026-08-15. Le cout de la garde est mesure lui aussi : **+0,55 %**. Le programme REFUSE
   de tourner si les deux ensembles se croisent.
2. 🔒 **L'UNION NE TRANSPORTE QUE DES PLANS, JAMAIS DES SCORES.** Les scores viennent de
   realisations differentes et ne sont PAS comparables entre eux -- c'est ecrit dans la
   docstring de `_screen_with_seeds`. D'ou le prelevement en TOURNIQUET (le meilleur de chaque
   graine, puis le deuxieme de chaque, ...) : a l'interieur d'une graine le tri est licite,
   entre graines il ne l'est pas.
3. 🔴 **ON N'ATTEND JAMAIS UN ARTEFACT COMME SIGNAL DE FIN.** La sonde l'ecrit AVANT sa
   synthese ; une chaine qui le guettait a lance la mesure suivante 10 s trop tot le
   2026-08-21 (« RuntimeError: QThread has been deleted »). On attend la SORTIE DU PROCESSUS.
4. 🔴 **LE BUDGET GOUVERNE LES LANCEMENTS, PAS LES ARRETS.** Un run coupe est une mesure
   DETRUITE -- quatre de 91 min ont ete perdues ainsi le 2026-08-22, coupees a 98,9 %. On ne
   lance donc jamais un run qui ne rentre pas, mais on laisse finir ceux qui volent, et le
   depassement est RAPPORTE au lieu d'etre masque.

## CE QU'IL NE FAIT PAS

Il ne crible pas les graines a budget Monte-Carlo reduit. Mesure le 2026-08-22 : couper les
tirages d'un facteur 4 ne rend le run que **1,63x** plus rapide -- le minage DP et la
generation ELITE n'en dependent pas. Cribler 7 graines puis rejouer les gagnantes coute
**321 min** contre **308** pour tout jouer plein. Le criblage est fiable et non rentable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux lignes,
# UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# `tests/unit/test_scripts_console_cp1252.py` refuse tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RACINE = Path(__file__).resolve().parents[1]

#: L'echelle de graines de GENERATION, deterministe et documentee. Aucun tirage aleatoire :
#: deux lancements du meme budget doivent essayer les memes realisations, sinon on ne peut ni
#: reprendre une campagne ni reproduire un resultat.
ECHELLE_GRAINES = (101, 202, 303, 404, 505, 606, 707, 808, 909, 1111, 1212, 1313)

#: La graine de NOTATION par defaut. 42 est la graine historique de notation du depot et
#: n'appartient pas a l'echelle ci-dessus -- la disjonction est donc vraie par construction,
#: et verifiee quand meme plus bas.
GRAINE_NOTATION_DEFAUT = 42

#: Tolerance de plantage de 👤. ⚠️ `crash_rate` EST DEJA le maximum sur les trois niveaux de
#: bruit (§3 point 7), dont un a 2x le bruit mesure : la lecture est donc conservatrice.
TOLERANCE_PLANTAGE = 0.05

#: Duree attendue d'un run tant qu'aucun n'a fini ICI. 🔴 Elle ne sert QU'A decider si un
#: lancement rentre dans le budget, jamais a annoncer un ETA : les durees ne valent que sur
#: leur machine (§0.2 piege 5). Des qu'un run finit, sa duree REELLE remplace celle-ci.
DUREE_ATTENDUE_DEFAUT_MIN = 60.0


def _duree_en_minutes(texte: str) -> float:
    """« 2h », « 90m », « 1h30 », « nuit » -> minutes.

    ⚠️ « nuit » vaut 10 h. C'est une convention, pas une mesure : elle ne dit rien de l'heure
    qu'il est, seulement de la duree qu'on accorde.
    """
    t = texte.strip().lower()
    if t == "nuit":
        return 600.0
    # ⚠️ Le `m` final est OPTIONNEL, et c'est un test qui l'a impose : le motif d'abord ecrit
    # exigeait `1h30m`, alors que le message d'erreur juste dessous annonce `1h30` comme
    # valide. Un outil qui contredit sa propre documentation est un piege, pas un outil.
    # Consequence voulue : un nombre NU se lit en minutes (« 45 » = 45 min).
    m = re.fullmatch(r"(?:(\d+(?:[.,]\d+)?)\s*h)?\s*(?:(\d+(?:[.,]\d+)?)\s*(?:m(?:in)?)?)?", t)
    if m and (m.group(1) or m.group(2)):
        h = float((m.group(1) or "0").replace(",", "."))
        mi = float((m.group(2) or "0").replace(",", "."))
        return h * 60.0 + mi
    raise argparse.ArgumentTypeError(
        f"budget {texte!r} illisible. Attendu : 2h · 90m · 1h30 · nuit · un nombre de minutes."
    )


#: Un suffixe de la forme `20260822_102742`. La sonde en ajoute un quand un homonyme existe
#: deja, pour ne pas ecraser une mesure.
_HORODATAGE = re.compile(r"\d{8}_\d{6}")


def _nom_artefact(composant: str, mode: str, graine: int, tag: str = "") -> str:
    suffixe = f"_{tag}" if tag else ""
    return f"blocs_vs_plantage_{composant}_{mode}_s{graine:03d}{suffixe}.json"


def _resoudre_artefact(composant: str, mode: str, graine: int, tag: str = "") -> Path | None:
    """Le chemin de l'artefact le plus RECENT qui corresponde EXACTEMENT a cette configuration.

    🔴 CE N'EST PAS UNE COMMODITE, C'EST LE DEFAUT N° 2 DE `generer_rampes.py`, REPRODUIT ICI
    PUIS CORRIGE. Resoudre par le nom canonique rate les homonymes : la sonde ajoute un
    horodatage quand un fichier du meme nom existe deja, pour ne pas ecraser une mesure. Sur ce
    depot, la mesure a plein budget de la graine 101 vit dans
    `..._s101_20260822_102742.json` -- un lecteur par nom canonique la declarerait ABSENTE et
    referait 45 minutes pour rien.

    🔴 ET LA FAUTE SYMETRIQUE EST PIRE : un `glob("...s101*.json")` naif ramasserait aussi
    `..._s101_mcreduit4x.json`, un run a BUDGET REDUIT, et le prendrait pour la mesure de
    reference. On n'accepte donc comme suffixe QUE le vide ou un horodatage -- jamais une
    etiquette de surcharge, qui designe une autre configuration.

    ⚠️ Le meme filtre protege d'une confusion de graines : `s101*` attrape `s1011`, dont le
    reste `1` n'est pas un horodatage et se trouve donc rejete.
    """
    attendu = _nom_artefact(composant, mode, graine, tag)[:-len(".json")]
    candidats = []
    for f in (RACINE / "reports").glob(f"{attendu}*.json"):
        reste = f.stem[len(attendu):].lstrip("_")
        if reste and not _HORODATAGE.fullmatch(reste):
            continue
        candidats.append(f)
    return max(candidats, key=lambda p: p.stat().st_mtime, default=None)


def _lire_artefact(chemin: Path | None) -> dict | None:
    """Rend le contenu si l'artefact est une MESURE, None sinon.

    🔴 `verdict != OK` ou une liste de strategies VIDE ne compte pas comme fait : les quatre
    mesures perdues du 2026-08-22 portaient toutes un artefact, et il ne portait rien.
    """
    if chemin is None or not chemin.is_file():
        return None
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if d.get("verdict") != "OK" or not (d.get("strategies") or []):
        return None
    return d


def _deposables(artefact: dict) -> list[dict]:
    """Les strategies sous la tolerance, triees par score CROISSANT.

    Le tri est licite ici : toutes ces strategies viennent de LA MEME realisation.
    """
    dep = [s for s in artefact["strategies"] if s.get("crash_rate", 1.0) <= TOLERANCE_PLANTAGE]
    return sorted(dep, key=lambda s: s.get("score", float("inf")))


def _seel(score: float) -> float:
    """SEEL = 2·√(score). Controle : 0,08053 rend 0,5676, la valeur publiee en §0ter."""
    return 2.0 * (float(score) ** 0.5)


#: Prefixe du flux d'EVENEMENTS, lisible par machine. Arme par `--evenements`.
#:
#: 🔑 POURQUOI UN FLUX, ET PAS DU REGEX SUR LES PHRASES. Le GUI pilote ce script au lieu de
#: reimplementer l'orchestration -- sinon deux chemins de code coexisteraient et divergeraient,
#: ce que ce depot a deja paye. Mais faire lire de la PROSE a une interface la rend solidaire
#: de la formulation : changer un mot d'affichage casserait le GUI en silence. Les phrases
#: restent donc pour l'humain, et cette ligne-ci pour la machine.
PREFIXE_EVT = "[ORCH] "

_evenements_armes = False


def _evt(type_: str, **champs) -> None:
    if _evenements_armes:
        print(PREFIXE_EVT + json.dumps({"evt": type_, **champs}, ensure_ascii=False), flush=True)


def lire_evenement(ligne: str) -> dict | None:
    """L'inverse de `_evt` -- rend le dictionnaire, ou None si la ligne n'est pas un evenement.

    Vit ici, a cote de l'emetteur, deliberement : un format dont l'ecriture et la lecture sont
    dans deux fichiers derive. Le GUI importe cette fonction.
    """
    if not ligne.startswith(PREFIXE_EVT):
        return None
    try:
        d = json.loads(ligne[len(PREFIXE_EVT):])
    except ValueError:
        return None
    return d if isinstance(d, dict) and "evt" in d else None


#: Ce que le changement de verre temoin COUTE la ou le monitoring optique fonctionne deja.
#: Mesure du 2026-08-15, controle negatif passe sur TROIS composants : 48c +73 a +89 %
#: (11/11 partitions), 35c +10 a +98 % (12/12), 75c aleatoire +110 % (0,272 -> 0,571 nm).
#: AUCUNE partition ne gagne, meme par chance.
DEGRADATION_MULTITEMOIN = "+73 a +110 % selon le composant, 3 composants sur 3"


def amorce_defaillance(strategies: list[dict]) -> int | None:
    """La couche ou la defaillance COMMENCE, mediane sur les strategies. None si aucune.

    🔑 CE N'EST PAS `critical_layer`, ET LA DIFFERENCE A COUTE TROIS RUNS. Le champ
    `critical_layer` de l'artefact rapporte la marge la PIRE, donc la plus profonde -- mediane
    **57** sur `r75x2`. En le lisant on croit le probleme profond, et une coupure a 38
    parfaitement placee. 📏 La PREMIERE marge negative, elle, est a la couche **6**.

    On lit donc `margin_by_layer["level"]`, qui porte la marge par couche en Angstroms, et on
    prend le plus petit indice ou elle passe sous zero. Une marge `level` negative signifie que
    le niveau d'arret, fige sur le nominal, n'est plus dans la bande atteignable du signal reel.
    """
    amorces: list[int] = []
    for s in strategies:
        lv = (s.get("margin_by_layer") or {}).get("level") or {}
        negatives = [int(k) for k, v in lv.items() if v is not None and float(v) < 0]
        if negatives:
            amorces.append(min(negatives))
    if not amorces:
        return None
    amorces.sort()
    return amorces[len(amorces) // 2]


def multitemoin_peut_agir(n_couches: int, amorce: int | None, n_temoins_max: int) -> tuple[bool, str]:
    """Une partition peut-elle seulement ATTEINDRE la defaillance ? Rend (peut, pourquoi).

    🔴 CE GARDE-FOU EXISTE PARCE QUE L'ESCALADE A DEPENSE TROIS RUNS POUR RIEN, le 2026-08-23,
    sur `r75x2` puis sur `r75x0.5`. Verifie ensuite sur les artefacts, plans APPARIES :

        29 plans communs mono / 2 temoins  ->  plantage INCHANGE sur 28, ameliore sur 1
        26 plans communs mono / 3 temoins  ->  INCHANGE sur 25
        25 plans communs mono / 4 temoins  ->  INCHANGE sur 24
        amorce de defaillance : mediane 6-7 couches, INCHANGEE dans les 80 cas sur 80

    Une coupure n'agit que sur ce qui vient APRES elle. Quand la defaillance commence a la
    couche 6 et que la coupure la moins profonde possible est a `n_couches / n_temoins_max`,
    il n'y a plus rien a sauver -- et cela se lit dans un artefact DEJA ECRIT, sans calcul.

    ⚠️ CE QU'IL NE DIT PAS : que le composant est infaisable. Il dit que le MULTI-TEMOIN ne
    peut rien pour lui. Ce sont deux affirmations differentes, et `r75x2` le prouve -- le meme
    empilement, la meme graine et la meme fente rendent 251 strategies deposables des qu'on
    injecte des plans de surveillance connus.
    """
    if amorce is None:
        return True, "amorce de defaillance inconnue -- rien ne s'oppose a l'essai"
    if n_temoins_max < 2 or n_couches < 2:
        return False, "aucune partition possible"
    # La coupure la MOINS PROFONDE qu'on s'autorise, tous nombres de temoins confondus : c'est
    # celle du nombre de temoins MAXIMAL, puisque plus on decoupe, plus la premiere coupure
    # remonte. Au-dela d'elle, aucune partition de l'escalade n'atteint la defaillance.
    plus_haute = min(partition_temoins(n_couches, n_temoins_max) or [n_couches])
    if amorce > plus_haute:
        return True, (
            f"la defaillance commence a la couche {amorce}, en aval de la coupure la moins "
            f"profonde ({plus_haute}) : une partition peut l'atteindre"
        )
    # Combien de temoins faudrait-il pour couper AVANT l'amorce ?
    besoin = n_couches // max(amorce, 1) + 1
    return False, (
        f"INUTILE PAR CONSTRUCTION : la defaillance commence des la couche {amorce}, alors que "
        f"la coupure la moins profonde possible a {n_temoins_max} temoins est a la couche "
        f"{plus_haute}. Une coupure n'agit que sur ce qui vient APRES elle. Il faudrait ~{besoin} "
        f"temoins pour couper avant l'amorce -- autant de segments dont l'erreur serait gelee. "
        f"⚠️ Cela ne dit PAS que le composant est infaisable : cela dit que le multi-temoin ne "
        f"peut rien pour lui."
    )


def verdict_multitemoin(par_graine: dict[int, list[dict]], graines_essayees: int) -> tuple[bool, str]:
    """Le multi-temoin est-il UTILE ici ? Rend (utile, la raison, en clair).

    🔑 👤, 2026-08-22 : *« un utilisateur ne sait pas au debut si le multi-temoin sera
    necessaire, donc il faut le rajouter, avec un critere qui permet de dire que dans ce cas ce
    n'est pas la peine »*. Voici ce critere, et il est ENTIEREMENT mesure.

    ## LE CRITERE

    Le multi-temoin est un outil de FAISABILITE, jamais d'optimisation. Il ne rend pas plus
    precis : il *retire* de la compensation d'erreur sans rien restaurer. La ou le monitoring
    optique fonctionne, il degrade donc TOUJOURS -- controle negatif passe sur trois composants,
    aucune partition ne gagne.

        au moins UN deposable  ->  le composant se surveille en une campagne.
                                   Le multi-temoin est INUTILE, et il COUTERAIT.
        AUCUN deposable        ->  le composant ne se surveille pas d'un bout a l'autre.
                                   Le multi-temoin est le levier qui reste.

    ## 🔴 ET L'ORDRE EST LA MOITIE DU CRITERE

    Il s'applique APRES le multiseed, JAMAIS avant, et le 2026-08-22 dit pourquoi : sur
    `r75x2`, les graines 42, 101, 202 et 303 rendent ZERO. A une seule graine, le composant
    ressemblait trait pour trait a un cas de multi-temoin. Les graines 404 et 505 rendent 372
    et 311 deposables.

    **Armer le multi-temoin sur la foi d'une graine malchanceuse aurait degrade de ~110 % un
    composant qui n'avait aucun probleme.** C'est l'erreur que ce critere existe pour empecher.
    """
    trouvent = {g: d for g, d in par_graine.items() if d}
    if trouvent:
        return False, (
            f"INUTILE : {len(trouvent)} realisation(s) sur {len(par_graine)} trouvent des "
            f"strategies deposables, donc le composant se surveille d'un bout a l'autre avec "
            f"UN SEUL verre temoin. Changer de temoin y degrade toujours ({DEGRADATION_MULTITEMOIN}) "
            f"-- c'est un outil de faisabilite, jamais d'optimisation."
        )
    return True, (
        f"CANDIDAT : aucune des {graines_essayees} realisation(s) essayees ne rend de strategie "
        f"deposable. Le composant ne se surveille pas d'un bout a l'autre en une campagne, et le "
        f"multi-temoin est le levier qui reste. ⚠️ Il ne rendra pas plus PRECIS -- il fait passer "
        f"d'impossible a possible, en gelant dans la piece l'erreur d'avant chaque coupure."
    )


def partition_temoins(n_couches: int, n_temoins: int) -> list[int]:
    """Les couches ou un verre temoin NEUF entre, pour `n_temoins` temoins.

    🔴 PARTITION REGULIERE PAR DEFAUT, ET C'EST UN CHOIX PAR ABSENCE DE MESURE, PAS UN CHOIX
    MESURE. Cette docstring a affirme le contraire jusqu'au 2026-08-23, en invoquant
    « etendue +14,4 % sur 440 partitions du 99c / +15,4 % sur 18 positions du 75c, l'optimum
    est PLAT ». Verification faite, cette etendue ne dit RIEN du choix d'une coupure quand le
    critere est le PLANTAGE :

      · `docs/CHANTIER_MULTITEMOINS.md:287` intitule la ligne « etendue totale du SEEL ».
      · `scripts/classer_partitions.py:178` ECARTE les partitions dont le plantage cumule
        depasse `--max-crash` (defaut 0.05, ligne 107) AVANT de calculer la RMSE. L'etendue
        est donc CONDITIONNELLE au fait d'avoir deja franchi la porte de plantage : elle
        decrit la dispersion du SEEL PARMI LES PARTITIONS DEJA DEPOSABLES.
      · `reports/controle_random75/ASSEMBLAGE_r75.json` ne porte aucun champ de plantage --
        chaque position n'a que `p`, `seel`, `S_gelee`, `S_gelee_rel`. Le +15,4 % ne
        transporte donc AUCUNE information de plantage.
      · Et `scripts/assembler_r75.py:57` mesure sur `JSON-strat-random75.json`, le x1 -- un
        composant a 0 % de plantage en une seule campagne, donc le cas ou la question ne se
        pose meme pas.

    🔑 CE QUE LA MESURE ETABLIT : une fois la porte de plantage franchie, PEU IMPORTE OU L'ON
    COUPE, le SEEL varie peu. CE QU'ELLE N'ETABLIT PAS : quelle coupure fait FRANCHIR cette
    porte a un composant qui echoue. Les deux questions sont disjointes, et c'est la seconde
    que l'escalade multi-temoin pose.

    ⚠️ La partition reguliere reste donc un DEFAUT RAISONNABLE -- il faut bien couper quelque
    part -- mais rien ne l'a mesuree meilleure qu'une autre sur le critere qui nous occupe.
    📏 Indice contraire, d'ailleurs : le 99c qui REUSSIT coupe a 0/22/72, ce qui n'est pas
    regulier.

    ⚠️ L'index 0 n'est jamais rendu : la couche 0 pousse deja sur verre nu.
    """
    if n_temoins < 2 or n_couches < 2:
        return []
    pas = n_couches / n_temoins
    return sorted({c for i in range(1, n_temoins) if 0 < (c := int(round(i * pas))) < n_couches})


def _escalade_multitemoin(a, jdir: Path) -> int:
    """Cherche le MINIMUM de temoins qui rende le composant faisable. 2, puis 3, puis 4...

    🔑 POURQUOI UN MINIMUM, ET PAS UN REGLAGE. 👤, 2026-08-22 : *« cette version doit
    fonctionner meme avec des coatings a 200 couches, donc clairement en multitemoins »*.

    A cette taille le mono-temoin n'a aucune chance -- le 99c plante deja a 100 % sur ses 487
    strategies en une seule campagne. Le multi-temoin n'y est donc plus un dernier recours,
    c'est le mode NORMAL, et la question devient : **combien**.

    🔴 ET LA REPONSE EST « LE MOINS POSSIBLE », POUR UNE RAISON MESUREE. Chaque coupure GELE
    dans la piece l'erreur accumulee avant elle, definitivement incorrigible. Le multi-temoin
    ne rend donc pas plus precis : il fait passer d'impossible a possible, en payant. On
    s'arrete DONC au premier nombre de temoins qui trouve -- pas au meilleur SEEL sur une
    grille de nombres de temoins, ce qui serait payer deux fois.

    🔴 CE QUE LA MESURE NE DIT PAS, ET QUE CETTE DOCSTRING A AFFIRME JUSQU'AU 2026-08-23.
    Elle invoquait « ou couper importe peu, etendue +14,4 %, l'optimum est PLAT » pour
    justifier la partition reguliere. Cette etendue porte sur le **SEEL de partitions DEJA
    DEPOSABLES** -- `classer_partitions.py:178` ecarte celles qui plantent avant meme de
    calculer la RMSE. Elle ne dit donc rien de la question posee ici, qui est de faire
    FRANCHIR la porte a un composant qui echoue. Voir `partition_temoins` pour le detail.

    📌 De meme, le « 2 contre 3 temoins vaut +3,0 %, sous la resolution de 5,1 % » compare des
    SEEL, pas des taux de plantage : il ne dit pas quel nombre de temoins rend FAISABLE.

    ⚠️ L'escalade reste donc fondee sur un raisonnement de COUT -- chaque coupure gele de
    l'erreur, on en prend le moins possible -- et non sur une mesure du meilleur nombre de
    temoins. C'est defendable, et ce n'est pas la meme chose.
    """
    n = _n_couches(a.composant)
    if not n:
        print(f"  🔴 nombre de couches inconnu pour {a.composant} : escalade annulee")
        return 1
    for k in range(2, int(a.multitemoin) + 1):
        print()
        print(f"  ▶  MULTI-TEMOIN a {k} temoins sur {n} couches")
        code = _passe_multitemoin(a, jdir, k, n)
        if code == 0:
            print(f"  🔑 MINIMUM TROUVE : {k} temoin(s) suffisent. On s'arrete la -- un temoin "
                  f"de plus gelerait davantage d'erreur pour rien.")
            return 0
    print(f"  🔴 aucun nombre de temoins jusqu'a {a.multitemoin} ne rend ce composant faisable.")
    return 1


def _passe_multitemoin(a, jdir: Path, n_temoins: int, n: int) -> int:
    """Rejoue la premiere graine avec K verres temoins, quand rien n'a ete trouve autrement.

    🔴 CE N'EST PAS UNE OPTIMISATION, ET LE MESSAGE LE DIT A CHAQUE FOIS. Le multi-temoin
    RETIRE de la compensation d'erreur : le residu d'avant chaque coupure est gele dans la
    piece, definitivement incorrigible. Il ne s'emploie que la ou le mono-temoin ne rend RIEN.

    ⚠️ Une seule graine, deliberement : si le multi-temoin change quelque chose, cela se voit
    des la premiere. En rejouer K couterait des heures pour repondre a une question binaire.
    """
    graine = int(a.graines[0]) if a.graines else ECHELLE_GRAINES[0]
    coupures = partition_temoins(n, n_temoins)
    if not coupures:
        print(f"  🔴 partition vide pour {n_temoins} temoins sur {n} couches")
        return 1
    tag = f"mt{n_temoins}"
    print(f"     {n} couches · coupures aux couches {coupures} · graine {graine} · etiquette {tag}")
    _evt("multitemoin_passe", temoins=n_temoins, coupures=coupures, graine=graine)
    p = _lancer(
        a.python, a.composant, a.mode, a.resolution, graine,
        jdir / f"journal_mt{n_temoins}_s{graine:03d}.log",
        # ⚠️ Le parseur de surcharges decoupe sur les VIRGULES : la liste s'ecrit donc avec des
        # POINTS-VIRGULES, que `_resolve_witness_resets` accepte.
        env_sup={
            "CERTUS_PROBE_OVERRIDES": "witness_reset_layers=" + ";".join(str(c) for c in coupures),
            "CERTUS_PROBE_TAG": tag,
        },
    )
    p.wait()
    try:
        p._certus_journal.close()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, graine, tag))
    dep = _deposables(art) if art else []
    if not dep:
        print(f"  ❌ {n_temoins} temoin(s) : aucun deposable.")
        _evt("multitemoin_resultat", trouve=False, temoins=n_temoins)
        return 1
    seel = _seel(dep[0]["score"])
    print(f"  🟢 {n_temoins} temoin(s) : {len(dep)} deposable(s) · SEEL {seel:.4f} nm · "
          f"{dep[0]['n_blocs']} blocs · plantage {100 * dep[0]['crash_rate']:.2f} %")
    print("     ⚠️ Ce SEEL n'est PAS comparable a un SEEL mono-temoin : il decrit une piece "
          "deposee sous plusieurs verres, dont l'erreur d'avant chaque coupure est gelee.")
    _evt("multitemoin_resultat", trouve=True, temoins=n_temoins, seel=seel,
         deposables=len(dep), coupures=coupures)
    return 0


def _n_couches(composant: str) -> int:
    """Le nombre de couches du composant, lu dans le registre de la sonde."""
    try:
        sys.path.insert(0, str(RACINE / "scripts"))
        from probe_blocs_vs_plantage import COMPOSANTS

        return int(COMPOSANTS[composant][1])
    except (ImportError, KeyError, TypeError, ValueError):
        return 0


def mode_finalisation_demandee(drapeau: Path) -> str:
    """Le fichier d'arret porte SON MODE dans son contenu. Rend "", "attendre" ou "abandonner".

    🔑 POURQUOI DANS LE CONTENU, ET PAS DANS UN DRAPEAU DE LANCEMENT. 👤 : « si on clique sur
    arreter, on n'est pas oblige de terminer de suite, on peut passer a l'etape 3 ». La
    question ne se pose donc PAS au lancement mais au moment du clic -- a ce moment-la seul on
    sait si le run en vol vaut la peine d'etre attendu. Un seul fichier, un seul mecanisme :
    ce qu'on ecrit dedans decide.

        vide / n'importe quoi  ->  attendre    : les runs en vol finissent, RIEN n'est perdu
        « abandonner »         ->  abandonner  : on les tue et on passe a l'etape 3 tout de
                                                 suite. Leur travail est perdu, et c'est DIT.

    🔴 Dans les DEUX cas on passe a l'union puis a la notation finale. Arreter n'a jamais voulu
    dire tout jeter : ce qui est deja mesure porte un artefact et sera note.
    """
    if not drapeau.exists():
        return ""
    try:
        contenu = drapeau.read_text(encoding="utf-8", errors="replace").strip().lower()
    except OSError:
        contenu = ""
    return "abandonner" if contenu.startswith("abandonner") else "attendre"


def motif_finalisation(
    *,
    drapeau: Path,
    seel_cible: float | None,
    meilleur_seel: float | None,
    succes: bool,
    objectif: str,
) -> str:
    """Faut-il FINALISER -- cesser de lancer et produire le chiffre ? Rend le motif, ou "".

    Fonction PURE et au niveau du module, deliberement : c'est la decision qui interrompt une
    campagne de plusieurs heures, elle doit etre testable sans lancer un seul run.

    L'ordre des trois causes est un ordre de PRIORITE d'affichage, pas de logique -- elles ne
    s'excluent pas. La demande explicite de 👤 passe devant, parce que c'est la seule qui vient
    de l'exterieur et qu'il doit la voir reconnue.
    """
    if drapeau.exists():
        return "demande de l'utilisateur (fichier FINALISER)"
    if seel_cible is not None and meilleur_seel is not None and meilleur_seel <= seel_cible:
        return f"cible atteinte : SEEL {meilleur_seel:.4f} <= {seel_cible:.4f} nm"
    if succes and objectif == "premier":
        return "objectif « premier » : une realisation a trouve"
    return ""


def _signature(strategie: dict) -> tuple:
    """Signature de PLAN : (nombre de blocs, frontieres et lambdas).

    🔴 Jamais par `id` : mesure §24-51, 21 identifiants sur 79 portent deux ou trois plans
    DIFFERENTS. Dedupliquer par id fusionnerait des plans distincts et en perdrait en silence
    -- exactement l'echec que cette union existe pour eviter.
    """
    blocs = strategie.get("blocs") or strategie.get("blocks") or []
    return (
        int(strategie.get("n_blocs", len(blocs))),
        tuple(
            (int(b["start"]), int(b["end"]), round(float(b.get("wavelength", b.get("wl", 0.0))), 4))
            for b in blocs
            if isinstance(b, dict) and "start" in b and "end" in b
        ),
    )


def unir_en_tourniquet(par_graine: dict[int, list[dict]], plafond: int) -> tuple[list[dict], int]:
    """Union des plans, en TOURNIQUET, dedupliquee par signature.

    🔒 LE TOURNIQUET N'EST PAS UN DETAIL. Prendre « les N meilleurs de l'union » exigerait de
    comparer des scores venus de realisations DIFFERENTES -- ce que la regle d'or du multiseed
    interdit. On prend donc le meilleur de chaque graine, puis le deuxieme de chaque, etc. :
    chaque comparaison reste interne a une graine, et aucune graine n'est affamee.

    Rend (plans, nombre de plans ECARTES par le plafond). 🔴 L'appelant DOIT dire ce qui a ete
    ecarte : une troncature silencieuse se lit comme « on a tout couvert ».
    """
    graines = sorted(par_graine)
    plans: list[dict] = []
    vues: set[tuple] = set()
    ecartes = 0
    rang = 0
    while True:
        encore = False
        for g in graines:
            lst = par_graine[g]
            if rang >= len(lst):
                continue
            encore = True
            s = lst[rang]
            sig = _signature(s)
            if not sig[1] or sig in vues:
                continue
            vues.add(sig)
            if len(plans) >= plafond:
                ecartes += 1
                continue
            plans.append(
                {
                    "nom": f"s{g:03d}_{s.get('origine', '?')}_{s.get('n_blocs', '?')}b_rang{rang}",
                    "blocs": [
                        {
                            "start": int(b["start"]),
                            "end": int(b["end"]),
                            "wavelength": float(b.get("wavelength", b.get("wl", 0.0))),
                        }
                        for b in (s.get("blocs") or s.get("blocks") or [])
                    ],
                }
            )
        if not encore:
            break
        rang += 1
    return plans, ecartes


def _lancer(py: str, composant: str, mode: str, res_nm: float, graine: int,
            journal: Path, env_sup: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    # 🔴 LE PLAFOND SE CALCULE, IL NE SE COPIE PAS. `bench_examples.py:171` fait rendre None a
    # `wait_for` au-dela -- ce qui RESSEMBLE a un resultat. Regle du depot : max(5400, 4x duree
    # attendue). Un plafond trop grand ne coute rien ; un plafond trop petit detruit la mesure
    # a la derniere minute.
    env.setdefault("CERTUS_BENCH_TIMEOUT_S", "38400")
    if env_sup:
        env.update(env_sup)
    journal.parent.mkdir(parents=True, exist_ok=True)
    fh = journal.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [py, "scripts/probe_blocs_vs_plantage.py", composant, mode, "0", "0",
         f"{res_nm:g}", "0", str(graine)],
        cwd=RACINE, stdout=fh, stderr=subprocess.STDOUT, env=env,
    )
    proc._certus_journal = fh  # type: ignore[attr-defined]
    return proc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Cherche sur K realisations dans un budget de temps, unit, renote sur une graine disjointe.",
    )
    ap.add_argument("composant", help="nom du composant, ex. r75x2")
    ap.add_argument("--budget", type=_duree_en_minutes, default="2h",
                    help="duree maximale : 2h · 90m · 1h30 · nuit (10 h). Defaut 2h")
    ap.add_argument("--objectif", choices=("premier", "meilleur"), default="premier",
                    help="premier : on s'arrete des qu'une graine trouve. "
                         "meilleur : on epuise le budget et on unit tout. Defaut premier")
    ap.add_argument("--seel-cible", type=float, default=None, metavar="NM",
                    help="on arrete des qu'une realisation rend un SEEL <= cette valeur, en nm. "
                         "⚠️ Le SEEL annonce en cours de campagne est PROVISOIRE : il est mesure "
                         "sur la graine qui l'a trouve. Le chiffre citable vient de la notation "
                         "finale sur une graine disjointe.")
    ap.add_argument("--runs-en-vol", choices=("attendre", "abandonner"), default="attendre",
                    help="que faire des runs EN VOL quand on decide d'arreter. "
                         "attendre : on les laisse finir, rien n'est gaspille (defaut). "
                         "abandonner : on les tue, on s'arrete tout de suite, leur travail est perdu.")
    ap.add_argument("--slots", type=int, default=0,
                    help="processus concurrents. 0 = auto (cpu_count//8, au moins 1)")
    ap.add_argument("--mode", default="deep", choices=("fast", "premium", "deep"))
    ap.add_argument("--resolution", type=float, default=2.0, help="fente, en nm. Defaut 2.0")
    ap.add_argument("--graines", type=int, nargs="+", default=None,
                    help=f"graines de generation. Defaut : l'echelle {ECHELLE_GRAINES[:5]}...")
    ap.add_argument("--graine-notation", type=int, default=GRAINE_NOTATION_DEFAUT,
                    help=f"graine de NOTATION finale, DISJOINTE. Defaut {GRAINE_NOTATION_DEFAUT}")
    ap.add_argument("--max-plans", type=int, default=200,
                    help="plafond de plans injectes a la notation finale. Defaut 200")
    ap.add_argument("--duree-attendue", type=float, default=DUREE_ATTENDUE_DEFAUT_MIN,
                    help="minutes, pour decider si un lancement rentre. Remplacee par la duree "
                         f"REELLE des le premier run fini. Defaut {DUREE_ATTENDUE_DEFAUT_MIN:g}")
    ap.add_argument("--python", default=os.environ.get("CERTUS_PY", "C:/envs/certus/Scripts/python.exe"))
    ap.add_argument("--multitemoin", type=int, default=0, metavar="K",
                    help="si AUCUNE realisation ne trouve, ESCALADER de 2 a K verres temoins "
                         "et s'arreter au MINIMUM qui rend faisable. 0 = ne pas essayer. "
                         "⚠️ Le multi-temoin ne rend pas plus PRECIS : il fait passer "
                         "d'impossible a possible. La ou le monitoring marche, il DEGRADE.")
    ap.add_argument("--evenements", action="store_true",
                    help="emet en plus un flux JSONL prefixe « [ORCH] », pour un pilote "
                         "(le GUI STRAT). Les phrases humaines restent inchangees.")
    ap.add_argument("--dry-run", action="store_true", help="dit ce qui serait fait, ne lance rien")
    a = ap.parse_args(argv)
    global _evenements_armes
    _evenements_armes = bool(a.evenements)

    graines = list(a.graines) if a.graines else list(ECHELLE_GRAINES)
    slots = a.slots if a.slots > 0 else max(1, (os.cpu_count() or 8) // 8)

    # 🔒 LA GARDE ANTI-MALEDICTION, ET ELLE REFUSE DE TOURNER. Ce n'est pas un avertissement :
    # un score publie apres notation sur une graine qui a servi a trouver est FAUX de +12,9 %,
    # et rien dans le resultat ne le dirait.
    if a.graine_notation in graines:
        print(f"🔴 la graine de notation {a.graine_notation} est AUSSI une graine de generation.")
        print("   Noter sur une graine qui a servi a trouver, c'est la malediction du vainqueur")
        print("   -- mesuree a +12,9 % le 2026-08-15. Choisis une graine disjointe.")
        return 2

    stamp = time.strftime("%Y%m%d_%H%M%S")
    jdir = RACINE / "reports" / f"orchestre_{a.composant}_{stamp}"

    print("=" * 78)
    print("ORCHESTRATEUR MULTI-REALISATION -- CERTUS")
    print("=" * 78)
    print(f"  composant        : {a.composant} · mode {a.mode} · fente {a.resolution:g} nm")
    print(f"  budget           : {a.budget:.0f} min · objectif « {a.objectif} »")
    print(f"  slots            : {slots} concurrents")
    print(f"  graines          : {graines}")
    print(f"  graine notation  : {a.graine_notation}  (disjointe ✔)")
    print(f"  journaux         : {jdir.relative_to(RACINE)}")
    print()
    _evt("demarrage", composant=a.composant, mode=a.mode, resolution=a.resolution,
         budget_min=a.budget, objectif=a.objectif, seel_cible=a.seel_cible, slots=slots,
         graines=graines, graine_notation=a.graine_notation)

    # 🔴 LE POINT DE FINALISATION DOIT EXISTER DES LA PREMIERE SECONDE. Cette annonce vivait plus bas,
    # apres le balayage de reprise : un pilote qui proposait « Arreter » pendant ce laps ne
    # trouvait aucun chemin ou ecrire, et le clic ne faisait RIEN, en silence. Un bouton actif
    # qui n'agit pas est pire qu'un bouton grise. Trouve par le test d'integration du GUI.
    drapeau_finaliser = jdir / "FINALISER"
    # 🔴 UN DRY-RUN N'ECRIT RIEN, PAS MEME UN DOSSIER VIDE. 📏 Le 2026-08-23, les tests
    # unitaires -- qui appellent `main` -- avaient seme QUARANTE-NEUF dossiers
    # `reports/orchestre_*` vides. Un `reports/` illisible n'est pas un detail : c'est
    # l'endroit ou l'on cherche les mesures, et `coherence_campagne.py` y date le debut d'une
    # campagne sur la mtime des journaux.
    if not a.dry_run:
        jdir.mkdir(parents=True, exist_ok=True)
    print(f"  ⏹  pour FINALISER a tout moment :  touch {drapeau_finaliser.relative_to(RACINE)}")
    _evt("drapeau", chemin=str(drapeau_finaliser))

    # --- Reprise : ce qui porte deja une mesure ne se refait pas -------------------------
    # 🔴 `meilleur_seel` EST HISSE ICI, ET C'EST UNE REPARATION. Il vivait plus bas, dans la
    # boucle : une campagne dont TOUTES les graines etaient deja mesurees le laissait vide,
    # donc l'ecart provisoire -> definitif -- le canal de malediction du vainqueur qu'on publie
    # a chaque campagne -- etait SILENCIEUSEMENT saute. Or le cas de reprise est le plus
    # frequent : c'est celui de la validation du 2026-08-22.
    meilleur_seel: float | None = None
    fait: dict[int, dict] = {}
    for g in graines:
        art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, g))
        if art is not None:
            fait[g] = art
            dep = _deposables(art)
            print(f"  ⏭  graine {g} DEJA MESUREE -- {len(dep)} deposable(s)")
            if dep:
                seel_deja = _seel(dep[0]["score"])
                if meilleur_seel is None or seel_deja < meilleur_seel:
                    meilleur_seel = seel_deja
            _evt("deja", graine=g, deposables=len(dep),
                 seel=_seel(dep[0]["score"]) if dep else None)
    a_faire = [g for g in graines if g not in fait]
    if fait:
        print()

    if a.dry_run:
        print(f"  [dry-run] a lancer : {a_faire}")
        print(f"  [dry-run] duree attendue {a.duree_attendue:g} min -> "
              f"{int(a.budget // max(a.duree_attendue, 1e-9)) * slots} run(s) tiennent dans le budget")
        return 0

    # --- La boucle -----------------------------------------------------------------------
    t0 = time.monotonic()
    duree_reelle: float | None = None
    en_vol: dict[int, tuple[subprocess.Popen, float]] = {}
    jamais_lancees: list[int] = []
    lances = 0
    succes = False
    raison_finalisation = ""

    # 🔑 L'ARRET A LA MAIN, ET IL DOIT MARCHER DEPUIS UNE AUTRE FENETRE. 👤 veut pouvoir
    # arreter « a tout moment si on lui annonce un SEEL qui lui convient ». Un Ctrl-C ne
    # suffit pas : la campagne peut tourner la nuit, detachee du terminal. Ce fichier-ci est
    # donc le vrai bouton -- il peut etre cree par l'utilisateur, par un script, ou plus tard
    # par un bouton d'interface, sans rien connaitre du processus.
    if a.seel_cible is not None:
        print(f"  🎯 finalisation automatique des qu'un SEEL <= {a.seel_cible:.4f} nm est atteint")
    print()

    def _minutes() -> float:
        return (time.monotonic() - t0) / 60.0

    def _rentre() -> bool:
        """🔴 Le budget gouverne les LANCEMENTS. On ne lance jamais ce qui ne rentre pas.

        🔴 SAUF LE TOUT PREMIER, ET C'EST UNE REPARATION DU 2026-08-22 QUI A COUTE UNE NUIT.
        La campagne de 12 h n'a RIEN lance : avec `--budget 1h` et une duree attendue de 60
        min, le test valait `0,001 + 60 <= 60` -- FAUX D'UN CHEVEU. Douze graines declarees
        « NON LANCEES », zero calcul, et un journal qui avait l'air normal.

        🔑 La regle corrigee : tant que RIEN n'a tourne et que RIEN ne vole, on lance quand
        meme. Un budget sous-estime doit rendre UNE mesure et un depassement DIT -- jamais
        zero mesure en silence. C'est le sens du budget : borner l'ambition, pas interdire
        d'essayer.
        """
        # 🔴 ON COMPTE LES LANCEMENTS, PAS LES SUCCES. Une premiere version gardait sur
        # `fait` -- or `fait` reste vide quand les runs echouent, et le budget ne bornait
        # alors plus RIEN : toutes les graines partaient. C'est un test qui l'a trouve, en
        # simulant des runs qui echouent.
        if not lances:
            return True
        attendue = duree_reelle if duree_reelle is not None else a.duree_attendue
        return _minutes() + attendue <= a.budget

    def _doit_finaliser() -> str:
        return motif_finalisation(
            drapeau=drapeau_finaliser, seel_cible=a.seel_cible, meilleur_seel=meilleur_seel,
            succes=succes, objectif=a.objectif,
        )

    file_attente = list(a_faire)
    try:
        while file_attente or en_vol:
            raison_finalisation = raison_finalisation or _doit_finaliser()
            while file_attente and len(en_vol) < slots and not raison_finalisation:
                if not _rentre():
                    jamais_lancees.extend(file_attente)
                    print(f"  ⏹  budget : {len(file_attente)} graine(s) NON LANCEE(S) -- "
                          f"{_minutes():.0f} min ecoulees, un run en demande "
                          f"~{duree_reelle if duree_reelle is not None else a.duree_attendue:.0f}")
                    file_attente = []
                    break
                g = file_attente.pop(0)
                p = _lancer(a.python, a.composant, a.mode, a.resolution, g,
                            jdir / f"journal_s{g:03d}.log")
                en_vol[g] = (p, time.monotonic())
                lances += 1
                print(f"  ▶  graine {g} lancee a {time.strftime('%H:%M:%S')} (pid {p.pid})")
                _evt("lancee", graine=g, pid=p.pid, ecoulees_min=round(_minutes(), 2))

            if raison_finalisation and file_attente:
                jamais_lancees.extend(file_attente)
                file_attente = []

            # 🔴 FINALISER N'EST PAS TUER, PAR DEFAUT. Un run coupe est une mesure DETRUITE :
            # quatre de 91 min ont ete perdues ainsi le 2026-08-22, a 98,9 % d'avancement. On
            # laisse donc finir ce qui vole -- sauf si 👤 a explicitement demande l'inverse,
            # auquel cas le travail perdu est DIT.
            # 🔑 LE MODE EST RELU A CHAQUE TOUR, parce que 👤 le decide au moment du CLIC et
            # non au lancement : le fichier FINALISER porte « abandonner » ou rien. Le drapeau
            # de ligne de commande reste la valeur par defaut pour un lancement sans pilote.
            mode = mode_finalisation_demandee(drapeau_finaliser) or a.runs_en_vol
            if raison_finalisation and en_vol and mode == "abandonner":
                print(f"  🛑 {raison_finalisation} -- abandon de {sorted(en_vol)} EN VOL, "
                      f"leur travail est PERDU. On passe a l'union et a la notation finale "
                      f"sur ce qui est deja mesure.")
                _evt("abandon", graines=sorted(en_vol))
                for g, (p, _tg) in list(en_vol.items()):
                    p.terminate()

            if not en_vol:
                break

            # 🔴 ON ATTEND LA SORTIE DU PROCESSUS, jamais l'apparition d'un artefact : la sonde
            # l'ecrit AVANT sa synthese.
            time.sleep(5)
            for g, (p, tg) in list(en_vol.items()):
                if p.poll() is None:
                    continue
                del en_vol[g]
                try:
                    p._certus_journal.close()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 -- fermer un journal ne doit rien casser
                    pass
                mins = (time.monotonic() - tg) / 60.0
                if duree_reelle is None and p.returncode == 0:
                    duree_reelle = mins
                    print(f"     📏 duree REELLE mesuree ici : {mins:.0f} min "
                          f"(elle remplace l'estimation de {a.duree_attendue:.0f})")
                art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, g))
                if p.returncode != 0 or art is None:
                    # 🔴 Un echec se DIT et n'arrete pas la campagne : les autres graines
                    # gardent leur valeur.
                    print(f"  🔴 graine {g} EXIT={p.returncode} en {mins:.0f} min, sans mesure "
                          f"exploitable -- cherche « WAIT_TIMEOUT= » dans son journal")
                    continue
                fait[g] = art
                dep = _deposables(art)
                if not dep:
                    print(f"  ❌ graine {g} : aucun deposable en {mins:.0f} min")
                    _evt("finie", graine=g, deposables=0, seel=None, minutes=round(mins, 1))
                    continue
                succes = True
                seel = _seel(dep[0]["score"])
                if meilleur_seel is None or seel < meilleur_seel:
                    meilleur_seel = seel
                # 🔑 L'ANNONCE VIVANTE, ET SA RESERVE DANS LA MEME LIGNE. C'est sur ce chiffre
                # que 👤 decide d'arreter, il doit donc porter ce qu'il vaut : il est mesure
                # sur la graine QUI L'A TROUVE. Le chiffre citable vient de la notation finale
                # sur une graine disjointe -- ecart mesure +0,55 %, canal mesure a +12,9 %.
                print(f"  ✅ graine {g} : {len(dep)} deposable(s) · SEEL {seel:.4f} nm "
                      f"({dep[0]['n_blocs']} blocs, plantage {100 * dep[0]['crash_rate']:.2f} %) "
                      f"en {mins:.0f} min   [PROVISOIRE -- note sur sa propre graine]")
                _evt("finie", graine=g, deposables=len(dep), seel=seel,
                     n_blocs=dep[0]["n_blocs"], crash=dep[0]["crash_rate"],
                     minutes=round(mins, 1), provisoire=True)

            raison_finalisation = raison_finalisation or _doit_finaliser()
    except KeyboardInterrupt:
        # 🔑 Ctrl-C N'EST PAS UNE PERTE. Ce qui est deja mesure porte un artefact sur disque ;
        # on enchaine donc sur la synthese et la notation finale au lieu de tout jeter.
        raison_finalisation = raison_finalisation or "Ctrl-C"
        jamais_lancees.extend(file_attente)
        print(f"\n  🛑 Ctrl-C -- {len(en_vol)} run(s) en vol abandonne(s), "
              f"{len(fait)} mesure(s) conservee(s)")
        for g, (p, _tg) in list(en_vol.items()):
            p.terminate()
        en_vol.clear()

    if raison_finalisation:
        print(f"\n  🛑 arret : {raison_finalisation}")

    # --- Synthese ------------------------------------------------------------------------
    print()
    print("=" * 78)
    par_graine = {g: _deposables(art) for g, art in sorted(fait.items())}
    qui_trouvent = {g: d for g, d in par_graine.items() if d}
    print(f"  {len(qui_trouvent)} graine(s) sur {len(par_graine)} mesuree(s) ont trouve · "
          f"{_minutes():.0f} min ecoulees sur un budget de {a.budget:.0f}")
    if jamais_lancees:
        # 🔴 Ce qui n'a pas ete essaye se DIT. Sans cette ligne, « 0 trouve » se lirait comme
        # « ca ne marche pas » alors que ce serait « on n'a pas eu le temps ».
        print(f"  ⚠️  NON ESSAYEES faute de budget : {sorted(set(jamais_lancees))}")
    if not qui_trouvent:
        print("  Aucune realisation n'a trouve. Ce n'est PAS « c'est impossible » : "
              "c'est « pas dans ce budget, sur ces graines ».")
        utile, raison = verdict_multitemoin(par_graine, len(par_graine))
        print()
        print(f"  🔬 MULTI-TEMOIN : {raison}")
        if utile and a.multitemoin:
            # 🔴 LE GARDE-FOU, AVANT DE DEPENSER TROIS RUNS. Il lit l'amorce de defaillance
            # dans les artefacts DEJA ECRITS : si elle est en amont de la coupure la moins
            # profonde possible, aucune partition ne peut l'atteindre.
            strats = [x for art in fait.values() for x in (art.get("strategies") or [])]
            amorce = amorce_defaillance(strats)
            peut, pourquoi = multitemoin_peut_agir(_n_couches(a.composant), amorce,
                                                   int(a.multitemoin))
            print(f"  🔬 AMORCE DE DEFAILLANCE : couche {amorce if amorce is not None else '?'} "
                  f"(mediane sur {len(strats)} strategies)")
            _evt("amorce", couche=amorce, peut_agir=peut, raison=pourquoi)
            if not peut:
                print(f"  ⏹  {pourquoi}")
                _evt("fin", trouve=False, multitemoin_utile=False,
                     non_essayees=sorted(set(jamais_lancees)))
                return 1
            code_mt = _escalade_multitemoin(a, jdir)
            _evt("fin", trouve=False, multitemoin=True,
                 non_essayees=sorted(set(jamais_lancees)))
            return code_mt
        if utile:
            print("     Relance avec --multitemoin 3 pour l'essayer.")
        _evt("fin", trouve=False, multitemoin_utile=utile,
             non_essayees=sorted(set(jamais_lancees)))
        return 1

    _utile_mt, _raison_mt = verdict_multitemoin(par_graine, len(par_graine))
    print(f"  🔬 MULTI-TEMOIN : {_raison_mt}")
    _evt("multitemoin", utile=_utile_mt, raison=_raison_mt)

    plans, ecartes = unir_en_tourniquet(qui_trouvent, a.max_plans)
    if ecartes:
        print(f"  ⚠️  plafond --max-plans={a.max_plans} : {ecartes} plan(s) unique(s) ECARTE(S)")
    chemin = RACINE / "reports" / "plans" / f"plans_union_{a.composant}_{stamp}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  union en tourniquet : {len(plans)} plan(s) -> {chemin.relative_to(RACINE)}")
    _evt("union", plans=len(plans), ecartes=ecartes, graines=sorted(qui_trouvent))

    print()
    print(f"  ▶  NOTATION FINALE sur la graine {a.graine_notation}, DISJOINTE des graines de "
          f"generation")
    print("     (garde anti-malediction du vainqueur -- cout mesure +0,55 %)")
    _evt("notation", graine=a.graine_notation)
    tag = f"union{stamp}"
    p = _lancer(
        a.python, a.composant, a.mode, a.resolution, a.graine_notation,
        jdir / f"journal_notation_s{a.graine_notation:03d}.log",
        env_sup={
            "CERTUS_PROBE_OVERRIDES": f"injected_strategies={chemin.relative_to(RACINE).as_posix()}",
            # 🔴 L'etiquette est OBLIGATOIRE des qu'il y a une surcharge : sans elle, deux
            # configurations differentes rendraient deux artefacts indiscernables.
            "CERTUS_PROBE_TAG": tag,
        },
    )
    p.wait()
    try:
        p._certus_journal.close()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, a.graine_notation, tag))
    if art is None:
        print(f"  🔴 la notation finale n'a pas rendu de mesure (EXIT={p.returncode}).")
        return 1
    dep = _deposables(art)
    print()
    print("=" * 78)
    if not dep:
        _evt("fin", trouve=False, raison="aucun plan de l'union ne tient a la notation")
        print("  🔴 AUCUN plan de l'union ne tient a la notation sur une graine disjointe.")
        print("     Les deposables trouves etaient donc propres a leur realisation.")
        return 1
    best = dep[0]
    seel = _seel(best["score"])
    print(f"  🟢 RESULTAT CITABLE : SEEL {seel:.4f} nm · {best['n_blocs']} blocs · "
          f"plantage {100 * best['crash_rate']:.2f} % · {len(dep)} deposable(s)")
    print(f"     trouve par {sorted(qui_trouvent)} · note sur {a.graine_notation}, disjointe")
    print(f"     artefact : reports/{_nom_artefact(a.composant, a.mode, a.graine_notation, tag)}")
    if meilleur_seel is not None:
        # 🔑 CE DELTA EST LE CANAL DE MALEDICTION DU VAINQUEUR, MESURE A CHAQUE CAMPAGNE. Il
        # valait +12,9 % le 2026-08-15 et +0,55 % le 2026-08-22 : ce n'est donc pas une
        # constante, et le publier a chaque fois evite de le supposer petit.
        ecart = 100.0 * (seel - meilleur_seel) / meilleur_seel
        print(f"     annonce en cours de campagne {meilleur_seel:.4f} nm -> "
              f"apres notation disjointe {seel:.4f} nm   ({ecart:+.2f} %)")
        if ecart > 2.59:
            print("     ⚠️  l'ecart depasse le bruit de 2,59 % sur une DIFFERENCE de SEEL : "
                  "le chiffre annonce en cours de route etait OPTIMISTE.")
    _evt("resultat", seel=seel, n_blocs=best["n_blocs"], crash=best["crash_rate"],
         deposables=len(dep), graine_notation=a.graine_notation,
         seel_provisoire=meilleur_seel, graines_trouvees=sorted(qui_trouvent),
         artefact=_nom_artefact(a.composant, a.mode, a.graine_notation, tag))
    _evt("fin", trouve=True, non_essayees=sorted(set(jamais_lancees)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
