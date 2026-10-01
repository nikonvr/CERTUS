"""A control's accessible name says what the control is, never the name of its class or of its style (audit v2, plan S6.5).

Measured on 2026-10-01, on the eleven windows, by reading what a screen reader would say (`scripts/audit_ux_certus.py`):
the plan counted ten explicit `setAccessibleName` calls and called it ten names; a generic pass (`certus_a11y`) already
gave one to nearly every control, and the names it gave were the finding.

* a radio button captioned "Custom (Constant)" was announced `QRadioButton`, the Run button `Certus primary btn`, the
  "1 Materials" section header `Expand 1 Materials section`: the pass wrote the class name or the prettified object
  name (a hook for the style sheet) into `accessibleName`, and an accessible name REPLACES the caption Qt would have read;
* a spin box whose tooltip came after the pass kept the class name for good (the pass saw a non-empty name and left it);
* a field with a label right beside it was named by its object name, never by that label, and no label was tied to
  its field (0 `setBuddy`);
* two fields under one label (`[ thickness ] [ min ] [ max ]`) can only be told apart by their tooltips;
* three windows (the launcher and the two utilities) do not inherit the base class and never ran the pass.

Now: a button that has a caption keeps it; a glyph button (`✕`, `◐`, `?`) says its tooltip; a field says its label (or,
when the label is too short or shared, what its tooltip says), the label becomes its buddy; a control nothing can name stays
unnamed rather than carrying a name that says nothing; the pass runs again once the window is built and when a page is turned.
"""

from __future__ import annotations

import gc
import os
import sys
import weakref
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from certus.ui.certus_a11y import (  # noqa: E402
    adjacent_label,
    apply_accessibility_defaults,
    derive_accessible_name,
    install_accessible_names,
    keep_names_current,
)


def _pump(qapp, ms: int = 60) -> None:
    from PyQt6.QtTest import QTest

    QTest.qWait(ms)
    qapp.processEvents()


# =============================================================================
# Where a field's name comes from


def test_a_field_in_a_form_row_is_named_by_the_label_of_its_row(qapp):
    root = QWidget()
    form = QFormLayout(root)
    spin = QDoubleSpinBox()
    form.addRow("Start wavelength (nm):", spin)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Start wavelength (nm)"  # the colon is not part of the name


def test_a_field_right_of_its_label_in_a_grid_is_named_and_the_label_becomes_its_buddy(qapp):
    root = QWidget()
    grid = QGridLayout(root)
    label, spin = QLabel("Thickness"), QDoubleSpinBox()
    grid.addWidget(label, 0, 0)
    grid.addWidget(spin, 0, 1)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Thickness"
    assert label.buddy() is spin


def test_a_field_after_its_label_in_a_row_and_one_under_its_label_in_a_column_are_named(qapp):
    root = QWidget()
    outer = QVBoxLayout(root)
    row = QHBoxLayout()
    outer.addLayout(row)
    combo = QComboBox()
    row.addWidget(QLabel("Material"))
    row.addWidget(combo)
    edit = QLineEdit()
    outer.addWidget(QLabel("Wavelengths"))
    outer.addWidget(edit)
    apply_accessibility_defaults(root)
    assert combo.accessibleName() == "Material"
    assert edit.accessibleName() == "Wavelengths"


def test_a_field_inside_a_row_inside_a_grid_cell_is_named_by_the_label_of_the_cell_on_its_left(qapp):
    root = QWidget()
    grid = QGridLayout(root)
    spin = QDoubleSpinBox()
    inner = QHBoxLayout()
    inner.addWidget(spin)
    inner.addWidget(QLabel("nm"))  # a unit: after the field, never its name
    grid.addWidget(QLabel("Layer thickness"), 0, 0)
    grid.addLayout(inner, 0, 1)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Layer thickness"


def test_a_label_between_a_label_and_its_field_that_is_a_unit_does_not_name_the_next_field(qapp):
    root = QWidget()
    row = QHBoxLayout(root)
    first, second = QDoubleSpinBox(), QDoubleSpinBox()
    second.setToolTip("Upper bound of the range. It must exceed the lower one.")
    for item in (QLabel("lambda min"), first, QLabel("nm"), second):
        row.addWidget(item)
    apply_accessibility_defaults(root)
    assert first.accessibleName() == "lambda min"
    assert second.accessibleName() == "Upper bound of the range"  # not "nm"


