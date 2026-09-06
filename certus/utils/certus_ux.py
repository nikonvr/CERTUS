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

    from certus.ui.certus_ui import apply_certus_theme
    from certus.utils.certus_ux import build_premium_overrides

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
    SUCCESS_BUTTON: Final[str] = "CertusSuccessBtn"
    FEATURED_BUTTON: Final[str] = "CertusFeaturedBtn"
    GHOST_BUTTON: Final[str] = "CertusGhostBtn"
    ICON_BUTTON: Final[str] = "CertusIconBtn"
    SUBTLE_TEXT: Final[str] = "CertusSubtle"
    KBD: Final[str] = "CertusKbd"
    DIVIDER: Final[str] = "CertusDivider"
    SEARCH_INPUT: Final[str] = "CertusSearch"


OBJ: Final[Objects] = Objects()


# =============================================================================
# Premium QSS overrides (_theme-aware, additive)
# =============================================================================


def _hex_with_alpha(hex_color: str, alpha_pct: int) -> str:
    """Return ``#RRGGBBAA`` from ``#RRGGBB`` + alpha percentage (0-100)."""
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return hex_color
    a = max(0, min(100, int(alpha_pct)))
    aa = f"{int(round(a * 255 / 100)):02x}"
    return f"#{c}{aa}"


def _darken_color(hex_color: str, factor: float = 0.1) -> str:
    """Darken a hex color by a given factor (0.0 to 1.0) without transparency."""
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return hex_color
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)

    r = max(0, min(255, int(r * (1.0 - factor))))
    g = max(0, min(255, int(g * (1.0 - factor))))
    b = max(0, min(255, int(b * (1.0 - factor))))

    return f"#{r:02x}{g:02x}{b:02x}"


