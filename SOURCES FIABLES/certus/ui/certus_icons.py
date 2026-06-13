"""CERTUS icon system (U2).

Theme-aware SVG icon helper built on top of a bundled Lucide-style icon
set. Every icon is stored as a minimal single-path SVG with a ``{color}``
placeholder so the same asset can be rendered in any accent color — in
particular, the current theme foreground.

Public API
----------

- :func:`certus_icon(name, color=None, size=20) -> QIcon`:
    Returns a rendered ``QIcon`` (pixmap-backed). Color defaults to the
    live :class:`CertusTheme.TEXT_MAIN`. The result is LRU-cached.
- :func:`available_icon_names() -> list[str]`:
    Names currently registered (sorted).
- :data:`ICON_SVG_SOURCES`:
    The raw templates, exposed for test/inspection.

Design choices
--------------

- Shipped **inline** (no external ``assets/icons/`` directory to manage).
  Each icon is ~1 line of SVG data; the payload is < 6 KB total and lives
  next to the helper, so imports work even if the repo is partially
  pruned or packaged.
- Backend: ``QSvgRenderer`` paints onto a ``QPixmap`` once per
  ``(name, color, size)``; the pixmap is cached.
- Shape: all icons use a 24x24 viewBox, 1.75 stroke width, round caps,
  aligned with Lucide defaults — visually coherent with the rest of the
  suite once U1 is applied.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Final


def _qsvg_stack_known_unstable() -> bool:
    """True when SVG rendering should be skipped to avoid a native crash.

    PyQt6 ``QSvgRenderer`` on **Windows + CPython 3.14+** can abort the process
    while painting (repro: minimal ``QSvgRenderer`` + ``QPainter`` + ``QPixmap``).
    Callers can override with env ``CERTUS_SVG_ICONS=1|true|on`` to force SVG
    (use only when a fixed wheel is available).
    """
    o = os.environ.get("CERTUS_SVG_ICONS", "").strip().lower()
    if o in ("1", "true", "yes", "on"):
        return False
    if o in ("0", "false", "no", "off"):
        return True
    return sys.platform == "win32" and sys.version_info >= (3, 14)


def is_svg_icon_rendering_disabled() -> bool:
    """True when :func:`certus_icon` intentionally returns an empty :class:`QIcon`."""
    return _qsvg_stack_known_unstable()


# =============================================================================
# SVG templates (Lucide-compatible, 24x24, stroke={color})
# =============================================================================
#
# Every entry is a function returning an SVG string given a stroke color.
# Keeping them as format templates (rather than raw files) avoids any
# filesystem coupling and makes theme-aware recolor trivial.

_SVG_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{color}" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round">'
)
_SVG_FOOT = "</svg>"


def _svg(body: str) -> str:
    return _SVG_HEAD + body + _SVG_FOOT


# Hand-curated Lucide-style paths for the 25 most useful icons across the
# CERTUS suite. Shape data taken from the Lucide icon set (ISC license).
ICON_SVG_SOURCES: Final[dict[str, str]] = {
    # File & IO
    "save": _svg(
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 3 7 8 15 8"/>'
    ),
    "folder-open": _svg(
        '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/>'
    ),
    "file": _svg(
        '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z"/><polyline points="14 2 14 8 20 8"/>'
    ),
    "download": _svg(
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "upload": _svg(
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>'
    ),
    # Actions
    "play": _svg('<polygon points="5 3 19 12 5 21 5 3"/>'),
    "pause": _svg('<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>'),
    "stop": _svg('<rect x="5" y="5" width="14" height="14" rx="2"/>'),
    "refresh": _svg(
        '<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>'
        '<path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>'
    ),
    "copy": _svg(
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    ),
    "trash": _svg(
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    # Navigation
    "search": _svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'),
    "chevron-right": _svg('<polyline points="9 18 15 12 9 6"/>'),
    "chevron-down": _svg('<polyline points="6 9 12 15 18 9"/>'),
    "x": _svg('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'),
    "arrow-right": _svg('<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>'),
    "home": _svg(
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><polyline points="9 22 9 12 15 12 15 22"/>'
    ),
    # Status / Feedback
    "check": _svg('<polyline points="20 6 9 17 4 12"/>'),
    "check-circle": _svg('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'),
    "alert-triangle": _svg(
        '<path d="m10.29 3.86-8.14 14a2 2 0 0 0 1.71 3h16.3a2 2 0 0 0 1.71-3l-8.14-14a2 2 0 0 0-3.44 0Z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="0.5"/>'
    ),
    "info": _svg(
        '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
    ),
    # Tools / Config
    "settings": _svg(
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "sliders": _svg(
        '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
        '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
        '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="17" y1="16" x2="23" y2="16"/>'
    ),
    "moon": _svg('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/>'),
    "sun": _svg(
        '<circle cx="12" cy="12" r="4"/>'
        '<line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/>'
        '<line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/>'
        '<line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/>'
        '<line x1="4.93" y1="19.07" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.07" y2="4.93"/>'
    ),
    "command": _svg(
        '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3Z"/>'
    ),
    "keyboard": _svg(
        '<rect x="2" y="4" width="20" height="16" rx="2"/>'
        '<path d="M6 8h.01"/><path d="M10 8h.01"/><path d="M14 8h.01"/><path d="M18 8h.01"/>'
        '<path d="M6 12h.01"/><path d="M10 12h.01"/><path d="M14 12h.01"/><path d="M18 12h.01"/>'
        '<path d="M7 16h10"/>'
    ),
    # Extended set (P1.3 / U8..U11)
    "plus": _svg('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'),
    "minus": _svg('<line x1="5" y1="12" x2="19" y2="12"/>'),
    "edit": _svg(
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5Z"/>'
    ),
    "layers": _svg(
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>'
    ),
    "target": _svg('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'),
    "activity": _svg('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'),
    "line-chart": _svg('<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>'),
    "inbox": _svg(
        '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>'
    ),
    "loader": _svg(
        '<line x1="12" y1="2" x2="12" y2="6"/>'
        '<line x1="12" y1="18" x2="12" y2="22"/>'
        '<line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>'
        '<line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>'
        '<line x1="2" y1="12" x2="6" y2="12"/>'
        '<line x1="18" y1="12" x2="22" y2="12"/>'
        '<line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>'
        '<line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>'
    ),
    "circle": _svg('<circle cx="12" cy="12" r="10"/>'),
    "square": _svg('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>'),
    "sparkles": _svg(
        '<path d="M12 3 14 9 20 12 14 15 12 21 10 15 4 12 10 9 Z"/>'
        '<path d="M5 3v4"/><path d="M3 5h4"/>'
        '<path d="M19 17v4"/><path d="M17 19h4"/>'
    ),
    "trash-2": _svg(
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    "refresh-ccw": _svg(
        '<path d="M3 2v6h6"/>'
        '<path d="M21 12A9 9 0 0 0 6 5.3L3 8"/>'
        '<path d="M21 22v-6h-6"/>'
        '<path d="M3 12a9 9 0 0 0 15 6.7l3-2.7"/>'
    ),
    "file-text": _svg(
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/>'
        '<polyline points="10 9 9 9 8 9"/>'
    ),
    "table": _svg(
        '<path d="M3 3h18v18H3Z"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>'
    ),
    "book-open": _svg(
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2Z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7Z"/>'
    ),
}


# =============================================================================
# Helpers
# =============================================================================


def available_icon_names() -> list[str]:
    """Return the sorted list of registered icon names."""
    return sorted(ICON_SVG_SOURCES)


def _resolve_color(color: str | None) -> str:
    """Return a concrete ``#RRGGBB`` string. Defaults to theme foreground."""
    if color:
        return color
    try:
        # Late import: keeps this module importable without PyQt.
        from certus.ui.certus_ui import CertusTheme  # type: ignore[import]

        return CertusTheme.TEXT_MAIN
    except (ImportError, AttributeError):  # pragma: no cover - defensive
        return "#212529"


