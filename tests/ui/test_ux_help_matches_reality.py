"""The shortcuts overlay must list what the window DOES, not what it declares.

CommandAction.shortcut is a documentation string, not a binding
(certus/utils/certus_command_palette.py). collect_window_shortcuts copied it into
the F1 overlay without ever checking that the sequence was installed, so the help
promised keys that do nothing.

Measured 2026-09-05, one process per module, announced vs actually bound:

    CERTUS_DESIGN        20 announced / 21 bound   phantom: Ctrl+R, Ctrl+W
    CERTUS_STRAT         17 announced / 20 bound   phantom: none
    CERTUS_METAL_SINGLE  16 announced / 15 bound   phantom: Ctrl+O "Load
                                                   configuration...", Ctrl+S
                                                   "Save configuration...",
                                                   Ctrl+R, Ctrl+W

An operator who presses Ctrl+S on METAL because the help says so loses nothing -
and learns that the help lies. Which is worse than no help.
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
MARKER = "__CERTUS_HELP_REALITY__"

MODULES_UNDER_TEST = [
    "CERTUS_DESIGN",
    "CERTUS_STRAT",
    "CERTUS_RE",
    "CERTUS_INDEX",
    "CERTUS_FIELD",
    "CERTUS_METAL_SINGLE",
    "CERTUS_METAL_BILAYER",
]


def _worker_main(tag: str) -> None:
    import time

    sys.path.insert(0, str(ROOT))
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_help_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from certus.ui.certus_shortcuts_overlay import collect_window_shortcuts
    from certus.ui.certus_ui_utils import shortcut_owner
    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()

    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    phantom = {}
    for entry in collect_window_shortcuts(win):
        seq = getattr(entry, "sequence", "") or ""
        if seq and shortcut_owner(win, seq) is None:
            phantom[seq] = getattr(entry, "label", "?")
    win.close()
    print(MARKER + json.dumps({"phantom": phantom}, ensure_ascii=False))


@pytest.mark.parametrize("tag", MODULES_UNDER_TEST)
def test_help_announces_no_shortcut_the_window_lacks(tag: str) -> None:
    """Every sequence the overlay lists must be bound on that window."""
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
    phantom = json.loads(hit[0][len(MARKER) :])["phantom"]

    assert not phantom, f"{tag}: the help announces keys that do nothing: {phantom}"


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2])
        sys.exit(0)
