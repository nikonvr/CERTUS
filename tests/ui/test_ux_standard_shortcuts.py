"""install_standard_shortcuts must never drop a requested binding in silence.

Two defects measured 2026-09-05 in certus/ui/certus_ui_utils.py:

1. THE EXPORT OF RE VANISHED. The standard map says "export" -> Ctrl+E, but
   certus_re_layout_mixin.py:1055 binds Ctrl+E to _schedule_eval FIRST and then
   asks for export=self.export_excel at :1061. install_unique_shortcut skips a
   sequence already claimed - deliberately, because binding one twice makes Qt
   emit activatedAmbiguously and run NEITHER handler - so the export was simply
   never installed, and nothing said so.

2. THE ZOOM ENTRIES USED A DEAD SEQUENCE. The map declared "Ctrl+Plus" and
   "Ctrl+Minus", which QKeySequence resolves to an EMPTY sequence on Qt 6. Zoom
   only worked because an alias_map installed Ctrl++ / Ctrl+- ten lines below;
   the primary entries bound nothing at all.

A caller that asks for a binding and gets none must be told. Silence is what
made the first defect survive.
"""

from __future__ import annotations

import pytest


def test_standard_map_holds_no_unresolvable_sequence(qapp) -> None:
    """A sequence Qt parses to nothing can never fire."""
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import QWidget

    from certus.ui import certus_ui_utils as utils

    window = QWidget()
    try:
        installed = utils.install_standard_shortcuts(window, save=lambda: None)
        _ = installed
    finally:
        window.deleteLater()

    # The map lives inside the function; assert on the source, which is where the
    # dead constants were written.
    import inspect

    src = inspect.getsource(utils.install_standard_shortcuts)
    for line in src.splitlines():
        if '": ("' not in line:
            continue
        seq = line.split('": ("', 1)[1].split('"', 1)[0]
        assert QKeySequence(seq).toString(), f"the standard map declares {seq!r}, which resolves to nothing"


def test_a_requested_binding_that_cannot_be_installed_is_reported(qapp, caplog) -> None:
    """Asking for a callback and getting no binding must not pass unnoticed."""
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_ui_utils import install_standard_shortcuts

    window = QWidget()
    try:
        # Claim Ctrl+E first, exactly as RE does with its evaluate action.
        QShortcut(QKeySequence("Ctrl+E"), window, lambda: None)

        with caplog.at_level("WARNING", logger="CERTUS"):
            installed = install_standard_shortcuts(window, export=lambda: None)

        assert not any(k.startswith("export:") for k in installed), (
            "the sequence was free after all: this test no longer reproduces the case"
        )
        # getMessage() interpolates: the logger formats lazily, so `message`
        # would still hold the raw "%s ... %r" template.
        assert any("export" in r.getMessage().lower() for r in caplog.records), (
            "the export binding was dropped without a word"
        )
    finally:
        window.deleteLater()


@pytest.mark.parametrize("mod_path,cls_name", [("CERTUS_RE", "CertusREApp")])
def test_re_can_export_from_the_keyboard(qapp, mod_path, cls_name) -> None:
    """RE advertises an Excel export; a keyboard user must be able to reach it."""
    from certus.ui.certus_ui_utils import shortcut_owner

    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    try:
        bound = [seq for seq in ("Ctrl+E", "Ctrl+Shift+E") if shortcut_owner(win, seq)]
        assert len(bound) >= 2, (
            f"{cls_name} binds only {bound}: evaluate took Ctrl+E and the export got nothing"
        )
    finally:
        win.close()
