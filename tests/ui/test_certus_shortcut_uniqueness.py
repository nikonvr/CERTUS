"""Guardrail: no CERTUS window may bind one key sequence twice.

Qt arbitrates QShortcut and QAction in a single table. When two of them carry
the same sequence on one window, Qt emits ``activatedAmbiguously`` and runs
NEITHER handler - the shortcut is silently dead.

Measured on 2026-09-03 before the fix, with ``QTest.keyClick`` and the real
handlers disconnected:

    CERTUS_INDEX   Ctrl+K -> activated=[]  activatedAmbiguously=['Ctrl+K']
    CERTUS_INDEX   Ctrl+0 -> activated=[]  activatedAmbiguously=['Ctrl+0']

Ctrl+K (command palette) was dead in the 5 apps installing it, F1 in 6 of 9,
Ctrl+0 in 7 of 9, and F5 (Run) in CERTUS-INDEX-SPLINE. These tests fail on the
code that preceded ``install_unique_shortcut`` / ``claim_shortcut_for_action``.
"""

from __future__ import annotations

from collections import Counter

import pytest
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

APP_TARGETS = [
    ("CERTUS_DESIGN", "certus.ui.certus_design_ui", "CertusDesignApp"),
    ("CERTUS_STRAT", "certus.ui.certus_strat_ui", "CertusStratApp"),
    ("CERTUS_INDEX", "certus.ui.certus_index_ui", "CertusIndexApp"),
    ("CERTUS_FIELD", "certus.ui.certus_field_ui", "CertusFieldApp"),
    ("CERTUS_HUB", "CERTUS_HUB", "CertusHub"),
]

# Sequences that must resolve to exactly one handler per window.
WINDOW_LEVEL_SEQUENCES = ("Ctrl+K", "Ctrl+0", "F1", "F5", "Esc", "Ctrl+S", "Ctrl+E")


def _norm(seq) -> str:
    return QKeySequence(seq).toString()


def _window_level_bindings(window) -> Counter:
    """Count window-scope bindings per sequence (QShortcut + menu QAction)."""
    counts: Counter = Counter()
    for sc in window.findChildren(QShortcut):
        text = _norm(sc.key())
        if not text:
            continue
        # Widget-scoped shortcuts (e.g. per-plot export) only compete when the
        # focus sits inside that widget; they are counted separately below.
        if sc.context().name in ("WindowShortcut", "ApplicationShortcut"):
            counts[text] += 1
    for act in window.findChildren(QAction):
        for ks in act.shortcuts():
            text = _norm(ks)
            if text:
                counts[text] += 1
    return counts


@pytest.mark.ui
@pytest.mark.parametrize("name,module,cls_name", APP_TARGETS)
def test_no_ambiguous_window_shortcut(qapp, name, module, cls_name) -> None:
    """Every vital sequence resolves to at most one window-level handler."""
    _ = qapp
    cls = getattr(__import__(module, fromlist=[cls_name]), cls_name)
    window = cls()
    try:
        counts = _window_level_bindings(window)
        duplicated = {seq: n for seq, n in counts.items() if n > 1 and seq in WINDOW_LEVEL_SEQUENCES}
        assert not duplicated, (
            f"{name}: sequences bound more than once at window level -> Qt runs neither handler: {duplicated}"
        )
    finally:
        window.close()


@pytest.mark.ui
def test_plot_export_does_not_collide_with_command_palette(qapp) -> None:
    """The per-plot 'copy for publication' must not reuse the palette sequence.

    Ctrl+Shift+P belongs to CertusBaseApp's command palette. CertusScientificPlot
    used it too (WidgetWithChildren scope), so with the focus inside any plot
    both were candidates and neither ran.
    """
    _ = qapp
    from certus.ui.certus_plot import CertusScientificPlot

    plot = CertusScientificPlot(title="probe")
    try:
        sequences = {_norm(sc.key()) for sc in plot.findChildren(QShortcut)}
        assert "Ctrl+Shift+P" not in sequences, "plot shortcut still collides with the command palette"
        assert "Ctrl+Shift+B" in sequences, "publication-copy shortcut is missing"
    finally:
        plot.deleteLater()


@pytest.mark.ui
def test_install_standard_shortcuts_is_idempotent(qapp) -> None:
    """Calling it twice must not double-bind - several apps do call it twice."""
    _ = qapp
    from PyQt6.QtWidgets import QMainWindow

    from certus.ui.certus_ui_utils import install_standard_shortcuts

    window = QMainWindow()
    try:
        noop = lambda: None  # noqa: E731 - a bare callable is all we need here
        for _ in range(2):
            install_standard_shortcuts(window, run=noop, stop=noop, reset_zoom=noop)
        counts = Counter(_norm(sc.key()) for sc in window.findChildren(QShortcut))
        for seq in ("F5", "Esc", "Ctrl+0"):
            assert counts[seq] == 1, f"{seq} bound {counts[seq]} times after two calls"
    finally:
        window.close()


@pytest.mark.ui
def test_unresolvable_sequences_are_not_installed(qapp) -> None:
    """Qt 6 maps 'Ctrl+Plus' and friends to an EMPTY sequence: a dead shortcut."""
    _ = qapp
    from PyQt6.QtWidgets import QMainWindow

    from certus.ui.certus_ui_utils import install_unique_shortcut

    window = QMainWindow()
    try:
        for dead in ("Ctrl+Plus", "Ctrl+Minus", "Ctrl+Equal", "Ctrl+Underscore"):
            assert _norm(dead) == "", f"{dead} unexpectedly resolves on this Qt build"
            assert install_unique_shortcut(window, dead, lambda: None) is None
        assert not window.findChildren(QShortcut)
    finally:
        window.close()
