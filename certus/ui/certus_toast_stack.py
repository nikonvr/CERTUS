"""CERTUS stacked toast notifications (U6).

A modern, non-blocking notification system that replaces the single
:class:`certus_ui.CertusToast` with a **stack** of toasts pinned to the
bottom-right of a window. Multiple simultaneous notifications stack
vertically with newest on top, each auto-dismisses after its own
duration, and closing one slides the rest down.

Features
--------

- **Variants**: ``info`` / ``success`` / ``warning`` / ``error``, each
  with a themed accent color and a Lucide icon from :mod:`certus_icons`.
- **Stack**: up to :data:`MAX_STACK_SIZE` toasts per parent window
  (default 4). Older toasts are evicted when the stack overflows.
- **Anchored**: positioned in the bottom-right with a fixed margin; re-
  lays out on parent resize via an event filter.
- **Theme-aware**: colors are read live from :class:`CertusTheme` so the
  same widget renders correctly in light + dark mode.
- **Click-to-dismiss**: clicking a toast closes it early.
- **No blocking**: built on ``QLabel`` + ``QTimer.singleShot``.

Public API
----------

- :func:`show_toast_stack(parent, text, variant="info", duration_ms=3000,
    icon_name=None, title=None)`: push a new toast.
- :class:`CertusToastStack`: the per-parent stack manager (rarely used
  directly; retrieved via :func:`get_toast_stack(parent)`).
"""

from __future__ import annotations

from typing import Final


MAX_STACK_SIZE: Final[int] = 4
DEFAULT_DURATION_MS: Final[int] = 3000
MARGIN_PX: Final[int] = 18
GAP_PX: Final[int] = 8
TOAST_WIDTH: Final[int] = 340

_VARIANT_ICON: Final[dict[str, str]] = {
    "info": "info",
    "success": "check-circle",
    "warning": "alert-triangle",
    "error": "alert-triangle",
}


def _variant_colors(variant: str) -> tuple[str, str, str]:
    """Return ``(bg, fg, accent)`` hex strings for ``variant``."""
    from certus.ui.certus_ui import CertusTheme as T

    base = {
        "info": (
            T.INFO_BG if hasattr(T, "INFO_BG") else T.SURFACE,
            T.INFO_TEXT if hasattr(T, "INFO_TEXT") else T.TEXT_MAIN,
            T.INFO,
        ),
        "success": (getattr(T, "SUCCESS_BG", T.SURFACE), getattr(T, "SUCCESS_TEXT", T.TEXT_MAIN), T.SUCCESS),
        "warning": (getattr(T, "WARNING_BG", T.SURFACE), getattr(T, "WARNING_TEXT", T.TEXT_MAIN), T.WARNING),
        "error": (getattr(T, "DANGER_BG", T.SURFACE), getattr(T, "DANGER_TEXT", T.TEXT_MAIN), T.DANGER),
    }
    return base.get(variant, base["info"])


# =============================================================================
# Widget (lazy Qt)
# =============================================================================


_TOAST_CLS = None
_STACK_CLS = None
_STACKS: dict[int, object] = {}  # parent id -> CertusToastStack


