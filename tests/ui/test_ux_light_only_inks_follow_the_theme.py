"""The inks and fills that were written for the light theme only follow the theme (audit v2, plan S6.4b).

Each of these sites wrote a colour of the LIGHT palette as a literal, with no counterpart in the dark one, so after the toggle (or in a window
built dark) the ink was the one of the other theme on a background of this one:

    INDEX     the final equations      `#1e293b` on the dark window       (the token is TEXT_MAIN)
    FIELD     the Pareto explorer hint `#475569` on a dark dialog          (TEXT_SUB)
    STRAT     a layer card, done       `#15803d` text and a `#bbf7d0` border on the dark surface (SUCCESS, and a tint of it)
    STRAT     a layer card, pending    `rgba(255, 255, 255, 0.4)`: a WHITE veil, so a light grey card in the dark theme, lighter than the
              cards that are done (the veil is now the surface colour at 40 %, the same white in the light theme)
    plots     the toolbar              `#f8f9fa` / `#ddd` / `#e2e6ea` fixed: a LIGHT bar in the dark theme (its ink stayed readable, 17:1:
              the defect is the white bar, not the contrast)

Measured on the pixels, as in `test_ux_ink_follows_the_fill.py`.
"""

from __future__ import annotations

import os
from collections import Counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QLabel, QTabWidget, QWidget

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_theme import CertusTheme

MINIMUM = 4.5


@pytest.fixture(autouse=True)
def light_palette(qapp):
    """Every test starts and ends in the light palette AND the light application style: the two are process state, and a toggle that an
    earlier test clicked leaves the application dark (its palette, its sheet) whatever `CertusTheme.configure` says."""
    CertusTheme.configure("light")
    CertusTheme.apply_to_app(qapp, False)
    yield
    CertusTheme.configure("light")
    CertusTheme.apply_to_app(qapp, False)


def contrast_of(image: QImage, inset: int = 2) -> float:
    """WCAG contrast of an image: its dominant colour is the fill, the colour farthest from it is the ink."""
    box = image.copy(QRect(inset, inset, max(4, image.width() - 2 * inset), max(4, image.height() - 2 * inset)))
    counts = Counter(box.pixel(x, y) for y in range(box.height()) for x in range(box.width()))
    fill = QColor.fromRgb(counts.most_common(1)[0][0]).name()
    ink = max((QColor.fromRgb(p).name() for p in counts), key=lambda c: contrast_ratio(c, fill))
    return contrast_ratio(ink, fill)


def region_contrast(parent: QWidget, child: QWidget, inset: int = 2) -> float:
    """The contrast of `child` as `parent` paints it (a label has no background of its own: its fill is the parent's)."""
    QApplication.processEvents()
    rect = QRect(child.mapTo(parent, QPoint(0, 0)), child.size())
    return contrast_of(parent.grab(rect).toImage(), inset)


@pytest.fixture
def windows_with_memory_preference(monkeypatch):
    """The preference is kept in memory: a toggle must not write the user's own configuration."""
    from certus.core import certus_core
    from certus.ui import certus_ui_utils, certus_ui_widgets_utils

    state = {"mode": "light"}
    for module in (certus_core, certus_ui_utils, certus_ui_widgets_utils):
        if hasattr(module, "load_theme_config"):
            monkeypatch.setattr(module, "load_theme_config", lambda: state["mode"])
        if hasattr(module, "save_theme_config"):
            monkeypatch.setattr(module, "save_theme_config", lambda m: state.__setitem__("mode", m) or True)
    return state


def build_window(tag: str, qapp) -> QWidget:
    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    win = getattr(__import__(modname, fromlist=[clsname]), clsname)()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    return win


def click_toggle(win: QWidget, qapp) -> None:
    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle

    next(w for w in win.findChildren(QWidget) if isinstance(w, CertusThemeToggle)).toggle()
    qapp.processEvents()


# =============================================================================
# INDEX: the final equations


def test_the_final_equations_of_index_read_in_both_themes(qapp, windows_with_memory_preference):
    win = build_window("CERTUS_INDEX", qapp)
    try:
        label = win.lbl_final_eq
        tabs = win.eq_tab.parentWidget().parentWidget()
        if isinstance(tabs, QTabWidget):
            tabs.setCurrentWidget(win.eq_tab)
        qapp.processEvents()
        assert region_contrast(win.eq_tab, label) >= MINIMUM, "light, as built"
        click_toggle(win, qapp)
        assert windows_with_memory_preference["mode"] == "dark"
        assert region_contrast(win.eq_tab, label) >= MINIMUM, "dark, after one click"
        assert f"color: {CertusTheme.TEXT_MAIN}" in label.styleSheet()
    finally:
        win.close()
        CertusTheme.configure("light")


# =============================================================================
# FIELD: the hint of the Pareto explorer


def pareto_hint(win: QWidget) -> QLabel:
    assert win._ensure_pareto_ui()
    hint = next(lbl for lbl in win.pareto_window.findChildren(QLabel) if lbl.text().startswith("Double-click"))
    win.pareto_window.show()
    QApplication.processEvents()
    return hint


