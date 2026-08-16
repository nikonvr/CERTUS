"""Reordonne et renumerote les sections de CLAUDE.md, et propage dans TOUS les fichiers.

    .venv\\Scripts\\python.exe scripts\\renumeroter.py --dry-run
    .venv\\Scripts\\python.exe scripts\\renumeroter.py

👤 2026-08-16 : *« n'hesite pas a renumeroter les sections et les hierarchiser »*.

🔴 CE QUI ETAIT CASSE DANS L'ORDRE. §18bis et §18ter arrivaient AVANT §18. Le chantier
COURANT -- le multi-temoins -- etait la DERNIERE section, donc la derniere lue. Les quatre
listes d'interdictions etaient dispersees entre les positions 3, 8, 9 et 24. Une IA qui lit
lineairement rencontrait le programme en cours apres tout le reste.

🔑 LA NOUVELLE HIERARCHIE suit l'ordre dans lequel un agent en a BESOIN :

    PARTIE I   AVANT DE TOUCHER A QUOI QUE CE SOIT   -- regles, interdits, environnement
    PARTIE II  LE SAVOIR                             -- physique, machine, constantes, reperes
    PARTIE III L'ETAT DU PROJET                      -- chantier courant EN TETE, puis defauts
    PARTIE IV  LES DOSSIERS DE docs/                 -- renvois

⚠️ 468 RENVOIS `§N` EXISTENT DANS 12 FICHIERS. Les renumeroter a la main est impossible sans
erreur ; ce script applique la table de correspondance PARTOUT, en une passe, avec un jeton
intermediaire pour qu'un numero deja remplace ne le soit pas une seconde fois. Le controle B
de `check_claude_md.py` verifie ensuite qu'aucun renvoi ne pointe dans le vide.

🔴 LES SOUS-RENVOIS SONT PRESERVES. `§17-41` devient `§NN-41`, `§12.3` devient `§NN.3` : seul
le numero de section change, le suffixe est intact. C'est ce qui permet aux renvois vers les
sous-sections extraites dans docs/ de rester lisibles.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: (prefixe de titre actuel, nouveau numero, partie). L'ordre de cette liste EST le nouvel
#: ordre du document. Les sections sans numero (les "⚡") en recoivent un.
PLAN = [
    ("# PARTIE I — AVANT DE TOUCHER À QUOI QUE CE SOIT", None, True),
    ("## 🔒 La règle des documents", "1", False),
    ("## ⚡ DÉMARRAGE", "2", False),
    ("## ⚡ CARTE DU DOCUMENT", "3", False),
    ("## 0. Vérifier l'environnement", "4", False),
    ("## ⚡ LES 7 ERREURS", "5", False),
    ("## 1. Les onze interdits absolus", "6", False),
    ("## 2. Les sept pièges", "7", False),
    ("## 16. Ce qu'il ne faut PAS faire", "8", False),
    ("## 3. La boucle de travail", "9", False),
    ("## 4. Quand s'arrêter et demander", "10", False),
    ("## 19. Règles de tenue de ce document", "11", False),
    ("## 20. Protocole de re-vérification", "12", False),

    ("# PARTIE II — LE SAVOIR", None, True),
    ("## 5. Ce qu'est CERTUS", "13", False),
    ("## 7. Vocabulaire", "14", False),
    ("## 8. Le cadre", "15", False),
    ("## 6. 🔴 Conventions physiques", "16", False),
    ("## 9. 👤 La machine réelle", "17", False),
    ("## 9bis. 🔒 LE MODÈLE DE LA CHAÎNE DE LECTURE", "18", False),
    ("## ⚡ TU NE DÉCIDES RIEN", "19", False),
    ("## 11. Les quatre paramètres du modèle", "20", False),
    ("## 10. Points de référence", "21", False),
    ("## 14. 👤 Les règles gravées", "22", False),

    ("# PARTIE III — L'ÉTAT DU PROJET", None, True),
    ("## 25. 🔴 MULTIPLE TESTGLASS METHODOLOGY", "23", False),
    ("## 17. Défauts ouverts", "24", False),
    ("## 13. Décisions ouvertes et tranchées", "25", False),
    ("## 15. 🔴 La validation externe", "26", False),
    ("## 18. Autres chantiers ouverts", "27", False),

    ("# PARTIE IV — LES DOSSIERS DE `docs/`", None, True),
    ("## ⚡ FEUILLE DE ROUTE", "28", False),
    ("## 12. Le travail à venir sur le MODÈLE PHYSIQUE", "29", False),
    ("## 18bis. 🔴 ÉTAT RÉEL DE L'IMPLANTATION", "30", False),
    ("## 18ter. ⚡ PERFORMANCE", "31", False),
    ("## 21. Les composants d'essai", "32", False),
    ("## 22-23. Décisions tranchées", "33", False),
    ("## 24. 💡 A25, A26, A27", "34", False),
]

#: ancien numero -> nouveau. Deduit de PLAN, plus les cas sans numero d'origine.
MAP = {
    "0": "4", "1": "6", "2": "7", "3": "9", "4": "10", "5": "13", "6": "16",
    "7": "14", "8": "15", "9": "17", "9bis": "18", "10": "21", "11": "20",
    "12": "29", "13": "25", "14": "22", "15": "26", "16": "8", "17": "24",
    "18": "27", "18bis": "30", "18ter": "31", "19": "11", "20": "12",
    "21": "32", "22": "33", "23": "33", "23bis": "33", "23ter": "33",
    "24": "34", "25": "23",
}


#: 🔴 LISTE BLANCHE, ET C'EST VITAL. Un balayage `docs/*.md` + `pages/*.html` corromprait
#: silencieusement des fichiers dont les `§N` designent LEURS PROPRES sections :
#:
#:   pages/CERTUS_STRAT.html         §2.8, §10.15 -> sa numerotation a elle
#:   pages/CERTUS_METAL_BILAYER.html §5
#:   docs/REPRISE_PERF.md            §1 a §6
#:   docs/PLAN_AMELIORATION.md       §0.3, §4, §7
#:   docs/REPRISE_TESTS_ISOLATION.md §2, §2.1
#:
#: Ne figurent ici que les fichiers dont les renvois pointent vers CLAUDE.md : celui-ci, les
#: dossiers EXTRAITS de lui (qui ont herite de ses renvois), et les deux documents ecrits en
#: le citant. Verifie qu'un fichier appartient bien a cette categorie AVANT de l'ajouter.
CIBLES = [
    "CLAUDE.md",
    "docs/CHANTIER_MULTITEMOINS.md",
    "docs/TRAVAUX_A_VENIR.md",
    "docs/FEUILLE_DE_ROUTE.md",
    "docs/MODE_RATE.md",
    "docs/DECISIONS_TRANCHEES.md",
    "docs/COMPOSANTS.md",
    "docs/PERFORMANCE.md",
    "docs/ETAT_IMPLANTATION.md",
    "docs/RESERVE_A25_A27.md",
    "docs/QWOT_ET_TURNING_POINT.md",
    "docs/REPRISE.md",
    "docs/PLAN_2026-08-16.md",
]


def decouper(lines: list[str]) -> dict[str, list[str]]:
    """prefixe -> bloc de lignes, pour chaque section de PLAN."""
    pos = []
    for pref, _num, est_partie in PLAN:
        if est_partie:
            continue
        idx = [i for i, l in enumerate(lines) if l.startswith(pref)]
        if len(idx) != 1:
            raise SystemExit(f"prefixe absent ou multiple ({len(idx)}) : {pref!r}")
        pos.append((idx[0], pref))
    pos.sort()
    blocs = {}
    for k, (i, pref) in enumerate(pos):
        j = pos[k + 1][0] if k + 1 < len(pos) else len(lines)
        # on laisse tomber les titres de PARTIE et les separateurs de fin de bloc
        bloc = [x for x in lines[i:j] if not x.startswith("# PARTIE")]
        while bloc and bloc[-1].strip() in ("", "---"):
            bloc.pop()
        blocs[pref] = bloc
    return blocs


def renumeroter_titre(titre: str, num: str) -> str:
    """Remplace le numero du titre, ou en insere un s'il n'y en avait pas."""
    corps = titre[3:]
    corps = re.sub(r"^\s*\d+(?:bis|ter)?\.\s*", "", corps)
    corps = re.sub(r"^\s*22-23\.\s*", "", corps)
    return f"## {num}. {corps.strip()}"


def propager(mapping: dict[str, str], dry: bool) -> int:
    """Reecrit tous les renvois §N dans tous les fichiers du depot."""
    cibles = CIBLES
    # jeton intermediaire : sans lui, §1 -> §6 puis §6 -> §16 renumeroterait deux fois.
    total = 0
    for f in cibles:
        p = ROOT / f
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        avant = s

        def sub(m: re.Match) -> str:
            anc, suite = m.group(1), m.group(2) or ""
            return f"§\x00{mapping.get(anc, anc)}\x00{suite}"

        s = re.sub(r"§\s*(\d+(?:bis|ter)?)((?:[.‑\-]\d+)?)", sub, s)
        s = s.replace("\x00", "")
        n = sum(1 for a, b in zip(avant.split("§"), s.split("§")) if a != b)
        if s != avant:
            total += 1
            if not dry:
                tmp = str(p) + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="\n") as g:
                    g.write(s)
                os.replace(tmp, p)
            print(f"  {'(dry) ' if dry else ''}{f}")
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = ROOT / "CLAUDE.md"
    lines = doc.read_text(encoding="utf-8").split("\n")
    tete_fin = next(i for i, l in enumerate(lines) if l.startswith("## ") or l.startswith("# PARTIE"))
    tete = lines[:tete_fin]
    blocs = decouper(lines)

    sortie: list[str] = list(tete)
    for pref, num, est_partie in PLAN:
        if est_partie:
            sortie += [pref, ""]
            continue
        bloc = list(blocs[pref])
        bloc[0] = renumeroter_titre(bloc[0], num)
        sortie += bloc + ["", "---", ""]
    while sortie and sortie[-1].strip() in ("", "---"):
        sortie.pop()

    print(f"CLAUDE.md : {len(lines)} -> {len(sortie)} lignes, {len(MAP)} numeros remappes")
    print("\nfichiers touches par la propagation des renvois :")
    if not args.dry_run:
        tmp = str(doc) + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as g:
            g.write("\n".join(sortie).rstrip("\n") + "\n")
        os.replace(tmp, doc)
    n = propager(MAP, args.dry_run)
    print(f"\n{n} fichiers {'seraient modifies' if args.dry_run else 'modifies'}.")
    if args.dry_run:
        print("--dry-run : CLAUDE.md n'a PAS ete reecrit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
