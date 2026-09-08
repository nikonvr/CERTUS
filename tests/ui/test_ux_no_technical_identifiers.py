"""No screen label may show a technical identifier (plan UX, 4.3).

Column headers, tab titles and card titles are read by an operator, not by the
program. Three kinds of leak were measured in the suite:

- an internal key used verbatim as a title, prefix included;
- a symbol spelled out as its variable name instead of the physical symbol,
  while another module writes the symbol correctly - so the same quantity has
  two names depending on the window;
- a label whose symbol was lost, leaving empty brackets.

The check is static: it reads the labels handed to Qt in the sources. That is
exhaustive and costs no window build, where scanning the eleven live windows
would cost minutes and still miss the tabs that are built lazily.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: (pattern, why it must not reach a label). Written as regexes so the offending
#: spelling is never repeated verbatim more than once here.
FORBIDDEN = (
    (r"lambda" + r"m(?:in|ax)", "internal key instead of a wavelength bound with its unit"),
    (r"substrate_[A-Z]", "internal prefix left in a visible title"),
    (r"Angle\(\)", "the symbol was lost, leaving empty brackets"),
    (r"\bn\(" + r"lambda\)", "the symbol spelled out, while another module writes it properly"),
)

#: Calls whose string argument reaches the screen.
LABEL_CALLS = re.compile(
    r"(?:setHorizontalHeaderLabels|addTab|CertusCard|setWindowTitle|setTabText)\s*\(",
)


def _ui_sources() -> list[Path]:
    files = list(ROOT.glob("CERTUS_*.py"))
    files += [p for p in (ROOT / "certus").rglob("*.py") if "tests" not in p.parts]
    return files


def _visible_label_lines() -> list[tuple[Path, int, str]]:
    out = []
    for path in _ui_sources():
        for num, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if LABEL_CALLS.search(line) or ('"' in line and "HeaderLabels" in line):
                out.append((path, num, line))
    return out


def test_there_are_labels_to_inspect():
    """Contrôle négatif : an empty set would make the guard pass on anything."""
    assert len(_visible_label_lines()) >= 20, "no label-bearing line found - has the API changed?"


@pytest.mark.parametrize("pattern,why", FORBIDDEN)
def test_no_visible_label_carries_a_technical_identifier(pattern: str, why: str):
    rx = re.compile(pattern)
    offenders = [f"{p.relative_to(ROOT)}:{num}" for p, num, line in _visible_label_lines() if rx.search(line)]
    assert not offenders, f"{why} — {offenders}"


def test_the_guard_would_catch_a_leak():
    """Negative control: the detection must really bite."""
    faulty = 'self.t.setHorizontalHeaderLabels(["Active", "' + "lambda" + 'min"])'
    assert LABEL_CALLS.search(faulty)
    assert re.search(FORBIDDEN[0][0], faulty)
