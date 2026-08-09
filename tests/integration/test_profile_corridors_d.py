"""Minimal test: n/k corridors by d-profiling (no UI).



Budgets are intentionally tight so the whole module finishes in about 30-45s

(typical laptop; uses a local monkeypatch on ``corridor_profile_refit_maxfun``):

fewer lambda points, fewer spline segments, capped continuation steps, no boundary bisection

unless the scenario requires it.


"""


from __future__ import annotations



import numpy as np

import pytest

from scipy.optimize import OptimizeResult



import certus.spline.certus_index_spline_core as _core_mod

import certus.spline.spline_profile_corridors as _spc_mod



from certus.spline.certus_index_spline_core import (

    DataType,

    SplineOptConfig,

    canonical_spline_sigma_knots,

    corridor_profile_refit_maxfun,

)

from certus.spline.spline_objective import spectral_mse_rmse_masked_from_nk

from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference

from certus.spline.spline_profile_corridors import (

    ProfileCorridorConfig,

    _expand_corridor_envelope_with_reported_nk,

    _extract_knots_and_nodes_from_result,

    _bounds_for_nodes_only,

    _fit_nodes_at_fixed_d,

    _spectral_rmse_at_packed_nodes,

    _x_nodes0_from_mesh_x_if_consistent,

    compute_profiled_corridors_by_d,

)

from certus.spline.certus_index_spline_corridor_contract import (
    CORRIDOR_LIVE_STATUS,
    normalize_corridor_live_payload,
)



# --- Fast suite defaults (total runtime target ~15-20s) ---
# ── PARE-FEU ──────────────────────────────────────────────────────────────────
#These budgets are deliberately tight for the CI.
# The tests check the STRUCTURE of the results (keys, shapes, intervals),
# NOT exact numerical convergence.
#If a test fails after reduction: increase its local n=, NOT these globals.
# ──────────────────────────────────────────────────────────────────────────────


_LAM_N = 14


_N_SEG = 5


_POLISH = 150  # cfg polish_maxfun (production floor for refits is bypassed below in tests)





@pytest.fixture(autouse=True)

def _cheap_corridor_refit_maxfun(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:

    """Lower L-BFGS-B maxfun for d-profiling refits in this module only (production floor stays 300)."""

    if "test_corridor_profile_refit_maxfun_override_and_fallback" in request.node.nodeid:

        return

    def _cheap(cfg: SplineOptConfig, override: int | None = None) -> int:

        if override is not None:

            return int(max(50, min(int(override), 150)))

        v = getattr(cfg, "corridor_profile_d_polish_maxfun", None)

        if v is not None:

            try:

                iv = int(v)

                if iv > 0:

                    return int(max(50, min(iv, 120)))

            except (TypeError, ValueError):

                pass

        return 60

    monkeypatch.setattr(_core_mod, "corridor_profile_refit_maxfun", _cheap)

    monkeypatch.setattr(_spc_mod, "corridor_profile_refit_maxfun", _cheap)



def _lam(lo: float = 400.0, hi: float = 800.0, n: int | None = None) -> np.ndarray:

    return np.linspace(lo, hi, int(n or _LAM_N))



def _cfg_base(*, lam: np.ndarray, n_seg: int | None = None, **kwargs: object) -> SplineOptConfig:

    n_seg_eff = int(n_seg if n_seg is not None else _N_SEG)

    t_exp = kwargs.pop("t_exp", None)

    if t_exp is None:

        t_exp = np.full_like(lam, 0.92, dtype=np.float64)

    return SplineOptConfig(

        lam_nm=np.asarray(lam, dtype=np.float64),

        data_type=DataType.TRANSMISSION,

        t_exp=np.asarray(t_exp, dtype=np.float64),

        t_is_ratio=True,

        substrate_name="Sapphire",

        substrate_thickness_nm=0.0,

        d_min_nm=80.0,

        d_max_nm=220.0,

        n_seg=n_seg_eff,

        n_min=1.0,

        n_max=3.5,

        k_min=1e-8,

        k_max=1e-1,

        rmse_fit_lambda_nm=(float(lam[0]), float(lam[-1])),

        corridor_profile_d_polish_maxfun=_POLISH,

        **kwargs,

    )



def test_corridor_payload_contract_roundtrip() -> None:
    payload = normalize_corridor_live_payload(
        {
            "profile_d_values_nm": np.array([2.0, 1.0, 3.0]),
            "profile_d_rmse_values": np.array([0.2, 0.1, 0.3]),
            "profile_d_status": CORRIDOR_LIVE_STATUS,
            "profile_d_manual_grid_current_d_nm": 2.0,
        }
    )

    assert payload["profile_d_status"] == CORRIDOR_LIVE_STATUS
    np.testing.assert_allclose(payload["profile_d_values_nm"], [2.0, 1.0, 3.0])
    np.testing.assert_allclose(payload["profile_d_rmse_values"], [0.2, 0.1, 0.3])
    np.testing.assert_allclose(payload["corridor_d_plot"], [2.0, 1.0, 3.0])
    np.testing.assert_allclose(payload["corridor_rmse_plot"], [0.2, 0.1, 0.3])



def test_corridor_payload_contract_legacy_keys_are_supported() -> None:
    payload = normalize_corridor_live_payload(
        {
            "d_plot": np.array([5.0, 4.0, 6.0]),
            "r_plot": np.array([0.5, 0.4, 0.6]),
        }
    )

    assert payload["profile_d_status"] == CORRIDOR_LIVE_STATUS
    np.testing.assert_allclose(payload["profile_d_values_nm"], [5.0, 4.0, 6.0])
    np.testing.assert_allclose(payload["profile_d_rmse_values"], [0.5, 0.4, 0.6])
    np.testing.assert_allclose(payload["corridor_d_vis"], [5.0, 4.0, 6.0])
    np.testing.assert_allclose(payload["corridor_rmse_vis"], [0.5, 0.4, 0.6])


def test_corridor_payload_contract_trims_mismatched_series() -> None:
    payload = normalize_corridor_live_payload(
        {
            "profile_d_values_nm": np.array([1.0, 2.0, 3.0, 4.0]),
            "profile_d_rmse_values": np.array([0.1, 0.2]),
        }
    )

    assert payload["profile_d_values_nm"].shape == payload["profile_d_rmse_values"].shape
    np.testing.assert_allclose(payload["profile_d_values_nm"], [1.0, 2.0])
    np.testing.assert_allclose(payload["profile_d_rmse_values"], [0.1, 0.2])
