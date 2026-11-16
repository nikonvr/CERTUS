"""The INFO records of CERTUS code that does not log through "CERTUS" reach its handlers (audit 2026-11-15, L3-m5).

Only the "CERTUS" logger had handlers. ``logging.info`` (root), ``getLogger(__name__)`` in certus/ and the "certus" and
"ThinFilm" loggers were cut at WARNING: the RE phase summaries and the FIELD workers' journal never reached the log.
"""

from __future__ import annotations

import logging

import pytest

from certus.core.certus_logging import setup_logging


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def certus_handler(monkeypatch):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", list(root.handlers))
    monkeypatch.setattr(root, "level", root.level)
    logger = setup_logging(log_file=None)
    collect = _Collect()
    logger.addHandler(collect)
    yield collect
    logger.removeHandler(collect)


@pytest.mark.parametrize("name", ["certus.spline.spline_workers", "certus", "ThinFilm", None])
def test_an_info_of_certus_code_reaches_the_certus_handlers(certus_handler, name) -> None:
    (logging.getLogger(name) if name else logging.getLogger()).info("phase 1 done %s", name)
    assert f"phase 1 done {name}" in certus_handler.messages


def test_another_library_is_not_forwarded(certus_handler) -> None:
    logging.getLogger("matplotlib.font_manager").info("font cache")
    assert "font cache" not in certus_handler.messages


def test_setting_up_twice_does_not_duplicate(certus_handler) -> None:
    setup_logging(log_file=None).addHandler(certus_handler)
    logging.getLogger("certus.x").info("once")
    assert certus_handler.messages.count("once") == 1
