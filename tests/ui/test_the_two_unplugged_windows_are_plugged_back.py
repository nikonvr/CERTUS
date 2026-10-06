"""Two windows were unplugged, and the owner decided on 2026-10-06 to plug them back.

STRAT showed the generic welcome page (`certus_ui_widgets_welcome`, the application name and nothing else) while its own
page, `certus_strat_welcome_ui` (the steps of a STRAT run and the readiness of the system), was imported by nothing. And
the live n, k monitor of INDEX SPLINE (`certus_index_spline_monitor_ui.LiveIndexMonitor`), which the optimization
still feeds through `_update_persistent_nk_monitor`, was opened by nothing since 2026-07-03: the Smart Init preview used
to open it beside itself.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "unplugged windows", main_windows_only=True)


def test_strat_shows_its_own_welcome_page(qapp):
    from certus.ui import certus_strat_welcome_ui
    from certus.ui.certus_strat_ui import CertusSTRATApp

    window = CertusSTRATApp()

    assert type(window.welcome_widget) is certus_strat_welcome_ui.WelcomeGuideWidget


def test_strat_s_welcome_page_counts_the_materials_of_its_database(qapp, monkeypatch):
    from PyQt6.QtWidgets import QLabel

    from certus.ui import certus_strat_welcome_ui

    class _Db:
        def __init__(self) -> None:
            self.materials = {"H800-Nb2O5": None, "H800-SiO2": None, "Ta2O5": None}

    monkeypatch.setitem(certus_strat_welcome_ui.APP_CONTEXT, "materials_db", _Db())
    page = certus_strat_welcome_ui.WelcomeGuideWidget()

    texts = [label.text() for label in page.findChildren(QLabel)]
    assert "<b>3 Materials</b>" in texts  # it read a `data` attribute STRAT's database does not have, and showed 0


def test_the_smart_init_preview_opens_the_live_nk_monitor_beside_it(qapp, monkeypatch):
    import certus.spline.certus_index_spline_smart_init as smart_init
    from certus.ui.certus_index_spline_monitor_ui import LiveIndexMonitor
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    class _Preview:
        def __init__(self, parent, payload):
            self.dlg = QDialog(parent)
            self.dlg.exec = lambda: QDialog.DialogCode.Rejected

    monkeypatch.setattr(smart_init, "SmartInitPreviewManager", _Preview)
    window = CertusIndexSplineApp()

    window._show_smart_init_preview_dialog(payload=object())

    monitor = getattr(window, "_live_nk_monitor", None)
    assert isinstance(monitor, LiveIndexMonitor)
    assert monitor.isVisible()
    monitor.close()
