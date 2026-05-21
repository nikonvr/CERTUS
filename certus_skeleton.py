"""CERTUS loading-skeleton widgets (U7).

A minimal, theme-aware "skeleton screen" toolkit used to signal
long-running operations (INDEX_SPLINE optimisation, METAL beam analysis,
DESIGN full-stack refit, ...) without freezing the UI with a modal busy
dialog.

Philosophy
----------

- **Non-blocking**: skeletons are plain ``QFrame``/``QLabel`` widgets
  animated on the UI thread; they consume < 1 ms of event-loop time per
  frame and are safe to overlay on top of existing widgets.
- **Themeable**: all colors are read from :class:`CertusTheme`, so the
  same widget looks native in light + dark mode.
- **Granular**: three primitives are exposed:

    * :class:`CertusSkeletonBlock` - an individual shimmering pill.
    * :class:`CertusSkeletonGroup` - a :class:`QFrame` containing a
      labelled grid of blocks (e.g. "Loading plot (title + chart +
      legend)").
    * :class:`CertusSkeletonOverlay` - a translucent panel that blankets
      another widget and displays a group of blocks in its centre.

- **Composable**: :func:`skeleton_for(widget)` builds an overlay tailored
  to the target widget's size and :func:`install_skeleton(widget)` /
  :func:`uninstall_skeleton(widget)` provide a clean lifecycle.
- **Pure-python fallback**: the module imports PyQt6 lazily so tests that
  exercise the data-layer run on any Python install.

Public API
----------

- :func:`skeleton_for(widget, *, lines=3, label="Loading...")` - convenience
- :func:`install_skeleton(widget, ...)` / :func:`uninstall_skeleton(widget)`
- :class:`CertusSkeletonBlock`, :class:`CertusSkeletonGroup`,
  :class:`CertusSkeletonOverlay`
"""

from __future__ import annotations

from typing import Final


SHIMMER_PERIOD_MS: Final[int] = 1200
DEFAULT_LINES: Final[int] = 3
DEFAULT_LINE_HEIGHT: Final[int] = 14
DEFAULT_GAP_PX: Final[int] = 10
DEFAULT_RADIUS_PX: Final[int] = 6


# =============================================================================
# Lazy Qt
# =============================================================================


_BLOCK_CLS = None
_GROUP_CLS = None
_OVERLAY_CLS = None
_OVERLAYS: dict[int, object] = {}  # target widget id -> overlay


def _theme_colors() -> tuple[str, str, str]:
    """Return ``(base, highlight, border)`` hex strings from CertusTheme."""
    from certus_ui import CertusTheme as T

    base = getattr(T, "SKELETON_BASE", None) or getattr(T, "BORDER_LIGHT", None) or getattr(T, "BORDER", "#E5E7EB")
    highlight = getattr(T, "SKELETON_HIGHLIGHT", None) or getattr(T, "SURFACE", "#F3F4F6")
    border = getattr(T, "BORDER", "#D1D5DB")
    return str(base), str(highlight), str(border)


# =============================================================================
# Classes
# =============================================================================


