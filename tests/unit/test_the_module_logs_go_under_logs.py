"""A module's log file goes under `logs/`, not in the working folder (2026-11-13).

`CERTUS_DESIGN.py` asks for `certus_design.log`, `CERTUS_FIELD.py` for `field.log`...: a bare name was opened in the
working folder, so every run from the repository left `*.log` and `*.jsonl` at its root, beside the sources. A bare
name now goes under `logs/`, where the default journal `logs/CERTUS.jsonl` already was; a path with a folder is kept.
"""

from __future__ import annotations

import logging
from pathlib import Path

from certus.core.certus_logging import _log_path, setup_logging


def test_a_bare_name_goes_under_logs_and_a_path_is_kept(tmp_path):
    assert _log_path("certus_design.log") == Path("logs") / "certus_design.log"
    assert _log_path("sub/run.log") == Path("sub/run.log")
    assert _log_path(str(tmp_path / "run.log")) == tmp_path / "run.log"


def test_a_module_run_leaves_nothing_in_the_working_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = setup_logging(log_file="certus_design.log", level=logging.INFO)
    try:
        logger.info("one line")
        for handler in logger.handlers:
            handler.flush()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["logs"]
        assert {p.name for p in (tmp_path / "logs").iterdir()} >= {"certus_design.log", "certus_design.jsonl"}
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
