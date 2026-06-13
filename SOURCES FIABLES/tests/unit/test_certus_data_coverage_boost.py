"""Additional coverage tests for certus_data.py — I/O edge cases, timing, perf monitor.

Targets gaps in:
- numpy_encoder edge cases
- read_csv_robust (semicolon detection, fallback paths)
- read_data_file_robust (dispatch)
- to_csv_robust (European format, validation)
- to_excel_robust (validation)
- export_optimization_report (Excel generation without plots)
- TimingLogger (start/end, global)
- PerformanceMonitor (measure, report)
- SharedIndicesManager/Worker (context manager, get)
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus.utils.certus_data import (
    PerformanceMonitor,
    SharedIndicesManager,
    SharedIndicesWorker,
    TimingLogger,
    numpy_encoder,
    read_csv_robust,
    read_data_file_robust,
    to_csv_robust,
)


# ─────────────────────────────────────────────────────────────────────
# numpy_encoder
# ─────────────────────────────────────────────────────────────────────


class TestNumpyEncoder:
    def test_int64(self):
        assert numpy_encoder(np.int64(42)) == 42
        assert isinstance(numpy_encoder(np.int64(42)), int)

    def test_float64(self):
        assert numpy_encoder(np.float64(3.14)) == pytest.approx(3.14)
        assert isinstance(numpy_encoder(np.float64(3.14)), float)

    def test_float32(self):
        assert isinstance(numpy_encoder(np.float32(1.5)), float)

    def test_int32(self):
        assert isinstance(numpy_encoder(np.int32(7)), int)

    def test_ndarray(self):
        arr = np.array([1, 2, 3])
        result = numpy_encoder(arr)
        assert result == [1, 2, 3]

    def test_fallback_to_str(self):
        result = numpy_encoder({"key": "val"})
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────
# read_csv_robust
# ─────────────────────────────────────────────────────────────────────


class TestReadCsvRobust:
    def test_comma_separated(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("wl,R,T\n400,0.1,0.9\n500,0.2,0.8\n")
        df = read_csv_robust(str(f))
        assert len(df) == 2
        assert "wl" in df.columns

    def test_semicolon_separated(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("wl;R;T\n400;0,1;0,9\n500;0,2;0,8\n")
        df = read_csv_robust(str(f))
        assert len(df) == 2

    def test_invalid_filepath_raises(self):
        with pytest.raises(ValueError):
            read_csv_robust("")

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            read_csv_robust("nonexistent_file_12345.csv")

    def test_none_filepath_raises(self):
        with pytest.raises(ValueError):
            read_csv_robust(None)


class TestReadDataFileRobust:
    def test_dispatches_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n3,4\n")
        df = read_data_file_robust(str(f))
        assert len(df) == 2

    def test_invalid_filepath_raises(self):
        with pytest.raises(ValueError):
            read_data_file_robust("")


# ─────────────────────────────────────────────────────────────────────
# to_csv_robust
# ─────────────────────────────────────────────────────────────────────


class TestToCsvRobust:
    def test_us_format(self, tmp_path):
        df = pd.DataFrame({"a": [1.1, 2.2], "b": [3.3, 4.4]})
        path = str(tmp_path / "out.csv")
        to_csv_robust(df, path)
        content = Path(path).read_text()
        assert "," in content

    def test_european_format(self, tmp_path):
        df = pd.DataFrame({"a": [1.1, 2.2], "b": [3.3, 4.4]})
        path = str(tmp_path / "out.csv")
        to_csv_robust(df, path, decimal_separator=",")
        content = Path(path).read_text()
        assert ";" in content

    def test_empty_df_raises(self, tmp_path):
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="empty"):
            to_csv_robust(df, str(tmp_path / "out.csv"))

    def test_invalid_path_raises(self):
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError):
            to_csv_robust(df, "")


# ─────────────────────────────────────────────────────────────────────
# TimingLogger
# ─────────────────────────────────────────────────────────────────────


class TestTimingLogger:
    def test_start_and_end(self):
        tl = TimingLogger()
        tl.start("test_section")
        assert "test_section" in tl.start_times
        tl.end("test_section")
        assert "test_section" not in tl.start_times

    def test_end_nonexistent_noop(self):
        tl = TimingLogger()
        tl.end("nonexistent")  # Should not raise

    def test_global_start_end(self):
        tl = TimingLogger()
        tl.start_global("phase_a")
        assert "phase_a" in tl.start_times
        tl.end_global("phase_a")
        assert "phase_a" not in tl.start_times


# ─────────────────────────────────────────────────────────────────────
# PerformanceMonitor
# ─────────────────────────────────────────────────────────────────────


class TestPerformanceMonitor:
    def test_measure_and_report(self):
        pm = PerformanceMonitor()
        with pm.measure("test_op"):
            pass
        report = pm.report()
        assert "test_op" in report
        assert "ms" in report

    def test_empty_report(self):
        pm = PerformanceMonitor()
        assert pm.report() == "No data"

    def test_multiple_measures(self):
        pm = PerformanceMonitor()
        for _ in range(3):
            with pm.measure("op"):
                pass
        assert "n=3" in pm.report()


# ─────────────────────────────────────────────────────────────────────
# SharedIndicesManager / Worker
# ─────────────────────────────────────────────────────────────────────


class TestSharedIndicesManagerWorker:
    def test_context_manager_lifecycle(self):
        clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}}
        with SharedIndicesManager(clues) as mgr:
            ctx = mgr.get_context_info()
            assert "shm_name" in ctx
            assert "shape" in ctx

    def test_worker_reads_correct_values(self):
        clues = {
            400.0: {"H": 2.2, "L": 1.4, "substrate": 1.5},
            600.0: {"H": 2.4, "L": 1.5, "substrate": 1.55},
        }
        with SharedIndicesManager(clues) as mgr:
            ctx = mgr.get_context_info()
            with SharedIndicesWorker(ctx) as worker:
                # Exact match
                d400 = worker.get(400.0)
                assert abs(d400["H"] - 2.2) < 0.01
                assert abs(d400["L"] - 1.4) < 0.01

                # Interpolation
                d500 = worker.get(500.0)
                assert 2.2 < d500["H"] < 2.4  # between 400 and 600

                # Edge: below range
                d300 = worker.get(300.0)
                assert abs(d300["H"] - 2.2) < 0.01  # clamps to first

                # Edge: above range
                d900 = worker.get(900.0)
                assert abs(d900["H"] - 2.4) < 0.01  # clamps to last

    def test_worker_cache_hit(self):
        clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}}
        with SharedIndicesManager(clues) as mgr:
            ctx = mgr.get_context_info()
            with SharedIndicesWorker(ctx) as worker:
                r1 = worker.get(500.0)
                r2 = worker.get(500.0)  # Cache hit
                assert r1 == r2

    def test_double_close_safe(self):
        clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}}
        mgr = SharedIndicesManager(clues)
        mgr.close()
        mgr.close()  # Should not raise
