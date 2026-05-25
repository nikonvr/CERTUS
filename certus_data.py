"""
CERTUS DATA - Data Handling, I/O and Reporting
==============================================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- Robust File I/O (CSV/Excel)
- Shared Memory Management (for STRAT)
- Performance Monitoring & Timing
- HTML Reporting Generation
"""

__all__ = [
    # File I/O
    "read_csv_robust",
    "read_excel_robust",
    "read_data_file_robust",
    "to_csv_robust",
    "to_excel_robust",
    "numpy_encoder",
    # Spectral Data Utilities
    "export_optimization_report",
    # Shared Memory
    "SharedIndicesManager",
    "SharedIndicesWorker",
    "SharedArrayManager",
    "SharedArrayWorker",
    # Performance
    "TimingLogger",
    "PerformanceMonitor",
    "PERF_MONITOR",
    # Reporting
    "generate_html_report",
    "ReportSection",
    "build_standard_report",
    "MANIFEST_REQUIRED_FIELDS",
    "get_missing_manifest_fields",
    # Spectrum loader (P8)
    "SpectrumLoadResult",
    "load_spectrum_columns",
    # Re-exports
    "QueueHandler",
    "setup_gui_logger",
    "OPENPYXL_AVAILABLE",
]

import base64
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from multiprocessing import shared_memory
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np
import pandas as pd

from certus_array_utils import as_float64_1d
# Import Core
from certus_core import NUMERICAL_FAULT_EXCEPTIONS, OPENPYXL_AVAILABLE, certus_timestamp_file

# =============================================================================
# CONSTANTS
# =============================================================================
CSV_SAMPLE_SIZE: int = 2048  # Bytes to sample for CSV delimiter detection
EXCEL_SHEET_NAME_MAX_LENGTH: int = 31  # Excel sheet name limit
MAX_SHARED_MEMORY_CACHE_SIZE: int = 1000  # Maximum entries in SharedIndicesWorker cache
WL_TOLERANCE: float = 1e-5  # Wavelength matching tolerance

# =============================================================================
# ROBUST FILE I/O
# =============================================================================


def numpy_encoder(obj) -> Any:
    """
    JSON encoder for numpy types.

    Converts numpy types (integers, floats, arrays) to native Python types
    for JSON serialization.

    Args:
        obj: Object to encode (numpy type or other)

    Returns:
        Native Python type (int, float, list, or str)
    """
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def read_csv_robust(filepath: str, **kwargs) -> pd.DataFrame:
    """
    Reads a CSV file with automatic separator detection.

    Automatically detects semicolon/comma and decimal separator, then
    converts numeric columns.

    Args:
        filepath: Path to CSV file
        **kwargs: Additional arguments for pd.read_csv

    Returns:
        Pandas DataFrame with automatically converted numeric columns

    Raises:
        FileNotFoundError: If file does not exist
        pd.errors.EmptyDataError: If file is empty
        ValueError: If path is invalid

    Example:
        >>> df = read_csv_robust("data.csv")
        >>> df.dtypes  # Numeric columns automatically detected
    """
    if not filepath or not isinstance(filepath, str):
        raise ValueError(f"Invalid filepath: {filepath}")
    if not Path(filepath).exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        # 1. Detect format
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(CSV_SAMPLE_SIZE)

        has_semi = ";" in sample
        cnt_semi = sample.count(";")
        cnt_comma = sample.count(",")

        if has_semi and cnt_semi > cnt_comma / 2:
            kwargs.setdefault("sep", ";")
            kwargs.setdefault("decimal", ",")
        else:
            kwargs.setdefault("sep", ",")
            kwargs.setdefault("decimal", ".")

        # 2. Read
        try:
            df = pd.read_csv(filepath, **kwargs)
        except (pd.errors.ParserError, ValueError, UnicodeDecodeError):
            # Fallback
            kwargs["decimal"] = ","
            df = pd.read_csv(filepath, **kwargs)

        # 3. Post-process numeric
        for col in df.columns:
            if df[col].dtype not in ["float64", "int64"]:
                try:
                    c = pd.to_numeric(df[col], errors="coerce")
                    if c.notna().sum() / len(c) > 0.5:
                        df[col] = c
                except (ValueError, TypeError):
                    # Skip columns that cannot be converted to numeric
                    pass
        return df
    except (pd.errors.ParserError, ValueError, UnicodeDecodeError, OSError):
        # Extreme fallback
        return pd.read_csv(filepath, sep=None, engine="python")


def read_excel_robust(filepath: str, **kwargs) -> pd.DataFrame:
    """
    Reads an Excel file with automatic numeric column conversion.

    Args:
        filepath: Path to Excel file (.xlsx, .xls)
        **kwargs: Additional arguments for pd.read_excel

    Returns:
        Pandas DataFrame with converted numeric columns

    Raises:
        ImportError: If openpyxl is not installed
        FileNotFoundError: If file does not exist
        ValueError: If Excel format or path is invalid
    """
    if not OPENPYXL_AVAILABLE:
        raise ImportError("openpyxl required for Excel file support")

    if not filepath or not isinstance(filepath, str):
        raise ValueError(f"Invalid filepath: {filepath}")
    if not Path(filepath).exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    df = pd.read_excel(filepath, **kwargs)
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        except (ValueError, TypeError):
            # Skip columns that cannot be converted to numeric
            pass
    return df


