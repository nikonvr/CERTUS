"""An export is either the old file or the complete new one, and nothing in `certus/` writes a file any other way.

Until 2026-09-30 seventeen places of `certus/` (the exports of the plots, the tables, the manifests, the spline reports,
the substrate, the STRAT strategies...) did `open(path, "w")` on the path the user had chosen. A writer that died in the middle
(a full disk, an exception while the table was being formatted, the process killed) left a truncated file over the copy
that was there, and the user found out when they opened it. `certus/utils/certus_atomic_io.py::atomic_open` writes to a
sibling temporary file and moves it over the target only when the block ended without an error.

Two halves: the helper does what it says, and a scan of `certus/` refuses a new `open(..., "w")` (a list of the few that
have a reason to stay).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from certus.utils.certus_atomic_io import atomic_open

ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# The helper
# =============================================================================


def _write_then_fail(target: Path, error: BaseException, text: str = "half of the new ") -> None:
    """Start an atomic write, write half of something, and die with `error`."""
    with atomic_open(target, "w") as f:
        f.write(text)
        raise error


def test_a_finished_block_replaces_the_target_with_the_complete_new_content(tmp_path) -> None:
    target = tmp_path / "export.json"
    target.write_text("old", encoding="utf-8")

    with atomic_open(target, "w", encoding="utf-8") as f:
        f.write("new content")

    assert target.read_text(encoding="utf-8") == "new content"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["export.json"]  # no temporary file left behind


def test_an_error_in_the_block_leaves_the_old_file_untouched_and_no_temporary_file(tmp_path) -> None:
    target = tmp_path / "export.csv"
    target.write_text("the copy that was there", encoding="utf-8")

    with pytest.raises(RuntimeError, match="died in the middle"):
        _write_then_fail(target, RuntimeError("the writer died in the middle"))

    assert target.read_text(encoding="utf-8") == "the copy that was there"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["export.csv"]


def test_a_block_that_dies_on_a_new_path_leaves_nothing_at_all(tmp_path) -> None:
    target = tmp_path / "never_written.txt"

    with pytest.raises(ValueError):
        _write_then_fail(target, ValueError("bad value"))

    assert list(tmp_path.iterdir()) == []


def test_an_interrupt_is_not_a_reason_to_leave_a_temporary_file(tmp_path) -> None:
    target = tmp_path / "export.txt"

    with pytest.raises(KeyboardInterrupt):
        _write_then_fail(target, KeyboardInterrupt())

    assert list(tmp_path.iterdir()) == []


def test_the_temporary_file_lives_next_to_the_target_so_that_the_move_stays_on_one_volume(tmp_path) -> None:
    target = tmp_path / "export.txt"

    with atomic_open(target, "w") as f:
        f.write("x")
        during = sorted(p.name for p in tmp_path.iterdir())
        assert not target.exists()  # nothing at the target until the block has ended

    assert len(during) == 1
    assert during[0].startswith(".export.txt.")
    assert during[0].endswith(".tmp")


def test_a_target_that_cannot_be_replaced_raises_and_leaves_no_temporary_file(tmp_path) -> None:
    target = tmp_path / "a_directory"
    target.mkdir()

    with pytest.raises(OSError), atomic_open(target, "w") as f:
        f.write("x")

    assert [p.name for p in tmp_path.iterdir()] == ["a_directory"]


def test_newline_is_the_one_of_open_a_csv_keeps_its_line_endings(tmp_path) -> None:
    target = tmp_path / "table.csv"

    with atomic_open(target, "w", newline="", encoding="utf-8") as f:
        f.write("a,b\r\n1,2\r\n")
    assert target.read_bytes() == b"a,b\r\n1,2\r\n"

    with atomic_open(target, "w", newline="", encoding="utf-8") as f:
        f.write("a\n")
    assert target.read_bytes() == b"a\n"  # no translation on Windows either: the mode `newline=""` of the csv module

    with atomic_open(target, "w", newline="\r\n", encoding="utf-8") as f:
        f.write("a\n")
    assert target.read_bytes() == b"a\r\n"  # and a chosen ending is applied on every system


def test_the_encoding_is_utf8_unless_told_otherwise(tmp_path) -> None:
    target = tmp_path / "unicode.txt"

    with atomic_open(target, "w") as f:
        f.write("epaisseur é → 200 nm")

    assert target.read_bytes() == "epaisseur é → 200 nm".encode()


def test_a_binary_file_is_written_as_bytes(tmp_path) -> None:
    target = tmp_path / "book.xlsx"

    with atomic_open(target, "wb") as f:
        f.write(b"PK\x03\x04 not really a workbook")

    assert target.read_bytes() == b"PK\x03\x04 not really a workbook"


@pytest.mark.parametrize("mode", ["a", "r", "x", "w+", "r+b", "ab"])
def test_only_whole_files_are_written_this_way(tmp_path, mode) -> None:
    with pytest.raises(ValueError, match="mode must be one of"), atomic_open(tmp_path / "f.txt", mode):
        pass


# =============================================================================
# The scan: nothing else in `certus/` opens a file for writing
# =============================================================================

#: (file -> why it may open a file for writing itself). A new entry needs a reason as good as these. The helper itself
#: opens its temporary file with a mode it received, which a scan of literals does not see.
ALLOWED = {
    "certus/core/certus_config.py": "its own temporary file, moved over the configuration by Path.replace (atomic as well)",
    "certus/core/certus_frozen_entry.py": "os.devnull, to silence the standard streams of a windowed executable",
}


def _writes(tree: ast.AST) -> list[int]:
    """The lines of the `open(...)` and `.open(...)` calls whose literal mode writes ("w" or "x")."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else ""
        if name != "open":
            continue
        # builtin open(file, mode): the mode is the second argument; Path.open(mode): the first
        position = 1 if isinstance(callee, ast.Name) else 0
        modes = [a for a in node.args[position : position + 1]] + [k.value for k in node.keywords if k.arg == "mode"]
        for mode in modes:
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wx"):
                lines.append(node.lineno)
    return lines


def _offenders() -> dict[str, list[int]]:
    found = {}
    for path in sorted((ROOT / "certus").rglob("*.py")):
        lines = _writes(ast.parse(path.read_text(encoding="utf-8-sig", errors="replace")))
        if lines:
            found[path.relative_to(ROOT).as_posix()] = lines
    return found


def test_no_file_of_certus_is_opened_for_writing_except_the_few_that_have_a_reason() -> None:
    offenders = {f: lines for f, lines in _offenders().items() if f not in ALLOWED}

    assert not offenders, (
        "these files open a file for writing themselves: a writer that dies leaves a truncated file over the user's copy. "
        f"Use `certus.utils.certus_atomic_io.atomic_open`: {offenders}"
    )


def test_every_allowed_file_still_opens_a_file_for_writing() -> None:
    stale = sorted(set(ALLOWED) - set(_offenders()))

    assert not stale, f"these no longer open a file for writing: remove them from ALLOWED: {stale}"


def test_the_scan_sees_the_ways_of_writing_it_is_meant_to_catch() -> None:
    code = ast.parse(
        "open('a.txt', 'w')\n"
        "open('b.bin', 'wb')\n"
        "open(p, mode='w', encoding='utf-8')\n"
        "p.open('w')\n"
        "p.open(mode='x')\n"
        "open('c.txt')\n"
        "open('d.txt', 'r')\n"
        "p.open('r')\n"
        "open('e.txt', 'a')\n"
    )

    assert _writes(code) == [1, 2, 3, 4, 5]  # reading and appending are not whole-file writes
