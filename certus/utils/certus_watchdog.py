"""CERTUS Crash and Freeze Watchdog.

Provides a-posteriori post-mortem traceability:
1. Unhandled exception catcher (sys.excepthook, threading.excepthook) -> crash.log
2. Native crash handler (faulthandler.enable) -> crash_dump.log
3. Freeze/hang detector: monitors Qt GUI heartbeat. If the GUI thread freezes for more than
   `freeze_timeout_s`, dumps the full Python stack trace of all running threads to freeze_dump.log.
"""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable


class CrashAndFreezeWatchdog:
    """Watches application health and records post-mortem diagnostics on crash or freeze."""

    def __init__(self, log_dir: Path | str | None = None, freeze_timeout_s: float = 15.0) -> None:
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.freeze_timeout_s = max(2.0, float(freeze_timeout_s))

        self.crash_log_file = self.log_dir / "crash.log"
        self.crash_dump_file = self.log_dir / "crash_dump.log"
        self.freeze_dump_file = self.log_dir / "freeze_dump.log"

        self._last_heartbeat = time.time()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._freeze_reported = False
        self._faulthandler_file: Any = None
        self._qt_timer: Any = None

    def heartbeat(self) -> None:
        """Reset the heartbeat timer. Must be called regularly from the GUI thread."""
        self._last_heartbeat = time.time()
        if self._freeze_reported:
            self._freeze_reported = False
            logging.info("[WATCHDOG] GUI thread resumed normal event loop.")

    def install(self) -> None:
        """Install exception hooks, faulthandler, and start the background freeze monitor."""
        # 1. Native crash handler (SIGSEGV, SIGABRT, etc.)
        try:
            self._faulthandler_file = open(self.crash_dump_file, "a", encoding="utf-8")
            faulthandler.enable(file=self._faulthandler_file, all_threads=True)
        except Exception as e:
            logging.warning(f"[WATCHDOG] Failed to enable faulthandler: {e}")

        # 2. Python unhandled exceptions
        orig_sys_hook = sys.excepthook

        def _certus_sys_excepthook(exc_type, exc_value, exc_tb):
            try:
                self.log_exception("SYS_UNHANDLED", exc_type, exc_value, exc_tb)
            except Exception:
                pass
            try:
                if sys.stderr and not getattr(sys.stderr, "closed", False):
                    orig_sys_hook(exc_type, exc_value, exc_tb)
            except Exception:
                pass

        sys.excepthook = _certus_sys_excepthook

        if hasattr(threading, "excepthook"):
            orig_thread_hook = threading.excepthook

            def _certus_thread_excepthook(args):
                try:
                    self.log_exception(
                        f"THREAD_UNHANDLED:{getattr(args.thread, 'name', 'unknown')}",
                        args.exc_type,
                        args.exc_value,
                        args.exc_traceback,
                    )
                except Exception:
                    pass
                try:
                    if sys.stderr and not getattr(sys.stderr, "closed", False):
                        orig_thread_hook(args)
                except Exception:
                    pass

            threading.excepthook = _certus_thread_excepthook

        import atexit
        atexit.register(self.stop)

        # 3. Start freeze monitor thread
        self._running = True
        self._last_heartbeat = time.time()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="CertusFreezeWatchdog",
            daemon=True,
        )
        self._monitor_thread.start()
        logging.info(
            f"[WATCHDOG] Installed: timeout={self.freeze_timeout_s}s, "
            f"logs={self.log_dir}"
        )

    def log_exception(self, origin: str, exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        """Record an unhandled exception to crash.log with timestamp and full traceback."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        tb_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        entry = (
            f"\n{'='*70}\n"
            f"[{ts}] CRASH DETECTED ({origin})\n"
            f"Exception: {exc_type.__name__}: {exc_value}\n"
            f"{'-'*70}\n"
            f"{tb_lines}"
            f"{'='*70}\n"
        )
        try:
            with open(self.crash_log_file, "a", encoding="utf-8") as f:
                f.write(entry)
                f.flush()
        except Exception:
            pass

    def _monitor_loop(self) -> None:
        """Background loop checking whether the GUI thread missed its heartbeat."""
        check_interval = max(0.5, self.freeze_timeout_s / 5.0)
        while self._running:
            time.sleep(check_interval)
            elapsed = time.time() - self._last_heartbeat
            if elapsed > self.freeze_timeout_s and not self._freeze_reported:
                self._report_freeze(elapsed)

    def _report_freeze(self, elapsed: float) -> None:
        """Dump Python thread stack traces to freeze_dump.log."""
        self._freeze_reported = True
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "\n" + "=" * 80,
            f"[{ts}] FREEZE DETECTED: Main GUI thread unresponsive for {elapsed:.1f}s (threshold: {self.freeze_timeout_s}s)",
            "=" * 80,
        ]

        # Extract all thread frames
        current_frames = sys._current_frames()
        for thread_obj in threading.enumerate():
            t_id = thread_obj.ident
            t_name = thread_obj.name
            t_daemon = "daemon" if thread_obj.daemon else "non-daemon"
            lines.append(f"\n--- Thread {t_name} (ID: {t_id}, {t_daemon}) ---")
            if t_id in current_frames:
                frame = current_frames[t_id]
                stack = traceback.format_stack(frame)
                lines.extend(stack)
            else:
                lines.append("  (No frame found)")

        lines.append("=" * 80 + "\n")
        content = "\n".join(lines)

        try:
            with open(self.freeze_dump_file, "a", encoding="utf-8") as f:
                f.write(content)
                f.flush()
            print(f"\n[WATCHDOG ERROR] Freeze detected! Diagnostics saved to {self.freeze_dump_file}")
        except Exception as err:
            print(f"\n[WATCHDOG ERROR] Failed to write freeze dump: {err}")

    def hook_qt_app(self, qt_app: Any, interval_ms: int = 500) -> None:
        """Attach a periodic QTimer to the Qt application to pulse heartbeats."""
        try:
            from PyQt6.QtCore import QTimer
            self._qt_timer = QTimer()
            self._qt_timer.setInterval(interval_ms)
            self._qt_timer.timeout.connect(self.heartbeat)
            self._qt_timer.start()
        except Exception as e:
            logging.warning(f"[WATCHDOG] Failed to attach Qt QTimer heartbeat: {e}")

    def stop(self) -> None:
        """Stop the watchdog cleanly."""
        self._running = False
        if self._qt_timer is not None:
            try:
                self._qt_timer.stop()
            except Exception:
                pass
        if self._faulthandler_file is not None:
            try:
                faulthandler.disable()
                self._faulthandler_file.flush()
                self._faulthandler_file.close()
                self._faulthandler_file = None
            except Exception:
                pass


_GLOBAL_WATCHDOG: CrashAndFreezeWatchdog | None = None


def install_watchdog(
    log_dir: Path | str | None = None,
    freeze_timeout_s: float = 15.0,
    qt_app: Any = None,
) -> CrashAndFreezeWatchdog:
    """Public helper to initialize and attach the global crash & freeze watchdog."""
    global _GLOBAL_WATCHDOG
    if _GLOBAL_WATCHDOG is None:
        _GLOBAL_WATCHDOG = CrashAndFreezeWatchdog(log_dir=log_dir, freeze_timeout_s=freeze_timeout_s)
        _GLOBAL_WATCHDOG.install()
    if qt_app is not None:
        _GLOBAL_WATCHDOG.hook_qt_app(qt_app)
    return _GLOBAL_WATCHDOG
