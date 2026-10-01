"""The results table of the multi-seed tab is read-only and sorts on its figures (audit v2, plan S6, UX-22).

Measured 2026-10-01 with `scripts/audit_ux_certus.py`: CERTUS-STRAT had two tables and none of them could be sorted. The
multi-seed table is the one that is a RESULT (one row per seed: status, SEEL, blocks, crash rate, duration), so it is the one an
operator wants to sort ("best SEEL first"). The layer table next to it is a stack, whose order is the physics: it stays as it is.

Three things go with sorting a table that is refilled by a state machine at every event, and each has a test:

    the order is on the figure, not on the text   "12.5000" comes before "5.0000" as text; "5.00 %" after "12.00 %"
    a seed that has no figure yet goes last       "--" is not zero, in either direction
    a refill never mixes two rows                 the cells are written one by one: with the sort live, the first cell sends its row elsewhere
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QTabWidget

from certus.ui.certus_strat_multigraine_ui import CertusStratMultigraineMixin, LigneGraine

SEED, STATUS, SEEL, BLOCKS, CRASH, DURATION = range(6)


class Holder(CertusStratMultigraineMixin):
    """The tab on its own: what `CertusStratApp` gives it is a `tabs` widget to add itself to."""

    def __init__(self) -> None:
        self.tabs = QTabWidget()


@pytest.fixture
def tab(qapp):
    holder = Holder()
    holder._create_multigraine_tab()
    try:
        yield holder
    finally:
        holder.tabs.close()


def fill(tab: Holder, rows: list[LigneGraine]) -> None:
    tab._mg_etat.lignes = {row.graine: row for row in rows}
    tab._mg_rafraichir()


def column(tab: Holder, index: int) -> list[str]:
    table = tab._mg_table
    return [table.item(r, index).text() for r in range(table.rowCount())]


THREE = [
    LigneGraine(graine=3, etat="trouve", seel=12.5, n_blocs=40, crash=0.12, minutes=95.0),
    LigneGraine(graine=1, etat="trouve", seel=5.0, n_blocs=8, crash=0.05, minutes=7.0),
    LigneGraine(graine=2, etat="en cours"),
]


def test_the_table_opens_with_the_seeds_in_increasing_order(tab):
    fill(tab, THREE)
    assert column(tab, SEED) == ["1", "2", "3"]


def test_the_table_is_a_results_table_nobody_types_in(tab):
    assert tab._mg_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert tab._mg_table.isSortingEnabled()


@pytest.mark.parametrize(
    ("col", "ascending", "descending"),
    [
        (SEEL, ["5.0000", "12.5000", "--"], ["12.5000", "5.0000", "--"]),
        (BLOCKS, ["8", "40", "--"], ["40", "8", "--"]),
        (CRASH, ["5.00 %", "12.00 %", "--"], ["12.00 %", "5.00 %", "--"]),
        (DURATION, ["7 min", "95 min", "--"], ["95 min", "7 min", "--"]),
    ],
    ids=["SEEL", "blocks", "crash rate", "duration"],
)
def test_a_figure_column_sorts_on_the_number_and_leaves_the_unmeasured_seed_last(tab, col, ascending, descending):
    fill(tab, THREE)
    tab._mg_table.sortByColumn(col, Qt.SortOrder.AscendingOrder)
    assert column(tab, col) == ascending
    tab._mg_table.sortByColumn(col, Qt.SortOrder.DescendingOrder)
    assert column(tab, col) == descending


def test_the_status_column_sorts_as_text(tab):
    fill(tab, THREE)
    tab._mg_table.sortByColumn(STATUS, Qt.SortOrder.AscendingOrder)
    assert column(tab, STATUS) == ["found", "found", "running"]


def test_a_refill_keeps_every_cell_in_the_row_of_its_seed_while_the_table_is_sorted(tab):
    """The operator sorts on SEEL, descending; the next event rewrites the table. A seed's cells must stay together."""
    fill(tab, THREE)
    tab._mg_table.sortByColumn(SEEL, Qt.SortOrder.DescendingOrder)
    fill(
        tab,
        [
            LigneGraine(graine=4, etat="trouve", seel=9.0, n_blocs=22, crash=0.07, minutes=31.0),
            *THREE,
        ],
    )
    table = tab._mg_table
    by_seed = {
        table.item(r, SEED).text(): [table.item(r, c).text() for c in (SEEL, BLOCKS, CRASH, DURATION)] for r in range(table.rowCount())
    }
    assert by_seed == {
        "1": ["5.0000", "8", "5.00 %", "7 min"],
        "2": ["--", "--", "--", "--"],
        "3": ["12.5000", "40", "12.00 %", "95 min"],
        "4": ["9.0000", "22", "7.00 %", "31 min"],
    }
    # and the order the operator chose is still the one on screen
    assert column(tab, SEEL) == ["12.5000", "9.0000", "5.0000", "--"]


def test_a_refill_with_fewer_rows_leaves_no_ghost_row(tab):
    fill(tab, THREE)
    fill(tab, THREE[:1])
    assert column(tab, SEED) == ["3"]
