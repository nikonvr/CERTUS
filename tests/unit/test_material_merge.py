import numpy as np
import pytest

from certus.core._certus_physics_impl import (
    find_matching_sheets,
    merge_two_curves,
    merge_multiple_curves,
    MergedMaterialDict,
)


@pytest.mark.unit
def test_find_matching_sheets() -> None:
    sheet_names = [
        "IR-H400-SiO2",
        "IR-H400-Nb2O5",
        "IR-Syrus-SiO2",
        "IR-Syrus-Nb2O5",
        "IR-H800-Ta2O5",
        "IR-H800-Nb2O5",
        "H800-Nb",
        "H800-SiO2",
        "Si-substrate",
        "IR-H800-SiO2",
        "Nb2O5-Syrus",
        "SiO2-Syrus",
    ]

    # Test process/material matching
    assert "H800-SiO2" in find_matching_sheets("H800-SiO2", sheet_names)
    assert "IR-H800-SiO2" in find_matching_sheets("H800-SiO2", sheet_names)
    assert len(find_matching_sheets("H800-SiO2", sheet_names)) == 2

    # Test alias mapping (Nb vs Nb2O5)
    assert "H800-Nb" in find_matching_sheets("H800-Nb", sheet_names)
    assert "IR-H800-Nb2O5" in find_matching_sheets("H800-Nb", sheet_names)
    assert len(find_matching_sheets("H800-Nb", sheet_names)) == 2

    # Test fallback substring matching
    assert "Si-substrate" in find_matching_sheets("substrate", sheet_names)


@pytest.mark.unit
def test_merge_two_curves_no_overlap() -> None:
    c1 = {
        "wl": np.array([400.0, 500.0], dtype=np.float64),
        "n": np.array([2.0, 2.1], dtype=np.float64),
        "k": np.array([0.01, 0.02], dtype=np.float64),
    }
    c2 = {
        "wl": np.array([600.0, 700.0], dtype=np.float64),
        "n": np.array([2.3, 2.4], dtype=np.float64),
        "k": np.array([0.03, 0.04], dtype=np.float64),
    }

    merged = merge_two_curves(c1, c2)
    assert np.allclose(merged["wl"], np.array([400.0, 500.0, 600.0, 700.0]))
    assert np.allclose(merged["n"], np.array([2.0, 2.1, 2.3, 2.4]))
    assert np.allclose(merged["k"], np.array([0.01, 0.02, 0.03, 0.04]))
    assert merged["min_wl_valid"] == 400.0
    assert merged["max_wl_valid"] == 700.0


@pytest.mark.unit
def test_merge_two_curves_with_overlap_and_blending() -> None:
    # Overlapping range: [500, 600]
    c1 = {
        "wl": np.array([400.0, 500.0, 600.0], dtype=np.float64),
        "n": np.array([2.00, 2.10, 2.20], dtype=np.float64),
    }
    c2 = {
        "wl": np.array([500.0, 600.0, 700.0], dtype=np.float64),
        "n": np.array([2.30, 2.40, 2.50], dtype=np.float64),
    }

    merged = merge_two_curves(c1, c2)
    
    # Unified wavelengths
    assert np.allclose(merged["wl"], np.array([400.0, 500.0, 600.0, 700.0]))
    
    # n at 400 must be exactly c1 n (2.0)
    assert merged["n"][0] == pytest.approx(2.0)
    # n at 700 must be exactly c2 n (2.5)
    assert merged["n"][3] == pytest.approx(2.5)
    
    # n at 500 (overlap_min) must be exactly c1 n at 500 (2.1) because weight is 0.0
    assert merged["n"][1] == pytest.approx(2.1)
    # n at 600 (overlap_max) must be exactly c2 n at 600 (2.4) because weight is 1.0
    assert merged["n"][2] == pytest.approx(2.4)


@pytest.mark.unit
def test_merged_material_dict() -> None:
    raw_data = {
        "H800-SiO2": {
            "wl": np.array([400.0, 500.0], dtype=np.float64),
            "n": np.array([1.46, 1.45], dtype=np.float64),
        },
        "IR-H800-SiO2": {
            "wl": np.array([500.0, 600.0], dtype=np.float64),
            "n": np.array([1.44, 1.43], dtype=np.float64),
        },
    }
    sheet_names = list(raw_data.keys())

    merged_dict = MergedMaterialDict(raw_data, sheet_names)

    # Key lookup check
    assert "H800-SiO2" in merged_dict
    assert "IR-H800-SiO2" in merged_dict
    
    # Merge on access check (H800-SiO2 matches both sheets!)
    merged_data = merged_dict["H800-SiO2"]
    assert np.allclose(merged_data["wl"], np.array([400.0, 500.0, 600.0]))
    assert merged_data["n"][0] == pytest.approx(1.46)
    assert merged_data["n"][1] == pytest.approx(1.45) # c1 at overlap_min
    assert merged_data["n"][2] == pytest.approx(1.44) # c2 at overlap_max (shifted for continuity)
