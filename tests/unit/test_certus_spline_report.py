"""Targeted tests for certus_spline_report export paths."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from certus.utils.certus_spline_report import SplineReportBuilder, SplineReportContext
from certus.spline.certus_index_spline_core import DataType, SplineOptConfig


class _DummyWriter:
    def __init__(self, path: str, *args, **kwargs) -> None:
        self.path = path
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class _DummyLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, tuple, dict]] = []

    def info(self, *args, **kwargs):
        self.records.append(("info", args, kwargs))

    def warning(self, *args, **kwargs):
        self.records.append(("warning", args, kwargs))

    def error(self, *args, **kwargs):
        self.records.append(("error", args, kwargs))

    def exception(self, *args, **kwargs):
        self.records.append(("exception", args, kwargs))


@pytest.fixture
def minimal_ctx() -> SplineReportContext:
    result = {
        "rmse": 0.0021,
        "d_nm": 1715.95,
        "lam_nm": np.array([400.0, 500.0, 600.0]),
        "n_lam": np.array([1.5, 1.6, 1.7]),
        "k_lam": np.array([0.01, 0.02, 0.03]),
        "t_theo": np.array([0.2, 0.3, 0.4]),
        "x": np.array([1715.95] + [0.1] * 18),
        "spectral_rmse_segments": 0.0022,
        "spectral_rmse_best_label": "Spline_cubique_sigma",
        "spectral_rmse_best_value": 0.0020,
        "n_lam_seg_spline_sigma": np.array([1.5, 1.6, 1.7]),
        "k_lam_seg_spline_sigma": np.array([0.01, 0.02, 0.03]),
        "d_nm_seg_spline_sigma": 1715.95,
        "sigma_knots": np.array([1e-4, 2e-4]),
        "run_manifest": {"ok": True},
    }
    df = pd.DataFrame({"lambda": [400.0, 500.0, 600.0], "T": [20.0, 30.0, 40.0]})
    cfg = SplineOptConfig(
        substrate_name="SiO2",
        weight_r=0.0,
        weight_t=1.0,
        d_hi=1800.0,
        d_lo=1600.0,
        n_seg=2,
        data_type=DataType.TRANSMISSION,
        n_sub=np.array([1.45, 1.45, 1.45]),
        r_exp=None,
        t_exp=np.array([0.2, 0.3, 0.4]),
        lam_nm=np.array([400.0, 500.0, 600.0]),
        rmse_fit_lambda_nm=(400.0, 600.0),
    )
    return SplineReportContext(
        result=result,
        df=df,
        spectrum_path=str(Path("sample.xlsx")),
        t_is_ratio=False,
        sub_name="SiO2",
        rmse_fit_lambda_tuple=(400.0, 600.0, 0.0),
        lam_mask_callable=lambda lam: np.ones_like(lam, dtype=float),
        opt_config=cfg,
    )


def test_build_report_auto_with_minimal_context(monkeypatch, tmp_path, minimal_ctx):
    writer_paths: list[str] = []
    monkeypatch.setattr(pd, "ExcelWriter", lambda path, *args, **kwargs: _DummyWriter(str(path), *args, **kwargs))
    monkeypatch.setattr(pd.DataFrame, "to_excel", lambda self, writer, *args, **kwargs: writer_paths.append(getattr(writer, "path", "")))
    monkeypatch.setattr("certus_spline_report._get_script_dir", lambda: tmp_path)
    monkeypatch.setattr("certus_spline_report._get_substrate_n_array_spline", lambda substrate_id, wavelengths_nm: np.ones_like(wavelengths_nm) * 1.45)
    monkeypatch.setattr("certus_spline_report.calculate_bare_substrate_RT", lambda lam, n: np.ones_like(lam) * 0.95)

    builder = SplineReportBuilder(minimal_ctx, logger=_DummyLogger())
    builder.build_report(auto_export=True)
    assert writer_paths


def test_build_report_auto_without_result_noop(monkeypatch, tmp_path, minimal_ctx):
    ctx = replace(minimal_ctx, result=None)
    monkeypatch.setattr(pd, "ExcelWriter", lambda path, *args, **kwargs: _DummyWriter(str(path), *args, **kwargs))
    monkeypatch.setattr(pd.DataFrame, "to_excel", lambda self, writer, *args, **kwargs: None)
    monkeypatch.setattr("certus_spline_report._get_script_dir", lambda: tmp_path)
    builder = SplineReportBuilder(ctx, logger=_DummyLogger())
    builder.build_report(auto_export=True)


def test_build_report_falls_back_to_df_lambda(monkeypatch, tmp_path, minimal_ctx):
    ctx = replace(minimal_ctx, result={k: v for k, v in minimal_ctx.result.items() if k != "lam_nm"})
    captured: list[str] = []

    class CaptureWriter(_DummyWriter):
        pass

    def fake_to_excel(self, writer, *args, **kwargs):
        captured.append(kwargs.get("sheet_name", ""))

    monkeypatch.setattr(pd, "ExcelWriter", lambda path, *args, **kwargs: CaptureWriter(str(path), *args, **kwargs))
    monkeypatch.setattr(pd.DataFrame, "to_excel", fake_to_excel)
    monkeypatch.setattr("certus_spline_report._get_script_dir", lambda: tmp_path)
    monkeypatch.setattr("certus_spline_report._get_substrate_n_array_spline", lambda substrate_id, wavelengths_nm: np.ones_like(wavelengths_nm) * 1.45)
    monkeypatch.setattr("certus_spline_report.calculate_bare_substrate_RT", lambda lam, n: np.ones_like(lam) * 0.95)

    builder = SplineReportBuilder(ctx, logger=_DummyLogger())
    builder.build_report(auto_export=True)
    assert "Spectrum" in captured
