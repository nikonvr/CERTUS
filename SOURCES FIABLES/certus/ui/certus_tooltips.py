"""CERTUS rich tooltips (U10).

Attach a richer tooltip to any ``QWidget``: a small, non-modal popup
with a **title**, **body** text, optional **icon**, and an optional
clickable **link** (e.g. to the online documentation).

Why not ``QToolTip``?
---------------------

Qt's native tooltip is a plain label — it cannot render a title/body
hierarchy, is single-line-ish, and does not support click-through links
without manual work. This module provides a lightweight alternative that
stays in-place until the cursor leaves the watched widget, supports
rich text formatting, and optionally opens a link on click.

Design
------

- **Event-filter based**: call :func:`attach_rich_tooltip(widget, ...)`;
  the module installs a single event filter that shows/hides a shared
  popup widget on ``Enter``/``Leave``.
- **No new thread / timer leak**: a :class:`QTimer` debounces the show
  event (tiny hover delay for non-flicker behavior).
- **Themeable**: colors + border radius read from :class:`CertusTheme`.
- **Pure-data helpers**: :data:`HOVER_DELAY_MS` + :data:`HIDE_DELAY_MS`
  are constants inspectable without Qt.

Public API
----------

- :func:`attach_rich_tooltip(widget, title, body, *, icon_name=None,
    link=None, link_label=None)` - enables a tooltip on ``widget``.
- :func:`detach_rich_tooltip(widget)` - removes a previously attached
  tooltip.
- :class:`TooltipSpec` - frozen data class describing a tooltip's
  content (useful for tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Optional


HOVER_DELAY_MS: Final[int] = 400
HIDE_DELAY_MS: Final[int] = 150
MAX_WIDTH_PX: Final[int] = 320


@dataclass(frozen=True)
class TooltipSpec:
    """Frozen description of a rich tooltip's content."""

    title: str
    body: str
    icon_name: Optional[str] = None
    link: Optional[str] = None
    link_label: Optional[str] = None

    def has_icon(self) -> bool:
        return bool(self.icon_name)

    def has_link(self) -> bool:
        return bool(self.link)


# Registry of (widget id -> (spec, event_filter))
_REGISTRY: dict[int, tuple[TooltipSpec, object]] = {}
_POPUP_CLS = None
_SHARED_POPUP = None


