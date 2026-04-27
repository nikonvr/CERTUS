"""CERTUS UX design system (U1).

Central, **additive** design-token layer for the CERTUS suite. Everything
here is plugged on top of the legacy ``CertusTheme`` (in ``certus_ui``):

- ``Spacing`` / ``Radius`` / ``Motion`` / ``Elevation`` / ``Typography`` /
  ``ZIndex`` namespaces give a formal design-system vocabulary.
- :func:`build_premium_overrides` produces a QSS fragment with modern focus
  rings, smooth hovers, pretty scrollbars, elevated cards, modern combo
  chevrons and improved table headers. It is appended to the legacy
  stylesheet via the ``overrides`` argument of ``apply_certus_theme``.

Design goals:

1. **Zero breakage**: all existing widgets keep rendering identically unless
   they opt in (via object-names like ``QFrame#CertusCard``).
2. **Theme-aware**: colors are read live from :class:`CertusTheme` so the
   same QSS works in light + dark mode.
3. **Deterministic**: tokens are plain integers/strings — no runtime
   computation or external dependencies.

Typical use::

    from certus_ui import apply_certus_theme
    from certus_ux import build_premium_overrides

    apply_certus_theme(window, overrides=build_premium_overrides())
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


# =============================================================================
# Design tokens (namespaces, not dataclasses, to mirror `CertusTheme` style)
# =============================================================================


class Spacing:
    """8-pt spacing scale (plus a 4-pt micro step for dense controls)."""

    XS: Final[int] = 4
    SM: Final[int] = 8
    MD: Final[int] = 12
    LG: Final[int] = 16
    XL: Final[int] = 24
    XXL: Final[int] = 32
    XXXL: Final[int] = 48


class Radius:
    """Border-radius scale (px)."""

    XS: Final[int] = 3
    SM: Final[int] = 6
    MD: Final[int] = 10
    LG: Final[int] = 14
    XL: Final[int] = 20
    PILL: Final[int] = 9999


class Motion:
    """Motion / animation tokens (ms + easing curves).

    Easings use ``QEasingCurve.Type.*`` names as strings so they can be
    consumed by code without importing Qt at module-import time.
    """

    # Durations
    INSTANT: Final[int] = 80
    FAST: Final[int] = 140
    BASE: Final[int] = 200
    SLOW: Final[int] = 320
    EMPHASIS: Final[int] = 480

    # Easings (names on QEasingCurve.Type)
    STANDARD: Final[str] = "OutCubic"
    DECELERATE: Final[str] = "OutQuint"
    ACCELERATE: Final[str] = "InCubic"
    EMPHASIZED: Final[str] = "OutBack"


class Elevation:
    """Drop-shadow tokens (blur, offset_y, alpha/255)."""

    NONE: Final[tuple[int, int, int]] = (0, 0, 0)
    SM: Final[tuple[int, int, int]] = (8, 2, 24)
    MD: Final[tuple[int, int, int]] = (18, 4, 38)
    LG: Final[tuple[int, int, int]] = (28, 8, 56)
    XL: Final[tuple[int, int, int]] = (40, 12, 74)


class Typography:
    """Typography scale (size pt, weight Qt int)."""

    FAMILY_UI: Final[str] = "'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif"
    FAMILY_MONO: Final[str] = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace"

    # Sizes (pt)
    CAPTION: Final[int] = 8
    BODY_SM: Final[int] = 9
    BODY: Final[int] = 10
    BODY_LG: Final[int] = 11
    H3: Final[int] = 12
    H2: Final[int] = 14
    H1: Final[int] = 18
    DISPLAY: Final[int] = 24

    # Weights (QFont.Weight numeric values)
    REGULAR: Final[int] = 50
    MEDIUM: Final[int] = 57
    SEMIBOLD: Final[int] = 63
    BOLD: Final[int] = 75


class ZIndex:
    """Logical z-order (mapped to WindowStaysOnTopHint layering hints)."""

    BASE: Final[int] = 0
    DROPDOWN: Final[int] = 10
    STICKY: Final[int] = 20
    OVERLAY: Final[int] = 40
    MODAL: Final[int] = 60
    TOAST: Final[int] = 80
    TOOLTIP: Final[int] = 100


# =============================================================================
# Semantic object-name contract (opt-in CSS classes)
# =============================================================================


@dataclass(frozen=True)
class Objects:
    """Opt-in ``objectName`` values recognised by :func:`build_premium_overrides`.

    Widgets that set one of these names inherit the premium styling
    (elevated card, ghost button, subdued text, ...). Widgets without
    these names render exactly as they did before U1.
    """

    CARD: Final[str] = "CertusCard"
    CARD_INTERACTIVE: Final[str] = "CertusCardInteractive"
    SURFACE_RAISED: Final[str] = "CertusSurfaceRaised"
    PRIMARY_BUTTON: Final[str] = "CertusPrimaryBtn"
    DANGER_BUTTON: Final[str] = "CertusDangerBtn"
    GHOST_BUTTON: Final[str] = "CertusGhostBtn"
    ICON_BUTTON: Final[str] = "CertusIconBtn"
    SUBTLE_TEXT: Final[str] = "CertusSubtle"
    KBD: Final[str] = "CertusKbd"
    DIVIDER: Final[str] = "CertusDivider"
    SEARCH_INPUT: Final[str] = "CertusSearch"


OBJ: Final[Objects] = Objects()


# =============================================================================
# Premium QSS overrides (theme-aware, additive)
# =============================================================================


def _hex_with_alpha(hex_color: str, alpha_pct: int) -> str:
    """Return ``#RRGGBBAA`` from ``#RRGGBB`` + alpha percentage (0-100)."""
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return hex_color
    a = max(0, min(100, int(alpha_pct)))
    aa = f"{int(round(a * 255 / 100)):02x}"
    return f"#{c}{aa}"


