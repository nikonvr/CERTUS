"""STRAT's multi-seed tab must speak the language of the suite (plan UX, 5.8).

The whole tab was written in French - and in French with the accents stripped,
so it was neither correct French nor English: "realisation", "Duree",
"deja mesuree". Its summary line also read *"1 realisation(s) ont trouve sur
4"*: a plural verb on a count that is very often 1, with the number of seeds
that FOUND something being exactly what the operator watches.

⚠️ Two things in this tab look like labels and are NOT:

- the objective combo. Its items are handed verbatim to
  ``orchestre_multigraine.py`` as ``--objectif``, whose ``choices`` are
  ``("premier", "meilleur")``. Renaming the items would make the runner reject
  the command. The English wording is therefore a LABEL and the French token
  stays as the item's data - the test below pins that;
- ``nuit`` in the budget tooltip. It is a keyword the runner's duration parser
  accepts, so it is quoted as such rather than translated.

The row states ("en attente", "trouve", ...) are internal tokens of a pure state
machine that ``tests/unit/test_strat_multigraine_ui.py`` pins by value. They are
therefore translated at DISPLAY time and left untouched at the source.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

#: Unambiguously French tokens, matched on word boundaries so that "blocs" does
#: not fire on "Blocks". ``nuit`` is deliberately absent: see the module docstring.
FRENCH_ON_SCREEN = (
    "realisation",
    "realisations",
    "lancer",
    "finaliser",
    "graine",
    "graines",
    "duree",
    "composant",
    "objectif",
    "plantage",
    "cible",
    "recherche",
    "attente",
    "essayee",
    "mesuree",
    "trouve",
    "blocs",
    "etat",
    "chiffre",
    "empilement",
)


@pytest.fixture(scope="module")
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _tab(win):
    """The multi-seed tab, found by containment rather than by its title."""
    for i in range(win.tabs.count()):
        page = win.tabs.widget(i)
        if page is not None and page.isAncestorOf(win._mg_table):
            return i, page
    raise AssertionError("the multi-seed tab is not in the tab bar")


def _texts(win) -> list[str]:
    """Everything the operator can read in that tab, tooltips included."""
    from PyQt6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QTableWidget

    index, page = _tab(win)
    out = [win.tabs.tabText(index)]
    for w in page.findChildren((QLabel, QAbstractButton, QComboBox, QLineEdit, QTableWidget)):
        if isinstance(w, QLabel | QAbstractButton):
            out.append(w.text())
        if isinstance(w, QLineEdit):
            out.append(w.placeholderText())
        if isinstance(w, QComboBox):
            out.extend(w.itemText(i) for i in range(w.count()))
        if isinstance(w, QTableWidget):
            header = w.horizontalHeader()
            model = w.model()
            out.extend(str(model.headerData(c, header.orientation()) or "") for c in range(w.columnCount()))
        out.append(w.toolTip())
    return [t for t in out if t and t.strip()]


def test_there_is_text_to_inspect(strat):
    """Contrôle négatif : an empty list would make everything below pass."""
    assert len(_texts(strat)) >= 15, f"only {len(_texts(strat))} string(s) found in the multi-seed tab"


@pytest.mark.parametrize("word", FRENCH_ON_SCREEN)
def test_no_french_word_reaches_the_screen(strat, word: str):
    pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
    found = [t for t in _texts(strat) if pattern.search(t)]
    assert not found, f"French in an English window ({word!r}): {found[:3]}"


# =============================================================================
# The value behind the label
# =============================================================================


def test_the_objective_still_sends_what_the_runner_accepts(strat):
    """Translating the items would make ``--objectif`` fail its ``choices``."""
    combo = strat._mg_objectif
    sent = {combo.itemData(i) for i in range(combo.count())}
    assert sent == {"premier", "meilleur"}, (
        f"the objective combo would send {sent} to the runner, which only accepts "
        "'premier' and 'meilleur' - the label was renamed along with the value"
    )


def test_the_command_line_carries_the_selected_objective(strat):
    """End to end: whatever is picked must reach the command line as its token."""
    from certus.ui.certus_strat_multigraine_ui import construire_arguments

    combo = strat._mg_objectif
    for i in range(combo.count()):
        combo.setCurrentIndex(i)
        args = construire_arguments(
            composant="r75x2",
            budget="2h",
            objectif=strat._mg_objectif_courant(),
            seel_cible=None,
            slots=2,
        )
        assert args[args.index("--objectif") + 1] in ("premier", "meilleur"), (
            f"item {combo.itemText(i)!r} puts {args[args.index('--objectif') + 1]!r} on the command line"
        )


# =============================================================================
# The summary line, a pure function - so its grammar is testable directly
# =============================================================================


def _state(found: int, total: int):
    from certus.ui.certus_strat_multigraine_ui import EtatMultigraine, LigneGraine

    e = EtatMultigraine()
    for i in range(total):
        line = LigneGraine(100 + i)
        line.deposables = 1 if i < found else 0
        line.etat = "trouve" if i < found else "rien"
        e.lignes[100 + i] = line
    return e


def test_one_seed_is_reported_in_the_singular():
    from certus.ui.certus_strat_multigraine_ui import resumer

    text = resumer(_state(found=1, total=4))
    assert "1 seed found" in text, f"the summary reads {text.split(' · ')[0]!r} for a single seed"


def test_several_seeds_are_reported_in_the_plural():
    from certus.ui.certus_strat_multigraine_ui import resumer

    text = resumer(_state(found=3, total=4))
    assert "3 seeds found" in text, f"the summary reads {text.split(' · ')[0]!r} for three seeds"


def test_none_found_is_not_reported_as_one():
    """Contrôle négatif : zero takes the plural in English, like any count but one."""
    from certus.ui.certus_strat_multigraine_ui import resumer

    text = resumer(_state(found=0, total=4))
    assert "0 seeds found" in text, f"the summary reads {text.split(' · ')[0]!r} when nothing was found"