def read_data_file_robust(filepath: str, **kwargs) -> pd.DataFrame:
    """
    Reads a data file (CSV or Excel) according to extension.
    Dispatches to read_excel_robust for .xlsx/.xls, else read_csv_robust.
    """
    if not filepath or not isinstance(filepath, str):
        raise ValueError(f"Invalid filepath: {filepath}")
    fp_lower = filepath.lower()
    if fp_lower.endswith((".xlsx", ".xls")):
        return read_excel_robust(filepath, **kwargs)
    return read_csv_robust(filepath, **kwargs)


def to_csv_robust(df: pd.DataFrame, filepath: str, decimal_separator: str = None, **kwargs) -> None:
    """
    Writes a DataFrame to a CSV file with configurable format.

    Args:
        df: Pandas DataFrame to save
        filepath: Destination path
        decimal_separator: ',' for European format (;), '.' for US format (,)
        **kwargs: Additional arguments for df.to_csv

    Raises:
        PermissionError: If file cannot be written
        ValueError: If DataFrame is empty or path is invalid
    """
    # Validation
    if df.empty:
        raise ValueError("Cannot save empty DataFrame")
    if not filepath or not isinstance(filepath, str):
        raise ValueError(f"Invalid filepath: {filepath}")

    if decimal_separator == ",":
        kwargs.setdefault("sep", ";")
        kwargs.setdefault("decimal", ",")
    else:
        kwargs.setdefault("sep", ",")
        kwargs.setdefault("decimal", ".")
    df.to_csv(filepath, **kwargs)


def to_excel_robust(df: pd.DataFrame, filepath: str, **kwargs) -> None:
    """
    Writes a DataFrame to an Excel file.

    Args:
        df: Pandas DataFrame to save
        filepath: Destination path (.xlsx)
        **kwargs: Additional arguments for df.to_excel

    Raises:
        ImportError: If openpyxl is not installed
        PermissionError: If file cannot be written
        ValueError: If DataFrame is empty or path is invalid
    """
    if not OPENPYXL_AVAILABLE:
        raise ImportError("openpyxl required for Excel file support")

    # Validation
    if df.empty:
        raise ValueError("Cannot save empty DataFrame")
    if not filepath or not isinstance(filepath, str):
        raise ValueError(f"Invalid filepath: {filepath}")

    kwargs.setdefault("engine", "openpyxl")
    df.to_excel(filepath, **kwargs)


def export_optimization_report(
    reports_dir: str,
    module_name: str,
    rmse: float,
    summary_dict: dict[str, Any],
    solution_df: pd.DataFrame,
    spectra_df: pd.DataFrame,
    plots: list[Any] | None = None,
    extra_sheets: dict[str, pd.DataFrame] | None = None,
    logger: logging.Logger | None = None,
) -> tuple[str | None, str | None]:
    """Unified export for all CERTUS optimization modules.

    Creates both Excel and HTML reports with standardized format.
    """
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    ts = certus_timestamp_file()
    base_name = f"Report_{module_name}_{ts}_RMSE_{rmse:.5f}"
    excel_path = reports_path / f"{base_name}.xlsx"
    html_path = reports_path / f"{base_name}.html"

    try:
        report_sections = build_report_sections(
            summary_dict=summary_dict,
            solution_df=solution_df,
            spectra_df=spectra_df,
            manifest=None,
            extra_sheets=extra_sheets,
        )

        excel_ok = True
        html_ok = True
        if OPENPYXL_AVAILABLE:
            report_result = build_standard_report(
                report_sections,
                excel_path=str(excel_path),
                html_path=str(html_path) if plots else None,
                html_title=f"CERTUS-{module_name} Report",
                run_manifest=None,
                require_complete_manifest=False,
            )
            excel_ok = bool(report_result.get("excel", False))
            html_ok = bool(report_result.get("html", False)) if plots else False
            if logger and excel_ok:
                logger.info("Excel saved: %s", excel_path.name)
            if logger and html_ok:
                logger.info("HTML saved: %s", html_path.name)
        else:
            df_summary = pd.DataFrame([{"Parameter": k, "Value": str(v)} for k, v in summary_dict.items()])
            to_excel_robust(df_summary, str(excel_path))
            excel_ok = True
            if logger:
                logger.info("Simple Excel saved: %s", excel_path.name)
            html_ok = False

        return (str(excel_path) if excel_ok else None), (str(html_path) if html_ok else None)
    except NUMERICAL_FAULT_EXCEPTIONS as e:
        if logger:
            logger.error("Error exporting reports: %s", e)
        return None, None


# =============================================================================
# SHARED MEMORY (STRAT)
# =============================================================================


