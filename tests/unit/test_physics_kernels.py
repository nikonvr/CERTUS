"""Unit tests for _certus_physics_impl.py core kernels.

Tests the fundamental TMM (Transfer Matrix Method) kernels in isolation,
without going through the high-level pipeline or GUI wrappers.
Validated against analytical Fresnel solutions for known thin-film systems.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus_physics import (
    calculate_bare_substrate_RT,
    calculate_RT_vectorized_real_HL,
    calculate_single_interface_R,
    calculate_transmission_single,
    calc_spectrum_front,
    calc_spectrum_full,
)

# Non-exported kernels: import directly from impl
from _certus_physics_impl import (
    calculate_bare_substrate_R,
    calculate_reflection_single,
    calculate_RT_single_layer_single,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fresnel_R_normal(n1: float, n2: float) -> float:
    """Analytical single-interface reflectance at normal incidence."""
    return ((n1 - n2) / (n1 + n2)) ** 2


def fresnel_R_substrate_incoherent(n_sub: float) -> float:
    """Incoherent 2-surface substrate reflectance: 2R/(1+R)."""
    R = fresnel_R_normal(1.0, n_sub)
    return 2.0 * R / (1.0 + R)


def fresnel_T_substrate_incoherent(n_sub: float) -> float:
    """Incoherent transmittance through a thick substrate (2 surfaces)."""
    R = fresnel_R_normal(1.0, n_sub)
    return (1.0 - R) / (1.0 + R)


# ── 1. Bare substrate kernels ────────────────────────────────────────────────

class TestBareSubstrate:
    """Tests for calculate_bare_substrate_R and _RT."""

    @pytest.mark.parametrize("n_sub", [1.46, 1.52, 2.0, 2.35])
    def test_bare_substrate_R_matches_incoherent_formula(self, n_sub: float) -> None:
        wls = np.array([500.0], dtype=np.float64)
        n_arr = np.array([n_sub], dtype=np.float64)
        R = calculate_bare_substrate_R(wls, n_arr)
        expected = fresnel_R_substrate_incoherent(n_sub)
        assert abs(float(R[0]) - expected) < 1e-10, f"R mismatch: {R[0]} vs {expected}"

    @pytest.mark.parametrize("n_sub", [1.46, 1.52, 2.0, 2.35])
    def test_bare_substrate_RT_matches_fresnel(self, n_sub: float) -> None:
        wls = np.array([500.0], dtype=np.float64)
        n_arr = np.array([n_sub], dtype=np.float64)
        T = calculate_bare_substrate_RT(wls, n_arr)
        expected = fresnel_T_substrate_incoherent(n_sub)
        assert abs(float(T[0]) - expected) < 1e-10, f"T mismatch: {T[0]} vs {expected}"

    @pytest.mark.parametrize("n_sub", [1.46, 1.52, 2.0, 2.35])
    def test_R_plus_T_equals_1(self, n_sub: float) -> None:
        """Energy conservation: R + T = 1 for a lossless substrate."""
        wls = np.array([500.0], dtype=np.float64)
        n_arr = np.array([n_sub], dtype=np.float64)
        R = float(calculate_bare_substrate_R(wls, n_arr)[0])
        T = float(calculate_bare_substrate_RT(wls, n_arr)[0])
        assert abs(R + T - 1.0) < 1e-10, f"R+T = {R+T}, expected 1.0"

    def test_bare_substrate_vectorized(self) -> None:
        """Test vectorized operation on many wavelengths."""
        wls = np.linspace(300, 2000, 500, dtype=np.float64)
        n_sub = np.full_like(wls, 1.52)
        T = calculate_bare_substrate_RT(wls, n_sub)
        assert T.shape == (500,)
        assert np.all(np.isfinite(T))
        assert np.all(T > 0.0)
        assert np.all(T < 1.0)
        # All same n_sub -> all same T
        assert np.allclose(T, T[0])


# ── 2. Single-layer TMM kernels ─────────────────────────────────────────────

class TestSingleLayerTMM:
    """Tests for single-layer R/T computations."""

    def test_RT_single_layer_transparent_film(self) -> None:
        """Transparent film (k=0) on glass: R should oscillate, always finite."""
        wls = np.linspace(400, 800, 100)
        n_film = 2.0
        k_film = 0.0
        d_nm = 100.0
        n_sub = 1.52
        for lam in wls:
            R = calculate_RT_single_layer_single(float(lam), n_film, k_film, d_nm, n_sub)
            assert np.isfinite(R), f"R not finite at {lam} nm"
            assert 0.0 <= R <= 1.0, f"R out of [0,1]: {R} at {lam} nm"

    def test_RT_single_layer_quarter_wave_AR(self) -> None:
        """Quarter-wave antireflection: n_film = sqrt(n_sub), d = lambda/(4n).
        Should give R ≈ 0 at design wavelength."""
        n_sub = 1.52
        n_film = np.sqrt(n_sub)  # ~1.233
        lam0 = 550.0
        d_qw = lam0 / (4.0 * n_film)
        R = calculate_RT_single_layer_single(lam0, n_film, 0.0, d_qw, n_sub)
        assert abs(R) < 0.001, f"Quarter-wave AR: R should be ~0, got {R}"

    def test_RT_single_layer_absorbing(self) -> None:
        """Film with k > 0: R should still be finite and in [0,1]."""
        R = calculate_RT_single_layer_single(550.0, 2.0, 0.5, 50.0, 1.52)
        assert np.isfinite(R)
        assert 0.0 <= R <= 1.0


# ── 3. Transmission / reflection single-point kernels ───────────────────────

class TestTransmissionReflection:
    """Tests for calculate_transmission_single and calculate_reflection_single.
    
    Note: calculate_transmission_single returns (R_total, T_total) tuple.
    calculate_reflection_single returns a scalar R.
    """

    def test_transmission_transparent_film(self) -> None:
        """For a transparent film, T should be in (0, 1]."""
        result = calculate_transmission_single(550.0, 1.46, 0.0, 200.0, 1.52)
        # Returns (R, T) tuple
        R_val, T_val = result
        assert np.isfinite(T_val), "T not finite"
        assert 0.0 < T_val <= 1.0, f"T out of range: {T_val}"

    def test_reflection_transparent_film(self) -> None:
        """For a transparent film, R should be in [0, 1)."""
        R = calculate_reflection_single(550.0, 1.46, 0.0, 200.0, 1.52)
        assert np.isfinite(R), "R not finite"
        assert 0.0 <= R < 1.0, f"R out of range: {R}"

    def test_T_plus_R_conservation(self) -> None:
        """For a transparent film (k=0), R + T ≈ 1 (energy conservation)."""
        lam = 550.0
        n, k_val, d, n_sub = 2.0, 0.0, 137.5, 1.52
        R_t, T_t = calculate_transmission_single(lam, n, k_val, d, n_sub)
        assert abs(R_t + T_t - 1.0) < 0.005, f"R+T = {R_t+T_t:.6f}, expected ~1.0"

    def test_absorbing_film_energy_loss(self) -> None:
        """For k > 0, R + T < 1 (absorption eats energy)."""
        lam = 550.0
        R_t, T_t = calculate_transmission_single(lam, 2.0, 0.5, 100.0, 1.52)
        assert R_t + T_t < 1.0, f"R+T = {R_t+T_t:.6f}, should be < 1 for absorbing film"


# ── 4. Multi-layer vectorized TMM ───────────────────────────────────────────

class TestMultiLayerHL:
    """Tests for calculate_RT_vectorized_real_HL (alternating H/L stacks)."""

    def test_single_H_layer(self) -> None:
        """Single H layer: should be valid spectrum."""
        wls = np.linspace(400, 800, 100, dtype=np.float64)
        nH = np.full_like(wls, 2.35)
        nL = np.full_like(wls, 1.46)
        nSub = np.full_like(wls, 1.52)
        d = np.array([58.5], dtype=np.float64)  # ~QW at 550 nm
        R, T = calculate_RT_vectorized_real_HL(wls, nH, nL, nSub, d)
        assert R.shape == (100,)
        assert T.shape == (100,)
        assert np.all(np.isfinite(R))
        assert np.all(np.isfinite(T))
        assert np.all(R + T <= 1.001)

    def test_quarter_wave_mirror_high_R(self) -> None:
        """7-layer QW mirror (HLHLHLH): should have high R at design wavelength."""
        lam0 = 550.0
        nH_val, nL_val = 2.35, 1.46
        wls = np.array([lam0], dtype=np.float64)
        nH = np.full_like(wls, nH_val)
        nL = np.full_like(wls, nL_val)
        nSub = np.full_like(wls, 1.52)
        # 7 layers: H L H L H L H
        d_H = lam0 / (4 * nH_val)
        d_L = lam0 / (4 * nL_val)
        d = np.array([d_H, d_L, d_H, d_L, d_H, d_L, d_H], dtype=np.float64)
        R, T = calculate_RT_vectorized_real_HL(wls, nH, nL, nSub, d)
        # With backside correction, 7-layer QW mirror gives R ~ 0.93-0.94
        assert float(R[0]) > 0.90, f"7-layer QW mirror R = {R[0]:.4f}, expected > 0.90"

    def test_energy_conservation_multilayer(self) -> None:
        """R + T <= 1 for all wavelengths in a 10-layer stack."""
        wls = np.linspace(300, 900, 300, dtype=np.float64)
        nH = np.full_like(wls, 2.35)
        nL = np.full_like(wls, 1.46)
        nSub = np.full_like(wls, 1.52)
        d = np.array([60, 95, 60, 95, 60, 95, 60, 95, 60, 95], dtype=np.float64)
        R, T = calculate_RT_vectorized_real_HL(wls, nH, nL, nSub, d)
        violations = np.where(R + T > 1.001)[0]
        assert len(violations) == 0, f"Energy violation at {len(violations)} wavelengths"


# ── 5. Edge cases and numerical stability ───────────────────────────────────

class TestEdgeCases:
    """Tests for numerical edge cases and guard conditions."""

    def test_zero_thickness(self) -> None:
        """Zero thickness film: should behave like bare substrate."""
        R = calculate_RT_single_layer_single(550.0, 2.0, 0.0, 0.0, 1.52)
        R_bare = fresnel_R_normal(1.0, 1.52)
        assert abs(R - R_bare) < 0.01, f"Zero-d film R={R}, bare R={R_bare}"

    def test_very_thick_film(self) -> None:
        """Very thick film (50 µm): should not overflow or NaN."""
        R = calculate_RT_single_layer_single(550.0, 1.46, 0.0, 50000.0, 1.52)
        assert np.isfinite(R)
        assert 0.0 <= R <= 1.0

    def test_high_extinction(self) -> None:
        """Very absorbing film (metal-like): T should approach 0."""
        R_t, T_t = calculate_transmission_single(550.0, 1.5, 3.0, 200.0, 1.52)
        assert np.isfinite(T_t)
        assert T_t < 0.01, f"Expected near-zero T for metal-like film, got {T_t}"

    def test_substrate_n_equals_1(self) -> None:
        """Substrate with n=1 (air): bare substrate R should be 0."""
        wls = np.array([550.0], dtype=np.float64)
        n_sub = np.array([1.0], dtype=np.float64)
        R = calculate_bare_substrate_R(wls, n_sub)
        assert abs(float(R[0])) < 1e-10, "R should be 0 when n_sub = 1"
