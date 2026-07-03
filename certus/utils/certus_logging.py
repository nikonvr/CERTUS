"""CERTUS structured logging helpers.

This module adds JSONL logging with contextual fields (run_id, app_id)
while preserving the existing human-readable console output.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class CertusJsonFormatter(logging.Formatter):
    """Render log records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "run_id": getattr(record, "run_id", None),
            "app_id": getattr(record, "app_id", None),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def attach_jsonl_handler(
    logger: logging.Logger,
    json_log_file: str | Path,
    *,
    level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """Attach a rotating JSONL file handler if not already attached."""

    target_path = Path(json_log_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            base_filename = getattr(handler, "baseFilename", "")
            if base_filename and Path(base_filename) == target_path:
                return

    json_handler = RotatingFileHandler(
        str(target_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    json_handler.setLevel(level)
    json_handler.setFormatter(CertusJsonFormatter())
    logger.addHandler(json_handler)


def get_structured_logger(
    logger: logging.Logger | logging.LoggerAdapter,
    *,
    run_context: "Any | None" = None,
    run_id: str | None = None,
    app_id: str,
) -> logging.LoggerAdapter:
    """Return a logger adapter that injects run metadata in every record."""
    
    actual_run_id = getattr(run_context, "run_id", run_id) if run_context else run_id

    if isinstance(logger, logging.LoggerAdapter):
        merged_extra = dict(getattr(logger, "extra", {}))
        merged_extra.update({"run_id": actual_run_id, "app_id": app_id})
        return logging.LoggerAdapter(logger.logger, extra=merged_extra)

    return logging.LoggerAdapter(logger, extra={"run_id": actual_run_id, "app_id": app_id})