def test_the_pareto_hint_of_field_reads_when_built_before_the_click_and_when_built_after(qapp, windows_with_memory_preference):
    win = build_window("CERTUS_FIELD", qapp)
    try:
        hint = pareto_hint(win)
        assert region_contrast(win.pareto_window, hint) >= MINIMUM, "light"
        click_toggle(win, qapp)
        assert windows_with_memory_preference["mode"] == "dark"
        assert region_contrast(win.pareto_window, hint) >= MINIMUM, "built in light, then one click"
        win.pareto_window.close()
        win.pareto_window.deleteLater()
        win.pareto_window = None  # `_ensure_pareto_ui` builds the dialog again, now under the dark palette
        fresh = pareto_hint(win)
        assert region_contrast(win.pareto_window, fresh) >= MINIMUM, "built after the click"
        assert f"color: {CertusTheme.TEXT_SUB}" in fresh.styleSheet()
    finally:
        win.close()
        CertusTheme.configure("light")


# =============================================================================
# STRAT: a layer card


STATES = ("active", "done", "pending")


def card_in_a_scroll_area(state: str):
    """A card on the background of the scroll area that holds it in the window (`BACKGROUND`)."""
    from certus.ui.certus_strat_stack_progress_widget import LayerCard

    host = QWidget()
    host.setStyleSheet(f"QWidget#Host {{ background-color: {CertusTheme.BACKGROUND}; }}")
    host.setObjectName("Host")
    host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    host.resize(300, 60)
    card = LayerCard(1, "SiO2", 1.0, 100.0, parent=host)
    card.move(10, 10)
    card.resize(280, 36)
    card.set_state(state)
    host.show()
    QApplication.processEvents()
    return host, card


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("state", ["active", "done"])
def test_the_texts_of_a_layer_card_that_is_active_or_done_read(qapp, mode, state):
    CertusTheme.configure(mode)
    host, card = card_in_a_scroll_area(state)
    try:
        assert region_contrast(card, card.lbl_status) >= MINIMUM, ("status", mode, state)
        assert region_contrast(card, card.lbl_num) >= MINIMUM, ("number", mode, state)
    finally:
        host.close()


def test_a_pending_layer_card_is_dark_in_the_dark_theme_and_lighter_than_nothing_in_the_light_one(qapp):
    """A white veil made it a light grey box in the dark theme, brighter than the cards that are done."""

    def card_pixel(mode: str) -> QColor:
        CertusTheme.configure(mode)
        host, card = card_in_a_scroll_area("pending")
        try:
            image = host.grab().toImage()
            return image.pixelColor(card.x() + 4, card.y() + 18)  # inside the card, left of its number
        finally:
            host.close()

    dark = card_pixel("dark")
    light = card_pixel("light")
    assert dark.lightness() < 60, f"a pending card is a light box in the dark theme: {dark.name()}"
    assert light.lightness() > 230, f"a pending card is not light in the light theme: {light.name()}"


def test_a_layer_card_follows_the_theme_by_name(qapp):
    host, card = card_in_a_scroll_area("done")
    try:
        done = card.styleSheet()
        assert "border: 1px solid rgba(21, 128, 61, 0.3)/*A:SUCCESS:0.3*/" in done
        assert "color: #15803d/*T:SUCCESS*/" in card.lbl_status.styleSheet()
        CertusTheme.configure("dark")
        CertusTheme.refresh_widget_sheets()
        assert "border: 1px solid rgba(52, 211, 153, 0.3)/*A:SUCCESS:0.3*/" in card.styleSheet()
        assert "color: #34d399/*T:SUCCESS*/" in card.lbl_status.styleSheet()
        card.set_state("pending")
        assert "background-color: rgba(17, 24, 39, 0.4)/*A:SURFACE:0.4*/" in card.styleSheet()
        CertusTheme.configure("light")
        CertusTheme.refresh_widget_sheets()
        assert "background-color: rgba(255, 255, 255, 0.4)/*A:SURFACE:0.4*/" in card.styleSheet()
    finally:
        host.close()


# =============================================================================
# The toolbar of the plots


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_toolbar_of_a_plot_reads_in_both_themes(qapp, mode):
    from certus.ui.certus_plot import CertusScientificPlot

    CertusTheme.configure(mode)
    CertusTheme.apply_to_app(qapp, mode == "dark")
    host = QWidget()
    plot = CertusScientificPlot(host)
    try:
        toolbar = plot.get_toolbar(host)
        toolbar.resize(520, 34)
        toolbar.show()
        qapp.processEvents()
        image = toolbar.grab().toImage()
        assert contrast_of(image, 3) >= MINIMUM, mode
        bar = image.pixelColor(image.width() - 8, image.height() // 2)  # the right end of the bar, clear of the buttons
        assert (bar.lightness() < 80) == (mode == "dark"), f"the bar is {bar.name()} in the {mode} theme"
        assert (bar.lightness() > 200) == (mode == "light"), f"the bar is {bar.name()} in the {mode} theme"
    finally:
        host.close()
        CertusTheme.configure("light")
        CertusTheme.apply_to_app(qapp, False)


def test_the_toolbar_of_a_plot_takes_the_new_palette_at_the_click(qapp):
    from certus.ui.certus_plot import CertusScientificPlot

    host = QWidget()
    plot = CertusScientificPlot(host)
    try:
        toolbar = plot.get_toolbar(host)
        assert "background: #f8fafc/*T:SURFACE_HOVER*/" in toolbar.styleSheet()
        assert "QToolButton:hover { background-color: #d7dfe8/*T:BORDER*/; }" in toolbar.styleSheet()
        CertusTheme.configure("dark")
        CertusTheme.refresh_widget_sheets()
        assert "background: #1f2937/*T:SURFACE_HOVER*/" in toolbar.styleSheet()
        assert "border-bottom: 1px solid #2d3748/*T:BORDER*/" in toolbar.styleSheet()
        assert "QToolButton:hover { background-color: #2d3748/*T:BORDER*/; }" in toolbar.styleSheet()
    finally:
        host.close()
