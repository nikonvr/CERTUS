"""Tests de non-régression validant l'ergonomie : Drag & Drop universel et auto-scroll."""

from __future__ import annotations

import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QMimeData, QUrl, QPointF
from PyQt6.QtGui import QDragEnterEvent

os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication([])

from certus.ui.certus_design_ui import CertusDesignApp
from certus.ui.certus_strat_stack_progress_widget import CertusStratStackProgressWidget


def _drag_enter(widget, filename: str):
    """Construit un QDragEnterEvent portant un seul fichier, et le soumet au widget.

    Rendu tel quel pour que l'appelant lise `isAccepted()`.
    """
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(Path(filename).resolve()))])
    event = QDragEnterEvent(
        QPoint(100, 100),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.dragEnterEvent(event)
    return event


def test_drag_and_drop_event_handling():
    """Vérifier que CertusBaseApp accepte les fichiers .json par glisser-déposer."""
    window = CertusDesignApp()
    # ⚠️ `acceptDrops()` N'EST PAS UN CONTROLE : mesure le 2026-09-08, un
    # QMainWindow NU le rend deja True. L'assertion qui se trouvait ici ne
    # pouvait donc pas echouer. Ce qui teste quelque chose est qu'un type que
    # la fenetre ne sait pas lire soit REFUSE -- sans quoi « accepte tout »
    # passerait aussi bien que « accepte ce qu'il faut ».
    refus = _drag_enter(window, "quelque_chose.exe")
    assert refus.isAccepted() is False, (
        "la fenetre accepte un type qu'elle ne sait pas lire : le filtre par extension ne mord pas"
    )

    # Simuler un drag enter avec un fichier JSON
    mime = QMimeData()
    test_json = Path("example/rampe_1_55_400_900_30c.json").resolve()
    mime.setUrls([QUrl.fromLocalFile(str(test_json))])

    from PyQt6.QtCore import Qt, QPoint
    event = QDragEnterEvent(
        QPoint(100, 100),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(event)
    assert event.isAccepted() is True
    window.close()


def test_stack_progress_auto_scroll():
    """Vérifier que CertusStratStackProgressWidget ajuste le scroll sans exception."""
    widget = CertusStratStackProgressWidget()
    from PyQt6.QtWidgets import QTableWidget
    table = QTableWidget(10, 4)
    widget.init_stack_from_table(table)
    assert len(widget.layer_cards) == 10

    # Mettre à jour la couche 5
    widget.update_progress(5, 10, 50)
    assert widget.layer_cards[4]._state == "active"
    assert widget.layer_cards[3]._state == "done"
    assert widget.layer_cards[5]._state == "pending"
    widget.close()


def test_plot_double_click_auto_range():
    """Vérifier que le double-clic sur CertusScientificPlot réinitialise l'échelle."""
    from certus.ui.certus_plot import CertusScientificPlot
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent, QPointF

    plot = CertusScientificPlot(title="Test Plot")
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(50, 50),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    plot.mouseDoubleClickEvent(event)
    assert event.isAccepted() is True
    plot.close()


def test_hub_shortcuts_and_drag_drop():
    """Vérifier que le HUB installe les raccourcis 1-9 et accepte le Drag & Drop."""
    from CERTUS_HUB import CertusHub

    hub = CertusHub()
    # ⚠️ `acceptDrops()` N'EST PAS UN CONTROLE : mesure le 2026-09-08, un
    # QMainWindow NU le rend deja True. L'assertion qui se trouvait ici ne
    # pouvait donc pas echouer. Ce qui teste quelque chose est qu'un type que
    # la fenetre ne sait pas lire soit REFUSE -- sans quoi « accepte tout »
    # passerait aussi bien que « accepte ce qu'il faut ».
    refus = _drag_enter(hub, "quelque_chose.exe")
    assert refus.isAccepted() is False, (
        "la fenetre accepte un type qu'elle ne sait pas lire : le filtre par extension ne mord pas"
    )

    # Vérifier le drag enter sur le HUB
    mime = QMimeData()
    test_json = Path("example/rampe_1_55_400_900_30c.json").resolve()
    mime.setUrls([QUrl.fromLocalFile(str(test_json))])

    event = QDragEnterEvent(
        QPoint(100, 100),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    hub.dragEnterEvent(event)
    assert event.isAccepted() is True
    hub.close()