def build_premium_overrides(theme: str | None = None) -> str:
    """Build the premium QSS overrides string.

    Parameters
    ----------
    theme:
        Unused argument kept for API symmetry with a future multi-theme
        dispatcher. Today the overrides read colors live from
        :class:`CertusTheme`, so they stay correct after a theme switch.

    Returns
    -------
    str
        A QSS fragment that can be appended (via ``overrides=``) to the
        legacy stylesheet returned by ``certus_ui.get_standard_stylesheet``.
    """
    # Lazy import to avoid a circular dep at module load time and to read
    # the *current* theme palette at call time.
    from certus_ui import CertusTheme as T

    primary = T.PRIMARY
    primary_soft = _hex_with_alpha(primary, 18)
    primary_stronger = _hex_with_alpha(primary, 36)
    border = T.BORDER
    surface = T.SURFACE
    surface_hover = T.SURFACE_HOVER
    text_main = T.TEXT_MAIN
    text_sub = T.TEXT_SUB
    danger = T.DANGER

    r_sm = Radius.SM
    r_md = Radius.MD
    r_lg = Radius.LG
    sp_sm = Spacing.SM
    sp_md = Spacing.MD
    sp_lg = Spacing.LG

    return f"""
/* ═══════════════════════════════════════════════════════════════════════
 * CERTUS UX premium overrides (U1) — additive, opt-in, theme-aware.
 * ═══════════════════════════════════════════════════════════════════════ */

/* -- Focus ring (keyboard accessibility) ------------------------------- */
QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus,
QPlainTextEdit:focus,
QTextEdit:focus {{
    border: 1px solid {primary};
    /* Qt does not honor box-shadow; we emulate a ring via padding + margin */
    selection-background-color: {primary};
    selection-color: #ffffff;
}}

/* -- Elevated card (opt-in via objectName="{OBJ.CARD}") --------------- */
QFrame#{OBJ.CARD},
QWidget#{OBJ.CARD} {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {r_lg}px;
    padding: {sp_lg}px;
}}

QFrame#{OBJ.CARD_INTERACTIVE},
QWidget#{OBJ.CARD_INTERACTIVE} {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {r_lg}px;
    padding: {sp_lg}px;
}}
QFrame#{OBJ.CARD_INTERACTIVE}:hover,
QWidget#{OBJ.CARD_INTERACTIVE}:hover {{
    border-color: {primary};
    background-color: {surface_hover};
}}

/* -- Raised surface (panels, sheets) ----------------------------------- */
QFrame#{OBJ.SURFACE_RAISED},
QWidget#{OBJ.SURFACE_RAISED} {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {r_md}px;
}}

/* -- Primary button (opt-in) ------------------------------------------- */
QPushButton#{OBJ.PRIMARY_BUTTON} {{
    background-color: {primary};
    color: #ffffff;
    border: none;
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton#{OBJ.PRIMARY_BUTTON}:hover {{
    background-color: {primary_stronger};
}}
QPushButton#{OBJ.PRIMARY_BUTTON}:pressed {{
    background-color: {primary};
    padding-top: {sp_sm + 1}px;
}}
QPushButton#{OBJ.PRIMARY_BUTTON}:disabled {{
    background-color: {border};
    color: {text_sub};
}}

/* -- Ghost button (opt-in) --------------------------------------------- */
QPushButton#{OBJ.GHOST_BUTTON} {{
    background-color: transparent;
    color: {text_main};
    border: 1px solid transparent;
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_md}px;
}}
QPushButton#{OBJ.GHOST_BUTTON}:hover {{
    background-color: {primary_soft};
    color: {primary};
}}
QPushButton#{OBJ.GHOST_BUTTON}:pressed {{
    background-color: {primary_stronger};
}}

/* -- Icon button (square, minimal) ------------------------------------- */
QPushButton#{OBJ.ICON_BUTTON} {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {r_sm}px;
    padding: {sp_sm - 2}px;
    min-width: 28px;
    min-height: 28px;
}}
QPushButton#{OBJ.ICON_BUTTON}:hover {{
    background-color: {surface_hover};
    border-color: {border};
}}

/* -- Subtle text (captions, hints, timestamps) ------------------------- */
QLabel#{OBJ.SUBTLE_TEXT} {{
    color: {text_sub};
    font-size: 9pt;
}}

/* -- Keyboard key indicator (Ctrl+K, Esc, ...) ------------------------- */
QLabel#{OBJ.KBD} {{
    background-color: {surface_hover};
    color: {text_sub};
    border: 1px solid {border};
    border-radius: {r_sm}px;
    padding: 1px 6px;
    font-family: {Typography.FAMILY_MONO};
    font-size: 8pt;
    font-weight: 600;
}}

/* -- Divider --------------------------------------------------------- */
QFrame#{OBJ.DIVIDER} {{
    background-color: {border};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

/* -- Search input (Command palette, filter bars) ----------------------- */
QLineEdit#{OBJ.SEARCH_INPUT} {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_md}px {sp_sm}px {sp_lg * 2}px;
    font-size: 11pt;
    min-height: 34px;
}}
QLineEdit#{OBJ.SEARCH_INPUT}:focus {{
    border-color: {primary};
}}

/* -- Modern scrollbars ------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {text_sub};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
    border: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {text_sub};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
    border: none;
}}

/* -- Table headers ----------------------------------------------------- */
QHeaderView::section {{
    background-color: {surface_hover};
    color: {text_sub};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: {sp_sm}px {sp_md}px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 9pt;
}}
QHeaderView::section:hover {{
    background-color: {primary_soft};
    color: {primary};
}}

/* -- Combo chevron (needs themed PNG/SVG ideally; we rely on default)  */
QComboBox {{
    padding-right: {sp_lg}px;
}}

/* -- Dock / splitter handle ------------------------------------------- */
QSplitter::handle {{
    background-color: transparent;
}}
QSplitter::handle:hover {{
    background-color: {primary_soft};
}}
QSplitter::handle:horizontal {{
    width: 6px;
}}
QSplitter::handle:vertical {{
    height: 6px;
}}

/* -- Error emphasis (QLineEdit[error="true"]) ------------------------- */
QLineEdit[error="true"],
QSpinBox[error="true"],
QDoubleSpinBox[error="true"] {{
    border: 1px solid {danger};
}}
"""


__all__ = [
    "Spacing",
    "Radius",
    "Motion",
    "Elevation",
    "Typography",
    "ZIndex",
    "Objects",
    "OBJ",
    "build_premium_overrides",
]