def build_premium_overrides(_theme: str | None = None) -> str:
    """Build the premium QSS overrides string.

    Parameters
    ----------
    _theme:
        Unused argument kept for API symmetry with a future multi-_theme
        dispatcher. Today the overrides read colors live from
        :class:`CertusTheme`, so they stay correct after a _theme switch.

    Returns
    -------
    str
        A QSS fragment that can be appended (via ``overrides=``) to the
        legacy stylesheet returned by ``certus_ui.get_standard_stylesheet``.
    """
    # Lazy import to avoid a circular dep at module load time and to read
    # the *current* _theme palette at call time.
    from certus.ui.certus_ui import CertusTheme as T

    primary = T.PRIMARY
    primary_soft = _hex_with_alpha(primary, 18)
    primary_hover = _darken_color(primary, 0.08)
    primary_pressed = _darken_color(primary, 0.16)
    primary_stronger = _hex_with_alpha(primary, 36)
    success = T.SUCCESS
    success_hover = _darken_color(success, 0.08)
    success_pressed = _darken_color(success, 0.16)
    secondary = T.SECONDARY
    border = T.BORDER
    # Step 3.3 - border of a control whose OUTLINE IS the affordance (>= 3:1).
    # `border` stays the DECORATIVE token, and the fill of disabled controls.
    border_strong = getattr(T, "BORDER_STRONG", T.BORDER)
    surface = T.SURFACE

    # Step 3.1 - sizes routed to the scale. Only the pt values that land EXACTLY on a step
    # are routed, so this sheet comes out byte-identical; `11pt` and `9.5pt` below are
    # off-scale and are left alone rather than nudged, because rounding them would be a
    # rendering change dressed as a refactor.
    font_xs = T.FONT_SIZE_XS
    font_sm = T.FONT_SIZE_SM
    font_base = T.FONT_SIZE_BASE

    # Step 3.7 - glyphs for checked indicators, painted with QPainter and served by
    # PATH. Returns "" when the write fails or no QApplication exists; the property is
    # then OMITTED rather than emitted empty.
    from certus.utils.certus_qss_icons import glyph_path

    # The glyph sits ON the primary fill, so its colour is the on-primary label token --
    # not a literal white. In dark mode PRIMARY is a light blue and PRIMARY_TEXT is dark,
    # so a hardcoded white tick would have been nearly invisible exactly there.
    def _image_rule(glyph: str) -> str:
        path = glyph_path(glyph, T.PRIMARY_TEXT, 16)
        return f'image: url("{path}");' if path else ""
    surface_hover = T.SURFACE_HOVER
    text_main = T.TEXT_MAIN
    text_sub = T.TEXT_SUB
    danger = T.DANGER
    danger_hover = _darken_color(danger, 0.08)
    danger_pressed = _darken_color(danger, 0.16)

    r_sm = Radius.SM
    r_md = Radius.MD
    r_lg = Radius.LG
    sp_sm = Spacing.SM
    sp_md = Spacing.MD
    sp_lg = Spacing.LG

    return f"""
/* ═══════════════════════════════════════════════════════════════════════
 * CERTUS UX premium overrides (U1) — additive, opt-in, _theme-aware.
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

/* -- Focus ring on BUTTONS (step 3.6) ----------------------------------
 * Measured 2026-09-06: before this block there was NOT ONE :focus rule on a
 * button, in either QSS layer. A keyboard user could not see where focus was.
 *
 * THE RING COLOUR DIFFERS PER FAMILY, and that is not decoration -- no single
 * colour clears 3:1 in both themes. Measured with certus_a11y.contrast_ratio:
 *
 *   default button   ring {{primary}} against SURFACE   5.00:1 light  6.98:1 dark
 *   filled variants  ring {{surface}} against the fill  4.83:1 .. 9.29:1 both
 *
 * Two candidates were measured and REJECTED: a {{primary}} ring vanishes on a
 * PRIMARY fill (1:1), and a {{text_main}} ring falls to 1.56:1 on SUCCESS in
 * dark mode -- because dark-mode text is light and so are the dark-mode fills.
 *
 * On a filled button the ring reads as an inset gap biting into the fill; it is
 * perceived against the fill, which is the pair measured above.
 *
 * 🔑 PADDING IS COMPENSATED so that taking focus NEVER reflows the layout. The
 * border grows by 1px (default, which already had 1px) or 2px (variants, which
 * declare `border: none`); the padding shrinks by exactly as much, so the outer
 * size is unchanged. A focus ring that moved its neighbours would be worse than
 * no focus ring at all.
 *
 * QToolButton is deliberately OUT OF SCOPE: this sheet sets it no padding, so
 * there is nothing to compensate against, and the chrome ones already carry
 * NoFocus. Giving them a ring is a separate change with its own measurement.
 */
QPushButton:focus {{
    border: 2px solid {primary};
    padding: {sp_sm - 1}px {sp_lg - 1}px;
}}

QPushButton#{OBJ.PRIMARY_BUTTON}:focus,
QPushButton#{OBJ.DANGER_BUTTON}:focus,
QPushButton#{OBJ.SUCCESS_BUTTON}:focus {{
    border: 2px solid {surface};
    padding: {sp_sm - 2}px {sp_lg - 2}px;
}}

QPushButton#{OBJ.FEATURED_BUTTON}:focus {{
    border: 2px solid {surface};
    padding: {sp_sm}px {sp_lg * 1.5 - 2}px;
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

/* -- Default QPushButton style (global fallback for entire suite) ------ */
/* Step 3.3 — border at >= 3:1. On a flat button with no fill, the outline is the
 * ONLY thing that says this is a button. The fill of that same button when
 * DISABLED stays on the softer `border`, and that is deliberate: WCAG exempts
 * disabled elements, and an inactive control must stay recessive. */
QPushButton {{
    background-color: {surface};
    color: {text_main};
    border: 1px solid {border_strong};
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 500;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {surface_hover};
    border-color: {primary};
}}
QPushButton:pressed {{
    background-color: {border};
}}
QPushButton:disabled {{
    background-color: {surface};
    color: {text_sub};
    border-color: {border};
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
    background-color: {primary_hover};
}}
QPushButton#{OBJ.PRIMARY_BUTTON}:pressed {{
    background-color: {primary_pressed};
    padding-top: {sp_sm + 1}px;
}}
QPushButton#{OBJ.PRIMARY_BUTTON}:disabled {{
    background-color: {border};
    color: {text_sub};
}}

/* -- Danger button (opt-in) -------------------------------------------- */
QPushButton#{OBJ.DANGER_BUTTON} {{
    background-color: {danger};
    color: #ffffff;
    border: none;
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton#{OBJ.DANGER_BUTTON}:hover {{
    background-color: {danger_hover};
}}
QPushButton#{OBJ.DANGER_BUTTON}:pressed {{
    background-color: {danger_pressed};
    padding-top: {sp_sm + 1}px;
}}
QPushButton#{OBJ.DANGER_BUTTON}:disabled {{
    background-color: {border};
    color: {text_sub};
}}

/* -- Success button (opt-in) ------------------------------------------- */
QPushButton#{OBJ.SUCCESS_BUTTON} {{
    background-color: {success};
    color: #ffffff;
    border: none;
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton#{OBJ.SUCCESS_BUTTON}:hover {{
    background-color: {success_hover};
}}
QPushButton#{OBJ.SUCCESS_BUTTON}:pressed {{
    background-color: {success_pressed};
    padding-top: {sp_sm + 1}px;
}}
QPushButton#{OBJ.SUCCESS_BUTTON}:disabled {{
    background-color: {border};
    color: {text_sub};
}}

/* -- Featured button (opt-in) ------------------------------------------ */
QPushButton#{OBJ.FEATURED_BUTTON} {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {primary}, stop:1 #2563eb);
    color: #ffffff;
    border: none;
    border-radius: {r_md}px;
    padding: {sp_sm + 2}px {sp_lg * 1.5}px;
    font-weight: 700;
    min-height: 32px;
}}
QPushButton#{OBJ.FEATURED_BUTTON}:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 {secondary});
    border: 1px solid #bfdbfe;
}}
QPushButton#{OBJ.FEATURED_BUTTON}:pressed {{
    background: {secondary};
    padding-top: {sp_sm + 3}px;
}}
QPushButton#{OBJ.FEATURED_BUTTON}:disabled {{
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
    font-size: {font_sm}pt;
}}

/* -- Keyboard key indicator (Ctrl+K, Esc, ...) ------------------------- */
QLabel#{OBJ.KBD} {{
    background-color: {surface_hover};
    color: {text_sub};
    border: 1px solid {border};
    border-radius: {r_sm}px;
    padding: 1px 6px;
    font-family: {Typography.FAMILY_MONO};
    font-size: {font_xs}pt;
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
QScrollBar::handle:vertical:pressed {{
    background: {primary};
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
QScrollBar::handle:horizontal:pressed {{
    background: {primary};
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
    font-size: {font_sm}pt;
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

/* -- Input Fields (Unified, modern layout) ---------------------------- */
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QTextEdit,
QPlainTextEdit {{
    background-color: {surface};
    color: {text_main};
    border: 1px solid {border};
    border-radius: {r_sm}px;
    padding: 5px 8px;
    font-family: {Typography.FAMILY_UI};
    font-size: {font_base}pt;
}}

/* -- Modern Tabs (Flat clean design) ---------------------------------- */
QTabWidget::pane {{
    border: 1px solid {border};
    background-color: {surface};
    border-radius: {r_md}px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {text_sub};
    border: 1px solid transparent;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 500;
    font-size: 9.5pt;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
}}
QTabBar::tab:hover {{
    color: {primary};
    background: {surface_hover};
    border-radius: {r_sm}px;
}}
QTabBar::tab:selected {{
    color: {primary};
    border-bottom: 2px solid {primary};
    font-weight: 600;
}}

/* -- Group boxes (Modern clean panels) --------------------------------- */
QGroupBox {{
    border: 1px solid {border};
    border-radius: {r_md}px;
    margin-top: 20px;
    padding-top: {sp_md}px;
    font-weight: 600;
    color: {text_main};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 {sp_sm}px;
    left: {sp_md}px;
}}

/* -- Table views ------------------------------------------------------- */
QTableView {{
    background-color: {surface};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: {r_md}px;
}}
QTableCornerButton::section {{
    background-color: {surface_hover};
    border: none;
}}

/* -- Checkboxes and Radio Buttons ------------------------------------- */
QCheckBox, QRadioButton {{
    spacing: 8px;
    font-size: 9.5pt;
    color: {text_main};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    background-color: {surface};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {primary};
    background-color: {surface_hover};
}}
/* -- Step 3.7 — the two rules below carried an SVG data-URL, and they NEVER displayed
 * anything. Measured at the pixel on 2026-09-06: a checked box rendered as a flat fill
 * of the primary colour, without a single pixel of tick, so the checked state rested on
 * hue alone — a WCAG 1.4.1 failure, on a stylesheet that looked correct.
 *
 * Cause isolated by experiment, not guessed:
 *     SVG data-URL    36 light px in the indicator   (background noise)
 *     PNG data-URL    36                             (identical)
 *     PNG as a FILE   76                             (the glyph appears)
 * Qt does not resolve data URLs inside a QSS `url()`.
 *
 * ⚠️ This is NOT the QtSvg instability guarded by `is_svg_icon_rendering_disabled()`:
 * the process survived every trial. Two distinct defects share one symptom.
 *
 * The glyphs are now painted with QPainter — no SVG anywhere on this path — and written
 * once to the temp directory. If the write fails, `glyph_path` returns an empty string
 * and the `image` property is OMITTED: an `image: url("")` would hide the native glyph
 * Qt would otherwise draw, which is worse than having no rule at all. */
QCheckBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
    {_image_rule("check")}
}}
QRadioButton::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
    {_image_rule("dot")}
}}

/* -- Sliders (QSlider) ------------------------------------------------- */
QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background: {border};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {primary};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {surface};
    border: 1px solid {border};
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    border-color: {primary};
    background-color: {surface_hover};
}}

/* -- Empty State Call-to-Action ---------------------------------------- */
QPushButton#empty-cta {{
    background-color: {primary};
    color: #ffffff;
    border: none;
    border-radius: {r_md}px;
    padding: {sp_sm}px {sp_lg}px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton#empty-cta:hover {{
    background-color: {primary_hover};
}}
QPushButton#empty-cta:pressed {{
    background-color: {primary_pressed};
    padding-top: {sp_sm + 1}px;
}}

/* -- Modern Tooltips (Tailwind style) --------------------------------- */
QToolTip {{
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    font-family: {Typography.FAMILY_UI};
    font-size: {font_sm}pt;
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