def _build_toast_class():
    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        Qt,
        QTimer,
        pyqtSignal,
    )
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import (
        QFrame,
        QGraphicsDropShadowEffect,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    class CertusToast(QFrame):
        """One stacked toast row. Emits :attr:`dismissed` on close."""

        dismissed = pyqtSignal(object)

        def __init__(
            self,
            parent: QWidget,
            text: str,
            variant: str = "info",
            duration_ms: int = DEFAULT_DURATION_MS,
            *,
            icon_name: str | None = None,
            title: str | None = None,
        ):
            super().__init__(parent)
            self._parent_widget = parent
            self._variant = variant
            self._duration_ms = int(duration_ms)

            bg, fg, accent = _variant_colors(variant)
            from certus.utils.certus_ux import Radius

            self.setObjectName("CertusToastStack")
            self.setStyleSheet(
                f"""
                CertusToast, QFrame#CertusToastStack {{
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {accent};
                    border-left: 4px solid {accent};
                    border-radius: {Radius.MD}px;
                }}
                QLabel#toast-title {{
                    color: {fg};
                    font-weight: 600;
                    font-size: 10pt;
                }}
                QLabel#toast-body {{
                    color: {fg};
                    font-size: 9pt;
                }}
                QPushButton#toast-close {{
                    background: transparent;
                    color: {fg};
                    border: none;
                    padding: 0px 4px;
                    font-size: 12pt;
                }}
                QPushButton#toast-close:hover {{
                    color: {accent};
                }}
                """
            )
            self.setFixedWidth(TOAST_WIDTH)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

            # Drop shadow for depth
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(28)
            shadow.setOffset(0, 6)
            shadow.setColor(QColor(0, 0, 0, 60))
            self.setGraphicsEffect(shadow)

            # Layout
            root = QHBoxLayout(self)
            root.setContentsMargins(12, 10, 10, 10)
            root.setSpacing(10)

            # Icon
            icon_label = QLabel(self)
            icon_label.setFixedSize(20, 20)
            resolved_icon = icon_name or _VARIANT_ICON.get(variant, "info")
            try:
                from certus.ui.certus_icons import certus_icon

                pix = certus_icon(resolved_icon, color=accent, size=20).pixmap(20, 20)
                icon_label.setPixmap(pix)
            except (ImportError, AttributeError, RuntimeError, TypeError):
                icon_label.setText("*")
            root.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

            # Title + body
            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(2)
            if title:
                title_lbl = QLabel(title, self)
                title_lbl.setObjectName("toast-title")
                title_lbl.setWordWrap(True)
                text_col.addWidget(title_lbl)
            body_lbl = QLabel(text, self)
            body_lbl.setObjectName("toast-body")
            body_lbl.setWordWrap(True)
            text_col.addWidget(body_lbl)
            root.addLayout(text_col, 1)

            # Close button
            close_btn = QPushButton("✕", self)
            close_btn.setObjectName("toast-close")
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setFixedSize(22, 22)
            close_btn.clicked.connect(self._dismiss)
            root.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

            # Auto-dismiss
            if self._duration_ms > 0:
                QTimer.singleShot(self._duration_ms, self._dismiss)

            # Entrance animation: fade-in + slide-left
            self.setWindowOpacity(0.0)
            self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
            self._fade_in.setDuration(180)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        def showEvent(self, e):  # noqa: N802 - Qt
            super().showEvent(e)
            try:
                self._fade_in.start()
            except (RuntimeError, AttributeError, TypeError):
                pass

        def mousePressEvent(self, e):  # noqa: N802 - Qt
            if e.button() == Qt.MouseButton.LeftButton:
                self._dismiss()
            super().mousePressEvent(e)

        def _dismiss(self):
            # Fade-out then close
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(140)
            anim.setStartValue(self.windowOpacity())
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.InCubic)
            anim.finished.connect(self._finalize_dismiss)
            self._fade_out = anim  # keep reference
            anim.start()

        def _finalize_dismiss(self):
            self.dismissed.emit(self)
            self.close()
            self.deleteLater()

    return CertusToast


