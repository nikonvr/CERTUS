"""An information that asks no decision is a toast, not a modal dialog (U11, decision Q33).

Measured on 2026-11-13 by an AST scan: 77 `QMessageBox.information` calls, each stopping the work for a message that
asked nothing (43 of them in INDEX SPLINE). They go through `certus_ui_utils.notify`: a toast when short, the dialog
when the message is a document to read.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


#: The dialogs that stay, each for its reason: `notify` for a document, `_inform` of certus.utils for a parent outside
#: the suite (certus.utils does not import certus.ui), `_notify_user` when its caller asks to block (`blocking=True`),
#: and SMOOTHER's help, which the operator asked for (F1): content requested is not an interruption.
FALLBACKS = {
    ("certus_ui_utils.py", "notify"),
    ("certus_export.py", "_inform"),
    ("certus_index_ui_utils.py", "_notify_user"),
    ("certus_curve_smoother.py", "show_help"),
}


def _is_information(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "information"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "QMessageBox"
    )


def _information_calls() -> list[str]:
    found = []
    for path in [*sorted((ROOT / "certus").rglob("*.py")), *sorted(ROOT.glob("CERTUS_*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        allowed: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (path.name, node.name) in FALLBACKS:
                allowed |= {n.lineno for n in ast.walk(node) if hasattr(n, "lineno")}
        rel = path.relative_to(ROOT).as_posix()
        found.extend(f"{rel}:{n.lineno}" for n in ast.walk(tree) if _is_information(n) and n.lineno not in allowed)
    return found


def test_no_information_opens_a_modal_dialog_outside_notify() -> None:
    calls = _information_calls()
    assert calls == [], f"{len(calls)} modal information dialogs: {calls[:10]}"


def test_a_short_message_is_a_toast(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from certus.ui import certus_ui_utils

    dialogs = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: dialogs.append(a))
    host = QWidget()
    host.show()

    assert certus_ui_utils.notify(host, "Export", "Saved to results.csv.") == "toast"
    assert dialogs == []
    host.close()


def test_a_document_keeps_its_dialog(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from certus.ui import certus_ui_utils

    dialogs = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: dialogs.append(a))
    host = QWidget()

    report = "\n".join(f"layer {i}: 12.3 nm" for i in range(8))
    assert certus_ui_utils.notify(host, "Report", report) == "dialog"
    assert len(dialogs) == 1
    host.close()
