"""CERTUS micro-animations (U8).

A tiny toolkit of **consistent**, **cheap** transitions used across the
suite to give the UI a subtle sense of motion without distraction:

- :func:`fade_in` / :func:`fade_out` - opacity transitions on any widget
  that can receive a :class:`QGraphicsOpacityEffect`.
- :func:`slide_in` - slide a widget from off-panel into place (good for
  toasts, snackbars, side panels).
- :func:`hover_lift(widget, lift_px=3)` - install an event filter that
  animates a small geometry raise on hover (cards, buttons).
- :func:`pulse(widget, ...)` - brief opacity pulse drawing attention to
  a freshly-updated element.

Design rules
------------

- **Cheap**: a single :class:`QPropertyAnimation` per call, capped
  short (<= 250 ms) so interactions never feel sluggish.
- **Non-blocking**: animations return the animation object so callers
  can keep references if they want; otherwise the module stores them on
  the target widget to prevent GC.
- **Reversible**: hover helpers remember their original geometry so
  removing the filter restores the widget exactly.
- **Pure-data introspection**: constants and helpers like
  :data:`DEFAULT_DURATION_MS` / :func:`easing_names` are importable
  without Qt for tests.

Public API
----------

- :data:`DEFAULT_DURATION_MS`, :data:`HOVER_DURATION_MS`,
  :data:`PULSE_DURATION_MS`
- :func:`fade_in`, :func:`fade_out`, :func:`slide_in`, :func:`pulse`
- :func:`hover_lift`, :func:`unhover_lift`
- :func:`easing_names` / :func:`is_valid_easing`
"""

from __future__ import annotations

from typing import Final


DEFAULT_DURATION_MS: Final[int] = 200
HOVER_DURATION_MS: Final[int] = 140
PULSE_DURATION_MS: Final[int] = 420
DEFAULT_HOVER_LIFT_PX: Final[int] = 3


_EASING_NAMES: Final[tuple[str, ...]] = (
    "linear",
    "in_cubic",
    "out_cubic",
    "in_out_cubic",
    "in_quad",
    "out_quad",
    "in_out_quad",
    "in_back",
    "out_back",
)


def easing_names() -> tuple[str, ...]:
    return _EASING_NAMES


def is_valid_easing(name: str) -> bool:
    return name in _EASING_NAMES


# =============================================================================
# Qt helpers (lazy imports)
# =============================================================================


_HOVER_FILTERS: dict[int, object] = {}


def _resolve_easing(name: str):
    from PyQt6.QtCore import QEasingCurve

    table = {
        "linear": QEasingCurve.Type.Linear,
        "in_cubic": QEasingCurve.Type.InCubic,
        "out_cubic": QEasingCurve.Type.OutCubic,
        "in_out_cubic": QEasingCurve.Type.InOutCubic,
        "in_quad": QEasingCurve.Type.InQuad,
        "out_quad": QEasingCurve.Type.OutQuad,
        "in_out_quad": QEasingCurve.Type.InOutQuad,
        "in_back": QEasingCurve.Type.InBack,
        "out_back": QEasingCurve.Type.OutBack,
    }
    return QEasingCurve(table.get(name, QEasingCurve.Type.OutCubic))


def _attach_anim(widget, key: str, anim) -> None:
    """Keep ``anim`` alive on ``widget`` so the GC does not drop it."""
    bag = getattr(widget, "_certus_anims", None)
    if bag is None:
        bag = {}
        try:
            setattr(widget, "_certus_anims", bag)
        except (AttributeError, RuntimeError, TypeError):
            return
    bag[key] = anim


def _ensure_opacity_effect(widget):
    from PyQt6.QtWidgets import QGraphicsOpacityEffect

    effect = widget.graphicsEffect() if hasattr(widget, "graphicsEffect") else None
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(1.0)
        widget.setGraphicsEffect(effect)
    return effect


# =============================================================================
# Fade
# =============================================================================


def fade_in(widget, *, duration_ms: int = DEFAULT_DURATION_MS, easing: str = "out_cubic"):
    """Fade ``widget`` from transparent to fully opaque.

    Returns the :class:`QPropertyAnimation` instance (already started),
    or ``None`` if ``widget`` is falsy.
    """
    if widget is None:
        return None
    try:
        from PyQt6.QtCore import QPropertyAnimation
    except ImportError:
        return None

    effect = _ensure_opacity_effect(widget)
    effect.setOpacity(0.0)
    if not widget.isVisible():
        widget.show()

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(int(duration_ms))
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(_resolve_easing(easing))
    _attach_anim(widget, "fade_in", anim)
    anim.start()
    return anim


def fade_out(widget, *, duration_ms: int = DEFAULT_DURATION_MS, hide_on_finish: bool = True, easing: str = "in_cubic"):
    """Fade ``widget`` from its current opacity to transparent."""
    if widget is None:
        return None
    try:
        from PyQt6.QtCore import QPropertyAnimation
    except ImportError:
        return None

    effect = _ensure_opacity_effect(widget)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(int(duration_ms))
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(_resolve_easing(easing))
    if hide_on_finish:
        anim.finished.connect(widget.hide)
    _attach_anim(widget, "fade_out", anim)
    anim.start()
    return anim


