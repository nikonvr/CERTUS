"""CERTUS status badges (U9).

Compact colored pill widgets that normalise how the suite renders
statuses (idle / running / success / error / warning / info / neutral).
Replaces ad-hoc ``QLabel`` + inline stylesheets scattered across the
monoliths.

Design
------

- **Consistent palette**: each variant ties to :class:`CertusTheme` and
  to a Lucide icon (see :func:`variant_icon_name`).
- **Tiny footprint**: a single :class:`QLabel` subclass with a custom
  style sheet and an optional icon pixmap — no heavy effects.
- **Dynamic**: :meth:`set_variant` / :meth:`set_text` so a badge can be
  updated inline without recreation.
- **Pure-data introspection**: constants :data:`VARIANT_LABELS` and
  :func:`variant_color` are usable without Qt for tests.

Public API
----------

- :class:`CertusStatusBadge` - the widget.
- :func:`build_status_badge(parent, text, variant, ...)` - factory.
- :func:`supported_variants()`, :func:`variant_icon_name(variant)`,
  :func:`variant_color(variant)` - pure-data helpers.
"""

from __future__ import annotations

from typing import Final


VARIANT_LABELS: Final[dict[str, str]] = {
    "idle": "Idle",
    "running": "Running",
    "success": "Success",
    "error": "Error",
    "warning": "Warning",
    "info": "Info",
    "neutral": "",
}

_VARIANT_ICONS: Final[dict[str, str]] = {
    "idle": "pause",
    "running": "loader",
    "success": "check-circle",
    "error": "alert-triangle",
    "warning": "alert-triangle",
    "info": "info",
    "neutral": "circle",
}


def supported_variants() -> list[str]:
    return list(VARIANT_LABELS.keys())


def variant_icon_name(variant: str) -> str:
    return _VARIANT_ICONS.get(variant, "circle")


def variant_color(variant: str) -> tuple[str, str, str]:
    """Return ``(bg, fg, border)`` hex strings for ``variant``.

    Falls back to ``neutral`` when the variant is unknown. Reads from
    :class:`CertusTheme` when available, and uses a hard-coded fallback
    palette otherwise so the function remains pure-python.
    """
    fallback = {
        "idle": ("#F3F4F6", "#6B7280", "#D1D5DB"),
        "running": ("#DBEAFE", "#1E40AF", "#93C5FD"),
        "success": ("#D1FAE5", "#065F46", "#6EE7B7"),
        "error": ("#FEE2E2", "#991B1B", "#FCA5A5"),
        "warning": ("#FEF3C7", "#92400E", "#FCD34D"),
        "info": ("#E0F2FE", "#075985", "#7DD3FC"),
        "neutral": ("#F9FAFB", "#374151", "#E5E7EB"),
    }
    base = fallback.get(variant, fallback["neutral"])
    try:
        from certus_ui import CertusTheme as T

        accent_map = {
            "idle": getattr(T, "MID", base[1]),
            "running": getattr(T, "INFO", base[1]),
            "success": getattr(T, "SUCCESS", base[1]),
            "error": getattr(T, "DANGER", base[1]),
            "warning": getattr(T, "WARNING", base[1]),
            "info": getattr(T, "INFO", base[1]),
            "neutral": getattr(T, "MID", base[1]),
        }
        fg = accent_map.get(variant, base[1])
        return base[0], str(fg), base[2]
    except (ImportError, AttributeError, TypeError):
        return base


# =============================================================================
# Widget (lazy Qt)
# =============================================================================


_BADGE_CLS = None


def _build_badge_class():
    from PyQt6.QtCore import QSize, Qt
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

    class CertusStatusBadge(QWidget):
        """Small coloured pill conveying a status."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            text: str | None = None,
            variant: str = "neutral",
            with_icon: bool = True,
            uppercase: bool = False,
        ):
            super().__init__(parent)
            self.setObjectName("CertusStatusBadge")
            self._variant = variant if variant in VARIANT_LABELS else "neutral"
            self._uppercase = bool(uppercase)
            self._with_icon = bool(with_icon)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

            root = QHBoxLayout(self)
            root.setContentsMargins(8, 2, 10, 2)
            root.setSpacing(6)

            self._icon_lbl = QLabel(self)
            self._icon_lbl.setFixedSize(QSize(12, 12))
            self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(self._icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            self._text_lbl = QLabel(self)
            self._text_lbl.setObjectName("badge-text")
            root.addWidget(self._text_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

            if text is None:
                text = VARIANT_LABELS.get(self._variant, "")
            self.set_text(text)
            self.set_variant(self._variant)

        # -- Public ----------------------------------------------------------
        def set_variant(self, variant: str) -> None:
            self._variant = variant if variant in VARIANT_LABELS else "neutral"
            bg, fg, border = variant_color(self._variant)
            self.setStyleSheet(
                "QWidget#CertusStatusBadge { "
                f" background: {bg}; "
                f" border: 1px solid {border}; "
                " border-radius: 10px; "
                "}"
                "QLabel#badge-text { "
                f" color: {fg}; "
                " font-weight: 600; font-size: 9pt; "
                "}"
            )
            self._refresh_icon()
            self.adjustSize()

        def set_text(self, text: str) -> None:
            formatted = text.upper() if self._uppercase and text else text
            self._text_lbl.setText(formatted or "")
            self._text_lbl.setVisible(bool(formatted))
            self.adjustSize()

        def variant(self) -> str:
            return self._variant

        def text(self) -> str:
            return self._text_lbl.text()

        # -- Internals ------------------------------------------------------
        def _refresh_icon(self) -> None:
            if not self._with_icon:
                self._icon_lbl.setVisible(False)
                return
            try:
                from certus_icons import certus_icon

                _bg, fg, _ = variant_color(self._variant)
                name = variant_icon_name(self._variant)
                pix: QPixmap = certus_icon(name, color=fg, size=12).pixmap(12, 12)
                self._icon_lbl.setPixmap(pix)
                self._icon_lbl.setVisible(True)
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                self._icon_lbl.setVisible(False)

    return CertusStatusBadge


def _get_badge_cls():
    global _BADGE_CLS
    if _BADGE_CLS is None:
        _BADGE_CLS = _build_badge_class()
    return _BADGE_CLS


# =============================================================================
# Factories
# =============================================================================


def build_status_badge(
    parent=None,
    *,
    text: str | None = None,
    variant: str = "neutral",
    with_icon: bool = True,
    uppercase: bool = False,
):
    """Convenience factory returning a configured :class:`CertusStatusBadge`."""
    Badge = _get_badge_cls()
    return Badge(
        parent,
        text=text,
        variant=variant,
        with_icon=with_icon,
        uppercase=uppercase,
    )


__all__ = [
    "VARIANT_LABELS",
    "supported_variants",
    "variant_icon_name",
    "variant_color",
    "build_status_badge",
]
