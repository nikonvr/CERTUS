"""LES LEVIERS DE RATE ET DE MULTI-TEMOIN -- un registre, et un seul.

## POURQUOI CE FICHIER EXISTE

👤, 2026-08-22 : *« améliore strat avec toutes les subtilités du rate et du multi témoin pour
une version ultra complète »*.

📏 L'audit du meme jour a trouve que la production n'utilise presque RIEN du savoir accumule :
`rate_by_swing` ecrit, teste et **eteint** ; `rate_tail_sweep` -- celui-la meme qui rend le
`r75x2` fabricable a 2 nm -- **eteint** ; le multi-Rate outille le 18/08 et **inerte**. Tout est
derriere un drapeau a `False`, et rien dans l'interface ne le disait.

## 🔴 CE QUE « ULTRA COMPLETE » NE PEUT PAS VOULOIR DIRE

**Tout allumer par defaut.** Chaque levier CHANGE LA RECHERCHE : les activer invaliderait en
silence toute comparaison avec les mesures existantes -- et ce depot compte ses mesures en
journees de calcul. Le dossier a d'ailleurs ecrit les criteres d'acceptation A L'AVANCE pour
plusieurs d'entre eux ; les allumer sans les appliquer les gaspillerait.

**Ultra complete veut donc dire : chaque levier ATTEIGNABLE, VISIBLE, et accompagne de ce que
la mesure en dit.** L'utilisateur arme en connaissance de cause, ou n'arme pas.

## 🔑 ET CE REGISTRE EST LA SOURCE UNIQUE

Il est lu par l'interface (pour construire le panneau) ET par les tests (qui confrontent chaque
`defaut` declare ici a la valeur REELLE du noyau). Un defaut qui changerait dans
`certus_strat_robustness.py` sans changer ici ferait **echouer un test** : l'interface ne peut
donc pas mentir sur ce que la production fait.

C'est la meme regle que le reste du depot -- *un fait, un seul endroit* -- appliquee a des
reglages dont l'utilisateur ne peut pas verifier l'effet a l'oeil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 🟢 mesure a l'appui, l'armer est defendable
VALIDE = "valide"
#: 🟠 mesure a l'appui, mais une reserve connue -- lire `reserve` avant d'armer
RESERVE = "reserve"
#: 🔵 ecrit et teste, JAMAIS mesure en production -- armer, c'est ouvrir une mesure
NON_MESURE = "non_mesure"
#: 🔒 outil de dernier recours : mesure comme NUISIBLE hors de son cas d'emploi
DERNIER_RECOURS = "dernier_recours"


@dataclass(frozen=True)
class Levier:
    """Un reglage, sa valeur de production, et ce que la mesure en dit."""

    cle: str
    libelle: str
    #: La valeur EFFECTIVE en production. 🔴 Confrontee au noyau par un test.
    defaut: Any
    #: `bool`, `int`, `float` ou `liste` (chaine separee par des `;`).
    genre: str
    statut: str
    #: Ce que la mesure etablit. Une phrase, avec ses chiffres.
    mesure: str
    #: Ce qu'il faut savoir AVANT d'armer. Vide si rien.
    reserve: str = ""
    #: Le critere d'acceptation ecrit d'avance, quand le dossier en pose un.
    critere: str = ""
    famille: str = "rate"
    #: Constantes du noyau non atteignables par configuration.
    constante: bool = False


#: 🔴 CHAQUE `defaut` CI-DESSOUS EST CONFRONTE AU NOYAU PAR
#: `tests/unit/test_strat_leviers.py`. Ne pas le modifier sans modifier le noyau, et
#: reciproquement.
LEVIERS: tuple[Levier, ...] = (
    # ---------------------------------------------------------------- RATE : le mecanisme
    Levier(
        cle="allow_rate",
        libelle="Autoriser le Rate (quartz / chrono)",
        defaut=True,
        genre="bool",
        statut=VALIDE,
        mesure="ON par defaut depuis le 2026-08-12, sur demande de 👤 : « add that rate is "
               "always allowed ». Chaque survivante est etendue en variantes portant une couche "
               "pilotee au quartz, et le classement les compare COTE A COTE avec le pur optique.",
        reserve="En mode Rate il n'y a AUCUNE compensation d'erreur : l'ecart part en boucle "
                "ouverte vers la couche suivante. Une gagnante qui porte un Rate n'est pas la "
                "meme promesse pour l'atelier qu'une gagnante en pur optique.",
    ),
    # ---------------------------------------------------------------- RATE : le placement
    Levier(
        cle="rate_by_swing",
        libelle="Placer le Rate ou il est NECESSAIRE (swing faible)",
        defaut=True,
        genre="bool",
        statut=VALIDE,
        mesure="Contradiction C de l'audit : « le placement cherche ou le Rate COUTE le moins, "
               "jamais ou il est NECESSAIRE ». Le critere de besoin est `swing < SWING_MIN`. "
               "Ecrit et teste le 2026-08-19 ; les deux criteres se PARTAGENT le plafond, ils "
               "ne s'evincent pas.",
        reserve="🟢 ARME PAR DEFAUT LE 2026-08-22. C'est sur, parce qu'une variante Rate entre "
                "comme COUT et jamais comme COUPERET : elle S'AJOUTE a un classement qui "
                "contient deja le pur optique. Le seul canal de nuisance etait le plafond "
                "partage -- repare dans le meme commit. ⚠️ Le cout CPU, lui, n'est pas mesure : "
                "~65 000 evaluations TMM sur le 75c.",
        critere="Rejouer `75c a 1 nm` -- la cellule ou le Rate gagne deja -- et compter les "
                "deposables Rate. Le placement par besoin doit faire MIEUX QUE 10/12, sinon la "
                "frontiere de bloc suffisait.",
    ),
    Levier(
        cle="dynamics_threshold",
        libelle="Seuil de swing : sous lui, une couche a BESOIN du Rate",
        defaut=0.025,
        genre="float",
        statut=RESERVE,
        mesure="L'amplitude T_max - T_min pendant la croissance de la couche. 🔴 Ce n'est PAS "
               "un critere d'epaisseur -- une couche de 30 nm a faible contraste d'indice a "
               "une dynamique aussi pauvre qu'une ultrafine.",
        reserve="🔴 IL SERT A DEUX ETAGES A LA FOIS, et c'est delibere : la Phase A l'emploie "
                "pour FILTRER les longueurs d'onde candidates, le placement Rate pour designer "
                "les couches qui ont BESOIN d'un quartz. Le baisser elargit les deux ; "
                "l'augmenter les restreint tous les deux. Un reglage, deux effets -- ne pas "
                "l'ajuster pour le Rate sans regarder ce qu'il fait a la Phase A.",
    ),
    # ---------------------------------------------------------------- RATE : les plafonds
    Levier(
        cle="rate_max_variants_per_strategy",
        libelle="Variantes Rate par strategie",
        defaut=40,
        genre="int",
        statut=VALIDE,
        mesure="Contradiction A : le plafond cite « l'essai sur les 10 meilleures » et etend "
               "en fait TOUTES les strategies a 3 variantes -- donc ni l'un ni l'autre. Cout "
               "mesure : 12 923 variantes Rate produites, dont 20 deposables.",
        reserve="🟢 PORTE DE 3 A 40 LE 2026-08-22, avec `rate_variant_top_n = 50`. Les deux "
                "vont ENSEMBLE : 2 000 evaluations au lieu de 12 923, treize fois plus "
                "profondement par parent. Moins cher ET plus profond -- c'est ce qui fait de "
                "la place au critere par swing sans evincer les frontieres de bloc.",
    ),
    Levier(
        cle="rate_variant_top_n",
        libelle="Strategies recevant des variantes Rate (les mieux classees)",
        defaut=50,
        genre="int",
        statut=VALIDE,
        mesure="Reparation de la contradiction A, 2026-08-22. Le plafond citait « l'essai sur "
               "les 10 meilleures » et etendait en fait TOUTES les strategies -- donc ni la "
               "consigne, ni son contraire. On etend desormais PROFONDEMENT les meilleures au "
               "lieu de PLATEMENT toutes.",
        reserve="🔒 `0` retablit le comportement d'avant : toutes les strategies etendues.",
    ),
    Levier(
        cle="rate_max_layers_per_variant",
        libelle="Couches Rate par variante (multi-Rate)",
        defaut=1,
        genre="int",
        statut=NON_MESURE,
        mesure="Outille le 2026-08-18. A 1, c'est le chemin historique AU BIT PRES.",
        reserve="Au-dela de 1, le nombre de variantes explose combinatoirement. Jamais mesure "
                "en production.",
    ),
    # ---------------------------------------------------------------- RATE : la queue
    Levier(
        cle="rate_tail_sweep",
        libelle="Queue Rate (hybride optique-puis-Rate)",
        defaut=None,
        genre="liste",
        statut=RESERVE,
        mesure="🟢 §3bis : « l'hybride optique-puis-Rate rend le ×2 FABRICABLE a 2 nm ». La ou "
               "le pur optique rend 0 deposable a 100 % de plantage, la queue Rate en rend 3 a "
               "SEEL 0,6859. 📏 Cause univoque : 100 % des plantages sont « niveau d'arret hors "
               "d'atteinte », zero « comptage de points tournants » -- c'est la DERIVE "
               "ACCUMULEE. Franchir la zone en boucle ouverte l'evite.",
        reserve="🔴 C'EST UNE AFFAIRE DE 2 nm. A 1 nm, le pur optique la BAT. Et le SEEL "
                "obtenu (0,68-0,69) est +18 % au-dessus de la voie avec rampes.",
    ),
    # ---------------------------------------------------------------- RATE : les constantes
    Levier(
        cle="RATE_MIN_LAYER",
        libelle="Premiere couche ou le Rate est permis",
        defaut=2,
        genre="int",
        statut=VALIDE,
        mesure="👤 2026-08-19 : « rate est interdit sur les 2 premieres couches, mais "
               "absolument pas la derniere ». 🔑 La borne a une RAISON PHYSIQUE et elle donne "
               "exactement 2 : le facteur de rate se calcule sur les couches de MEME PARITE "
               "deposees avant ; pour i = 0 et 1 cette boucle est vide, `n_ref = 0`.",
        reserve="🔴 Avant la correction, le noyau retombait SILENCIEUSEMENT sur POEM : une "
                "variante etiquetee `RATE_L1` simulait du POEM pur. Deux resultats portaient "
                "une etiquette qui mentait sur ce qui avait tourne.",
        constante=True,
    ),
    Levier(
        cle="RATE_MIN_LAYERS_PER_BLOCK",
        libelle="Couches par bloc minimales pour offrir le Rate",
        defaut=3.0,
        genre="float",
        statut=RESERVE,
        mesure="Contradiction B : rend ZERO candidate aux strategies dont les blocs font moins "
               "de 3 couches. Une strategie qui surveille COUCHE PAR COUCHE n'a donc jamais eu "
               "une seule variante Rate.",
        reserve="🔴 Or §24-40 a mesure que le monitoring couche par couche GAGNE sur 2 graines "
                "sur 5. Le regime que la mesure designe comme gagnant est celui dont le Rate "
                "est exclu par construction. ⚠️ La raison de l'exclusion est bonne et il ne faut "
                "pas la perdre : sur 48 blocs chaque couche est une frontiere, et la selection "
                "degenere en balayage exhaustif -- cout Monte-Carlo x6.",
        constante=True,
    ),
    # ---------------------------------------------------------------- MULTI-TEMOIN
    Levier(
        cle="witness_reset_layers",
        libelle="Couches ou un verre temoin NEUF entre",
        defaut=None,
        genre="liste",
        statut=DERNIER_RECOURS,
        mesure="🔒 OUTIL DE FAISABILITE, JAMAIS D'OPTIMISATION. Controle negatif passe sur "
               "TROIS composants monitorables : 48c +73 a +89 % (11/11 partitions), 35c +10 a "
               "+98 % (12/12), 75c aleatoire +110 % (0,272 -> 0,571 nm). AUCUNE partition ne "
               "gagne, meme par chance. Il RETIRE de la compensation sans rien restaurer.",
        reserve="🔴 A n'armer que si AUCUNE realisation ne trouve -- et le verdict se prend "
                "APRES le multiseed, jamais avant. Sur `r75x2`, quatre graines rendaient zero "
                "avant que la 404 n'en trouve 372 : l'armer alors aurait degrade de ~110 % un "
                "composant qui n'avait aucun probleme. ⚠️ Ou couper importe peu -- etendue de "
                "+14,4 % sur 440 partitions du 99c, l'optimum est PLAT.",
        famille="temoin",
    ),
)

#: Index par cle, pour les lectures ponctuelles.
PAR_CLE: dict[str, Levier] = {lv.cle: lv for lv in LEVIERS}

#: Les libelles courts des statuts, pour l'interface.
LIBELLE_STATUT: dict[str, str] = {
    VALIDE: "🟢 valide",
    RESERVE: "🟠 mesure, avec reserve",
    NON_MESURE: "🔵 jamais mesure en production",
    DERNIER_RECOURS: "🔒 dernier recours -- nuisible hors de son cas",
}


def leviers_de(famille: str) -> tuple[Levier, ...]:
    return tuple(lv for lv in LEVIERS if lv.famille == famille)


def surcharges_non_defaut(valeurs: dict[str, Any]) -> dict[str, Any]:
    """Ce qui s'ecarte de la production, et rien d'autre.

    🔑 Sert a construire `CERTUS_PROBE_OVERRIDES` : un levier laisse a son defaut ne doit PAS
    entrer dans la surcharge, sinon l'artefact porterait une etiquette et se croirait different
    d'un run nominal -- alors qu'il en serait le jumeau. Ce depot a deja perdu des mesures pour
    des artefacts indiscernables.
    """
    out: dict[str, Any] = {}
    for cle, val in valeurs.items():
        lv = PAR_CLE.get(cle)
        if lv is None or lv.constante:
            continue
        if val in (None, "", []) and lv.defaut in (None, "", []):
            continue
        if val != lv.defaut:
            out[cle] = val
    return out


__all__ = [
    "DERNIER_RECOURS",
    "LEVIERS",
    "LIBELLE_STATUT",
    "NON_MESURE",
    "PAR_CLE",
    "RESERVE",
    "VALIDE",
    "Levier",
    "leviers_de",
    "surcharges_non_defaut",
]
