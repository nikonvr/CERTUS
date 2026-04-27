"""Sélection automatique du meilleur preset matériau (Smart Init)."""
from __future__ import annotations

import numpy as np

from certus_index_spline_core import DataType, SplineOptConfig
from certus_physics import calculate_transmission_array
from spline_smart_init import MANUAL_MATERIAL_PRESET_IDS, pick_best_manual_material_preset


def _cfg_and_sk_for_pick() -> tuple[SplineOptConfig, np.ndarray]:
    lam = np.linspace(400.0, 2000.0, 48, dtype=np.float64)
    n_sub = np.full_like(lam, 1.52)
    n_film = 2.0
    k_film = 1e-6
    d_nm = 800.0
    n_l = np.full_like(lam, n_film)
    k_l = np.full_like(lam, k_film)
    t_exp = calculate_transmission_array(lam, n_l, k_l, d_nm, n_sub)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=7,
        d_lo=100.0,
        d_hi=3500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
    )
    sig = 1.0 / np.maximum(lam, 1e-9)
    sk = np.linspace(float(np.min(sig)), float(np.max(sig)), 8, dtype=np.float64)
    return cfg, sk


def test_pick_best_manual_material_preset_returns_a_known_id() -> None:
    cfg, sk = _cfg_and_sk_for_pick()
    out = pick_best_manual_material_preset(
        cfg, sk, d_nm_hint=900.0, relax_n_mono=False
    )
    assert out is not None
    best_id, rm, d_o, n_p, L_p, rows = out
    assert best_id in MANUAL_MATERIAL_PRESET_IDS
    assert np.isfinite(rm)
    assert n_p.size == sk.size == L_p.size
    assert len(rows) >= 1
    assert all(pid in MANUAL_MATERIAL_PRESET_IDS for pid, _ in rows)
