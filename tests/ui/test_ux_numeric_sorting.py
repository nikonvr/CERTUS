"""A column of numbers must sort as numbers (step 2.10).

ExcelTableWidget sorts, and its cells hold QTableWidgetItem carrying text, so Qt
compared strings. Measured 2026-09-05, before the fix:

    inserted  ['300.0', '1000.0', '450.0', '-12,5', 'n/a']
    sorted    ['1000.0', '-12,5', '300.0', '450.0', 'n/a']

1000 nm ahead of 300 nm - and the column looks sorted, which is the whole
problem. This is the defect step 2.10 predicted would come back the moment
sorting was restored, and it did.

The obvious fix does NOT work, and the mission order says so with measurements:
writing the value into Qt.ItemDataRole.EditRole neither sorts (QTableWidgetItem
compares the DisplayRole) nor is harmless (on this class Qt treats EditRole and
DisplayRole as one value, so "-12,5" started displaying as "-12.5" - the French
decimal comma vanished from the screen).

Hence the two families of assertion below: the ORDER must become numeric, and
the DISPLAYED TEXT must be untouched, comma included.
"""

from __future__ import annotations

import pytest

VALUES = ["300.0", "1000.0", "450.0", "-12,5", "n/a"]


@pytest.fixture
def table(qapp):
    from certus.ui.certus_ui_widgets_utils import ExcelTableWidget

    widget = ExcelTableWidget()
    widget.setColumnCount(1)
    yield widget
    widget.deleteLater()


def _fill(widget, values):
    from PyQt6.QtWidgets import QTableWidgetItem

    widget.setSortingEnabled(False)
    widget.setRowCount(len(values))
    for row, value in enumerate(values):
        widget.setItem(row, 0, QTableWidgetItem(value))
    widget.setSortingEnabled(True)


def test_a_numeric_column_sorts_by_value(table) -> None:
    """300 must come before 1000, whatever their string forms."""
    _fill(table, VALUES)
    table.sortItems(0)
    ordered = [table.item(r, 0).text() for r in range(table.rowCount())]

    numbers = [t for t in ordered if t != "n/a"]
    as_floats = [float(t.replace(",", ".")) for t in numbers]
    assert as_floats == sorted(as_floats), f"the column is not in numeric order: {ordered}"


def test_sorting_does_not_rewrite_what_is_displayed(table) -> None:
    """The French decimal comma must survive: the EditRole fix silently ate it."""
    _fill(table, VALUES)
    table.sortItems(0)
    ordered = [table.item(r, 0).text() for r in range(table.rowCount())]

    assert sorted(ordered) == sorted(VALUES), (
        f"sorting changed the displayed strings: {ordered} instead of a permutation of {VALUES}"
    )
    assert "-12,5" in ordered, "the decimal comma was rewritten as a dot on screen"


def test_non_numeric_cells_still_sort_alphabetically(table) -> None:
    """A text column must keep working; numbers are the special case, not the rule."""
    words = ["delta", "alpha", "charlie", "bravo"]
    _fill(table, words)
    table.sortItems(0)
    ordered = [table.item(r, 0).text() for r in range(table.rowCount())]

    assert ordered == sorted(words), f"a text column no longer sorts alphabetically: {ordered}"