def test_a_stretch_and_a_help_button_between_a_label_and_its_field_are_stepped_over(qapp):
    """The METAL rows: `[label] [?] <stretch> [field]`."""
    root = QWidget()
    row = QHBoxLayout(root)
    field, help_button = QLineEdit(), QPushButton("?")
    help_button.setToolTip("Minimum expected thickness of the metal layer (nm).")
    row.addWidget(QLabel("eM min:"))
    row.addWidget(help_button)
    row.addStretch()
    row.addWidget(field)
    apply_accessibility_defaults(root)
    assert field.accessibleName() == "eM min"
    assert help_button.accessibleName() == "Help: Minimum expected thickness of the metal layer (nm)"


def test_a_label_too_short_to_say_what_the_field_is_is_completed_by_the_tooltip(qapp):
    root = QWidget()
    form = QFormLayout(root)
    weight = QDoubleSpinBox()
    weight.setToolTip("Relative weight given to Transmittance (T) in the cost function. More text.")
    form.addRow("T:", weight)
    apply_accessibility_defaults(root)
    assert weight.accessibleName() == "T: Relative weight given to Transmittance (T) in the cost function"


def test_two_fields_under_one_label_are_told_apart_and_neither_is_the_labels_buddy(qapp):
    root = QWidget()
    grid = QGridLayout(root)
    label, low, high = QLabel("Thickness (nm):"), QDoubleSpinBox(), QDoubleSpinBox()
    low.setToolTip("Minimum film thickness to search (nm). More text.")
    high.setToolTip("Maximum film thickness to search (nm). More text.")
    inner = QHBoxLayout()
    inner.addWidget(low)
    inner.addWidget(high)
    grid.addWidget(label, 0, 0)
    grid.addLayout(inner, 0, 1)
    apply_accessibility_defaults(root)
    assert low.accessibleName() == "Minimum film thickness to search (nm)"
    assert high.accessibleName() == "Maximum film thickness to search (nm)"
    assert label.buddy() is None


def test_two_fields_under_one_label_without_tooltips_get_a_rank(qapp):
    root = QWidget()
    grid = QGridLayout(root)
    first, second = QDoubleSpinBox(), QDoubleSpinBox()
    inner = QHBoxLayout()
    inner.addWidget(first)
    inner.addWidget(second)
    grid.addWidget(QLabel("Range"), 0, 0)
    grid.addLayout(inner, 0, 1)
    apply_accessibility_defaults(root)
    assert (first.accessibleName(), second.accessibleName()) == ("Range (1)", "Range (2)")


def test_a_label_with_a_mnemonic_names_its_field_and_is_not_tied_to_it(qapp):
    """`&T` would make Alt+T jump to the field: a key the author did not choose."""
    root = QWidget()
    form = QHBoxLayout(root)
    label, spin = QLabel("&Thickness"), QDoubleSpinBox()
    form.addWidget(label)
    form.addWidget(spin)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Thickness"
    assert label.buddy() is None


def test_a_label_that_already_has_a_buddy_keeps_it(qapp):
    root = QWidget()
    row = QHBoxLayout(root)
    label, other, spin = QLabel("Thickness"), QLineEdit(root), QDoubleSpinBox()
    label.setBuddy(other)
    row.addWidget(label)
    row.addWidget(spin)
    apply_accessibility_defaults(root)
    assert label.buddy() is other
    assert spin.accessibleName() == "Thickness"


def test_the_label_text_is_read_as_plain_text(qapp):
    root = QWidget()
    row = QHBoxLayout(root)
    spin = QDoubleSpinBox()
    row.addWidget(QLabel("<b>Index</b>  n &amp; k"))
    row.addWidget(spin)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Index n & k"


def test_adjacent_label_is_none_for_a_field_alone_or_beside_another_field(qapp):
    root = QWidget()
    row = QHBoxLayout(root)
    a, b = QLineEdit(), QLineEdit()
    row.addWidget(a)
    row.addWidget(b)
    assert adjacent_label(a) is None
    assert adjacent_label(b) is None
    assert adjacent_label(QLineEdit()) is None  # no parent at all


