"""`scripts/orient.py` gives an AI its bearings in a bounded output, and the bound is pinned here.

A session used to open with a dozen exploratory commands (git status, ls, grep, whole documents) whose output costs tokens each time an AI takes
the work over. `orient.py` replaces them with one output of fixed size. What is pinned: the size of that output (a brief that grows back into
a report defeats its purpose), that it names the real head, that it finds the last validation in section 0 of `docs/ETAT.md` (so the paragraph
cannot be renamed without the script noticing), that the outline gives exact line ranges to read with `offset`/`limit`, and that another
python process on the machine is reported but this process and non-python processes are not.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

from scripts import orient

ROOT = Path(__file__).resolve().parents[2]

MAX_BRIEF_BYTES = 3000
MAX_MAP_LINES = 110


def test_the_brief_stays_within_its_bound():
    text = orient.brief(with_processes=False)
    assert len(text.splitlines()) <= orient.MAX_LINES
    assert len(text.encode("utf-8")) <= MAX_BRIEF_BYTES, "the brief grew: it costs tokens at the start of every session"


def test_the_brief_names_the_real_head():
    full = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    named = re.search(r"git +: .* @ ([0-9a-f]{7,40}) ", orient.brief(with_processes=False))
    assert named, "the brief has no `git : branch @ hash subject` line"
    assert full.startswith(named.group(1))


def test_the_last_validation_is_found_in_section_zero_of_the_state_file():
    etat = (ROOT / "docs" / "ETAT.md").read_text(encoding="utf-8")
    found = orient.last_validation(etat)
    assert re.search(r"20\d\d-\d\d-\d\d", found), "section 0 of docs/ETAT.md has no paragraph that begins with '**Dernière validation complète**'"
    assert len(found) <= 335


def test_section_zero_ends_where_section_one_starts():
    etat = "# T\n\n## 0. Zero\n\ntexte\n\n## 1. Un\n\nautre\n"
    assert orient.section_zero(etat) == "## 0. Zero\n\ntexte\n\n"
    assert orient.section_zero("pas de sections") == ""


def test_the_outline_gives_exact_line_ranges_and_ignores_code_fences():
    text = "\n".join(
        [
            "# Titre",  # 1
            "",  # 2
            "## 1. Un",  # 3
            "texte",  # 4
            "```",  # 5
            "## faux titre dans un bloc",  # 6
            "```",  # 7
            "### 1a. Sous-titre",  # 8
            "plus",  # 9
            "## 2. Deux",  # 10
            "fin",  # 11
        ]
    )
    assert orient.outline(text) == [(2, "1. Un", 3, 9), (2, "2. Deux", 10, 11)]
    assert orient.outline(text, (2, 3)) == [(2, "1. Un", 3, 9), (3, "1a. Sous-titre", 8, 9), (2, "2. Deux", 10, 11)]


def test_the_paragraph_leads_cover_a_document_without_numbered_titles():
    text = "# Titre\n\n> note\n\n**A3 — premier** suite\nsuite\n\n**A4 — second**\n"
    assert orient.paragraph_leads(text) == [(0, "**A3 — premier** suite", 5, 6), (0, "**A4 — second**", 8, 8)]


def test_another_python_process_is_reported_but_not_this_one_nor_other_programs():
    listing = f"{os.getpid()}|python orient.py\n999991|C:\\Python314\\python.exe C:\\work\\measure_slow.py --seed 7\n999992|notepad.exe C:\\x\\python.txt\n"
    seen = orient.foreign_pythons(run=lambda *_a, **_k: SimpleNamespace(stdout=listing))
    assert [pid for pid, _command in seen] == [999991]


def test_a_process_listing_that_fails_reports_nothing():
    def broken(*_a, **_k):
        raise OSError("no such program")

    assert orient.foreign_pythons(run=broken) == []


def test_a_process_is_named_by_its_script():
    assert orient.what('"C:\\Python314\\python.exe" C:\\Users\\x\\bm_window_laws.py --flag') == "bm_window_laws.py"
    assert orient.what("python -c pass") == "python -c pass"


def test_the_map_lists_every_reading_document_within_its_bound():
    text = orient.carte()
    assert len(text.splitlines()) <= MAX_MAP_LINES
    assert "docs/ETAT.md" in text
    assert re.search(r"L\d+-\d+ ~\d+\.\dk ", text)


def test_a_folder_without_git_or_documents_does_not_crash_the_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ROOT", tmp_path)
    text = orient.brief(with_processes=False)
    assert "indisponible" in text
    assert "introuvable" in text
