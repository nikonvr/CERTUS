"""CERTUS multi-step progress tracker (U11).

A vertical list of named steps with a visual indicator of progress:

- **done** steps show a check icon in the theme success color;
- the **current** step shows a spinning loader icon with an emphasised
  title;
- **pending** steps remain muted.

Supports an optional **ETA label** in the header and **per-step
sub-message** so long-running workers (INDEX_SPLINE optimisation, METAL
beam fit, DESIGN full-stack refit) can report fine-grained progress
without opening a modal.

Design
------

- **Pure QWidget**, no threading. Drive it from your worker via
  :meth:`advance_to(index, sub_message=None)` and :meth:`set_eta`.
- **Deterministic states**: each step is in one of ``pending`` /
  ``running`` / ``done`` / ``error``.
- **Data-first**: steps are described by :class:`ProgressStep` dataclass
  entries; the widget is a thin view over this data.
- **Lazy Qt**: all widget construction is behind factory getters, so
  importing the module does not touch Qt.

Public API
----------

- :class:`ProgressStep` — frozen step descriptor.
- :class:`CertusProgressTracker` — the widget.
- :func:`build_progress_tracker(parent, steps, ...)` — factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


SPINNER_PERIOD_MS: Final[int] = 900
ROW_HEIGHT_PX: Final[int] = 28
ICON_SIZE_PX: Final[int] = 16


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class ProgressStep:
    """Descriptor of a single step in a :class:`CertusProgressTracker`."""

    title: str
    key: str = ""
    state: StepState = StepState.PENDING
    sub_message: str = ""

    def __post_init__(self):
        if not self.key:
            self.key = _slug(self.title)


def _slug(s: str) -> str:
    out = []
    for ch in str(s).strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "_", "-", "/"):
            out.append("_")
    return "".join(out) or "step"


# =============================================================================
# Pure-data helpers
# =============================================================================


def step_icon_name(state: StepState | str) -> str:
    if isinstance(state, str):
        try:
            state = StepState(state)
        except ValueError:
            state = StepState.PENDING
    return {
        StepState.PENDING: "circle",
        StepState.RUNNING: "loader",
        StepState.DONE: "check-circle",
        StepState.ERROR: "alert-triangle",
    }[state]


def step_color(state: StepState | str) -> str:
    if isinstance(state, str):
        try:
            state = StepState(state)
        except ValueError:
            state = StepState.PENDING
    try:
        from certus_ui import CertusTheme as T

        mapping = {
            StepState.PENDING: getattr(T, "MID", "#9CA3AF"),
            StepState.RUNNING: getattr(T, "PRIMARY", "#2563EB"),
            StepState.DONE: getattr(T, "SUCCESS", "#10B981"),
            StepState.ERROR: getattr(T, "DANGER", "#EF4444"),
        }
        return str(mapping[state])
    except (ImportError, AttributeError, TypeError):
        return {
            StepState.PENDING: "#9CA3AF",
            StepState.RUNNING: "#2563EB",
            StepState.DONE: "#10B981",
            StepState.ERROR: "#EF4444",
        }[state]


def format_eta(seconds: float | None) -> str:
    """Return a compact human-friendly ETA string."""
    if seconds is None or seconds < 0:
        return ""
    s = int(round(seconds))
    if s < 60:
        return f"ETA ~{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"ETA ~{m}m{sec:02d}s"
    h, m = divmod(m, 60)
    return f"ETA ~{h}h{m:02d}m"


# =============================================================================
# Widget (lazy Qt)
# =============================================================================


_TRACKER_CLS = None


def _build_tracker_class():
    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        QSize,
        Qt,
        pyqtProperty,
    )
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    class _RotatingIconLabel(QLabel):
        """Label that rotates its pixmap around its centre (for the loader)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._angle = 0.0
            self._anim = QPropertyAnimation(self, b"angle", self)
            self._anim.setDuration(SPINNER_PERIOD_MS)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(360.0)
            self._anim.setEasingCurve(QEasingCurve.Type.Linear)
            self._anim.setLoopCount(-1)
            self._base_pix: QPixmap | None = None

        def set_base_pixmap(self, pix: QPixmap | None):
            self._base_pix = pix
            self._apply_rotation()

        def _get_angle(self) -> float:
            return self._angle

        def _set_angle(self, v: float):
            self._angle = float(v) % 360.0
            self._apply_rotation()

        angle = pyqtProperty(float, fget=_get_angle, fset=_set_angle)

        def _apply_rotation(self):
            if self._base_pix is None or self._base_pix.isNull():
                return
            from PyQt6.QtGui import QTransform

            t = QTransform()
            t.rotate(self._angle)
            rotated = self._base_pix.transformed(t, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(rotated)

        def start(self):
            if self._anim.state() != QPropertyAnimation.State.Running:
                self._anim.start()

        def stop(self):
            if self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()
                self._angle = 0.0
                self._apply_rotation()

    class _StepRow(QFrame):
        def __init__(self, step: ProgressStep, parent=None):
            super().__init__(parent)
            self.setObjectName("CertusProgressStep")
            self._step = step
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

            root = QHBoxLayout(self)
            root.setContentsMargins(4, 2, 4, 2)
            root.setSpacing(10)

            self._icon = _RotatingIconLabel(self)
            self._icon.setFixedSize(QSize(ICON_SIZE_PX, ICON_SIZE_PX))
            self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(0)
            self._title = QLabel(step.title, self)
            self._title.setObjectName("step-title")
            text_col.addWidget(self._title)
            self._sub = QLabel(step.sub_message, self)
            self._sub.setObjectName("step-sub")
            self._sub.setWordWrap(True)
            self._sub.setVisible(bool(step.sub_message))
            text_col.addWidget(self._sub)
            root.addLayout(text_col, 1)

            self._apply_state(step.state)

        def set_state(self, state: StepState):
            self._step.state = state
            self._apply_state(state)

        def set_sub_message(self, msg: str):
            self._step.sub_message = msg
            self._sub.setText(msg)
            self._sub.setVisible(bool(msg))

        def _apply_state(self, state: StepState):
            color = step_color(state)
            title_weight = "600" if state == StepState.RUNNING else "500"
            title_color = color if state in (StepState.RUNNING, StepState.ERROR) else "palette(text)"
            self.setStyleSheet(
                f"#step-title {{ color: {title_color}; font-weight: {title_weight}; font-size: 10pt; }}"
                f"#step-sub   {{ color: palette(mid); font-size: 8pt; }}"
            )

            # Icon pixmap
            try:
                from certus_icons import certus_icon

                name = step_icon_name(state)
                pix = certus_icon(name, color=color, size=ICON_SIZE_PX).pixmap(ICON_SIZE_PX, ICON_SIZE_PX)
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                pix = None
            self._icon.set_base_pixmap(pix)

            if state == StepState.RUNNING:
                self._icon.start()
            else:
                self._icon.stop()

    class CertusProgressTracker(QWidget):
        """Multi-step progress indicator."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            steps: list[ProgressStep] | None = None,
            title: str = "Progress",
            eta_seconds: float | None = None,
        ):
            super().__init__(parent)
            self.setObjectName("CertusProgressTracker")
            self._steps: list[ProgressStep] = []
            self._rows: list[_StepRow] = []

            outer = QVBoxLayout(self)
            outer.setContentsMargins(10, 10, 10, 10)
            outer.setSpacing(6)

            header = QHBoxLayout()
            self._title_lbl = QLabel(title, self)
            self._title_lbl.setObjectName("tracker-title")
            self._title_lbl.setStyleSheet("#tracker-title { font-weight: 700; font-size: 11pt; color: palette(text); }")
            header.addWidget(self._title_lbl, 1)
            self._eta_lbl = QLabel("", self)
            self._eta_lbl.setObjectName("tracker-eta")
            self._eta_lbl.setStyleSheet("#tracker-eta { color: palette(mid); font-size: 9pt; font-style: italic; }")
            header.addWidget(self._eta_lbl, 0, Qt.AlignmentFlag.AlignRight)
            outer.addLayout(header)

            self._rows_host = QVBoxLayout()
            self._rows_host.setContentsMargins(0, 0, 0, 0)
            self._rows_host.setSpacing(2)
            outer.addLayout(self._rows_host)

            self.set_steps(steps or [])
            self.set_eta(eta_seconds)

        # -- Public ----------------------------------------------------------
        def set_steps(self, steps: list[ProgressStep]) -> None:
            # Clear
            for row in self._rows:
                self._rows_host.removeWidget(row)
                row.deleteLater()
            self._rows.clear()
            self._steps = list(steps)
            for s in self._steps:
                row = _StepRow(s, self)
                self._rows.append(row)
                self._rows_host.addWidget(row)

        def advance_to(self, index: int, *, sub_message: str | None = None) -> None:
            """Mark steps [0..index-1] as done and ``index`` as running."""
            for i, row in enumerate(self._rows):
                if i < index:
                    row.set_state(StepState.DONE)
                elif i == index:
                    row.set_state(StepState.RUNNING)
                    if sub_message is not None:
                        row.set_sub_message(sub_message)
                else:
                    row.set_state(StepState.PENDING)

        def mark_step(self, index: int, state: StepState, *, sub_message: str | None = None) -> None:
            if 0 <= index < len(self._rows):
                self._rows[index].set_state(state)
                if sub_message is not None:
                    self._rows[index].set_sub_message(sub_message)

        def mark_all_done(self) -> None:
            for row in self._rows:
                row.set_state(StepState.DONE)

        def set_eta(self, seconds: float | None) -> None:
            txt = format_eta(seconds)
            self._eta_lbl.setText(txt)
            self._eta_lbl.setVisible(bool(txt))

        def steps(self) -> list[ProgressStep]:
            return list(self._steps)

        def state_of(self, index: int) -> StepState | None:
            if 0 <= index < len(self._steps):
                return self._steps[index].state
            return None

    return CertusProgressTracker


def _get_tracker_cls():
    global _TRACKER_CLS
    if _TRACKER_CLS is None:
        _TRACKER_CLS = _build_tracker_class()
    return _TRACKER_CLS


# =============================================================================
# Public factory
# =============================================================================


def build_progress_tracker(
    parent=None,
    *,
    steps: list[ProgressStep] | list[str] | None = None,
    title: str = "Progress",
    eta_seconds: float | None = None,
):
    """Return a :class:`CertusProgressTracker`.

    ``steps`` accepts either a list of :class:`ProgressStep` or a list
    of plain strings (converted to steps with ``state=pending``).
    """
    Tracker = _get_tracker_cls()
    step_objs: list[ProgressStep] = []
    for s in steps or []:
        if isinstance(s, ProgressStep):
            step_objs.append(s)
        else:
            step_objs.append(ProgressStep(title=str(s)))
    return Tracker(parent, steps=step_objs, title=title, eta_seconds=eta_seconds)


__all__ = [
    "SPINNER_PERIOD_MS",
    "StepState",
    "ProgressStep",
    "step_icon_name",
    "step_color",
    "format_eta",
    "build_progress_tracker",
]
