"""Read-only UX probes; all UI preferences isolated by the repository harness."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path.cwd()
OUT = ROOT / "reports" / "audit_ux_2026-10-02"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "audit_dependencies"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
from scripts import audit_ux_certus as audit


def spin(seconds=0.6):
    from PyQt6.QtWidgets import QApplication
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        QApplication.processEvents()
        time.sleep(0.02)


def run(tag):
    from PyQt6.QtGui import QPalette
    from PyQt6.QtWidgets import QLabel, QMessageBox, QWidget
    results = {"app": tag}
    original = audit.low_contrast_sheets
    calls = 0

    def inspect(win, minimum=4.5):
        nonlocal calls
        calls += 1
        result = original(win, minimum)
        if calls != 2:
            return result
        results["dark_palette_labels"] = [
            {"text": w.text(), "name": w.objectName(), "text_colour": w.palette().color(QPalette.ColorRole.WindowText).name(), "mid_colour": w.palette().color(QPalette.ColorRole.Mid).name(), "style": w.styleSheet()}
            for w in win.findChildren(QLabel)
            if w.isVisible() and w.objectName() in ("empty-title", "empty-desc", "coach-title", "coach-body")
        ]
        for w in list(win.findChildren(QWidget)):
            if type(w).__name__ == "_OnboardingOverlay" and w.isVisible():
                w._on_skip()
        spin()
        win.grab().save(str(OUT / f"{tag}_1366x768_sans_tutoriel_dark.png"))
        toggles = [w for w in win.findChildren(QWidget) if type(w).__name__ == "CertusThemeToggle"]
        if toggles:
            toggles[0].toggle()
        spin()
        win.grab().save(str(OUT / f"{tag}_1366x768_sans_tutoriel_light.png"))

        if tag == "CERTUS_FIELD":
            import certus.ui.certus_base_app_run_mixin as run_mixin
            import certus.ui.certus_io_ui as io_ui
            messages = []
            errors = []
            bad_path = OUT / "invalide_field.json"
            bad_path.write_text("{", encoding="utf-8")
            def dismissed(msg):
                errors.append(msg.text())
                return 0
            with patch.object(run_mixin, "show_toast", lambda _w, text, level: messages.append({"text": text, "level": level})), patch.object(QMessageBox, "exec", dismissed), patch.object(io_ui, "set_certus_last_dir", lambda *_: None):
                win._handle_dropped_file(str(bad_path))
            results["invalid_drop"] = {"error_dialogs": errors, "toasts": messages}
            before = win.edit_lcalc.text()
            win.edit_lcalc.setText("1234.0")
            prompts = []
            from PyQt6.QtGui import QCloseEvent
            event = QCloseEvent()
            with patch.object(win, "confirm_destructive", lambda *a, **kw: prompts.append(str(a)) or True):
                allowed = win.confirm_close_during_run(event)
            results["unsaved_idle_close_guard"] = {"before": before, "edited": win.edit_lcalc.text(), "workers_running": win.running_worker_count(), "close_allowed": allowed, "prompts": prompts}
            win.edit_lcalc.setText(before)
            from PyQt6.QtGui import QShortcut
            stops = []
            confirmations = []
            escapes = [s for s in win.findChildren(QShortcut) if s.key().toString() == "Esc"]
            with patch.object(win.worker_manager, "stop_all", lambda: stops.append("stop_all")), patch.object(QMessageBox, "exec", lambda msg: confirmations.append(msg.text()) or 0):
                for shortcut in escapes:
                    shortcut.activated.emit()
            results["escape_action"] = {"shortcuts": len(escapes), "stop_calls": stops, "confirmation_dialogs": confirmations}
        results["render_note"] = "Qt offscreen; onboarding skipped by its normal callback; no calculation launched."
        return result

    audit.low_contrast_sheets = inspect
    audit._measure(tag, *audit.MODULES[tag], 1366, 768)
    (OUT / f"probe_{tag}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        tree = ast.parse((ROOT / "CERTUS_HUB.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_module_for_dropped_file")
        scope = {"Path": Path}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "CERTUS_HUB.py", "exec"), scope)
        paths = ["mon_projet.json", "config_RE.json", "metal_bilayer_config.json", "field_config.json", "mesures_RE.xlsx"]
        routing = {p: scope[node.name](None, p) for p in paths}
        (OUT / "probe_routage.json").write_text(json.dumps(routing, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ROUTAGE=" + json.dumps(routing), flush=True)
        for tag in ["CERTUS_FIELD", "CERTUS_RE", "CERTUS_INDEX_SPLINE", "CERTUS_STRAT", "CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER"]:
            proc = subprocess.run([sys.executable, __file__, tag], capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            (OUT / f"probe_{tag}.log").write_text(proc.stdout + "\nSTDERR\n" + proc.stderr, encoding="utf-8")
            print(f"PROBE {tag}: exit={proc.returncode}", flush=True)