class SharedIndicesManager:
    """Shared memory manager for optical clues.

    Enables sharing optical index data between processes for parallel
    calculations (used by CERTUS-STRAT).

    Supports context manager protocol for automatic resource management.

    Args:
        clues_at_wl: Dictionary {wavelength: {material: index_value}}

    Example:
        >>> clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}}
        >>> # Use with context manager (recommended)
        >>> with SharedIndicesManager(clues) as manager:
        ...ctx = manager.get_context_info()
        ... # Pass ctx to workers
        >>> # Memory automatically released

        >>> # Manual usage (not recommended)
        >>> manager = SharedIndicesManager(clues)
        >>> ctx = manager.get_context_info()
        >>> manager.close() # Do not forget to close!"""

    def __init__(self, clues_at_wl: dict[float, dict[str, float]]) -> None:
        self.shm = None
        self.dtype = np.float32
        self._serialize(clues_at_wl)

    def __enter__(self) -> Any:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> bool:
        """Context manager exit - automatically closes shared memory."""
        self.close()
        return False  # Don't suppress exceptions

    def _serialize(self, clues_dict: dict[float, dict[str, float]]) -> None:
        """Serializes clues into a numpy array in shared memory.

        Args:
            clues_dict: Dictionary {wavelength: {material: index_value}}"""
        sorted_wls = sorted(clues_dict.keys())
        data = []
        for wl in sorted_wls:
            e = clues_dict[wl]
            # Extract real part from potentially complex clues
            h_val = np.real(e.get("H", 1.0))
            l_val = np.real(e.get("L", 1.0))
            sub_val = np.real(e.get("substrate", e.get("Sub", 1.0)))
            data.append([wl, h_val, l_val, sub_val])

        arr = np.array(data, dtype=self.dtype)
        self.shape = arr.shape
        self.shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
        self.shm_name = self.shm.name

        target = np.ndarray(self.shape, dtype=self.dtype, buffer=self.shm.buf)
        target[:] = arr[:]

    def get_context_info(self) -> dict[str, Any]:
        """
        Returns context info to share with workers.

        Returns:
            Dictionary containing shm_name, shape, dtype for reconstruction
        """
        return {"shm_name": self.shm_name, "shape": self.shape, "dtype": self.dtype}

    def close(self) -> None:
        """
        Closes and releases shared memory.

        Must be called explicitly to avoid memory leaks.
        Called automatically in __del__ but manual call preferred.
        """
        if self.shm:
            try:
                self.shm.close()
                self.shm.unlink()
            except (OSError, FileNotFoundError):
                # Shared memory may already be closed/unlinked
                pass
            self.shm = None

    def __del__(self) -> None:
        self.close()


class SharedIndicesWorker:
    """Worker to access optical clues in shared memory.

    Allows a worker process to access index data shared by SharedIndicesManager.

    Supports context manager protocol for automatic resource management.

    Args:
        ctx: Context dictionary returned by SharedIndicesManager.get_context_info()

    Example:
        >>> # Use with context manager (recommended)
        >>> with SharedIndicesWorker(ctx) as worker:
        ... clues = worker.get(500.0)
        >>> # Memory automatically released

        >>> # Manual usage (not recommended)
        >>> worker = SharedIndicesWorker(ctx)
        >>> clues = worker.get(500.0)
        >>> worker.close()"""

    def __init__(self, ctx: dict[str, Any]) -> None:
        self.shm = shared_memory.SharedMemory(name=ctx["shm_name"])
        self.arr = np.ndarray(ctx["shape"], dtype=ctx["dtype"], buffer=self.shm.buf)
        self.wls = self.arr[:, 0]
        self.vals = self.arr[:, 1:]
        self._cache = {}

    def __enter__(self) -> Any:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> bool:
        """Context manager exit - automatically closes shared memory."""
        self.close()
        return False

    def close(self) -> None:
        if hasattr(self, "shm") and self.shm:
            try:
                self.shm.close()
            except (OSError, FileNotFoundError):
                logging.getLogger("CERTUS").debug("SharedMemory.close() failed (non-critical)", exc_info=True)
            self.shm = None

    def __del__(self) -> None:
        self.close()

    def get(self, wl: float) -> dict[str, float]:
        """Retrieves optical clues for a given wavelength.

        Uses linear interpolation if exact wavelength is missing.

        Args:
            wl: Wavelength in nanometers

        Returns:
            Dictionary {"H": n_H, "L": n_L, "substrate": n_sub}"""
        if wl in self._cache:
            return self._cache[wl]
        idx = np.searchsorted(self.wls, wl)
        if idx >= len(self.wls):
            r = self.vals[-1]
        elif idx == 0:
            r = self.vals[0]
        elif abs(self.wls[idx] - wl) < 1e-5:
            r = self.vals[idx]
        else:
            w0, w1 = self.wls[idx - 1], self.wls[idx]
            t = (wl - w0) / (w1 - w0)
            r = self.vals[idx - 1] + t * (self.vals[idx] - self.vals[idx - 1])

        res = {"H": float(r[0]), "L": float(r[1]), "substrate": float(r[2])}
        if len(self._cache) < 1000:
            self._cache[wl] = res
        return res


