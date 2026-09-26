"""Comments, docstrings and log messages of `certus/` are written in English (rule 11).

Until 2026-09-26 nothing enforced the rule, and 1 143 lines of French had accumulated in
22 files -- the densest in the STRAT modules, where most of the recent work happened.
They were translated that day; this sweep keeps them from coming back.

What stays French on purpose, and is NOT scanned here: words used as DATA (French column
headers recognised in `certus_re_helpers.py`), persisted keys (`seuil1`/`seuil2`),
identifiers, and user-facing strings. Only prose is checked: comments, docstrings and
the text of logging calls.

The detector is deliberately simple: a line is French when its French function words
outnumber its English ones. It under-reports (a single French word in an English
sentence passes), which is the right direction for a guard that must never cry wolf.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Function words that are French and (almost) never English.
FRENCH = {
    "le", "la", "les", "des", "du", "de", "une", "un", "et", "est", "sont", "pour", "dans",
    "qui", "que", "pas", "avec", "cette", "ces", "mais", "donc", "etre", "être", "avoir",
    "c'est", "n'est", "qu'il", "qu'on", "jamais", "toujours", "parce", "quand", "comme",
    "sans", "sous", "chaque", "leur", "leurs", "nous", "vous", "elle", "ils", "sur", "aussi",
    "deja", "déjà", "tres", "très", "ne", "aux", "au", "ou", "où", "ce", "cet", "ici",
    "alors", "selon", "depuis", "encore", "meme", "même", "tout", "tous", "toute", "rien",
    "fois", "d'un", "d'une", "puis", "peut", "doit", "faut", "etait", "était", "en", "par",
}
ENGLISH = {
    "the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "with", "on", "at",
    "by", "from", "it", "this", "that", "be", "as", "not", "no", "if", "when", "which",
    "what", "its", "into", "than", "then", "so",
}
_WORD = re.compile(r"[A-Za-zÀ-ÿ_'\-]+")
_ACCENT = re.compile(r"[éèêàùçîôûœÉÈÀÊ]")

#: Lines that are French BY DESIGN, with the reason. Match on a substring of the line.
ALLOWED = {
    # The ELITE counters line is a machine-read format: scripts parse it by regex and the
    # logs archived in reports/ carry it. Its words are field names, like a persisted key.
    ("certus/core/certus_strat_consensus.py", "rejets -- halving="),
}


def _words(text: str) -> list[str]:
    text = re.sub(r"`[^`]*`", " ", text)  # code spans are not prose
    text = re.sub(r"\bet al\b", " ", text)  # a citation, not French
    out = []
    for w in _WORD.findall(text):
        if "_" in w or "-" in w:
            continue  # identifiers and hyphenated compounds
        if not (w.islower() or w.istitle() or (w.isupper() and len(w) > 2)):
            continue  # camelCase fragments such as dE0, d/dEg
        out.append(w.lower().strip("'"))
    return out


def is_french(text: str) -> bool:
    words = _words(text)
    fr = [w for w in words if w in FRENCH]
    en = [w for w in words if w in ENGLISH]
    return bool(fr) and (len(fr) > len(en) or bool(_ACCENT.search(text)))


def _prose_lines(src: str) -> list[tuple[int, str]]:
    """(line, text) of every comment, docstring line and logging-call string."""
    tree = ast.parse(src)
    lines = src.splitlines()
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                out += [(i, lines[i - 1]) for i in range(body[0].lineno, body[0].end_lineno + 1)]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"debug", "info", "warning", "error", "critical", "exception"} and node.args:
            arg = node.args[0]
            parts = [s.value for s in ast.walk(arg) if isinstance(s, ast.Constant) and isinstance(s.value, str)]
            if parts:
                out.append((arg.lineno, " ".join(parts)))
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            out.append((tok.start[0], tok.string))
    return out


def _french_lines(rel: str, src: str) -> list[str]:
    found = []
    for line, text in _prose_lines(src):
        if is_french(text) and not any(rel == f and frag in text for f, frag in ALLOWED):
            found.append(f"{rel}:{line}: {text.strip()[:100]}")
    return found


def _certus_sources() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", "certus/*.py"], cwd=ROOT, capture_output=True, check=False)
    if out.returncode != 0 or not out.stdout:
        pytest.skip("git ls-files unavailable: the sweep needs the tracked file list")
    return [f for f in out.stdout.decode("utf-8").split("\0") if f]


@pytest.mark.unit
def test_certus_prose_is_english() -> None:
    files = _certus_sources()
    assert len(files) > 200, "the sweep must see the package"
    found = []
    for rel in files:
        found += _french_lines(rel, (ROOT / rel).read_text(encoding="utf-8-sig"))
    assert found == [], "French prose in certus/ (rule 11):\n" + "\n".join(found)


@pytest.mark.unit
def test_the_detector_catches_french_in_all_three_places() -> None:
    src = (
        '"""Module qui calcule la transmission pour chaque couche."""\n'
        "import logging\n"
        "# On garde la couche si elle est deja admissible.\n"
        'logging.info("la passe n\'a pas tourne pour cette couche")\n'
    )
    found = _french_lines("probe.py", src)
    assert sorted(f.split(":")[1] for f in found) == ["1", "3", "4"], found


@pytest.mark.unit
def test_the_detector_leaves_english_alone() -> None:
    src = (
        '"""Computes [eps2, d/dEg, d/dE0] -- Zideluns et al., Opt. Express (2021)."""\n'
        "# De-duplicate sheet names (mixed Excel FR/EN labels); refresh_nk_plots_aux.\n"
        "# dP/dE0 = -200 * (Eg - E0 + 0.1)\n"
    )
    assert _french_lines("probe.py", src) == []
