"""Extra comprehensive coverage tests for certus_data.py and certus_metrology.py.
Covers all remaining import exceptions, OSError/ValueError fallbacks, PyQt visual html report grab buffers,
and sheet de-duplication branches.
"""

import sys
import os
import base64
import logging
import importlib
from pathlib import Path
from unittest.mock import Mock, patch
from importlib.machinery import SourceFileLoader

import pytest
import numpy as np
import pandas as pd

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage

import certus.utils.certus_data as certus_data
from certus.utils.certus_data import (
    read_csv_robust,
    read_excel_robust,
    read_data_file_robust,
    to_excel_robust,
    export_optimization_report,
    SharedIndicesManager,
    SharedIndicesWorker,
    SharedArrayManager,
    SharedArrayWorker,
    TimingLogger,
    PerformanceMonitor,
    generate_html_report,
    ReportSection,
    build_standard_report,
    get_missing_manifest_fields,
    load_spectrum_columns,
    _detect_x_unit,
)
import certus.core.certus_metrology as certus_metrology
from certus.core.certus_metrology import (
    RunContext,
    RunManifest,
    ValidationStatus,
    compute_params_hash,
)

# ─────────────────────────────────────────────────────────────────────
#1. certus_metrology.py Exception & ImportError Fallback Tests
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_metrology_imports_and_exceptions(monkeypatch) -> None:
    # A. Test missing certus_core version & materials DB hash fallback using isolated loader
    # to avoid redefining types in sys.modules["certus_metrology"] which breaks other tests.
    import builtins
    real_import = builtins.__import__
    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "certus.core.certus_core":
            raise ImportError("mocked")
        return real_import(name, globals, locals, fromlist, level)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    import importlib.util
    file_path = str(Path(certus_metrology.__file__).resolve())
    spec = importlib.util.spec_from_file_location("certus_metrology_fallback", file_path)
    fallback_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fallback_mod)
    
    assert fallback_mod.CERTUS_VERSION == "unknown"
    assert fallback_mod.get_materials_db_hash() == ""
    
    
    
    # B. Test missing PyQt6 version detection exception
    monkeypatch.setattr(certus_metrology, "version", Mock(side_effect=certus_metrology.PackageNotFoundError("PyQt6")))
    assert certus_metrology._detect_pyqt_version() == "unknown"
    
    # C. Test Numba threading layer error fallbacks
    import numba
    monkeypatch.setattr(numba, "threading_layer", Mock(side_effect=RuntimeError("numba thread layer error")))
    assert certus_metrology._detect_threading_layer() == "unknown"
    
    # D. Test locale lookup OSError/ValueError fallbacks
    import locale
    monkeypatch.setattr(locale, "getlocale", Mock(side_effect=ValueError("locale error")))
    assert certus_metrology._detect_locale() == ""
    
    # E. Test platform processor / machine OSError/ValueError fallbacks
    import platform
    monkeypatch.setattr(platform, "processor", Mock(side_effect=OSError("processor error")))
    monkeypatch.setattr(platform, "machine", Mock(side_effect=ValueError("machine error")))
    assert certus_metrology._detect_cpu_brand() == ""


# ─────────────────────────────────────────────────────────────────────
# 2. certus_data.py Robust CSV/Excel Fallbacks
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_read_csv_robust_failures(tmp_path, monkeypatch) -> None:
    f = tmp_path / "corrupt_data.csv"
    f.write_text("wl,R,T\n400,0.1,0.9\n500,0.2,0.8\n", encoding="utf-8")

    # A. Test intermediate pd.read_csv ValueError/ParserError fallback
    original_read_csv = pd.read_csv
    calls = []

    def mock_read_csv(filepath, **kwargs):
        calls.append(kwargs.get("decimal"))
        if len(calls) == 1:
            raise pd.errors.ParserError("Simulated intermediate parse error")
        return original_read_csv(filepath, **kwargs)

    monkeypatch.setattr(pd, "read_csv", mock_read_csv)
    df = read_csv_robust(str(f))
    assert len(df) == 2
    assert calls == [".", ","]

    # B. Test extreme fallback path
    calls_extreme = []
    def mock_read_csv_extreme(filepath, **kwargs):
        calls_extreme.append(kwargs)
        if len(calls_extreme) < 3:
            raise ValueError("Extreme parse error")
        return original_read_csv(filepath, sep=None, engine="python")

    monkeypatch.setattr(pd, "read_csv", mock_read_csv_extreme)
    df_ext = read_csv_robust(str(f))
    assert len(df_ext) == 2
    assert len(calls_extreme) == 3

    # C. Test columns numeric conversion exception pathway
    # We can pass an object column that cannot be converted to numeric
    # containing list objects, which raises a TypeError/ValueError on to_numeric.
    df_unconvertible = pd.DataFrame({"col1": [[1], [2]]})
    f_unconv = tmp_path / "unconv.csv"
    df_unconvertible.to_csv(str(f_unconv), index=False)
    df_res = read_csv_robust(str(f_unconv))
    assert len(df_res) == 2


