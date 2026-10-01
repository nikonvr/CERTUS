"""A click on the theme toggle reaches the style sheets of the widgets, not only the window's (audit v2, plan S6.4, UX-08).

A style sheet set on a widget is an f-string evaluated ONCE, while the widget is built. The toggle rebuilt the window's sheet and the
sheets of the components that know how to repaint themselves; every other widget kept the palette it was built with.

📏 Measured 2026-10-01, a light window then one click, counting the widget sheets that still hold a colour that only the light
palette uses (`scripts/audit_ux_certus.py`, `frozen_light_sheets`):

    HUB 12 of 60 · DESIGN 45 of 97 · STRAT 63 of 115 · RE 49 of 81 · INDEX 61 of 94 · INDEX SPLINE 105 of 171
    FIELD 47 of 86 · METAL 45 of 79 and 56 of 87             -- 483 sheets on nine windows

The value alone cannot be mapped back to its token (the same hex serves as text in one theme and as a fill in the other), so a colour
of the palette is a `_Token`: a plain string to everything, except an f-string, which writes it WITH its name,
`#ffffff/*T:SURFACE*/`. Qt reads the comment as white space (style sheets, gradients and the style attribute of rich text, tested
below), and `CertusTheme.refresh_widget_sheets` rewrites each sheet from the names. The style of a solid button is bounded by two
markers and built again from its variant: its label and its hover and pressed fills are DERIVED from its fill, so they are not tokens.

After: 0 on every window, with no call site changed.
"""

from __future__ import annotations

import json
import os
import pickle
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from certus.ui.certus_theme import _TOKEN_NAMES, CertusTheme, _Token


@pytest.fixture(autouse=True)
def light_palette():
    """Every test starts and ends in the light palette: `CertusTheme` is a class, its palette is process state."""
    CertusTheme.configure("light")
    yield
    CertusTheme.configure("light")


def _palette(mode: str) -> dict[str, str]:
    CertusTheme.configure(mode)
    return {n: str(v).lower() for n, v in vars(CertusTheme).items() if n.isupper() and isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}


# =============================================================================
# The token: a plain string to everything but an f-string


def test_a_colour_is_a_plain_string_to_everything_but_an_fstring():
    token = CertusTheme.SURFACE
    assert isinstance(token, _Token)
    assert token == "#ffffff"
    assert str(token) == "#ffffff" and type(str(token)) is str
    assert "%s" % token == "#ffffff"  # noqa: UP031 - the percent operator IS what is tested
    assert token + "22" == "#ffffff22"
    assert token.lstrip("#") == "ffffff"
    assert json.dumps({"c": token}) == '{"c": "#ffffff"}'
    assert hash(token) == hash("#ffffff")
    assert f"{token!s}" == "#ffffff"
    assert f"{token:>9}" == "  #ffffff"  # a format spec is a plain formatting request
    assert QColor(token).name() == "#ffffff"
    assert type(pickle.loads(pickle.dumps(token))) is str  # a worker process must not import Qt to read a colour


def test_an_fstring_writes_the_colour_with_its_name():
    assert f"{CertusTheme.SURFACE}" == "#ffffff/*T:SURFACE*/"
    assert f"color: {CertusTheme.TEXT_MAIN}; border: 1px solid {CertusTheme.BORDER};" == (
        "color: #0f172a/*T:TEXT_MAIN*/; border: 1px solid #d7dfe8/*T:BORDER*/;"
    )
    assert format(CertusTheme.PRIMARY) == "#0f62fe/*T:PRIMARY*/"  # `str.format` and `format` go through the same hook


def test_an_fstring_writes_the_colour_the_palette_has_now_even_for_a_token_kept_since_before():
    kept = CertusTheme.TEXT_SUB  # a default argument, an attribute of a widget
    CertusTheme.configure("dark")
    assert str(kept) == "#475569"  # the object is what it was
    assert f"{kept}" == f"{CertusTheme.TEXT_SUB}" == "#94a3b8/*T:TEXT_SUB*/"  # what it writes is today's colour


