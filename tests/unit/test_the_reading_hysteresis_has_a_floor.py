"""The turning-point hysteresis can be kept from vanishing with the noise (`tp_hysteresis_floor`, 0 = inactive).

📏 2026-10-20: with the optical noise divided by 100, every deposition of the STRAT winners of r75 and r75x2 stopped
(TP_MISCOUNT on one layer, only with the slit bias): the hysteresis `factor x noise` went to zero and the slit-bias ripple
was counted as turning points (`reports/STRAT_r75_budget_et_affinage_2026-10-20/bilan.md`).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from certus.core.certus_strat_robustness_task import reading_hysteresis

ROOT = Path(__file__).resolve().parents[2]


def test_without_a_floor_the_rule_is_the_historical_one_to_the_bit():
    for noise in (0.0005, 0.025, 0.05, 0.1):
        assert reading_hysteresis(1.66, 0.0, noise, False) == 1.66 * noise / 100.0
    dT_dd = np.array([0.003, -0.01, 0.02])
    assert reading_hysteresis(1.66, 0.0, 0.05, True, dT_dd) == 1.66 * float(np.median(np.abs(dT_dd))) * 0.05
    assert reading_hysteresis(0.0, 0.0, 0.05, False) == 0.0


def test_the_floor_holds_at_low_noise_and_leaves_the_usual_levels_alone():
    floor = 1.66 * 0.025 / 100.0
    assert reading_hysteresis(1.66, floor, 0.0005, False) == floor
    for noise in (0.025, 0.05, 0.1):
        assert reading_hysteresis(1.66, floor, noise, False) == 1.66 * noise / 100.0


def test_the_floor_reaches_the_task_and_is_loaded_from_the_configuration():
    task = (ROOT / "certus/core/certus_strat_robustness_task.py").read_text(encoding="utf-8")
    service = (ROOT / "certus/utils/certus_strat_service.py").read_text(encoding="utf-8")
    ui = (ROOT / "certus/ui/certus_strat_ui_state.py").read_text(encoding="utf-8")
    assert 'params.get("tp_hysteresis_floor"' in task
    assert "reading_hysteresis(tp_hysteresis_factor, tp_hysteresis_floor," in task
    assert 'params.get("tp_hysteresis_floor"' in service
    assert '"tp_hysteresis_floor": _config_float(' in ui