# =============================================================================
# Buttons: the caption, or the tooltip of a glyph


def test_a_button_that_has_a_caption_keeps_it_whatever_its_object_name_and_tooltip(qapp):
    root = QWidget()
    button = QPushButton("Run optimization", root)
    button.setObjectName("certus_primary_btn")
    button.setToolTip("Start the run.")
    apply_accessibility_defaults(root)
    assert button.accessibleName() == ""  # Qt reads the caption


def _tool_button(text: str) -> QToolButton:
    button = QToolButton()
    button.setText(text)
    return button


@pytest.mark.parametrize(
    "make",
    [lambda: QRadioButton("Custom (Constant)"), lambda: QCheckBox("Auto Y scale"), lambda: _tool_button("Detach")],
    ids=["radio", "check", "tool"],
)
def test_a_radio_button_a_check_box_and_a_tool_button_with_a_caption_are_left_to_their_caption(qapp, make):
    root = QWidget()
    control = make()
    control.setParent(root)
    apply_accessibility_defaults(root)
    assert control.accessibleName() == ""


def test_a_glyph_button_says_its_tooltip_and_a_question_mark_says_help(qapp):
    root = QWidget()
    close, info = QPushButton("✕", root), QPushButton("?", root)
    close.setToolTip("Close the log panel. It can be reopened from the toolbar.")
    info.setToolTip("Width of the window, in nm. Smaller is faster.")
    apply_accessibility_defaults(root)
    assert close.accessibleName() == "Close the log panel"
    assert info.accessibleName() == "Help: Width of the window, in nm"


def test_a_subclass_of_a_button_is_named_too(qapp):
    class Toggle(QPushButton):
        pass

    root = QWidget()
    toggle = Toggle("◐", root)
    toggle.setToolTip("Switch to dark theme")
    apply_accessibility_defaults(root)
    assert toggle.accessibleName() == "Switch to dark theme"


# =============================================================================
# Never a name that says nothing


def test_a_control_nothing_can_name_stays_unnamed_not_named_after_its_class_or_its_object(qapp):
    root = QWidget()
    spin, glyph = QSpinBox(root), QPushButton("✕", root)
    spin.setObjectName("thickness_spin")
    glyph.setObjectName("certus_primary_btn")
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == ""
    assert glyph.accessibleName() == ""


def test_a_name_is_never_the_class_the_object_or_a_glyph_on_any_control_without_a_source(qapp):
    root = QWidget()
    controls = [QSpinBox(root), QLineEdit(root), QComboBox(root), QCheckBox(root), QRadioButton(root)]
    for i, control in enumerate(controls):
        control.setObjectName(f"some_hook_{i}")
    apply_accessibility_defaults(root)
    assert [c.accessibleName() for c in controls] == [""] * len(controls)


def test_a_field_with_only_a_tooltip_says_the_first_sentence_without_the_markup(qapp):
    root = QWidget()
    edit = QLineEdit(root)
    edit.setToolTip("<b>Start</b> of the range (nm). More text, e.g. a second sentence.")
    apply_accessibility_defaults(root)
    assert edit.accessibleName() == "Start of the range (nm)"


def test_an_abbreviation_does_not_end_the_sentence(qapp):
    root = QWidget()
    combo = QComboBox(root)
    combo.setToolTip("Superstrate medium (incident medium, e.g. Air). Second sentence.")
    apply_accessibility_defaults(root)
    assert combo.accessibleName() == "Superstrate medium (incident medium, e.g. Air)"


def test_a_placeholder_names_a_field_that_has_no_tooltip(qapp):
    root = QWidget()
    edit = QLineEdit(root)
    edit.setPlaceholderText("Enter a wavelength")
    apply_accessibility_defaults(root)
    assert edit.accessibleName() == "Enter a wavelength"


