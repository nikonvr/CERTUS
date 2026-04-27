"""Shared load-summary dialog for CERTUS modules."""

from __future__ import annotations

import functools
import html
from typing import Iterable


def build_summary_plain_text(
    title: str, lines: Iterable[tuple[str, bool] | str]
) -> str:
    normalized: list[tuple[str, bool]] = []
    substrate_txt: str | None = None
    faces_txt: str | None = None

    for row in lines:
        if isinstance(row, tuple):
            txt, suspicious = row
            txt_s = str(txt)
            susp = bool(suspicious)
        else:
            txt_s = str(row)
            susp = False

        upper = txt_s.strip().upper()
        if upper.startswith("SUBSTRATE:"):
            substrate_txt = txt_s.split(":", 1)[1].strip() if ":" in txt_s else txt_s.strip()
            continue
        if upper.startswith("FACES:"):
            faces_txt = txt_s.split(":", 1)[1].strip() if ":" in txt_s else txt_s.strip()
            continue
        normalized.append((txt_s, susp))

    if not substrate_txt:
        substrate_txt = "UNKNOWN"
    if not faces_txt:
        faces_txt = "ONE FACE (NO BACKSIDE)"

    out: list[str] = [title, "", f"SUBSTRATE: {substrate_txt}", f"FACES: {faces_txt}", ""]
    for txt_s, susp in normalized:
        out.append(f"!! {txt_s}" if susp else txt_s)
    return "\n".join(out)


def show_load_summary_dialog(parent, title: str, plain_text: str) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(860, 580)
    lay = QVBoxLayout(dlg)

    info = QLabel("Interpreted metadata only. Suspicious lines are shown in bold.")
    info.setWordWrap(True)
    lay.addWidget(info)

    html_lines: list[str] = []
    for ln in plain_text.splitlines():
        if ln.startswith("!! "):
            html_lines.append(f"<b>{html.escape(ln[3:])}</b>")
        else:
            html_lines.append(html.escape(ln))

    box = QTextEdit()
    box.setReadOnly(True)
    box.setHtml(
        "<pre style='font-family: Consolas, monospace;'>"
        + "\n".join(html_lines)
        + "</pre>"
    )
    lay.addWidget(box, 1)

    row = QHBoxLayout()
    btn_copy = QPushButton("Copy summary")
    btn_copy.clicked.connect(functools.partial(QApplication.clipboard().setText, plain_text))
    btn_close = QPushButton("Close")
    btn_close.clicked.connect(dlg.close)
    row.addWidget(btn_copy)
    row.addStretch()
    row.addWidget(btn_close)
    lay.addLayout(row)

    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dlg.show()
