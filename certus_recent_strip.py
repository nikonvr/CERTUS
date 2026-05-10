"""CERTUS recent-files strip widget (U5+).

A compact horizontal strip rendering the N most-recent files for a given
category (default: ``RecentCategories.CONFIG``) as pill buttons. Clicking
a pill fires a callback with the chosen path - designed to be embedded
on the HUB landing page, in a status bar, or in any sidebar.

Decoupled from :class:`CertusHub` on purpose so it can be reused by
individual apps (INDEX, DESIGN, METAL, STRAT, RE) without importing the
HUB monolith.

Public API
----------

- :class:`CertusRecentFilesStrip`: the widget itself.
- :func:`build_recent_files_strip(parent, ...)`: convenience factory.
"""

from __future__ import annotations

from typing import Callable, Final


STRIP_MAX_ITEMS: Final[int] = 5
PILL_MAX_CHARS: Final[int] = 22


_STRIP_CLS = None


def _build_strip_class():
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QWidget,
    )

    class CertusRecentFilesStrip(QWidget):
        """Horizontal strip of recent-file pills.

        Parameters
        ----------
        parent:
            Parent widget.
        category:
            Recent-files category (see :class:`certus_recent.RecentCategories`).
        limit:
            Max number of pills to render (capped at :data:`STRIP_MAX_ITEMS`).
        title:
            Optional left-side caption. Pass ``None`` to hide.
        on_open:
            Callback ``fn(path: str) -> None`` invoked when a pill is
            clicked. Defaults to a no-op.
        """

        path_selected = pyqtSignal(str)

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            category: str | None = None,
            limit: int = STRIP_MAX_ITEMS,
            title: str | None = "Recent:",
            on_open: Callable[[str], None] | None = None,
        ):
            super().__init__(parent)
            self._category = category
            self._limit = max(1, min(int(limit), STRIP_MAX_ITEMS))
            self._on_open = on_open
            self._pills: list[QPushButton] = []

            self.setObjectName("CertusRecentStrip")
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

            root = QHBoxLayout(self)
            root.setContentsMargins(8, 4, 8, 4)
            root.setSpacing(8)
            self._root = root

            if title:
                cap = QLabel(title, self)
                cap.setObjectName("recent-strip-title")
                cap.setStyleSheet("#recent-strip-title { color: palette(mid); font-weight: 600; font-size: 9pt; }")
                root.addWidget(cap, 0, Qt.AlignmentFlag.AlignVCenter)

            self._pill_container = QHBoxLayout()
            self._pill_container.setSpacing(6)
            root.addLayout(self._pill_container, 1)
            root.addStretch(1)

            self.refresh()

        # -- Public ----------------------------------------------------------
        def refresh(self) -> None:
            """Re-query the recent-files registry and rebuild the pills."""
            # Tear down old pills
            while self._pill_container.count():
                item = self._pill_container.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            self._pills.clear()

            paths = self._fetch_paths()
            if not paths:
                empty = QLabel("(none yet)", self)
                empty.setStyleSheet("color: palette(mid); font-style: italic;")
                self._pill_container.addWidget(empty)
                return

            for p in paths:
                pill = self._build_pill(p)
                self._pills.append(pill)
                self._pill_container.addWidget(pill)

        def set_category(self, category: str) -> None:
            self._category = category
            self.refresh()

        def category(self) -> str | None:
            return self._category

        # -- Internals -------------------------------------------------------
        def _fetch_paths(self) -> list[str]:
            try:
                from certus_recent import RecentCategories, list_recent

                cat = self._category or RecentCategories.CONFIG
                return list_recent(cat, limit=self._limit)
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                return []

        def _build_pill(self, path: str) -> QPushButton:
            from certus_recent import short_label

            label = short_label(path, max_length=PILL_MAX_CHARS)
            btn = QPushButton(label, self)
            btn.setObjectName("recent-pill")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setToolTip(path)
            btn.setStyleSheet(
                "QPushButton#recent-pill { "
                " background: palette(base); color: palette(text); "
                " border: 1px solid palette(mid); border-radius: 10px; "
                " padding: 3px 10px; font-size: 9pt; }"
                "QPushButton#recent-pill:hover { "
                " background: palette(highlight); color: palette(highlighted-text); }"
            )

            def _emit_path(*_args, current_path=path):
                self._emit(current_path)

            btn.clicked.connect(_emit_path)
            return btn

        def _emit(self, path: str) -> None:
            if self._on_open is not None:
                try:
                    self._on_open(path)
                except (RuntimeError, AttributeError, TypeError, ValueError):
                    pass
            self.path_selected.emit(path)

    return CertusRecentFilesStrip


def _get_strip_cls():
    global _STRIP_CLS
    if _STRIP_CLS is None:
        _STRIP_CLS = _build_strip_class()
    return _STRIP_CLS


def build_recent_files_strip(
    parent=None,
    *,
    category: str | None = None,
    limit: int = STRIP_MAX_ITEMS,
    title: str | None = "Recent:",
    on_open: Callable[[str], None] | None = None,
):
    """Factory returning a :class:`CertusRecentFilesStrip` widget.

    Returns ``None`` when Qt is not available. Use as a drop-in on a
    status bar, sidebar or landing page.
    """
    try:
        Strip = _get_strip_cls()
    except (ImportError, AttributeError, RuntimeError, TypeError):
        return None
    return Strip(
        parent,
        category=category,
        limit=limit,
        title=title,
        on_open=on_open,
    )


__all__ = [
    "STRIP_MAX_ITEMS",
    "PILL_MAX_CHARS",
    "build_recent_files_strip",
]