def test_an_explicit_name_is_kept_and_a_second_pass_changes_nothing(qapp):
    root = QWidget()
    kept, named = QLineEdit(root), QLineEdit(root)
    kept.setAccessibleName("Already set")
    named.setToolTip("A tooltip")
    assert apply_accessibility_defaults(root) == 1
    assert apply_accessibility_defaults(root) == 0
    assert (kept.accessibleName(), named.accessibleName()) == ("Already set", "A tooltip")


def test_the_label_map_names_a_control_by_its_object_name_first(qapp):
    root = QWidget()
    edit = QLineEdit(root)
    edit.setObjectName("wl_min")
    edit.setToolTip("A tooltip that comes second")
    apply_accessibility_defaults(root, label_map={"wl_min": "Shortest wavelength"})
    assert edit.accessibleName() == "Shortest wavelength"


def test_the_line_edit_inside_a_spin_box_is_a_part_of_it_and_is_not_named(qapp):
    root = QWidget()
    spin = QDoubleSpinBox(root)
    spin.setToolTip("Thickness in nm")
    spin.lineEdit().setPlaceholderText("a source that would name it if it were a field")
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Thickness in nm"
    assert spin.lineEdit().accessibleName() == ""


def test_a_tooltip_that_arrives_after_the_first_pass_still_names_the_control(qapp):
    """The class name the old pass wrote was non-empty, so the control stayed named `QSpinBox` for good."""
    root = QWidget()
    spin = QSpinBox(root)
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == ""
    spin.setToolTip("Number of points")
    apply_accessibility_defaults(root)
    assert spin.accessibleName() == "Number of points"


def test_the_derivation_alone_returns_the_name_and_the_label(qapp):
    root = QWidget()
    row = QHBoxLayout(root)
    label, spin = QLabel("Angle"), QDoubleSpinBox()
    row.addWidget(label)
    row.addWidget(spin)
    assert derive_accessible_name(spin) == ("Angle", label)
    assert derive_accessible_name(QPushButton("Run")) == ("", None)


# =============================================================================
# The pass runs again


def test_a_page_built_after_the_first_pass_is_named_when_the_tab_is_turned(qapp):
    root = QWidget()
    tabs = QTabWidget(root)
    tabs.addTab(QWidget(), "one")
    tabs.addTab(QWidget(), "two")
    keep_names_current(root, delay_ms=60_000)
    late = QLineEdit(tabs.widget(1))
    late.setToolTip("Built late")
    assert late.accessibleName() == ""
    tabs.setCurrentIndex(1)
    _pump(qapp)
    assert late.accessibleName() == "Built late"


def test_a_page_of_a_stack_is_named_when_it_is_shown(qapp):
    root = QWidget()
    stack = QStackedWidget(root)
    stack.addWidget(QWidget())
    stack.addWidget(QWidget())
    keep_names_current(root, delay_ms=60_000)
    late = QLineEdit(stack.widget(1))
    late.setToolTip("Built late on a stack")
    stack.setCurrentIndex(1)
    _pump(qapp)
    assert late.accessibleName() == "Built late on a stack"


def test_the_pass_runs_again_after_the_delay(qapp):
    root = QWidget()
    keep_names_current(root, delay_ms=20)
    late = QLineEdit(root)
    late.setToolTip("Tooltip written after the build")
    _pump(qapp, 120)
    assert late.accessibleName() == "Tooltip written after the build"


def test_a_pending_pass_does_not_keep_the_window_alive(qapp):
    class Window(QWidget):
        pass

    window = Window()
    QTabWidget(window)
    keep_names_current(window, delay_ms=60_000)
    reference = weakref.ref(window)
    del window
    gc.collect()
    assert reference() is None


def test_install_names_the_controls_now_and_arranges_the_later_pass(qapp):
    root = QWidget()
    now = QLineEdit(root)
    now.setToolTip("Named now")
    assert install_accessible_names(root) == 1
    later = QLineEdit(root)
    later.setToolTip("Named later")
    keep_names_current(root, delay_ms=20)
    _pump(qapp, 120)
    assert (now.accessibleName(), later.accessibleName()) == ("Named now", "Named later")


# =============================================================================
# What the audit measures: the name a reader says


