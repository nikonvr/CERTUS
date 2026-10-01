"""The audit counts as a RESULT table the tables nobody can type in, and only those (plan S6, UX-22).

`table_figures` is what `scripts/audit_ux_certus.py` records about the tables of a window. These tests build real tables, the three kinds
the suite has, and read what it records: an editable stack (an input: its row order is data), a read-only table that sorts, a read-only
table that does not. The verdicts that follow from the figures are in tests/unit/test_the_ux_audit_exempts_only_what_it_says.py.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from scripts.audit_ux_certus import table_figures


def table(*, editable: bool, sorted_: bool = False, interactive: bool = False) -> QTableWidget:
    t = QTableWidget(2, 3)
    t.setHorizontalHeaderLabels(["a", "b", "c"])
    if not editable:
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSortingEnabled(sorted_)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive if interactive else QHeaderView.ResizeMode.Stretch)
    return t


@pytest.fixture
def three_kinds(qapp):
    return [
        table(editable=True),  # the layer stack
        table(editable=False, sorted_=True, interactive=True),  # a result that sorts and widens
        table(editable=False),  # a result that does neither
    ]


def test_every_table_is_counted_and_the_results_apart(three_kinds):
    figures = table_figures(three_kinds)
    assert figures["n_tables"] == 3
    assert figures["tables_sortable"] == 1
    assert figures["tables_resizable"] == 1
    assert figures["n_result_tables"] == 2
    assert figures["result_tables_sortable"] == 1
    assert figures["result_tables_resizable"] == 1


def test_an_editable_table_is_never_a_result_whatever_it_does(qapp):
    """A sorted editable table counts in the totals but is not judged: the stack of layers may not be sorted, and if it were, it would not become a result."""
    figures = table_figures([table(editable=True, sorted_=True, interactive=True)])
    assert (figures["n_tables"], figures["tables_sortable"], figures["tables_resizable"]) == (1, 1, 1)
    assert (figures["n_result_tables"], figures["result_tables_sortable"], figures["result_tables_resizable"]) == (0, 0, 0)


def test_a_window_without_a_table_has_zeros_everywhere(qapp):
    assert set(table_figures([]).values()) == {0}
