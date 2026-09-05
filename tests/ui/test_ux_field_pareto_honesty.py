"""FIELD must not record a Pareto point built on an invented stack (step 2.22).

certus/ui/certus_field_state_mixin.py used to answer a failure by fabricating
the physics:

    except Exception:
        layer_types = [i % 2 for i in range(len(emp_factors))]

layer_types says which layer is high-index and which is low. Inventing a
perfectly alternating H/L sequence produces a cost from a stack that does not
exist, stores it in pareto_history, and displays it next to real points with
nothing marking it apart. That is interdiction 9 of CLAUDE.md realised inside
the interface: not an error, a plausible wrong answer.

The same block also fabricated on a SILENT length mismatch - no exception
needed - which is the harder half to notice.

Not recording the point is an outcome the function already has: it returns early
three times before this (no factors, non-finite cost, cost out of range).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def field_window(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    yield win
    win.close()


def test_no_pareto_point_when_the_layer_types_are_unknown(field_window, monkeypatch, caplog) -> None:
    """A stack whose materials cannot be read must produce no point at all."""

    def _boom():
        raise RuntimeError("parameters unavailable")

    monkeypatch.setattr(field_window, "_get_params", _boom)
    field_window.pareto_history.clear()

    with caplog.at_level("WARNING"):
        field_window._update_pareto_record(emp_factors=[1.0, 1.0, 1.0, 1.0], cost_val=0.01)

    assert not field_window.pareto_history, (
        "a Pareto point was recorded from an invented H/L sequence: "
        f"{field_window.pareto_history}"
    )


def test_no_pareto_point_when_the_layer_count_disagrees(field_window, monkeypatch) -> None:
    """A silent length mismatch must not be padded with a made-up sequence."""

    class _Params:
        layer_types = [0, 1]  # two materials for four thicknesses
        n1_rs = [1.46]
        n2_rs = [2.35]
        l0 = 500.0

    monkeypatch.setattr(field_window, "_get_params", lambda: _Params())
    field_window.pareto_history.clear()

    field_window._update_pareto_record(emp_factors=[1.0, 1.0, 1.0, 1.0], cost_val=0.01)

    assert not field_window.pareto_history, (
        "a Pareto point was recorded although the stack had 4 thicknesses for 2 materials: "
        f"{field_window.pareto_history}"
    )
