"""DESIGN's « Stack information » button opens its window.

CoreManager._show_substrate_info_window built the dialog as QDialog(self), the manager as
parent: Qt refuses a parent that is not a QWidget, so the button raised TypeError and no
window ever opened, from the split of the window into managers (c79316b, 2026-06-13) to
2026-09-29.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN stack information", main_windows_only=True)


def test_the_stack_information_window_opens_over_the_design_window(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()

    app._show_substrate_info_window()

    window = app.substrate_info_window
    assert window.isVisible()
    assert window.parent() is app
    window.close()
