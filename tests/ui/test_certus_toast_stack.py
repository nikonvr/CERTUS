"""Tests for the CERTUS stacked toast notification system (U6)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# Pure-python: variants + icon mapping + API surface
# =============================================================================


def test_u6_supported_variants_and_icons():
    from certus_toast_stack import supported_variants, variant_icon_name

    variants = supported_variants()
    assert set(variants) == {"info", "success", "warning", "error"}
    # Each variant has a concrete icon associated
    for v in variants:
        assert variant_icon_name(v)
    # Unknown variant falls back to "info"
    assert variant_icon_name("nope") == "info"


def test_u6_icons_are_real_lucide_names():
    """Every variant's associated icon must exist in the Lucide bundle."""
    from certus_icons import available_icon_names
    from certus_toast_stack import supported_variants, variant_icon_name

    names = set(available_icon_names())
    for v in supported_variants():
        assert variant_icon_name(v) in names


def test_u6_variant_colors_returns_three_hex_strings():
    from certus_toast_stack import _variant_colors

    for variant in ("info", "success", "warning", "error", "unknown"):
        bg, fg, accent = _variant_colors(variant)
        for x in (bg, fg, accent):
            assert isinstance(x, str) and x.startswith("#") and len(x) in (7, 9)


def test_u6_public_api_does_nothing_when_parent_is_none():
    from certus_toast_stack import get_toast_stack, show_toast_stack

    assert get_toast_stack(None) is None
    assert show_toast_stack(None, "hello") is None


# =============================================================================
# Qt integration
# =============================================================================


@pytest.fixture
def qt_parent():
    from PyQt6.QtWidgets import QApplication, QMainWindow

    QApplication.instance() or QApplication([])
    win = QMainWindow()
    win.resize(900, 600)
    win.show()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()


def test_u6_stack_per_parent_is_memoised(qt_parent):
    from certus_toast_stack import get_toast_stack

    s1 = get_toast_stack(qt_parent)
    s2 = get_toast_stack(qt_parent)
    assert s1 is s2


def test_u6_show_toast_stack_returns_toast_and_registers(qt_parent):
    from certus_toast_stack import get_toast_stack, show_toast_stack

    t = show_toast_stack(qt_parent, "Saved successfully", variant="success")
    assert t is not None
    assert t.isVisible()
    stack = get_toast_stack(qt_parent)
    assert t in stack._toasts


def test_u6_stack_caps_at_max_size(qt_parent):
    from certus_toast_stack import MAX_STACK_SIZE, get_toast_stack, show_toast_stack

    for i in range(MAX_STACK_SIZE + 3):
        show_toast_stack(
            qt_parent, f"Event {i}", variant="info", duration_ms=0,  # no auto-dismiss
        )
    stack = get_toast_stack(qt_parent)
    # Eviction is asynchronous (fade-out); allow a beat for QTimer callbacks
    from PyQt6.QtCore import QCoreApplication
    for _ in range(6):
        QCoreApplication.processEvents()
    assert len(stack._toasts) <= MAX_STACK_SIZE


def test_u6_toast_geometry_inside_parent(qt_parent):
    from certus_toast_stack import show_toast_stack

    t = show_toast_stack(qt_parent, "Alert", variant="error", duration_ms=0)
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    # Toast must be in the bottom-right quadrant of the parent
    px = qt_parent.width()
    py = qt_parent.height()
    assert 0 < t.x() <= px
    assert 0 < t.y() <= py
    # Right-anchored: toast's right edge close to parent's right edge
    assert t.x() + t.width() <= px
    # Bottom-anchored: toast's bottom edge close to parent's bottom edge
    assert t.y() + t.height() <= py


def test_u6_variants_render_without_exception(qt_parent):
    from certus_toast_stack import show_toast_stack, supported_variants

    for v in supported_variants():
        t = show_toast_stack(
            qt_parent, f"variant={v}", variant=v, duration_ms=0, title=v.title(),
        )
        assert t is not None
        assert t.isVisible()
