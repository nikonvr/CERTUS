"""The "SiO2" substrate of STRAT is fused silica, not a blend of SiO2 layer sheets (audit 2026-11-15, C-L4).

``MergedMaterialDict.__contains__`` answers yes by substring: "SiO2" matched the five SiO2 *layer* sheets of the index
database (H800, Helios, Syrus and two infrared ones), which were merged and served as the substrate, n(550 nm) = 1.48625
instead of the Sellmeier law of fused silica, 1.45991. Every STRAT result on a "SiO2" substrate was computed with it.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_indices_db import _resolve_strat_indices_db_path
from certus.utils.certus_db_helpers import MergedMaterialDict
from certus.utils.certus_strat_db import RobustMaterialDatabase

WLS = (400.0, 550.0, 700.0, 1000.0)


def _malitson(wl_nm: float) -> float:
    """Fused silica, Malitson 1965: written here, not read from CERTUS."""
    x = (wl_nm / 1000.0) ** 2
    return float(
        np.sqrt(
            1
            + 0.6961663 * x / (x - 0.0684043**2)
            + 0.4079426 * x / (x - 0.1162414**2)
            + 0.8974794 * x / (x - 9.896161**2)
        )
    )


@pytest.fixture(scope="module")
def db() -> RobustMaterialDatabase:
    return RobustMaterialDatabase(_resolve_strat_indices_db_path())


def test_the_sio2_substrate_follows_the_sellmeier_law_of_fused_silica(db) -> None:
    assert _malitson(550.0) == pytest.approx(1.45991, abs=1e-5)
    for wl in WLS:
        assert db.get_refractive_index("SiO2", wl).real == pytest.approx(_malitson(wl), abs=1e-5)
    vectorised = db.get_refractive_clues_vectorized("SiO2", np.array(WLS))
    np.testing.assert_allclose(vectorised.real, [_malitson(wl) for wl in WLS], atol=1e-5)
    np.testing.assert_array_equal(vectorised.imag, 0.0)


def test_a_built_in_substrate_name_is_not_a_sheet_by_substring(db) -> None:
    assert "SiO2" not in db.materials
    with pytest.raises(KeyError):
        db.materials["SiO2"]


def test_the_sio2_layer_sheet_keeps_its_own_index(db) -> None:
    sheet = dict.__getitem__(db.materials, "H800-SiO2")
    expected = float(np.interp(550.0, sheet["wl"], sheet["n"]))
    assert expected > 1.48
    assert db.get_refractive_index("H800-SiO2", 550.0).real == expected


def _curve(wl0: float, wl1: float, n: float) -> dict:
    wl = np.linspace(wl0, wl1, 5)
    return {"wl": wl, "n": np.full(5, n), "k": np.zeros(5)}


def test_other_names_still_merge_their_sheets() -> None:
    raw = {"Nb2O5 H800": _curve(400.0, 1000.0, 2.3), "Nb2O5 H800 IR": _curve(1000.0, 2000.0, 2.2)}
    merged = MergedMaterialDict(raw, list(raw), exact_keys=frozenset({"SiO2"}))
    assert "Nb2O5 H800" in merged
    assert merged["Nb2O5 H800"]["wl"][-1] == 2000.0


def test_an_exact_sheet_named_like_a_substrate_is_still_served() -> None:
    raw = {"SiO2": _curve(400.0, 1000.0, 1.46), "H800-SiO2": _curve(400.0, 1000.0, 1.49)}
    merged = MergedMaterialDict(raw, list(raw), exact_keys=frozenset({"SiO2"}))
    assert "SiO2" in merged
    assert merged["SiO2"]["n"][0] == 1.46
