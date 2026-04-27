"""Tests for the CERTUS skeleton loading widgets (U7).

Most tests are introspective (import + API surface) to keep runtime low.
A handful of Qt tests exercise the widget lifecycle using offscreen Qt.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# Introspection (no Qt required)
# =============================================================================


def test_u7_module_exposes_public_api():
    import certus_skeleton as m

    for name in (
        "skeleton_for",
        "install_skeleton",
        "uninstall_skeleton",
        "is_skeleton_active",
        "SHIMMER_PERIOD_MS",
        "DEFAULT_LINES",
        "DEFAULT_LINE_HEIGHT",
    ):
        assert hasattr(m, name), f"certus_skeleton missing {name!r}"


def test_u7_public_api_safe_on_none():
    from certus_skeleton import (
        install_skeleton,
        is_skeleton_active,
        skeleton_for,
        uninstall_skeleton,
    )

    assert skeleton_for(None) is None
    assert install_skeleton(None) is None
    assert uninstall_skeleton(None) is False
    assert is_skeleton_active(None) is False


def test_u7_theme_colors_return_three_strings():
    from certus_skeleton import _theme_colors

    base, highlight, border = _theme_colors()
    for x in (base, highlight, border):
        assert isinstance(x, str) and x


def test_u7_constants_are_reasonable():
    from certus_skeleton import (
        DEFAULT_GAP_PX,
        DEFAULT_LINES,
        DEFAULT_LINE_HEIGHT,
        DEFAULT_RADIUS_PX,
        SHIMMER_PERIOD_MS,
    )

    assert 500 <= SHIMMER_PERIOD_MS <= 3000
    assert 1 <= DEFAULT_LINES <= 10
    assert 8 <= DEFAULT_LINE_HEIGHT <= 32
    assert 2 <= DEFAULT_GAP_PX <= 24
    assert 2 <= DEFAULT_RADIUS_PX <= 16


# =============================================================================
# Qt integration (offscreen)
# =============================================================================


@pytest.fixture
def qt_target():
    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    w = QWidget()
    w.resize(400, 300)
    w.show()
    try:
        yield w
    finally:
        w.close()
        w.deleteLater()


def test_u7_install_then_uninstall_is_idempotent_and_symmetric(qt_target):
    from certus_skeleton import install_skeleton, is_skeleton_active, uninstall_skeleton

    overlay_a = install_skeleton(qt_target, label="Optimising...", lines=4)
    assert overlay_a is not None
    assert is_skeleton_active(qt_target)

    # Re-installing returns the same overlay (no duplication)
    overlay_b = install_skeleton(qt_target, label="Optimising still...", lines=4)
    assert overlay_b is overlay_a

    # Uninstall reports success + clears the state
    assert uninstall_skeleton(qt_target) is True
    assert not is_skeleton_active(qt_target)

    # A second uninstall is a no-op that returns False
    assert uninstall_skeleton(qt_target) is False


def test_u7_overlay_covers_target_area(qt_target):
    from certus_skeleton import install_skeleton

    overlay = install_skeleton(qt_target, label="Loading")
    # Overlay must match target's geometry
    assert overlay.width() == qt_target.width()
    assert overlay.height() == qt_target.height()


def test_u7_overlay_resizes_with_target(qt_target):
    from PyQt6.QtCore import QCoreApplication

    from certus_skeleton import install_skeleton

    overlay = install_skeleton(qt_target)
    qt_target.resize(650, 420)
    QCoreApplication.processEvents()
    # Event filter must have resized the overlay
    assert overlay.width() == qt_target.width()
    assert overlay.height() == qt_target.height()


def test_u7_skeleton_for_builds_overlay_without_starting(qt_target):
    from certus_skeleton import skeleton_for

    ov = skeleton_for(qt_target, lines=2, label="Test")
    assert ov is not None
    # Not started + not visible yet (install_skeleton would do both)
    assert not ov.isVisible()


def test_u7_group_uses_requested_line_count(qt_target):
    from certus_skeleton import install_skeleton

    ov = install_skeleton(qt_target, lines=5)
    assert len(ov._group._blocks) == 5
