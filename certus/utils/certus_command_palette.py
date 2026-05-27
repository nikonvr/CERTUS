"""CERTUS command palette (U3).

A keyboard-first, ``Ctrl+K``-style modal that lets the user search and
trigger any registered action across the current app. Inspired by VS Code
/ Linear / Raycast.

Public API
----------

- :class:`CommandAction` : declarative action description.
- :class:`CertusCommandPalette` : the modal dialog.
- :func:`fuzzy_score` : the scoring used by the palette (pure Python,
  unit-testable without Qt).

Integration (done in ``CertusBaseApp``)
---------------------------------------

- ``self.register_command(action)`` adds a command.
- ``self._default_commands()`` returns the baseline commands installed by
  ``CertusBaseApp`` (Save/Load config, Toggle theme, Copy logs,
  Show shortcuts, Quit). Subclasses override to add app-specific ones.
- ``Ctrl+K`` / ``Ctrl+Shift+P`` open the palette. Both are wired
  automatically on any ``CertusBaseApp`` instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# =============================================================================
# Dataclass
# =============================================================================


@dataclass
class CommandAction:
    """Declarative description of a runnable command.

    Attributes
    ----------
    id:
        Stable identifier (e.g. ``"file.save_config"``). Used for dedup on
        registration.
    title:
        Short human-readable title displayed in bold.
    callback:
        Zero-arg callable invoked when the user accepts the command.
    subtitle:
        Optional longer description shown in a muted tone.
    shortcut:
        Optional keyboard shortcut string (``"Ctrl+S"``) shown on the
        right of the row.
    category:
        Optional group tag (``"File"``, ``"View"``, ...).
    icon_name:
        Optional icon name resolved by :func:`certus_icons.certus_icon`.
    keywords:
        Additional search tokens that don't appear in the title.
    enabled_cb:
        Optional callable returning ``bool`` to dynamically disable the
        row. Default: always enabled.
    """

    id: str
    title: str
    callback: Callable[[], None]
    subtitle: str = ""
    shortcut: str = ""
    category: str = ""
    icon_name: str = ""
    keywords: tuple[str, ...] = ()
    enabled_cb: Callable[[], bool] | None = None

    def is_enabled(self) -> bool:
        if self.enabled_cb is None:
            return True
        try:
            return bool(self.enabled_cb())
        except (RuntimeError, AttributeError, TypeError, ValueError):
            return False

    def search_haystack(self) -> str:
        """Concatenated lower-case search string."""
        parts = [self.title, self.subtitle, self.category, *self.keywords]
        return " ".join(p for p in parts if p).lower()


# =============================================================================
# Fuzzy matcher (pure Python, no rapidfuzz dep)
# =============================================================================


def fuzzy_score(query: str, haystack: str) -> float:
    """Return a score in ``[0.0, 1.0]`` for how well ``query`` matches.

    - Empty query matches everything with a neutral positive score.
    - Exact substring match is strongly boosted.
    - Otherwise, every character of ``query`` is greedily located in
      ``haystack`` in order; consecutive matches score higher than
      scattered ones.
    - Returns ``0.0`` if the query cannot be subsequence-matched at all.
    """
    q = (query or "").strip().lower()
    h = (haystack or "").lower()
    if not q:
        return 0.5
    if not h:
        return 0.0

    # Strong boost for exact substring
    if q in h:
        # Earlier match = higher score
        pos = h.find(q)
        return 0.9 + 0.1 * (1.0 - min(pos, 80) / 80.0)

    # Greedy subsequence with consecutive bonus
    i = 0
    streak = 0
    streak_bonus = 0.0
    matched = 0
    for ch in q:
        found = h.find(ch, i)
        if found < 0:
            return 0.0
        if found == i:
            streak += 1
            streak_bonus += 0.05 * streak
        else:
            streak = 0
        matched += 1
        i = found + 1

    base = matched / max(len(q), 1)
    return min(0.85, 0.4 * base + streak_bonus)


def rank_commands(
    query: str, actions: "list[CommandAction]", *, min_score: float = 0.0
) -> "list[tuple[float, CommandAction]]":
    """Return actions sorted by descending fuzzy score.

    Items with score < ``min_score`` are dropped. With an empty query the
    actions are returned in declaration order (with a neutral score).
    """
    if not query.strip():
        return [(0.5, a) for a in actions]
    scored: list[tuple[float, CommandAction]] = []
    for a in actions:
        s = fuzzy_score(query, a.search_haystack())
        if s > min_score:
            scored.append((s, a))
    scored.sort(key=lambda t: (-t[0], t[1].category, t[1].title.lower()))
    return scored


# =============================================================================
# Qt modal
# =============================================================================


def _lazy_qt():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtWidgets import (
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    return {
        "Qt": Qt,
        "QKeyEvent": QKeyEvent,
        "QDialog": QDialog,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QListWidget": QListWidget,
        "QListWidgetItem": QListWidgetItem,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def _build_palette_class():
    """Factory: builds the QDialog subclass lazily to avoid Qt at import time."""
    q = _lazy_qt()
    Qt = q["Qt"]

    class CertusCommandPalette(q["QDialog"]):  # type: ignore[name-defined]
        """Modal command palette. Instantiate fresh on each open.

        Usage::

            palette = CertusCommandPalette(parent, actions)
            palette.exec()
        """

        def __init__(self, parent, actions: "list[CommandAction]"):
            super().__init__(parent)
            self._all_actions: list[CommandAction] = list(actions)
            self._filtered: list[CommandAction] = []

            self.setWindowTitle("Command palette")
            self.setModal(True)
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            self.setMinimumWidth(560)
            self.setMinimumHeight(360)

            self._build_ui()
            self._apply_premium_style()
            self._refresh()

            # Center over parent
            if parent is not None:
                geo = parent.geometry()
                self.move(
                    geo.center().x() - self.width() // 2,
                    geo.top() + max(80, geo.height() // 6),
                )

        # -- UI -----------------------------------------------------------
        def _build_ui(self):
            from certus.utils.certus_ux import OBJ

            root = q["QVBoxLayout"](self)
            root.setContentsMargins(16, 16, 16, 16)
            root.setSpacing(10)

            # Search input
            self.input = q["QLineEdit"](self)
            self.input.setObjectName(OBJ.SEARCH_INPUT)
            self.input.setPlaceholderText("Type a command or search…")
            self.input.textChanged.connect(self._on_query_changed)
            root.addWidget(self.input)

            # Results list
            self.list = q["QListWidget"](self)
            self.list.setUniformItemSizes(False)
            self.list.itemActivated.connect(self._on_item_activated)
            root.addWidget(self.list, 1)

            # Footer hint
            hint_row = q["QHBoxLayout"]()
            hint_row.setContentsMargins(0, 0, 0, 0)
            hint_row.setSpacing(8)
            hint_row.addStretch(1)
            for label_text in ("↑↓ navigate", "↵ run", "Esc close"):
                lbl = q["QLabel"](label_text)
                lbl.setObjectName(OBJ.KBD)
                hint_row.addWidget(lbl)
            root.addLayout(hint_row)

            # Keyboard: forward ↑↓ from input to list
            self.input.installEventFilter(self)

        def _apply_premium_style(self):
            from certus.ui.certus_ui import CertusTheme as T
            from certus.utils.certus_ux import Radius

            self.setStyleSheet(
                f"""
                CertusCommandPalette {{
                    background-color: {T.SURFACE};
                    border: 1px solid {T.BORDER};
                    border-radius: {Radius.LG}px;
                }}
                QListWidget {{
                    background: transparent;
                    border: none;
                    padding: 4px;
                }}
                QListWidget::item {{
                    padding: 10px 12px;
                    border-radius: {Radius.SM}px;
                    color: {T.TEXT_MAIN};
                }}
                QListWidget::item:selected {{
                    background-color: {T.PRIMARY};
                    color: #ffffff;
                }}
                """
            )

        # -- Filtering ----------------------------------------------------
        def _on_query_changed(self, _text: str):
            self._refresh()

        def _refresh(self):
            self.list.clear()
            self._filtered.clear()
            ranked = rank_commands(self.input.text(), self._all_actions)
            for _score, action in ranked:
                if not action.is_enabled():
                    continue
                item = q["QListWidgetItem"](self._format_row(action))
                item.setData(Qt.ItemDataRole.UserRole, action.id)
                self.list.addItem(item)
                self._filtered.append(action)
            if self.list.count() > 0:
                self.list.setCurrentRow(0)

        def _format_row(self, a: "CommandAction") -> str:
            lines = [a.title]
            if a.subtitle:
                lines.append(a.subtitle)
            if a.category or a.shortcut:
                tail = []
                if a.category:
                    tail.append(a.category)
                if a.shortcut:
                    tail.append(a.shortcut)
                lines.append(" · ".join(tail))
            return "\n".join(lines)

        # -- Key handling -------------------------------------------------
        def eventFilter(self, obj, event):
            if obj is self.input and event.type() == event.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._move_selection(1 if key == Qt.Key.Key_Down else -1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._accept_current()
                    return True
                if key == Qt.Key.Key_Escape:
                    self.reject()
                    return True
            return super().eventFilter(obj, event)

        def _move_selection(self, delta: int):
            n = self.list.count()
            if n == 0:
                return
            row = (self.list.currentRow() + delta) % n
            self.list.setCurrentRow(row)

        def _accept_current(self):
            row = self.list.currentRow()
            if 0 <= row < len(self._filtered):
                action = self._filtered[row]
                self.accept()
                try:
                    action.callback()
                except (RuntimeError, AttributeError, TypeError, ValueError):  # pragma: no cover - defensive
                    import logging

                    logging.getLogger("CERTUS").exception("Command %r failed", action.id)

        def _on_item_activated(self, *_args):
            self._accept_current()

    return CertusCommandPalette


# Lazily instantiated; avoids importing Qt at module import for headless tests.
_PALETTE_CLS = None


def open_command_palette(parent, actions: "list[CommandAction]"):
    """Convenience helper: open a modal palette with ``actions``."""
    global _PALETTE_CLS
    if _PALETTE_CLS is None:
        _PALETTE_CLS = _build_palette_class()
    dlg = _PALETTE_CLS(parent, actions)
    return dlg.exec()


__all__ = [
    "CommandAction",
    "fuzzy_score",
    "rank_commands",
    "open_command_palette",
]
