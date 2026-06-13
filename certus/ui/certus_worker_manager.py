"""
CERTUS UI - Worker and Async Task Management
Implements dependency injection for background task orchestration.
"""

import logging
from typing import Protocol, Any, Callable
from PyQt6.QtCore import QObject, QThread, pyqtSignal

class CertusWorkerManagerProtocol(Protocol):
    """Protocol for managing long-running background workers."""
    def register_worker(self, worker: QThread) -> None: ...
    def unregister_worker(self, worker: QThread) -> None: ...
    def stop_all(self) -> None: ...
    def active_count(self) -> int: ...

class CertusWorkerManager(QObject):
    """
    Default implementation of the WorkerManager.
    Tracks active QThreads and ensures they are safely stopped.
    """
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._active_workers: list[QThread] = []

    def register_worker(self, worker: QThread) -> None:
        """Register a new worker and connect its finished signal."""
        if worker not in self._active_workers:
            self._active_workers.append(worker)
            try:
                worker.finished.connect(lambda w=worker: self.unregister_worker(w))
            except Exception as e:
                logging.getLogger("CERTUS").error(f"Failed to connect worker finished signal: {e}")

    def unregister_worker(self, worker: QThread) -> None:
        """Remove a worker from the active list."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def stop_all(self) -> None:
        """Gracefully interrupt all running workers."""
        for worker in list(self._active_workers):
            if hasattr(worker, "stop") and callable(getattr(worker, "stop")):
                try:
                    worker.stop()
                except Exception:
                    pass
            if hasattr(worker, "requestInterruption"):
                try:
                    worker.requestInterruption()
                except Exception:
                    pass

    def active_count(self) -> int:
        return len(self._active_workers)

class CertusNumbaWarmupProtocol(Protocol):
    """Protocol for managing Numba JIT warmup routines."""
    numba_ready: bool
    def start_warmup(self) -> None: ...
    def is_ready(self) -> bool: ...

class CertusNumbaWarmupManager(QObject):
    """
    Handles Numba JIT warmup to prevent UI freezing during first spectral evaluation.
    Emits signals when ready or if an error occurs.
    """
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal(str)

    def __init__(self, app_logger: logging.Logger | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.numba_ready = False
        self._warmup_done = False
        self.logger = app_logger or logging.getLogger("CERTUS")
        
    def start_warmup(self, custom_warmup_fn: Callable[[], None] | None = None) -> None:
        """
        Initiate the warmup sequence.
        If a custom QThread/QRunnable is needed, the caller should launch it
        and bind its finished signal to `self.on_warmup_done`.
        """
        if custom_warmup_fn:
            try:
                custom_warmup_fn()
            except Exception as e:
                self.on_warmup_error(str(e))
        else:
            self.on_warmup_done()

    def on_warmup_done(self) -> None:
        """Mark warmup as completed successfully."""
        self._warmup_done = True
        self.numba_ready = True
        self.logger.info("[WARMUP] JIT compilation completed; spectrum eval may proceed.")
        self.sig_numba_ready.emit()

    def on_warmup_error(self, message: str) -> None:
        """Handle a warmup failure."""
        self.numba_ready = False
        self.logger.error(f"Warmup Error: {message}")
        self.sig_numba_error.emit(message)

    def is_ready(self) -> bool:
        return self.numba_ready
