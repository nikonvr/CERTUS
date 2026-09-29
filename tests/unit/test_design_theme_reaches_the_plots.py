"""The compact theme of DESIGN is applied to the plots of the window.

`LayoutManager._apply_theme` listed the five plots of the window with
`getattr(self, "spectrum_plot", None)` and its four siblings, read on the manager, which holds
none of them: `_apply_certus_compact_theme` received five `None`, so the plots kept their own
white background at start-up and a change of theme (dark mode) left them as they were.
The owner accepted the change of rendering on 2026-09-29: the plots take the background of the
theme, `#eef2f7` in the light theme, and follow the dark mode.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN theme", main_windows_only=True)


def test_the_compact_theme_receives_the_plots_of_the_window(qapp, monkeypatch) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    received = []
    apply_theme = app._apply_certus_compact_theme
    monkeypatch.setattr(app, "_apply_certus_compact_theme", lambda plots: received.append(list(plots)))

    app.layout_manager._apply_theme()

    [plots] = received
    assert plots == [app.spectrum_plot, app.profile_plot, app.nk_plot, app.color_plot, app.plot_convergence]
    assert all(plot is not None for plot in plots)
    apply_theme(plots)  # the theme applies to these plots without raising


def test_the_plots_take_the_background_of_the_theme(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.ui.certus_theme import CertusTheme

    app = CertusDesignApp()

    app.layout_manager._apply_theme()

    plots = [app.spectrum_plot, app.profile_plot, app.nk_plot, app.color_plot, app.plot_convergence]
    assert [plot.backgroundBrush().color().name() for plot in plots] == [CertusTheme.BACKGROUND] * 5