def _build_popup_class() -> Any:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QCursor, QDesktopServices
    from PyQt6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QVBoxLayout,
    )

    class _RichTooltipPopup(QFrame):
        """Floating borderless popup rendered on top of every window."""

        def __init__(self) -> None:
            super().__init__(None)
            self.setObjectName("CertusRichTooltip")
            self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setMaximumWidth(MAX_WIDTH_PX)

            root = QVBoxLayout(self)
            root.setContentsMargins(12, 10, 12, 10)
            root.setSpacing(6)

            header = QHBoxLayout()
            header.setSpacing(8)
            self._icon_lbl = QLabel(self)
            self._icon_lbl.setFixedSize(16, 16)
            header.addWidget(self._icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
            self._title_lbl = QLabel(self)
            self._title_lbl.setObjectName("tip-title")
            self._title_lbl.setWordWrap(True)
            header.addWidget(self._title_lbl, 1)
            root.addLayout(header)

            self._body_lbl = QLabel(self)
            self._body_lbl.setObjectName("tip-body")
            self._body_lbl.setWordWrap(True)
            self._body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            root.addWidget(self._body_lbl)

            self._link_lbl = QLabel(self)
            self._link_lbl.setObjectName("tip-link")
            self._link_lbl.setTextFormat(Qt.TextFormat.RichText)
            self._link_lbl.setOpenExternalLinks(False)
            self._link_lbl.linkActivated.connect(self._on_link)
            self._link_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            root.addWidget(self._link_lbl)

            self._apply_style()

        def _apply_style(self) -> None:
            try:
                from certus.ui.certus_ui import CertusTheme as T

                bg = getattr(T, "SURFACE", "#FFFFFF")
                border = getattr(T, "BORDER", "#D1D5DB")
                text = getattr(T, "TEXT_MAIN", "#111827")
                link = getattr(T, "PRIMARY", "#2563EB")
                muted = getattr(T, "TEXT_MUTED", None) or getattr(T, "MID", "#6B7280")
            except (ImportError, AttributeError, RuntimeError, TypeError):
                bg, border, text, link, muted = (
                    "#FFFFFF",
                    "#D1D5DB",
                    "#111827",
                    "#2563EB",
                    "#6B7280",
                )
            self.setStyleSheet(
                f"#CertusRichTooltip {{ background: {bg}; "
                f"border: 1px solid {border}; border-radius: 8px; }}"
                f"#tip-title {{ color: {text}; font-weight: 700; font-size: 10pt; }}"
                f"#tip-body  {{ color: {muted}; font-size: 9pt; }}"
                f"#tip-link  {{ color: {link}; font-size: 9pt; font-weight: 600; }}"
            )

        def apply_spec(self, spec: TooltipSpec) -> None:
            self._spec = spec
            self._title_lbl.setText(spec.title)
            self._body_lbl.setText(spec.body)
            if spec.has_icon():
                try:
                    from certus.ui.certus_icons import certus_icon
                    from certus.ui.certus_ui import CertusTheme as T

                    color = getattr(T, "PRIMARY", "#2563EB")
                    pix = certus_icon(spec.icon_name, color=color, size=16).pixmap(16, 16)
                    self._icon_lbl.setPixmap(pix)
                    self._icon_lbl.setVisible(True)
                except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                    self._icon_lbl.setVisible(False)
            else:
                self._icon_lbl.setVisible(False)

            if spec.has_link():
                label = spec.link_label or "Learn more →"
                self._link_lbl.setText(f"<a href='{spec.link}'>{label}</a>")
                self._link_lbl.setVisible(True)
            else:
                self._link_lbl.setVisible(False)

            self.adjustSize()

        def _on_link(self, url: str) -> None:
            try:
                from PyQt6.QtCore import QUrl

                QDesktopServices.openUrl(QUrl(url))
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                pass

    return _RichTooltipPopup


def _get_popup() -> Any:
    global _POPUP_CLS, _SHARED_POPUP
    if _POPUP_CLS is None:
        _POPUP_CLS = _build_popup_class()
    if _SHARED_POPUP is None:
        _SHARED_POPUP = _POPUP_CLS()
    return _SHARED_POPUP


def _build_event_filter(widget, spec: TooltipSpec) -> Any:
    from PyQt6.QtCore import QEvent, QObject, QTimer

    class _Filter(QObject):
        def __init__(self) -> None:
            super().__init__(widget)
            self._widget = widget
            self._spec = spec
            self._show_timer = QTimer(self)
            self._show_timer.setSingleShot(True)
            self._show_timer.setInterval(HOVER_DELAY_MS)
            self._show_timer.timeout.connect(self._show)
            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.setInterval(HIDE_DELAY_MS)
            self._hide_timer.timeout.connect(self._hide)

        def eventFilter(self, obj, event) -> bool:
            if obj is not self._widget:
                return False
            et = event.type()
            if et == QEvent.Type.Enter:
                self._hide_timer.stop()
                self._show_timer.start()
            elif et == QEvent.Type.Leave:
                self._show_timer.stop()
                self._hide_timer.start()
            elif et == QEvent.Type.Hide:
                self._hide()
            return False

        def _show(self) -> None:
            popup = _get_popup()
            popup.apply_spec(self._spec)
            # Position below the widget's bottom-left corner.
            gp = self._widget.mapToGlobal(self._widget.rect().bottomLeft())
            popup.move(gp.x(), gp.y() + 6)
            popup.show()
            popup.raise_()

        def _hide(self) -> None:
            popup = _get_popup()
            popup.hide()

    return _Filter()


# =============================================================================
# Public API
# =============================================================================


def attach_rich_tooltip(
    widget,
    title: str,
    body: str,
    *,
    icon_name: str | None = None,
    link: str | None = None,
    link_label: str | None = None,
) -> TooltipSpec:
    """Attach a rich tooltip to ``widget``.

    Returns the :class:`TooltipSpec` that was stored. Subsequent calls on
    the same widget replace the previous spec.
    """
    if widget is None:
        return TooltipSpec(title=title, body=body, icon_name=icon_name, link=link, link_label=link_label)

    spec = TooltipSpec(
        title=title,
        body=body,
        icon_name=icon_name,
        link=link,
        link_label=link_label,
    )

    # Remove any previous attachment
    detach_rich_tooltip(widget)

    try:
        flt = _build_event_filter(widget, spec)
        widget.installEventFilter(flt)
    except (RuntimeError, AttributeError, TypeError):
        return spec

    _REGISTRY[id(widget)] = (spec, flt)

    def _drop_tooltip_spec(*_args, key=id(widget)) -> None:
        _REGISTRY.pop(key, None)

    try:
        widget.destroyed.connect(_drop_tooltip_spec)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return spec


def detach_rich_tooltip(widget) -> bool:
    """Remove a previously attached tooltip. Returns True if one was active."""
    if widget is None:
        return False
    entry = _REGISTRY.pop(id(widget), None)
    if entry is None:
        return False
    _spec, flt = entry
    try:
        widget.removeEventFilter(flt)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return True


def get_tooltip_spec(widget) -> TooltipSpec | None:
    """Return the :class:`TooltipSpec` attached to ``widget``, or None."""
    if widget is None:
        return None
    entry = _REGISTRY.get(id(widget))
    if entry is None:
        return None
    return entry[0]


__all__ = [
    "HOVER_DELAY_MS",
    "HIDE_DELAY_MS",
    "MAX_WIDTH_PX",
    "TooltipSpec",
    "attach_rich_tooltip",
    "detach_rich_tooltip",
    "get_tooltip_spec",
]
