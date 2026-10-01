"""A tint is written `rgba(r, g, b, a)`, never `#rrggbbaa`: Qt reads eight hex digits as `#aarrggbb` (audit v2, plan S6.4b).

📏 Measured 2026-10-01, in a Qt style sheet:

    `background: #ff000080`      -> (0, 0, 128), opaque: alpha ff, red 00, green 00, blue 80
    `#0f62fe` + `2e` (what `certus_ux._hex_with_alpha` wrote for an 18 % tint) -> alpha 0f, rgb (98, 254, 46): a lime green at 6 %

so the hover of every ghost button, header section and splitter handle was a lime green at 6 % in the light theme and a yellow-green at 38 %
in the dark one, where a blue at 18 % was meant. `f"{token}11"` (the red tint of a numeric field that does not parse) was worse once a colour
of the palette carries its name: the comment `/*T:DANGER*/` sits INSIDE the number, and Qt drops the whole declaration (tested below).

`CertusTheme.tint` writes the documented form, and a colour of the palette keeps its name, `rgba(15, 98, 254, 0.18)/*A:PRIMARY:0.18*/`, so a tint
follows the theme like the colour it is made of. A sheet KEPT as a string (a validator keeps the one of its field) goes through
`CertusTheme.current_sheet` before it is applied again.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget

from certus.ui.certus_theme import CertusTheme

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def light_palette():
    """Every test starts and ends in the light palette: `CertusTheme` is a class, its palette is process state."""
    CertusTheme.configure("light")
    yield
    CertusTheme.configure("light")


def _pixel(widget: QWidget, x: int = 2, y: int = 2) -> tuple[int, int, int]:
    """The colour of a pixel of `widget`, painted over WHITE (`grab()` keeps the alpha apart: a tint would read as its bare colour)."""
    widget.resize(160, 40)
    widget.show()
    QApplication.processEvents()
    image = QImage(160, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    widget.render(painter)
    painter.end()
    c = image.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def _close(a: tuple[int, int, int], b: tuple[int, int, int], tolerance: int = 2) -> bool:
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))


def _labelled(sheet: str) -> QLabel:
    label = QLabel("x")
    label.setStyleSheet(sheet)
    return label


# =============================================================================
# What Qt reads


def test_qt_reads_eight_hex_digits_as_argb_not_as_css_rgba(qapp):
    """The reason for everything below: `#ff000080` is an opaque navy, not a red at 50 %."""
    assert _pixel(_labelled("background: #ff000080;")) == (0, 0, 128)


def test_a_colour_followed_by_digits_after_its_comment_is_not_a_colour_to_qt(qapp):
    """`f"{token}11"` writes `#dc2626/*T:DANGER*/11`: the declaration is dropped, the widget keeps its own background."""
    plain = _pixel(QLabel("x"))
    broken = _pixel(_labelled("background: #dc2626/*T:DANGER*/11;"))
    assert broken == plain


# =============================================================================
# The helper of `certus_ux`


def test_a_hex_with_alpha_is_an_rgba_that_qt_paints_as_the_tint_asked_for(qapp):
    from certus.utils.certus_ux import _hex_with_alpha

    written = _hex_with_alpha("#0f62fe", 18)
    assert written == "rgba(15, 98, 254, 0.18)"
    argb_reference = f"#{round(0.18 * 255):02x}0f62fe"  # what Qt reads as the same tint: alpha first
    assert _close(_pixel(_labelled(f"background: {written};")), _pixel(_labelled(f"background: {argb_reference};")))


def test_a_hex_with_alpha_keeps_its_old_edge_cases():
    from certus.utils.certus_ux import _hex_with_alpha

    assert _hex_with_alpha("#12345", 18) == "#12345"  # not six digits: given back as it came
    assert _hex_with_alpha("#ff0000", 150) == "rgba(255, 0, 0, 1)"  # clamped to 100 %
    assert _hex_with_alpha("#ff0000", -5) == "rgba(255, 0, 0, 0)"
    assert _hex_with_alpha("ff0000", 50) == "rgba(255, 0, 0, 0.5)"  # the `#` is optional


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_soft_fills_of_the_premium_sheet_are_the_primary_colour_at_eighteen_and_thirty_six_percent(qapp, mode):
    from certus.utils.certus_ux import build_premium_overrides

    CertusTheme.configure(mode)
    sheet = build_premium_overrides()
    assert not re.search(r"#[0-9a-fA-F]{8}\b", sheet), "an eight-digit hex colour is read as #aarrggbb by Qt"
    primary = QColor(CertusTheme.PRIMARY)
    fills = re.findall(r"background-color:\s*rgba\((\d+), (\d+), (\d+), ([0-9.]+)\)", sheet)
    assert sorted(alpha for *_rgb, alpha in fills) == ["0.18", "0.18", "0.18", "0.36"]  # three hovers, one pressed
    for red, green, blue, _alpha in fills:
        assert (int(red), int(green), int(blue)) == (primary.red(), primary.green(), primary.blue())


def test_the_ghost_button_hover_and_pressed_are_the_two_strengths_in_that_order(qapp):
    from certus.utils.certus_ux import OBJ, build_premium_overrides

    sheet = build_premium_overrides()
    for state, alpha in (("hover", "0.18"), ("pressed", "0.36")):
        body = re.search(rf"QPushButton#{OBJ.GHOST_BUTTON}:{state}\s*\{{([^}}]*)\}}", sheet)
        assert body, state
        assert f", {alpha})" in body.group(1)


# =============================================================================
# `CertusTheme.tint`


def test_a_tint_of_a_plain_colour_is_a_plain_rgba():
    assert CertusTheme.tint("#0f62fe", 0.18) == "rgba(15, 98, 254, 0.18)"
    assert CertusTheme.tint("red", 0.5) == "rgba(255, 0, 0, 0.5)"  # any colour Qt can read
    assert CertusTheme.tint("#000000", 1) == "rgba(0, 0, 0, 1)"
    assert CertusTheme.tint("#000000", 0.07) == "rgba(0, 0, 0, 0.07)"


def test_a_tint_of_a_colour_of_the_palette_keeps_its_name():
    assert CertusTheme.tint(CertusTheme.PRIMARY, 0.18) == "rgba(15, 98, 254, 0.18)/*A:PRIMARY:0.18*/"
    assert CertusTheme.tint(CertusTheme.SURFACE, 0.4) == "rgba(255, 255, 255, 0.4)/*A:SURFACE:0.4*/"


def test_a_tint_of_something_that_is_not_a_colour_is_given_back():
    assert CertusTheme.tint("not a colour", 0.5) == "not a colour"


def test_qt_paints_an_annotated_tint_like_a_plain_one(qapp):
    plain = _pixel(_labelled("background: rgba(15, 98, 254, 0.18);"))
    noted = _pixel(_labelled("background: rgba(15, 98, 254, 0.18)/*A:PRIMARY:0.18*/;"))
    assert plain == noted
    assert plain != _pixel(QLabel("x")), "the tint must be visible, or the comparison above proves nothing"


def test_a_tint_of_the_palette_takes_the_new_palette_and_keeps_its_name(qapp):
    label = _labelled(f"background: {CertusTheme.tint(CertusTheme.PRIMARY, 0.18)}; margin: 2px;")
    original = label.styleSheet()
    CertusTheme.configure("dark")
    assert CertusTheme.refresh_widget_sheets() >= 1
    assert label.styleSheet() == "background: rgba(96, 165, 250, 0.18)/*A:PRIMARY:0.18*/; margin: 2px;"
    CertusTheme.configure("light")
    CertusTheme.refresh_widget_sheets()
    assert label.styleSheet() == original  # the annotation survives: a second change works the same


def test_a_tint_of_an_ordinary_colour_or_of_a_name_that_is_no_token_is_left_alone(qapp):
    fixed = _labelled("background: rgba(1, 2, 3, 0.5);")
    unknown = _labelled("background: rgba(1, 2, 3, 0.5)/*A:NOT_A_TOKEN:0.5*/; color: rgba(4, 5, 6, 0.25)/*A:TEXT:0.25*/;")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert fixed.styleSheet() == "background: rgba(1, 2, 3, 0.5);"
    assert unknown.styleSheet() == "background: rgba(1, 2, 3, 0.5)/*A:NOT_A_TOKEN:0.5*/; color: rgba(4, 5, 6, 0.25)/*A:TEXT:0.25*/;"


def test_a_label_that_spells_a_tint_in_rich_text_follows_the_theme(qapp):
    label = QLabel(f'<span style="background:{CertusTheme.tint(CertusTheme.PRIMARY, 0.2)};">ready</span>')
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert label.text() == '<span style="background:rgba(96, 165, 250, 0.2)/*A:PRIMARY:0.2*/;">ready</span>'


# =============================================================================
# `CertusTheme.current_sheet`: a text kept elsewhere


def test_a_kept_sheet_text_takes_the_active_palette(qapp):
    kept = f"color: {CertusTheme.TEXT_SUB}; background: {CertusTheme.tint(CertusTheme.PRIMARY, 0.2)}; border: 1px solid #123456;"
    CertusTheme.configure("dark")
    assert CertusTheme.current_sheet(kept) == (
        "color: #94a3b8/*T:TEXT_SUB*/; background: rgba(96, 165, 250, 0.2)/*A:PRIMARY:0.2*/; border: 1px solid #123456;"
    )
    assert CertusTheme.current_sheet("font-size: 11px;") == "font-size: 11px;"
    assert CertusTheme.current_sheet("") == ""


def test_a_kept_button_style_is_built_again_by_current_sheet(qapp):
    kept = CertusTheme.get_button_style("danger")
    CertusTheme.configure("dark")
    assert CertusTheme.current_sheet(kept) == CertusTheme.get_button_style("danger")


# =============================================================================
# A numeric field that does not parse


def _invalid_field_sheet(mode_after: str | None = None) -> tuple[QLineEdit, str]:
    from certus.ui.certus_ui_utils import attach_numeric_validator

    edit = QLineEdit()
    edit.setStyleSheet(f"QLineEdit {{ color: {CertusTheme.TEXT_MAIN}; }}")
    attach_numeric_validator(edit, minimum=0, maximum=10)
    if mode_after:
        CertusTheme.configure(mode_after)
        CertusTheme.refresh_widget_sheets()
    edit.setText("abc")
    return edit, edit.styleSheet()


def test_a_field_that_does_not_parse_has_a_red_border_and_a_red_tint(qapp):
    edit, sheet = _invalid_field_sheet()
    assert "border: 1px solid #dc2626/*T:DANGER*/" in sheet
    assert "background: rgba(220, 38, 38, 0.07)/*A:DANGER:0.07*/" in sheet
    edit.setText("5")
    assert edit.styleSheet() == "QLineEdit { color: #0f172a/*T:TEXT_MAIN*/; }"


def test_the_red_tint_of_an_invalid_field_is_painted(qapp):
    """The declaration used to be dropped by Qt (a token with digits glued to it): the inside of the field kept its colour."""
    edit, _sheet = _invalid_field_sheet()
    flagged = _pixel(edit, 100, 20)
    fine = QLineEdit()
    fine.setStyleSheet(f"QLineEdit {{ color: {CertusTheme.TEXT_MAIN}; }}")
    reference = _pixel(fine, 100, 20)
    assert flagged != reference
    assert flagged[0] >= flagged[1] + 8, f"not red: {flagged}"


def test_a_field_flagged_after_the_toggle_gets_the_new_palette_not_the_one_it_was_attached_in(qapp):
    """The validator keeps two sheets as strings: put back later, they would bring the light palette back."""
    edit, sheet = _invalid_field_sheet(mode_after="dark")
    assert "border: 1px solid #f87171/*T:DANGER*/" in sheet
    assert "background: rgba(248, 113, 113, 0.07)/*A:DANGER:0.07*/" in sheet
    assert "QLineEdit { color: #e2e8f0/*T:TEXT_MAIN*/; }" in sheet
    edit.setText("5")
    assert edit.styleSheet() == "QLineEdit { color: #e2e8f0/*T:TEXT_MAIN*/; }"
    edit.setText("")
    assert edit.styleSheet() == "QLineEdit { color: #e2e8f0/*T:TEXT_MAIN*/; }"


# =============================================================================
# The badge of the hub


def test_the_module_badge_tints_its_colour_instead_of_gluing_digits_to_it(qapp):
    from certus.ui.certus_hub_widgets import ModuleBadge

    badge = ModuleBadge("DESIGN", CertusTheme.PRIMARY)
    sheet = badge.styleSheet()
    assert "background-color: rgba(15, 98, 254, 0.08)/*A:PRIMARY:0.08*/" in sheet
    assert "border: 1px solid rgba(15, 98, 254, 0.38)/*A:PRIMARY:0.38*/" in sheet
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert "background-color: rgba(96, 165, 250, 0.08)/*A:PRIMARY:0.08*/" in badge.styleSheet()
    plain = ModuleBadge("X", "#336699").styleSheet()
    assert "background-color: rgba(51, 102, 153, 0.08);" in plain and "/*A:" not in plain


# =============================================================================
# The status pill


PILL_ACCENTS = (("ready", "SUCCESS"), ("running", "PRIMARY"), ("error", "DANGER"), ("warning", "WARNING"), ("done", "SECONDARY"))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_a_status_pill_tints_its_accent_instead_of_appending_digits_to_it(qapp, mode):
    """`CertusTheme.SUCCESS + "22"` was `#15803d22`: alpha 15, rgb (80, 3d, 22), a brown at 8 % under a green label."""
    from certus.ui.certus_ui_widgets_utils import CertusStatusPill

    CertusTheme.configure(mode)
    for level, accent in PILL_ACCENTS:
        sheet = CertusStatusPill("x", level).styleSheet()
        colour = QColor(getattr(CertusTheme, accent))
        rgb = f"{colour.red()}, {colour.green()}, {colour.blue()}"
        assert f"background: rgba({rgb}, 0.13)/*A:{accent}:0.13*/" in sheet, (level, sheet)
        assert not re.search(r"#[0-9a-fA-F]{8}\b", sheet), (level, sheet)
    border = CertusStatusPill("x", "warning").styleSheet()
    warning = QColor(CertusTheme.WARNING)
    assert f"border: 1px solid rgba({warning.red()}, {warning.green()}, {warning.blue()}, 0.33)/*A:WARNING:0.33*/" in border


def test_a_status_pill_that_has_no_accent_keeps_its_plain_tokens(qapp):
    from certus.ui.certus_ui_widgets_utils import CertusStatusPill

    sheet = CertusStatusPill("x", "no such level").styleSheet()
    assert sheet.startswith("background: #f8fafc/*T:SURFACE_HOVER*/; color: #475569/*T:TEXT_SUB*/; border: 1px solid #d7dfe8/*T:BORDER*/;")


def test_the_ready_pill_is_painted_green_not_brown(qapp):
    """Painted over white: the tint of a green is greener than white, the old brown at 8 % was redder."""
    from certus.ui.certus_ui_widgets_utils import CertusStatusPill

    red, green, _blue = _pixel(CertusStatusPill("", "ready"), 100, 20)
    assert green > red, f"not green: {(red, green, _blue)}"


def test_a_status_pill_follows_the_theme(qapp):
    from certus.ui.certus_ui_widgets_utils import CertusStatusPill

    pill = CertusStatusPill("x", "error")
    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()
    assert "background: rgba(248, 113, 113, 0.13)/*A:DANGER:0.13*/" in pill.styleSheet()
    assert "color: #f87171/*T:DANGER*/" in pill.styleSheet()


# =============================================================================
# The pattern itself, everywhere


def digits_glued_to_an_interpolation(source: str) -> list[int]:
    """Lines of the f-strings that write hex digits right after an interpolation inside a colour declaration."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.JoinedStr):
            continue
        for index, (before, after) in enumerate(zip(node.values, node.values[1:], strict=False)):
            if not (isinstance(before, ast.FormattedValue) and isinstance(after, ast.Constant) and isinstance(after.value, str)):
                continue
            if not re.match(r"[0-9a-fA-F]{2}(?![0-9A-Za-z_])", after.value):
                continue
            text = "".join(v.value for v in node.values[: index + 1] if isinstance(v, ast.Constant) and isinstance(v.value, str))
            declaration = re.split(r"[;{}]", text)[-1]
            if re.search(r"color|background|border|fill|stroke|outline|stop:", declaration):
                found.append(before.lineno)
    return found


