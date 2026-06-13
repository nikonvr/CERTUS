"""Intégration légère: grille RMSE(d) avec doublon extra→base et couverture complète."""

from __future__ import annotations

from typing import Any

import numpy as np
import time
import pytest

from certus.spline.certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
import certus.spline.spline_profile_corridors as spc


@pytest.fixture(autouse=True)
def _narrow_corridor_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spc, "corridor_profile_refit_maxfun", lambda *_a, **_k: 12)


@pytest.fixture(autouse=True)
def _silent_global_opt_from_break(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_quick(
        *_a: Any,
        **_kw: Any,
    ) -> dict[str, Any]:
        return {"success": False, "rmse": float("nan")}

    monkeypatch.setattr(spc, "quick_pwlnk_refit_result_dict", _fake_quick)


def test_manual_grid_reverse_extra_then_base_duplicate_keeps_coverage_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Grille 3000+i*10 nm: reverse depuis une cassure (+) peut atteindre 3000 avant la chaîne gauche.

    Le premier jeu de fits à 3000 nm (reverse, kind=extra) garde un RMSE bas; la visite base
    ultérieure est rejetée en doublon — le slot doit être compté comme base pour l’audit.

    Mécanisme: médiane des espacements grille = 10 nm → pas reverse = 5 nm ;
    depuis 3080 nm, j=16 donne 3000 nm avant la paire ofs=12 sur le dernier bras.
    """

    monkeypatch.delenv("NUMBA_DISABLE_JIT", raising=False)
    monkeypatch.setenv("NUMBA_DISABLE_JIT", "1")
    monkeypatch.delenv("NUMBA_DISABLE_PARALLEL", raising=False)
    monkeypatch.setenv("NUMBA_DISABLE_PARALLEL", "1")

    d_grid = np.array([float(3000 + 10 * j) for j in range(13)], dtype=np.float64)
    n_pts = int(d_grid.size)

    lam = np.linspace(400.0, 920.0, 18)
    sk = canonical_spline_sigma_knots(float(np.min(lam)), float(np.max(lam)))
    kk = int(sk.size)
    n_phys = np.full(kk, 2.1)
    L_ln = np.full(kk, np.log(5e-4))
    d0 = float(d_grid[n_pts // 2])
    dim = 1 + 2 * kk
    x_full = np.empty(dim)
    x_full[0] = d0
    x_full[1 : 1 + kk] = n_phys
    x_full[1 + kk : 1 + 2 * kk] = L_ln

    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.55),
        r_exp=None,
        n_sub=np.full_like(lam, 1.52),
        data_type=DataType.TRANSMISSION,
        n_seg=max(8, kk - 1),
        d_lo=float(np.min(d_grid)) - 200.0,
        d_hi=float(np.max(d_grid)) + 200.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
        corridor_profile_d_enabled=True,
        corridor_profile_d_parallel_walks=False,
    )

    base_result = {
        "sigma_knots": sk,
        "n_seg": kk - 1,
        "x": x_full.copy(),
        "n_nodes_physical": n_phys.copy(),
        "L_nodes": L_ln.copy(),
        "d_nm": d0,
        "lam_nm": lam,
        "n_lam": np.full_like(lam, 2.1),
        "k_lam": np.full_like(lam, 5e-4),
        "rmse": 0.01,
        "spectral_rmse_segments": 0.01,
    }

    d_target = float(d_grid[0])
    fit_passes_at_target: dict[str, int] = {"n": 0}

    def rmse_schedule(d_nm: float) -> float:
        dn = float(d_nm)
        if abs(dn - d_target) < 0.2:
            fit_passes_at_target["n"] += 1
            # 2 appels polish par visite réussie (~fit0 puis fit1) : garder RMSE excellent
            # pour le premier bloc (reverse extra), médiocre ensuite (visite base rejetée).
            if fit_passes_at_target["n"] <= 2:
                return 1e-4
            return 5e-2
        anchors_nm_rmse = (
            (3060.0, 2.0),
            (3070.0, 2.0),
            (3080.0, 1e-5),
            (3075.0, 5e-6),
            (3085.0, 3.0),
        )
        for d_ref, rr in anchors_nm_rmse:
            if abs(dn - d_ref) <= 0.26:
                return float(rr)
        return float(1.25 + abs(dn - 3060.0) * 2e-4)

    def fake_fit(cfg2, ski, d_nm, x_seed, bounds_nodes, **_kw: Any) -> dict[str, Any] | None:
        dn = float(d_nm)
        lam_v = np.asarray(cfg2.lam_nm, dtype=np.float64).ravel()
        n_l = lam_v.size
        bk = np.asarray(bounds_nodes, dtype=np.float64).reshape(-1, 2)
        xb = np.clip(np.asarray(x_seed, dtype=np.float64).ravel(), bk[:, 0], bk[:, 1])
        if int(xb.size) != 2 * kk:
            return None
        rmse = rmse_schedule(dn)
        n_lami = np.full(n_l, 2.06 + dn * 1e-14, dtype=np.float64)
        k_lami = np.full(n_l, 5e-4 + dn * 1e-15, dtype=np.float64)

        return {
            "success": True,
            "rmse": float(rmse),
            "nit": 1,
            "nfev": 2,
            "x_nodes_best": xb.copy(),
            "n_lam": n_lami,
            "k_lam": k_lami,
        }

    monkeypatch.setattr(spc, "_fit_nodes_at_fixed_d", fake_fit)

    out = spc.compute_regular_grid_rmse_profile(
        cfg,
        base_result,
        d_grid,
        profile_polish_maxfun=8,
        breakpoint_lookback_points=3,
    )

    assert str(out.get("profile_d_status", "")) == "manual_grid"

    pk = np.asarray(out["profile_d_manual_grid_point_kind"], dtype=np.int32).ravel()
    dvals = np.asarray(out["profile_d_values_nm"], dtype=np.float64).ravel()

    kinds_by_d = {float(dvals[i]): int(pk[i]) for i in range(int(pk.size))}
    bases = int(sum(1 for v in kinds_by_d.values() if v == 0))
    assert bases == n_pts, (
        f"attendu {n_pts} points base (audit), observé={bases}; kinds_by_d={kinds_by_d!r}"
    )

    assert bool(out.get("profile_d_manual_grid_coverage_complete", False)) is True