def test_every_colour_that_changes_with_the_theme_is_a_token_with_its_own_name():
    light, dark = _palette("light"), _palette("dark")
    CertusTheme.configure("light")
    changing = {name for name in light if name in dark and light[name] != dark[name]}
    assert changing, "no colour differs between the palettes: the comparison below would prove nothing"
    assert changing <= set(_TOKEN_NAMES), f"a colour of the palette is not a token: {sorted(changing - set(_TOKEN_NAMES))}"
    for name in _TOKEN_NAMES:
        token = getattr(CertusTheme, name)
        assert isinstance(token, _Token) and token.name == name


def test_the_tokens_stay_tokens_after_each_change_and_the_aliases_follow_their_target():
    for mode in ("dark", "light", "dark"):
        CertusTheme.configure(mode)
        assert isinstance(CertusTheme.PRIMARY, _Token)
        assert CertusTheme.ACCENT == CertusTheme.CHART_PRIMARY == CertusTheme.PRIMARY
        assert CertusTheme.ELEVATED == CertusTheme.SURFACE_HOVER
        assert CertusTheme.BASE_ELEVATED == CertusTheme.SURFACE
        assert all(isinstance(c, _Token) for c in CertusTheme.CHART_COLORS if c != CertusTheme.CHART_PURPLE)


def test_the_text_colour_that_is_the_same_in_both_themes_is_not_a_token():
    assert "TEXT" not in _TOKEN_NAMES
    assert not isinstance(CertusTheme.TEXT, _Token)


# =============================================================================
# Qt reads the comment as white space


def _grab(widget: QWidget, width: int = 160, height: int = 40):
    widget.resize(width, height)
    widget.show()
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()
    return widget.grab().toImage()


def test_qt_paints_an_annotated_sheet_like_a_plain_one(qapp):
    plain, noted = QLabel("x"), QLabel("x")
    plain.setStyleSheet("background: #ff0000; color: #00ff00;")
    noted.setStyleSheet("background: #ff0000/*T:SURFACE*/; color: #00ff00/*T:TEXT_MAIN*/;")
    for image in (_grab(plain), _grab(noted)):
        c = image.pixelColor(2, 2)
        assert (c.red(), c.green(), c.blue()) == (255, 0, 0)


def test_qt_reads_a_comment_in_a_border_in_a_gradient_and_in_a_rich_text_span(qapp):
    box = QLabel("")
    box.setStyleSheet("QLabel { border: 3px solid #0000ff/*T:BORDER*/; background: #ffffff/*T:SURFACE*/; }")
    image = _grab(box)
    assert image.pixelColor(1, 20).blue() == 255 and image.pixelColor(1, 20).red() == 0
    assert image.pixelColor(80, 20).red() == 255

    bar = QProgressBar()
    bar.setValue(100)
    bar.setTextVisible(False)
    bar.setStyleSheet(
        "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff0000/*T:PRIMARY*/, stop:1 #ff0000/*T:SECONDARY*/); }"
    )
    assert _grab(bar).pixelColor(80, 20).red() == 255

    rich = QLabel('<span style="color:#ff0000/*T:PRIMARY*/;"><b>XXXXXXXXXX</b></span>')
    rich.setStyleSheet("background: #ffffff;")
    image = _grab(rich, 200, 30)
    reds = sum(1 for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).red() > 200 > image.pixelColor(x, y).green() + 120)
    assert reds > 100


# =============================================================================
# The refresh


