"""Tests for the CERTUS crash and freeze watchdog."""

import time
import pytest
from pathlib import Path
from certus.utils.certus_watchdog import CrashAndFreezeWatchdog


@pytest.mark.unit
def test_watchdog_log_exception(tmp_path: Path):
    """Verify that unhandled exceptions are logged with traceback to crash.log."""
    watchdog = CrashAndFreezeWatchdog(log_dir=tmp_path, freeze_timeout_s=5.0)
    
    try:
        raise ValueError("Simulated computation fault")
    except ValueError as e:
        import sys
        exc_type, exc_val, exc_tb = sys.exc_info()
        watchdog.log_exception("UNIT_TEST", exc_type, exc_val, exc_tb)

    crash_log = tmp_path / "crash.log"
    assert crash_log.exists(), "crash.log was not created"
    content = crash_log.read_text(encoding="utf-8")
    assert "CRASH DETECTED (UNIT_TEST)" in content
    assert "ValueError: Simulated computation fault" in content
    assert "test_watchdog_log_exception" in content


@pytest.mark.unit
def test_watchdog_freeze_detection(tmp_path: Path):
    """Verify that a missed heartbeat triggers thread stack dumps in freeze_dump.log."""
    timeout_s = 2.0
    watchdog = CrashAndFreezeWatchdog(log_dir=tmp_path, freeze_timeout_s=timeout_s)
    watchdog.install()
    
    try:
        # Simulate a frozen thread by not sending heartbeats for timeout + margin
        time.sleep(timeout_s + 1.0)
        
        freeze_log = tmp_path / "freeze_dump.log"
        assert freeze_log.exists(), "freeze_dump.log was not created on freeze"
        content = freeze_log.read_text(encoding="utf-8")
        assert "FREEZE DETECTED: Main GUI thread unresponsive" in content
        assert "Thread" in content
    finally:
        watchdog.stop()
