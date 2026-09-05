"""CERTUS keyboard shortcuts overlay (U4).

Introspective modal that lists every keyboard shortcut currently active
on a window:

1. Every ``QShortcut`` child of the window (grouped by context).
2. Every :class:`CommandAction` registered in the window's command
   palette that declares a ``shortcut`` value.

Entries are grouped by category and rendered with kbd-style chips using
the U1 premium QSS (``CertusKbd`` object-name).

Public API
----------

- :func:`collect_window_shortcuts(window) -> list[ShortcutEntry]`
    Pure-Python; does not require showing any UI. Used by tests.
- :func:`open_shortcuts_overlay(window)` — build + exec() the dialog.

Integration
-----------

``CertusBaseApp`` installs ``F1`` (and ``Shift+?``) to
``open_shortcuts_overlay``. Apps may add custom entries by providing
:class:`CommandAction` with a ``shortcut=`` value — they are picked up
automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


# =============================================================================
# Data
# =============================================================================


@dataclass(frozen=True)
class ShortcutEntry:
    """One shortcut row displayed in the overlay."""

    sequence: str
    label: str
    category: str = "General"
    source: str = "shortcut"  # "shortcut" | "command" | "custom"

    def sort_key(self) -> tuple[str, str, str]:
        return (self.category.lower(), self.label.lower(), self.sequence.lower())


# =============================================================================
# Collection
# =============================================================================


def _q_shortcut_key(sc) -> str:
    try:
        return sc.key().toString()
    except AttributeError, RuntimeError, TypeError:
        return ""


_STANDARD_LABELS = {
    "Ctrl+S": "Save configuration",
    "Ctrl+O": "Load configuration",
    "Ctrl+E": "Export",
    "F5": "Run",
    "Esc": "Stop / cancel",
    "F1": "Show shortcuts",
    "Ctrl+L": "Toggle log panel",
    "Ctrl+K": "Open command palette",
    "Ctrl+Shift+P": "Open command palette",
    "Ctrl+Shift+C": "Copy to Excel (plots)",
    "Ctrl+Shift+B": "Copy plot (publication quality)",
    "Ctrl+Shift+D": "Detach plot window",
    "Ctrl+W": "Close window",
    "Shift+?": "Show shortcuts",
}


def collect_window_shortcuts(window) -> list[ShortcutEntry]:
    """Build the full list of shortcut entries for ``window``.

    - Enumerates ``QShortcut`` children (one-level deep) and maps their
      key sequence to a human-friendly label via :data:`_STANDARD_LABELS`
      with a fallback to the raw sequence.
    - Appends every :class:`certus_command_palette.CommandAction`
      registered on the window that has a ``shortcut`` field.
    - Deduplicates on ``(sequence, label)`` pairs — command entries take
      priority over bare ``QShortcut`` mappings (more descriptive).
    """
    entries: list[ShortcutEntry] = []
    seen: set[tuple[str, str]] = set()

    # 1) Commands registered in the palette (richer metadata) take priority.
    cmds = _get_window_commands(window)
    for cmd in cmds:
        seq = getattr(cmd, "shortcut", "") or ""
        if not seq:
            continue
        key = (seq.lower(), cmd.title.lower())
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            ShortcutEntry(
                sequence=seq,
                label=cmd.title,
                category=cmd.category or "General",
                source="command",
            )
        )

    # 2) Bare QShortcut children of the window.
    try:
        from PyQt6.QtGui import QShortcut  # type: ignore

        for child in list(window.children() if hasattr(window, "children") else []):
            try:
                if not isinstance(child, QShortcut):
                    continue
            except RuntimeError, TypeError, ValueError:
                continue
            seq = _q_shortcut_key(child)
            if not seq:
                continue
            label = _STANDARD_LABELS.get(seq, seq)
            key = (seq.lower(), label.lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                ShortcutEntry(
                    sequence=seq,
                    label=label,
                    category=_guess_category(seq, label),
                    source="shortcut",
                )
            )
    except ImportError, AttributeError, RuntimeError, TypeError, ValueError:
        # No Qt / no children / deleted wrappers: skip safely.
        pass

    entries.sort(key=ShortcutEntry.sort_key)
    return entries


def _get_window_commands(window) -> list:
    """Best-effort retrieval of the command list registered on window."""
    cmds = getattr(window, "_commands", None)
    if cmds is None:
        # Build defaults if available without mutating the window.
        try:
            cmds = window._default_commands()  # type: ignore[attr-defined]
        except AttributeError, RuntimeError, TypeError:
            cmds = []
    return list(cmds or [])


def _guess_category(sequence: str, label: str) -> str:
    s = (sequence + " " + label).lower()
    if "save" in s or "load" in s or "open" in s or "export" in s:
        return "File"
    if "run" in s or "stop" in s or "pause" in s or "f5" in s or "esc" in s.split():
        return "Run"
    if "log" in s or "detach" in s or "copy" in s or "plot" in s:
        return "View"
    if "palette" in s or "command" in s or "ctrl+k" in s:
        return "Navigation"
    if "shortcut" in s or "help" in s or "f1" in s:
        return "Help"
    return "General"


def group_entries(entries: Iterable[ShortcutEntry]) -> dict[str, list[ShortcutEntry]]:
    """Return ``{category: [entries]}`` preserving per-group sort."""
    groups: dict[str, list[ShortcutEntry]] = {}
    for e in entries:
        groups.setdefault(e.category, []).append(e)
    for lst in groups.values():
        lst.sort(key=ShortcutEntry.sort_key)
    return dict(sorted(groups.items(), key=lambda kv: kv[0].lower()))


# =============================================================================
# Qt dialog (lazy)
# =============================================================================


_DIALOG_CLS = None


def _build_dialog_class() -> Any:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    class CertusShortcutsOverlay(QDialog):
        def __init__(self, parent, entries: list[ShortcutEntry]) -> None:
            super().__init__(parent)
            self._entries = list(entries)
            self.setWindowTitle("Keyboard shortcuts")
            self.setModal(True)
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            self.setMinimumSize(560, 480)

            self._build_ui()
            self._apply_style()

            if parent is not None:
                geo = parent.geometry()
                self.move(
                    geo.center().x() - self.width() // 2,
                    geo.center().y() - self.height() // 2,
                )

        def _build_ui(self) -> None:
            from certus.utils.certus_ux import OBJ

            root = QVBoxLayout(self)
            root.setContentsMargins(20, 20, 20, 20)
            root.setSpacing(12)

            # Title row
            head = QHBoxLayout()
            title = QLabel("Keyboard shortcuts", self)
            title.setObjectName("h1")
            head.addWidget(title)
            head.addStretch(1)
            hint = QLabel("Press Esc to close", self)
            hint.setObjectName(OBJ.SUBTLE_TEXT)
            head.addWidget(hint)
            root.addLayout(head)

            # Scrollable body
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            body = QWidget(scroll)
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(16)

            groups = group_entries(self._entries)
            if not groups:
                empty = QLabel("No keyboard shortcuts registered.", body)
                empty.setObjectName(OBJ.SUBTLE_TEXT)
                body_layout.addWidget(empty)
            else:
                for category, items in groups.items():
                    body_layout.addWidget(self._build_group(category, items, body))
            body_layout.addStretch(1)

            scroll.setWidget(body)
            root.addWidget(scroll, 1)

        def _build_group(self, category: str, items: list[ShortcutEntry], parent) -> QFrame:
            from certus.utils.certus_ux import OBJ

            frame = QFrame(parent)
            frame.setObjectName(OBJ.CARD)
            grid = QGridLayout(frame)
            grid.setContentsMargins(16, 12, 16, 12)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(8)

            cat_label = QLabel(category.upper(), frame)
            cat_label.setObjectName(OBJ.SUBTLE_TEXT)
            grid.addWidget(cat_label, 0, 0, 1, 2)

            for i, entry in enumerate(items, start=1):
                text = QLabel(entry.label, frame)
                grid.addWidget(text, i, 0)

                chips_row = self._build_chip_row(entry.sequence, frame)
                grid.addWidget(chips_row, i, 1, alignment=Qt.AlignmentFlag.AlignRight)

            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
            return frame

        def _build_chip_row(self, sequence: str, parent) -> QWidget:
            from certus.utils.certus_ux import OBJ

            row = QWidget(parent)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(4)
            for token in _split_sequence(sequence):
                chip = QLabel(token, row)
                chip.setObjectName(OBJ.KBD)
                lay.addWidget(chip)
            return row

        def _apply_style(self) -> None:
            from certus.ui.certus_ui import CertusTheme as T
            from certus.utils.certus_ux import Radius

            self.setStyleSheet(
                f"""
                CertusShortcutsOverlay {{
                    background-color: {T.BACKGROUND};
                    border: 1px solid {T.BORDER};
                    border-radius: {Radius.LG}px;
                }}
                """
            )

        def keyPressEvent(self, e) -> None:  # noqa: N802 - Qt naming
            if e.key() == Qt.Key.Key_Escape:
                self.reject()
                return
            super().keyPressEvent(e)

    return CertusShortcutsOverlay


def _split_sequence(sequence: str) -> list[str]:
    """Turn ``"Ctrl+Shift+P"`` into ``["Ctrl", "Shift", "P"]`` for chips."""
    if not sequence:
        return []
    parts = [p.strip() for p in sequence.split("+")]
    return [p for p in parts if p]


def open_shortcuts_overlay(window) -> Any:
    """Open the shortcut overlay for ``window``. Returns the dialog result."""
    global _DIALOG_CLS
    if _DIALOG_CLS is None:
        _DIALOG_CLS = _build_dialog_class()
    entries = collect_window_shortcuts(window)
    dlg = _DIALOG_CLS(window, entries)
    return dlg.exec()


__all__ = [
    "ShortcutEntry",
    "collect_window_shortcuts",
    "group_entries",
    "open_shortcuts_overlay",
]
