"""The UX subprocess launcher must tell a native abort from a real failure.

Every UX test that measures a window spawns a worker process and reads its
stdout. Until this harness existed, none of the eight call sites looked at
``returncode``: a worker that died natively produced ``assert []`` with an
empty stderr, so a transient abort was indistinguishable from a UX regression.
Three such runs were measured over five full passes, each passing in isolation.

These tests drive the launcher with fake workers, so both failure modes are
reproduced on demand instead of waited for.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ux_worker import describe_exit_status, run_ux_worker  # noqa: E402

MARKER = "__FAKE_WORKER__"


def _write_worker(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fake_worker.py"
    script.write_text(body, encoding="utf-8")
    return str(script)


# =============================================================================
# Exit status reporting
# =============================================================================


def test_a_windows_structured_exception_is_named_as_a_native_abort():
    """0xC0000005 is an access violation: Python never ran an except clause."""
    assert "native abort" in describe_exit_status(0xC0000005)
    assert "0xc0000005" in describe_exit_status(0xC0000005)


def test_a_posix_signal_is_named_as_a_signal():
    assert describe_exit_status(-11) == "killed by signal 11"


def test_an_ordinary_non_zero_exit_is_not_called_an_abort():
    assert describe_exit_status(3) == "exit status 3"
    assert "abort" not in describe_exit_status(3)


# =============================================================================
# Launcher behaviour
# =============================================================================


def test_a_healthy_worker_returns_its_payload(tmp_path):
    script = _write_worker(
        tmp_path,
        f'print("{MARKER}" + \'{{"value": 42}}\')\n',
    )
    assert run_ux_worker([sys.executable, script], MARKER, context="healthy") == {"value": 42}


def test_a_worker_that_always_aborts_names_its_exit_status(tmp_path):
    """The whole point: an abort must not look like an empty assertion.

    ``os.abort()`` reproduces the measured signature - the process dies without
    unwinding Python, so stderr stays empty (Windows: 0xC0000409).
    """
    script = _write_worker(tmp_path, "import os\nos.abort()\n")

    with pytest.raises(AssertionError) as excinfo:
        run_ux_worker([sys.executable, script], MARKER, context="always aborts")

    message = str(excinfo.value)
    assert "native abort" in message or "killed by signal" in message, message
    assert "2 attempts" in message, message
    assert "stderr empty" in message, message


def test_a_worker_that_exits_quietly_is_not_reported_as_an_abort(tmp_path):
    """A worker that runs to completion and prints nothing is a real failure."""
    script = _write_worker(tmp_path, "pass\n")

    with pytest.raises(AssertionError) as excinfo:
        run_ux_worker([sys.executable, script], MARKER, context="silent")

    message = str(excinfo.value)
    assert "exit status 0" in message, message
    assert "native abort" not in message, message


def test_a_transient_abort_is_retried_and_reported(tmp_path):
    """The retry absorbs the flake - and says so, instead of hiding it."""
    flag = tmp_path / "already_ran"
    script = _write_worker(
        tmp_path,
        "import os\n"
        f"flag = r'{flag}'\n"
        "if not os.path.exists(flag):\n"
        "    open(flag, 'w').close()\n"
        "    os.abort()\n"
        f'print("{MARKER}" + \'{{"value": 7}}\')\n',
    )

    with pytest.warns(UserWarning, match="attempt 1"):
        result = run_ux_worker([sys.executable, script], MARKER, context="transient")

    assert result == {"value": 7}


def test_a_healthy_worker_does_not_warn(tmp_path):
    script = _write_worker(
        tmp_path,
        f'print("{MARKER}" + \'{{"value": 1}}\')\n',
    )
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert run_ux_worker([sys.executable, script], MARKER, context="quiet") == {"value": 1}