class SharedArrayManager:
    """
    Generic shared memory manager for numpy arrays.

    Enables zero-copy sharing of numpy arrays (like cumulative TMM matrices)
    between processes for parallel calculations.

    Supports context manager protocol.
    """

    def __init__(self, arr: np.ndarray) -> None:
        self.shm = None
        self.shape = arr.shape
        self.dtype = arr.dtype
        self._serialize(arr)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> bool:
        self.close()
        return False

    def _serialize(self, arr: np.ndarray) -> None:
        self.shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
        self.shm_name = self.shm.name
        target = np.ndarray(self.shape, dtype=self.dtype, buffer=self.shm.buf)
        target[:] = arr[:]

    def get_context_info(self) -> dict[str, Any]:
        return {
            "shm_name": self.shm_name,
            "shape": self.shape,
            "dtype": str(self.dtype),
        }

    def close(self) -> None:
        if self.shm:
            try:
                self.shm.close()
                self.shm.unlink()
            except (OSError, FileNotFoundError):
                logging.getLogger("CERTUS").debug("SharedMemory.unlink() failed (non-critical)", exc_info=True)
            self.shm = None

    def __del__(self) -> None:
        self.close()


class SharedArrayWorker:
    """
    Worker to access generic numeric arrays in shared memory.

    Supports context manager protocol.
    """

    def __init__(self, ctx: dict[str, Any]) -> None:
        self.shm = shared_memory.SharedMemory(name=ctx["shm_name"])
        self.dtype = np.dtype(ctx["dtype"])
        self.arr = np.ndarray(ctx["shape"], dtype=self.dtype, buffer=self.shm.buf)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> bool:
        self.close()
        return False

    def get_array(self) -> np.ndarray:
        return self.arr

    def close(self) -> None:
        if self.shm:
            try:
                self.shm.close()
            except (OSError, FileNotFoundError):
                logging.getLogger("CERTUS").debug("SharedMemory.close() failed on read (non-critical)", exc_info=True)
            self.shm = None

    def __del__(self) -> None:
        self.close()


# =============================================================================
# PERFORMANCE & LOGGING
# =============================================================================


class TimingLogger:
    """
    Logger to measure and record execution times.

    Allows tracking performance of code sections with auto-logging.

    Example:
        >>> timing = TimingLogger()
        >>> timing.start("calculation")
        >>> # ... code ...
        >>> timing.end("calculation")  # Log: "Finished calculation in 123.45ms"
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Args:
            logger: Custom logger (defaults to "CERTUS.Timing")
        """
        self.logger = logger or logging.getLogger("CERTUS.Timing")
        self.start_times: dict[str, float] = {}

    def start(self, name: str) -> None:
        """
        Start the timer for a named section.

        Args:
            name: Section name to measure
        """
        self.start_times[name] = time.perf_counter()

    def end(self, name: str) -> None:
        """
        Stop the timer and log the elapsed time.

        Args:
            name: Section name (must match the corresponding start() call)
        """
        if name in self.start_times:
            dt = time.perf_counter() - self.start_times.pop(name)
            self.logger.info(f"Finished {name} in {dt * 1000:.2f}ms")

    def start_global(self, name) -> None:
        """Starts a global timing section with emphasized logging."""
        self.logger.info(f"▶️ START GLOBAL: {name}")
        self.start(name)

    def end_global(self, name) -> None:
        """Ends a global timing section."""
        self.end(name)


class PerformanceMonitor:
    """
    Performance monitor to collect timing statistics.

    Automatically collects execution times and generates statistical reports.

    Example:
        >>> monitor = PerformanceMonitor()
        >>> with monitor.measure("optimization"):
        ...     # ... code ...
        >>> print(monitor.report())  # Average statistics
    """

    def __init__(self) -> None:
        self.metrics: dict[str, list[float]] = defaultdict(list)
        self._lock = RLock()

    @contextmanager
    def measure(self, name: str) -> None:
        """
        Context manager to measure a code section.

        Args:
            name: Metric name to measure

        Example:
            >>> with monitor.measure("calculation"):
            ...     result = expensive_function()
        """
        t0 = time.perf_counter()
        yield
        with self._lock:
            self.metrics[name].append(time.perf_counter() - t0)

    def report(self) -> str:
        """
        Generate a performance statistics report.

        Returns:
            Formatted string with averages and sample counts
        """
        if not self.metrics:
            return "No data"
        lines = ["Perf Report:"]
        for k, v in self.metrics.items():
            lines.append(f"{k}: {np.mean(v) * 1000:.2f}ms (n={len(v)})")
        return "\n".join(lines)


PERF_MONITOR = PerformanceMonitor()

# =============================================================================
# REPORTING
# =============================================================================


