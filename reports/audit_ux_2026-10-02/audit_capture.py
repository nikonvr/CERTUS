"""Capture the existing CERTUS audit without altering application code."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path.cwd()
OUT = ROOT / "reports" / "audit_ux_2026-10-02"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "audit_dependencies"))
from scripts import audit_ux_certus as audit


def worker(tag: str, width: int, height: int) -> None:
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QLabel, QTabWidget

    original = audit.low_contrast_sheets
    captures = []

    def capture(win, minimum=4.5):
        theme = "light" if not captures else "dark"
        stem = f"{tag}_{width}x{height}_{theme}"
        assert win.grab().save(str(OUT / f"{stem}.png"))
        widgets = []
        for w in audit.interactive_controls(win):
            p = w.mapTo(win, QPoint(0, 0))
            widgets.append({
                "class": type(w).__name__, "name": w.objectName(),
                "text": w.text() if hasattr(w, "text") else "",
                "accessible": audit.screen_reader_name(w),
                "tooltip": w.toolTip(), "enabled": w.isEnabled(),
                "geometry": [p.x(), p.y(), w.width(), w.height()],
            })
        tabs = [{"name": t.objectName(), "current": t.currentIndex(),
                 "tabs": [t.tabText(i) for i in range(t.count())]}
                for t in win.findChildren(QTabWidget)]
        texts = [w.text() for w in win.findChildren(QLabel) if w.isVisible()]
        (OUT / f"{stem}.json").write_text(json.dumps({"controls": widgets, "tabs": tabs, "labels": texts}, ensure_ascii=False, indent=2), encoding="utf-8")
        captures.append(stem)
        return original(win, minimum)

    audit.low_contrast_sheets = capture
    row = audit._measure(tag, *audit.MODULES[tag], width, height)
    row["issues"] = audit._verdicts(row)
    row["captures"] = captures
    print(audit.MARKER + json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        worker(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
    else:
        rows = []
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_FONTDIR=r"C:\Windows\Fonts", PYTHONIOENCODING="utf-8")
        for width, height in [(1920, 1080), (1366, 768)]:
            for tag in audit.MODULES:
                proc = subprocess.run([sys.executable, __file__, tag, str(width), str(height)], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150)
                (OUT / f"{tag}_{width}x{height}.log").write_text(proc.stdout + "\nSTDERR\n" + proc.stderr, encoding="utf-8")
                found = [s[len(audit.MARKER):] for s in proc.stdout.splitlines() if s.startswith(audit.MARKER)]
                row = json.loads(found[-1]) if found else {"app": tag, "ERROR": proc.stderr[-1000:]}
                row["process_exit_code"] = proc.returncode
                row["requested_size"] = [width, height]
                rows.append(row)
                (OUT / "mesures.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{tag} {width}x{height}: " + json.dumps(row.get("issues", row.get("ERROR")), ensure_ascii=False), flush=True)
        print(f"CAPTURE_DONE={len(rows)}", flush=True)
