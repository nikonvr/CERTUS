"""The units and symbols the user reads are whole: an inverse nanometre keeps its superscript, xi keeps its letter.

A clean-up of the encoding removed non-ASCII characters from visible strings. Where the character carried meaning, what
was left is wrong or unreadable (audit of the interface, A1; road map U1):

* `nm?1`, `nm?2`: the superscript minus became a question mark, the superscript digit a plain one. Elsewhere the minus
  survived and the digit did not (`nm⁻1`), or neither did (`nm-1`, which reads as `nm minus one`). The intact form is
  in the smart-init dialog: `Sigma (nm⁻¹)`, `Sigma² (nm⁻²)`.
* `Gaussian jitter sigma on n (or ? if monotonicity active)`: the letter is xi. certus/spline/certus_corridor_config.py
  says so next to the setting itself: `Jitters are in parameter units (n or ξ; and ln k)`.

* Eight question marks in the sentences of the RMSE(d) tab, where git has no trace of the character (they are there
  from the first commit). Written back the way the rest of the interface writes: `≈` before a computed value (the
  spectrum tab says `y ≈ ...`), `∈` before an interval `[lo, hi]`, and the dash of the cards of the tab in its title.
  A choice, not a restoration. tests/unit/test_rmse_tab_summary.py holds the sentence; the three other strings are
  held here.

* Three French strings in the INDEX SPLINE window, which tests/ui/test_ux_index_spline_speaks_one_language.py holds to
  one language by looking for accented letters on the built window: `Demi-fen?tre locale` had lost its accent with
  the character, `Profilage Robuste` and `Nombre d'onde` never had one. Held here in the sources, by the accents, the
  elisions (`d'onde`) and a short list of French words. The other windows are not held: STRAT, RE and the HUB show
  French on purpose in places (rule 11 of CLAUDE.md allows it in what the user reads), and that is the user's call.

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
#: A question mark that is not the end of a question: glued to what follows (`fen?tre`, `d*?{value}`), or standing
#: alone before an interval, a lowercase word or inside `(or ? if`.
STRAY_MARK = re.compile(r"\?(?=[A-Za-zÀ-ÿ0-9{\[])|(?<=\s)\?\s+[\[\(a-z]|\(or \?")
#: `Layer 3: SiO2  n@lambda₀=1.460  ? QWOT`: the mark stands for a QWOT that is not a finite number. Not a lost symbol.
MARKS_THAT_ARE_VALUES = ("  ? QWOT\n",)
SPLINE_WINDOW = sorted((ROOT / "certus" / "ui").glob("certus_index_spline*.py"))
FRENCH = (
    re.compile(r"[àâçéèêëîïôùûÀÂÇÉÈÊÔÛ]"),
    re.compile(r"\b[dlnqsjcDLNQSJC]'[a-zéèêà]{2,}"),
    re.compile(r"\b(profilage|robuste|demi|fen[êe]tre|nombre|onde|couches?|[ée]paisseurs?|longueur|seuil|criblage)\b", re.IGNORECASE),
)


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


def test_the_three_other_sentences_of_the_rmse_tab_have_their_symbols():
    ui = ROOT / "certus" / "ui"
    texts = {
        name: [text for _line, text in visible_strings(ui / f"certus_index_spline_corridor_{name}.py")]
        for name in ("rmse_plot", "rmse_view", "worker")
    }
    assert any("Corridor profile RMSE(d) — best d* = " in text for text in texts["rmse_plot"])
    assert any(" | robust interval ∈ [" in text for text in texts["rmse_view"])
    assert any("(center d* ≈ " in text for text in texts["worker"])


def test_no_question_mark_stands_where_a_symbol_was():
    stray = []
    for path in INTERFACE:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        glued = {  # the constant part of an f-string that ends on a mark, right before a value
            id(part)
            for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
            for part, following in zip(node.values, node.values[1:], strict=False)
            if isinstance(part, ast.Constant) and str(part.value).endswith("?") and isinstance(following, ast.FormattedValue)
        }  # fmt: skip
        visible = {text for _line, text in visible_strings(path)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in visible):
                continue
            if node.value.endswith(MARKS_THAT_ARE_VALUES):
                continue
            if id(node) in glued or STRAY_MARK.search(node.value):
                stray.append(f"{path.name}:{node.lineno} {node.value[:60]!r}")
    assert sorted(set(stray)) == []


def test_the_detector_of_stray_marks_sees_them_and_leaves_a_question_alone():
    texts = ("Demi-fen?tre", " | robust interval ? [", "(or ? if active)", "Stop the run?", "Overwrite? It cannot be undone.", "Why?\n")
    assert [bool(STRAY_MARK.search(text)) for text in texts] == [True, True, True, False, False, False]


def test_no_visible_string_of_the_spline_window_is_french():
    french = [
        f"{path.name}:{line} {text[:60]!r}"
        for path in SPLINE_WINDOW
        for line, text in visible_strings(path)
        if any(detector.search(text) for detector in FRENCH)
    ]
    assert french == []
