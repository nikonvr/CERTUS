from __future__ import annotations

import json
import logging
from pathlib import Path

from certus_logging import attach_jsonl_handler, get_structured_logger


def test_structured_logger_emits_run_context(tmp_path: Path) -> None:
    logger = logging.getLogger("CERTUS_TEST_STRUCTURED")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    jsonl_path = tmp_path / "certus_test.jsonl"
    attach_jsonl_handler(logger, jsonl_path)

    structured = get_structured_logger(
        logger,
        run_id="run-123",
        app_id="APP_X",
    )
    structured.info("hello-structured")

    assert jsonl_path.exists()
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert lines

    payload = json.loads(lines[-1])
    assert payload["message"] == "hello-structured"
    assert payload["run_id"] == "run-123"
    assert payload["app_id"] == "APP_X"
