"""DESIGN's report exports build their run manifest.

ExportManager (the full-results export that ends every DESIGN run, and the Excel export) and
PlotManager (the Pareto summary) pass `app_version=__version__` to the manifest request, and the
Pareto summary checks the manifest with get_missing_manifest_fields. Neither module imported
either name: `import *` never carries a name that starts with an underscore, and
certus_design_common (removed since) had no get_missing_manifest_fields. From the split of the monolith (June
2026) to 2026-09-28, each of these exports stopped on a NameError before writing anything.
"""

from __future__ import annotations

from types import SimpleNamespace

from certus.core.certus_core import __version__
from certus.utils.certus_data import get_missing_manifest_fields


def _fake_ui(**extra):
    logs = []
    ui = SimpleNamespace(
        last_result={"vis": {}},
        l0_spin=SimpleNamespace(value=lambda: 550.0),
        front_table=SimpleNamespace(rowCount=lambda: 3),
        log=lambda message, level="INFO": logs.append((level, message)),
        **extra,
    )
    return ui, logs


def test_the_full_results_export_builds_a_complete_manifest() -> None:
    from certus.ui.certus_design_ui_export import ExportManager

    ui, _logs = _fake_ui()
    manager = ExportManager(ui)
    manifest = manager._build_export_manifest()

    assert manifest["app_version"] == __version__
    assert get_missing_manifest_fields(manifest) == []
    assert manager._is_export_manifest_complete(manifest)


def test_the_pareto_summary_is_written(tmp_path, monkeypatch) -> None:
    import certus.core.certus_core as core
    from certus.ui.certus_design_ui_plot import PlotManager

    # The report goes to get_resource_path("reports"): here, a temporary folder.
    monkeypatch.setattr(core, "get_resource_path", lambda name: str(tmp_path / name))
    record = {"best_rmse": 0.01, "dmin_rmse": 12.0, "best_mc": 0.02, "dmin_mc": 11.0, "best_fab": 0.015, "dmin_fab": 6.0}
    ui, logs = _fake_ui(pareto_history={4: record}, _workflow_best_rmse=0.01)

    PlotManager(ui)._export_pareto_report()

    assert len(list((tmp_path / "reports").glob("Pareto_Summary_*.html"))) == 1, logs
    assert not [message for level, message in logs if level in ("WARNING", "ERROR")]
