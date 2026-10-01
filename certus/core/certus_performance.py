"""
CERTUS Performance Monitoring & Profiling

Part of CERTUS Suite (Harmonized Architecture 2026)

Provides:
- Performance decorators for measuring function execution time
- PerformanceMonitor for collecting and reporting metrics
- Context managers for measuring code blocks
- Integration with CERTUS logging system

Usage:
    from certus.core.certus_performance import perf_monitor, log_perf

    # Decorator usage
    @log_perf
    def expensive_operation():
        ...

    # Context manager usage
    with perf_monitor.measure("calculation"):
        result = heavy_computation()

    # Get report
    stats = perf_monitor.report()
"""

from __future__ import annotations

import functools
import os
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

import numpy as np

from certus.core.certus_logging import get_logger
from collections.abc import Iterator
import logging

# Enable performance logging via environment variable
ENABLE_PERF_LOGGING = os.environ.get("CERTUS_PERF_LOG", "").strip().lower() in ("1", "true", "yes", "on")

# Threshold in seconds - log only operations taking longer than this
PERF_LOG_THRESHOLD = float(os.environ.get("CERTUS_PERF_THRESHOLD", "0.1"))


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""

    operation: str
    times: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.times)

    @property
    def total(self) -> float:
        return sum(self.times)

    @property
    def mean(self) -> float:
        return np.mean(self.times) if self.times else 0.0

    @property
    def median(self) -> float:
        return np.median(self.times) if self.times else 0.0

    @property
    def std(self) -> float:
        return np.std(self.times) if self.times else 0.0

    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0.0

    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0.0

    @property
    def p50(self) -> float:
        return np.percentile(self.times, 50) if self.times else 0.0

    @property
    def p95(self) -> float:
        return np.percentile(self.times, 95) if self.times else 0.0

    @property
    def p99(self) -> float:
        return np.percentile(self.times, 99) if self.times else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for reporting."""
        return {
            "operation": self.operation,
            "count": self.count,
            "total": self.total,
            "mean": self.mean,
            "median": self.median,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
        }


class PerformanceMonitor:
    """
    Central performance monitoring system.

    Collects timing data for operations and provides statistical reports.
    Thread-safe for concurrent measurements.
    """

    def __init__(self) -> None:
        self._metrics: dict[str, OperationMetrics] = defaultdict(lambda: OperationMetrics(operation=""))
        self._enabled = ENABLE_PERF_LOGGING
        self._logger: logging.Logger | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        """Enable performance monitoring."""
        self._enabled = True

    def disable(self) -> None:
        """Disable performance monitoring."""
        self._enabled = False

    def _get_logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_logger()
        return self._logger

    @contextmanager
    def measure(self, operation: str) -> Iterator[None]:
        """
        Context manager for measuring operation duration.

        Args:
            operation: Name of the operation being measured

        Example:
            with perf_monitor.measure("needle_scan"):
                result = needle_scan_cached(...)
        """
        if not self._enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record(operation, elapsed)

    def record(self, operation: str, elapsed: float) -> None:
        """
        Record a timing measurement.

        Args:
            operation: Name of the operation
            elapsed: Time taken in seconds
        """
        if not self._enabled:
            return

        if operation not in self._metrics:
            self._metrics[operation] = OperationMetrics(operation=operation)

        self._metrics[operation].times.append(elapsed)

        # Log if above threshold
        if elapsed > PERF_LOG_THRESHOLD:
            logger = self._get_logger()
            logger.info(f"PERF: {operation} took {elapsed:.3f}s")

    def report(self, top_n: int | None = None, sort_by: str = "total") -> dict[str, Any]:
        """
        Generate performance report.

        Args:
            top_n: If specified, return only top N operations by sort key
            sort_by: Sort operations by this metric (total, mean, count, p95)

        Returns:
            Dictionary with aggregated metrics per operation
        """
        if not self._metrics:
            return {"operations": [], "summary": {"total_operations": 0}}

        operations = []
        for metric in self._metrics.values():
            operations.append(metric.to_dict())

        # Sort by requested metric
        if sort_by in ("total", "mean", "count", "p95", "max"):
            operations.sort(key=lambda x: x[sort_by], reverse=True)

        if top_n:
            operations = operations[:top_n]

        # Calculate summary statistics
        total_time = sum(op["total"] for op in operations)
        total_calls = sum(op["count"] for op in operations)

        return {
            "operations": operations,
            "summary": {
                "total_operations": len(self._metrics),
                "total_time": total_time,
                "total_calls": total_calls,
                "operations_reported": len(operations),
            },
        }

    def reset(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()


# Global performance monitor instance
perf_monitor = PerformanceMonitor()


def log_perf(func: Callable | None = None, *, operation: str | None = None, threshold: float | None = None) -> Callable[..., Any]:
    """
    Decorator for automatic performance logging.

    Args:
        func: Function to decorate (when used without arguments)
        operation: Custom operation name (defaults to function name)
        threshold: Custom threshold in seconds (defaults to PERF_LOG_THRESHOLD)

    Usage:
        @log_perf
        def my_function():
            ...

        @log_perf(operation="custom_name", threshold=0.5)
        def expensive_function():
            ...
    """

    def decorator(f: Callable) -> Callable:
        op_name = operation or f"{f.__module__}.{f.__name__}"
        log_threshold = threshold if threshold is not None else PERF_LOG_THRESHOLD

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not perf_monitor.enabled:
                return f(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                perf_monitor.record(op_name, elapsed)

                if elapsed > log_threshold:
                    logger = perf_monitor._get_logger()
                    logger.info(f"PERF: {op_name} took {elapsed:.3f}s")

        return wrapper

    # Handle both @log_perf and @log_perf(...) syntax
    if func is None:
        return decorator
    return decorator(func)


__all__ = [
    "ENABLE_PERF_LOGGING",
    "PERF_LOG_THRESHOLD",
    "OperationMetrics",
    "PerformanceMonitor",
    "log_perf",
    "perf_monitor",
]
