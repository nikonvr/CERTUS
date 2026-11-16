"""Excel exports are atomic and HTML reports declare their encoding (audit 2026-11-15, L4-m6, L5-m4, L4-m7).

L4-m6, L5-m4: the Excel exports wrote straight to the chosen path (pd.ExcelWriter, wb.save, to_excel); an error in
the middle left a truncated file over the previous one. They go through atomic_open, like the HTML ones.
L4-m7: generate_html_report wrote UTF-8 without a <meta charset>: lambda, mu and +- could be misread.
"""

from __future__ import annotations

import ast
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from certus.utils.certus_atomic_io import atomic_excel_writer, atomic_save_workbook

ROOT = Path(__file__).resolve().parents[2]
ATOMIC_MODULE = "certus/utils/certus_atomic_io.py"


def _direct_writes(path: Path) -> list[str]:
    """Calls that write an Excel file to a path: pd.ExcelWriter(<not a handle>), <x>.save(<path>), <df>.to_excel(<path>)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func, first = node.func, node.args[0]
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        target = ast.unparse(first)
        if name == "ExcelWriter" and target not in {"handle", "output", "buf", "b"}:
            found.append(f"{name}({target})")
        if name == "to_excel" and target not in {"writer", "w", "handle"}:
            found.append(f"{name}({target})")
        if name == "save" and isinstance(func, ast.Attribute) and ast.unparse(func.value).startswith(("wb", "workbook")):
            found.append(f"{ast.unparse(func.value)}.save({target})")
    return found


def test_no_excel_export_writes_straight_to_its_path() -> None:
    offenders = {}
    for path in sorted((ROOT / "certus").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel == ATOMIC_MODULE:
            continue
        hits = _direct_writes(path)
        if hits:
            offenders[rel] = hits
    assert not offenders, f"Excel written straight to its path, not through atomic_open: {offenders}"


def _write_then_fail(target: Path) -> None:
    with atomic_excel_writer(target) as writer:
        pd.DataFrame({"a": [2]}).to_excel(writer, index=False)
        raise RuntimeError("disk full")


def test_a_failed_excel_export_leaves_the_previous_file(tmp_path) -> None:
    target = tmp_path / "export.xlsx"
    with atomic_excel_writer(target) as writer:
        pd.DataFrame({"a": [1]}).to_excel(writer, index=False)
    before = target.read_bytes()
    with pytest.raises(RuntimeError):
        _write_then_fail(target)
    assert target.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["export.xlsx"]


def test_a_workbook_is_saved_whole(tmp_path) -> None:
    wb = openpyxl.Workbook()
    wb.active["A1"] = "λ (nm)"
    atomic_save_workbook(wb, tmp_path / "w.xlsx")
    assert openpyxl.load_workbook(tmp_path / "w.xlsx").active["A1"].value == "λ (nm)"


def test_l4_m7_the_html_report_declares_utf8(tmp_path) -> None:
    from certus.utils.certus_data import generate_html_report

    out = tmp_path / "r.html"
    generate_html_report(str(out), "λ report", [{"title": "λ", "type": "kv", "content": {"λ (nm)": "550"}}])
    head = out.read_text(encoding="utf-8")[:300].lower()
    assert "<meta charset='utf-8'>" in head or '<meta charset="utf-8">' in head
