"""The artefact of `scripts/probe_blocs_vs_plantage.py` keeps, per strategy and per noise level, what `score` hides.

`score` is one number per strategy: the consensus aggregate of the largest, over the three noise levels, of the 95th
percentile of the per-draw RMSE (ETAT D7), crashed draws included. On 2026-10-12 the question was the SEEL of the plan the
software keeps when nothing is depositable (r75x0.5, seed 101: crash 1.7 / 1.7 / 8.3 %). The artefact could not answer: it
held no percentile per level and no count of crashed draws, and a replay of four hours was needed to measure them. At the
highest level 25 draws of 300 crashed, their RMSE (0.20 to 0.23) was above that of every draw that terminated (at most
0.13), so the 95th percentile of all the draws was a crashed draw's: SEEL 0.960 nm, against 0.644 nm for the draws that
terminate.

`rmse_par_bruit` keeps both percentiles and the counts, per level, for every strategy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_blocs_vs_plantage as probe  # noqa: E402

#: A crashed layer is written as its nominal thickness plus a multiple of 1e6 (`CRASH_SENTINEL_UNIT`).
CRASHED = 1_000_040.0


def _level(noise: float, rmse: np.ndarray, crashed: range) -> dict:
    thicknesses = np.full((rmse.size, 3), 100.0)
    for row in crashed:
        thicknesses[row, 1] = CRASHED
    return {
        "noise_level": noise,
        "rmse_all": rmse.tolist(),
        "thicknesses_all": thicknesses.tolist(),
        "rmse_p95": float(np.percentile(rmse, 95)),
    }


def test_the_percentile_of_all_the_draws_and_of_the_draws_that_terminate_are_kept_apart() -> None:
    rmse = np.concatenate([np.linspace(0.05, 0.12, 95), np.full(5, 0.22)])
    kept = probe._rmse_par_bruit({"results_per_noise": [_level(0.05, rmse, range(95, 100))]})["0.05"]

    assert (kept["n"], kept["plantes"]) == (100, 5)
    assert kept["rmse_p95"] == pytest.approx(np.percentile(rmse, 95))
    assert kept["rmse_p95_termines"] == pytest.approx(np.percentile(rmse[:95], 95))
    assert kept["rmse_max_termines"] == pytest.approx(0.12)
    assert kept["rmse_min_plantes"] == pytest.approx(0.22)
    assert kept["rmse_moyen_plantes"] == pytest.approx(0.22)


def test_above_five_percent_of_crashes_the_percentile_of_all_the_draws_is_a_crashed_draw() -> None:
    rmse = np.concatenate([np.linspace(0.05, 0.12, 90), np.full(10, 0.22)])
    kept = probe._rmse_par_bruit({"results_per_noise": [_level(0.1, rmse, range(90, 100))]})["0.1"]

    assert kept["plantes"] == 10
    assert kept["rmse_p95"] == pytest.approx(0.22)
    assert kept["rmse_p95_termines"] < 0.12 + 1e-12


def test_every_noise_level_has_its_own_entry_keyed_by_the_level() -> None:
    rmse = np.linspace(0.05, 0.12, 50)
    result = {"results_per_noise": [_level(0.025, rmse, range(0)), _level(0.05, rmse, range(0)), _level(0.1, rmse, range(0))]}

    kept = probe._rmse_par_bruit(result)

    assert list(kept) == ["0.025", "0.05", "0.1"]
    assert all(entry["plantes"] == 0 and entry["rmse_moyen_plantes"] is None and entry["rmse_min_plantes"] is None for entry in kept.values())
    assert all(entry["rmse_p95_termines"] == pytest.approx(entry["rmse_p95"]) for entry in kept.values())


def test_a_level_without_per_draw_values_keeps_its_percentile_only() -> None:
    assert probe._rmse_par_bruit({"results_per_noise": [{"noise_level": 0.1, "rmse_p95": 0.3}]}) == {"0.1": {"rmse_p95": 0.3}}


def test_a_result_without_levels_keeps_nothing() -> None:
    assert probe._rmse_par_bruit({}) == {}


def test_a_level_whose_draws_all_crashed_has_no_percentile_of_the_ones_that_terminate() -> None:
    rmse = np.full(20, 0.22)
    kept = probe._rmse_par_bruit({"results_per_noise": [_level(0.1, rmse, range(20))]})["0.1"]

    assert kept["plantes"] == 20
    assert kept["rmse_p95_termines"] is None
    assert kept["rmse_max_termines"] is None


def test_the_artefact_lines_carry_the_field() -> None:
    source = (ROOT / "scripts" / "probe_blocs_vs_plantage.py").read_text(encoding="utf-8")

    assert '"rmse_par_bruit": _rmse_par_bruit(s),' in source
