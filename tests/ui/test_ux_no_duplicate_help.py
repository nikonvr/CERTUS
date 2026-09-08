"""No window may offer two controls that say the same thing (plan UX, 4.4).

SMOOTHER showed two buttons reading "Help": the shared window chrome, which
opens the module documentation, and one of its own, which pops a short usage
reminder. Two different destinations behind one word - the operator cannot
choose, and will suspect one of them is broken.

🔑 The fix is NOT to delete one. They do different things, and removing the
module's own button would lose the short guide. What was wrong is that both
were called the same.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

from scripts.audit_ux_certus import MODULES


@pytest.fixture(scope="module", params=list(MODULES.keys()))
def window(request, qapp):
    from PyQt6.QtCore import Qt

    modname, clsname = MODULES[request.param]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1920, 1080)
    win.show()
    win._certus_tag = request.param
    try:
        yield win
    finally:
        win.close()


def _button_captions(win) -> list[str]:
    from PyQt6.QtWidgets import QPushButton, QToolButton

    out = []
    for b in win.findChildren((QPushButton, QToolButton)):
        if not b.isVisible():
            continue
        caption = b.text().replace("&", "").strip()
        # Strip a leading pictogram so "X Help" and "Help" do not look distinct.
        caption = "".join(ch for ch in caption if ch.isalnum() or ch.isspace()).strip()
        if caption:
            out.append(caption.casefold())
    return out


def test_there_are_buttons_to_inspect(window):
    """Contrôle négatif : no caption would make the guard pass on anything."""
    assert len(_button_captions(window)) >= 3, f"{window._certus_tag}: almost no button found"


def test_no_two_buttons_claim_to_be_the_help(window):
    captions = _button_captions(window)
    helps = [c for c in captions if c == "help"]
    assert len(helps) <= 1, (
        f"{window._certus_tag}: {len(helps)} buttons both labelled 'Help', for two "
        "different destinations - the operator cannot tell which is which"
    )