def _build_block_class():
    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        Qt,
        pyqtProperty,
    )
    from PyQt6.QtGui import QColor, QLinearGradient, QPainter
    from PyQt6.QtWidgets import QFrame

    class CertusSkeletonBlock(QFrame):
        """A single shimmering rectangular block.

        The animation is a horizontal gradient sweeping left-to-right,
        driven by a :class:`QPropertyAnimation` on a Qt property.
        """

        def __init__(
            self, parent=None, *, width: int = 120, height: int = DEFAULT_LINE_HEIGHT, radius: int = DEFAULT_RADIUS_PX
        ):
            super().__init__(parent)
            self.setFixedSize(int(width), int(height))
            self._radius = int(radius)
            self._offset = 0.0
            self._anim = QPropertyAnimation(self, b"offset", self)
            self._anim.setDuration(SHIMMER_PERIOD_MS)
            self._anim.setStartValue(-0.4)
            self._anim.setEndValue(1.4)
            self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._anim.setLoopCount(-1)  # infinite

        def start(self):
            if self._anim.state() != QPropertyAnimation.State.Running:
                self._anim.start()

        def stop(self):
            if self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()

        def _get_offset(self) -> float:
            return self._offset

        def _set_offset(self, value: float):
            self._offset = float(value)
            self.update()

        offset = pyqtProperty(float, fget=_get_offset, fset=_set_offset)

        def paintEvent(self, _event):  # noqa: N802 - Qt
            p = QPainter()
            if not p.begin(self):
                return
            try:
                base, highlight, _ = _theme_colors()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                rect = self.rect()
                # Background
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(base))
                p.drawRoundedRect(rect, self._radius, self._radius)
                # Gradient shimmer
                grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
                pos = max(0.0, min(1.0, self._offset))
                base_col = QColor(base)
                hl = QColor(highlight)
                grad.setColorAt(max(0.0, pos - 0.15), base_col)
                grad.setColorAt(pos, hl)
                grad.setColorAt(min(1.0, pos + 0.15), base_col)
                p.setBrush(grad)
                p.drawRoundedRect(rect, self._radius, self._radius)
            finally:
                p.end()

        def showEvent(self, e):  # noqa: N802 - Qt
            super().showEvent(e)
            self.start()

        def hideEvent(self, e):  # noqa: N802 - Qt
            self.stop()
            super().hideEvent(e)

    return CertusSkeletonBlock


def _build_group_class():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

    Block = _get_block_cls()

    class CertusSkeletonGroup(QFrame):
        """A labelled stack of :class:`CertusSkeletonBlock` widgets.

        Parameters
        ----------
        lines:
            Number of horizontal blocks to stack.
        label:
            Optional caption shown above the blocks.
        widths:
            Optional per-line width override (defaults to a decreasing
            pattern for a typewriter feel).
        """

        def __init__(
            self,
            parent=None,
            *,
            lines: int = DEFAULT_LINES,
            label: str | None = "Loading...",
            widths: list[int] | None = None,
            line_height: int = DEFAULT_LINE_HEIGHT,
        ):
            super().__init__(parent)
            self.setObjectName("CertusSkeletonGroup")
            self._blocks: list = []
            v = QVBoxLayout(self)
            v.setContentsMargins(12, 12, 12, 12)
            v.setSpacing(DEFAULT_GAP_PX)

            if label:
                caption = QLabel(label, self)
                caption.setObjectName("skeleton-label")
                caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
                caption.setStyleSheet(
                    "#skeleton-label { color: palette(text); font-size: 9pt; font-weight: 600; opacity: 0.8; }"
                )
                v.addWidget(caption, 0, Qt.AlignmentFlag.AlignHCenter)

            default_widths = [220, 180, 140, 200, 160, 120]
            for i in range(max(1, int(lines))):
                w = widths[i] if widths and i < len(widths) else default_widths[i % len(default_widths)]
                blk = Block(self, width=w, height=line_height)
                self._blocks.append(blk)
                v.addWidget(blk, 0, Qt.AlignmentFlag.AlignHCenter)

            self.setStyleSheet(self._default_stylesheet())

        def _default_stylesheet(self) -> str:
            _, _, border = _theme_colors()
            return (
                f"#CertusSkeletonGroup {{ background: transparent; border: 1px dashed {border}; border-radius: 10px; }}"
            )

        def start(self):
            for b in self._blocks:
                b.start()

        def stop(self):
            for b in self._blocks:
                b.stop()

    return CertusSkeletonGroup


