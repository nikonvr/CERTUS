"""Whether Qt's SVG widgets can be used, computed in one place.

It lives in the interface layer on purpose: finding out imports PyQt6.QtSvgWidgets, which
certus.core must never do (CLAUDE.md, section 8). Until 2026-09-28 the core computed it, and
importing certus.core.certus_core loaded QtWidgets, QtGui, QtSvg and QtSvgWidgets.
"""

from __future__ import annotations

import os


def check_svg_availability() -> bool:
    """Check SVG widget availability.

    Returns False if explicitly disabled or if PyQt6.QtSvgWidgets is missing.
    """
    # Respect manual override if requested
    o = os.environ.get("CERTUS_SVG_ICONS", "").strip().lower()
    if o in ("0", "false", "no", "off"):
        return False

    try:
        from PyQt6.QtSvgWidgets import QSvgWidget  # noqa: F401  # availability check

        return True

    except ImportError, ModuleNotFoundError:
        return False


SVG_AVAILABLE = check_svg_availability()
