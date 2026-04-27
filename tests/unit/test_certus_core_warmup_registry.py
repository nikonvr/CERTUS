"""Regression tests for the warmup thread registry in `certus_core`.

Locks the contract of `wait_warmup` and the module-level warmup thread reference
before the P1-13 refactor that replaces the `_certus_warmup_thread` module-level
mutable global with a `_WarmupRegistry` class attribute.

Acceptance: `wait_warmup` must
1. Be a no-op when no warmup thread is registered.
2. Reset the registered thread to None after the call (idempotent).
3. Join an alive thread with the requested timeout, then reset.
4. Never raise.
"""

from __future__ import annotations

import threading
import time

import pytest

import certus_core


@pytest.fixture(autouse=True)
def _isolate_warmup_state():
    """Snapshot/restore the warmup registry state to keep tests independent."""
    saved = certus_core._WarmupRegistry.thread
    yield
    certus_core._WarmupRegistry.thread = saved


def _set_warmup_thread(thread: threading.Thread | None) -> None:
    certus_core._WarmupRegistry.thread = thread


def _get_warmup_thread() -> threading.Thread | None:
    return certus_core._WarmupRegistry.thread


def test_wait_warmup_is_noop_when_no_thread_registered():
    _set_warmup_thread(None)
    # Must not raise, must complete quickly.
    t0 = time.monotonic()
    certus_core.wait_warmup(timeout=0.5)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.2, "wait_warmup should be a no-op when no thread is registered"
    assert _get_warmup_thread() is None


def test_wait_warmup_resets_state_when_thread_is_dead():
    """A finished thread must be cleared by wait_warmup without blocking."""
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    t.join()  # already dead
    assert not t.is_alive()
    _set_warmup_thread(t)
    certus_core.wait_warmup(timeout=0.5)
    assert _get_warmup_thread() is None


def test_wait_warmup_joins_alive_thread_then_resets():
    """An alive thread must be joined within the requested timeout, then reset."""
    barrier = threading.Event()

    def worker() -> None:
        # Block until the test releases the barrier (or short fallback).
        barrier.wait(timeout=2.0)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    _set_warmup_thread(t)
    barrier.set()  # let the worker exit promptly
    certus_core.wait_warmup(timeout=2.0)
    assert _get_warmup_thread() is None
    # Thread must have completed by now.
    assert not t.is_alive()


def test_wait_warmup_does_not_raise_on_repeated_calls():
    _set_warmup_thread(None)
    for _ in range(3):
        certus_core.wait_warmup(timeout=0.1)
    assert _get_warmup_thread() is None
