"""Traque MECANIQUEMENT les contradictions de CLAUDE.md.

    .venv\\Scripts\\python.exe scripts\\check_claude_md.py

👤 2026-08-15 : *« je te propose de faire des passes successives sur claude.md jusqu'a
trouver zero contradiction »*. Relire 4 500 lignes a l'oeil ne converge pas -- on retrouve
ce qu'on cherche et on rate le reste. Ce script rend le critere d'arret OBJECTIF : il sort
un compte, et une passe reussie est une passe qui le fait baisser.

CE QU'IL SAIT VERIFIER, sans aucun jugement :

  A. REFERENCES DE CODE MORTES -- tout `chemin/fichier.py:NNN` cite. Le fichier existe-t-il,
     et a-t-il seulement NNN lignes ? C'est ainsi qu'on a decouvert que le document citait
     14 fois `certus/core/certus_strat_growth.py`, un fichier qui n'existe pas : le module
     est en `certus/physics/`.

  B. RENVOIS DE SECTION FANTOMES -- tout `§N` ou `§N-M`. La section existe-t-elle ? La
     vitrine portait un renvoi vers un « §17-26 » alors qu'elle s'arrete a la section 11.

  C. VALEURS DISCORDANTES -- un meme parametre cite avec deux valeurs differentes. C'est la
     forme exacte du defaut `tp_hysteresis_factor` : 0,354 dans deux tableaux d'autorite,
     1,00 dans le postulat qui le refute.

  D. NOMBRES DUPLIQUES -- un resultat recopie a N endroits. Chaque copie est une occasion de
     perimer, et c'est le mecanisme de TOUTES les contradictions trouvees jusqu'ici. Signale
     pour relecture, pas comme faute.

🔴 CE QU'IL NE SAIT PAS FAIRE, et il faut le dire : juger si deux PHRASES se contredisent.
Un « ce parametre n'existe pas » ecrit a cote d'un parametre qui existe lui echappe. Zero
ici ne veut donc pas dire zero contradiction -- ca veut dire zero contradiction MECANIQUE.
Le reste demande une lecture.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "CLAUDE.md"

#: Parametres dont une valeur mal recopiee change une mesure. Motif : nom puis un nombre
#: proche, en tolerant le gras markdown et la virgule decimale francaise.
WATCHED = (
    "tp_hysteresis_factor",
    "phase_a_level_margin_factor",
    "index_corridor",
    "reading_smoothing_window",
    "SEEL_RESOLUTION_NM",
    "machine_sampling_dd",
    "dp_yield_weight",
    "crash_gate_confidence",
    "MAX_LOOKBACK",
    "SCORE_RESOLUTION_REL",
)

#: Un nombre cite ici est une PREUVE de refutation, pas une valeur a appliquer.
REFUTED_MARKERS = ("réfut", "RÉFUT", "faux", "FAUX", "n'est pas", "jamais", "périmé",
                   "PÉRIMÉ", "ancienne", "refuté")


def load() -> list[str]:
    return DOC.read_text(encoding="utf-8").splitlines()


def check_code_refs(lines: list[str]) -> list[str]:
    """A -- `fichier.py:NNN` : le fichier existe-t-il, et est-il assez long ?"""
    out = []
    pat = re.compile(r"\b((?:[\w.\-]+/)*[\w.\-]+\.py):(\d+)\b")
    seen: set[tuple[str, str]] = set()
    for i, line in enumerate(lines, 1):
        for path, num in pat.findall(line):
            if (path, num) in seen:
                continue
            seen.add((path, num))
            f = ROOT / path
            if not f.exists():
                # peut-etre cite sans son dossier : on cherche le basename
                hits = [h for h in ROOT.glob(f"**/{Path(path).name}")
                        if ".venv" not in str(h) and "__pycache__" not in str(h)]
                if not hits:
                    out.append(f"{DOC.name}:{i}  FICHIER INTROUVABLE  {path}")
                elif len(hits) > 1:
                    out.append(f"{DOC.name}:{i}  NOM AMBIGU  {path} -> "
                               f"{len(hits)} fichiers portent ce nom")
                else:
                    # raccourci sans dossier, mais il resout : on verifie quand meme la ligne
                    n = len(hits[0].read_text(encoding="utf-8", errors="replace").splitlines())
                    if int(num) > n:
                        out.append(f"{DOC.name}:{i}  LIGNE HORS FICHIER  {path}:{num} "
                                   f"({hits[0].relative_to(ROOT)} en a {n})")
            else:
                n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                if int(num) > n:
                    out.append(f"{DOC.name}:{i}  LIGNE HORS FICHIER  {path}:{num} (le fichier en a {n})")
    return out


def check_section_refs(lines: list[str]) -> list[str]:
    """B -- `§N` : la section existe-t-elle dans le document ?"""
    existing = set()
    for line in lines:
        if not line.startswith("##"):
            continue
        m = re.match(r"(\d+)(bis|ter)?\.", line.lstrip("#* "))
        if m:
            existing.add(m.group(1) + (m.group(2) or ""))
    out = []
    seen: set[str] = set()
    for i, line in enumerate(lines, 1):
        # 🔴 UNE LIGNE QUI NOMME UN AUTRE `.md` PORTE UN RENVOI CROISE, pas un renvoi interne.
        # 📏 Faux positif du 2026-08-20 : `📌 Detail : [CHANTIER_RATE.md](...) §3bis` etait
        # signale comme fantome parce que CLAUDE.md n'a pas de §3bis -- alors que la ligne
        # designe explicitement l'autre document. Exactement le meme defaut que le controle I
        # de `coherence_md.py`, corrige le meme jour : un controle qui crie a tort se fait
        # ignorer, et un controle ignore ne protege plus de rien.
        if re.search(r"\w+\.md", line):
            continue
        for ref in re.findall(r"§\s*(\d+(?:bis|ter)?)", line):
            if ref in existing or ref in seen:
                continue
            seen.add(ref)
            out.append(f"{DOC.name}:{i}  RENVOI FANTOME  §{ref} (sections connues : "
                       f"{', '.join(sorted(existing, key=lambda s: (int(re.sub('[a-z]', '', s)), s)))})")
    return out


def check_param_values(lines: list[str]) -> list[str]:
    """C -- un parametre cite avec deux valeurs differentes, hors contexte de refutation."""
    vals: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i, line in enumerate(lines, 1):
        if any(mk in line for mk in REFUTED_MARKERS):
            continue                      # la ligne PORTE sa refutation : elle est saine
        for p in WATCHED:
            if p not in line:
                continue
            tail = line.split(p, 1)[1][:110]
            # Un numero de ligne (`fichier.py:991`) et un renvoi (`§12.3`) ne sont pas
            # des valeurs. Sans ce nettoyage le controle rend surtout du bruit, et un
            # controle bruyant finit par ne plus etre lu -- ce qui est pire que pas de
            # controle du tout.
            tail = re.sub(r"[\w./\-]+\.py:\d+(?:-\d+)?", " ", tail)
            tail = re.sub(r"§\s*\d+(?:bis|ter)?(?:[.‑-]\d+)*", " ", tail)
            tail = re.sub(r"(?:20\d\d[-/]\d\d[-/]\d\d|commit\s+\w+)", " ", tail)
            for raw in re.findall(r"\*{0,2}(\d+[.,]\d+|\d+)\*{0,2}", tail)[:2]:
                v = raw.replace(",", ".").rstrip("0").rstrip(".") or "0"
                vals[p][v].append(i)
    out = []
    for p, byval in vals.items():
        if len(byval) > 1:
            detail = " | ".join(f"{v} (l. {', '.join(map(str, ln[:4]))})"
                                for v, ln in sorted(byval.items()))
            out.append(f"VALEURS DISCORDANTES  {p} : {detail}")
    return out


def check_dup_numbers(lines: list[str]) -> list[str]:
    """D -- un resultat recopie a 3 endroits ou plus. Signale, pas fautif."""
    occ: dict[str, list[int]] = defaultdict(list)
    pat = re.compile(r"\b\d+[.,]\d{3,}\b")
    for i, line in enumerate(lines, 1):
        for m in set(pat.findall(line)):
            occ[m.replace(",", ".")].append(i)
    return [f"RECOPIE {len(v)}x  {k}  l. {', '.join(map(str, v[:8]))}"
            for k, v in sorted(occ.items(), key=lambda kv: -len(kv[1])) if len(v) >= 4]


#: 🔴 E -- LA CONFUSION QWOT / TURNING POINT. 👤 le 2026-08-15 : *« il ne faut plus faire la
#: confusion et empecher toute IA moins intelligente de faire la confusion »*.
#:
#: Un turning point, c'est l'instant ou l'ADMITTANCE DU SYSTEME devient reelle
#: (`tan 2.delta = R/Q`). Le QWOT, c'est l'epaisseur d'UNE couche. Les deux ne coincident
#: que sur la couche 1 d'un substrat nu -- ou R = 0 exactement, verifie -- ou sur un
#: empilement entierement en QWOT a lambda_mon. Ailleurs, le decalage de phase impose par
#: l'empilement du dessous les separe.
#:
#: 📏 De combien on se trompe : sur le random75 x0.5, le comptage naif annonce 59 couches
#: « sans point d'arret », le comptage exact en trouve 1. Facteur 59.
#:
#: Ces motifs cherchent une phrase qui traite les deux notions comme equivalentes DANS UNE
#: MEME PHRASE. Ils ne se declenchent pas sur un texte qui les OPPOSE -- c'est le role de
#: DISCULPANTS, sinon docs/QWOT_ET_TURNING_POINT.md se signalerait lui-meme.
QWOT_TP_MOTIFS = (
    re.compile(r"sous\s+1\s*QWOT[^.]{0,60}(aucun|pas d[eu']|sans)\s+(extrem|turning|point d)", re.I),
    re.compile(r"(aucun|pas d[eu']|sans)\s+(extremum|extrema|turning point|point d'arr[eê]t)[^.]{0,60}sous\s+1\s*QWOT", re.I),
    re.compile(r"turning\s+point[^.]{0,40}(c'est|=|equivaut|correspond|revient)[^.]{0,20}\bQWOT\b", re.I),
    re.compile(r"\bQWOT\b[^.]{0,40}(c'est|=|equivaut|correspond|revient)[^.]{0,25}turning\s+point", re.I),
    re.compile(r"(compte|nombre)\s+de\s+QWOT[^.]{0,50}(nombre|compte)\s+(de\s+)?(turning|extrem)", re.I),
)
#: Une phrase qui DISTINGUE les deux notions est correcte : elle ne doit pas etre signalee.
DISCULPANTS = ("n'est pas", "different", "différent", "ne coincide", "ne coïncide", "pas la meme",
               "pas la même", "confusion", "faux", "FAUX", "réfut", "refut", "sauf",
               "uniquement sur la premiere", "uniquement sur la première", "erreur")


def check_qwot_vs_tp(lines: list[str]) -> list[str]:
    """E -- assimile-t-on QWOT et turning point ? Voir docs/QWOT_ET_TURNING_POINT.md."""
    out = []
    for i, line in enumerate(lines, 1):
        if any(d in line for d in DISCULPANTS):
            continue
        for pat in QWOT_TP_MOTIFS:
            if pat.search(line):
                out.append(f"QWOT != TURNING POINT  l. {i} : {line.strip()[:110]}")
                break
    return out


#: 🔴 F -- BUDGET DE TAILLE. 👤 le 2026-08-16 : *« CLAUDE.md fait 5413 lignes, je pense que
#: c'est inefficace car les IA ne lisent pas forcement tout et il peut y avoir des
#: contradictions »*. Il avait raison, et la cause racine n'etait pas la longueur : c'est que
#: le MEME FAIT etait enonce a plusieurs endroits. Corriger le SEEL du 99c a demande SEPT
#: modifications a la main, et une avait ete oubliee.
#:
#: Le fichier est passe de 5413 a ~1780 lignes par extraction vers docs/. Ce controle existe
#: pour que ca ne regonfle pas en silence : au-dela du plafond, on ARBITRE, on ne reporte pas.
#: Un depassement n'est pas une faute morale -- c'est le signal qu'une section merite son
#: propre dossier dans docs/, avec un renvoi ici.
MAX_LIGNES = 2000


def check_taille(lines: list[str]) -> list[str]:
    """F -- le fichier tient-il dans son budget ?"""
    n = len(lines)
    if n <= MAX_LIGNES:
        return []
    return [
        f"CLAUDE.md fait {n} lignes, plafond {MAX_LIGNES}. Extrais une section vers docs/ "
        f"et laisse un renvoi -- voir scripts/extraire_section.py."
    ]


def main() -> int:
    lines = load()
    blocks = [
        ("A. REFERENCES DE CODE MORTES", check_code_refs(lines), True),
        ("B. RENVOIS DE SECTION FANTOMES", check_section_refs(lines), True),
        ("C. VALEURS DISCORDANTES", check_param_values(lines), True),
        ("D. NOMBRES RECOPIES (a relire, pas forcement faux)", check_dup_numbers(lines), False),
        ("E. CONFUSION QWOT / TURNING POINT", check_qwot_vs_tp(lines), True),
        (f"F. BUDGET DE TAILLE (plafond {MAX_LIGNES} lignes)", check_taille(lines), True),
    ]
    faults = 0
    for title, items, counts in blocks:
        print(f"\n{'=' * 78}\n{title} : {len(items)}\n{'=' * 78}")
        for it in items:
            print("  " + it)
        if counts:
            faults += len(items)
    print(f"\n{'=' * 78}")
    print(f"CONTRADICTIONS MECANIQUES : {faults}")
    print("Zero ici ne veut PAS dire zero contradiction : ce script ne juge aucune phrase.")
    print("=" * 78)
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
