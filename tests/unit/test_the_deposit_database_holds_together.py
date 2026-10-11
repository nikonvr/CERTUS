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
