"""Small raster glyphs for QSS ``image:`` properties — step 3.7.

WHY THIS MODULE EXISTS, AND IT IS NOT THE REASON THE STEP GAVE.

``certus_ux.py`` already declared a checkmark and a radio dot for checked indicators, as
inline SVG data URLs. Measured 2026-09-06, at the pixel: a checked ``QCheckBox`` renders as
**284 px of the flat PRIMARY fill with no glyph at all**.

⚠️ That fill colour is deliberately named rather than quoted here. ``test_ux_design_system``
counts hex literals with a plain regex over the file text, so a colour written in a docstring
is counted exactly like one written in code — writing the artefact you are describing trips
the ratchet you are trying to respect.

The cause was isolated by experiment rather than guessed:

    SVG data-URL (what the sheet had)   36 light px inside the indicator   (background noise)
    PNG data-URL (same image, raster)   36                                 (identical)
    PNG written to a FILE               76                                 (the glyph appears)

**Qt's QSS ``url()`` does not resolve data URLs.** Both encodings render nothing; a real path
renders. So the checkmark and the radio dot had *never* worked, and the checked state was
signalled by colour alone — a WCAG 1.4.1 failure that looked fixed in the source.

⚠️ It is NOT the QtSvg instability that ``certus_icons.is_svg_icon_rendering_disabled()``
guards against: the process survived every trial. Two different defects share one symptom,
which is exactly why the experiment separated them before the fix was written.

These glyphs are therefore painted with ``QPainter`` — no SVG anywhere on this path, so the
known ``QSvgRenderer`` abort on Windows + CPython 3.14 cannot reach it — and written once to
a temp file, following the cache convention already used for the fonts and the numba cache
(``tempfile.gettempdir() / "certus_*"``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tempfile

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

#: Same convention as the numba cache and the font cache.
CACHE_DIR = Path(tempfile.gettempdir()) / "certus_qss_icons"

#: Painted at 4x then downscaled. Qt draws no sub-pixel strokes at 16 px, and a checkmark
#: one pixel wide reads as a smudge rather than as a tick.
_SUPERSAMPLE = 4


def _cache_path(name: str, color: str, size: int) -> Path:
    return CACHE_DIR / f"{name}_{color.lstrip('#').lower()}_{size}.png"


def _set_pen(painter: QPainter, color: str, width: float) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)


def _new_canvas(size: int) -> tuple[QPixmap, QPainter, int]:
    n = size * _SUPERSAMPLE
    pixmap = QPixmap(n, n)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pixmap, painter, n


def _downscale(pixmap: QPixmap, size: int) -> QPixmap:
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _paint_check(size: int, color: str) -> QPixmap:
    pixmap, painter, n = _new_canvas(size)
    _set_pen(painter, color, n * 0.14)
    # Proportions of a tick that stays legible at 16 px: short left leg, long right leg.
    painter.drawPolyline(
        QPointF(n * 0.24, n * 0.52), QPointF(n * 0.43, n * 0.71), QPointF(n * 0.77, n * 0.31)
    )
    painter.end()
    return _downscale(pixmap, size)


def _paint_dot(size: int, color: str) -> QPixmap:
    pixmap, painter, n = _new_canvas(size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    radius = n * 0.22
    painter.drawEllipse(QPointF(n / 2, n / 2), radius, radius)
    painter.end()
    return _downscale(pixmap, size)


_PAINTERS = {"check": _paint_check, "dot": _paint_dot}


@lru_cache(maxsize=32)
def glyph_path(name: str, color: str, size: int = 16) -> str:
    """Path to a PNG glyph, ready to drop into a QSS ``url()``.

    Returns a **forward-slash** string: QSS reads a Windows backslash as an escape, so
    ``C:\\Users\\...`` is unusable there.

    Returns an empty string when the file cannot be written — full disk, read-only temp dir.
    🔑 The caller must then OMIT the ``image`` property rather than emit an empty one: an
    ``image: url("")`` would hide the native glyph Qt would otherwise have drawn, turning a
    degraded case into a worse one than having no rule at all.
    """
    painter = _PAINTERS.get(name)
    if painter is None:
        raise KeyError(f"unknown glyph {name!r} (known: {sorted(_PAINTERS)})")

    # QPixmap aborts the process when no QGuiApplication exists. A stylesheet builder may
    # legitimately run before the app is up (module import, a headless config dump), and a
    # missing tick is a far smaller problem than a dead process.
    from PyQt6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return ""

    target = _cache_path(name, color, size)
    if target.exists() and target.stat().st_size > 0:
        return target.as_posix()

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not painter(size, color).save(str(target), "PNG"):
            return ""
    except OSError:
        return ""
    return target.as_posix()


def clear_glyph_cache() -> None:
    """Forget memoised paths. Call after a theme switch."""
    glyph_path.cache_clear()