def _build_stack_class():
    from PyQt6.QtCore import QEvent, QObject

    Toast = _get_toast_cls()

    class CertusToastStack(QObject):
        """Manages the vertical stack of toasts for one parent window."""

        def __init__(self, parent):
            super().__init__(parent)
            self._parent = parent
            self._toasts: list = []
            parent.installEventFilter(self)

        def eventFilter(self, obj, event):
            if obj is self._parent and event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Move,
                QEvent.Type.Show,
            ):
                self._relayout()
            return False

        def push(
            self,
            text: str,
            variant: str = "info",
            duration_ms: int = DEFAULT_DURATION_MS,
            *,
            icon_name: str | None = None,
            title: str | None = None,
        ):
            # Evict oldest if overflow
            while len(self._toasts) >= MAX_STACK_SIZE:
                old = self._toasts[0]
                self._toasts.remove(old)
                try:
                    old._dismiss()
                except (RuntimeError, AttributeError, TypeError):
                    old.close()

            toast = Toast(
                self._parent,
                text,
                variant=variant,
                duration_ms=duration_ms,
                icon_name=icon_name,
                title=title,
            )
            toast.dismissed.connect(self._on_dismissed)
            self._toasts.append(toast)
            toast.adjustSize()
            toast.show()
            toast.raise_()
            self._relayout()
            return toast

        def _on_dismissed(self, toast):
            if toast in self._toasts:
                self._toasts.remove(toast)
            self._relayout()

        def _relayout(self):
            if not self._parent.isVisible():
                return
            pw = self._parent.width()
            ph = self._parent.height()
            # Stack newest at the bottom, older above.
            y = ph - MARGIN_PX
            for toast in reversed(self._toasts):
                try:
                    toast.adjustSize()
                    h = toast.height()
                    x = pw - toast.width() - MARGIN_PX
                    y -= h
                    
                    from PyQt6.QtCore import QPoint
                    target_pos = QPoint(max(MARGIN_PX, x), max(MARGIN_PX, y))
                    
                    if getattr(toast, "_init_positioned", False):
                        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
                        if hasattr(toast, "_pos_anim") and toast._pos_anim is not None:
                            toast._pos_anim.stop()
                        
                        anim = QPropertyAnimation(toast, b"pos", toast)
                        anim.setDuration(220)
                        anim.setStartValue(toast.pos())
                        anim.setEndValue(target_pos)
                        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                        toast._pos_anim = anim
                        anim.start()
                    else:
                        toast.move(target_pos)
                        toast._init_positioned = True
                        toast._pos_anim = None
                        
                    y -= GAP_PX
                except (RuntimeError, AttributeError, TypeError):
                    continue

        def clear(self):
            for t in list(self._toasts):
                try:
                    t._dismiss()
                except (RuntimeError, AttributeError, TypeError):
                    t.close()
            self._toasts.clear()

    return CertusToastStack


def _get_toast_cls():
    global _TOAST_CLS
    if _TOAST_CLS is None:
        _TOAST_CLS = _build_toast_class()
    return _TOAST_CLS


def _get_stack_cls():
    global _STACK_CLS
    if _STACK_CLS is None:
        _STACK_CLS = _build_stack_class()
    return _STACK_CLS


# =============================================================================
# Public API
# =============================================================================


def get_toast_stack(parent):
    """Return (creating if needed) the :class:`CertusToastStack` for ``parent``."""
    if parent is None:
        return None
    key = id(parent)
    stack = _STACKS.get(key)
    if stack is None:
        StackCls = _get_stack_cls()
        stack = StackCls(parent)
        _STACKS[key] = stack

        # Cleanup entry on destroy
        def _drop_stack(*_args, stack_key=key):
            _STACKS.pop(stack_key, None)

        try:
            parent.destroyed.connect(_drop_stack)
        except (AttributeError, RuntimeError, TypeError):
            pass
    return stack


def show_toast_stack(
    parent,
    text: str,
    variant: str = "info",
    duration_ms: int = DEFAULT_DURATION_MS,
    *,
    icon_name: str | None = None,
    title: str | None = None,
):
    """Push a new stacked toast on ``parent``.

    Returns the :class:`CertusToast` instance (or ``None`` if ``parent``
    is not a visible widget).
    """
    if parent is None:
        return None
    stack = get_toast_stack(parent)
    if stack is None:
        return None
    return stack.push(
        text,
        variant=variant,
        duration_ms=duration_ms,
        icon_name=icon_name,
        title=title,
    )


def variant_icon_name(variant: str) -> str:
    """Return the default Lucide icon name associated to ``variant``."""
    return _VARIANT_ICON.get(variant, "info")


def supported_variants() -> list[str]:
    return list(_VARIANT_ICON.keys())


__all__ = [
    "MAX_STACK_SIZE",
    "DEFAULT_DURATION_MS",
    "get_toast_stack",
    "show_toast_stack",
    "variant_icon_name",
    "supported_variants",
]
