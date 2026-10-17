"""CERTUS has ONE sapphire index, everywhere: the Sellmeier law of id 3 (ordinary ray, Malitson and Dodge).

Found 2026-10-12: a second index, "Sapphire Fresnel", lived in the STRAT database (a Sellmeier set fitted to an index deduced from the
reflectance of the bare plate: n lower than the true one by 0.0077 at 1 um) and was offered to the user by the FIELD and METAL lists.
In METAL it was worse: the label had no Sellmeier id, so the substrate silently became N-BK7. Every name, every resolver and the data
file now give the same n(lambda).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
LAM = np.array([250.0, 400.0, 633.0, 1000.0, 1550.0, 3000.0, 5000.0])
NAMES = ["Sapphire", "Sapphire (Al2O3)", "sapphire (FR)", "Sapphire Fresnel", "Al2O3", "saphir"]


def _ref():
    from certus.core.certus_core import SELLMEIER_COEFFS_BY_ID

    return np.asarray(SELLMEIER_COEFFS_BY_ID[3], dtype=float)


def _n(c, lam):
    w2 = (lam / 1000.0) ** 2
    return np.sqrt(1 + c[0] * w2 / (w2 - c[1]) + c[2] * w2 / (w2 - c[3]) + c[4] * w2 / (w2 - c[5]))


@pytest.mark.parametrize("name", NAMES)
def test_every_sapphire_name_has_the_sellmeier_id_3(name) -> None:
    from certus.core.certus_substrate_db import substrate_sellmeier_coeffs, substrate_sellmeier_id

    assert substrate_sellmeier_id(name) == 3
    assert np.allclose(substrate_sellmeier_coeffs(name), _ref(), rtol=0, atol=0)


@pytest.mark.parametrize("name", ["Sapphire (Al2O3)", "Sapphire (FR)", "Sapphire Fresnel"])
def test_the_strat_database_has_no_other_sapphire(name) -> None:
    from certus.utils.certus_strat_db import RobustMaterialDatabase

    assert np.allclose(RobustMaterialDatabase.SELLMEIER_COEFFS[name], _ref(), rtol=0, atol=0)


def test_the_user_is_offered_one_sapphire() -> None:
    from certus.core.certus_substrate_db import SUBSTRATE_CHOICES

    assert [c for c in SUBSTRATE_CHOICES if "sapph" in c.lower()] == ["Sapphire (Al2O3)"]


def test_every_resolver_of_the_substrate_index_agrees() -> None:
    from certus.core.certus_substrate_sellmeier import _sellmeier_3term_standard_eval
    from certus.utils.certus_index_utils import _get_substrate_n_array_index, _get_substrate_n_array_spline
    from certus_physics import get_n_substrate_array_by_id

    expected = _n(_ref(), LAM)
    for got in (get_n_substrate_array_by_id(3, LAM), _get_substrate_n_array_index(3, LAM), _get_substrate_n_array_spline(3, LAM),
                _sellmeier_3term_standard_eval(_ref(), LAM / 1000.0)):
        assert np.allclose(np.asarray(got, dtype=float), expected, rtol=1e-12, atol=0)


def test_the_data_file_and_the_code_give_the_same_index() -> None:
    """Two writings of the same published law: the file squares roots of more digits (C3 = 325.01883, the code 18.028251**2 = 325.01783).
    Measured 2026-10-12: n differs by 4.6e-7 at most (5 um). Equal to 1e-6, not to the bit: aligning them would change the locked hash
    of the file and the copy of the standalone application for nothing physical."""
    data = np.asarray(json.loads((ROOT / "data" / "materials_v1.json").read_text(encoding="utf-8"))["sellmeier_coeffs_by_id"]["3"], dtype=float)

    assert np.allclose(_n(data, LAM), _n(_ref(), LAM), rtol=0, atol=1e-6)


def test_no_source_defines_another_sapphire_law() -> None:
    """The false set had B1 = 1.4155 and B3 = 3.2352; a law is recognised by its literals, a tuple of six numbers has no name."""
    hits = []
    for folder in ("certus", "certus_physics"):
        for f in (ROOT / folder).rglob("*.py"):
            text = f.read_text(encoding="utf-8", errors="replace")
            if "226.57863" in text or "1.4155, 0.00904" in text:
                hits.append(str(f.relative_to(ROOT)))
    assert not hits, hits