def test_the_audit_reads_a_name_the_way_qt_does(qapp):
    """The accessible name first, then the label whose buddy the control is, then a button's caption."""
    from scripts.audit_ux_certus import screen_reader_name

    root = QWidget()
    explicit, tied, button, bare = QLineEdit(root), QDoubleSpinBox(root), QPushButton("&Run now", root), QLineEdit(root)
    explicit.setAccessibleName("Explicit")
    label = QLabel("Thickness (&T)", root)
    label.setBuddy(tied)
    assert screen_reader_name(explicit) == "Explicit"
    assert screen_reader_name(tied) == "Thickness (T)"  # the mnemonic ampersand is not said
    assert screen_reader_name(button) == "Run now"
    assert screen_reader_name(bare) == ""


def test_the_audit_calls_poor_a_name_that_says_nothing(qapp):
    from scripts.audit_ux_certus import is_poor_name

    root = QWidget()
    spin, button = QSpinBox(root), QPushButton("Run", root)
    button.setObjectName("certus_primary_btn")
    assert is_poor_name(spin, "")
    assert is_poor_name(spin, "QSpinBox")  # the class
    assert is_poor_name(button, "Certus primary btn")  # the object name, prettified
    assert is_poor_name(button, "◐")  # a glyph
    assert not is_poor_name(button, "Run")
    assert not is_poor_name(spin, "Thickness in nm")


def test_the_audit_counts_the_visible_controls_and_not_the_inner_editor_of_a_spin_box(qapp):
    from scripts.audit_ux_certus import interactive_controls

    root = QWidget()
    layout = QVBoxLayout(root)
    spin, button, hidden = QDoubleSpinBox(), QPushButton("Run"), QPushButton("Hidden")
    for widget in (spin, button, hidden):
        layout.addWidget(widget)
    root.show()
    hidden.hide()
    found = interactive_controls(root)
    assert spin in found
    assert button in found
    assert hidden not in found
    assert spin.lineEdit() not in found
    root.close()


# =============================================================================
# The real windows


REAL_WINDOWS = {
    "CERTUS_HUB": ("CERTUS_HUB", "CertusHub"),
    "CERTUS_DESIGN": ("certus.ui.certus_design_ui", "CertusDesignApp"),
    "CERTUS_STRAT": ("certus.ui.certus_strat_ui", "CertusStratApp"),
    "CERTUS_SMOOTHER": ("certus.utils.certus_curve_smoother", "CurveSmootherGUI"),
    "CERTUS_SUBSTRATE_INDEX": ("certus.ui.certus_substrate_ui", "SubstrateIndexGUI"),
    "CERTUS_METAL_SINGLE": ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
}


@pytest.mark.parametrize("tag", list(REAL_WINDOWS))
def test_every_visible_control_of_a_real_window_says_something_a_reader_can_use(qapp, tag):
    """What the audit measures on the eleven windows (378 controls, 0 poor name on 2026-10-01), on six of them."""
    from PyQt6.QtCore import Qt

    from scripts.audit_ux_certus import interactive_controls, is_poor_name, screen_reader_name

    module, cls = REAL_WINDOWS[tag]
    win = getattr(__import__(module, fromlist=[cls]), cls)()
    try:
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        win.show()
        _pump(qapp, 1800)  # the second pass runs 1.5 s after the window is built
        poor = [
            f"{type(w).__name__}|{w.objectName() or '-'}|{w.toolTip()[:40]}"
            for w in interactive_controls(win)
            if is_poor_name(w, screen_reader_name(w))
        ]
        assert not poor, f"{tag}: {len(poor)} controls with a name that says nothing: {poor}"
    finally:
        win.close()


def test_the_theme_toggle_says_the_action_it_will_do_and_changes_it_when_it_does_it(qapp, monkeypatch):
    from certus.ui import certus_ui_widgets_utils as utils

    mode = {"value": "light"}
    monkeypatch.setattr(utils, "load_theme_config", lambda: mode["value"])
    toggle = utils.CertusThemeToggle()
    assert toggle.accessibleName() == "Switch to dark theme"
    mode["value"] = "dark"
    toggle.update_appearance()
    assert toggle.accessibleName() == "Switch to light theme"
    assert toggle.accessibleName() == toggle.toolTip()
