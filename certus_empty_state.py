"""CERTUS empty-state widget (U8).

A reusable placeholder to show inside panels that have no data yet
(empty spectra list, untouched targets table, unloaded results area,
...). Conveys three things: *what* is empty, *why*, and *how to fix it*
via an optional call-to-action button.

Design
------

- **Composition**: Lucide icon (large, muted), bold title, multi-line
  description, optional primary action button.
- **Centered**: uses spacers so the content is vertically centered in
  whatever container it lives in.
- **Themeable**: reads palette colors from :class:`CertusTheme` + Lucide
  icons from :mod:`certus_icons`.
- **Lightweight**: pure QWidget, no timers, no workers.

Public API
----------

- :class:`CertusEmptyState`: the widget class.
- :func:`build_empty_state(parent, ...)`: factory returning a ready-to-
  place widget.
- :func:`attach_empty_state_to(table_view, ...)`: helper that overlays an
  empty-state on top of an empty :class:`QTableView` / :class:`QListView`
  and hides it when the model becomes non-empty.
"""

from __future__ import annotations

from typing import Callable, Final


DEFAULT_ICON_SIZE_PX: Final[int] = 48
DEFAULT_TITLE: Final[str] = "No data yet"
DEFAULT_DESCRIPTION: Final[str] = "Load a file or create an entry to get started."


_WIDGET_CLS = None
_OVERLAYS: dict[int, object] = {}


def _build_widget_class():
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    class CertusEmptyState(QWidget):
        """Placeholder shown when a panel has nothing to display.

        Emits :attr:`action_triggered` when the optional CTA button is
        clicked.
        """

        action_triggered = pyqtSignal()

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            icon_name: str = "inbox",
            title: str = DEFAULT_TITLE,
            description: str = DEFAULT_DESCRIPTION,
            action_label: str | None = None,
            on_action: Callable[[], None] | None = None,
            icon_size_px: int = DEFAULT_ICON_SIZE_PX,
        ):
            super().__init__(parent)
            self.setObjectName("CertusEmptyState")
            self._on_action = on_action
            self._action_btn = None
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(24, 24, 24, 24)
            outer.setSpacing(12)
            outer.addStretch(1)

            # Icon
            icon_row = QHBoxLayout()
            icon_row.addStretch(1)
            icon_label = QLabel(self)
            icon_label.setObjectName("empty-icon")
            icon_label.setFixedSize(int(icon_size_px), int(icon_size_px))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            try:
                from certus_icons import certus_icon
                from certus_ui import CertusTheme

                muted = getattr(CertusTheme, "TEXT_MUTED", None) or getattr(CertusTheme, "MID", "#9CA3AF")
                ico = certus_icon(icon_name, color=muted, size=int(icon_size_px))
                pix = ico.pixmap(int(icon_size_px), int(icon_size_px))
                if pix is None or pix.isNull():
                    icon_label.setText("∅")
                else:
                    icon_label.setPixmap(pix)
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                icon_label.setText("∅")
            icon_row.addWidget(icon_label)
            icon_row.addStretch(1)
            outer.addLayout(icon_row)

            # Title
            title_lbl = QLabel(title, self)
            title_lbl.setObjectName("empty-title")
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_lbl.setStyleSheet(
                "#empty-title { color: palette(text); font-size: 12pt; font-weight: 600; }"
            )
            outer.addWidget(title_lbl)

            # Description
            desc_lbl = QLabel(description, self)
            desc_lbl.setObjectName("empty-desc")
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                "#empty-desc { color: palette(mid); font-size: 9pt; }"
            )
            outer.addWidget(desc_lbl)

            # Action button
            if action_label:
                btn_row = QHBoxLayout()
                btn_row.addStretch(1)
                btn = QPushButton(action_label, self)
                btn.setObjectName("empty-cta")
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.setMinimumWidth(160)
                btn.clicked.connect(self._emit_action)
                btn_row.addWidget(btn)
                btn_row.addStretch(1)
                outer.addLayout(btn_row)
                self._action_btn = btn

            outer.addStretch(1)

            # Keep labels for later refresh
            self._title_lbl = title_lbl
            self._desc_lbl = desc_lbl
            self._icon_label = icon_label
            self._icon_name = icon_name
            self._icon_size_px = int(icon_size_px)

        # -- API -------------------------------------------------------------
        def set_title(self, title: str) -> None:
            self._title_lbl.setText(title)

        def set_description(self, description: str) -> None:
            self._desc_lbl.setText(description)

        def set_action_label(self, label: str | None) -> None:
            if self._action_btn is None:
                return
            if label:
                self._action_btn.setText(label)
                self._action_btn.setVisible(True)
            else:
                self._action_btn.setVisible(False)

        def has_action(self) -> bool:
            return self._action_btn is not None

        # -- Internals ------------------------------------------------------
        def _emit_action(self) -> None:
            if self._on_action is not None:
                try:
                    self._on_action()
                except (RuntimeError, AttributeError, TypeError, ValueError):
                    pass
            self.action_triggered.emit()

    return CertusEmptyState


