"""Orientation en une commande : l'etat du depot, le cout de lecture des documents, ce qu'il ne faut pas ouvrir.

    python scripts\\orient.py            # le bref : une quarantaine de lignes
    python scripts\\orient.py --carte    # + les titres de chaque document, avec leurs lignes et leur cout
    python scripts\\orient.py --sans-processus   # sans chercher les autres processus python (plus rapide)

Pourquoi : une session commence par une dizaine de commandes exploratoires (git status, ls, grep, documents lus en entier) dont la sortie
coute des tokens a chaque IA qui reprend le travail. Ce script les remplace par une sortie de taille bornee, que
`tests/unit/test_orient.py` plafonne. Il ne lit que git, `ps` ou PowerShell et les documents ; il ne calcule rien de physique et ne
modifie rien.

Le cout est un ordre de grandeur : octets / 3,6, mesure le 2026-10-18 sur CLAUDE.md et docs/ETAT.md avec le codage o200k_base (3,3 a 3,9
octets par token selon le document). Ce n'est pas une facturation, et un autre modele compte autrement.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# La console Windows est en cp1252 : sans ces deux lignes, un « 👤 » dans un titre leve UnicodeEncodeError (tests/unit/test_scripts_console_cp1252.py).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

BYTES_PER_TOKEN = 3.6
MAX_LINES = 45  # le plafond du bref, verifie par tests/unit/test_orient.py

#: Lus d'abord : (chemin, ce qu'il porte).
READ_FIRST = (
    ("CLAUDE.md", "les regles qui annulent un travail"),
    ("AGENTS.md", "les consignes de sobriete de lecture"),
)
#: Lus a la demande : (chemin, quand les ouvrir).
ON_DEMAND = (
    ("docs/ETAT_actions.md", "actions A3 a A9 et protocole de mesure du Rate"),
    ("docs/ETAT_acquis.md", "acquis du Rate, corrections qui invalident des mesures, vocabulaire"),
    ("docs/REGLES_reference.md", "pieges d'execution, architecture du gel, vocabulaire, documentation, revue d'un autre agent"),
)
#: Gros fichiers de la racine : se lisent par identifiant (`grep -n "ID" fichier`), jamais en entier.
NEVER_WHOLE = ("ideeargon.md",)
#: Documents dont `--carte` donne les titres.
MAP_DOCS = ("CLAUDE.md", "docs/ETAT.md", "docs/ETAT_actions.md", "docs/ETAT_acquis.md", "docs/REGLES_reference.md")


def tokens(size: int) -> str:
    return f"~{size / BYTES_PER_TOKEN / 1000:.1f}k"


def git(*args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.rstrip() if done.returncode == 0 else ""


def read(path: str) -> str:
    try:
        return (ROOT / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def section_zero(etat: str) -> str:
    """Le texte de la section 0 de docs/ETAT.md, titre compris."""
    start = re.search(r"^## 0\. ", etat, re.MULTILINE)
    end = re.search(r"^## 1\. ", etat, re.MULTILINE)
    if not start or not end or end.start() < start.start():
        return ""
    return etat[start.start() : end.start()]


def last_validation(etat: str) -> str:
    """Le paragraphe « Dernière validation complète » de la section 0, sur une ligne et borné ; vide s'il n'y est plus."""
    match = re.search(r"\*\*Dernière validation complète\*\*(.*?)(?:\n\s*\n|\Z)", section_zero(etat), re.DOTALL)
    if not match:
        return ""
    text = " ".join(match.group(1).split())
    return text if len(text) <= 330 else text[:327] + "..."


def is_python(command: str) -> bool:
    """Le programme d'une ligne de commande est-il un interpreteur python (et pas un editeur qui ouvre `python.txt`) ?"""
    program = re.match(r"\s*\"?([^\"\s]+)", command)
    return bool(program) and re.split(r"[\\/]", program.group(1))[-1].lower().startswith("python")


def foreign_pythons(run=subprocess.run) -> list[tuple[int, str]]:
    """Les autres processus python de la machine : une mesure lancee pendant qu'une autre tourne rend RESULT=None (CLAUDE.md §4)."""
    own = {os.getpid(), os.getppid()}
    if os.name == "nt":
        script = "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"
        command = ["powershell", "-NoProfile", "-Command", script]
    else:
        command = ["ps", "-eo", "pid=,args="]
    try:
        done = run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    found: list[tuple[int, str]] = []
    for line in (done.stdout or "").splitlines():
        match = re.match(r"\s*(\d+)[|\s]\s*(.*)", line)
        if not match or not is_python(match.group(2)):
            continue
        pid = int(match.group(1))
        if pid not in own:
            found.append((pid, match.group(2).strip()))
    return found


def outline(text: str, levels: tuple[int, ...] = (2,)) -> list[tuple[int, str, int, int]]:
    """(niveau, titre, premiere ligne, derniere ligne) des titres `#`, lignes comptees depuis 1 ; derniere ligne incluse."""
    lines = text.split("\n")
    heads: list[tuple[int, str, int]] = []
    fenced = False
    for number, line in enumerate(lines, 1):
        if line.startswith("```"):
            fenced = not fenced
        match = None if fenced else re.match(r"(#{1,6}) +(.*\S)", line)
        if match:
            heads.append((len(match.group(1)), match.group(2), number))
    out = []
    for index, (level, title, start) in enumerate(heads):
        if level not in levels:
            continue
        end = len(lines)
        for next_level, _title, next_start in heads[index + 1 :]:
            if next_level <= level:
                end = next_start - 1
                break
        out.append((level, title, start, end))
    return out


