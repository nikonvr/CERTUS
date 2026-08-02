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
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from certus.core.certus_logging import get_logger

# Enable performance logging via environment variable
ENABLE_PERF_LOGGING = os.environ.get("CERTUS_PERF_LOG", "").strip().lower() in ("1", "true", "yes", "on")

# Threshold in seconds - log only operations taking longer than this
PERF_LOG_THRESHOLD = float(os.environ.get("CERTUS_PERF_THRESHOLD", "0.1"))


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""

    operation: str
    times: List[float] = field(default_factory=list)

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

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(self):
        self._metrics: Dict[str, OperationMetrics] = defaultdict(lambda: OperationMetrics(operation=""))
        self._enabled = ENABLE_PERF_LOGGING
        self._logger = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        """Enable performance monitoring."""
        self._enabled = True

    def disable(self):
        """Disable performance monitoring."""
        self._enabled = False

    def _get_logger(self):
        if self._logger is None:
            self._logger = get_logger()
        return self._logger

    @contextmanager
    def measure(self, operation: str):
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

    def record(self, operation: str, elapsed: float):
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

    def get_metrics(self, operation: str) -> Optional[OperationMetrics]:
        """Get metrics for a specific operation."""
        return self._metrics.get(operation)

    def report(self, top_n: Optional[int] = None, sort_by: str = "total") -> Dict[str, Any]:
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

    def report_str(self, top_n: Optional[int] = 10, sort_by: str = "total") -> str:
        """
        Generate human-readable performance report.

        Args:
            top_n: Number of top operations to include
            sort_by: Sort operations by this metric

        Returns:
            Formatted string report
        """
        report = self.report(top_n=top_n, sort_by=sort_by)

        if not report["operations"]:
            return "No performance data collected."

        lines = [
            "=" * 80,
            "CERTUS PERFORMANCE REPORT",
            "=" * 80,
            f"Total operations tracked: {report['summary']['total_operations']}",
            f"Total time: {report['summary']['total_time']:.3f}s",
            f"Total calls: {report['summary']['total_calls']}",
            "",
            f"Top {len(report['operations'])} operations by {sort_by}:",
            "-" * 80,
            f"{'Operation':<40} {'Count':>8} {'Total':>10} {'Mean':>10} {'P95':>10}",
            "-" * 80,
        ]

        for op in report["operations"]:
            lines.append(
                f"{op['operation']:<40} {op['count']:>8} {op['total']:>10.3f}s {op['mean']:>10.3f}s {op['p95']:>10.3f}s"
            )

        lines.append("=" * 80)
        return "\n".join(lines)

    def reset(self):
        """Clear all collected metrics."""
        self._metrics.clear()

    def log_report(self, top_n: Optional[int] = 10, sort_by: str = "total"):
        """Log the performance report."""
        logger = self._get_logger()
        report_str = self.report_str(top_n=top_n, sort_by=sort_by)
        logger.info("\n" + report_str)


# Global performance monitor instance
perf_monitor = PerformanceMonitor()


def log_perf(func: Optional[Callable] = None, *, operation: Optional[str] = None, threshold: Optional[float] = None):
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
        def wrapper(*args, **kwargs):
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
    "perf_monitor",
    "log_perf",
    "PerformanceMonitor",
    "OperationMetrics",
    "ENABLE_PERF_LOGGING",
    "PERF_LOG_THRESHOLD",
]
