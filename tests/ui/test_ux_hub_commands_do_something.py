"""The welcome window must not offer commands that do nothing (plan UX, 4.2).

The UX dossier records two broken commands on the HUB: "Show Details", said to
toggle something other than the log panel, and "Scientific Documentation", said
to render white on white. Both claims predate several refactors, so this guard
checks them instead of trusting them.

"Show Details" is verifiable: toggling it must change the log panel's
visibility. The documentation button is only checked for being wired to a
callable - what it renders is not something a headless test can judge.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


@pytest.fixture(scope="module")
def hub(qapp):
    from PyQt6.QtCore import Qt

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def test_show_details_reveals_the_log_panel(hub):
    """The button promises to show the launch logs - it must actually show them."""
    panel = hub.log_panel
    assert not panel.isVisible(), "the log panel starts visible - the toggle would be untestable"

    hub.btn_details.setChecked(True)
    hub.on_toggle_details(True)
    assert panel.isVisible(), (
        "'Show Details' left the log panel hidden: the button promises the launch logs and delivers nothing"
    )

    hub.btn_details.setChecked(False)
    hub.on_toggle_details(False)
    assert not panel.isVisible(), "'Show Details' cannot hide the panel again"


def test_show_details_toggles_the_panel_the_user_was_promised(hub):
    """It must be the log panel, not some other widget that happens to move."""
    assert hub.log_container is hub.log_panel, "btn_details toggles log_container, which is no longer the log panel"


def test_the_documentation_button_is_wired(hub):
    assert callable(getattr(hub, "open_documentation", None)), "the documentation button has no handler"


# =============================================================================
# STRAT - same promise, same contract
# =============================================================================


@pytest.fixture(scope="module")
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def test_strat_show_details_reveals_its_log_panel(strat):
    """A hidden panel must be re-openable, or its Copy button is unreachable.

    STRAT toggled the inner text widget only. Once the panel itself is honestly
    hidden, showing the child alone reveals nothing - the parent stays hidden.
    """
    panel = strat._log_panel
    assert not panel.isVisible(), "STRAT's log panel starts visible - nothing to toggle"

    strat.on_toggle_details(True)
    assert panel.isVisible(), (
        "'Show Details' does not re-open STRAT's log panel: its Copy Logs button is unreachable for the whole session"
    )

    strat.on_toggle_details(False)
    assert not panel.isVisible(), "STRAT cannot hide its log panel again"
