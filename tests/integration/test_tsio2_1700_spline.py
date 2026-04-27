"""Intégration INDEX_SPLINE : TSIO2-1700-1.xlsx, fenêtre 250–5000 nm (masque RMSE).

Le fichier peut être fourni par ``spectro_data/TSIO2-1700-1.xlsx`` à la racine du dépôt
ou via la variable d'environnement ``CERTUS_TSIO2_XLSX``.

Référence RMSE : de l'ordre de **1,5–2e-3** sur le jeu filtré (T/T_sub, saphir),
avec x0 issu du preset matériau SiO₂ + descente locale obligatoire + polish (profil rapide).
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import pytest

pytest.importorskip("openpyxl")

from certus_data import read_data_file_robust
from certus_index_spline_core import (
    DataType,
    SplineOptConfig,
    canonical_spline_sigma_knots,
    default_n_mono_band_nm_from_spectrum,
    normalize_spectrum_dataframe,
    physical_nodes_to_x_slice_n,
    prepare_exp_TR_for_fit,
    substrate_id_from_name,
)
from certus_physics import get_n_substrate_array_by_id, warmup_physics
from spline_pipeline import worker_spline_optimization
from spline_smart_init import pick_best_manual_material_preset


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_tsio2_1700_xlsx() -> Path | None:
    env = os.environ.get("CERTUS_TSIO2_XLSX", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    root = _repo_root()
    candidates.append(root / "spectro_data" / "TSIO2-1700-1.xlsx")
    here = root.parent / "0804 - Copie" / "data spectro" / "TSIO2-1700-1.xlsx"
    candidates.append(here)
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


@pytest.fixture(scope="module")
def _warm_physics() -> None:
    warmup_physics()


@pytest.fixture
def tsio2_bundle(_warm_physics):
    path = resolve_tsio2_1700_xlsx()
    if path is None:
        pytest.skip("TSIO2-1700-1.xlsx introuvable (spectro_data/ ou CERTUS_TSIO2_XLSX).")

    df = read_data_file_robust(str(path))
    df = normalize_spectrum_dataframe(df)
    lam = df["lambda"].to_numpy(dtype=np.float64)
    if float(np.nanmax(lam)) < 100.0:
        lam = lam * 1000.0
    mask = (lam >= 250.0) & (lam <= 5000.0)
    lam = lam[mask]
    t_raw = df["T"].to_numpy(dtype=np.float64)[mask]

    sid = substrate_id_from_name("Sapphire (Al2O3)")
    n_sub = get_n_substrate_array_by_id(sid, lam)
    t_exp, _r = prepare_exp_TR_for_fit(lam, n_sub, t_raw, None, t_is_ratio=True)

    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))
    n_seg = int(sk.size) - 1
    nb = default_n_mono_band_nm_from_spectrum(lam)

    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=n_seg,
        d_lo=1600.0,
        d_hi=1800.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Sapphire (Al2O3)",
        t_is_ratio=True,
        rmse_fit_lambda_nm=(250.0, 5000.0),
        n_mono_band_nm=nb,
        nk_profile_interp="smooth",
    )
    return {"path": path, "cfg0": cfg, "sk": sk, "n_lambda": int(lam.size)}


def test_tsio2_1700_lambda_window_and_mesh(tsio2_bundle: dict) -> None:
    assert tsio2_bundle["n_lambda"] >= 400
    lam = tsio2_bundle["cfg0"].lam_nm
    assert float(np.min(lam)) >= 249.0
    assert float(np.max(lam)) <= 5010.0
    sk = tsio2_bundle["sk"]
    assert int(sk.size) == 14
    assert tsio2_bundle["cfg0"].n_seg == 13


def test_tsio2_1700_material_preset_is_sio2(tsio2_bundle: dict) -> None:
    cfg0: SplineOptConfig = tsio2_bundle["cfg0"]
    sk = tsio2_bundle["sk"]
    pk = pick_best_manual_material_preset(
        cfg0,
        sk,
        d_nm_hint=0.5 * (cfg0.d_lo + cfg0.d_hi),
        relax_n_mono=True,
    )
    assert pk is not None
    best_id, _best_rm, _d, _n, _L, rows = pk
    assert str(best_id) == "sio2"
    assert len(rows) >= 2


@pytest.mark.integration
@pytest.mark.slow
def test_tsio2_1700_headless_best_rmse_order_2e_minus_3(tsio2_bundle: dict) -> None:
    """Pipeline courte : pas de PGlobal ; le meilleur RMSE spectrale reste ~1,5–2e-3."""
    cfg0: SplineOptConfig = tsio2_bundle["cfg0"]
    sk = tsio2_bundle["sk"]
    nb = cfg0.n_mono_band_nm
    assert nb is not None

    pk = pick_best_manual_material_preset(
        cfg0,
        sk,
        d_nm_hint=0.5 * (cfg0.d_lo + cfg0.d_hi),
        relax_n_mono=True,
    )
    assert pk is not None
    _bid, _rm0, d_opt, n_p, L_p, _rows = pk
    xi = physical_nodes_to_x_slice_n(n_p, sk, nb)
    x0w = np.concatenate((np.asarray([d_opt], dtype=np.float64), xi, L_p.astype(np.float64)))

    cfg = replace(
        cfg0,
        x0_warm=x0w,
        spline_local_only=True,
        stage_mandatory_local_maxfun=3800,
        polish_maxfun=2500,
        nonlinear_alpha_second_pass_enabled=False,
        nonlinear_alpha_budget_mode="fast",
    )

    out = worker_spline_optimization(cfg, stop_event=Event(), progress_cb=lambda _p, _m: None)
    assert isinstance(out, dict)
    wm = float(out.get("pipeline_best_rmse_watermark", float("nan")))
    sp = out.get("spectral_rmse_seg_spline_sigma")
    spf = float(sp) if sp is not None else float("nan")

    assert np.isfinite(wm)
    assert wm < 0.0021, f"watermark RMSE trop élevée: {wm}"
    assert np.isfinite(spf)
    assert spf < 0.0021, f"RMSE spectrale spline cubique trop élevée: {spf}"