def test_the_scanner_tells_digits_glued_to_a_colour_from_a_number_or_a_unit():
    """Negative control: with a scanner that finds nothing, the guard below would pass for nothing."""
    assert digits_glued_to_an_interpolation('x = f"background: {c}15;"') == [1]
    assert digits_glued_to_an_interpolation('x = f"border: 1px solid {c}60; color: red;"') == [1]
    assert digits_glued_to_an_interpolation('x = f"QLabel {{ color: {c}ff; }}"') == [1]
    assert digits_glued_to_an_interpolation('x = f"width: {w}10px;"') == []  # a unit follows the digits
    assert digits_glued_to_an_interpolation('x = f"{n}00 items"') == []  # no colour declaration
    assert digits_glued_to_an_interpolation('x = f"color: {c}; width: {w}20;"') == []  # the digits belong to `width`
    assert digits_glued_to_an_interpolation('x = f"background: {c}"') == []


def test_no_f_string_of_the_interface_glues_digits_to_a_colour():
    offenders = []
    files = [*ROOT.glob("CERTUS_*.py"), *(ROOT / "certus").rglob("*.py")]
    for path in sorted(files):
        for line in digits_glued_to_an_interpolation(path.read_text(encoding="utf-8-sig")):
            offenders.append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    assert not offenders, f"hex digits written right after an interpolation (Qt reads them wrong, or not at all): {offenders}; use CertusTheme.tint"