def _build_overlay_class():
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

    Group = _get_group_cls()

    class CertusSkeletonOverlay(QWidget):
        """Translucent panel that covers a target widget while loading.

        Install with :func:`install_skeleton(widget)` and remove with
        :func:`uninstall_skeleton(widget)`. Automatically re-lays-out on
        the target's resize events.
        """

        def __init__(
            self,
            target: QWidget,
            *,
            lines: int = DEFAULT_LINES,
            label: str = "Loading...",
            line_height: int = DEFAULT_LINE_HEIGHT,
        ):
            super().__init__(target)
            self._target = target
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setObjectName("CertusSkeletonOverlay")
            self.setStyleSheet("#CertusSkeletonOverlay { background: rgba(255,255,255,170); }")
            v = QVBoxLayout(self)
            v.setContentsMargins(0, 0, 0, 0)
            h = QHBoxLayout()
            h.addStretch(1)
            self._group = Group(self, lines=lines, label=label, line_height=line_height)
            h.addWidget(self._group)
            h.addStretch(1)
            v.addStretch(1)
            v.addLayout(h)
            v.addStretch(1)

            target.installEventFilter(self)
            self._resize_to_target()

        def eventFilter(self, obj, event):
            if obj is self._target and event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Show,
            ):
                self._resize_to_target()
            return False

        def _resize_to_target(self):
            if self._target is None:
                return
            self.setGeometry(0, 0, self._target.width(), self._target.height())

        def start(self):
            self._group.start()
            self.show()
            self.raise_()

        def stop(self):
            self._group.stop()
            self.hide()

    return CertusSkeletonOverlay


def _get_block_cls():
    global _BLOCK_CLS
    if _BLOCK_CLS is None:
        _BLOCK_CLS = _build_block_class()
    return _BLOCK_CLS


def _get_group_cls():
    global _GROUP_CLS
    if _GROUP_CLS is None:
        _GROUP_CLS = _build_group_class()
    return _GROUP_CLS


def _get_overlay_cls():
    global _OVERLAY_CLS
    if _OVERLAY_CLS is None:
        _OVERLAY_CLS = _build_overlay_class()
    return _OVERLAY_CLS


# =============================================================================
# Public API
# =============================================================================


def skeleton_for(
    widget,
    *,
    lines: int = DEFAULT_LINES,
    label: str = "Loading...",
    line_height: int = DEFAULT_LINE_HEIGHT,
):
    """Build and return a :class:`CertusSkeletonOverlay` covering ``widget``.

    The overlay is *not* started — call ``.start()`` to display it.
    Prefer :func:`install_skeleton` for a lifecycle-managed version.
    """
    if widget is None:
        return None
    Overlay = _get_overlay_cls()
    return Overlay(widget, lines=lines, label=label, line_height=line_height)


def install_skeleton(
    widget,
    *,
    lines: int = DEFAULT_LINES,
    label: str = "Loading...",
    line_height: int = DEFAULT_LINE_HEIGHT,
):
    """Install (once) and start a skeleton overlay on ``widget``.

    Returns the overlay instance so callers can tweak it if needed.
    Subsequent calls on the same widget reuse the same overlay.
    """
    if widget is None:
        return None
    key = id(widget)
    overlay = _OVERLAYS.get(key)
    if overlay is None:
        overlay = skeleton_for(widget, lines=lines, label=label, line_height=line_height)
        _OVERLAYS[key] = overlay

        def _drop_overlay(*_args, overlay_key=key):
            _OVERLAYS.pop(overlay_key, None)

        try:
            widget.destroyed.connect(_drop_overlay)
        except (AttributeError, RuntimeError, TypeError):
            pass
    overlay.start()
    return overlay


def uninstall_skeleton(widget) -> bool:
    """Stop + remove the skeleton overlay previously installed on ``widget``.

    Returns ``True`` if an overlay was found and removed.
    """
    if widget is None:
        return False
    key = id(widget)
    overlay = _OVERLAYS.pop(key, None)
    if overlay is None:
        return False
    try:
        overlay.stop()
        overlay.setParent(None)
        overlay.deleteLater()
    except (AttributeError, RuntimeError, TypeError):
        pass
    return True


def is_skeleton_active(widget) -> bool:
    """Return True if a skeleton overlay is currently attached to ``widget``."""
    if widget is None:
        return False
    return id(widget) in _OVERLAYS


__all__ = [
    "SHIMMER_PERIOD_MS",
    "DEFAULT_LINES",
    "DEFAULT_LINE_HEIGHT",
    "skeleton_for",
    "install_skeleton",
    "uninstall_skeleton",
    "is_skeleton_active",
]
