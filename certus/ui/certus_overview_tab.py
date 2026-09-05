"""Shared synthesis banner for the CERTUS suite.

Rationale: DESIGN, INDEX and both METAL modules devoted a whole tab of the
scientific area to static marketing cards ("Why CERTUS?", "About") carrying no
measured value, while an operator had to hunt across the status bar and the plot
titles to answer "did this fit converge?". CERTUS-INDEX-SPLINE already solved
this with a CompleteEASE-style KPI banner; this module generalises that widget so
every app can expose the same one-glance summary.

The banner holds no domain logic: callers push values through :meth:`set_value`.
"""

from __future__ import annotations

import logging
from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from certus.ui.certus_theme import CertusTheme

# Tone -> theme attribute, resolved lazily so a theme switch is picked up.
_TONE_ATTRS = {
    "neutral": "TEXT_MAIN",
    "primary": "PRIMARY",
    "good": "SUCCESS",
    "warn": "WARNING",
    "bad": "CHART_DANGER",
}

PLACEHOLDER = "—"


def _tone_color(tone: str) -> str:
    attr = _TONE_ATTRS.get(tone, "TEXT_MAIN")
    return str(getattr(CertusTheme, attr, None) or getattr(CertusTheme, "TEXT_MAIN", "#212529"))


class CertusKpiBanner(QFrame):
    """Horizontal strip of labelled result values.

    ``fields`` is an iterable of ``(key, caption)``; ``key`` is what callers use
    with :meth:`set_value`, ``caption`` is what the operator reads.
    """

    def __init__(self, fields: Iterable[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("certusKpiBanner")
        self.setFixedHeight(58)
        self.setStyleSheet(
            f"#certusKpiBanner {{ background: {CertusTheme.SURFACE};"
            f" border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; }}"
        )
        # A KPI strip must never dictate how wide the panel is. Left on the
        # default Preferred policy this banner claimed a 630 px minimum, which
        # unbalanced the main splitter and cost CERTUS-DESIGN 12 points of plot
        # area (71.9 % -> 60.1 %, measured). Ignored lets it shrink freely.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(18)

        self._values: dict[str, QLabel] = {}
        for key, caption in fields:
            box = QVBoxLayout()
            box.setSpacing(1)

            lbl_caption = QLabel(caption)
            lbl_caption.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-weight: bold;")
            lbl_value = QLabel(PLACEHOLDER)
            lbl_value.setStyleSheet(f"color: {_tone_color('primary')}; font-size: 14px; font-weight: 700;")
            lbl_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            box.addWidget(lbl_caption)
            box.addWidget(lbl_value)
            lay.addLayout(box)
            self._values[key] = lbl_value

        lay.addStretch(1)

    def set_value(self, key: str, value: str, tone: str = "primary") -> None:
        """Update one KPI. Unknown keys are ignored rather than raising."""
        lbl = self._values.get(key)
        if lbl is None:
            logging.getLogger("CERTUS").debug("Unknown KPI key %r", key)
            return
        try:
            lbl.setText(str(value))
            lbl.setStyleSheet(f"color: {_tone_color(tone)}; font-size: 14px; font-weight: 700;")
        except RuntimeError:  # widget already destroyed
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def reset(self) -> None:
        """Blank every KPI - used when the model changes and results go stale."""
        for key in self._values:
            self.set_value(key, PLACEHOLDER, "neutral")

    def keys(self) -> tuple[str, ...]:
        return tuple(self._values)


def build_synthesis_tab(
    banner: CertusKpiBanner,
    hint: str,
    extra: QWidget | None = None,
) -> QWidget:
    """Wrap ``banner`` into a tab body: caption, KPI strip, optional content.

    ``extra`` is stretched to fill the remaining height. When it is None the
    banner stays pinned to the top rather than floating in the middle of an
    empty tab.
    """
    panel = QWidget()
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)

    lbl_hint = QLabel(hint)
    lbl_hint.setWordWrap(True)
    lbl_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
    lay.addWidget(lbl_hint)

    lay.addWidget(banner)

    if extra is not None:
        lay.addWidget(extra, 1)
    else:
        lay.addStretch(1)

    return panel
