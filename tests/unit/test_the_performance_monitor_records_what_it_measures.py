"""The performance monitor records only when enabled, reports what it recorded, and logs only the slow (certus_performance).

`certus/core/certus_performance.py` was covered at 45.9 % on 2026-09-30 and no test named it. Nothing here waits
on a clock: durations are given to `record`, so the statistics are exact and the tests cannot flake.
"""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pytest

import certus.core.certus_performance as performance
from certus.core.certus_performance import OperationMetrics, PerformanceMonitor, log_perf


def _monitor(enabled: bool = True) -> PerformanceMonitor:
    monitor = PerformanceMonitor()
    monitor._logger = Mock()  # never the real logger: what is logged is asserted
    monitor.enable() if enabled else monitor.disable()
    return monitor


def test_the_statistics_of_an_operation_are_those_of_its_durations() -> None:
    metrics = OperationMetrics("scan", times=[1.0, 2.0, 3.0, 4.0, 10.0])

    assert (metrics.count, metrics.total, metrics.min, metrics.max) == (5, 20.0, 1.0, 10.0)
    assert (metrics.mean, metrics.median, metrics.p50) == (4.0, 3.0, 3.0)
    assert metrics.std == pytest.approx(np.std([1.0, 2.0, 3.0, 4.0, 10.0]))
    assert metrics.p95 == pytest.approx(np.percentile([1.0, 2.0, 3.0, 4.0, 10.0], 95))
    assert metrics.to_dict()["operation"] == "scan"


def test_an_operation_never_measured_reports_zeros_not_errors() -> None:
    empty = OperationMetrics("never")

    assert (empty.count, empty.total, empty.mean, empty.median, empty.std, empty.min, empty.max) == (0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert (empty.p50, empty.p95, empty.p99) == (0.0, 0.0, 0.0)


def test_a_disabled_monitor_records_nothing_and_an_enabled_one_does() -> None:
    off, on = _monitor(enabled=False), _monitor()

    off.record("scan", 1.0)
    on.record("scan", 1.0)

    assert off.report() == {"operations": [], "summary": {"total_operations": 0}}
    assert on.report()["summary"]["total_calls"] == 1


def test_the_report_sorts_by_the_requested_metric_and_keeps_the_top_n() -> None:
    monitor = _monitor()
    for operation, times in {"slow": [5.0, 5.0], "many": [0.1] * 10, "once": [7.0]}.items():
        for elapsed in times:
            monitor.record(operation, elapsed)

    by_total = monitor.report()
    assert [op["operation"] for op in by_total["operations"]] == ["slow", "once", "many"]  # 10.0, 7.0, 1.0
    assert [op["operation"] for op in monitor.report(sort_by="count")["operations"]] == ["many", "slow", "once"]
    assert [op["operation"] for op in monitor.report(top_n=1)["operations"]] == ["slow"]
    assert by_total["summary"] == {
        "total_operations": 3, "total_time": pytest.approx(18.0), "total_calls": 13, "operations_reported": 3,
    }  # fmt: skip


def test_reset_forgets_what_was_recorded() -> None:
    monitor = _monitor()
    monitor.record("scan", 1.0)

    monitor.reset()

    assert monitor.report()["operations"] == []


def test_only_a_measurement_above_the_threshold_is_logged() -> None:
    monitor = _monitor()

    monitor.record("fast", performance.PERF_LOG_THRESHOLD / 10)
    monitor.record("slow", performance.PERF_LOG_THRESHOLD * 10)

    monitor._logger.info.assert_called_once()
    assert "PERF: slow took" in monitor._logger.info.call_args.args[0]


def test_a_measured_block_is_recorded_once_even_when_it_raises() -> None:
    monitor = _monitor()

    with pytest.raises(RuntimeError), monitor.measure("block"):
        raise RuntimeError("boom")

    assert monitor.report()["summary"]["total_calls"] == 1  # the `finally`: the failed run is measured too
    with _monitor(enabled=False).measure("ignored"):
        pass  # disabled: nothing to record, nothing to fail


def test_the_decorator_records_under_the_function_name_or_a_given_one_and_keeps_the_result(monkeypatch) -> None:
    monitor = _monitor()
    monkeypatch.setattr(performance, "perf_monitor", monitor)

    @log_perf
    def add(a, b):
        return a + b

    @log_perf(operation="custom", threshold=1e9)
    def twice(x):
        return 2 * x

    assert add(1, 2) == 3
    assert twice(4) == 8
    recorded = {op["operation"] for op in monitor.report()["operations"]}
    assert recorded == {f"{add.__module__}.add", "custom"}
    assert add.__name__ == "add"  # functools.wraps


def test_the_decorator_does_nothing_when_the_monitor_is_disabled_and_lets_errors_through(monkeypatch) -> None:
    monitor = _monitor(enabled=False)
    monkeypatch.setattr(performance, "perf_monitor", monitor)

    @log_perf
    def fail():
        raise ValueError("kept")

    with pytest.raises(ValueError, match="kept"):
        fail()
    assert monitor.report()["operations"] == []