def generate_html_report(filename: str, title: str, sections: list[dict], figures: list = None) -> bool:
    """
    Generates an HTML report with sections and figures.

    Args:
        filename: Destination path of HTML file
        title: Report title
        sections: List of dictionaries defining sections
                  Format: [{"title": str, "type": str, "content": Any}, ...]
                  Supported types: 'text', 'kv', 'table', 'image'
        figures: Optional list of figures to include (PyQt widgets or base64)

    Returns:
        True if success, False otherwise

    Raises:
        ValueError: If filename invalid or sections empty
        PermissionError: If file cannot be written

    Example:
        >>> sections = [{"title": "Results", "type": "table", "content": df}]
        >>> generate_html_report("report.html", "Analysis", sections)
    """
    # Validation
    if not filename or not isinstance(filename, str):
        raise ValueError(f"Invalid filename: {filename}")
    if not sections:
        raise ValueError("Sections list cannot be empty")

    try:
        from PyQt6.QtCore import QBuffer, QIODevice

        css = (
            "body { font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f8fafc; color: #1e293b; }"
            ".container { max-width: 1000px; margin: 0 auto; background: white; padding: 50px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }"
            "h1 { color: #2563eb; text-align: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }"
            "h2 { border-left: 4px solid #2563eb; padding-left: 10px; margin-top: 40px; }"
            "table { width: 100%; border-collapse: collapse; margin: 20px 0; }"
            "th, td { padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: left; }"
            "th { background: #f8fafc; color: #475569; }"
            ".img-container { text-align: center; margin: 30px 0; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; }"
            "img { max-width: 100%; height: auto; }"
        )

        html = [f"<html><head><title>{title}</title><style>{css}</style></head><body><div class='container'>"]
        html.append(f"<h1>{title}</h1>")

        for sec in sections:
            html.append(f"<h2>{sec.get('title', '')}</h2>")
            typ = sec.get("type", "text")
            cnt = sec.get("content", "")

            if typ == "text":
                html.append(f"<p>{cnt}</p>")
            elif typ == "kv":
                grid_style = "display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;"
                html.append(f"<div style='{grid_style}'>")
                for k, v in cnt.items():
                    item_style = "background:#f1f5f9; padding:10px; border-radius:6px;"
                    html.append(f"<div style='{item_style}'><b>{k}</b><br>{v}</div>")
                html.append("</div>")
            elif typ == "table":
                if isinstance(cnt, pd.DataFrame):
                    html.append(cnt.to_html(border=0, classes="dataframe", index=False))
                elif isinstance(cnt, list) and cnt and isinstance(cnt[0], dict):
                    html.append(pd.DataFrame(cnt).to_html(border=0, classes="dataframe", index=False))
                elif isinstance(cnt, dict):
                    html.append(pd.DataFrame([cnt]).to_html(border=0, classes="dataframe", index=False))
                else:
                    try:
                        html.append(pd.DataFrame(cnt).to_html(border=0, classes="dataframe", index=False))
                    except NUMERICAL_FAULT_EXCEPTIONS:
                        html.append("<p>Table content could not be rendered.</p>")
            elif typ == "image":
                html.append(f"<div class='img-container'><img src='data:image/png;base64,{cnt}'></div>")

        if figures:
            html.append("<h2>Visual Analysis</h2>")
            for fig in figures:
                b64 = None
                if isinstance(fig, str):
                    b64 = fig
                elif hasattr(fig, "grab"):
                    img = fig.grab().toImage()
                    b = QBuffer()
                    b.open(QIODevice.OpenModeFlag.WriteOnly)
                    img.save(b, "PNG")
                    b64 = base64.b64encode(b.data()).decode()

                if b64:
                    html.append(f"<div class='img-container'><img src='data:image/png;base64,{b64}'></div>")

        html.append("</div></body></html>")

        with open(filename, "w", encoding="utf-8") as f:
            f.write("".join(html))
        return True
    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logging.error(f"Report Error: {e}")
        return False


# =============================================================================
# STANDARD REPORT BUILDER (P6 scaffold)
# =============================================================================
#
# ``ReportSection`` + ``build_standard_report`` factorise the pattern
# duplicated across INDEX / DESIGN / METAL_SINGLE / METAL_BILAYER export
# helpers (see audit §A4). Each app can gradually migrate by building a
# list of ``ReportSection`` and calling ``build_standard_report`` instead
# of maintaining its own Excel-+-HTML writer.
#
# The builder is **opt-in** and purely additive: existing exporters keep
# working unchanged.


@dataclass(frozen=True)
class ReportSection:
    """Describe one section of a standard export report.

    Parameters
    ----------
    title : str
        Section title (used both as Excel sheet name prefix and HTML ``<h2>``).
    kind : str
        Section kind. Supported values:

        - ``"text"`` : ``content`` is a string paragraph.
        - ``"kv"``   : ``content`` is a ``dict[str, Any]`` rendered as a
          key-value grid (HTML) and a 2-column sheet (Excel).
        - ``"table"``: ``content`` is a ``pandas.DataFrame`` (or anything
          coercible to one). Rendered as an HTML table and a dedicated
          Excel sheet.
        - ``"image"``: ``content`` is a base64-encoded PNG (HTML only).
    content : Any
        Payload as described above.
    sheet_name : str, optional
        Override for the Excel sheet name. Defaults to ``title`` truncated
        to the Excel 31-char limit.
    include_in_html : bool
        If False, section is skipped in HTML (useful for bulky raw data).
    include_in_excel : bool
        If False, section is skipped in Excel (useful for pure visuals).
    """

    title: str
    kind: str
    content: Any
    sheet_name: str | None = None
    include_in_html: bool = True
    include_in_excel: bool = True

    # ---- conversion helpers ------------------------------------------------

    def to_html_dict(self) -> dict[str, Any]:
        """Return the legacy dict form accepted by :func:`generate_html_report`."""

        return {"title": self.title, "type": self.kind, "content": self.content}

    def excel_sheet_name(self) -> str:
        """Return a safe Excel sheet name (truncated, no illegal chars)."""

        raw = self.sheet_name or self.title or "Sheet"
        # Excel forbids: \\ / ? * [ ] :
        cleaned = raw
        for ch in "\\/?*[]:":
            cleaned = cleaned.replace(ch, "_")
        return cleaned[:EXCEL_SHEET_NAME_MAX_LENGTH] or "Sheet"


