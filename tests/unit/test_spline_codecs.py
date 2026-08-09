"""Unit tests: sigma codecs, monotonic n repair, k floor on nodes."""
from __future__ import annotations

import numpy as np

from certus.core.certus_core import N_MAX_LIMIT, N_MIN_LIMIT
from certus.spline.certus_index_spline_core import (
    K_FLOOR_DEFAULT,
    SIGMA_KNOTS_MIN_SEP_REL,
    _enforce_sigma_min_sep,
    canonical_spline_sigma_knots,
    enforce_k_floor_on_nodes,
    n_mono_knot_chains,
    n_mono_segment_flags,
    decode_xi_n_to_physical_n,
    encode_physical_n_to_xi_n,
)
from certus.spline.spline_objective import (
    physical_nodes_to_x_slice_n,
    sigma_knots_decode,
    sigma_knots_encode,
    x_slice_n_to_physical_nodes,
)


def test_sigma_knots_encode_decode_roundtrip() -> None:
    s_lo, s_hi = 0.001, 0.004
    sk = np.array([s_lo, 0.002, 0.0032, s_hi], dtype=np.float64)
    raw = sigma_knots_encode(sk, s_lo, s_hi)
    sk2 = sigma_knots_decode(raw, s_lo, s_hi)
    assert sk2.shape == sk.shape
    np.testing.assert_allclose(sk2, sk, rtol=0, atol=1e-9)


def test_physical_n_xi_roundtrip_with_mono_band() -> None:
    sk = np.array([1.0 / 800.0, 1.0 / 600.0, 1.0 / 400.0], dtype=np.float64)
    band = (450.0, 700.0)
    seg = n_mono_segment_flags(sk, band[0], band[1])
    assert seg.shape == (sk.size - 1,)
    chains = n_mono_knot_chains(seg)
    n_phys = np.array([1.52, 1.53, 1.55], dtype=np.float64)
    xi = encode_physical_n_to_xi_n(n_phys, chains, float(N_MIN_LIMIT), float(N_MAX_LIMIT))
    n_back = decode_xi_n_to_physical_n(xi, chains, float(N_MIN_LIMIT), float(N_MAX_LIMIT))
    np.testing.assert_allclose(n_back, n_phys, rtol=0, atol=1e-6)
    n_via_slice = x_slice_n_to_physical_nodes(xi, sk, band)
    xi2 = physical_nodes_to_x_slice_n(n_phys, sk, band)
    np.testing.assert_allclose(xi2, xi, rtol=0, atol=1e-6)
    np.testing.assert_allclose(n_via_slice, n_phys, rtol=0, atol=1e-6)


def test_enforce_k_floor_clamp_and_insert() -> None:
    sk = np.array([0.001, 0.002], dtype=np.float64)
    L = np.array([np.log(1e-7), np.log(1e-3)], dtype=np.float64)
    sk2, L2, mod = enforce_k_floor_on_nodes(sk, L, k_floor=K_FLOOR_DEFAULT, allow_insert=True)
    assert mod is True
    assert sk2.size >= sk.size
    assert np.all(L2 >= np.log(K_FLOOR_DEFAULT) - 1e-12)


def test_enforce_k_floor_noop_when_already_above() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    L = np.full(3, np.log(0.01), dtype=np.float64)
    sk2, L2, mod = enforce_k_floor_on_nodes(sk, L, k_floor=1e-6)
    assert mod is False
    np.testing.assert_array_equal(sk2, sk)
    np.testing.assert_array_equal(L2, L)


def test_n_mono_segment_flags_empty_knots() -> None:
    assert n_mono_segment_flags(np.array([]), 400.0, 800.0).size == 0
    assert n_mono_segment_flags(np.array([0.001]), 400.0, 800.0).size == 0


def test_canonical_mesh_respects_min_sep_ir_extension() -> None:
    """Regression: IR extension (K=14) must already respect eps_s so encode→decode is stable."""
    lam_min, lam_max = 249.99, 5199.88
    sk = canonical_spline_sigma_knots(lam_min, lam_max)
    s_lo, s_hi = 1.0 / lam_max, 1.0 / lam_min
    eps_s = max(1e-10, SIGMA_KNOTS_MIN_SEP_REL * (s_hi - s_lo))
    gaps = np.diff(sk)
    assert np.all(gaps >= eps_s - 1e-15), (
        f"canonical mesh gap {float(np.min(gaps)):.6e} < eps_s {eps_s:.6e}"
    )


def test_enforce_sigma_min_sep_encode_decode_roundtrip() -> None:
    """After _enforce_sigma_min_sep, encode→decode must be a no-op (within ~1e-9)."""
    lam_min, lam_max = 249.99, 5199.88
    sk = canonical_spline_sigma_knots(lam_min, lam_max)
    s_lo, s_hi = 1.0 / lam_max, 1.0 / lam_min
    raw = sigma_knots_encode(sk, s_lo, s_hi)
    sk2 = sigma_knots_decode(raw, s_lo, s_hi)
    assert sk2.shape == sk.shape
    np.testing.assert_allclose(sk2, sk, rtol=0, atol=1e-9)


def test_enforce_sigma_min_sep_pushes_close_knots() -> None:
    """Knots closer than eps_s are pushed apart by _enforce_sigma_min_sep."""
    s_lo, s_hi = 1e-4, 4e-3
    eps_s = SIGMA_KNOTS_MIN_SEP_REL * (s_hi - s_lo)
    sk = np.array([s_lo, s_lo + 5e-6, s_lo + 1e-5, 2e-3, s_hi], dtype=np.float64)
    assert np.min(np.diff(sk[:3])) < eps_s  # confirm violation
    sk_fixed = _enforce_sigma_min_sep(sk, s_lo, s_hi)
    gaps = np.diff(sk_fixed)
    assert np.all(gaps >= eps_s - 1e-15)
    assert sk_fixed[0] == s_lo
    assert sk_fixed[-1] >= s_hi
