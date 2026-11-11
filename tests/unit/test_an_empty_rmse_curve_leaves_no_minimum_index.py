"""An RMSE(d) curve with no point left says `no minimum` the way everything else does: -1, not None.

`_corridor_rmse_best_idx` is the index of the minimum of the plotted RMSE(d) curve. Everywhere, `no minimum` is -1: the
table of the corridor state, the tab when it is built, `_load_defaults`, the worker when it starts a grid, and the
fallback of every reader, which all do `int(getattr(self, "_corridor_rmse_best_idx", -1))`. One place wrote None:
`_plot_rmse_data_scatter`, when the curve it was given has no finite point. The next reader then raised
`TypeError: int() argument must be ... not 'NoneType'`, in a slot of the window (audit of the corridors, Q17).

Without Qt: the plot is a recorder, and the readers run on a namespace that holds what they read.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui import certus_index_spline_corridor_rmse_plot as module
from certus.ui.certus_index_spline_corridor_interval import _CorridorIntervalMixin
from certus.ui.certus_index_spline_corridor_rmse_plot import _CorridorRmsePlotMixin
from certus.ui.certus_index_spline_corridor_state import CORRIDOR_STATE

GROUP = sorted((Path(__file__).resolve().parents[2] / "certus" / "ui").glob("certus_index_spline*.py"))


class Plot:
    def __init__(self) -> None:
        self.cleared = 0
        self.series: list[str] = []

    def clear(self) -> None:
        self.cleared += 1

    def plot(self, _x, _y, **kwargs) -> None:
        self.series.append(kwargs.get("name", "?"))


@pytest.fixture(autouse=True)
def fake_pyqtgraph(monkeypatch):
    monkeypatch.setattr(module, "pg", SimpleNamespace(mkBrush=lambda *a, **k: ("brush", a, k), mkPen=lambda *a, **k: ("pen", a, k)))


def host_after_the_scatter_of(d, r) -> SimpleNamespace:
    """A window that held a minimum at index 3, after `_plot_rmse_data_scatter` drew the curve (d, r)."""
    host = SimpleNamespace(
        plot_corridor_rmse_d=Plot(),
        _plot_the_reversal_and_fallback_points=lambda *args: None,
        _plot_the_breakpoint_events=lambda *args: (0, 0, []),
        _corridor_rmse_best_idx=3,
        _corridor_rmse_d_vals=np.array([100.0, 110.0, 120.0, 130.0]),
        _corridor_rmse_robust_ok=True,
    )
    ctx = SimpleNamespace(d_plot=d, r_plot=r, d_vis=d, r_vis=r, i_best=-1)
    _CorridorRmsePlotMixin._plot_rmse_data_scatter(host, {}, ctx)
    return host


EMPTY = {"no point": ([], []), "no finite point": ([100.0, 110.0], [float("nan"), float("inf")])}


@pytest.mark.parametrize("curve", EMPTY.values(), ids=list(EMPTY))
def test_an_empty_curve_leaves_minus_one(curve):
    host = host_after_the_scatter_of(*curve)
    assert host._corridor_rmse_best_idx == -1
    assert type(host._corridor_rmse_best_idx) is int
    assert host.plot_corridor_rmse_d.cleared == 1


@pytest.mark.parametrize("reader", ["_on_corridor_manual_slider_changed", "_use_robust_corridor_interval"])
@pytest.mark.parametrize("curve", EMPTY.values(), ids=list(EMPTY))
def test_a_reader_that_runs_after_an_empty_curve_finds_no_minimum_and_returns(curve, reader):
    host = host_after_the_scatter_of(*curve)
    arguments = (0,) if reader == "_on_corridor_manual_slider_changed" else ()
    assert getattr(_CorridorIntervalMixin, reader)(host, *arguments) is None


def test_no_module_of_the_group_writes_none_in_the_minimum_index():
    offenders = []
    for path in GROUP:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value is None):
                continue
            offenders += [f"{path.name}:{node.lineno}" for t in node.targets if isinstance(t, ast.Attribute) and t.attr == "_corridor_rmse_best_idx"]
    assert offenders == []


def test_the_table_declares_an_integer():
    assert CORRIDOR_STATE["_corridor_rmse_best_idx"].annotation == "int"
