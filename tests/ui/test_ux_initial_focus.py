"""The keyboard must not land on Help when a window opens (step 2.23).

Measured 2026-09-05 on shown windows - WA_DontShowOnScreen makes focusWidget()
useless, so these are really shown on the offscreen platform:

    CERTUS_DESIGN  focus=QToolButton  text='Help'
    CERTUS_RE      focus=QToolButton  text='Help'
    CERTUS_INDEX   focus=QToolButton  text='Help'
    CERTUS_FIELD   focus=QToolButton  text='Help'

So pressing Space on a freshly opened window opens the documentation, and the
tab chain starts with the help button, the theme toggle and the toolbar before
reaching any field the operator came for.

The chrome of a window - help, theme, toolbar - is reachable by its shortcut and
by the mouse. It has no business holding the keyboard focus.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "__CERTUS_FOCUS_TEST__"

MODULES_UNDER_TEST = [
    "CERTUS_DESIGN",
    "CERTUS_STRAT",
    "CERTUS_RE",
    "CERTUS_INDEX",
    "CERTUS_FIELD",
    "CERTUS_METAL_SINGLE",
]

#: What matters is not the LABEL but the KIND: Space on a button runs something,
#: Space on a scroll area scrolls and Space in a field types. So the criterion is
#: "the focus must not sit on a button", not "not on a button named Help" - the
#: first version of this test used labels and passed a window focused on
#: "Capture".


def _worker_main(tag: str) -> None:
    import time

    sys.path.insert(0, str(ROOT))
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_focus_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtWidgets import QApplication

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.show()
    win.activateWindow()

    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)

    focused = win.focusWidget()
    from PyQt6.QtWidgets import QAbstractButton

    out = {
        "cls": type(focused).__name__ if focused is not None else None,
        "text": (focused.text() if focused is not None and hasattr(focused, "text") else ""),
        "is_button": isinstance(focused, QAbstractButton),
    }
    win.close()
    print(MARKER + json.dumps(out, ensure_ascii=False))


@pytest.mark.parametrize("tag", MODULES_UNDER_TEST)
def test_the_help_button_does_not_hold_the_focus(tag: str) -> None:
    """Space on a fresh window must not open the documentation."""
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--worker", tag],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(MARKER)]
    assert hit, f"Worker crashed for {tag}:\n{proc.stderr}"
    row = json.loads(hit[0][len(MARKER) :])

    assert not row["is_button"], (
        f"{tag} opens with the focus on {row['cls']} {row['text']!r}: "
        f"Space triggers it before the operator has touched anything"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2])
        sys.exit(0)
