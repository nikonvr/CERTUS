"""The ink drawn on a solid fill follows the fill, in both themes (audit v2, plan S6.4b).

📏 Measured 2026-10-01, on the pixels (the colour of the middle of a widget that is farthest from its dominant colour, against that
dominant colour), dark theme, threshold 4.5:1:

    stepper, active / done badge          2.54 / 1.92        toast info / success / error     2.54 / 1.92 / 2.77
    status badge, idle .. warning         1.5 to 2.26        (a fixed pastel fill under the theme's accent as ink)
    light theme, for the record           warning toast 3.17, error badge 3.95, success badge 4.42, idle badge 4.39

and, read in the style sheets by `scripts/audit_ux_certus.py` (`low_contrast_sheets`, every rule that declares an ink AND a fill),
32 pairs under 4.5:1 in the dark theme on nine windows: the selected item of every menu (white on the light PRIMARY, 2.54:1, in the
sheet of each window) and twenty buttons filled with SECONDARY and lettered `white` (2.56:1).

An ink is now a colour of the palette of its own, one per solid fill: `PRIMARY_TEXT`, `DANGER_LABEL` (by hand, before) and
`SUCCESS_LABEL`, `WARNING_LABEL`, `SECONDARY_LABEL`, `INFO_LABEL`, which `CertusTheme` DERIVES from the fill (`label_on`) each time it
writes the palette. A token follows the toggle with no call site to repaint. A literal white on a fill of the palette is what a
static scan now refuses.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_theme import _DERIVED_LABELS, _TOKEN_NAMES, CertusTheme, _Token
from scripts.audit_ux_certus import declared_colour, low_contrast_sheets, sheet_contrast_pairs

ROOT = Path(__file__).resolve().parents[2]
MINIMUM = 4.5

#: (fill, the ink that is drawn on it), both NAMES of colours of the palette.
FILL_INK = [
    ("PRIMARY", "PRIMARY_TEXT"),
    ("DANGER", "DANGER_LABEL"),
    ("SUCCESS", "SUCCESS_LABEL"),
    ("WARNING", "WARNING_LABEL"),
    ("SECONDARY", "SECONDARY_LABEL"),
    ("INFO", "INFO_LABEL"),
]


@pytest.fixture(autouse=True)
def light_palette():
    """Every test starts and ends in the light palette: `CertusTheme` is a class, its palette is process state."""
    CertusTheme.configure("light")
    yield
    CertusTheme.configure("light")


# =============================================================================
# The inks of the palette


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize(("fill", "ink"), FILL_INK)
def test_each_ink_reads_on_its_fill_in_both_themes(mode, fill, ink):
    CertusTheme.configure(mode)
    ratio = contrast_ratio(str(getattr(CertusTheme, ink)), str(getattr(CertusTheme, fill)))
    assert ratio >= MINIMUM, f"{ink} on {fill}, {mode}: {ratio:.2f}:1"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_derived_inks_are_the_ink_label_on_gives_for_their_fill(mode):
    CertusTheme.configure(mode)
    assert [ink for _fill, ink in _DERIVED_LABELS] == ["SUCCESS_LABEL", "WARNING_LABEL", "SECONDARY_LABEL", "INFO_LABEL"]
    for fill, ink in _DERIVED_LABELS:
        assert str(getattr(CertusTheme, ink)) == CertusTheme.label_on(str(getattr(CertusTheme, fill))), (fill, ink, mode)


def test_the_two_inks_that_were_set_by_hand_are_what_the_derivation_gives_too():
    for mode in ("light", "dark"):
        CertusTheme.configure(mode)
        assert str(CertusTheme.PRIMARY_TEXT) == CertusTheme.label_on(str(CertusTheme.PRIMARY))
        assert str(CertusTheme.DANGER_LABEL) == CertusTheme.label_on(str(CertusTheme.DANGER))


def test_an_ink_is_a_token_with_its_own_name_and_changes_with_the_theme():
    for fill, ink in FILL_INK:
        token = getattr(CertusTheme, ink)
        assert isinstance(token, _Token) and token.name == ink and ink in _TOKEN_NAMES, (fill, ink)
    CertusTheme.configure("light")
    light = {ink: str(getattr(CertusTheme, ink)) for _f, ink in FILL_INK}
    CertusTheme.configure("dark")
    dark = {ink: str(getattr(CertusTheme, ink)) for _f, ink in FILL_INK}
    assert all(light[ink] != dark[ink] for ink in light), "an ink that does not change cannot read on both a light and a dark fill"


def test_an_ink_follows_its_fill_in_a_sheet_when_the_theme_changes(qapp):
    button = QPushButton("?")
    button.setStyleSheet(f"background: {CertusTheme.SECONDARY}; color: {CertusTheme.SECONDARY_LABEL};")
    assert button.styleSheet() == "background: #334155/*T:SECONDARY*/; color: #ffffff/*T:SECONDARY_LABEL*/;"
    CertusTheme.configure("dark")
    assert CertusTheme.refresh_widget_sheets() >= 1
    assert button.styleSheet() == "background: #94a3b8/*T:SECONDARY*/; color: #0f172a/*T:SECONDARY_LABEL*/;"


# =============================================================================
# What the pixels say


def contrast_of(image: QImage, inset: int = 6) -> float:
    """WCAG contrast of what an image shows: the dominant colour of its middle is the fill, the colour farthest from it the ink.

    Only the middle: the corners of a rounded badge are not its fill. Measured on pixels, so a label that no rule reaches is judged
    as it is drawn, not as the sheet says.
    """
    box = image.copy(QRect(inset, inset // 2, max(8, image.width() - 2 * inset), max(8, image.height() - inset)))
    counts = Counter(box.pixel(x, y) for y in range(box.height()) for x in range(box.width()))
    fill = QColor.fromRgb(counts.most_common(1)[0][0]).name()
    ink = max((QColor.fromRgb(p).name() for p in counts), key=lambda c: contrast_ratio(c, fill))
    return contrast_ratio(ink, fill)


def ink_contrast(widget: QWidget, inset: int = 6) -> float:
    widget.show()
    QApplication.processEvents()
    return contrast_of(widget.grab().toImage(), inset)


@pytest.fixture
def host(qapp, monkeypatch):
    """The widgets that draw an ink on a fill, in one window with a real toggle; the preference is kept in memory, never written."""
    from certus.core import certus_core
    from certus.ui import certus_ui_utils, certus_ui_widgets_utils
    from certus.ui.certus_ui_widgets_factory import create_help_button
    from certus.ui.certus_ui_widgets_layout import CertusStepper
    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle, CertusToast
    from certus.utils.certus_badges import _get_badge_cls, supported_variants

    state = {"mode": "light"}
    for module in (certus_core, certus_ui_utils, certus_ui_widgets_utils):
        if hasattr(module, "load_theme_config"):
            monkeypatch.setattr(module, "load_theme_config", lambda: state["mode"])
        if hasattr(module, "save_theme_config"):
            monkeypatch.setattr(module, "save_theme_config", lambda m: state.__setitem__("mode", m) or True)

    root = QWidget()
    root.resize(720, 420)
    toggle = CertusThemeToggle(root)
    stepper = CertusStepper(["Un", "Deux", "Trois"], parent=root)
    stepper.set_step(1)
    widgets: dict[str, QWidget] = {
        "stepper active": stepper._badges[1],
        "stepper done": stepper._badges[0],
        "stepper upcoming": stepper._badges[2],
    }
    for level in ("info", "success", "warning", "error"):
        widgets[f"toast {level}"] = CertusToast(root, "Message de test", level=level, duration_ms=10**9)
    badge_class = _get_badge_cls()
    for variant in supported_variants():
        widgets[f"badge {variant}"] = badge_class(root, text=variant, variant=variant, with_icon=False)
    help_button = create_help_button("CERTUS")
    help_button.setParent(root)
    widgets["help button"] = help_button
    icon_badge = badge_class(root, text="ok", variant="success", with_icon=True)
    root.show()
    QApplication.processEvents()
    try:
        yield widgets, toggle, state, icon_badge
    finally:
        root.close()
        CertusTheme.configure("light")


def _unreadable(widgets: dict[str, QWidget]) -> dict[str, float]:
    return {name: round(ratio, 2) for name, w in widgets.items() if (ratio := ink_contrast(w)) < MINIMUM}


def test_every_ink_on_a_fill_reads_in_the_light_theme_after_one_click_and_after_two(host, qapp):
    widgets, toggle, state, _icon = host
    assert len(widgets) >= 15
    assert _unreadable(widgets) == {}, "light, as built"
    toggle.toggle()
    qapp.processEvents()
    assert state["mode"] == "dark"
    assert _unreadable(widgets) == {}, "dark, after one click"
    toggle.toggle()
    qapp.processEvents()
    assert state["mode"] == "light"
    assert _unreadable(widgets) == {}, "light again, after two"


def test_the_pixel_measure_tells_a_readable_label_from_an_unreadable_one(qapp):
    """Negative control: with a measure that always passes, the test above would prove nothing."""
    bad, good = QLabel("Words"), QLabel("Words")
    bad.setStyleSheet("background: #60a5fa; color: #ffffff; font-size: 14pt; font-weight: bold;")
    good.setStyleSheet("background: #60a5fa; color: #0f172a; font-size: 14pt; font-weight: bold;")
    assert ink_contrast(bad, 4) == pytest.approx(2.54, abs=0.05)
    assert ink_contrast(good, 4) == pytest.approx(7.02, abs=0.05)


def test_the_icon_of_a_status_badge_is_asked_for_again_in_the_ink_of_the_new_palette(host, qapp, monkeypatch):
    """A sheet follows the theme by itself; an icon is a pixmap painted once, and `refresh_theme` paints it again.

    Asked, not measured: where the QtSvg stack is known unstable `certus_icon` returns an empty icon on purpose
    (`is_svg_icon_rendering_disabled`), so no pixel of an icon can be read there.
    """
    from certus.ui import certus_icons

    _widgets, toggle, _state, _icon_badge = host
    asked: list[str] = []
    real = certus_icons.certus_icon
    monkeypatch.setattr(certus_icons, "certus_icon", lambda name, color=None, size=20: asked.append(str(color)) or real(name, color, size))
    toggle.toggle()
    qapp.processEvents()
    assert asked == ["#60dc8f"], asked  # SUCCESS_TEXT of the dark palette: one badge with an icon, asked once, in the colour of today


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_selected_row_of_the_command_palette_reads(qapp, mode):
    from certus.utils.certus_command_palette import CommandAction, _build_palette_class

    CertusTheme.configure(mode)
    palette = _build_palette_class()(None, [CommandAction("file.open", "Open the file", lambda: None, category="File")])
    try:
        palette.resize(560, 360)
        palette.show()
        QApplication.processEvents()
        row = palette.list.visualItemRect(palette.list.item(0))
        assert palette.list.currentRow() == 0
        assert contrast_of(palette.list.viewport().grab(row).toImage(), 4) >= MINIMUM
    finally:
        palette.close()


# =============================================================================
# What the sheets say: the application's own, and the small factories


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_no_rule_of_the_application_sheet_pairs_an_ink_and_a_fill_under_the_threshold(qapp, mode):
    CertusTheme.configure(mode)
    CertusTheme.apply_to_app(qapp, mode == "dark")
    try:
        sheet = qapp.styleSheet()
        pairs = sheet_contrast_pairs(sheet)
        assert len(pairs) >= 4, "too few rules were read: the comparison below would prove little"
        weak = [(s, i, f, round(contrast_ratio(i, f), 2)) for s, i, f in pairs if i != f and contrast_ratio(i, f) < MINIMUM]
        assert weak == []
        assert not re.search(r"(?<![\w-])(?:selection-)?color\s*:\s*white", sheet)
        assert f"selection-color: {CertusTheme.PRIMARY_TEXT};" in sheet  # the f-string writes the token with its name
    finally:
        CertusTheme.configure("light")
        CertusTheme.apply_to_app(qapp, False)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_small_factories_pair_their_ink_with_their_fill_in_every_state(qapp, mode):
    from certus.ui.certus_ui_widgets_factory import create_help_button, create_info_icon

    CertusTheme.configure(mode)
    for button in (create_info_icon("Tip"), create_help_button("CERTUS")):
        pairs = sheet_contrast_pairs(button.styleSheet())
        assert pairs, "no rule with an ink and a fill was read"
        for selector, ink, fill in pairs:
            assert contrast_ratio(ink, fill) >= MINIMUM, (mode, selector, ink, fill)


@pytest.mark.parametrize("window", ["CERTUS_HUB", "CERTUS_INDEX", "CERTUS_METAL_SINGLE"])
def test_no_widget_sheet_of_a_window_pairs_an_ink_and_a_fill_under_the_threshold_before_or_after_a_click(window, qapp, monkeypatch):
    """The window sheet carries the selected item of the menu, the INDEX details button and the METAL help buttons carry white on SECONDARY."""
    from certus.core import certus_core
    from certus.ui import certus_ui_utils, certus_ui_widgets_utils
    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle
    from scripts.audit_ux_certus import MODULES

    state = {"mode": "light"}
    for module in (certus_core, certus_ui_utils, certus_ui_widgets_utils):
        if hasattr(module, "load_theme_config"):
            monkeypatch.setattr(module, "load_theme_config", lambda: state["mode"])
        if hasattr(module, "save_theme_config"):
            monkeypatch.setattr(module, "save_theme_config", lambda m: state.__setitem__("mode", m) or True)
    modname, clsname = MODULES[window]
    win = getattr(__import__(modname, fromlist=[clsname]), clsname)()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        assert low_contrast_sheets(win) == [], f"{window}, light"
        next(w for w in win.findChildren(QWidget) if isinstance(w, CertusThemeToggle)).toggle()
        qapp.processEvents()
        assert state["mode"] == "dark"
        assert low_contrast_sheets(win) == [], f"{window}, dark"
    finally:
        win.close()
        CertusTheme.configure("light")


# =============================================================================
# What the audit measures


def test_a_declared_colour_is_read_the_way_qt_reads_it(qapp):
    assert declared_colour("#0f62fe/*T:PRIMARY*/") == "#0f62fe"  # the comment of a token is white space
    assert declared_colour("white") == "#ffffff"
    assert declared_colour("#fff !important") == "#ffffff"
    assert declared_colour("rgba(15, 98, 254, 1)") == "#0f62fe"  # an alpha up to 1 is a fraction: opaque
    assert declared_colour("rgba(15, 98, 254, 0.18)") is None  # translucent: its colour depends on what is under it
    assert declared_colour("rgba(15, 98, 254, 128)") is None  # above 1 it is a byte
    assert declared_colour("rgba(10, 20, 30, 50%)") is None
    assert declared_colour("#80ff0000") is None  # eight digits are #aarrggbb: half transparent
    assert declared_colour("#ff0000ff") == "#0000ff"  # alpha ff, red 00, green 00, blue ff
    assert declared_colour("qlineargradient(x1:0, y1:0, stop:0 #fff, stop:1 #000)") is None
    assert declared_colour("transparent") is None
    assert declared_colour("not a colour") is None
    assert declared_colour("") is None


def test_a_rule_that_declares_an_ink_and_a_fill_is_a_pair_unless_it_is_disabled_or_a_tooltip(qapp):
    sheet = (
        "QPushButton { background: #ffffff/*T:SURFACE*/; color: #475569/*T:TEXT_SUB*/; }"
        "QPushButton:hover { background-color: #0f62fe; color: white; }"
        "QPushButton:disabled { background: #ffffff; color: #ffffff; }"
        "QToolTip { background: #111; color: #eee; }"
        "QLabel { color: #123456; }"
        "QFrame { background: qlineargradient(x1:0, stop:0 #fff, stop:1 #000); color: #fff; }"
    )
    assert sheet_contrast_pairs(sheet) == [
        ("QPushButton", "#475569", "#ffffff"),
        ("QPushButton:hover", "#ffffff", "#0f62fe"),
    ]
    assert sheet_contrast_pairs("background: #111111; color: #eeeeee;") == [("", "#eeeeee", "#111111")]  # a sheet without braces is one rule
    assert sheet_contrast_pairs("") == []
    assert sheet_contrast_pairs("color: red;") == []  # an ink alone is nothing to compare
    last_wins = "QLabel { color: #000000; background: #ffffff; color: #ffffff; }"
    assert sheet_contrast_pairs(last_wins) == [("QLabel", "#ffffff", "#ffffff")]
    unreadable_later = "QLabel { color: #000000; background: #ffffff; background: qlineargradient(x1:0, stop:0 #fff); }"
    assert sheet_contrast_pairs(unreadable_later) == []  # a declaration that is not read erases the one before it: only what is read is judged


def test_the_low_contrast_scan_walks_the_window_and_its_children_and_skips_a_one_colour_rule(qapp):
    window = QWidget()
    window.setStyleSheet("QPushButton { background: #60a5fa; color: #ffffff; }")
    child = QLabel("x", window)
    child.setObjectName("weak")
    child.setStyleSheet("background: #888888; color: #777777;")
    fine = QLabel("y", window)
    fine.setStyleSheet("background: #ffffff; color: #000000;")
    line = QLabel("", window)
    line.setStyleSheet("color: #d7dfe8; background: #d7dfe8;")  # a divider drawn with one colour
    found = low_contrast_sheets(window)
    assert len(found) == 2
    assert any(entry.startswith("QWidget|-|QPushButton|#ffffff sur #60a5fa = 2.54") for entry in found)
    assert any(entry.startswith("QLabel|weak||#777777 sur #888888 = 1.") for entry in found)
    assert low_contrast_sheets(window, minimum=1.0) == []


# =============================================================================
# The static scan: no literal white ink on a fill of the palette


LITERAL_WHITE_INK = re.compile(r"(?<![\w-])(?:selection-)?color\s*:\s*(?:white|#fff(?:fff)?)\b", re.IGNORECASE)
WHITE_ICON = re.compile(r"certus_icon\([^)]*color\s*=\s*[\"']#(?:fff|ffffff)[\"']", re.IGNORECASE)

#: The literal white inks that stay, each on a fill that is NOT a colour of the palette and is the same in both themes.
KEPT_WHITE_INKS = {
    "certus/ui/certus_hub_widgets.py": 1,  # the glyph on the square of a hub card, whose fill is the accent colour of its module
    "certus/ui/certus_manual_sigma_knot_dialog.py": 1,  # the overlay buttons of the knot dialog: a fixed dark rgba(30, 30, 30, 180)
    "certus/utils/certus_reset_framework.py": 1,  # the reset button: a fixed dark amber, #5a3a00
}


def test_the_white_ink_scanner_tells_an_ink_from_a_fill_or_a_token():
    """Negative control for the guard below."""
    assert len(LITERAL_WHITE_INK.findall("color: white;")) == 1
    assert len(LITERAL_WHITE_INK.findall("QPushButton { color:#FFF; }")) == 1
    assert len(LITERAL_WHITE_INK.findall("selection-color: #ffffff;")) == 1
    assert len(LITERAL_WHITE_INK.findall("background-color: white;")) == 0  # a fill
    assert len(LITERAL_WHITE_INK.findall("border-color: white;")) == 0
    assert len(LITERAL_WHITE_INK.findall("color: {CertusTheme.PRIMARY_TEXT};")) == 0
    assert len(LITERAL_WHITE_INK.findall("color: #ffffff80;")) == 0  # eight digits: not a white
    assert len(WHITE_ICON.findall('certus_icon("activity", color="#FFFFFF")')) == 1
    assert len(WHITE_ICON.findall('certus_icon("activity", color=CertusTheme.PRIMARY_TEXT)')) == 0


def test_no_style_sheet_of_the_interface_letters_a_fill_of_the_palette_with_a_literal_white():
    found: dict[str, int] = {}
    icons: list[str] = []
    for path in sorted([*ROOT.glob("CERTUS_*.py"), *(ROOT / "certus").rglob("*.py")]):
        text = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(ROOT).as_posix()
        if count := len(LITERAL_WHITE_INK.findall(text)):
            found[relative] = count
        icons += [relative for _ in WHITE_ICON.findall(text)]
    assert found == KEPT_WHITE_INKS, "a literal white ink appeared (or one of the kept ones went): write the ink of the fill, CertusTheme.PRIMARY_TEXT and its kin"
    assert icons == [], f"an icon painted white on a fill that is not white in the dark theme: {icons}"
