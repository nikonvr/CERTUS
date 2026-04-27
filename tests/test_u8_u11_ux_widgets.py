"""Tests for U8..U11 UX widgets (empty state, badges, tooltips, tracker).

Introspection-first so the suite stays fast. Qt behaviour is exercised
only where the logic is non-trivial.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# U8 - Empty state
# =============================================================================


def test_u8_module_surface():
    import certus_empty_state as m

    for name in (
        "DEFAULT_ICON_SIZE_PX",
        "DEFAULT_TITLE",
        "DEFAULT_DESCRIPTION",
        "build_empty_state",
        "attach_empty_state_to",
        "detach_empty_state_from",
    ):
        assert hasattr(m, name), f"certus_empty_state missing {name!r}"


def test_u8_defaults_are_sensible():
    from certus_empty_state import DEFAULT_DESCRIPTION, DEFAULT_ICON_SIZE_PX, DEFAULT_TITLE

    assert 24 <= DEFAULT_ICON_SIZE_PX <= 96
    assert DEFAULT_TITLE.strip()
    assert DEFAULT_DESCRIPTION.strip()


def test_u8_factory_returns_visible_widget():
    from PyQt6.QtWidgets import QApplication

    from certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None, title="Nothing here", description="Load a file", action_label="Load")
    assert w is not None
    assert w.has_action() is True


def test_u8_without_action_label_has_no_cta():
    from PyQt6.QtWidgets import QApplication

    from certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None, title="X", description="Y")
    assert w.has_action() is False


def test_u8_action_emits_signal_and_invokes_callback():
    from PyQt6.QtWidgets import QApplication

    from certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    called = []

    w = build_empty_state(
        None, title="t", description="d", action_label="Go", on_action=lambda: called.append(1)
    )
    signal_hit = []
    w.action_triggered.connect(lambda: signal_hit.append(1))
    w._action_btn.click()
    assert called == [1]
    assert signal_hit == [1]


def test_u8_set_title_and_description():
    from PyQt6.QtWidgets import QApplication

    from certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None)
    w.set_title("New title")
    w.set_description("New desc")
    assert "New title" in w._title_lbl.text()
    assert "New desc" in w._desc_lbl.text()


# =============================================================================
# U9 - Status badges
# =============================================================================


def test_u9_variants_and_icon_mapping():
    from certus_badges import VARIANT_LABELS, supported_variants, variant_icon_name

    variants = supported_variants()
    assert set(variants) == set(VARIANT_LABELS.keys())
    assert set(variants) == {"idle", "running", "success", "error", "warning", "info", "neutral"}
    for v in variants:
        assert variant_icon_name(v)  # every variant has an icon


def test_u9_icons_are_real_lucide_names():
    from certus_badges import supported_variants, variant_icon_name
    from certus_icons import available_icon_names

    names = set(available_icon_names())
    for v in supported_variants():
        assert variant_icon_name(v) in names


def test_u9_variant_color_returns_three_hex_strings():
    from certus_badges import supported_variants, variant_color

    for v in list(supported_variants()) + ["unknown"]:
        bg, fg, border = variant_color(v)
        for x in (bg, fg, border):
            assert isinstance(x, str) and x.startswith("#") and 4 <= len(x) <= 9


def test_u9_widget_set_variant_changes_state():
    from PyQt6.QtWidgets import QApplication

    from certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(text="Run", variant="running")
    assert b.variant() == "running"
    b.set_variant("error")
    assert b.variant() == "error"


def test_u9_uppercase_option_transforms_text():
    from PyQt6.QtWidgets import QApplication

    from certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(text="done", variant="success", uppercase=True)
    assert b.text() == "DONE"


def test_u9_unknown_variant_falls_back_to_neutral():
    from PyQt6.QtWidgets import QApplication

    from certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(variant="wat")
    assert b.variant() == "neutral"


# =============================================================================
# U10 - Rich tooltips
# =============================================================================


def test_u10_tooltip_spec_is_frozen_dataclass():
    from certus_tooltips import TooltipSpec

    s = TooltipSpec(title="Hello", body="World")
    assert s.title == "Hello"
    assert s.body == "World"
    with pytest.raises(Exception):
        s.title = "Changed"  # frozen


def test_u10_has_icon_and_has_link_flags():
    from certus_tooltips import TooltipSpec

    s = TooltipSpec(title="t", body="b")
    assert not s.has_icon()
    assert not s.has_link()

    s2 = TooltipSpec(title="t", body="b", icon_name="info", link="https://example.com")
    assert s2.has_icon()
    assert s2.has_link()


def test_u10_attach_and_detach_are_symmetric():
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus_tooltips import attach_rich_tooltip, detach_rich_tooltip, get_tooltip_spec

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("Hover me")
    spec = attach_rich_tooltip(w, "Title", "Body text")
    assert get_tooltip_spec(w) is spec
    assert detach_rich_tooltip(w) is True
    assert get_tooltip_spec(w) is None


def test_u10_reattach_replaces_previous_spec():
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus_tooltips import attach_rich_tooltip, get_tooltip_spec

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("x")
    s1 = attach_rich_tooltip(w, "A", "alpha")
    s2 = attach_rich_tooltip(w, "B", "beta")
    current = get_tooltip_spec(w)
    assert current is s2
    assert s1 is not s2


def test_u10_none_widget_returns_spec_without_error():
    from certus_tooltips import attach_rich_tooltip

    spec = attach_rich_tooltip(None, "T", "B")
    assert spec.title == "T"


# =============================================================================
# U11 - Progress tracker
# =============================================================================


def test_u11_step_auto_slug_key():
    from certus_progress_tracker import ProgressStep

    s = ProgressStep(title="Load data")
    assert s.key == "load_data"
    s2 = ProgressStep(title="Solve")
    assert s2.key == "solve"
    s3 = ProgressStep(title="Custom", key="custom-id")
    assert s3.key == "custom-id"


def test_u11_step_icons_match_states():
    from certus_progress_tracker import StepState, step_icon_name

    assert step_icon_name(StepState.PENDING) == "circle"
    assert step_icon_name(StepState.RUNNING) == "loader"
    assert step_icon_name(StepState.DONE) == "check-circle"
    assert step_icon_name(StepState.ERROR) == "alert-triangle"
    # Accepts string too
    assert step_icon_name("done") == "check-circle"


def test_u11_step_icons_exist_in_lucide_bundle():
    from certus_icons import available_icon_names
    from certus_progress_tracker import StepState, step_icon_name

    names = set(available_icon_names())
    for st in StepState:
        assert step_icon_name(st) in names


def test_u11_step_color_returns_hex_string():
    from certus_progress_tracker import StepState, step_color

    for st in StepState:
        c = step_color(st)
        assert isinstance(c, str) and c.startswith("#")


def test_u11_format_eta_variants():
    from certus_progress_tracker import format_eta

    assert format_eta(None) == ""
    assert format_eta(-1) == ""
    assert format_eta(0) == "ETA ~0s"
    assert format_eta(25) == "ETA ~25s"
    assert format_eta(65) == "ETA ~1m05s"
    assert format_eta(3725) == "ETA ~1h02m"


def test_u11_tracker_advance_to_updates_states():
    from PyQt6.QtWidgets import QApplication

    from certus_progress_tracker import StepState, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["Read", "Solve", "Save"], title="Run")
    tr.advance_to(0)
    assert tr.state_of(0) == StepState.RUNNING
    assert tr.state_of(1) == StepState.PENDING

    tr.advance_to(2, sub_message="Writing JSON")
    assert tr.state_of(0) == StepState.DONE
    assert tr.state_of(1) == StepState.DONE
    assert tr.state_of(2) == StepState.RUNNING


def test_u11_mark_all_done_and_error_state():
    from PyQt6.QtWidgets import QApplication

    from certus_progress_tracker import StepState, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B"])
    tr.mark_all_done()
    assert tr.state_of(0) == StepState.DONE
    assert tr.state_of(1) == StepState.DONE

    tr.mark_step(1, StepState.ERROR, sub_message="Boom")
    assert tr.state_of(1) == StepState.ERROR


def test_u11_set_eta_shows_label():
    from PyQt6.QtWidgets import QApplication

    from certus_progress_tracker import build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A"], eta_seconds=42)
    assert tr._eta_lbl.text().startswith("ETA")
    tr.set_eta(None)
    assert tr._eta_lbl.text() == ""


def test_u11_steps_returns_snapshot_copy():
    from PyQt6.QtWidgets import QApplication

    from certus_progress_tracker import build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B"])
    lst = tr.steps()
    lst.clear()
    # Mutating the returned list must not alter tracker state
    assert tr.state_of(0) is not None
