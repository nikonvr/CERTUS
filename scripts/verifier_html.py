"""VERIFIER LA STRUCTURE D'UNE PAGE HTML -- balises appariees, ancres uniques, renvois vivants.

    python scripts/verifier_html.py pages/CERTUS_STRAT.html

🔑 POURQUOI CE CONTROLE EXISTE. La vitrine est le seul document que 👤 juge « ultra
importante », et c'est un fichier de 5 800 lignes edite a la main. Une balise mal fermee n'y
provoque aucune erreur : le navigateur devine, et la page s'affiche -- avec une section
avalee par la precedente, ou un tableau qui absorbe tout ce qui suit. C'est exactement la
famille de panne que ce depot redoute : **ca ne plante pas, ca rend un resultat faux qui a
l'air juste.**

Trois controles :

  1. BALISES APPARIEES -- chaque ouverture a sa fermeture, dans le bon ordre
  2. ANCRES UNIQUES -- deux `id` identiques rendent un lien silencieusement ambigu
  3. RENVOIS INTERNES VIVANTS -- un `href="#sec-X"` qui ne pointe sur rien

Rend 0 si tout tient, 1 sinon.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

#: Elements HTML qui n'ont pas de balise fermante. Les oublier ferait crier le controle sur
#: du HTML parfaitement valide -- un faux positif est aussi couteux qu'un faux negatif, il
#: apprend a ignorer l'outil.
SANS_FERMETURE = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class Verificateur(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.pile: list[tuple[str, int]] = []
        self.erreurs: list[str] = []
        self.ancres: list[tuple[str, int]] = []
        self.renvois: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        d = dict(attrs)
        if d.get("id"):
            self.ancres.append((d["id"], self.getpos()[0]))
        href = d.get("href") or ""
        if href.startswith("#"):
            self.renvois.append((href[1:], self.getpos()[0]))
        if tag not in SANS_FERMETURE:
            self.pile.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in SANS_FERMETURE and self.pile:
            self.pile.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in SANS_FERMETURE:
            return
        if not self.pile:
            self.erreurs.append(f"l.{self.getpos()[0]} : </{tag}> sans ouverture")
            return
        ouvert, ligne = self.pile.pop()
        if ouvert != tag:
            self.erreurs.append(
                f"l.{self.getpos()[0]} : </{tag}> ferme <{ouvert}> ouvert l.{ligne}"
            )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python scripts/verifier_html.py <fichier.html> [...]")
        return 2

    total = 0
    for nom in args:
        chemin = Path(nom)
        if not chemin.is_file():
            print(f"🔴 {nom} : introuvable")
            total += 1
            continue
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        v = Verificateur()
        v.feed(texte)

        points: list[str] = list(v.erreurs)
        for tag, ligne in v.pile:
            points.append(f"l.{ligne} : <{tag}> jamais fermee")

        # 2. ancres uniques
        vues: dict[str, int] = {}
        for ident, ligne in v.ancres:
            if ident in vues:
                points.append(f"l.{ligne} : id « {ident} » deja utilise l.{vues[ident]}")
            else:
                vues[ident] = ligne

        # 3. renvois internes vivants
        for cible, ligne in v.renvois:
            if cible and cible not in vues:
                points.append(f"l.{ligne} : href=\"#{cible}\" ne pointe sur aucune ancre")

        etat = "🟢" if not points else "🔴"
        print(f"{etat} {nom} : {len(texte.splitlines())} lignes · {len(vues)} ancres · "
              f"{len(v.renvois)} renvois internes · {len(points)} point(s)")
        for pt in points[:20]:
            print(f"     {pt}")
        if len(points) > 20:
            print(f"     ... et {len(points) - 20} autre(s)")
        total += len(points)

    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
