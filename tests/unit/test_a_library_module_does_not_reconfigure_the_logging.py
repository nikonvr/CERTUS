"""D42: a module of the certus package that asks for its environment does not replace the logging of the process.

Nine library modules called `create_module_environment(__file__, ...)` at import, and each call replaced the handlers of the CERTUS logger
(`setup_logging` removes the old ones): the log file of a run depended on the order in which they were imported, and a script that imported
one got `certus_certus_index_spline.log` in its working folder. An entry script still sets the logging up; a library takes it as it finds it.
"""

from __future__ import annotations

import logging

import pytest

import certus.core.certus_index_core as a_library_module
from certus.core.certus_core import create_module_environment


@pytest.fixture
def certus_logger(tmp_path, monkeypatch):
    """The CERTUS logger with no handler, in an empty working folder; whatever the test did to it is undone."""
    monkeypatch.chdir(tmp_path)
    logger = logging.getLogger("CERTUS")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    logger.handlers[:] = []
    yield logger
    for handler in logger.handlers:
        handler.close()
    logger.handlers[:] = saved[0]
    logger.setLevel(saved[1])
    logger.propagate = saved[2]


def test_an_entry_script_sets_the_logging_up(certus_logger, tmp_path) -> None:
    create_module_environment(str(tmp_path / "entry.py"), "ENTRY")

    assert (tmp_path / "certus_entry.log").exists()
    assert certus_logger.handlers


def test_a_library_module_leaves_the_logging_of_the_entry_script_alone(certus_logger, tmp_path) -> None:
    create_module_environment(str(tmp_path / "entry.py"), "ENTRY")
    before = list(certus_logger.handlers)

    create_module_environment(a_library_module.__file__, "CERTUS_INDEX_CORE")

    assert certus_logger.handlers == before
    assert not (tmp_path / "certus_certus_index_core.log").exists()


def test_a_library_module_imported_alone_does_not_make_a_log_file_named_after_itself(certus_logger, tmp_path) -> None:
    env = create_module_environment(a_library_module.__file__, "CERTUS_INDEX_CORE")

    assert not list(tmp_path.glob("certus_*.log"))
    assert env["logger"] is not None
    assert env["script_dir"]


def test_the_entry_script_that_comes_after_a_library_module_still_wins(certus_logger, tmp_path) -> None:
    create_module_environment(a_library_module.__file__, "CERTUS_INDEX_CORE")

    create_module_environment(str(tmp_path / "entry.py"), "ENTRY")

    assert (tmp_path / "certus_entry.log").exists()
