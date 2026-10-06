import numpy as np
import pandas as pd

from certus.utils.certus_index_utils import (
    DataType,
    _detect_data_type_from_array,
    _detect_type_from_column_name,
    _ensure_strictly_increasing,
    _filter_rmse_peaks_iteratively,
    _lam_uniform_grid,
    _merge_closest_knot_pair,
    _safe_int_from_mapping,
    _sorted_finite_sigma_knots,
    analyze_loaded_data,
    calculate_index_rmse,
    normalize_index_config,
    spectral_rmse_weights,
)


def test_detect_data_type_from_array():
    # Empty array defaults to T
    assert _detect_data_type_from_array(np.array([])) == "T"
    
    # Transmission is usually high
    assert _detect_data_type_from_array(np.array([0.9, 0.95, 0.85])) == "T"
    
    # Reflection is usually low
    assert _detect_data_type_from_array(np.array([0.05, 0.1, 0.15])) == "R"
    
    # Values > 1.5 are normalized
    assert _detect_data_type_from_array(np.array([90.0, 95.0, 85.0])) == "T"

def test_detect_type_from_column_name():
    assert _detect_type_from_column_name("T") == "T"
    assert _detect_type_from_column_name("Transmission") == "T"
    assert _detect_type_from_column_name("R") == "R"
    assert _detect_type_from_column_name("Refl") == "R"
    assert _detect_type_from_column_name("Wavelength") == "unknown"

def test_lam_uniform_grid():
    grid = _lam_uniform_grid(400.0, 410.0, 2.0)
    assert np.array_equal(grid, np.array([400.0, 402.0, 404.0, 406.0, 408.0, 410.0]))
    
    # invalid
    assert len(_lam_uniform_grid(410.0, 400.0, 2.0)) == 0

def test_spectral_rmse_weights():
    lam = np.array([400.0, 500.0, 600.0])
    w = spectral_rmse_weights(lam)
    assert len(w) == 3
    assert np.isclose(np.sum(w), 3.0)

def test_sorted_finite_sigma_knots():
    knots = np.array([0.0, -1.0, np.nan, 2.5, 1.2, 1.2])
    cleaned = _sorted_finite_sigma_knots(knots)
    assert np.array_equal(cleaned, np.array([1.2, 2.5]))

def test_ensure_strictly_increasing():
    arr = np.array([1.0, 1.0, 2.0, 1.5])
    strict = _ensure_strictly_increasing(arr, min_gap=0.1)
    assert strict[1] > strict[0]
    assert strict[2] > strict[1]
    assert strict[3] > strict[2]

def test_merge_closest_knot_pair():
    lam = np.array([1.0, 2.0, 2.1, 4.0])
    k = np.array([0.1, 0.2, 0.3, 0.4])
    new_lam, _new_k = _merge_closest_knot_pair(lam, k)
    assert len(new_lam) == 3
    assert new_lam[1] == 2.05

def test_filter_rmse_peaks_iteratively():
    d = np.array([1, 2, 3, 4, 5])
    r = np.array([0.1, 0.5, 0.2, 0.6, 0.1]) # peaks at idx 1 and 3
    df, _rf = _filter_rmse_peaks_iteratively(d, r)
    assert len(df) == 2
    assert np.array_equal(df, np.array([1, 5]))

def test_safe_int_from_mapping():
    m = {"a": "42", "b": "foo"}
    assert _safe_int_from_mapping(m, "a") == 42
    assert _safe_int_from_mapping(m, "b", default=10) == 10
    assert _safe_int_from_mapping(m, "c", default=5) == 5

def test_normalize_index_config():
    cfg = {
        "substratee": "Sapphire",
        "weight_t": "2.0",
        "frosted": "true",
        "stack_string": "1.0, 2.0",
    }
    norm = normalize_index_config(cfg)
    assert norm["substrate"] == "Al2O3"
    assert norm["weight_T"] == 2.0
    assert norm["frosted"] is True
    assert norm["stack_multipliers"] == [1.0, 2.0]

def test_calculate_index_rmse():
    assert calculate_index_rmse(4.0) == 2.0
    assert calculate_index_rmse(-1.0) == 0.0

def test_analyze_loaded_data():
    df = pd.DataFrame({
        "wl": [400, 500, 600],
        "T": [0.9, 0.9, 0.9],
        "R": [0.1, 0.1, 0.1]
    })
    typ, res = analyze_loaded_data(df)
    assert typ == DataType.BOTH
    assert res["T"] is not None
    assert res["R"] is not None

from certus.utils.certus_index_utils import fit_k_global_8p, fit_sellmeier_global


def test_fit_sellmeier_global():
    # Synthetic constant index n = 1.5
    wls_nm = np.array([400.0, 500.0, 600.0, 700.0])
    n_exp = np.array([1.5, 1.5, 1.5, 1.5])
    
    n_fit, p_opt = fit_sellmeier_global(wls_nm, n_exp, material='other')
    
    assert p_opt is not None
    assert len(n_fit) == 4
    # The fit should be somewhat close to 1.5
    assert np.all(np.abs(n_fit - 1.5) < 0.1)
    
def test_fit_k_global_8p():
    # Synthetic zero extinction
    wls_nm = np.array([400.0, 500.0, 600.0, 700.0])
    k_exp = np.array([0.01, 0.01, 0.01, 0.01])
    
    k_fit, p_opt = fit_k_global_8p(wls_nm, k_exp)
    
    # In fit_k_global_8p, the mask requires k_exp > 1e-8 and L_um >= 0.8
    # Since our max wavelength is 700 nm = 0.7 um, it will be masked out completely!
    # If mask has < 8 points, it returns k_exp directly
    assert p_opt is None
    assert np.array_equal(k_fit, k_exp)

def test_fit_k_global_8p_valid():
    # Need >= 8 points with wavelength >= 800 nm (0.8 um)
    wls_nm = np.linspace(800.0, 2000.0, 10)
    k_exp = np.full(10, 0.1)
    
    k_fit, p_opt = fit_k_global_8p(wls_nm, k_exp)
    assert p_opt is not None
    assert len(k_fit) == 10