def _get_widget_cls():
    global _WIDGET_CLS
    if _WIDGET_CLS is None:
        _WIDGET_CLS = _build_widget_class()
    return _WIDGET_CLS


# =============================================================================
# Public API
# =============================================================================


def build_empty_state(
    parent=None,
    *,
    icon_name: str = "inbox",
    title: str = DEFAULT_TITLE,
    description: str = DEFAULT_DESCRIPTION,
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
    icon_size_px: int = DEFAULT_ICON_SIZE_PX,
):
    """Return a new :class:`CertusEmptyState` widget.

    Returns ``None`` if Qt is unavailable (never for PyQt6 environments).
    """
    Widget = _get_widget_cls()
    return Widget(
        parent,
        icon_name=icon_name,
        title=title,
        description=description,
        action_label=action_label,
        on_action=on_action,
        icon_size_px=icon_size_px,
    )


def attach_empty_state_to(
    view,
    *,
    icon_name: str = "inbox",
    title: str = DEFAULT_TITLE,
    description: str = DEFAULT_DESCRIPTION,
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
):
    """Overlay an empty-state widget on a :class:`QAbstractItemView`.

    Automatically toggled visible/hidden by watching the model's row
    count. Returns the overlay widget (or ``None`` on failure).
    """
    if view is None:
        return None
    try:
        from PyQt6.QtCore import QEvent, QObject
    except ImportError:
        return None

    overlay = build_empty_state(
        view,
        icon_name=icon_name,
        title=title,
        description=description,
        action_label=action_label,
        on_action=on_action,
    )
    if overlay is None:
        return None
    overlay.setGeometry(0, 0, view.width(), view.height())

    class _Watcher(QObject):
        def __init__(self, v, ov):
            super().__init__(v)
            self._view = v
            self._overlay = ov
            v.installEventFilter(self)
            self._sync()

        def eventFilter(self, obj, event):
            if obj is self._view and event.type() == QEvent.Type.Resize:
                self._overlay.setGeometry(0, 0, self._view.width(), self._view.height())
                self._sync()
            return False

        def _sync(self):
            model = self._view.model() if self._view is not None else None
            empty = True
            try:
                empty = (model is None) or model.rowCount() == 0
            except (AttributeError, RuntimeError, TypeError):
                empty = True
            self._overlay.setVisible(bool(empty))
            if empty:
                self._overlay.raise_()

    watcher = _Watcher(view, overlay)
    _OVERLAYS[id(view)] = (overlay, watcher)
    def _drop_overlay(*_args, key=id(view)):
        _OVERLAYS.pop(key, None)

    try:
        view.destroyed.connect(_drop_overlay)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return overlay


def detach_empty_state_from(view) -> bool:
    """Remove a previously installed overlay. Returns True on success."""
    if view is None:
        return False
    entry = _OVERLAYS.pop(id(view), None)
    if entry is None:
        return False
    overlay, _watcher = entry
    try:
        overlay.setParent(None)
        overlay.deleteLater()
    except (AttributeError, RuntimeError, TypeError):
        pass
    return True


__all__ = [
    "DEFAULT_ICON_SIZE_PX",
    "DEFAULT_TITLE",
    "DEFAULT_DESCRIPTION",
    "build_empty_state",
    "attach_empty_state_to",
    "detach_empty_state_from",
]
