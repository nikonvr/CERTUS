"""What an AI reads at the start of a session only shrinks, and what is too big to read stays out of the default searches.

Every AI that takes the work over pays for these files in full, each session. Measured on 2026-10-18 with the `o200k_base` encoding:
`CLAUDE.md` 4 000 tokens, section 0 of `docs/ETAT.md` 9 963 and `AGENTS.md` 132, so 14 095 before it could touch anything. After the split
(rules that cancel a piece of work in `CLAUDE.md`, the reference in `docs/REGLES_reference.md`, the Rate record and the actions in
`docs/ETAT_acquis.md` and `docs/ETAT_actions.md`) the same three cost 7 071, and `AGENTS.md` carries the instructions that keep the rest down.
Nothing keeps that true by itself: each session appends a paragraph to the state file. These are the ratchets.

* The caps below are a few percent above what was measured. Shrinking is free (lower the cap in the same commit). Raising one needs a reason that
  outweighs paying those bytes in every session; move reference text to the on-demand files first.
* A big document at the root (`UXargon.md`, `designargon.md`, `ideeargon.md`) is read by identifier, never whole. `.rgignore` hides it from the
  default searches of the tools built on ripgrep, as it hides `reports/` (84 % of the tracked files) and `studies/`.
* `.ignore` must not exist: ruff reads it too, and measured on 2026-10-18 it changed the scope of `ruff check .` (1 491 violations with it absent,
  1 421 with it). `.rgignore` is read by ripgrep only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: bytes of the file as git stores it (LF), measured 2026-10-18
CAPS = {
    "CLAUDE.md": 11_800,
    "AGENTS.md": 2_600,
    "docs/ETAT.md": 80_000,
    "docs/ETAT_actions.md": 16_000,
    "docs/ETAT_acquis.md": 12_500,
    "docs/REGLES_reference.md": 6_500,
}
#: section 0 of docs/ETAT.md alone: the part every session reads
SECTION_ZERO_CAP = 12_000
#: a root document above this size has to be hidden from the default searches
BIG_ROOT_DOCUMENT = 20_000


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _size(path: str) -> int:
    return len(_read(path).encode("utf-8"))


@pytest.mark.parametrize("path", sorted(CAPS))
def test_a_document_an_ai_reads_stays_under_its_cap(path):
    size, cap = _size(path), CAPS[path]
    assert size <= cap, (
        f"{path} is {size} bytes, its cap is {cap}: it is paid by every AI that opens it. Move reference text to an on-demand file "
        "(docs/REGLES_reference.md, docs/ETAT_acquis.md, docs/ETAT_actions.md), or raise the cap here with a reason."
    )


def test_section_zero_of_the_state_file_stays_under_its_cap():
    etat = _read("docs/ETAT.md")
    start, end = re.search(r"^## 0\. ", etat, re.MULTILINE), re.search(r"^## 1\. ", etat, re.MULTILINE)
    assert start, "docs/ETAT.md has lost its section 0"
    assert end, "docs/ETAT.md has lost its section 1"
    assert start.start() < end.start(), "sections 0 and 1 of docs/ETAT.md are out of order"
    size = len(etat[start.start() : end.start()].encode("utf-8"))
    assert size <= SECTION_ZERO_CAP, (
        f"section 0 of docs/ETAT.md is {size} bytes, its cap is {SECTION_ZERO_CAP}: every session reads it whole. "
        "A paragraph that has become a record belongs in docs/ETAT_acquis.md, an action in docs/ETAT_actions.md."
    )


def test_reports_and_studies_are_hidden_from_the_default_searches():
    hidden = {line.strip() for line in _read(".rgignore").splitlines() if line.strip() and not line.startswith("#")}
    absent = {"/reports/", "/studies/"} - hidden
    assert not absent, f".rgignore no longer hides {sorted(absent)}: a default search would read measurement reports and studies whole"


def test_a_big_document_at_the_root_is_hidden_from_the_default_searches():
    hidden = {line.strip() for line in _read(".rgignore").splitlines() if line.strip() and not line.startswith("#")}
    exposed = [p.name for p in sorted(ROOT.glob("*.md")) if p.stat().st_size > BIG_ROOT_DOCUMENT and f"/{p.name}" not in hidden]
    assert not exposed, f"{exposed} are above {BIG_ROOT_DOCUMENT} bytes and not listed in .rgignore: a default search would read them whole"


def test_there_is_no_dot_ignore_file_at_the_root():
    assert not (ROOT / ".ignore").exists(), "ruff reads .ignore and would stop checking what it lists: use .rgignore, which only ripgrep reads"


def test_the_instructions_reach_every_ai():
    assert "@AGENTS.md" in _read("CLAUDE.md"), "Claude Code reads CLAUDE.md, not AGENTS.md: the import line is how it gets the reading discipline"
    assert "CLAUDE.md" in _read("AGENTS.md"), "AGENTS.md is the entry of the other AIs: it must lead them to the rules"


def test_the_entry_points_name_only_scripts_and_documents_that_exist():
    missing = []
    for source in ("AGENTS.md", "CLAUDE.md"):
        text = _read(source)
        scripts = sorted(set(re.findall(r"scripts\\([\w]+\.py)", text)))
        documents = sorted(set(re.findall(r"docs/([\w]+\.md)", text)))
        missing += [f"{source}: scripts\\{name}" for name in scripts if not (ROOT / "scripts" / name).exists()]
        missing += [f"{source}: docs/{name}" for name in documents if not (ROOT / "docs" / name).exists()]
    assert not missing, missing
