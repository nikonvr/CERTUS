"""A button that carries a caption is at least as wide as the suite's click-target floor (audit v2, plan S6, UX-22).

Measured 2026-10-01 with `scripts/audit_ux_certus.py`, every module of the suite had at least one captioned button narrower than 60 px:

    the "Help" button of the header          45 px  (a fixed 45 x 45 square, in all 11 windows)
    the toolbar of a scientific plot         "Reset" 52, "Detach" 59, "CSV" 42 px  (the width of their own letters plus 4 px of padding)
    the "Skip" button of the guided tour     58 px

The floor is `ClickTarget.MIN_WIDTH`. The harness keeps its own copy (`BUTTON_MIN_W`) because it measures from outside; the first test
pins the two together so that neither can move alone. The widths of the whole suite are pinned by the ratchet baselines
(`ux_baseline*.json`, `btn_narrow`), which are now zero.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton, QWidget

from certus.utils.certus_ux import ClickTarget
from scripts.audit_ux_certus import BUTTON_MIN_H, BUTTON_MIN_W


def test_the_app_and_the_harness_agree_on_the_floor():
    assert ClickTarget.MIN_WIDTH == BUTTON_MIN_W
    assert ClickTarget.MIN_HEIGHT == BUTTON_MIN_H


def test_the_floor_is_a_real_constraint():
    """Negative control: a floor of a few pixels would let every button pass."""
    assert ClickTarget.MIN_WIDTH >= 48


def test_the_help_button_of_the_header_meets_the_floor(qapp):
    from certus.ui.certus_ui_widgets_factory import create_header_logo_widget

    header = create_header_logo_widget(title_text="Width test", module_name="TEST")
    try:
        header.resize(900, 70)
        header.show()
        QApplication.processEvents()
        (help_button,) = [b for b in header.findChildren(QToolButton) if b.text() == "Help"]
        assert help_button.width() >= ClickTarget.MIN_WIDTH
    finally:
        header.close()


def test_every_captioned_button_of_a_plot_toolbar_meets_the_floor(qapp):
    from certus.ui.certus_plot import CertusScientificPlot

    host = QWidget()
    plot = CertusScientificPlot(host)
    try:
        toolbar = plot.get_toolbar(host)
        toolbar.resize(900, 34)
        toolbar.show()
        QApplication.processEvents()
        captioned = {b.text().strip(): b for b in toolbar.findChildren(QToolButton) if b.text().strip()}
        # the six captions of the bar: the test must see all of them, or it measures nothing
        assert {"Reset", "Detach", "CSV", "Export"} <= set(captioned), sorted(captioned)
        narrow = {caption: b.width() for caption, b in captioned.items() if b.width() < ClickTarget.MIN_WIDTH}
        assert not narrow, f"narrower than {ClickTarget.MIN_WIDTH} px: {narrow}"
    finally:
        host.close()


def test_the_buttons_of_the_guided_tour_meet_the_floor(qapp, monkeypatch):
    from certus.ui import certus_onboarding
    from certus.ui.certus_onboarding import TourStep, run_onboarding
    from certus.ui.certus_ui_utils import apply_certus_theme

    monkeypatch.setattr(certus_onboarding, "mark_completed", lambda *args, **kwargs: None)
    host = QWidget()
    host.resize(900, 600)
    # The sheet every window of the suite carries: without it the native style keeps a 75 px floor under a push button and the test
    # would measure a widget that the application never shows.
    apply_certus_theme(host)
    host.show()
    try:
        assert run_onboarding(host, "width_test", [TourStep(title="Step", body="What this step shows.")], force=True) == "running"
        QApplication.processEvents()
        captions = {b.text(): b.width() for b in host.findChildren(QPushButton)}
        assert {"Skip", "Back", "Finish"} <= set(captions), captions
        narrow = {caption: width for caption, width in captions.items() if width < ClickTarget.MIN_WIDTH}
        assert not narrow, f"narrower than {ClickTarget.MIN_WIDTH} px: {narrow}"
    finally:
        host.close()
