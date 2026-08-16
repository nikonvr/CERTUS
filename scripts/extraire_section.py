"""Extrait une section de CLAUDE.md vers docs/, et laisse un renvoi a sa place.

    .venv\\Scripts\\python.exe scripts\\extraire_section.py --section "## 25." \\
        --vers docs/CHANTIER_MULTITEMOINS.md --titre "..." --resume resume.txt

👤 2026-08-16 : *« CLAUDE.md fait 5413 lignes, je pense que c'est inefficace car les IA ne
lisent pas forcement tout et il peut y avoir des contradictions. Comment l'epurer ? »*

🔑 LE DIAGNOSTIC, ET IL N'EST PAS « C'EST TROP LONG ». Le fichier melange quatre natures de
contenu qui n'ont pas la meme frequence de lecture : des DIRECTIVES (lues chaque session),
un ETAT COURANT (lu chaque session), un JOURNAL DE CAMPAGNE (lu quand on touche le sujet) et
des INVESTIGATIONS CLOSES (lues pour ne pas les refaire). Les deux dernieres categories font
environ 60 % du fichier et sont avalees a chaque demarrage sans etre utiles.

🔴 ET LA CAUSE RACINE DES CONTRADICTIONS EST LA : le meme fait est enonce a plusieurs
endroits. Quand la mesure change, on en corrige un seul. Le 2026-08-16, corriger le SEEL du
99c a demande SEPT modifications a la main, et une avait ete oubliee au premier passage.
Extraire force la regle : **un fait, un seul endroit, des renvois partout ailleurs.**

⚠️ CE SCRIPT NE RESUME RIEN TOUT SEUL. Le resume laisse en place est fourni par l'appelant,
qui a lu la section. Un resume genere mecaniquement dirait ce que la section CONTIENT, pas ce
qu'un agent doit en RETENIR -- et c'est la seule chose qui merite de rester.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "CLAUDE.md"


def bornes(lines: list[str], prefixe: str) -> tuple[int, int]:
    """Indices [debut, fin) de la section dont le titre commence par `prefixe`."""
    debut = None
    for i, l in enumerate(lines):
        if l.startswith(prefixe):
            if debut is not None:
                raise SystemExit(f"prefixe ambigu, {prefixe!r} apparait deux fois (l. {debut+1} et {i+1})")
            debut = i
    if debut is None:
        raise SystemExit(f"section introuvable : {prefixe!r}")
    fin = len(lines)
    for j in range(debut + 1, len(lines)):
        if lines[j].startswith("## "):
            fin = j
            break
    # on avale le separateur '---' qui precede la section suivante
    k = fin - 1
    while k > debut and lines[k].strip() in ("", "---"):
        k -= 1
    return debut, k + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True, help='prefixe du titre, ex "## 25."')
    ap.add_argument("--vers", required=True, help="chemin du fichier docs/ de destination")
    ap.add_argument("--resume", required=True,
                    help="fichier texte contenant le renvoi a laisser dans CLAUDE.md")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lines = open(DOC, encoding="utf-8").read().split("\n")
    a, b = bornes(lines, args.section)
    bloc = lines[a:b]
    titre = bloc[0].lstrip("# ").strip()
    resume = open(args.resume, encoding="utf-8").read().rstrip("\n")

    dest = ROOT / args.vers
    entete = [
        f"# {titre}",
        "",
        f"> Extrait de `CLAUDE.md` le {date.today().isoformat()}. Ce contenu **fait autorite** ;",
        "> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges",
        "> quelque chose ici, ne le recopie pas ailleurs, mets un lien.",
        "",
        "---",
        "",
    ]
    corps = entete + bloc[1:]

    print(f"section  : {titre[:70]}")
    print(f"lignes   : {a+1} a {b}  ({b-a} lignes)")
    print(f"vers     : {args.vers}")
    print(f"restant  : {len(lines) - (b - a) + len(resume.split(chr(10)))} lignes dans CLAUDE.md")
    if args.dry_run:
        print("\n--dry-run : rien ecrit.")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(dest) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(corps).rstrip("\n") + "\n")
    os.replace(tmp, dest)

    neuf = lines[:a] + resume.split("\n") + lines[b:]
    tmp = str(DOC) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(neuf).rstrip("\n") + "\n")
    os.replace(tmp, DOC)
    print(f"\nfait. CLAUDE.md : {len(neuf)} lignes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
