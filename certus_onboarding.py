"""CERTUS onboarding tour (U9).

A first-run guided tour that walks a new user through the key controls
of each monolithic app using a **spotlight + coach-mark** pattern:

1. A semi-transparent full-window overlay dims everything.
2. A clear rectangular hole "spotlights" the widget of the current step.
3. A floating coach-mark (card with title, body, Skip/Next/Finish
   buttons) is positioned adjacent to the spotlight.
4. The tour remembers its "completed" state per app via ``QSettings`` so
   each user sees it only once; a "Don't show again" checkbox is
   optionally offered.

Design
------

- **Data-first**: the tour is described by a list of :class:`TourStep`
  objects (frozen dataclass). The widget layer is a thin view over this
  data.
- **Safe when widgets are missing**: a step whose target widget cannot
  be resolved is silently skipped - tour continues, no crash.
- **Opt-in**: applications call :func:`run_onboarding(parent, app_name,
  steps)` after the window is shown. Nothing happens unless called.
- **Testable**: the persistence layer (QSettings key / is-completed
  flag) is pure-python and covered by tests.

Public API
----------

- :class:`TourStep`, :class:`OnboardingResult`
- :func:`is_completed(app_name)` / :func:`mark_completed(app_name)` /
  :func:`reset_onboarding(app_name=None)`
- :func:`run_onboarding(parent, app_name, steps, *, force=False)` -
  returns ``OnboardingResult`` (``"completed"`` / ``"skipped"`` /
  ``"already_done"`` / ``"empty"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Final, Optional


_QS_ORG: Final[str] = "CERTUS"
_QS_APP: Final[str] = "onboarding"


class OnboardingResult(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ALREADY_DONE = "already_done"
    EMPTY = "empty"


@dataclass(frozen=True)
class TourStep:
    """One coach-mark in an onboarding tour.

    Parameters
    ----------
    title:
        Short heading shown in the coach-mark.
    body:
        Description text (wrapped).
    target_attr:
        Attribute name to resolve on the app instance (e.g.
        ``"load_button"`` means ``parent.load_button``). Pass ``None``
        or an empty string to show a "general" step centred on the
        window.
    placement:
        Preferred coach-mark placement relative to the target
        (``"auto"`` / ``"top"`` / ``"bottom"`` / ``"left"`` /
        ``"right"``).
    icon_name:
        Optional Lucide icon.
    """

    title: str
    body: str
    target_attr: Optional[str] = None
    placement: str = "auto"
    icon_name: Optional[str] = None


# =============================================================================
# Persistence (pure-python, QSettings-backed with memory fallback)
# =============================================================================


_MEMORY_FLAGS: dict[str, bool] = {}


def _qs_settings():
    try:
        from PyQt6.QtCore import QSettings

        return QSettings(_QS_ORG, _QS_APP)
    except ImportError:
        return None


def _qs_key(app_name: str) -> str:
    return f"onboarding/{app_name or 'default'}/completed"


def is_completed(app_name: str) -> bool:
    """Return True if the user already finished (or skipped) the tour."""
    qs = _qs_settings()
    if qs is None:
        return bool(_MEMORY_FLAGS.get(app_name, False))
    v = qs.value(_qs_key(app_name))
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def mark_completed(app_name: str, value: bool = True) -> None:
    qs = _qs_settings()
    if qs is None:
        _MEMORY_FLAGS[app_name] = bool(value)
        return
    qs.setValue(_qs_key(app_name), bool(value))
    qs.sync()


def reset_onboarding(app_name: str | None = None) -> None:
    """Forget the "completed" flag so the tour shows on next launch."""
    qs = _qs_settings()
    if qs is None:
        if app_name is None:
            _MEMORY_FLAGS.clear()
        else:
            _MEMORY_FLAGS.pop(app_name, None)
        return
    if app_name is None:
        qs.clear()
    else:
        qs.remove(_qs_key(app_name))
    qs.sync()


# =============================================================================
# Resolution helpers (also pure-python, testable without Qt)
# =============================================================================


def resolve_target(parent, target_attr: Optional[str]):
    """Look up ``target_attr`` on ``parent``. Returns the widget or None."""
    if not target_attr:
        return None
    try:
        w = getattr(parent, target_attr, None)
    except (AttributeError, RuntimeError, TypeError):
        return None
    if w is None:
        return None
    return w


def filter_resolvable_steps(parent, steps: list[TourStep]) -> list[tuple[TourStep, object | None]]:
    """Return ``(step, target)`` pairs, dropping steps whose target went missing.

    Steps with an empty ``target_attr`` always survive (general step).
    """
    out: list[tuple[TourStep, object | None]] = []
    for step in steps or []:
        if not step.target_attr:
            out.append((step, None))
            continue
        target = resolve_target(parent, step.target_attr)
        if target is None:
            continue
        out.append((step, target))
    return out


# =============================================================================
# Runner
# =============================================================================


def _build_overlay_class():
    from PyQt6.QtCore import QEvent, QRect, Qt, pyqtSignal
    from PyQt6.QtGui import QColor, QPainter, QPainterPath
    from PyQt6.QtWidgets import (
        QCheckBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    class _CoachMark(QFrame):
        def __init__(self, parent, step: TourStep, index: int, total: int):
            super().__init__(parent)
            self.setObjectName("CertusCoachMark")
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setMaximumWidth(360)

            v = QVBoxLayout(self)
            v.setContentsMargins(14, 12, 14, 12)
            v.setSpacing(8)

            # Title
            t = QLabel(step.title, self)
            t.setObjectName("coach-title")
            t.setStyleSheet("#coach-title { font-size: 11pt; font-weight: 700; color: palette(text); }")
            v.addWidget(t)

            # Body
            b = QLabel(step.body, self)
            b.setObjectName("coach-body")
            b.setWordWrap(True)
            b.setStyleSheet("#coach-body { font-size: 9pt; color: palette(mid); }")
            v.addWidget(b)

            # Progress
            prog = QLabel(f"Step {index + 1} / {total}", self)
            prog.setObjectName("coach-progress")
            prog.setStyleSheet("#coach-progress { font-size: 8pt; color: palette(mid); font-style: italic; }")
            v.addWidget(prog)

            # Buttons
            row = QHBoxLayout()
            self.btn_skip = QPushButton("Skip", self)
            self.btn_back = QPushButton("Back", self)
            self.btn_back.setEnabled(index > 0)
            self.btn_next = QPushButton("Finish" if index == total - 1 else "Next", self)
            row.addWidget(self.btn_skip)
            row.addStretch(1)
            row.addWidget(self.btn_back)
            row.addWidget(self.btn_next)
            v.addLayout(row)

            self.setStyleSheet(
                "#CertusCoachMark { background: palette(base); border: 1px solid palette(mid); border-radius: 8px; }"
            )

    class _OnboardingOverlay(QWidget):
        finished = pyqtSignal(str)  # OnboardingResult value

        def __init__(self, parent, app_name: str, steps: list[tuple[TourStep, object | None]]):
            super().__init__(parent)
            self._parent = parent
            self._app_name = app_name
            self._steps = list(steps)
            self._index = 0
            self._coach: _CoachMark | None = None
            self._dont_show: QCheckBox | None = None

            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet("background: transparent;")
            parent.installEventFilter(self)
            self._resize_to_parent()
            self._build_coach()

        def eventFilter(self, obj, event):
            if obj is self._parent and event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Move,
            ):
                self._resize_to_parent()
                self._position_coach()
            return False

        def _resize_to_parent(self):
            self.setGeometry(0, 0, self._parent.width(), self._parent.height())

        # -- Drawing ---------------------------------------------------------
        def paintEvent(self, _event):  # noqa: N802 Qt
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Full-window dim
            path = QPainterPath()
            path.addRect(0.0, 0.0, float(self.width()), float(self.height()))
            hole = self._spotlight_rect()
            if hole is not None:
                hole_path = QPainterPath()
                hole_path.addRoundedRect(
                    float(hole.x()),
                    float(hole.y()),
                    float(hole.width()),
                    float(hole.height()),
                    10.0,
                    10.0,
                )
                path = path.subtracted(hole_path)
                # Accent border around spotlight
                p.setBrush(Qt.BrushStyle.NoBrush)
                pen_color = QColor(37, 99, 235, 220)
                pen = p.pen()
                pen.setColor(pen_color)
                pen.setWidth(2)
                p.setPen(pen)
                p.drawRoundedRect(hole, 10, 10)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 140))
            p.drawPath(path)
            p.end()

        def _spotlight_rect(self) -> QRect | None:
            if not self._steps:
                return None
            _step, target = self._steps[self._index]
            if target is None:
                return None
            try:
                tl = target.mapTo(self._parent, target.rect().topLeft())
                return QRect(tl, target.size()).adjusted(-6, -6, 6, 6)
            except (AttributeError, RuntimeError, TypeError):
                return None

        # -- Coach mark ------------------------------------------------------
        def _build_coach(self):
            if self._coach is not None:
                self._coach.deleteLater()
            step, _ = self._steps[self._index]
            self._coach = _CoachMark(self, step, self._index, len(self._steps))
            self._coach.btn_skip.clicked.connect(self._on_skip)
            self._coach.btn_back.clicked.connect(self._on_back)
            self._coach.btn_next.clicked.connect(self._on_next)
            self._coach.show()
            self._position_coach()

        def _position_coach(self):
            if self._coach is None:
                return
            self._coach.adjustSize()
            hole = self._spotlight_rect()
            margin = 14
            if hole is None:
                # Center on window
                x = (self.width() - self._coach.width()) // 2
                y = (self.height() - self._coach.height()) // 2
            else:
                # Prefer below the hole; if no room, put it above
                below_y = hole.bottom() + margin
                if below_y + self._coach.height() <= self.height() - margin:
                    y = below_y
                else:
                    y = max(margin, hole.top() - self._coach.height() - margin)
                x = hole.left()
                if x + self._coach.width() > self.width() - margin:
                    x = self.width() - self._coach.width() - margin
                x = max(margin, x)
            self._coach.move(x, y)

        # -- Navigation ------------------------------------------------------
        def _on_skip(self):
            mark_completed(self._app_name, True)
            self._close(OnboardingResult.SKIPPED.value)

        def _on_back(self):
            if self._index > 0:
                self._index -= 1
                self._build_coach()
                self.update()

        def _on_next(self):
            if self._index == len(self._steps) - 1:
                mark_completed(self._app_name, True)
                self._close(OnboardingResult.COMPLETED.value)
            else:
                self._index += 1
                self._build_coach()
                self.update()

        def _close(self, result: str):
            self.finished.emit(result)
            self.hide()
            self.setParent(None)
            self.deleteLater()

    return _OnboardingOverlay


def run_onboarding(
    parent,
    app_name: str,
    steps: list[TourStep],
    *,
    force: bool = False,
    on_finished: Callable[[str], None] | None = None,
) -> str:
    """Start the tour for ``app_name`` on ``parent``.

    Skipped if the tour was already completed (unless ``force=True``).
    Returns the initial :class:`OnboardingResult` string. Actual
    per-step progression happens asynchronously — pass ``on_finished``
    if you need the final outcome.
    """
    if parent is None or not steps:
        return OnboardingResult.EMPTY.value
    if not force and is_completed(app_name):
        return OnboardingResult.ALREADY_DONE.value

    resolvable = filter_resolvable_steps(parent, steps)
    if not resolvable:
        return OnboardingResult.EMPTY.value

    try:
        Overlay = _build_overlay_class()
    except (ImportError, AttributeError, RuntimeError, TypeError):
        # Qt not available - mark completed silently
        mark_completed(app_name, True)
        if on_finished:
            on_finished(OnboardingResult.COMPLETED.value)
        return OnboardingResult.COMPLETED.value

    overlay = Overlay(parent, app_name, resolvable)
    if on_finished:
        overlay.finished.connect(on_finished)
    overlay.show()
    overlay.raise_()
    return "running"


__all__ = [
    "TourStep",
    "OnboardingResult",
    "is_completed",
    "mark_completed",
    "reset_onboarding",
    "resolve_target",
    "filter_resolvable_steps",
    "run_onboarding",
]
