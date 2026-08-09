"""Targeted hot-path tests for _certus_physics_impl utilities."""

from __future__ import annotations
from certus.physics.certus_material_db import numba_interp_vectorized
from certus.physics.certus_material_db import numba_interp_scalar
from certus.physics.certus_colorimetry import lab_to_xyz

import numpy as np
import pytest

from certus.core._certus_physics_impl import (
    MaterialDatabase,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATE_MIN_LAMBDA,
    arange_inclusive,
    calc_qwot,
    calc_rmse,
    compute_RT_from_matrix,
    compute_TMM_single_point_k0_exact,
    delta_e_2000,
    get_n_substrate_array_by_id,
    trim_worst_only,
    validate_wavelengths_batch,
    xyz_from_spectrum,
    xyz_to_lab,
)
from certus.physics.certus_strat_math import fit_parabola_vertex_3points


class _DummyTarget:
    def __init__(self, lmin: float, lmax: float, tmin: float, tmax: float, w: float = 1.0) -> None:
        self.lmin = lmin
        self.lmax = lmax
        self.tmin = tmin
        self.tmax = tmax
        self.w = w

    def valid(self) -> bool:
        return bool(self.lmax >= self.lmin and self.w > 0.0)


@pytest.mark.unit
def test_arange_inclusive_includes_stop_and_validates_step() -> None:
    arr = arange_inclusive(400.0, 500.0, 50.0, decimals=1)
    assert np.allclose(arr, np.array([400.0, 450.0, 500.0]))
    with pytest.raises(ValueError):
        arange_inclusive(400.0, 500.0, 0.0)


@pytest.mark.unit
def test_trim_worst_only_trims_sorted_tail() -> None:
    data = np.array([3.0, 1.0, 5.0, 2.0, 4.0])
    trimmed = trim_worst_only(data, trim_percent=20)
    assert np.allclose(trimmed, np.array([1.0, 2.0, 3.0, 4.0]))
    assert trim_worst_only(np.array([])).size == 0


@pytest.mark.unit
def test_fit_parabola_vertex_3points_coefficients() -> None:
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([1.0, 0.0, 1.0])  # y = (x - 2)^2 = x^2 - 4x + 4
    a, b, c = fit_parabola_vertex_3points(x, y)
    assert a == pytest.approx(1.0, rel=1e-8, abs=1e-8)
    assert b == pytest.approx(-4.0, rel=1e-8, abs=1e-8)
    assert c == pytest.approx(4.0, rel=1e-8, abs=1e-8)


@pytest.mark.unit
def test_calc_qwot_and_calc_rmse_weighted_band() -> None:
    qw = calc_qwot(2.0, 550.0, 68.75)  # 4*n*d/l0 = 1
    assert qw == pytest.approx(1.0, rel=1e-10, abs=1e-10)

    wls = np.array([500.0, 550.0, 600.0], dtype=np.float64)
    ts = np.array([0.50, 0.60, 0.70], dtype=np.float64)
    targets = [_DummyTarget(lmin=500.0, lmax=600.0, tmin=0.55, tmax=0.65, w=1.0)]
    rmse, mse = calc_rmse(ts, wls, targets)
    assert rmse > 0.0
    assert mse > 0.0
    assert rmse == pytest.approx(np.sqrt(mse), rel=1e-10, abs=1e-10)


@pytest.mark.unit
def test_colorimetry_roundtrip_and_delta_e_zero() -> None:
    wls = np.linspace(400.0, 700.0, 31)
    refl = np.full_like(wls, 0.5)
    xyz = xyz_from_spectrum(wls, refl)
    lab = xyz_to_lab(xyz)
    xyz_back = lab_to_xyz(lab)
    assert xyz.shape == (3,)
    assert lab.shape == (3,)
    assert xyz_back.shape == (3,)
    assert np.allclose(xyz_back, xyz, rtol=1e-4, atol=1e-4)
    assert delta_e_2000(lab, lab) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.unit
