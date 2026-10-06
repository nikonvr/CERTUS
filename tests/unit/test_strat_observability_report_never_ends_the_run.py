"""D89: the Phase A observability report is a diagnostic; a folder that cannot be written must not end the run.

It is written to the `reports/` folder next to the executable. Seen on 2026-10-06 in a simulation of the frozen
build whose folder was not writable: `PermissionError` went up through `_finalize_block_strategy_result` and ended
the STRAT workflow at the end of Phase A ("Workflow error"). An executable installed in a read-only folder would
have stopped every STRAT run there.
"""

from __future__ import annotations

import logging

import certus.core.certus_strat_solvers as solvers


def test_a_report_folder_that_cannot_be_written_only_leaves_a_warning(tmp_path, monkeypatch, caplog):
    def refused(*args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(solvers, "get_resource_path", lambda name: str(tmp_path / "reports"))
    monkeypatch.setattr(solvers.os, "makedirs", refused)

    with caplog.at_level(logging.WARNING, logger="CERTUS"):
        solvers._export_phase_a_observability_json({"export_observability_json": True}, {"n": 3})

    assert any("observability" in record.getMessage() for record in caplog.records)
    assert not list(tmp_path.rglob("STRAT_observability_*.json"))


def test_a_report_folder_that_can_be_written_still_receives_the_report(tmp_path, monkeypatch):
    monkeypatch.setattr(solvers, "get_resource_path", lambda name: str(tmp_path))

    solvers._export_phase_a_observability_json({"export_observability_json": True}, {"n": 3})

    assert len(list(tmp_path.glob("STRAT_observability_*.json"))) == 1
