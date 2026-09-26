"""THE RATE AND MULTIPLE-TESTGLASS LEVERS -- one registry, and only one.

## WHY THIS FILE EXISTS

👤, 2026-08-22: *"improve strat with all the subtleties of rate and of the multiple testglass
for an ultra complete version"*.

📏 The audit of the same day found that production uses almost NONE of the accumulated
knowledge: `rate_by_swing` written, tested and **switched off**; `rate_tail_sweep` -- the very
one that makes `r75x2` manufacturable at 2 nm -- **switched off**; the multi-Rate tooled on
08-18 and **inert**. Everything is behind a flag set to `False`, and nothing in the interface
said so.

## 🔴 WHAT "ULTRA COMPLETE" CANNOT MEAN

**Switching everything on by default.** Each lever CHANGES THE SEARCH: activating them would
silently invalidate every comparison with the existing measurements -- and this repository
counts its measurements in days of computation. The dossier also wrote the acceptance
criteria IN ADVANCE for several of them; switching them on without applying those criteria
would waste them.

**Ultra complete therefore means: every lever REACHABLE, VISIBLE, and accompanied by what the
measurement says about it.** The user arms knowingly, or does not arm.

## 🔑 AND THIS REGISTRY IS THE SINGLE SOURCE

It is read by the interface (to build the panel) AND by the tests (which confront every
`defaut` declared here with the REAL value of the kernel). A default that changed in
`certus_strat_robustness.py` without changing here would **fail a test**: the interface
therefore cannot lie about what production does.

It is the same rule as the rest of the repository -- *one fact, one place* -- applied to
settings whose effect the user cannot check by eye.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 🟢 backed by a measurement, arming it is defensible
VALIDE = "valide"
#: 🟠 backed by a measurement, but with a known caveat -- read `reserve` before arming
RESERVE = "reserve"
#: 🔵 written and tested, NEVER measured in production -- arming it opens a measurement
NON_MESURE = "non_mesure"
#: 🔒 last-resort tool: measured as HARMFUL outside its use case
DERNIER_RECOURS = "dernier_recours"


@dataclass(frozen=True)
class Levier:
    """A setting, its production value, and what the measurement says about it."""

    cle: str
    libelle: str
    #: The EFFECTIVE value in production. 🔴 Confronted with the kernel by a test.
    defaut: Any
    #: `bool`, `int`, `float` or `liste` (string separated by `;`).
    genre: str
    statut: str
    #: What the measurement establishes. One sentence, with its figures.
    mesure: str
    #: What must be known BEFORE arming. Empty if nothing.
    reserve: str = ""
    #: The acceptance criterion written in advance, when the dossier sets one.
    critere: str = ""
    famille: str = "rate"
    #: Kernel constants that no configuration can reach.
    constante: bool = False


#: 🔴 EVERY `defaut` BELOW IS CONFRONTED WITH THE KERNEL BY
#: `tests/unit/test_strat_leviers.py`. Do not change it without changing the kernel, and
#: vice versa.
LEVIERS: tuple[Levier, ...] = (
    # ---------------------------------------------------------------- RATE: the mechanism
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
    # ---------------------------------------------------------------- RATE: the placement
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
    # ---------------------------------------------------------------- RATE: the caps
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
    # ---------------------------------------------------------------- RATE: the tail
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
    # ---------------------------------------------------------------- RATE: the constants
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
                "composant qui n'avait aucun probleme. ⚠️ OU COUPER N'EST PAS MESURE. Cette "
                "reserve annoncait « ou couper importe peu, l'optimum est PLAT » jusqu'au "
                "2026-08-23 : l'etendue de +14,4 % citee porte sur le SEEL de partitions DEJA "
                "DEPOSABLES (`classer_partitions.py:178` ecarte celles qui plantent avant de "
                "calculer la RMSE). Elle ne dit donc rien du choix d'une coupure quand le "
                "critere est le PLANTAGE. La partition reguliere est un defaut, pas un optimum.",
        famille="temoin",
    ),
)

#: Index by key, for one-off lookups.
PAR_CLE: dict[str, Levier] = {lv.cle: lv for lv in LEVIERS}

#: The short labels of the statuses, for the interface.
LIBELLE_STATUT: dict[str, str] = {
    VALIDE: "🟢 valide",
    RESERVE: "🟠 mesure, avec reserve",
    NON_MESURE: "🔵 jamais mesure en production",
    DERNIER_RECOURS: "🔒 dernier recours -- nuisible hors de son cas",
}


def leviers_de(famille: str) -> tuple[Levier, ...]:
    return tuple(lv for lv in LEVIERS if lv.famille == famille)


def surcharges_non_defaut(valeurs: dict[str, Any]) -> dict[str, Any]:
    """What departs from production, and nothing else.

    🔑 Used to build `CERTUS_PROBE_OVERRIDES`: a lever left at its default must NOT enter
    the override, otherwise the artefact would carry a label and believe itself different
    from a nominal run -- while being its twin. This repository has already lost
    measurements to indistinguishable artefacts.
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
