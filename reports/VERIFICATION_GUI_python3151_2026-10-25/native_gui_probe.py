"""Capture one native Windows GUI using the repository's existing UX audit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["CERTUS_CONFIG_DIR"] = str(HERE / "preferences")

from scripts import audit_ux_certus as audit

tag = sys.argv[1]
snapshots = {}
original_skeleton = audit.skeleton
original_frozen = audit.frozen_light_sheets


def capture(window, theme):
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    path = HERE / f"{tag}_{theme}.png"
    if not window.grab().save(str(path)):
        raise RuntimeError(f"Could not capture {path.name}")
    snapshots[theme] = {
        "file": path.name,
        "visible": window.isVisible(),
        "platform": app.platformName(),
        "width": window.width(),
        "height": window.height(),
    }


def capture_light(window):
    capture(window, "light")
    return original_skeleton(window)


def capture_dark(window, colours):
    capture(window, "dark")
    return original_frozen(window, colours)


audit.skeleton = capture_light
audit.frozen_light_sheets = capture_dark
module, cls = audit.MODULES[tag]
row = audit._measure(tag, module, cls, 1920, 1080)
row["native_snapshots"] = snapshots
row["audit_findings"] = audit._verdicts(row)
(HERE / f"{tag}_native.json").write_text(
    json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
)
if not snapshots or any(s["platform"] != "windows" or not s["visible"] for s in snapshots.values()):
    raise RuntimeError("The native GUI was not visible at capture time")
print(json.dumps({"app": tag, "captures": list(snapshots), "findings": row["audit_findings"]}, ensure_ascii=False))
