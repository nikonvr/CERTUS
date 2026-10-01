"""`_CorridorWorkerMixin._log_regular_grid_result` says what the regular d grid brought back (audit v2, plan S5.2).

It was the first block of `_finish_corridor_rmse_d_grid_worker_done`, a 330-line handler no unit test reaches. Two lines come out of it, both only when the window has a logger: the size of the grid,
its NaNs and its coverage, then - when there is at least one finite point - the extremes of the RMSE curve and where the visit started.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from certus.spline.certus_index_spline_corridor_worker import _CorridorWorkerMixin


class Recorder:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, fmt: str, *args) -> None:
        self.lines.append(fmt % args if args else fmt)


def result(**changes) -> dict:
    base = {
        "profile_d_values_nm": [90.0, 95.0, 100.0, 105.0, float("nan")],
        "profile_d_rmse_values": [0.5, 0.2, 0.1, 0.3, 0.4],
        "profile_d_manual_grid_requested_base_points": 5,
        "profile_d_manual_grid_returned_base_points": 4,
        "profile_d_manual_grid_missing_after_emergency": 1,
        "profile_d_manual_grid_coverage_complete": False,
        "profile_d_manual_grid_d0_seed_nm": 100.0,
        "profile_d_manual_grid_nominal_pack_d_nm": 98.5,
    }
    base.update(changes)
    return base


def log(res: dict) -> list[str]:
    recorder = Recorder()
    _CorridorWorkerMixin._log_regular_grid_result(SimpleNamespace(logger=recorder), res)
    return recorder.lines


def test_without_a_logger_nothing_is_read_and_nothing_fails():
    _CorridorWorkerMixin._log_regular_grid_result(SimpleNamespace(logger=None), {"profile_d_values_nm": "not an array"})


def test_the_first_line_counts_the_points_the_nans_and_the_coverage():
    first = log(result())[0]
    assert "[order A:result-received]" in first
    assert "points=5" in first
    assert "nan(d)=1" in first
    assert "nan(rmse)=0" in first
    assert "coverage requested/returned/missing=5/4/1" in first
    assert "complete=no" in first


def test_a_complete_grid_says_so():
    assert "complete=yes" in log(result(profile_d_manual_grid_coverage_complete=True))[0]


def test_a_result_without_coverage_figures_reports_minus_one():
    res = result()
    for key in ("requested_base_points", "returned_base_points", "missing_after_emergency"):
        res.pop(f"profile_d_manual_grid_{key}")
    assert "coverage requested/returned/missing=-1/-1/-1" in log(res)[0]


def test_the_second_line_gives_the_extremes_of_the_finite_curve_and_where_the_visit_began():
    lines = log(result())
    assert len(lines) == 2
    second = lines[1]
    assert "[order A-ext:curve-on-receive]" in second
    assert "d_nm[min,max]=[90.000000,105.000000]" in second
    assert "rmse[min,max]=[0.10000000,0.50000000]" in second
    assert "curve_min(d,rmse)=(100.000000,0.10000000)" in second
    assert "curve_max(d,rmse)=(90.000000,0.50000000)" in second
    assert "visit_first_d_nm=100.000000" in second
    assert "nominal_pack_d_nm=98.500000" in second


def test_the_nan_point_is_left_out_of_the_extremes():
    second = log(result(profile_d_rmse_values=[0.5, 0.2, 0.1, 0.3, 0.0]))[1]
    assert "rmse[min,max]=[0.10000000,0.50000000]" in second


@pytest.mark.parametrize("missing", [None, float("nan")], ids=["absent", "NaN"])
def test_missing_seeds_are_written_n_a(missing):
    second = log(result(profile_d_manual_grid_d0_seed_nm=missing, profile_d_manual_grid_nominal_pack_d_nm=missing))[1]
    assert "visit_first_d_nm=n/a" in second
    assert "nominal_pack_d_nm=n/a" in second


@pytest.mark.parametrize(
    "changes",
    [
        {"profile_d_values_nm": [], "profile_d_rmse_values": []},
        {"profile_d_rmse_values": [0.1, 0.2]},
        {"profile_d_values_nm": [float("nan")] * 2, "profile_d_rmse_values": [0.1, 0.2]},
    ],
    ids=["empty grid", "sizes differ", "no finite point"],
)
def test_without_a_finite_curve_only_the_first_line_comes_out(changes):
    assert len(log(result(**changes))) == 1


def test_the_handler_calls_the_helper():
    import inspect

    assert "self._log_regular_grid_result(result)" in inspect.getsource(_CorridorWorkerMixin._finish_corridor_rmse_d_grid_worker_done)
