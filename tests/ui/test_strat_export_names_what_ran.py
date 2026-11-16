"""The STRAT export names what ran (audit 2026-11-15, M-L6f).

The export read ``nH``, ``nL``, ``substrate`` and ``n_target_layers``, keys the parameters never had: the summary said
"N/A" four times. The run was declared unseeded although ``robustness_seed`` seeds it, the score of robustness was
labelled "Best RMSE", and the SEEL, the figure CERTUS reports, was absent.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import openpyxl
import pytest


@pytest.fixture
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        yield win
    finally:
        win.close()


@pytest.fixture
def seel_calibration():
    """APP_CONTEXT is a process-wide dict: the calibration set here must not leak."""
    from certus.utils.certus_strat_service import APP_CONTEXT

    saved = APP_CONTEXT.get("seel_data", "__absent__")
    APP_CONTEXT["seel_data"] = {"fit_k": 2.0, "fit_alpha": 0.5}
    try:
        yield
    finally:
        if saved == "__absent__":
            APP_CONTEXT.pop("seel_data", None)
        else:
            APP_CONTEXT["seel_data"] = saved


def _best_strategy() -> dict:
    return {
        "strategy_id": 7,
        "strategy": {"strategy_id": 7, "n_blocks": 1, "origin": "TEST", "blocks": [{"start": 0, "end": 3, "wavelength": 550.0}]},
        "rmse": 0.004,
        "robustness_score": 0.0064,
        "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.0064, "rmse_mean": 0.005}],
    }


def _summary(strat, tmp_path) -> dict[str, str]:
    strat.opti_results = {}
    path = tmp_path / "report.xlsx"
    strat._write_export_excel([_best_strategy()], 0.0064, str(path), str(tmp_path), None, "report")
    rows = list(openpyxl.load_workbook(path)["Summary"].iter_rows(values_only=True))
    return {str(k): str(v) for k, v in rows[1:]}


def test_the_excel_summary_names_the_materials_the_substrate_and_the_layer_count(strat, tmp_path) -> None:
    params = strat.collect_params()
    summary = _summary(strat, tmp_path)
    assert "N/A" not in (summary["High Index (H)"], summary["Low Index (L)"], summary["substrate"], summary["Target Layers"])
    assert summary["High Index (H)"] == str(params["nH_id"])
    assert summary["Low Index (L)"] == str(params["nL_id"])
    assert summary["substrate"] == str(params["nSub_id"])
    assert summary["Target Layers"] == str(len(params["stack_string"].split(",")))


def test_the_excel_summary_reports_the_seel_and_calls_the_score_a_score(strat, tmp_path, seel_calibration) -> None:
    summary = _summary(strat, tmp_path)
    assert "Best RMSE" not in summary
    assert summary["Best robustness score"] == "0.006400"
    assert summary["Best SEEL (nm)"] == "0.160"  # 2.0 x 0.0064 ** 0.5, the calibration of the fixture


def test_a_run_seeded_by_the_robustness_seed_is_not_declared_unseeded(strat) -> None:
    assert strat._export_params_are_unseeded({"robustness_seed": 42}) is False
    assert strat._export_params_are_unseeded({"seed": 3}) is False
    assert strat._export_params_are_unseeded({}) is True
