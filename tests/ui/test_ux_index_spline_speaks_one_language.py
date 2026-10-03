"""INDEX SPLINE speaks the language of the rest of the suite, and shows no variable names (audit UX A10, ETAT D85).

Measured 2026-10-02, the window mixed French and English in one view: "Spectre Photométrique (Mesure vs Modèle)" and
"Longueur d'onde lambda (nm)" over "Workflow guide" and "Load spectrum", the KPI banner in French ("RMSE GLOBALE",
"STATUT AJUSTEMENT", "Prêt pour calcul") under a tab named "✦ Synthèse (Overview)" where DESIGN, RE and METAL say
"✦ Synthesis", a stop tooltip that ended in "Raccourci : Échap.", and a field labelled with the variable name
"d_nominal (nm) :".

The rule pinned here is the plain one: every text of the window, and the titles of its two overview plots, is free of
the accented letters of French and of the `name_with_underscore` of a variable. (A single `&` in a button is
tested elsewhere: tests/ui/test_ux_stepper_shows_an_ampersand_as_text.py.)
"""

from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QAbstractButton, QComboBox, QLabel, QTabWidget, QWidget

ACCENTED = re.compile("[éèêëàâçôûîïÉÈÊÀÇÔÛ]")
IDENTIFIER = re.compile("[a-z]{3,}_[a-z]{3,}")


@pytest.fixture
def window(qapp):
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    win = CertusIndexSplineApp()
    win.show()
    try:
        yield win
    finally:
        win.close()


def _widget_texts(win) -> list[tuple[str, str]]:
    """(kind, text) of everything the window writes in words: labels, buttons, tabs, combo items, tooltips."""
    found: list[tuple[str, str]] = []
    for widget in win.findChildren(QWidget):
        kind = type(widget).__name__
        found += [(f"{kind}.toolTip", widget.toolTip()), (f"{kind}.accessibleName", widget.accessibleName())]
        if isinstance(widget, (QLabel, QAbstractButton)):
            found.append((f"{kind}.text", widget.text()))
        if isinstance(widget, QTabWidget):
            found += [(f"{kind}.tab", widget.tabText(i)) for i in range(widget.count())]
        if isinstance(widget, QComboBox):
            found += [(f"{kind}.item", widget.itemText(i)) for i in range(widget.count())]
    return [(kind, text) for kind, text in found if text]


def _plot_texts(win) -> list[tuple[str, str]]:
    found = []
    for name in ("plot_ov_T", "plot_ov_nk"):
        item = getattr(win, name).getPlotItem()
        found.append((f"{name}.title", item.titleLabel.text or ""))
        found += [(f"{name}.{axis}", item.getAxis(axis).labelText or "") for axis in ("bottom", "left")]
    return found


def test_no_text_of_the_window_is_written_in_french(window) -> None:
    french = [(kind, text) for kind, text in _widget_texts(window) + _plot_texts(window) if ACCENTED.search(text)]
    assert not french, "French text in the INDEX SPLINE window:\n" + "\n".join(f"  {k}: {t!r}" for k, t in french)


def test_the_overview_plots_are_titled_and_labelled(window) -> None:
    texts = dict(_plot_texts(window))
    assert all(texts.values()), f"an overview plot lost a title or an axis label: {texts}"


def test_no_label_shows_the_name_of_a_variable(window) -> None:
    labels = [
        (kind, text)
        for kind, text in _widget_texts(window)
        if kind.endswith((".text", ".tab", ".item")) and IDENTIFIER.search(text)
    ]
    assert not labels, "variable-like text in the INDEX SPLINE window:\n" + "\n".join(f"  {k}: {t!r}" for k, t in labels)


def test_the_synthesis_tab_is_named_like_the_other_modules(window) -> None:
    assert window.tabs_main.tabText(0) == "✦ Synthesis"
