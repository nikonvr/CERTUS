"""The HUB grid must fit the catalogue it displays (plan UX, 4.2).

``CERTUS_HUB`` laid the launchers out on a column count written in the source as
``MAX_COLS = 3  # 3x3 Grid (9 modules)``. The catalogue holds **ten** modules, so
the tenth sat alone on a fourth row - the comment described a catalogue that no
longer existed.

The rule checked here is deliberately about layout, not taste: **no row may hold
a single tile while others are full.** How many columns that implies is derived
from the catalogue, so adding an eleventh module cannot reopen the defect.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


# =============================================================================
# The pure rule
# =============================================================================


def test_the_column_count_is_derived_not_hard_coded():
    from certus.core.certus_hub_config import HUB_APP_CATALOG, hub_grid_columns

    cols = hub_grid_columns(len(HUB_APP_CATALOG))
    orphans = len(HUB_APP_CATALOG) % cols
    assert orphans != 1, f"{len(HUB_APP_CATALOG)} modules over {cols} columns leaves one tile alone on the last row"


@pytest.mark.parametrize("n", list(range(2, 17)))
def test_no_catalogue_size_leaves_an_orphan_tile(n: int):
    """Whatever the catalogue grows to, the last row is never a lone tile."""
    from certus.core.certus_hub_config import hub_grid_columns

    cols = hub_grid_columns(n)
    assert 1 <= cols, f"{n} modules gave a non-positive column count"
    assert n % cols != 1 or n <= cols, f"{n} modules over {cols} columns leaves an orphan"


# =============================================================================
# The real window
# =============================================================================


@pytest.fixture(scope="module")
def hub(qapp):
    from PyQt6.QtCore import Qt

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def test_the_rendered_grid_has_no_lone_tile(hub):
    from PyQt6.QtWidgets import QGridLayout

    from certus.ui.certus_hub_widgets import BaseApplicationCard

    cards = hub.findChildren(BaseApplicationCard)
    assert cards, "no launcher found - the guard would be vacuous"

    grids = [g for g in hub.findChildren(QGridLayout) if any(g.indexOf(c) != -1 for c in cards)]
    assert grids, "the launchers are not in a QGridLayout - has the layout changed?"

    per_row: dict[int, int] = {}
    for grid in grids:
        for card in cards:
            idx = grid.indexOf(card)
            if idx == -1:
                continue
            row = grid.getItemPosition(idx)[0]
            per_row[row] = per_row.get(row, 0) + 1

    assert per_row, "no launcher located in the grid"
    if len(per_row) > 1:
        widest = max(per_row.values())
        lonely = [r for r, n in per_row.items() if n == 1 and widest > 1]
        assert not lonely, (
            f"row(s) {lonely} hold a single tile while others hold {widest}: "
            f"distribution {dict(sorted(per_row.items()))}"
        )