@pytest.mark.unit
def test_excel_openpyxl_not_installed_exception(monkeypatch) -> None:
    # Force openpyxl to be missing
    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", False)

    with pytest.raises(ImportError, match="openpyxl required"):
        read_excel_robust("dummy.xlsx")

    with pytest.raises(ImportError, match="openpyxl required"):
        to_excel_robust(pd.DataFrame({"a": [1]}), "dummy.xlsx")


@pytest.mark.unit
def test_read_excel_robust_validations_and_failures(tmp_path, monkeypatch) -> None:
    # Set OPENPYXL_AVAILABLE to True to hit validation blocks
    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", True)

    with pytest.raises(ValueError, match="Invalid filepath"):
        read_excel_robust("")

    with pytest.raises(FileNotFoundError, match="File not found"):
        read_excel_robust("non_existent_excel_file_12345.xlsx")

    # Excel numeric conversion exception pathway
    # We create a dummy dataframe and mock pd.read_excel to return it
    df_unconvertible = pd.DataFrame({"col1": [object(), object()]})
    monkeypatch.setattr(pd, "read_excel", Mock(return_value=df_unconvertible))
    
    # We create a dummy file just to pass the file exists validation
    f_dummy = tmp_path / "dummy.xlsx"
    f_dummy.write_text("dummy content")

    df_res = read_excel_robust(str(f_dummy))
    assert len(df_res) == 2


@pytest.mark.unit
def test_to_excel_robust_validations(monkeypatch) -> None:
    monkeypatch.setattr("certus.utils.certus_data.OPENPYXL_AVAILABLE", True)

    with pytest.raises(ValueError, match="Cannot save empty DataFrame"):
        to_excel_robust(pd.DataFrame(), "dummy.xlsx")

    with pytest.raises(ValueError, match="Invalid filepath"):
        to_excel_robust(pd.DataFrame({"a": [1]}), "")


# ─────────────────────────────────────────────────────────────────────
# 3. export_optimization_report Edge Cases
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_export_optimization_report_numerical_fault_exceptions(tmp_path, monkeypatch) -> None:
    # Mock pd.ExcelWriter to raise ValueError inside the try-except block
    monkeypatch.setattr(pd, "ExcelWriter", Mock(side_effect=ValueError("ExcelWriter error")))

    res_excel, res_html = export_optimization_report(
        reports_dir=str(tmp_path),
        module_name="METAL",
        rmse=0.0123,
        summary_dict={"A": 1},
        solution_df=pd.DataFrame({"param": ["d"], "value": [10.0]}),
        spectra_df=pd.DataFrame({"wl": [400], "R": [0.1]}),
        logger=logging.getLogger("CERTUS"),
    )
    assert res_excel is None
    assert res_html is None


@pytest.mark.unit
def test_export_optimization_report_success_with_plots(tmp_path) -> None:
    # Mock PyQt widget with grab() support
    mock_plot = Mock()
    mock_qimage = Mock()
    mock_plot.grab.return_value.toImage.return_value = mock_qimage
    mock_qimage.save = lambda buffer, fmt: buffer.write(b"mocked_png") or True

    res_excel, res_html = export_optimization_report(
        reports_dir=str(tmp_path),
        module_name="DESIGN",
        rmse=0.0005,
        summary_dict={"Wavelength range": "400-800nm"},
        solution_df=pd.DataFrame({"thickness": [45.2, 112.5]}),
        spectra_df=pd.DataFrame({"wl": [500], "R_calc": [0.2]}),
        plots=[mock_plot],
        extra_sheets={"ExtraTab": pd.DataFrame({"val": [1, 2, 3]})},
    )
    assert res_excel is not None
    assert res_html is not None
    assert Path(res_excel).exists()
    assert Path(res_html).exists()