def digits_appended_by_concatenation(source: str) -> list[int]:
    """Lines where two hex digits are added with `+` to a colour of the palette or to a variable named like a colour."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
            continue
        right = node.right
        if not (isinstance(right, ast.Constant) and isinstance(right.value, str) and re.fullmatch(r"[0-9a-fA-F]{2}", right.value)):
            continue
        left = ast.get_source_segment(source, node.left) or ""
        if re.search(r"\b(?:CertusTheme|T|theme|Theme)\.[A-Z_]+\s*$|(?:color|colour|hex|accent|tone|bg|fg)\w*\s*$", left):
            found.append(node.lineno)
    return found


def test_the_second_scanner_tells_an_appended_alpha_from_any_other_concatenation():
    """Negative control for the guard below."""
    assert digits_appended_by_concatenation('x = CertusTheme.SUCCESS + "22"') == [1]
    assert digits_appended_by_concatenation('x = color + "55"') == [1]
    assert digits_appended_by_concatenation('x = (T.PRIMARY + "1a", 2)') == [1]
    assert digits_appended_by_concatenation('x = CertusTheme.SUCCESS + "px"') == []  # not two hex digits
    assert digits_appended_by_concatenation('x = prefix + "12"') == []  # nothing says it is a colour
    assert digits_appended_by_concatenation('x = "ab" + "12"') == []


def test_no_colour_of_the_interface_gets_two_digits_appended_with_a_plus():
    offenders = []
    files = [*ROOT.glob("CERTUS_*.py"), *(ROOT / "certus").rglob("*.py")]
    for path in sorted(files):
        for line in digits_appended_by_concatenation(path.read_text(encoding="utf-8-sig")):
            offenders.append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    assert not offenders, f"alpha appended to a colour by `+` (Qt reads it as #aarrggbb): {offenders}; use CertusTheme.tint"
