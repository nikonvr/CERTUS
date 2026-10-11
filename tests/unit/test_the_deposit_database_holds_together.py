"""The deposit database (`example/database_depots/`): a catalogue that says what each file holds, and files INDEX reads.

Imported on 2026-10-11 by `scripts/importer_base_depots.py` from the single layers measured on the Photon RT. These
tests hold what a user of the database relies on: every entry points to files that exist, every measurement file loads
through the loader INDEX uses and gives the channels and the range the catalogue announces, every raw file is either
read or recorded as a duplicate, and nothing is attributed to a material or a substrate that the name does not state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "example" / "database_depots"
CATALOGUE = json.loads((BASE / "catalogue.json").read_text(encoding="utf-8"))
DEPOTS = CATALOGUE["depots"]


def test_the_catalogue_lists_deposits_under_unique_ids():
    ids = [d["id"] for d in DEPOTS]
    assert ids
    assert len(ids) == len(set(ids))
    assert not CATALOGUE["refus"], CATALOGUE["refus"]


@pytest.mark.parametrize("depot", DEPOTS, ids=lambda d: d["id"])
def test_each_deposit_loads_as_the_catalogue_announces(depot):
    from certus.utils.certus_data import load_spectrum_columns
    from certus.utils.certus_index_utils import analyze_loaded_data

    assert (BASE / depot["brut"]).is_file()
    frame = load_spectrum_columns(str(BASE / depot["fichier"]), column_roles={}).dataframe
    _kind, parsed = analyze_loaded_data(frame)
    modes = {channel["mode"] for channel in depot["voies"]}
    assert (parsed["T"] is not None) == ("T" in modes)
    assert (parsed["R"] is not None) == ("R" in modes)
    wavelengths = parsed["lambda"]
    assert len(wavelengths) == depot["points"]
    assert wavelengths.min() == pytest.approx(depot["lambda_nm"][0])
    assert wavelengths.max() == pytest.approx(depot["lambda_nm"][1])


def test_every_raw_file_is_read_or_recorded_as_a_duplicate():
    read = {d["brut"].split("/", 1)[1] for d in DEPOTS}
    twins = {name.split(" [")[0] for names in CATALOGUE["doublons"].values() for name in names}
    raw = {p.name for p in (BASE / "bruts").iterdir()}
    assert raw <= read | twins, sorted(raw - read - twins)


def test_a_material_or_a_substrate_is_only_what_the_name_states():
    for depot in DEPOTS:
        for key in ("materiau", "substrat"):
            if depot[key] is not None:
                assert depot[key]["source"] == "nom", depot["id"]



def test_a_channel_is_read_in_its_geometry_not_in_the_declared_mode():
    """In manual mode the Photon RT declares "Transmittance" whatever the detector does: 13 such columns of this source are
    reflectances (detector at 16 deg, sample at 8 deg). A detector at 180 deg sees the transmitted beam, one at twice the
    stage angle the reflected one."""
    checked = 0
    for depot in DEPOTS:
        for channel in depot["voies"]:
            detector, stage = channel["detecteur_deg"], channel["angle_deg"]
            if detector is not None and abs(detector - 180.0) < 0.5:
                assert channel["mode"] == "T", depot["id"]
                checked += 1
            elif detector is not None and stage is not None and abs(detector - 2.0 * stage) < 0.5:
                assert channel["mode"] == "R", depot["id"]
                checked += 1
    assert checked == sum(len(depot["voies"]) for depot in DEPOTS)

REFERENCES = json.loads((BASE / "references_index.json").read_text(encoding="utf-8"))["references"]


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: r["nom"])
def test_a_reference_names_deposits_of_one_workbook_on_one_grid(reference):
    """`scripts/bench_base_depots.py` sets the T and R of a reference side by side: they must share their grid."""
    by_id = {d["id"]: d for d in DEPOTS}
    entries = [by_id[depot_id] for depot_id in reference["depots"]]
    assert [e["voies"][0]["mode"] for e in entries] in (["T"], ["R"], ["T", "R"])
    assert len({e["brut"] for e in entries}) == 1
    assert len({(e["points"], tuple(e["lambda_nm"])) for e in entries}) == 1


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: r["nom"])
def test_the_reference_index_is_what_the_index_model_gives_for_its_parameters(reference):
    """The standalone app computed n(633); the functions INDEX fits with must give it back from the same parameters."""
    import numpy as np

    from certus.core.certus_core import HC_EV_NM
    from certus_physics import epsilon1_TL_analytic, epsilon2_TLU_array, epsilon_to_nk

    p = reference["parametres"]
    assert reference["d_nm"] == p["d"]
    energy = np.array([HC_EV_NM / 633.0])
    eps2 = epsilon2_TLU_array(energy, p["Eg"], p["A"], p["E0"], p["C"], p["Eu"])
    eps1 = epsilon1_TL_analytic(energy, p["Eg"], p["A"], p["E0"], p["C"], p["eps_inf"])
    n, _k, _ok = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)
    assert n[0] == pytest.approx(reference["n633"], abs=1e-9)