# ─────────────────────────────────────────────────────────────────────
#4. Shared Memory Close Exception Paths
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_shared_memory_close_exception_safeties(monkeypatch) -> None:
    clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}}
    
    # A. SharedIndicesManager close OSError handling
    mgr = SharedIndicesManager(clues)
    assert mgr.shm is not None
    # Force self.shm.close to raise OSError
    monkeypatch.setattr(mgr.shm, "close", Mock(side_effect=OSError("Already unlinked")))
    mgr.close()
    assert mgr.shm is None

    # B. SharedIndicesWorker close OSError handling
    mgr2 = SharedIndicesManager(clues)
    ctx = mgr2.get_context_info()
    worker = SharedIndicesWorker(ctx)
    monkeypatch.setattr(worker.shm, "close", Mock(side_effect=OSError("Worker shm close failed")))
    worker.close()
    assert worker.shm is None
    mgr2.close()

    # C. SharedArrayManager close OSError handling
    arr = np.array([1.0, 2.0, 3.0])
    arr_mgr = SharedArrayManager(arr)
    monkeypatch.setattr(arr_mgr.shm, "close", Mock(side_effect=OSError("Array shm close failed")))
    arr_mgr.close()
    assert arr_mgr.shm is None

    # D. SharedArrayWorker close OSError handling
    arr_mgr2 = SharedArrayManager(arr)
    arr_ctx = arr_mgr2.get_context_info()
    arr_worker = SharedArrayWorker(arr_ctx)
    monkeypatch.setattr(arr_worker.shm, "close", Mock(side_effect=OSError("Array worker close failed")))
    arr_worker.close()
    assert arr_worker.shm is None
    arr_mgr2.close()


@pytest.mark.unit
def test_shared_indices_worker_exact_match_and_large_cache() -> None:
    clues = {
        500.0: {"H": 2.0, "L": 1.0, "substrate": 1.5},
        500.000001: {"H": 2.1, "L": 1.1, "substrate": 1.6},
    }
    with SharedIndicesManager(clues) as mgr:
        ctx = mgr.get_context_info()
        with SharedIndicesWorker(ctx) as worker:
            # Exact match logic (difference < 1e-5) at index 1
            r = worker.get(500.000001)
            assert r["H"] == pytest.approx(2.1)

            # Force cache to not insert once size reaches 1000, using keys that do not include 500.0
            worker._cache = {float(i): {"H": 1.0} for i in range(1000, 2000)}
            r_uncached = worker.get(500.0)
            # Wavelength not stored in cached dict because cache is full and key wasn't in cache
            assert 500.0 not in worker._cache


# ─────────────────────────────────────────────────────────────────────
# 5. Visual Reports (PyQt buffering & HTML images)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_generate_html_report_visual_buffering(tmp_path) -> None:
    sections = [
        {"title": "Summary", "type": "kv", "content": {"A": 1}},
        {"title": "TextSection", "type": "text", "content": "hello paragraph"},
        {"title": "TableListSection", "type": "table", "content": [{"Key": "Val"}]},
        {"title": "TableDictSection", "type": "table", "content": {"Key": "Val"}},
        {"title": "TableOtherSection", "type": "table", "content": "not_a_valid_table_payload"},
        {"title": "visual", "type": "image", "content": "base64_data_xyz"},
    ]
    html_file = tmp_path / "visual_report.html"

    # Mock PyQt widget with grab() support
    mock_widget = Mock()
    mock_qimage = Mock()
    mock_widget.grab.return_value.toImage.return_value = mock_qimage

    # Mock the QImage save method to return True
    def mock_save(buffer, fmt):
        buffer.write(b"mocked_png_binary")
        return True

    mock_qimage.save = mock_save

    res = generate_html_report(
        str(html_file),
        title="Visual Smoke Test",
        sections=sections,
        figures=["string_base64_visual", mock_widget],
    )
    assert res is True
    assert html_file.exists()
    content = html_file.read_text(encoding="utf-8")
    assert "mocked_png_binary" not in content # Encoded in base64
    assert "Visual Smoke Test" in content

    # Validation errors for generate_html_report
    with pytest.raises(ValueError, match="Invalid filename"):
        generate_html_report("", "Title", [{"title": "Summary"}])

    with pytest.raises(ValueError, match="Sections list cannot be empty"):
        generate_html_report("dummy.html", "Title", [])

    # Write exception path: raising a Value Error on open()
    with patch("builtins.open", Mock(side_effect=ValueError("open mock error"))):
        res_fail = generate_html_report(
            str(html_file),
            title="Title",
            sections=[{"title": "Summary", "type": "text", "content": "text"}]
        )
        assert res_fail is False


