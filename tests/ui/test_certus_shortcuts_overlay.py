"""Tests for the CERTUS keyboard shortcuts overlay (U4)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# =============================================================================
# Pure-Python: data + collection + grouping
# =============================================================================


def test_u4_split_sequence_is_correct():
    from certus_shortcuts_overlay import _split_sequence

    assert _split_sequence("Ctrl+K") == ["Ctrl", "K"]
    assert _split_sequence("Ctrl+Shift+P") == ["Ctrl", "Shift", "P"]
    assert _split_sequence("F1") == ["F1"]
    assert _split_sequence("") == []
    assert _split_sequence(" Ctrl +  Alt + Del ") == ["Ctrl", "Alt", "Del"]


def test_u4_group_entries_sorts_and_preserves_categories():
    from certus_shortcuts_overlay import ShortcutEntry, group_entries

    entries = [
        ShortcutEntry("Ctrl+K", "Open command palette", "Navigation"),
        ShortcutEntry("Ctrl+S", "Save configuration", "File"),
        ShortcutEntry("Ctrl+O", "Load configuration", "File"),
        ShortcutEntry("F1", "Show shortcuts", "Help"),
    ]
    groups = group_entries(entries)
    # Categories are alphabetical
    assert list(groups.keys()) == ["File", "Help", "Navigation"]
    # File group is internally sorted by label
    assert [e.label for e in groups["File"]] == [
        "Load configuration",
        "Save configuration",
    ]


def test_u4_collect_window_shortcuts_uses_commands():
    """Duck-typed window with a ``_commands`` registry produces entries."""
    from certus_command_palette import CommandAction
    from certus_shortcuts_overlay import collect_window_shortcuts

    class _FakeWindow:
        def __init__(self, cmds):
            self._commands = cmds

        def findChildren(self, _cls):  # emulate Qt API
            return []

    cmds = [
        CommandAction(
            id="opt.run",
            title="Run optimization",
            shortcut="F5",
            category="Run",
            callback=lambda: None,
        ),
        CommandAction(
            id="opt.no_shortcut",
            title="Internal command",
            callback=lambda: None,
        ),  # no shortcut -> must be ignored
        CommandAction(
            id="file.save",
            title="Save configuration",
            shortcut="Ctrl+S",
            category="File",
            callback=lambda: None,
        ),
    ]
    entries = collect_window_shortcuts(_FakeWindow(cmds))
    seqs = [e.sequence for e in entries]
    # Only entries with a shortcut are returned
    assert "F5" in seqs and "Ctrl+S" in seqs
    assert len(entries) == 2


def test_u4_collect_window_shortcuts_dedup_qshortcut_vs_command():
    """A QShortcut with the same sequence as a CommandAction must not duplicate."""
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    from certus_command_palette import CommandAction
    from certus_shortcuts_overlay import collect_window_shortcuts

    w = QWidget()
    QShortcut(QKeySequence("Ctrl+S"), w)  # will appear as "Save configuration"

    class _Proxy:
        """Wrap w so we can inject a commands registry."""

        def __init__(self, widget, cmds):
            self._widget = widget
            self._commands = cmds

        def findChildren(self, cls):
            return self._widget.findChildren(cls)

    cmds = [
        CommandAction(
            id="file.save",
            title="Save configuration",
            shortcut="Ctrl+S",
            category="File",
            callback=lambda: None,
        ),
    ]
    entries = collect_window_shortcuts(_Proxy(w, cmds))
    ctrl_s = [e for e in entries if e.sequence == "Ctrl+S"]
    # Dedup: exactly one row for Ctrl+S
    assert len(ctrl_s) == 1
    # Command entry (priority) wins: source == "command"
    assert ctrl_s[0].source == "command"


def test_u4_collect_window_shortcuts_handles_fallback_label():
    """Unknown sequence must fall back to the raw sequence as label."""
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    from certus_shortcuts_overlay import collect_window_shortcuts

    w = QWidget()
    QShortcut(QKeySequence("Ctrl+Alt+Z"), w)

    class _Proxy:
        def __init__(self, widget):
            self._widget = widget
            self._commands = []

        def findChildren(self, cls):
            return self._widget.findChildren(cls)

    entries = collect_window_shortcuts(_Proxy(w))
    raw = [e for e in entries if e.sequence == "Ctrl+Alt+Z"]
    assert raw and raw[0].label == "Ctrl+Alt+Z"


# =============================================================================
# CertusBaseApp integration
# =============================================================================


def test_u4_certus_base_app_exposes_overlay_hook():
    from certus_ui import CertusBaseApp

    assert hasattr(CertusBaseApp, "open_shortcuts_overlay")
    assert callable(CertusBaseApp.open_shortcuts_overlay)


def test_u4_default_commands_include_show_shortcuts():
    from certus_ui import CertusBaseApp

    class _Stub:
        pass

    cmds = CertusBaseApp._default_commands(_Stub())
    ids = {c.id for c in cmds}
    assert "help.shortcuts" in ids
    shortcut_entry = next(c for c in cmds if c.id == "help.shortcuts")
    assert shortcut_entry.shortcut == "F1"


def test_u4_open_shortcuts_overlay_builds_dialog():
    """Integration: construct the dialog without exec() to verify wiring."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    from certus_command_palette import CommandAction
    from certus_shortcuts_overlay import ShortcutEntry, _build_dialog_class

    entries = [
        ShortcutEntry("Ctrl+S", "Save configuration", "File"),
        ShortcutEntry("F5", "Run", "Run"),
        ShortcutEntry("Ctrl+K", "Open command palette", "Navigation"),
    ]
    DialogCls = _build_dialog_class()
    dlg = DialogCls(None, entries)
    try:
        assert dlg.windowTitle() == "Keyboard shortcuts"
        # Dialog must contain all sequences somewhere in its children text.
        from PyQt6.QtWidgets import QLabel
        texts = [lbl.text() for lbl in dlg.findChildren(QLabel)]
        joined = " ".join(texts)
        for seq_token in ("Ctrl", "S", "F5", "K"):
            assert seq_token in joined
    finally:
        dlg.deleteLater()
