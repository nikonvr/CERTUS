"""A3: the 99-layer assembly scores the realisation its slices grew with (C2).

The assembly of 2026-10-21 was refused (reports/STRAT_A3_C2_assemblage_2026-10-21/bilan.md): the slices' thicknesses came from the
2x noise level while the assembler read the index stream of level 1, and each slice normalised the index error over the envelope
of the spectral grid and ITS monitoring wavelengths while the assembler took the spectral band alone. Both are pinned here.
"""

import importlib.util
from pathlib import Path

import numpy as np

from certus.core.certus_strat_robustness_noise import corridor_monitor_span
from certus.physics.certus_strat_batch import corridor_wl_range

ROOT = Path(__file__).resolve().parents[2]


def _campaign():
    spec = importlib.util.spec_from_file_location("campagne_intervalles_a3", ROOT / "scripts" / "campagne_intervalles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cached_thicknesses_are_those_of_the_nominal_level():
    strat = {"results_per_noise": [{"noise_level": lv, "thicknesses_all": [[th]]} for lv, th in ((0.1, 3.0), (0.025, 1.0), (0.05, 2.0))]}
    assert _campaign()._epaisseurs(strat)[0, 0] == 2.0  # 0.05 is 1x of trigger_tolerance 0.05; "nearest 1.0" took 0.1


def test_by_default_the_domain_follows_the_plan():
    plan = np.array([480.0, 620.0])
    assert corridor_monitor_span({}, plan) is plan


def test_with_the_fixed_domain_two_plans_and_the_assembler_share_one_domain():
    params = {"index_corridor_fixed_domain": True, "scan_wl_min": 450.0, "scan_wl_max": 750.0}
    band = np.arange(610.0, 655.5, 0.5)
    slice_a = corridor_wl_range(band, corridor_monitor_span(params, np.array([598.0, 640.0])))
    slice_b = corridor_wl_range(band, corridor_monitor_span(params, np.array([700.0, 712.0])))
    assembler = corridor_wl_range(band, corridor_monitor_span(params, np.empty(0)))
    assert slice_a == slice_b == assembler == (450.0, 750.0)