def build_standard_report(
    sections: list[ReportSection],
    *,
    excel_path: str | None = None,
    html_path: str | None = None,
    html_title: str = "CERTUS Report",
    run_manifest: Any | None = None,
    require_complete_manifest: bool = False,
) -> dict[str, bool]:
    """Write a multi-section report to Excel and/or HTML in a single call.

    This is the opt-in replacement for the Excel-+-HTML boilerplate copy-pasted
    across CERTUS monoliths (audit §A4). Apps provide the section list; the
    helper handles Excel sheet generation (one sheet per ``table`` / ``kv``
    section) and HTML rendering via :func:`generate_html_report`.

    Parameters
    ----------
    sections : list[ReportSection]
        Ordered list of report sections. Sections with ``include_in_excel=False``
        or ``include_in_html=False`` are skipped in the respective output.
    excel_path : str or None
        Destination path for the ``.xlsx`` file. If ``None``, Excel output
        is skipped.
    html_path : str or None
        Destination path for the ``.html`` file. If ``None``, HTML output
        is skipped.
    html_title : str
        Title for the HTML report (Excel does not use it).
    run_manifest : Any | None
        Optional run manifest. If provided, a ``Manifest`` key/value section is
        appended to both Excel and HTML outputs.
    require_complete_manifest : bool
        If True, report generation is blocked unless ``run_manifest`` is present
        and contains all required fields (``run_id``, ``started_at_utc``,
        ``app_id``, ``app_version``, ``status``, ``params_hash``).

    Returns
    -------
    dict[str, bool]
        Keys ``"excel"`` and ``"html"`` with ``True`` when the corresponding
        output was written successfully, ``False`` on error, and ``None``
        (missing key) when the caller did not request that output.
    """

    result: dict[str, bool] = {}
    report_sections = list(sections)
    manifest_kv: dict[str, Any] | None = None
    if run_manifest is not None:
        if hasattr(run_manifest, "as_flat_dict"):
            manifest_kv = dict(run_manifest.as_flat_dict())
        elif isinstance(run_manifest, dict):
            manifest_kv = dict(run_manifest)
        else:
            manifest_kv = {"manifest": str(run_manifest)}

    if require_complete_manifest:
        missing_fields = get_missing_manifest_fields(manifest_kv)
        if missing_fields:
            logging.error(
                "Standard report blocked: incomplete manifest (missing: %s)",
                ", ".join(missing_fields),
            )
            if excel_path:
                result["excel"] = False
            if html_path:
                result["html"] = False
            return result

    if manifest_kv is not None:
        report_sections.append(
            ReportSection(
                title="Manifest",
                kind="kv",
                content=manifest_kv,
                sheet_name="Manifest",
                include_in_html=True,
                include_in_excel=True,
            )
        )

    # --- Excel -------------------------------------------------------------
    if excel_path:
        try:
            used_names: set[str] = set()
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                summary_rows: list[dict[str, Any]] = []
                for sec in report_sections:
                    if not sec.include_in_excel:
                        continue
                    if sec.kind == "table":
                        df = sec.content
                        if not isinstance(df, pd.DataFrame):
                            try:
                                df = pd.DataFrame(df)
                            except (ValueError, TypeError):
                                continue
                        name = sec.excel_sheet_name()
                        # De-duplicate sheet names
                        base = name
                        k = 2
                        while name in used_names:
                            name = f"{base[: EXCEL_SHEET_NAME_MAX_LENGTH - 2]}_{k}"
                            k += 1
                        used_names.add(name)
                        df.to_excel(writer, sheet_name=name, index=False)
                    elif sec.kind == "kv":
                        content = sec.content
                        if not isinstance(content, dict):
                            continue
                        name = sec.excel_sheet_name()
                        base = name
                        k = 2
                        while name in used_names:
                            name = f"{base[: EXCEL_SHEET_NAME_MAX_LENGTH - 2]}_{k}"
                            k += 1
                        used_names.add(name)
                        df = pd.DataFrame(
                            [(k, v) for k, v in content.items()],
                            columns=["Key", "Value"],
                        )
                        df.to_excel(writer, sheet_name=name, index=False)
                    elif sec.kind == "text":
                        summary_rows.append({"Section": sec.title, "Content": str(sec.content)})
                    # "image" sections are HTML-only
                if summary_rows and "Summary" not in used_names:
                    pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
            result["excel"] = True
        except (ValueError, TypeError, RuntimeError, OSError, PermissionError) as e:
            logging.error(f"Standard report Excel error: {e}")
            result["excel"] = False

    # --- HTML --------------------------------------------------------------
    if html_path:
        html_sections = [s.to_html_dict() for s in report_sections if s.include_in_html]
        if html_sections:
            result["html"] = generate_html_report(html_path, html_title, html_sections)
        else:
            result["html"] = False

    return result


MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id",
    "started_at_utc",
    "app_id",
    "app_version",
    "status",
    "params_hash",
    "materials_db_hash",
)


