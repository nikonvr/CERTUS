"""An empty-state overlay must follow the model, not the window size (step 2.19).

_Watcher only re-synchronised on QEvent.Type.Resize, so between two resizes the
overlay said whatever it last said. Measured 2026-09-04, in both directions:

    attach (0 row)     -> overlay visible = True
    setRowCount(5)     -> overlay visible = True    <- it HIDES the data
    a resize           -> overlay visible = False
    setRowCount(0)     -> overlay visible = False   <- it should have come back

The first line of that table is the serious one: a panel that has just been
filled with results stays covered by a card saying there is nothing to show.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def table(qapp):
    from PyQt6.QtWidgets import QTableWidget

    widget = QTableWidget(0, 2)
    widget.resize(400, 300)
    yield widget
    widget.deleteLater()


def _attach(widget):
    from certus.ui.certus_empty_state import attach_empty_state_to

    return attach_empty_state_to(
        widget,
        icon_name="table",
        title="No data",
        description="Load a file to populate this table.",
    )


def test_overlay_hides_as_soon_as_rows_arrive(table, qapp) -> None:
    """Filling a table must uncover it, with no resize in between."""
    overlay = _attach(table)
    # isVisibleTo, not isVisible: the table has no shown ancestor here, so
    # isVisible() would answer False whatever the overlay decided - a test that
    # passes for the wrong reason.
    assert overlay.isVisibleTo(table), "the overlay did not appear on an empty table"

    table.setRowCount(5)
    qapp.processEvents()

    assert not overlay.isVisibleTo(table), (
        "the empty-state card still covers a table that now holds 5 rows"
    )


def test_overlay_returns_when_the_table_is_emptied(table, qapp) -> None:
    """And it must come back, again without a resize."""
    overlay = _attach(table)
    table.setRowCount(5)
    qapp.processEvents()

    table.setRowCount(0)
    qapp.processEvents()

    assert overlay.isVisibleTo(table), (
        "the table is empty again and nothing tells the operator why it is blank"
    )


# --- coverage: the registry knew six attribute NAMES, and only two modules --------
#
# _EMPTY_STATE_HINTS keys on attribute names that only DESIGN and RE own, so the
# other modules showed blank tables with no word of explanation. Measured
# 2026-09-05, before the sweep over persistable tables:
#
#     DESIGN 3/3 overlays   RE 2/2   INDEX 0/2   FIELD 0/4   SPLINE 0/3
#
# The registry keeps its role - overriding the wording where a specific message
# exists - which is what stops the coverage from expiring at the next rename.

@pytest.mark.parametrize(
    "mod_path,cls_name",
    [
        ("certus.ui.certus_index_ui", "CertusIndexApp"),
        ("certus.ui.certus_field_ui", "CertusFieldApp"),
    ],
)
def test_every_table_of_a_module_gets_an_empty_state(qapp, mod_path, cls_name) -> None:
    """A blank table must say why it is blank."""
    from PyQt6.QtWidgets import QTableView

    from certus.ui import certus_empty_state as es

    es._OVERLAYS.clear()
    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    try:
        tables = win.findChildren(QTableView)
        assert tables, f"{cls_name} has no table at all: this test would prove nothing"
        assert len(es._OVERLAYS) >= len(tables), (
            f"{cls_name}: {len(es._OVERLAYS)} empty states for {len(tables)} tables"
        )
    finally:
        win.close()
        es._OVERLAYS.clear()