def test_a_sheet_built_with_tokens_takes_the_new_palette_and_keeps_its_names(qapp):
    label = QLabel("x")
    label.setStyleSheet(f"background: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
    original = label.styleSheet()
    CertusTheme.configure("dark")
    assert CertusTheme.refresh_widget_sheets() >= 1
    assert label.styleSheet() == "background: #111827/*T:SURFACE*/; color: #e2e8f0/*T:TEXT_MAIN*/; font-size: 11px;"
    CertusTheme.configure("light")
    assert CertusTheme.refresh_widget_sheets() >= 1
    assert label.styleSheet() == original  # the annotation survives: a second change works the same


def test_a_hard_coded_colour_and_a_sheet_without_colours_are_left_alone(qapp):
    fixed, bare = QLabel("x"), QLabel("y")
    fixed.setStyleSheet("background: #ffffff; color: #0f172a;")
    bare.setStyleSheet("font-size: 11px;")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert fixed.styleSheet() == "background: #ffffff; color: #0f172a;"
    assert bare.styleSheet() == "font-size: 11px;"


def test_only_the_widgets_that_changed_are_counted(qapp):
    noted, fixed = QLabel("a"), QLabel("b")
    noted.setStyleSheet(f"color: {CertusTheme.PRIMARY};")
    fixed.setStyleSheet("color: #ff0000;")
    before = CertusTheme.refresh_widget_sheets()  # nothing has changed yet: no widget is rewritten
    CertusTheme.configure("dark")
    after = CertusTheme.refresh_widget_sheets()
    assert after - before == 1


def test_a_solid_button_is_built_again_with_the_label_and_the_states_of_its_new_fill(qapp):
    button = QPushButton("Stop")
    button.setStyleSheet(CertusTheme.get_button_style("danger"))
    assert "color: #ffffff" in button.styleSheet()  # white on the light red
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    sheet = button.styleSheet()
    assert sheet == CertusTheme.get_button_style("danger")
    assert "background-color: #f87171/*T:DANGER*/" in sheet
    assert "color: #0f172a" in sheet  # the dark ink: white on #f87171 is 2.77:1, the failure of S6.1 that the toggle must not bring back


def test_a_button_whose_fill_is_a_colour_of_the_palette_follows_that_colour(qapp):
    button = QPushButton("Load")
    button.setStyleSheet(CertusTheme.get_button_style(CertusTheme.SECONDARY))
    assert "background-color: #334155/*T:SECONDARY*/" in button.styleSheet()
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert "background-color: #94a3b8/*T:SECONDARY*/" in button.styleSheet()
    assert button.styleSheet() == CertusTheme.get_button_style(CertusTheme.SECONDARY)


def test_a_button_whose_fill_is_any_other_colour_is_rebuilt_to_the_same_sheet(qapp):
    button = QPushButton("Custom")
    button.setStyleSheet(CertusTheme.get_button_style("#123456"))
    original = button.styleSheet()
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert "background-color: #123456" in button.styleSheet()
    assert button.styleSheet() == CertusTheme.get_button_style("#123456")
    assert original.startswith("/*B:#123456*/")


def test_a_button_style_inside_a_longer_sheet_is_rebuilt_in_place(qapp):
    widget = QWidget()
    widget.setStyleSheet("QLabel { margin: 3px; }" + CertusTheme.get_button_style("primary") + f"QWidget {{ color: {CertusTheme.TEXT_SUB}; }}")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    sheet = widget.styleSheet()
    assert sheet.startswith("QLabel { margin: 3px; }/*B:primary*/")
    assert "background-color: #60a5fa/*T:PRIMARY*/" in sheet
    assert sheet.endswith("QWidget { color: #94a3b8/*T:TEXT_SUB*/; }")


def test_a_button_style_still_has_the_rules_it_had_with_its_markers_around_them():
    sheet = CertusTheme.get_button_style("primary")
    assert sheet.startswith("/*B:primary*/") and sheet.rstrip().endswith("/*B-END*/")
    for rule in ("QPushButton {", "QPushButton:hover {", "QPushButton:pressed {", "QPushButton:focus {", "QPushButton:disabled {"):
        assert rule in sheet


def test_rich_text_that_spells_a_colour_follows_the_theme(qapp):
    label = QLabel(f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>ready</b></span>')
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert label.text() == 'Corridors: <span style="color:#60a5fa/*T:PRIMARY*/;"><b>ready</b></span>'


def test_a_plain_label_text_is_not_touched(qapp):
    label = QLabel("color: #0f62fe/*T:PRIMARY*/ is only words here")
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText("plain")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert label.text() == "plain"


def test_a_name_that_is_not_a_colour_of_the_palette_is_kept_as_written(qapp):
    """`TEXT` is an attribute of the class and a colour, but the same in both themes: it is not a token."""
    widget = QWidget()
    widget.setStyleSheet("color: #ff00ff/*T:NOT_A_TOKEN*/; background: #ff00ff/*T:TEXT*/;")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert widget.styleSheet() == "color: #ff00ff/*T:NOT_A_TOKEN*/; background: #ff00ff/*T:TEXT*/;"


def test_a_widget_that_repaints_itself_later_does_not_bring_the_old_palette_back(qapp):
    """`AutoShrinkTitleLabel` keeps its colour as an attribute and writes its sheet again on every resize."""
    from certus.ui.certus_ui_widgets_utils import AutoShrinkTitleLabel

    label = AutoShrinkTitleLabel("A title", color=CertusTheme.TEXT_SUB)
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    label._current_rendered_size = -1  # as if it had to shrink
    label._update_style(12)
    assert "#94a3b8/*T:TEXT_SUB*/" in label.styleSheet()


def test_the_tone_colour_of_the_overview_banner_is_the_token_itself(qapp):
    from certus.ui.certus_overview_tab import _tone_color

    assert isinstance(_tone_color("primary"), _Token)
    assert f"{_tone_color('primary')}" == "#0f62fe/*T:PRIMARY*/"


# =============================================================================
# The windows


@pytest.fixture
def light_window(request, qapp, monkeypatch):
    """A window built in LIGHT, with the preference kept in memory: nothing is written to the user's configuration."""
    from certus.core import certus_core
    from certus.ui import certus_ui_utils, certus_ui_widgets_utils
    from scripts.audit_ux_certus import MODULES

    state = {"mode": "light"}
    for module in (certus_core, certus_ui_utils, certus_ui_widgets_utils):
        if hasattr(module, "load_theme_config"):
            monkeypatch.setattr(module, "load_theme_config", lambda: state["mode"])
        if hasattr(module, "save_theme_config"):
            monkeypatch.setattr(module, "save_theme_config", lambda m: state.__setitem__("mode", m) or True)
    tag = request.param
    modname, clsname = MODULES[tag]
    win = getattr(__import__(modname, fromlist=[clsname]), clsname)()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        yield tag, win, state
    finally:
        win.close()
        CertusTheme.configure("light")


@pytest.mark.parametrize("light_window", ["CERTUS_HUB", "CERTUS_DESIGN", "CERTUS_STRAT", "CERTUS_INDEX_SPLINE"], indirect=True)
def test_after_one_click_no_widget_sheet_of_a_window_holds_a_colour_only_the_light_palette_uses(light_window, qapp):
    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle
    from scripts.audit_ux_certus import frozen_light_sheets, light_only_colours

    tag, win, state = light_window
    light_only = light_only_colours()
    assert light_only, "the palettes share every colour: the count below would be vacuous"
    toggle = next(w for w in win.findChildren(QWidget) if isinstance(w, CertusThemeToggle))
    toggle.toggle()
    qapp.processEvents()
    assert state["mode"] == "dark"
    stale = frozen_light_sheets(win, light_only)
    assert stale == [], f"{tag}: {len(stale)} widget sheets kept a light colour after the click: {stale[:4]}"


# =============================================================================
# What the audit measures


def test_a_sheet_holds_a_light_colour_unless_it_is_the_tooltip_constant():
    from scripts.audit_ux_certus import sheet_light_colours

    light_only = {"#ffffff", "#f8fafc"}
    assert sheet_light_colours("color: #FFFFFF; border: 1px solid #333333;", light_only) == ["#ffffff"]
    assert sheet_light_colours("QToolTip { color: #f8fafc; }", light_only) == []  # a dark tooltip with a light ink, in both themes
    assert sheet_light_colours("QToolTip { color: #f8fafc; } QLabel { color: #f8fafc; }", light_only) == ["#f8fafc"]
    assert sheet_light_colours("", light_only) == []


def test_the_light_only_colours_are_those_of_the_light_palette_that_the_dark_one_does_not_use():
    from scripts.audit_ux_certus import light_only_colours

    found = light_only_colours()
    assert CertusTheme.DARK_MODE is False  # the helper changes the palette to compare, and puts it back
    assert "#ffffff" in found  # the light surface
    dark = set(_palette("dark").values())
    CertusTheme.configure("light")
    assert "#111827" in dark and "#111827" not in found  # the dark surface
    assert found.isdisjoint(dark)


def test_the_helper_puts_back_a_dark_palette_as_it_found_it():
    from scripts.audit_ux_certus import light_only_colours

    CertusTheme.configure("dark")
    light_only_colours()
    assert CertusTheme.DARK_MODE is True
