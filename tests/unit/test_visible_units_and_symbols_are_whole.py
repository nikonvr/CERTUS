"""The units and symbols the user reads are whole: an inverse nanometre keeps its superscript, xi keeps its letter.

A clean-up of the encoding removed non-ASCII characters from visible strings. Where the character carried meaning, what
was left is wrong or unreadable (audit of the interface, A1; road map U1):

* `nm?1`, `nm?2`: the superscript minus became a question mark, the superscript digit a plain one. Elsewhere the minus
  survived and the digit did not (`nm⁻1`), or neither did (`nm-1`, which reads as `nm minus one`). The intact form is
  in the smart-init dialog: `Sigma (nm⁻¹)`, `Sigma² (nm⁻²)`.
* `Gaussian jitter sigma on n (or ? if monotonicity active)`: the letter is xi. certus/spline/certus_corridor_config.py
  says so next to the setting itself: `Jitters are in parameter units (n or ξ; and ln k)`.

Read in the sources, without Qt: every string constant of the interface that is neither a docstring nor a log message.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTERFACE = [*sorted((ROOT / "certus" / "ui").glob("*.py")), *sorted(ROOT.glob("CERTUS_*.py"))]
LOGGING = {"debug", "info", "warning", "error", "exception", "critical", "log"}
#: An inverse unit written without its superscripts: `nm?1`, `nm⁻1`, `nm-2`. The caret form (`cm^-1`) is plain ASCII
#: written on purpose, and reads as what it is.
BROKEN_UNIT = re.compile(r"\b[cnµu]?m[?⁻-][1-3]\b")


def visible_strings(path: Path) -> list[tuple[int, str]]:
    """(line, text) of every string constant of `path` that is not a docstring nor inside a logging call."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    hidden: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                hidden.add(id(first.value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOGGING:
            hidden |= {id(sub) for sub in ast.walk(node)}
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in hidden
    ]


def test_the_interface_is_found():
    assert len(INTERFACE) > 100


def test_the_detector_sees_the_three_broken_forms_and_not_the_whole_one():
    assert [bool(BROKEN_UNIT.search(text)) for text in ("sigma (nm?1)", "Sigma2 (nm⁻2)", "1/λ (nm-1)", "Sigma (nm⁻¹)", "d (nm)", "T-1")] == [
        True, True, True, False, False, False,
    ]  # fmt: skip


def test_no_visible_unit_lost_its_superscript():
    broken = [f"{path.name}:{line} {text[:60]!r}" for path in INTERFACE for line, text in visible_strings(path) if BROKEN_UNIT.search(text)]
    assert broken == []


def test_the_jitter_of_the_corridor_starts_names_xi():
    path = ROOT / "certus" / "ui" / "certus_index_spline_managers_ui.py"
    [tip] = [text for _line, text in visible_strings(path) if text.startswith("Gaussian jitter sigma on n")]
    assert tip == "Gaussian jitter sigma on n (or ξ if monotonicity active) for additional starts."
    assert "n or ξ" in (ROOT / "certus" / "spline" / "certus_corridor_config.py").read_text(encoding="utf-8")
