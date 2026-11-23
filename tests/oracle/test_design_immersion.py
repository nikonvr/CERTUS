"""DESIGN in immersion: the air-equivalent problem of `certus.core.certus_design_immersion` has the R and T of the
immersed one.

The configuration of a DESIGN worker is translated once (materials n(c lambda) / c, wavelengths and target bands
divided by c); the kernels, which take the incident medium to be air, then run unchanged with the physical
thicknesses. The R and T they give at the translated wavelengths must equal those that the independent oracle
`tests/oracle/tmm_reference.py::rt_stack_oblique` computes directly in the immersed system at the true wavelengths,
with dispersive materials.
"""

from __future__ import annotations

import numpy as np
import pytest
from tmm_reference import rt_stack_oblique

WLS = np.array([400.0, 450.0, 551.3, 650.0, 700.0])
MATERIALS = {"H": (2.35, 2.22), "M": (1.39, 1.37), "substrate": (1.80, 1.80)}


def _cfg(n_inc_rows: int = 9):
    from certus.physics.certus_opt_tmm import Material
    from certus_physics.structures import ObliqueTarget

    rng = np.random.default_rng(7)
    stack = ["H" if k % 2 == 0 else "M" for k in range(n_inc_rows)]
    d = rng.uniform(5.0, 250.0, n_inc_rows)
    cfg = {
        "mats": {k: Material(*v) for k, v in MATERIALS.items()},
        "wls": WLS.copy(),
        "oblique_mode": True,
        "has_back": False,
        "oblique_tgts": [ObliqueTarget(45.0, "s", 445.0, 455.0, 0.0, 0.0, "T")],
        "tgts": [ObliqueTarget(45.0, "p", 400.0, 700.0, 1.0, 1.0, "T")],
    }
    return cfg, stack, d


@pytest.mark.parametrize("polarization", ["s", "p"])
@pytest.mark.parametrize("angle", [0.0, 30.0, 45.0])
@pytest.mark.parametrize("n_inc", [1.33, 1.52, 1.80])
def test_the_translated_configuration_matches_the_oracle_in_immersion(n_inc, angle, polarization) -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    cfg, stack, d = _cfg()
    imm = immerse_design_cfg(cfg, n_inc)
    wls_eq = imm["wls"]
    n_eq = np.stack([imm["mats"][m].get_nk(wls_eq) for m in stack], axis=1).astype(np.complex128)
    n_sub_eq = imm["mats"]["substrate"].get_nk(wls_eq).astype(np.complex128)
    r, t = calc_spectrum_oblique_vectorized(wls_eq, n_eq, d, n_sub_eq, angle, polarization)

    for i, wl in enumerate(WLS):
        n_true = np.array([cfg["mats"][m].get_nk(np.array([wl]))[0] for m in stack], dtype=np.complex128)
        n_sub = complex(cfg["mats"]["substrate"].get_nk(np.array([wl]))[0])
        r_ref, t_ref = rt_stack_oblique(
            float(wl), n_true, d, angle, polarization == "s", n_inc=complex(n_inc, 0.0), n_sub=n_sub
        )
        assert r[i] == pytest.approx(r_ref, abs=1e-12)
        assert t[i] == pytest.approx(t_ref, abs=1e-12)


def test_an_incident_index_of_one_returns_the_same_configuration() -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg, true_wavelengths

    cfg, _, _ = _cfg()
    assert immerse_design_cfg(cfg, 1.0) is cfg
    assert true_wavelengths(cfg["wls"], 1.0) is cfg["wls"]


def test_the_bands_are_translated_and_the_wavelengths_come_back() -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg, true_wavelengths

    cfg, _, _ = _cfg()
    imm = immerse_design_cfg(cfg, 1.8)
    assert imm["incident_index"] == 1.8
    assert imm["oblique_tgts"][0].lmin == pytest.approx(445.0 / 1.8)
    assert imm["oblique_tgts"][0].lmax == pytest.approx(455.0 / 1.8)
    assert imm["tgts"][0].lmax == pytest.approx(700.0 / 1.8)
    assert cfg["oblique_tgts"][0].lmin == 445.0  # the caller's targets are left alone
    assert true_wavelengths(imm["wls"], 1.8) == pytest.approx(WLS, rel=1e-15)


@pytest.mark.parametrize(
    ("change", "message"),
    [({"oblique_mode": False}, "oblique mode"), ({"has_back": True}, "back side")],
)
def test_immersion_refuses_what_it_cannot_compute(change, message) -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg

    cfg, _, _ = _cfg()
    cfg.update(change)
    with pytest.raises(ValueError, match=message):
        immerse_design_cfg(cfg, 1.8)


@pytest.mark.parametrize("bad", [0.9, float("nan"), float("inf")])
def test_an_index_below_air_or_not_finite_is_refused(bad) -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg

    cfg, _, _ = _cfg()
    with pytest.raises(ValueError, match="incident medium index"):
        immerse_design_cfg(cfg, bad)
