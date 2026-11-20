"""A Rate layer, not monitored, is not a flat layer: its swing sentinel (dyn = -1) stays out of the dynamics (chantier 5).

Measured on 2026-11-20 (reports/nuit_2026-11-19/lot3/bilan.md): `simulate_stack_robustness_batch` averaged the per-run
swing of each layer with the sentinel -1.0 of `certus_strat_growth` ("NOT MONITORED", a Rate layer) included; the
`[DYN-ALERT]` check then compared the grid swing with -100 % (90 % of 231 459 alerts on the 99-layer bench, 425 MB of logs
over the official benches), and `_worst_layer_swing` named a Rate layer as the poorest swing. Diagnostics only: the
score of a strategy never reads these numbers.
"""

from __future__ import annotations

import numpy as np

from certus.core.certus_strat_robustness_diagnostics import _worst_layer_swing, dynamics_alerts
from certus.physics.certus_strat_batch import average_monitored_dynamics


def test_a_layer_monitored_in_every_run_keeps_its_plain_mean() -> None:
    dyns = np.array([[0.20, 0.10], [0.40, 0.30], [0.30, 0.20]])
    out = average_monitored_dynamics(dyns)
    expected = np.array([(0.20 + 0.40 + 0.30) / 3, (0.10 + 0.30 + 0.20) / 3])
    # fastmath may reassociate the sum: the bit identity with the code of before is c1_diff's (9172 arrays).
    np.testing.assert_allclose(out, expected, rtol=1e-15, atol=0.0)


def test_the_sentinel_runs_of_a_layer_are_left_out_of_its_mean() -> None:
    dyns = np.array([[0.20, -1.0], [-1.0, -1.0], [0.40, -1.0]])
    out = average_monitored_dynamics(dyns)
    assert out[0] == (0.20 + 0.40) / 2
    assert out[1] == -1.0


def test_no_alert_compares_the_grid_with_the_sentinel() -> None:
    grid = {0: {550.0: 0.30}, 1: {600.0: 0.25}, 2: {650.0: 0.10}}
    lines = dynamics_alerts([550.0, 600.0, 650.0], grid, np.array([-1.0, 0.24, 0.40]), 3)

    assert [level for level, _ in lines] == ["info", "warning"]
    assert "L2" in lines[0][1]
    assert "L3" in lines[1][1]
    assert all("-100.00%" not in message for _, message in lines)


def test_a_layer_without_a_grid_swing_or_without_a_wavelength_gets_no_line() -> None:
    lines = dynamics_alerts([0.0, 600.0], {1: {}}, np.array([0.3, 0.3]), 2)
    assert lines == []


def test_the_worst_swing_is_taken_among_monitored_layers() -> None:
    swing = _worst_layer_swing([{"avg_dynamics": [0.30, -1.0, 0.05, 0.20]}])

    assert swing["layer"] == 2
    assert swing["swing"] == 0.05
    assert swing["median_swing"] == 0.20
    assert swing["n_below_swing_min"] == 0


def test_a_strategy_whose_layers_are_all_rate_has_no_worst_swing() -> None:
    assert _worst_layer_swing([{"avg_dynamics": [-1.0, -1.0]}]) == {}
