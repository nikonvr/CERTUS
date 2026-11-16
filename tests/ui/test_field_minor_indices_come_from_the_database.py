"""FIELD computes with the indices of the database, never with invented ones (audit 2026-11-15, L5-m8; D88).

`_get_n_for_material` called `SUBSTRATE_NAMES`, `get_substrate_index` and `get_material_index`, which exist nowhere: the
AttributeError was caught and every computation of FIELD (field profile, R spectrum, thicknesses from the QWOTs) used
constant, non-dispersive indices typed in the code: 2.20 for Nb2O5 where the database has 2.2505 at 1064 nm. D88: a
material absent from the database refuses the computation.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def field(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    yield win
    win.close()


@pytest.mark.parametrize("material", ["H800-Nb2O5", "H800-SiO2", "SiO2", "N-BK7"])
def test_the_index_is_the_one_of_the_database(field, material: str) -> None:
    for wl in (500.0, 1064.0):
        assert field._get_n_for_material(material, wl) == pytest.approx(field.materials_db.get_index(material, wl), abs=0)


def test_the_index_follows_the_dispersion(field) -> None:
    assert field._get_n_for_material("H800-Nb2O5", 450.0) != field._get_n_for_material("H800-Nb2O5", 1064.0)


def test_a_material_absent_from_the_database_refuses_the_computation(field) -> None:
    with pytest.raises(ValueError, match="D88"):
        field._get_n_for_material("Unobtainium", 1064.0)


def test_air_is_one(field) -> None:
    assert field._get_n_for_material("Air", 1064.0) == 1.0
