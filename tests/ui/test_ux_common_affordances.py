"""Every CertusBaseApp window must offer the common affordances (step 2.18).

CertusBaseApp._finalize_init installs, in one go: the command palette
(Ctrl+K / Ctrl+Shift+P), the shortcuts overlay (F1 / Shift+?), the zoom
shortcuts, the Help menu, the empty-state overlays and the accessible names.

DESIGN, STRAT and RE deliberately do NOT call it - they own their warmup and
timers, and each says so in a comment (certus_design_ui.py:197,
certus_strat_ui.py:165, CERTUS_RE.py:454). They therefore lost everything else
_finalize_init does, silently.

Measured 2026-09-04, one dedicated process per module:

    module   Ctrl+K   Help menu   fields with an accessible name
    DESIGN     no        no                0 / 58
    STRAT      no        no                0 / 59
    RE         no        no                0 /  6
    INDEX      yes       yes              18 / 18
    FIELD      yes       yes              21 / 21

The three most used modules of the suite: no command palette, no shortcuts
overlay reachable, no Help menu, and not one of 123 input fields carrying a name
a screen reader could announce.

One process per module, because QApplication state is a process global (rule
0.14 of the mission order).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "__CERTUS_AFFORDANCE_TEST__"

# Modules whose window derives from CertusBaseApp. The HUB is a plain
# QMainWindow (see step 2.18's own note) and is out of scope here.
BASE_APP_MODULES = [
    "CERTUS_DESIGN",
    "CERTUS_STRAT",
    "CERTUS_RE",
    "CERTUS_INDEX",
    "CERTUS_INDEX_SPLINE",
    "CERTUS_FIELD",
    "CERTUS_METAL_SINGLE",
    "CERTUS_METAL_BILAYER",
]


def _worker_main(tag: str) -> None:
    import time

    sys.path.insert(0, str(ROOT))
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QShortcut
    from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit, QMenuBar

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

    keys = {s.key().toString() for s in win.findChildren(QShortcut)}
    menus = set()
    for bar in win.findChildren(QMenuBar):
        for act in bar.actions():
            menus.add((act.text() or "").replace("&", "").strip().lower())
    fields = win.findChildren(QLineEdit) + win.findChildren(QAbstractSpinBox)

    out = {
        "palette": "Ctrl+K" in keys,
        "overlay": "F1" in keys,
        "help_menu": "help" in menus,
        "fields": len(fields),
        "named": sum(1 for f in fields if f.accessibleName()),
    }
    win.close()
    print(MARKER + json.dumps(out))


def _measure(tag: str) -> dict:
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
    return json.loads(hit[0][len(MARKER) :])


@pytest.mark.parametrize("tag", BASE_APP_MODULES)
def test_window_offers_the_common_affordances(tag: str) -> None:
    """Command palette, shortcuts overlay and Help menu, in every window."""
    row = _measure(tag)
    missing = [
        name
        for name, present in (
            ("command palette (Ctrl+K)", row["palette"]),
            ("shortcuts overlay (F1)", row["overlay"]),
            ("Help menu", row["help_menu"]),
        )
        if not present
    ]
    assert not missing, f"{tag} is missing: " + ", ".join(missing)


@pytest.mark.parametrize("tag", BASE_APP_MODULES)
def test_input_fields_carry_an_accessible_name(tag: str) -> None:
    """A field with no accessible name is unannounceable to a screen reader."""
    row = _measure(tag)
    if row["fields"] == 0:
        pytest.skip(f"{tag} has no input field to name")
    coverage = row["named"] / row["fields"]
    assert coverage >= 0.9, (
        f"{tag}: only {row['named']}/{row['fields']} input fields "
        f"({coverage:.0%}) carry an accessible name"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2])
        sys.exit(0)
