"""The RMSE(d) corridor starts from the n, k the window displays (audit 2026-11-15, L3-m3).

With separate sigma meshes for n and L (free-knot SOL3 stage), the display projects L onto the mesh of n
(`_snap_nk_mesh_sol3_split`), while `_extract_knots_and_nodes_from_result` projected n onto the mesh of L: the corridor
started from another model than the one shown. Not triggered by the default SPLINE example, whose result has a single
mesh; owner's decision (2026-11-16): align anyway.
"""

from __future__ import annotations

import numpy as np

from certus.spline.certus_corridor_utils import _extract_knots_and_nodes_from_result
from certus.spline.spline_workers import _snap_nk_mesh_sol3_split


def _result(sk_n: np.ndarray, sk_L: np.ndarray) -> dict:
    return {
        "sigma_knots_n": sk_n,
        "sigma_knots_L": sk_L,
        "n_nodes_physical": np.array([2.30, 2.20, 2.12, 2.08, 2.05]),
        "L_nodes": np.array([-9.0, -10.0, -11.5, -12.0, -12.5]),
        "d_nm": 250.0,
    }


def test_two_meshes_give_the_projection_of_the_display() -> None:
    sk_n = np.array([1.0e-3, 1.3e-3, 1.6e-3, 2.0e-3, 2.5e-3])
    sk_L = np.array([1.0e-3, 1.4e-3, 1.7e-3, 2.1e-3, 2.5e-3])
    res = _result(sk_n, sk_L)
    sk, n_nodes, L_nodes, d_nm, meta = _extract_knots_and_nodes_from_result(res)

    sk_ref, nn_at, LL_at = _snap_nk_mesh_sol3_split(
        sk_n, sk_L, res["n_nodes_physical"], res["L_nodes"], np.zeros(0), sigma_snap_atol=0.0
    )
    np.testing.assert_array_equal(sk, sk_ref)
    np.testing.assert_array_equal(n_nodes, nn_at)
    np.testing.assert_array_equal(L_nodes, LL_at)
    assert d_nm == 250.0
    assert meta["sigma_grids_coincide"] is False


def test_one_mesh_is_returned_as_it_is() -> None:
    sk = np.array([1.0e-3, 1.4e-3, 1.7e-3, 2.1e-3, 2.5e-3])
    res = _result(sk, sk)
    out_sk, n_nodes, L_nodes, _d, meta = _extract_knots_and_nodes_from_result(res)
    np.testing.assert_array_equal(out_sk, sk)
    np.testing.assert_array_equal(n_nodes, res["n_nodes_physical"])
    np.testing.assert_array_equal(L_nodes, res["L_nodes"])
    assert meta["sigma_grids_coincide"] is True
