"""`REPhase4Strategy._close_phase4_profile` switches the phase 4 profiling off and logs what it measured (audit v2, plan S5.2).

The block was the tail of `_execute_phase4_beam`, a 302-line method; the unit tests of the phase never reach it (they stop before the high-angle branch), so the helper it became is
pinned here on its own: the profiling flag goes down, the accumulated profile is dropped, and the two log lines say the same things as before (the P4 profile of the last scan,
then the wall-clock split between the scan and the TRF stage).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from certus.workers import certus_re_workers_phase4
from certus.workers.certus_re_workers_phase4 import REPhase4Strategy


@pytest.fixture
def clock(monkeypatch):
    """`time.perf_counter` of the module reads 12.0: a phase that started at 10.0 took 2.0 s."""
    monkeypatch.setattr(certus_re_workers_phase4, "time", SimpleNamespace(perf_counter=lambda: 12.0))


def profile() -> dict:
    return {"phy_wall_s": 1.5, "phi_calls": 7, "meta_p4_count": 3, "n_wls_union_max": 40, "band_groups": 5, "band_mask_steps": 11}


def close(state: dict, scan_s: float = 0.8, trf_s: float = 1.1) -> None:
    REPhase4Strategy._close_phase4_profile(None, state, 10.0, scan_s, trf_s)


def messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_the_profiling_flag_goes_down_and_the_profile_is_dropped(clock):
    state = {"is_phase4": True, "p4_prof": profile()}
    close(state)
    assert state["is_phase4"] is False
    assert state["p4_prof"] is None


def test_the_profile_of_the_last_scan_is_logged_with_its_counters(clock, caplog):
    state = {"is_phase4": True, "p4_prof": profile()}
    with caplog.at_level(logging.INFO):
        close(state)
    line = next(m for m in messages(caplog) if "P4 profile" in m and "inner_physics_wall_s" in m)
    assert "inner_physics_wall_s=1.5000" in line
    assert "oblique_phi_calls=7" in line
    assert "meta_passes=3" in line
    assert "n_wls_union_max=40" in line
    assert "band_groups=5" in line
    assert "band_mask_steps=11" in line


def test_the_wall_clock_split_is_logged_in_seconds(clock, caplog):
    state = {"is_phase4": True, "p4_prof": profile()}
    with caplog.at_level(logging.INFO):
        close(state, scan_s=0.8, trf_s=1.1)
    line = next(m for m in messages(caplog) if m.startswith("RE phase 4 wall"))
    assert "total=2.000s" in line
    assert "scan=0.800s" in line
    assert "TRF=1.100s" in line


def test_without_a_profile_only_the_wall_clock_line_is_logged(clock, caplog):
    state = {"is_phase4": True, "p4_prof": None}
    with caplog.at_level(logging.INFO):
        close(state)
    assert not any("inner_physics_wall_s" in m for m in messages(caplog))
    assert any(m.startswith("RE phase 4 wall") for m in messages(caplog))
    assert state["is_phase4"] is False
    assert state["p4_prof"] is None


def test_the_helper_is_called_by_the_beam_method():
    import inspect

    assert "REPhase4Strategy._close_phase4_profile(None," in inspect.getsource(REPhase4Strategy._execute_phase4_beam)


def test_no_method_of_the_strategy_reads_self_since_the_worker_passes_none():
    """`REWorker` calls every method as `REPhase4Strategy._x(None, worker, ...)`. Until 2026-10-04 the beam method called
    `self._close_phase4_profile(...)`, so every RE run whose phase 4 went through its high-angle branch ended on an
    AttributeError and returned no result; the test above pinned that call."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(REPhase4Strategy)))
    reads = sorted(
        {
            f"{method.name}: self.{node.attr}"
            for method in ast.walk(tree)
            if isinstance(method, ast.FunctionDef)
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"
        }
    )
    assert reads == []
