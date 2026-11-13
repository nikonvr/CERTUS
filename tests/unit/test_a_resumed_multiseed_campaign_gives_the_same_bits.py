"""An interrupted multi-seed campaign, resumed, gives the same bits as one run straight through (U12 B, spec 5.1).

The acceptance criterion of the U12 specification, not a wish. A seed's measure is a pure function of its seed (C2):
what the resume can change is only the ORDER in which measures reach the union. The union is what the final scoring
receives; it must be the same bytes whatever the order and whatever was already on disk.
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

HERE = {"git_commit": "a" * 40, "git_dirty": False, "numba_cache_key": "k" * 12}
SEEDS = (101, 202, 303)


def _measure(seed: int) -> dict:
    """What the probe would write for this seed: a pure function of the seed, as C2 requires."""
    strategies = [
        {
            "score": 0.2 + 0.01 * ((seed * 7 + i) % 13) + 1e-17 * i,
            "crash_rate": 0.01 * (i % 3),
            "n_blocs": 2 + i % 3,
            "blocs": [{"start": i, "end": i + 3 + seed % 5, "wavelength": 500.0 + seed / 7 + i}],
        }
        for i in range(6)
    ]
    strategies.sort(key=lambda s: s["score"])
    return {
        "verdict": "OK",
        "strategies": strategies,
        "config": {"monochromator_resolution_nm": 2.0},
        "provenance": HERE,
    }


def _write(reports: Path, seed: int) -> None:
    (reports / OM._nom_artefact("r75x2", "deep", seed)).write_text(json.dumps(_measure(seed)), encoding="utf-8")


def _campaign(tmp: Path, monkeypatch: pytest.MonkeyPatch, already: tuple[int, ...]) -> bytes:
    reports = tmp / "reports"
    reports.mkdir(parents=True)
    monkeypatch.setattr(OM, "RACINE", tmp)
    monkeypatch.setattr(OM, "_provenance_courante", lambda: dict(HERE))
    monkeypatch.setattr(OM.time, "sleep", lambda s: None)
    for seed in already:
        _write(reports, seed)

    class _Done:
        returncode = 0
        pid = 1

        def poll(self):
            return 0

        def wait(self):
            return 0

    def _launch(py, composant, mode, res, graine, journal, env_sup=None):
        if graine in SEEDS:
            _write(reports, graine)
        p = _Done()
        p._certus_journal = type("F", (), {"close": lambda self: None})()
        return p

    monkeypatch.setattr(OM, "_lancer", _launch)
    OM.main(["r75x2", "--budget", "10h", "--objectif", "meilleur", "--graines", *map(str, SEEDS),
             "--graine-notation", "42", "--slots", "1"])
    (union,) = (tmp / "reports" / "plans").glob("plans_union_r75x2_*.json")
    return union.read_bytes()


@pytest.mark.parametrize("already", [(202,), (303, 101), SEEDS], ids=["one-done", "two-done-out-of-order", "all-done"])
def test_a_resumed_campaign_gives_the_union_of_a_straight_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, already: tuple[int, ...]
) -> None:
    straight = _campaign(tmp_path / "straight", monkeypatch, ())
    resumed = _campaign(tmp_path / "resumed", monkeypatch, already)
    assert json.loads(straight), "control: the union must hold plans, or the comparison proves nothing"
    assert resumed == straight
