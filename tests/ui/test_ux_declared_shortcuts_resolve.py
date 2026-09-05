"""A shortcut the palette advertises must be one the keyboard can produce.

Measured 2026-09-04 with Qt 6.11:

    QKeySequence("Ctrl+Plus").toString()   ->  ''      resolves to NOTHING
    QKeySequence("Ctrl+Minus").toString()  ->  ''      resolves to NOTHING
    QKeySequence("Ctrl++").toString()      ->  'Ctrl++'
    QKeySequence("Ctrl+-").toString()      ->  'Ctrl+-'

and yet the command palette declared "Ctrl+Plus" / "Ctrl+Minus" for zoom in
every module (certus/ui/mixins/certus_base_core_mixins.py:205 and :217). The
palette printed them verbatim, so the operator read an instruction that cannot
be typed. The Help MENU next to it already used the right sequences (:490-491)
and even carried a comment saying why - the palette was simply never updated.

CommandAction.shortcut is documentation, not a binding, which is exactly why it
needs a test: nothing else can contradict it.
"""

from __future__ import annotations

import pytest

CANDIDATES = ["CERTUS_DESIGN", "CERTUS_INDEX", "CERTUS_FIELD"]


@pytest.mark.parametrize("tag", CANDIDATES)
def test_every_declared_shortcut_resolves_to_a_real_sequence(qapp, tag) -> None:
    """No command may advertise a key sequence Qt cannot parse."""
    from PyQt6.QtGui import QKeySequence

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    try:
        actions = win._default_commands()
        unresolvable = {
            getattr(a, "id", "?"): a.shortcut
            for a in actions
            if getattr(a, "shortcut", None) and not QKeySequence(a.shortcut).toString()
        }
        assert not unresolvable, (
            f"{tag} advertises key sequences Qt resolves to nothing: {unresolvable}"
        )
    finally:
        win.close()
