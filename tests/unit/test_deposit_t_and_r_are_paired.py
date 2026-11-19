"""The transmission and the reflection of one sample, named apart by the operator, are paired (lot 2d, 2026-11-19).

Before: `NbT3` and `NbR3`, `H800-NbT` and `H800-NbR` stayed two entries, and nothing paired them by name
(example/database_depots/README.md). The pairing is read, not stored: one single-channel entry of the same workbook, the
other channel, the same grid, and a sample name that differs by that one letter (T for R) at one place. INDEX loads the
pair side by side only when the operator asks for it (off by default).
"""

from __future__ import annotations

import pytest

from certus.utils.certus_depots_db import load_catalogue, measurement_path, paired_entry, write_side_by_side

DEPOTS = load_catalogue()
BY_ID = {entry["id"]: entry for entry in DEPOTS}


def _pairs() -> set[tuple[str, str]]:
    found = set()
    for entry in DEPOTS:
        partner = paired_entry(entry, DEPOTS)
        if partner is not None:
            found.add(tuple(sorted((entry["id"], partner["id"]))))
    return found


def test_thirteen_samples_have_their_t_and_r_paired() -> None:
    pairs = _pairs()
    assert len(pairs) == 13
    assert ("fab19__nbr3", "fab19__nbt3") in pairs
    assert ("03-03-2026-12-32-54__h800-nbr", "03-03-2026-12-32-54__h800-nbt") in pairs


def test_the_pairing_is_mutual_and_joins_a_t_to_an_r_on_one_grid() -> None:
    for entry in DEPOTS:
        partner = paired_entry(entry, DEPOTS)
        if partner is None:
            continue
        assert paired_entry(partner, DEPOTS) is entry
        assert {entry["voies"][0]["mode"], partner["voies"][0]["mode"]} == {"T", "R"}
        assert entry["brut"] == partner["brut"]
        assert entry["lambda_nm"] == partner["lambda_nm"]
        assert entry["points"] == partner["points"]


def test_a_sample_without_its_other_channel_has_no_pair() -> None:
    lonely = [entry for entry in DEPOTS if paired_entry(entry, DEPOTS) is None]
    assert len(lonely) == len(DEPOTS) - 26


def test_side_by_side_puts_t_then_r_on_the_common_grid(tmp_path) -> None:
    import numpy as np

    t, r = BY_ID["fab19__nbt3"], BY_ID["fab19__nbr3"]
    path = write_side_by_side([r, t], tmp_path / "pair.csv")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "wavelength_nm,T,R"
    data = np.loadtxt(path, delimiter=",", skiprows=1)
    t_data = np.loadtxt(measurement_path(t), delimiter=",", skiprows=1)
    r_data = np.loadtxt(measurement_path(r), delimiter=",", skiprows=1)
    assert np.array_equal(data[:, 0], t_data[:, 0])
    assert np.array_equal(data[:, 1], t_data[:, 1])
    assert np.array_equal(data[:, 2], r_data[:, 1])


def test_side_by_side_refuses_two_grids(tmp_path) -> None:
    t = BY_ID["fab19__nbt3"]
    other = next(e for e in DEPOTS if e["voies"][0]["mode"] == "R" and e["points"] != t["points"])
    with pytest.raises(ValueError, match="grid"):
        write_side_by_side([t, other], tmp_path / "x.csv")
