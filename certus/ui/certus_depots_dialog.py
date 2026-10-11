"""The deposit database dialog: pick a measured single layer and hand its measurement file to the module that asked.

The rows come from `example/database_depots/catalogue.json` (`certus/utils/certus_depots_db.py`). A material or a
substrate is shown only when the file or sample name states it: the catalogue infers nothing from a spectrum, and the
dialog adds nothing to it.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from certus.ui.certus_ui import CertusTheme, create_styled_label
from certus.utils.certus_depots_db import attribute, channels_label, load_catalogue, range_label

COLUMNS = ("Sample", "Material", "Substrate", "Channels", "Range (nm)", "Measured")


class DepositDatabaseDialog(QDialog):
    """The deposits of the database, filterable by words; `selected_entry()` is the one chosen."""

    def __init__(self, parent: Any = None, entries: list[dict[str, Any]] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deposit database — Photon RT single layers")
        self.resize(900, 560)
        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};")
        self._entries = list(entries) if entries is not None else load_catalogue()
        layout = QVBoxLayout(self)
        layout.addWidget(create_styled_label(
            f"{len(self._entries)} measured single layers. A material or a substrate is shown only when "
            "the file or sample name states it.",
            style="subtitle",
        ))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter: sample, material, substrate, channel…")
        self.filter.setToolTip("Keeps the rows whose text contains every word typed here.")
        self.filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter)
        self.table = QTableWidget(len(self._entries), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        for row, entry in enumerate(self._entries):
            measured = (entry["voies"][0].get("debut") or "")[:10] if entry.get("voies") else ""
            cells = (entry["echantillon"], attribute(entry, "materiau"), attribute(entry, "substrat"),
                     channels_label(entry), range_label(entry), measured)
            for column, text in enumerate(cells):
                self.table.setItem(row, column, QTableWidgetItem(text))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        self.load_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        self.load_button.setText("Load")
        self.load_button.setToolTip("Load the measurement of the selected layer.")
        self.load_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_filter(self, text: str) -> None:
        words = text.lower().split()
        for row in range(self.table.rowCount()):
            line = " ".join(self.table.item(row, column).text().lower() for column in range(self.table.columnCount()))
            self.table.setRowHidden(row, not all(word in line for word in words))
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.load_button.setEnabled(self.selected_entry() is not None)

    def _double_clicked(self, _row: int, _column: int) -> None:
        self.accept()

    def selected_entry(self) -> dict[str, Any] | None:
        """The deposit of the selected row, None when no visible row is selected."""
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        if len(rows) != 1:
            return None
        row = rows.pop()
        return None if self.table.isRowHidden(row) else self._entries[row]

    def accept(self) -> None:
        if self.selected_entry() is not None:
            super().accept()
