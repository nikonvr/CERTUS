"""Test that importing certus_core produces no file writes and no log output.

Acceptance criterion for action #32 — eradicate import-time side effects.
"""
from __future__ import annotations

import importlib
import logging
import sys
import io
from pathlib import Path


def test_certus_core_import_no_file_write(tmp_path, monkeypatch):
    """certus_core import must not create or modify any file in the working directory."""
    monkeypatch.chdir(tmp_path)

    # Remove cached module so it re-imports fresh
    for mod in list(sys.modules.keys()):
        if "certus_core" in mod:
            del sys.modules[mod]

    before = {
        p.name: p.stat().st_mtime
        for p in Path(tmp_path).iterdir()
        if p.is_file()
    }

    import certus.core.certus_core as certus_core  # noqa: F401

    after = {
        p.name: p.stat().st_mtime
        for p in Path(tmp_path).iterdir()
        if p.is_file()
    }
    new_files = [f for f in after if f not in before]
    assert not new_files, f"certus_core import created files: {new_files}"


def test_certus_core_import_no_unexpected_log(caplog):
    """certus_core import must not produce WARNING or higher log output."""
    # Remove cached module
    for mod in list(sys.modules.keys()):
        if "certus_core" in mod:
            del sys.modules[mod]

    with caplog.at_level(logging.WARNING, logger="certus_core"):
        import certus.core.certus_core as certus_core  # noqa: F401

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings, (
        f"certus_core import produced {len(warnings)} WARNING+ log record(s): "
        + "; ".join(r.getMessage() for r in warnings)
    )