def get_missing_manifest_fields(manifest: dict[str, Any] | None) -> list[str]:
    """Return missing required RunManifest fields for gate checks."""
    if manifest is None:
        return list(MANIFEST_REQUIRED_FIELDS)
    return [key for key in MANIFEST_REQUIRED_FIELDS if manifest.get(key) in (None, "")]


def build_export_context(
    *,
    module_name: str,
    title: str,
    rmse: float | None = None,
    subtitle: str = "",
    app_name: str = "CERTUS",
    author: str = "",
    source_paths: list[str] | None = None,
    run_manifest: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    status: str | None = None,
) -> ReportContext:
    """Build a consistent report context for all CERTUS exports."""
    meta_bits = [module_name]
    if rmse is not None and np.isfinite(float(rmse)):
        meta_bits.append(f"RMSE={float(rmse):.6f}")
    if status:
        meta_bits.append(f"status={status}")
    if warnings:
        meta_bits.append(f"warnings={len(warnings)}")
    if source_paths:
        meta_bits.append(f"sources={len(source_paths)}")
    subtitle_full = " | ".join([subtitle] + [bit for bit in meta_bits if bit]) if subtitle else " | ".join(meta_bits)
    return ReportContext(
        title=title,
        subtitle=subtitle_full,
        app_name=app_name,
        author=author,
        run_manifest=run_manifest,
    )


def build_report_sections(
    *,
    summary_dict: dict[str, Any],
    solution_df: pd.DataFrame,
    spectra_df: pd.DataFrame,
    manifest: dict[str, Any] | None = None,
    extra_sheets: dict[str, pd.DataFrame] | None = None,
) -> list[ReportSection]:
    """Build the standard CERTUS optimization report sections."""
    sections: list[ReportSection] = [
        ReportSection(title="Optimization Summary", kind="kv", content=dict(summary_dict)),
        ReportSection(title="Solution Parameters", kind="table", content=solution_df.copy() if solution_df is not None else pd.DataFrame()),
        ReportSection(title="Spectra", kind="table", content=spectra_df.copy() if spectra_df is not None else pd.DataFrame()),
    ]
    if manifest is not None:
        sections.append(ReportSection(title="Manifest", kind="kv", content=dict(manifest)))
    if extra_sheets:
        for name, df in extra_sheets.items():
            sections.append(ReportSection(title=str(name), kind="table", content=df.copy()))
    return sections


def validate_manifest_for_export(
    manifest: dict[str, Any] | None,
    *,
    auto: bool = False,
    logger: logging.Logger | None = None,
    module_name: str = "",
) -> tuple[bool, list[str]]:
    """Validate a manifest before export; return (ok, missing_fields)."""
    missing = get_missing_manifest_fields(manifest)
    if missing and logger:
        logger.error(
            "[%s.export] blocked export | reason=incomplete manifest | missing=%s | auto=%s",
            module_name or "CERTUS",
            ", ".join(missing),
            auto,
        )
    return (not missing), missing


# =============================================================================
# SPECTRUM LOADER (P8 scaffold)
# =============================================================================
#
# ``load_spectrum_columns`` factorise the column-detection / sort / unit-
# normalisation boilerplate currently duplicated across ``CERTUS_INDEX.load_file``,
# ``CERTUS_INDEX_SPLINE._DataMixin``, ``certus_substrate_index.load_file`` and
# ``certus_spectrum_eval_ui``. The helper is **opt-in** and purely additive;
# apps can migrate progressively by calling it from their own ``load_file``.
#
# The returned ``SpectrumLoadResult`` separates the cleaned DataFrame from
# the numeric arrays callers usually extract manually (wavelength, T, R).


@dataclass(frozen=True)
class SpectrumLoadResult:
    """Structured result of :func:`load_spectrum_columns`.

    Attributes
    ----------
    dataframe : pd.DataFrame
        Cleaned DataFrame with monotonic ``x`` and up to two ``y`` columns.
        Column names are normalised to ``("lambda", "T", "R")`` when detected
        by the default ``column_roles`` heuristic, or kept from the source
        file otherwise.
    x : np.ndarray
        First column (wavelengths) as a 1-D ``float64`` array.
    y_columns : dict[str, np.ndarray]
        Additional numeric columns keyed by their (normalised) name.
    x_unit : str
        Detected or forced unit for ``x`` (``"nm"`` or ``"um"``).
    normalised_to_fraction : bool
        True if any ``y`` column had values > 1.5 and was divided by 100
        (percentage → fraction heuristic).
    n_rows : int
        Number of rows after dropping non-numeric entries.
    source_path : str
        Absolute path of the loaded file.
    """

    dataframe: "pd.DataFrame"
    x: "np.ndarray"
    y_columns: dict[str, "np.ndarray"]
    x_unit: str
    normalised_to_fraction: bool
    n_rows: int
    source_path: str


def _detect_x_unit(x: "np.ndarray", hint: str | None = None) -> str:
    """Detect whether ``x`` is expressed in ``nm`` (≈ 200–20000) or ``um``
    (≈ 0.2–20). Falls back to ``hint`` or ``nm``."""

    if hint in ("nm", "um"):
        return hint
    if x.size == 0:
        return hint or "nm"
    x_max = float(np.nanmax(x))
    # Typical CERTUS ranges: 300..2500 nm, i.e. 0.3..2.5 µm.
    if x_max < 50.0:
        return "um"
    return "nm"


