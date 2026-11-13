"""An error dialog says the cause and what to do, not the raw text of an exception (U11, constat A9).

Measured on 2026-11-13 by an AST scan: 43 `QMessageBox.critical` / `warning` calls inside an `except ... as e` put `e`
itself in their message ("[Errno 13] Permission denied: 'C:/.../run.xlsx'"). They go through
`certus.utils.errors.describe_error`, which turns the system exceptions into a cause and an action and keeps the text
of the exceptions the suite wrote for the operator.
"""

from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import pytest

from certus.utils.errors import describe_error

ROOT = Path(__file__).resolve().parents[2]


def _raw_exception_dialogs() -> list[str]:
    found = []
    for path in [*sorted((ROOT / "certus").rglob("*.py")), *sorted(ROOT.glob("CERTUS_*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for handler in ast.walk(tree):
            if not (isinstance(handler, ast.ExceptHandler) and handler.name):
                continue
            for call in ast.walk(handler):
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr in ("critical", "warning")
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "QMessageBox"
                    and len(call.args) > 2
                ):
                    continue
                described = {
                    id(n)
                    for c in ast.walk(call.args[2])
                    if isinstance(c, ast.Call)
                    and ((isinstance(c.func, ast.Name) and c.func.id == "describe_error") or (isinstance(c.func, ast.Attribute) and c.func.attr == "describe_error"))
                    for n in ast.walk(c)
                }
                read_as_attribute = {id(n.value) for n in ast.walk(call.args[2]) if isinstance(n, ast.Attribute)}
                raw = [
                    n
                    for n in ast.walk(call.args[2])
                    if isinstance(n, ast.Name) and n.id == handler.name and id(n) not in described and id(n) not in read_as_attribute
                ]
                if raw:
                    found.append(f"{path.relative_to(ROOT).as_posix()}:{call.lineno}")
    return found


def test_no_error_dialog_shows_the_raw_text_of_an_exception() -> None:
    found = _raw_exception_dialogs()
    assert found == [], f"{len(found)} dialogs show a raw exception: {found[:10]}"


@pytest.mark.parametrize(
    ("exc", "words"),
    [
        (PermissionError(13, "Permission denied", "run.xlsx"), "Close it"),
        (FileNotFoundError(2, "No such file", "gone.json"), "gone.json"),
        (json.JSONDecodeError("Expecting value", "{", 0), "not valid JSON"),
        (zipfile.BadZipFile("File is not a zip file"), "not a valid Excel workbook"),
        (KeyError("blocks"), "blocks"),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), "UTF-8"),
    ],
)
def test_a_system_exception_is_told_as_a_cause_and_an_action(exc, words) -> None:
    text = describe_error(exc)
    assert words in text
    assert "Errno" not in text


def test_a_message_written_for_the_operator_keeps_its_words() -> None:
    assert describe_error(ValueError("Thickness must be positive.")) == "Thickness must be positive."


def test_an_exception_without_text_still_says_something() -> None:
    assert "RuntimeError" in describe_error(RuntimeError())