def test_numba_interp_scalar_and_vectorized_linear_extrapolation() -> None:
    xp = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    fp = np.array([1.0, 2.0, 3.0], dtype=np.float64)

    assert numba_interp_scalar(550.0, xp, fp) == pytest.approx(2.5, rel=1e-12, abs=1e-12)
    assert numba_interp_scalar(350.0, xp, fp) == pytest.approx(0.5, rel=1e-12, abs=1e-12)
    assert numba_interp_scalar(650.0, xp, fp) == pytest.approx(3.5, rel=1e-12, abs=1e-12)

    x_arr = np.array([350.0, 450.0, 650.0], dtype=np.float64)
    got = numba_interp_vectorized(x_arr, xp, fp)
    expected = np.array([0.5, 1.5, 3.5], dtype=np.float64)
    assert np.allclose(got, expected, rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_numba_interp_edge_cases_empty_and_singleton_grid() -> None:
    # Empty interpolation grid -> NaN by contract.
    xp_empty = np.array([], dtype=np.float64)
    fp_empty = np.array([], dtype=np.float64)
    assert np.isnan(numba_interp_scalar(500.0, xp_empty, fp_empty))

    # Singleton grid -> constant value regardless of x.
    xp_one = np.array([550.0], dtype=np.float64)
    fp_one = np.array([1.234], dtype=np.float64)
    assert numba_interp_scalar(400.0, xp_one, fp_one) == pytest.approx(1.234, abs=1e-12)
    assert numba_interp_scalar(700.0, xp_one, fp_one) == pytest.approx(1.234, abs=1e-12)

    x_arr = np.array([400.0, 550.0, 700.0], dtype=np.float64)
    got = numba_interp_vectorized(x_arr, xp_one, fp_one)
    assert np.allclose(got, np.array([1.234, 1.234, 1.234], dtype=np.float64), atol=1e-12)


@pytest.mark.unit
def test_get_n_substrate_array_by_id_handles_unknown_and_min_lambda() -> None:
    with pytest.raises(KeyError):
        get_n_substrate_array_by_id(-999, np.array([550.0], dtype=np.float64))

    # Use one known Sellmeier substrate (excluding sapphire special-case id=3).
    substrate_id = next(k for k in SELLMEIER_COEFFS_BY_ID.keys() if int(k) != 3)
    min_lambda = float(SUBSTRATE_MIN_LAMBDA.get(substrate_id, 200.0))
    wls = np.array([min_lambda - 10.0, min_lambda + 10.0], dtype=np.float64)
    n_arr = get_n_substrate_array_by_id(int(substrate_id), wls)
    assert np.isnan(n_arr[0])
    assert np.isfinite(n_arr[1]) and n_arr[1] > 1.0


@pytest.mark.unit
def test_validate_wavelengths_batch_shape_and_nonnegative_metrics() -> None:
    candidate_wls = np.array([550.0, 650.0], dtype=np.float64)
    n_h = np.array([2.3, 2.3], dtype=np.float64)
    n_l = np.array([1.45, 1.45], dtype=np.float64)
    n_sub = np.array([1.52, 1.52], dtype=np.float64)
    runs_history = np.array([[80.0, 120.0], [81.0, 119.0]], dtype=np.float64)
    p_thick_nominal = np.array([80.0, 120.0, 90.0], dtype=np.float64)
    noise_values = np.array([0.0, 0.0], dtype=np.float64)

    metrics = validate_wavelengths_batch(
        candidate_wls,
        n_h,
        n_l,
        n_sub,
        runs_history,
        p_thick_nominal,
        2,  # evaluate current layer index
        0.0,
        noise_values,
        2.0,
    )
    #FOUR columns since the integration of the three criteria of Phase A:
    #   0 = P95(|Delta d|) en nm   1 = ecart-type   2 = taux de plantage   3 = gain
    #This test required (2, 2) and `metrics >= 0` everywhere. Both were wrong:
    #the GAIN column admits a NEGATIVE value as sentinel “no
    # mesurable » — le depot ne se termine pas meme a bruit nul — et
    # _validate_candidates_phase_a s'en sert pour eliminer (certus_strat_service.py,
    #`if crash_rate >= crash_tol or gain < 0.0`). A global assertion
    #`>= 0` would therefore prohibit the sentinel which operates the filter.
    assert metrics.shape == (2, 4)
    assert np.all(np.isfinite(metrics))
    p95, std, crash, gain = metrics[:, 0], metrics[:, 1], metrics[:, 2], metrics[:, 3]
    assert np.all(p95 >= 0.0), "un P95 d'ecart d'epaisseur ne peut pas etre negatif"
    assert np.all(std >= 0.0), "un ecart-type ne peut pas etre negatif"
    assert np.all((crash >= 0.0) & (crash <= 1.0)), "le taux de plantage est une proportion"
    assert np.all(np.isfinite(gain)), "le gain peut etre negatif (sentinelle), jamais non fini"


@pytest.mark.unit
def test_compute_rt_from_matrix_handles_zero_admittance_and_low_incident_real_part() -> None:
    # Degenerate matrix -> Y_sys == 0 path.
    r0, t0 = compute_RT_from_matrix(
        complex(0.0, 0.0),
        complex(0.0, 0.0),
        complex(0.0, 0.0),
        complex(0.0, 0.0),
        complex(1.0, 0.0),
        complex(1.52, 0.0),
    )
    assert r0 == pytest.approx(0.0, abs=1e-14)
    assert t0 == pytest.approx(0.0, abs=1e-14)

    # Very small Re(n_inc) -> explicit transmission clamp to 0.
    r1, t1 = compute_RT_from_matrix(
        complex(1.0, 0.0),
        complex(0.0, 0.0),
        complex(0.0, 0.0),
        complex(1.0, 0.0),
        complex(1e-12, 0.0),
        complex(1.52, 0.0),
    )
    assert r1 >= 0.0
    assert t1 == pytest.approx(0.0, abs=1e-14)


@pytest.mark.unit
def test_compute_tmm_single_point_exact_normalizes_positive_imaginary_part() -> None:
    k0 = 2.0 * np.pi / 550.0
    thicknesses = np.array([80.0], dtype=np.float64)

    # Intentionally feed "n + ik" to exercise the guard that converts to n - ik.
    n_layers_pos_imag = np.array([complex(2.3, +0.05)], dtype=np.complex128)
    n_layers_neg_imag = np.array([complex(2.3, -0.05)], dtype=np.complex128)
    n_sub = complex(1.52, 0.0)

    rf_pos, tf_pos, rb_pos = compute_TMM_single_point_k0_exact(
        k0, thicknesses, n_layers_pos_imag, n_sub
    )
    rf_neg, tf_neg, rb_neg = compute_TMM_single_point_k0_exact(
        k0, thicknesses, n_layers_neg_imag, n_sub
    )

    assert rf_pos == pytest.approx(rf_neg, rel=1e-10, abs=1e-10)
    assert tf_pos == pytest.approx(tf_neg, rel=1e-10, abs=1e-10)
    assert rb_pos == pytest.approx(rb_neg, rel=1e-10, abs=1e-10)


@pytest.mark.unit
def test_material_database_missing_file_loads_empty_data(tmp_path) -> None:
    missing = tmp_path / "missing_materials.xlsx"
    db = MaterialDatabase(filepath=str(missing))
    assert db.data == {}
    assert db.get_material_list() == []


@pytest.mark.unit
def test_material_database_interpolation_cache_and_ranges() -> None:
    db = MaterialDatabase(filepath="unused.xlsx")
    db._data = {
        "SiO2-Layer": {
            "wl": np.array([400.0, 500.0, 600.0], dtype=np.float64),
            "n": np.array([1.46, 1.455, 1.45], dtype=np.float64),
            "min_wl_valid": 400.0,
            "max_wl_valid": 600.0,
        }
    }

    n1 = db.get_index("SiO2-Layer", 550.0)
    n2 = db.get_index("SiO2-Layer", 550.0)  # cached path
    assert n1 == pytest.approx(1.4525, rel=1e-10, abs=1e-10)
    assert n2 == pytest.approx(n1, rel=1e-12, abs=1e-12)
    assert len(db._interpolation_cache) == 1

    vec = db.get_clues_vectorized("SiO2-Layer", np.array([450.0, 550.0], dtype=np.float64))
    assert np.allclose(vec, np.array([1.4575, 1.4525], dtype=np.float64), atol=1e-10)
    assert db.get_wavelength_range("SiO2-Layer") == (400.0, 600.0)
    assert db.get_material_list() == ["SiO2-Layer"]

    db.clear_cache()
    assert len(db._interpolation_cache) == 0



@pytest.mark.unit
def test_material_database_generic_computation_cache_stats() -> None:
    db = MaterialDatabase(filepath="unused.xlsx")

    def _compute(a: int, b: int) -> int:
        return a + b

    out1 = db.get_cached_computation("sum:1:2", _compute, 1, 2)
    out2 = db.get_cached_computation("sum:1:2", _compute, 1, 2)
    assert out1 == 3
    assert out2 == 3

    stats = db.get_cache_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["cache_size"] >= 1
    assert 0.0 <= stats["hit_rate"] <= 1.0