def paragraph_leads(text: str) -> list[tuple[int, str, int, int]]:
    """Pour un document sans titres numerotes : le debut de chaque paragraphe, avec ses lignes."""
    out = []
    start = None
    lead = ""
    lines = text.split("\n")
    for number, line in enumerate([*lines, ""], 1):
        if line.strip() and start is None:
            start, lead = number, line
        elif not line.strip() and start is not None:
            if not lead.startswith(("# ", "> ")):
                out.append((0, lead, start, number - 1))
            start = None
    return out


def what(command: str) -> str:
    """Ce qu'un processus python execute : le nom de son script, sinon le debut de sa ligne de commande."""
    script = re.search(r"([^\s\"'\\/]+\.py)\b", command)
    return script.group(1) if script else short(command, 60)


def short(title: str, width: int = 74) -> str:
    title = re.sub(r"[*`]", "", title)
    return title if len(title) <= width else title[: width - 3] + "..."


def tree_lines() -> list[str]:
    changed = [line for line in git("status", "--porcelain=v1").splitlines() if line.strip()]
    if not changed:
        return ["arbre   : propre"]
    untracked = [line[3:] for line in changed if line.startswith("??")]
    modified = [line[3:] for line in changed if not line.startswith("??")]
    names = (modified + untracked)[:6]
    more = len(changed) - len(names)
    tail = f" (+{more} autres)" if more > 0 else ""
    return [f"arbre   : {len(modified)} modifies, {len(untracked)} non suivis : {', '.join(names)}{tail}"]


def brief(with_processes: bool = True) -> str:
    etat = read("docs/ETAT.md")
    lines = [f"orient  : {datetime.now():%Y-%m-%d %H:%M} | a lire dans l'ordre : CLAUDE.md, AGENTS.md, section 0 de docs/ETAT.md"]

    head = git("log", "-1", "--format=%h %s")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    lines.append(f"git     : {branch} @ {head}" if head else "git     : indisponible")
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream:
        behind, _, ahead = git("rev-list", "--left-right", "--count", "@{u}...HEAD").partition("\t")
        lines.append(f"amont   : {upstream}, en avance de {ahead or '?'}, en retard de {behind or '?'}")
    else:
        lines.append("amont   : aucun")
    hooks = git("config", "--get", "core.hooksPath")
    if hooks:
        lines.append(f"hook    : core.hooksPath={hooks} : un commit peut PUBLIER ; ne committe qu'avec l'ordre de 👤")
    else:
        lines.append("hook    : core.hooksPath absent : committer ne publie pas ; pousser publie, sur ordre de 👤 seulement")
    lines.extend(tree_lines())
    worktrees = [line for line in git("worktree", "list").splitlines() if line.strip() and "prunable" not in line]
    if len(worktrees) > 1:
        lines.append(f"worktrees : {len(worktrees)} (un balayage depuis la racine lit leurs copies : balayer `git ls-files`)")

    if with_processes:
        others = foreign_pythons()
        if others:
            shown = "; ".join(f"pid {pid} {what(command)}" for pid, command in others[:3])
            lines.append(f"python  : {len(others)} autre(s) processus en cours : {shown}")
            lines.append("          pas de mesure ni d'etape ui de la validation tant qu'ils tournent (CLAUDE.md §4)")
        else:
            lines.append("python  : aucun autre processus python en cours")

    validation = last_validation(etat)
    lines.append(f"validation : {validation}" if validation else "validation : paragraphe « Dernière validation complète » introuvable dans la section 0")

    sizes = [f"{path} {tokens(len(read(path).encode('utf-8')))}" for path, _role in READ_FIRST]
    sizes.append(f"docs/ETAT.md section 0 {tokens(len(section_zero(etat).encode('utf-8')))}")
    lines.append("a lire  : " + ", ".join(sizes))
    for path, role in ON_DEMAND:
        text = read(path)
        if text:
            lines.append(f"demande : {path} {tokens(len(text.encode('utf-8')))} ({role})")
    rest = len(etat.encode("utf-8")) - len(section_zero(etat).encode("utf-8"))
    lines.append(f"          docs/ETAT.md sections 1 a 7 {tokens(rest)} : par section avec Read offset/limit, titres et lignes par --carte")

    tracked = git("ls-files", "--", "reports").splitlines()
    heavy = ", ".join(f"{name} {tokens((ROOT / name).stat().st_size)}" for name in NEVER_WHOLE if (ROOT / name).exists())
    heavy = f", {heavy}" if heavy else ""
    lines.append(f"jamais en entier : reports/ ({len(tracked)} fichiers suivis), studies/{heavy} ; chercher par identifiant (grep -n \"ID\" fichier)")
    lines.append("commandes : python scripts\\preflight.py ; python -m pytest tests/unit -q --no-cov -x ; python scripts\\validate_parallel.py")
    return "\n".join(lines)


def carte() -> str:
    lines = ["", "carte : lignes de debut-fin, cout approximatif en tokens, titre (Read avec offset et limit)"]
    for path in MAP_DOCS:
        text = read(path)
        if not text:
            continue
        levels = (2, 3) if path == "docs/ETAT.md" else (2,)
        entries = outline(text, levels) or paragraph_leads(text)
        total = len(text.encode("utf-8"))
        lines.append(f"{path} ({len(text.splitlines())} lignes, {tokens(total)})")
        body = text.split("\n")
        for level, title, start, end in entries:
            size = len("\n".join(body[start - 1 : end]).encode("utf-8"))
            marker = "  " * max(level - 2, 0)
            lines.append(f"  L{start}-{end} {tokens(size)} {marker}{short(title)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(brief(with_processes="--sans-processus" not in args))
    if "--carte" in args:
        print(carte())
    return 0


if __name__ == "__main__":
    sys.exit(main())
