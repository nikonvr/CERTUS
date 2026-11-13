"""A multi-seed campaign at another slit than 2 nm finds its own artefacts, and only them (U12 B).

`scripts/orchestre_multigraine.py` skips every seed that already carries an artefact in `reports/`: that is its
resume. A skipped seed is never recomputed, so an artefact from another configuration would enter the union and the
final scoring as if it had been measured now: a wrong result that looks right (U12 specification, section 3.4).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import orchestre_multigraine as OM  # noqa: E402


@pytest.fixture
def reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    monkeypatch.setattr(OM, "RACINE", tmp_path)
    return d


def _touch(d: Path, name: str) -> Path:
    f = d / name
    f.write_text("{}", encoding="utf-8")
    return f


def test_a_campaign_at_another_slit_does_not_find_the_2_nm_artefact(reports: Path) -> None:
    """The probe names a run at 1 nm `..._res1.json`: a campaign at 1 nm must not take the 2 nm one for its own."""
    _touch(reports, "blocs_vs_plantage_r75x2_deep_s101.json")
    assert OM._resoudre_artefact("r75x2", "deep", 101, res_nm=1.0) is None
    assert OM._resoudre_artefact("r75x2", "deep", 101) is not None, "2 nm stays the default"


def test_a_campaign_at_another_slit_finds_its_own_artefact(reports: Path) -> None:
    mine = _touch(reports, "blocs_vs_plantage_r75x2_deep_s101_res1.json")
    assert OM._resoudre_artefact("r75x2", "deep", 101, res_nm=1.0) == mine
    assert OM._resoudre_artefact("r75x2", "deep", 101) is None, "a 1 nm run is not the 2 nm reference"


def test_the_slit_suffix_follows_the_tag_as_the_probe_writes_it(reports: Path) -> None:
    """The probe writes `_<tag>` then `_res<slit>`: the final scoring at 1 nm must find its artefact."""
    mine = _touch(reports, "blocs_vs_plantage_r75x2_deep_s042_union20261113_res1.json")
    assert OM._resoudre_artefact("r75x2", "deep", 42, tag="union20261113", res_nm=1.0) == mine
    assert OM._nom_artefact("r75x2", "deep", 42, "union20261113", res_nm=1.0) == mine.name
