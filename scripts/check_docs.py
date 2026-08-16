"""Controle MECANIQUE de TOUS les documents du depot -- md et html.

    .venv\\Scripts\\python.exe scripts\\check_docs.py

👤 2026-08-16 : *« fais un controle minutieux des autres fichiers md et html »*.

🔑 POURQUOI UN SECOND OUTIL, ET PAS UNE EXTENSION DU PREMIER. `check_claude_md.py` verifie la
COHERENCE INTERNE d'un seul fichier : ses renvois `§N` pointent-ils vers ses propres sections,
ses valeurs se contredisent-elles. Ce controle-la n'a de sens que la ou une numerotation fait
autorite. Applique a `pages/CERTUS_STRAT.html`, qui a sa PROPRE numerotation, il produirait du
bruit -- et un controle bruyant finit par ne plus etre lu.

Celui-ci verifie ce qui vaut pour TOUS les documents, sans rien savoir de leur structure :

  A. LIENS MORTS -- tout `[texte](chemin)` vers un fichier du depot. Le fichier existe-t-il ?
     Le 2026-08-16, la suppression de `GEMINI_TODO.md` a laisse deux renvois orphelins, et
     l'extraction de neuf sections vers `docs/` en a laisse d'autres.

  B. REFERENCES DE CODE MORTES -- tout `chemin/fichier.py:NNN`. Le fichier existe-t-il, et
     a-t-il seulement NNN lignes ? Un numero de ligne perime envoie un agent lire autre chose
     que ce qu'on lui annonce, ce qui est pire que pas de reference.

  C. CHIFFRES PERIMES -- une liste explicite d'affirmations REFUTEES par la mesure. C'est le
     seul controle qui porte un jugement, et il ne le porte que sur ce qui est ecrit ici
     noir sur blanc. Une ligne qui PORTE sa propre correction (« perime », « refute »,
     « corrige le ») est disculpee : c'est ainsi qu'on garde la trace d'une erreur sans que
     l'outil la signale comme une erreur.

  D. STRUCTURE HTML -- balises non fermees ou fermetures orphelines, au parseur, jamais a
     l'oeil. Le 2026-08-14 un `</ul>` supprime faisait rendre 400 lignes a l'interieur d'une
     liste et avait emporte une puce entiere sans que rien ne le signale.

🔴 CE QU'IL NE SAIT PAS FAIRE : juger si deux phrases se contredisent. Zero ici veut dire zero
defaut MECANIQUE, pas zero contradiction.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Documents controles. Les rapports de campagne de `reports/` sont des SORTIES : ils
#: temoignent de ce qui a ete mesure ce jour-la et ne doivent pas etre reecrits.
CIBLES = (sorted(ROOT.glob("*.md")) + sorted(ROOT.glob("docs/*.md"))
          + sorted(ROOT.glob("pages/*.html")))

#: (motif, ce qui est vrai). Une affirmation refutee par la mesure, citee comme si elle
#: tenait encore. Motifs volontairement etroits : mieux vaut rater un cas que crier a tort.
PERIMES = [
    (re.compile(r"0[.,]760\s*nm"),
     "le 0,760 nm etait biaise vers le bas (N=50). La valeur est 0,782 nm a 4 temoins"),
    (re.compile(r"0[.,]86\d?\s*nm|0[.,]860\s*nm"),
     "le 0,86 nm du 99c est un SCORE DE REPLI : 100 % de plantage, pas une performance"),
    (re.compile(r"espaceurs?[^.]{0,60}swing[^.]{0,20}nul", re.I),
     "refute : les 5 espaceurs offrent 65 a 133 lambda utilisables, 0 couche muette sur 99"),
    (re.compile(r"au-del[aà] d[e']un[e]? cinquantaine de couches", re.I),
     "refute : 75 couches aleatoires se surveillent a 0 % de plantage"),
    (re.compile(r"GEMINI_TODO", re.I),
     "fichier SUPPRIME le 2026-08-16"),
    (re.compile(r"C:\\+dev\\+gemini", re.I),
     "chemin de travail perime"),
    (re.compile(r"seul sous-empilement (?:infaisable|non deposable)", re.I),
     "refute : [22,78) est contredit par [22,99), et AUCUNE_DEPOSABLE != infaisable"),
    # 🔴 Le compte de tests DERIVE en silence. Le 2026-08-16 il valait 2310 a deux endroits
    # et 2450 a quatre autres : une consigne de non-regression qui annonce le mauvais
    # attendu fait passer un ECHEC pour un succes. Motif etroit : seulement la forme
    # « NNNN passed », pas un nombre isole.
    (re.compile(r"\b(?!2450\b)2[0-46-9]\d\d passed"),
     "compte de tests perime : la reference est 2450 passed, 5 skipped "
     "(pytest tests/oracle/ tests/unit/). 2774 est le total de `pytest tests/`, autre perimetre"),
]

#: Une ligne qui porte sa propre correction n'est pas fautive -- c'est meme la bonne facon
#: de garder la trace d'une erreur. Sans ces disculpants, ce controle signalerait les
#: avertissements ecrits exprès pour empecher l'erreur.
#: 🔴 COMPARES EN MINUSCULES, et les deux langues sont couvertes. Trois ratés mesures le
#: 2026-08-16 : « n'est PAS » echappait a « n'est pas » (casse), « périme » echappait a
#: « périmé » (accent final), et toute la vitrine anglophone echappait faute de disculpants
#: en anglais. Un controle qui crie sur ses propres avertissements finit ignore.
DISCULPANTS = ("périm", "perim", "réfut", "refut", "faux", "biais", "corrig",
               "supprim", "caduque", "n'est pas", "score de repli", "ne veut pas dire",
               "was biased", "corrected", "refut", "wrong", "fallback", "not a robustness",
               "never a performance", "least-bad", "obsolete", "superseded")


#: Portee du disculpant, en lignes de part et d'autre. 🔴 Une portee de ZERO -- le controle
#: ligne a ligne -- produit une majorite de faux positifs : un tableau ecrit « 0,860 nm » sur
#: une ligne et « perime » sur la suivante. C'est la FORME NORMALE d'une correction bien
#: ecrite, et un controle qui la signale apprend seulement a etre ignore.
PORTEE = 3

#: Bibliotheques TIERCES citees dans des traces d'execution -- pas des fichiers du depot.
TIERS = {"numba", "llvmlite", "numpy", "scipy", "PyQt6", "matplotlib", "openpyxl"}


class Balises(HTMLParser):
    VIDES = {"br", "img", "meta", "link", "hr", "input", "source", "col", "area", "base"}

    def __init__(self) -> None:
        super().__init__()
        self.pile: list[str] = []
        self.orphelines: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag not in self.VIDES:
            self.pile.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VIDES:
            return
        if self.pile and self.pile[-1] == tag:
            self.pile.pop()
        else:
            self.orphelines.append(tag)


def check_liens(p: Path, s: str) -> list[str]:
    """A -- `[texte](chemin)` vers un fichier du depot."""
    out = []
    for m in re.finditer(r"\[[^\]]{1,120}\]\(([^)#\s]+)(?:#[^)\s]*)?\)", s):
        cible = m.group(1)
        if cible.startswith(("http://", "https://", "mailto:", "data:")):
            continue
        chemin = (p.parent / cible).resolve()
        if not chemin.exists() and not (ROOT / cible).exists():
            ligne = s[:m.start()].count("\n") + 1
            out.append(f"{p.relative_to(ROOT)}:{ligne}  LIEN MORT  {cible}")
    return out


def check_code(p: Path, s: str) -> list[str]:
    """B -- `chemin/fichier.py:NNN`."""
    out = []
    vus: set[tuple[str, str]] = set()
    for m in re.finditer(r"\b((?:[\w.\-]+/)*[\w.\-]+\.py):(\d+)\b", s):
        path, num = m.group(1), m.group(2)
        if (path, num) in vus:
            continue
        vus.add((path, num))
        # 🔴 Un chemin de bibliotheque TIERCE (`numba/core/caching.py`) n'est pas une
        # reference au depot : c'est une citation de trace d'execution. La signaler comme
        # fichier introuvable est un faux positif, et un controle bruyant n'est plus lu.
        if path.split('/')[0] in TIERS:
            continue
        f = ROOT / path
        if not f.exists():
            hits = [h for h in ROOT.glob(f"**/{Path(path).name}")
                    if ".venv" not in str(h) and "__pycache__" not in str(h)]
            if not hits:
                ligne = s[:m.start()].count("\n") + 1
                out.append(f"{p.relative_to(ROOT)}:{ligne}  FICHIER INTROUVABLE  {path}")
                continue
            f = hits[0]
        n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
        if int(num) > n:
            ligne = s[:m.start()].count("\n") + 1
            out.append(f"{p.relative_to(ROOT)}:{ligne}  LIGNE HORS FICHIER  {path}:{num} "
                       f"(le fichier en a {n})")
    return out


def check_perimes(p: Path, s: str) -> list[str]:
    """C -- affirmations refutees, citees sans leur correction."""
    out = []
    lignes = s.splitlines()
    for i, ligne in enumerate(lignes, 1):
        voisinage = "\n".join(lignes[max(0, i - 1 - PORTEE):i + PORTEE]).lower()
        if any(d in voisinage for d in DISCULPANTS):
            continue
        for pat, verite in PERIMES:
            if pat.search(ligne):
                out.append(f"{p.relative_to(ROOT)}:{i}  PERIME  {verite}\n"
                           f"        > {ligne.strip()[:96]}")
                break
    return out


def check_html(p: Path, s: str) -> list[str]:
    """D -- structure des balises."""
    b = Balises()
    try:
        b.feed(s)
    except Exception as exc:  # noqa: BLE001
        return [f"{p.relative_to(ROOT)}  PARSEUR EN ECHEC  {exc!r}"]
    out = []
    if b.pile:
        out.append(f"{p.relative_to(ROOT)}  BALISES NON FERMEES  {b.pile[:6]}")
    if b.orphelines:
        out.append(f"{p.relative_to(ROOT)}  FERMETURES ORPHELINES  {b.orphelines[:6]}")
    return out


def main() -> int:
    blocs: dict[str, list[str]] = {
        "A. LIENS MORTS": [], "B. REFERENCES DE CODE MORTES": [],
        "C. CHIFFRES ET AFFIRMATIONS PERIMES": [], "D. STRUCTURE HTML": [],
    }
    for p in CIBLES:
        s = p.read_text(encoding="utf-8", errors="replace")
        blocs["A. LIENS MORTS"] += check_liens(p, s)
        blocs["B. REFERENCES DE CODE MORTES"] += check_code(p, s)
        blocs["C. CHIFFRES ET AFFIRMATIONS PERIMES"] += check_perimes(p, s)
        if p.suffix == ".html":
            blocs["D. STRUCTURE HTML"] += check_html(p, s)

    print("=" * 82)
    print(f"CONTROLE DE {len(CIBLES)} DOCUMENTS "
          f"({sum(1 for p in CIBLES if p.suffix == '.md')} md, "
          f"{sum(1 for p in CIBLES if p.suffix == '.html')} html)")
    print("=" * 82)
    total = 0
    for titre, items in blocs.items():
        print(f"\n{titre} : {len(items)}")
        for it in items[:25]:
            print("  " + it)
        if len(items) > 25:
            print(f"  ... et {len(items) - 25} autres")
        total += len(items)
    print("\n" + "=" * 82)
    print(f"DEFAUTS MECANIQUES : {total}")
    print("Zero ici ne veut PAS dire zero contradiction : ce script ne juge aucune phrase.")
    print("=" * 82)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