def load_spectrum_columns(
    path: str,
    *,
    max_columns: int = 3,
    normalise_percent: bool = True,
    sort_ascending: bool = True,
    x_unit: str | None = None,
    to_nm: bool = True,
    column_roles: dict[int, str] | None = None,
    **read_kwargs,
) -> SpectrumLoadResult:
    """Load a CERTUS-style 2- or 3-column spectrum from a CSV/Excel file.

    Common ingestion pipeline:
    1. Dispatch to :func:`read_data_file_robust` based on extension.
    2. Keep only the first ``max_columns`` columns.
    3. Coerce every cell to numeric, drop rows with NaN.
    4. Sort ascending (by default) on the first column, reset index.
    5. Normalise ``%`` values (>1.5 in any ``y`` column) to fractions.
    6. Convert ``x`` from µm to nm when ``to_nm=True`` and the unit is ``um``.
    7. Rename columns using ``column_roles`` (default: ``{0:"lambda", 1:"T", 2:"R"}``).

    Parameters
    ----------
    path : str
        Path to the CSV or Excel file.
    max_columns : int, default 3
        Keep only the first ``max_columns`` numeric columns.
    normalise_percent : bool, default True
        If True, any ``y`` column whose max > 1.5 is divided by 100 (percent
        → fraction heuristic).
    sort_ascending : bool, default True
        Sort rows by the first column in ascending order.
    x_unit : {"nm", "um", None}, default None
        Force the x unit. When ``None`` the unit is auto-detected from the
        range (< 50 → ``um``; otherwise ``nm``).
    to_nm : bool, default True
        If ``x_unit`` resolves to ``um``, multiply ``x`` by 1000 to obtain
        nanometers. Result's ``x_unit`` becomes ``"nm"`` in that case.
    column_roles : dict[int, str] or None
        Mapping column index → normalised name. Default:
        ``{0: "lambda", 1: "T", 2: "R"}``. Use ``{}`` to keep source names.
    **read_kwargs
        Forwarded to :func:`read_data_file_robust` (e.g. ``header=0``).

    Returns
    -------
    SpectrumLoadResult

    Raises
    ------
    FileNotFoundError
        If ``path`` cannot be read.
    ValueError
        If the file has no numeric columns or the resulting DataFrame is
        empty after NaN-filtering.
    """

    abs_path = Path(path).resolve(strict=False)
    if not abs_path.exists():
        raise FileNotFoundError(f"Spectrum file not found: {abs_path}")

    df = read_data_file_robust(str(abs_path), **read_kwargs)

    n_cols = min(max_columns, len(df.columns))
    if n_cols < 1:
        raise ValueError(f"Spectrum file has no columns: {abs_path}")
    df = df.iloc[:, :n_cols].copy()

    # Coerce to numeric, drop NaN rows
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    if df.empty:
        raise ValueError(f"Spectrum file is empty after numeric coercion: {abs_path}")

    # Sort on first column
    if sort_ascending and len(df) > 1:
        df = df.sort_values(by=df.columns[0], kind="mergesort").reset_index(drop=True)

    # Rename columns
    roles = column_roles if column_roles is not None else {0: "lambda", 1: "T", 2: "R"}
    if roles:
        new_names = [roles.get(i, str(df.columns[i])) for i in range(len(df.columns))]
        df.columns = new_names

    # Extract x
    x = as_float64_1d(df.iloc[:, 0].to_numpy(dtype=float, copy=False))

    # Unit detection + conversion
    detected_unit = _detect_x_unit(x, hint=x_unit)
    if to_nm and detected_unit == "um":
        x = x * 1000.0
        df.isetitem(0, x)
        result_unit = "nm"
    else:
        result_unit = detected_unit

    # Percent → fraction heuristic on y columns
    normalised = False
    if normalise_percent and len(df.columns) > 1:
        for i in range(1, len(df.columns)):
            values = as_float64_1d(df.iloc[:, i].to_numpy(dtype=float, copy=True), copy=True)
            col_max = float(np.nanmax(values))
            if col_max > 1.5:
                # ``isetitem`` replaces the column in-place regardless of dtype,
                # avoiding FutureWarning on int->float promotion and working
                # even when two source columns share a name.
                df.isetitem(i, values / 100.0)
                normalised = True

    # y_columns dict (everything after x)
    y_columns: dict[str, np.ndarray] = {}
    for i in range(1, len(df.columns)):
        y_columns[str(df.columns[i])] = as_float64_1d(df.iloc[:, i].to_numpy(dtype=float, copy=False))

    return SpectrumLoadResult(
        dataframe=df,
        x=x,
        y_columns=y_columns,
        x_unit=result_unit,
        normalised_to_fraction=normalised,
        n_rows=int(len(df)),
        source_path=str(abs_path),
    )


# =============================================================================
# LOGGING UTILITIES
# =============================================================================

# QueueHandler and setup_gui_logger are defined in certus_core.py (Single Source of Truth)
from certus_core import QueueHandler, setup_gui_logger