# =============================================================================
# Slide
# =============================================================================


def slide_in(
    widget,
    *,
    direction: str = "up",
    distance_px: int = 12,
    duration_ms: int = DEFAULT_DURATION_MS,
    easing: str = "out_cubic",
):
    """Slide ``widget`` into place by ``distance_px`` from a direction.

    ``direction`` ∈ ``up`` / ``down`` / ``left`` / ``right``.
    """
    if widget is None:
        return None
    try:
        from PyQt6.QtCore import QPoint, QPropertyAnimation
    except ImportError:
        return None

    end_pos = widget.pos()
    dx = dy = 0
    if direction == "up":
        dy = int(distance_px)
    elif direction == "down":
        dy = -int(distance_px)
    elif direction == "left":
        dx = int(distance_px)
    elif direction == "right":
        dx = -int(distance_px)
    start_pos = QPoint(end_pos.x() + dx, end_pos.y() + dy)
    widget.move(start_pos)
    if not widget.isVisible():
        widget.show()

    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(int(duration_ms))
    anim.setStartValue(start_pos)
    anim.setEndValue(end_pos)
    anim.setEasingCurve(_resolve_easing(easing))
    _attach_anim(widget, "slide_in", anim)
    anim.start()
    return anim


# =============================================================================
# Pulse
# =============================================================================


def pulse(widget, *, duration_ms: int = PULSE_DURATION_MS, min_opacity: float = 0.55):
    """Brief opacity pulse to draw attention to a fresh update.

    Goes from 1.0 -> ``min_opacity`` -> 1.0 using a symmetric curve.
    """
    if widget is None:
        return None
    try:
        from PyQt6.QtCore import QPropertyAnimation
    except ImportError:
        return None

    effect = _ensure_opacity_effect(widget)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(int(duration_ms))
    anim.setKeyValueAt(0.0, 1.0)
    anim.setKeyValueAt(0.5, float(max(0.0, min(1.0, min_opacity))))
    anim.setKeyValueAt(1.0, 1.0)
    anim.setEasingCurve(_resolve_easing("in_out_cubic"))
    _attach_anim(widget, "pulse", anim)
    anim.start()
    return anim


# =============================================================================
# Hover lift
# =============================================================================


def _build_hover_filter(target, lift_px: int, duration_ms: int):
    from PyQt6.QtCore import QEvent, QObject, QPropertyAnimation, QRect

    class _HoverLiftFilter(QObject):
        def __init__(self):
            super().__init__(target)
            self._target = target
            self._lift = int(lift_px)
            self._duration = int(duration_ms)
            self._base: QRect | None = None
            target.installEventFilter(self)

        def eventFilter(self, obj, event):
            if obj is not self._target:
                return False
            if event.type() == QEvent.Type.Enter:
                self._animate_to(-self._lift)
            elif event.type() == QEvent.Type.Leave:
                self._animate_to(0)
            return False

        def _animate_to(self, offset: int):
            if self._base is None:
                self._base = QRect(self._target.geometry())
            start = self._target.geometry()
            end = QRect(self._base)
            end.moveTop(self._base.top() + offset)
            anim = QPropertyAnimation(self._target, b"geometry", self._target)
            anim.setDuration(self._duration)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(_resolve_easing("out_cubic"))
            _attach_anim(self._target, "hover_lift", anim)
            anim.start()

    return _HoverLiftFilter()


def hover_lift(
    widget,
    *,
    lift_px: int = DEFAULT_HOVER_LIFT_PX,
    duration_ms: int = HOVER_DURATION_MS,
):
    """Make ``widget`` visibly lift by ``lift_px`` on hover.

    Returns the filter object. Remove with :func:`unhover_lift(widget)`.
    """
    if widget is None:
        return None
    # Already installed: update params silently
    existing = _HOVER_FILTERS.get(id(widget))
    if existing is not None:
        try:
            existing._lift = int(lift_px)
            existing._duration = int(duration_ms)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        return existing

    try:
        flt = _build_hover_filter(widget, lift_px, duration_ms)
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return None
    _HOVER_FILTERS[id(widget)] = flt

    def _drop_hover_filter(*_args, key=id(widget)):
        _HOVER_FILTERS.pop(key, None)

    try:
        widget.destroyed.connect(_drop_hover_filter)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return flt


def unhover_lift(widget) -> bool:
    """Remove a previously installed hover-lift filter."""
    if widget is None:
        return False
    flt = _HOVER_FILTERS.pop(id(widget), None)
    if flt is None:
        return False
    try:
        widget.removeEventFilter(flt)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return True


__all__ = [
    "DEFAULT_DURATION_MS",
    "HOVER_DURATION_MS",
    "PULSE_DURATION_MS",
    "DEFAULT_HOVER_LIFT_PX",
    "easing_names",
    "is_valid_easing",
    "fade_in",
    "fade_out",
    "slide_in",
    "pulse",
    "hover_lift",
    "unhover_lift",
]