@lru_cache(maxsize=512)
def _render_icon(name: str, color: str, size: int):
    """Render an SVG icon to a ``QIcon`` (cached)."""
    # Late import so this module can be unit-tested without PyQt installed.
    from PyQt6.QtCore import QByteArray, QSize, Qt
    from PyQt6.QtGui import QIcon, QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer

    if _qsvg_stack_known_unstable():
        return QIcon()

    if name not in ICON_SVG_SOURCES:
        # Return an empty but valid icon so callers never crash.
        return QIcon()

    svg = ICON_SVG_SOURCES[name].replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pm)


def certus_icon(name: str, color: str | None = None, size: int = 20):
    """Return a ``QIcon`` for ``name`` rendered in ``color`` at ``size`` px.

    - ``color``: any valid CSS/Qt color string (``"#0f62fe"``, ``"red"``).
      Defaults to the current theme foreground.
    - Invalid names return an empty ``QIcon`` (never raise), so UI code
      remains robust against icon-set evolution.
    """
    color = _resolve_color(color)
    return _render_icon(name, color, int(size))


def clear_icon_cache() -> None:
    """Invalidate the LRU cache (call after a theme switch)."""
    _render_icon.cache_clear()


__all__ = [
    "ICON_SVG_SOURCES",
    "available_icon_names",
    "certus_icon",
    "clear_icon_cache",
    "is_svg_icon_rendering_disabled",
]
