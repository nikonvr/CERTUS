"""Only finite, physically admissible retained states may enter the A2 comparison."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SOURCE = (Path(__file__).resolve().parents[2] / "reports" / "A2_preparation_calculs_2026-11-05"
          / "pilote_threeline.py")


def _select(rows, cap):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"state", "admissible_rounds"}]
    context = {"np": np, "tr": SimpleNamespace(gs=SimpleNamespace(
        FLOOR=0.1, s=SimpleNamespace(total_ot=lambda _seq, d: float(1.5 * d.sum()))))}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), context)
    return context["admissible_rounds"](rows, cap)


def test_an_over_budget_round_cannot_replace_an_admissible_initial_state():
    before = {"seq": "LL", "d_nm": "1.0 1.0", "mf_tracked": 1.0}
    outside = {"seq": "LL", "d_nm": "1.0 1.000000001", "mf_tracked": 0.01}
    rows = _select([before, outside], 3.0)
    assert min(rows, key=lambda row: row["mf_tracked"]) is before


@pytest.mark.parametrize(("seq", "thickness"), [("L", "nan"), ("L", "inf"), ("L", "-1"),
                                             ("L", "0.099"), ("LL", "1.0")])
def test_invalid_states_leave_no_admissible_result(seq, thickness):
    with pytest.raises(RuntimeError, match="no retained round"):
        _select([{"seq": seq, "d_nm": thickness}], 15000.0)
