"""CERTUS logging helpers extracted from the core module."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path


from certus.utils.certus_logging import attach_jsonl_handler

MAX_LOG_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_LOG_BACKUP_FILES = 3


def _supports_color() -> bool:
    if os.environ.get("CERTUS_NO_COLOR", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform != "win32":
        return True
    return "ANSICON" in os.environ or "WT_SESSION" in os.environ or os.environ.get("TERM") == "xterm-256color"


def _supports_utf8() -> bool:
    try:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        return "utf" in encoding.lower()
    except Exception:
        return False


class CertusConsoleFormatter(logging.Formatter):
    def __init__(self, use_color: bool = True):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color
        self.use_unicode = _supports_utf8()

    def format(self, record: logging.LogRecord) -> str:
        sep1 = "✦" if self.use_unicode else "*"
        sep2 = "➔" if self.use_unicode else "->"
        time_str = self.formatTime(record, self.datefmt)
        msg = record.getMessage()
        if self.use_color:
            c_reset = "\033[0m"
            c_bold = "\033[1m"
            c_grey = "\033[90m"
            if record.levelno >= logging.CRITICAL:
                c_level, lvl_name = "\033[97;41m", " CRIT "
            elif record.levelno >= logging.ERROR:
                c_level, lvl_name = "\033[91m", " ERROR "
            elif record.levelno >= logging.WARNING:
                c_level, lvl_name = "\033[93m", " WARN  "
            elif record.levelno >= logging.INFO:
                c_level, lvl_name = "\033[92m", " INFO  "
            else:
                c_level, lvl_name = "\033[90m", " DEBUG "
            details = f"{c_grey}[{record.module}.{record.funcName}:{record.lineno}]{c_reset}"
            level_str = f"{c_level}{c_bold}{lvl_name}{c_reset}"
            formatted = f"{time_str} {sep1} {level_str} {details} {sep2} {msg}"
        else:
            lvl_name = record.levelname.ljust(5)
            details = f"[{record.module}.{record.funcName}:{record.lineno}]"
            formatted = f"{time_str} {sep1} {lvl_name} {details} {sep2} {msg}"
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


class CertusGuiFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_unicode = _supports_utf8()

    def format(self, record: logging.LogRecord) -> str:
        sep1 = "✦" if self.use_unicode else "*"
        sep2 = "➔" if self.use_unicode else "->"
        time_str = self.formatTime(record, self.datefmt)
        lvl_name = record.levelname.ljust(5)
        return f"{time_str} {sep1} {lvl_name} {sep2} {record.getMessage()}"


def _resolve_console_log_level(default: int) -> int:
    raw = os.environ.get("CERTUS_CONSOLE_LOG_LEVEL", "").strip().upper()
    if not raw:
        return logging.WARNING
    return getattr(logging, raw, default)


def setup_logging(log_file: str | None = None, level: int | None = None) -> logging.Logger:
    logger = logging.getLogger("CERTUS")
    logger.setLevel(logging.INFO if level is None else level)
    logger.propagate = False
    for handler in list(logger.handlers):
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)-12s | %(funcName)-22s:%(lineno)-4d | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CertusConsoleFormatter(use_color=_supports_color()))
    console_handler.setLevel(_resolve_console_log_level(logger.level))
    logger.addHandler(console_handler)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        try:
            file_handler = RotatingFileHandler(str(log_path), maxBytes=MAX_LOG_FILE_SIZE_BYTES, backupCount=MAX_LOG_BACKUP_FILES, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            pass
    jsonl_path = Path(log_file).with_suffix(".jsonl") if log_file else Path("logs") / "CERTUS.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        attach_jsonl_handler(logger, jsonl_path)
    except Exception:
        logger.debug("logger=certus sink=jsonl status=unavailable path=%s", jsonl_path, exc_info=True)
    return logger


def get_logger() -> logging.Logger:
    logger = logging.getLogger("CERTUS")
    return logger if logger.handlers else setup_logging()


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("logger=certus event=uncaught_exception\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
