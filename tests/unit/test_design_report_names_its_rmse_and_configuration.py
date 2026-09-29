"""The DESIGN reports are named after the best RMSE of the workflow and the loaded configuration.

`ExportManager._prepare_export_paths` read `_workflow_best_rmse` and `_last_config_file` on the
manager (`getattr(self, "_workflow_best_rmse", None)`, `hasattr(self, "_last_config_file")`),
which holds neither: a report was labelled with the RMSE of the last evaluation instead of the
best one the workflow had reached, and its name never carried the configuration it came from.
Found on 2026-09-29 by listing every guard a class puts on a name it never holds.

The output folder is redirected: the test writes nothing under `reports/`.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace


def _paths(tmp_path, monkeypatch, **window):
    import certus.ui.certus_design_ui_export as export

    monkeypatch.setattr(export, "get_resource_path", lambda name: str(tmp_path / name))
    return export.ExportManager(SimpleNamespace(**window))._prepare_export_paths()


def test_the_report_carries_the_best_rmse_of_the_workflow_and_its_configuration(tmp_path, monkeypatch) -> None:
    rmse, base_name, excel_path, html_path = _paths(
        tmp_path,
        monkeypatch,
        _workflow_best_rmse=0.00123,
        last_result={"rmse": 0.5},
        _last_config_file=str(tmp_path / "my_design.json"),
    )

    assert rmse == 0.00123
    assert base_name.startswith("Report_DESIGN_my_design_")
    assert base_name.endswith("_RMSE_0.00123")
    assert Path(excel_path) == tmp_path / "reports" / f"{base_name}.xlsx"
    assert Path(html_path) == tmp_path / "reports" / f"{base_name}.html"


def test_without_a_workflow_the_report_falls_back_on_the_last_result(tmp_path, monkeypatch) -> None:
    rmse, base_name, _excel, _html = _paths(
        tmp_path, monkeypatch, last_result={"rmse": 0.5}, _last_config_file=None
    )

    assert rmse == 0.5
    assert re.fullmatch(r"Report_DESIGN_\d{8}_\d{6}_RMSE_0\.50000", base_name), base_name