# ─────────────────────────────────────────────────────────────────────
# 6. build_standard_report & RunManifest Flat sections
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_standard_report_manifest_variations(tmp_path) -> None:
    # A. Test run_manifest standard object string conversion fallback
    sections = [ReportSection(title="Summary", kind="kv", content={"X": 1})]
    excel_file = tmp_path / "std_report.xlsx"
    html_file = tmp_path / "std_report.html"

    # Raw manifest standard object
    class CustomManifest:
        def __str__(self):
            return "CustomManifestStr"

    res = build_standard_report(
        sections,
        excel_path=str(excel_file),
        html_path=str(html_file),
        run_manifest=CustomManifest(),
    )
    assert res["excel"] is True
    assert res["html"] is True

    # B. Test require_complete_manifest validation failures
    res_incomplete = build_standard_report(
        sections,
        excel_path=str(excel_file),
        html_path=str(html_file),
        run_manifest={"run_id": "missing_others"},
        require_complete_manifest=True,
    )
    assert res_incomplete["excel"] is False
    assert res_incomplete["html"] is False

    # Also test Excel only path for incomplete manifest
    res_incomplete_excel = build_standard_report(
        sections,
        excel_path=str(excel_file),
        run_manifest={"run_id": "missing_others"},
        require_complete_manifest=True,
    )
    assert res_incomplete_excel["excel"] is False

    # C. Test sheet name deduplication & long duplicate truncation
    long_dup_title = "A" * 40
    dup_sections = [
        ReportSection(title="Spectra", kind="table", content=pd.DataFrame({"wl": [400]})),
        ReportSection(title="Spectra", kind="table", content=pd.DataFrame({"wl": [500]})), # duplicate title
        ReportSection(title=long_dup_title, kind="table", content=pd.DataFrame({"val": [1.0]})),
        ReportSection(title=long_dup_title, kind="table", content=pd.DataFrame({"val": [2.0]})), # duplicate + long
        ReportSection(title="CorruptTable", kind="table", content=12345), # non-coercible table
        ReportSection(title="CorruptKV", kind="kv", content="not_a_dict"), # non-coercible kv
    ]
    res_dup = build_standard_report(
        dup_sections,
        excel_path=str(tmp_path / "dup_std_report.xlsx"),
    )
    assert res_dup["excel"] is True

    # D. Test standard report HTML missing sections pathway
    res_empty_html = build_standard_report(
        [ReportSection(title="Summary", kind="kv", content={"A": 1}, include_in_html=False)],
        html_path=str(html_file),
    )
    assert res_empty_html["html"] is False


# ─────────────────────────────────────────────────────────────────────
# 7. Spectrum Loader (load_spectrum_columns) Edge Cases
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_load_spectrum_columns_edge_cases(tmp_path) -> None:
    # A. Test empty after numeric coercion
    f_empty = tmp_path / "empty.csv"
    f_empty.write_text("a,b\nfoo,bar\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty after numeric coercion"):
        load_spectrum_columns(str(f_empty))

    # B. Test Empty x unit auto-detect range
    f_um = tmp_path / "microns.csv"
    f_um.write_text("lambda,T\n0.5,0.9\n1.5,0.8\n", encoding="utf-8")
    # Convert um to nm on load
    res = load_spectrum_columns(str(f_um), to_nm=True)
    assert res.x_unit == "nm"
    assert np.allclose(res.x, [500.0, 1500.0])

    # C. Test _detect_x_unit empty x
    assert _detect_x_unit(np.array([]), hint="nm") == "nm"
    assert _detect_x_unit(np.array([])) == "nm"

    # D. Test no columns error pathway
    with patch("certus.utils.certus_data.read_data_file_robust", return_value=pd.DataFrame()):
        with pytest.raises(ValueError, match="Spectrum file has no columns"):
            load_spectrum_columns(str(f_um))
