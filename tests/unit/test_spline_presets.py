"""Tests for spline_presets material projection helpers."""
from __future__ import annotations

import numpy as np
import pytest

from certus.spline.spline_presets import (
    _interp_n_L_linear_on_sigma,
    _project_nb2o5_preset_to_sigma_knots,
    _project_sio2_preset_to_sigma_knots,
    _project_tabulated_nk_lam_preset_to_sigma_knots,
    project_manual_material_preset,
)


def test_interp_n_L_linear_on_sigma_basic() -> None:
    sk_ref = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    n_ref = np.array([1.4, 1.5, 1.6], dtype=np.float64)
    L_ref = np.array([-10.0, -9.0, -8.0], dtype=np.float64)
    sk_tgt = np.array([0.0015, 0.0025], dtype=np.float64)
    n_out, L_out = _interp_n_L_linear_on_sigma(sk_ref, n_ref, L_ref, sk_tgt)
    assert n_out.shape == sk_tgt.shape
    assert L_out.shape == sk_tgt.shape
    assert np.all(np.isfinite(n_out))
    assert np.all(np.isfinite(L_out))


def test_project_nb2o5_preset() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    sk_out, n_out, L_out, d_out = _project_nb2o5_preset_to_sigma_knots(sk)
    assert sk_out.shape == sk.shape
    assert n_out.shape == sk.shape
    assert L_out.shape == sk.shape
    assert d_out > 0


def test_project_sio2_preset_uses_hint() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    _, _, _, d_out = _project_sio2_preset_to_sigma_knots(sk, d_nm_hint=1234.5)
    assert d_out == pytest.approx(1234.5)


def test_project_tabulated_preset_to_sigma_knots() -> None:
    lam = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    n = np.array([2.0, 2.1, 2.2], dtype=np.float64)
    k = np.array([0.01, 0.02, 0.03], dtype=np.float64)
    sk = np.array([0.0015, 0.0025], dtype=np.float64)
    sk_out, n_out, L_out, d_out = _project_tabulated_nk_lam_preset_to_sigma_knots(lam, n, k, sk, d_nm_hint=777.0)
    assert sk_out.shape == sk.shape
    assert n_out.shape == sk.shape
    assert L_out.shape == sk.shape
    assert d_out == pytest.approx(777.0)


def test_project_manual_material_preset_dispatches() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    for preset in ("nb2o5", "sio2", "ta2o5"):
        out = project_manual_material_preset(preset, sk, d_nm_hint=999.0)
        assert len(out) == 4
        assert out[0].shape == sk.shape


def test_project_manual_material_preset_unknown_raises() -> None:
    with pytest.raises(ValueError):
        project_manual_material_preset("unknown", np.array([0.001], dtype=np.float64))


@pytest.mark.parametrize("material", ["sio2", "ta2o5", "nb2o5"])
@pytest.mark.parametrize("wavelength_nm", [400.0, 1000.0, 3000.0])
def test_the_presets_are_the_published_optical_constants(material: str, wavelength_nm: float) -> None:
    """Smart Init starts from the optical constants published with the Optics Continuum article (Zenodo, Certus Index Spline
    1.1-revised): at a wavelength of the table, the projected n and k are the table's. The profiles they replaced -- 12 nodes
    for SiO2 and Nb2O5, 4 points for Ta2O5 -- were 0.015 low in n for SiO2 and up to 0.055 off for Ta2O5, and the fit then
    settled 18 nm away from the published SiO2 thickness."""
    import certus.spline.spline_presets as presets

    lam = getattr(presets, f"{material.upper()}_PRESET_LAM_NM")
    n_tab = getattr(presets, f"{material.upper()}_PRESET_N")
    k_tab = getattr(presets, f"{material.upper()}_PRESET_K")
    i = int(np.flatnonzero(np.isclose(lam, wavelength_nm))[0])
    _, n, L, _ = project_manual_material_preset(material, np.array([1.0 / wavelength_nm]), d_nm_hint=1700.0)
    assert n[0] == pytest.approx(n_tab[i], abs=1e-12)
    assert np.exp(L[0]) == pytest.approx(k_tab[i], rel=1e-9)
