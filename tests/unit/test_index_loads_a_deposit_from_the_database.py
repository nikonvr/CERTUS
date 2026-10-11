"""INDEX loads a measured layer of the deposit database (`example/database_depots/`) as it loads a file.

The button "Deposit database…" opens `DepositDatabaseDialog`, which lists the catalogue and hands back the deposit
chosen; `load_from_deposit_database` then goes through `load_file`, so a deposit taken from the database and the same
file opened by hand give INDEX the same measurement.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from certus.utils.certus_depots_db import load_catalogue, measurement_path  # noqa: E402

DEPOTS = load_catalogue()


def _first(mode: str) -> dict:
    return next(d for d in DEPOTS if [channel["mode"] for channel in d["voies"]] == [mode])


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "INDEX deposit database", main_windows_only=True)


@pytest.fixture
def dialog(qapp):
    from certus.ui.certus_depots_dialog import DepositDatabaseDialog

    box = DepositDatabaseDialog()
    yield box
    box.deleteLater()


@pytest.fixture
def index_window(qapp):
    from certus.ui.certus_index_ui import CertusIndexApp

    return CertusIndexApp()


def _visible_rows(box) -> list[int]:
    return [row for row in range(box.table.rowCount()) if not box.table.isRowHidden(row)]


def test_the_dialog_lists_every_deposit_of_the_catalogue(dialog):
    assert DEPOTS
    assert dialog.table.rowCount() == len(DEPOTS)
    assert [dialog.table.item(row, 0).text() for row in range(len(DEPOTS))] == [d["echantillon"] for d in DEPOTS]


def test_the_filter_keeps_the_rows_holding_every_word(dialog):
    dialog.filter.setText("nb2o5")
    shown = _visible_rows(dialog)
    assert shown
    assert len(shown) == sum(1 for d in DEPOTS if (d["materiau"] or {}).get("valeur") == "Nb2O5")
    dialog.filter.setText("nb2o5 no-such-word")
    assert not _visible_rows(dialog)
    dialog.filter.setText("")
    assert len(_visible_rows(dialog)) == len(DEPOTS)


def test_load_needs_a_visible_selected_row(dialog):
    assert not dialog.load_button.isEnabled()
    assert dialog.selected_entry() is None
    dialog.table.selectRow(3)
    assert dialog.load_button.isEnabled()
    assert dialog.selected_entry() == DEPOTS[3]
    dialog.filter.setText("no-such-word")
    assert not dialog.load_button.isEnabled()
    assert dialog.selected_entry() is None


@pytest.mark.parametrize("mode", ["T", "R"])
def test_index_takes_the_chosen_deposit_as_it_takes_the_file(index_window, monkeypatch, mode):
    from PyQt6.QtWidgets import QDialog

    from certus.ui.certus_depots_dialog import DepositDatabaseDialog

    depot = _first(mode)
    monkeypatch.setattr(DepositDatabaseDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(DepositDatabaseDialog, "selected_entry", lambda self: depot)
    assert index_window.load_from_deposit_database() is True
    from_database = index_window.target_data.copy()

    assert list(from_database.columns) == ["lambda", mode]
    assert len(from_database) == depot["points"]
    assert from_database["lambda"].min() == pytest.approx(depot["lambda_nm"][0])
    assert from_database["lambda"].max() == pytest.approx(depot["lambda_nm"][1])

    assert index_window.load_file(str(measurement_path(depot))) is True
    assert index_window.target_data.equals(from_database)


def test_a_cancelled_dialog_loads_nothing(index_window, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    from certus.ui.certus_depots_dialog import DepositDatabaseDialog

    before = index_window.target_data
    monkeypatch.setattr(DepositDatabaseDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert index_window.load_from_deposit_database() is False
    assert index_window.target_data is before


def test_the_button_opens_the_database(index_window, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    from certus.ui.certus_depots_dialog import DepositDatabaseDialog

    opened: list[int] = []

    def fake_exec(self):
        opened.append(self.table.rowCount())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(DepositDatabaseDialog, "exec", fake_exec)
    index_window.btn_load_deposit.click()
    assert opened == [len(DEPOTS)]
