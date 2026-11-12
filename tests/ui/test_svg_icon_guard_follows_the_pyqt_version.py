"""The SVG guard holds below PyQt6 6.11 only (decision Q35, 2026-11-13).

`certus_icon` returned an empty icon on Windows with CPython >= 3.14, whatever the PyQt6 version: every SVG icon of the
suite was invisible on the owner's machine (PyQt6 6.11.0, CPython 3.15.2), where 84 480 renders measured no crash.
"""

from __future__ import annotations

import sys

import pytest

from certus.ui import certus_icons


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CERTUS_SVG_ICONS", raising=False)


@pytest.mark.parametrize(("version", "disabled"), [((6, 10), True), ((6, 11), False), ((7, 0), False)])
def test_the_guard_depends_on_the_pyqt_version_on_windows(monkeypatch, version, disabled) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "version_info", (3, 15, 2, "final", 0))
    monkeypatch.setattr(certus_icons, "_pyqt_version", lambda: version)

    assert certus_icons.is_svg_icon_rendering_disabled() is disabled


def test_the_environment_still_turns_the_icons_off(monkeypatch) -> None:
    monkeypatch.setenv("CERTUS_SVG_ICONS", "0")

    assert certus_icons.is_svg_icon_rendering_disabled() is True
