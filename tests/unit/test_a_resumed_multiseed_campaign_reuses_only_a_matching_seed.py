"""A resumed multi-seed campaign reuses a seed's artefact only when it measured the same thing (U12 B).

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


def _artefact(reports: Path, seed: int, *, res_nm: float = 2.0, provenance: dict | None) -> Path:
    data = {
        "verdict": "OK",
        "strategies": [{"score": 0.25, "crash_rate": 0.0, "n_blocs": 3, "blocs": []}],
        "config": {"monochromator_resolution_nm": res_nm},
    }
    if provenance is not None:
        data["provenance"] = provenance
    f = reports / OM._nom_artefact("r75x2", "deep", seed, res_nm=res_nm)
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


HERE = {"git_commit": "a" * 40, "git_dirty": False, "numba_cache_key": "k" * 12}


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str], here: dict = HERE) -> list[int]:
    """Run the campaign with a launcher that computes nothing; return the seeds it launched."""
    launched: list[int] = []

    class _Fake:
        returncode = 1
        pid = 1

        def poll(self):
            return 1

        def wait(self):
            return 1

    def _fake(py, composant, mode, res, graine, journal, env_sup=None):
        launched.append(int(graine))
        f = _Fake()
        f._certus_journal = type("F", (), {"close": lambda self: None})()
        return f

    monkeypatch.setattr(OM, "_lancer", _fake)
    monkeypatch.setattr(OM, "_provenance_courante", lambda: dict(here))
    OM.main(["r75x2", "--budget", "10h", "--graines", "101", "--graine-notation", "42", "--slots", "1", *argv])
    return [g for g in launched if g != 42]  # 42 is the final scoring, launched once a seed is known


def test_a_matching_artefact_is_reused(reports: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control: a guard that refuses everything resumes nothing."""
    _artefact(reports, 101, provenance=HERE)
    assert _run(monkeypatch, []) == []


def test_a_seed_measured_at_2_nm_is_measured_again_for_a_1_nm_campaign(
    reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _artefact(reports, 101, provenance=HERE)
    assert _run(monkeypatch, ["--resolution", "1"]) == [101]


def test_an_artefact_of_another_slit_in_its_config_is_refused(
    reports: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Even under the right name, the configuration it records decides (a file renamed by hand)."""
    f = _artefact(reports, 101, provenance=HERE)
    data = json.loads(f.read_text(encoding="utf-8"))
    data["config"]["monochromator_resolution_nm"] = 1.0
    f.write_text(json.dumps(data), encoding="utf-8")
    assert _run(monkeypatch, []) == [101]
    assert "slit" in capsys.readouterr().out


def test_an_artefact_of_other_compiled_kernels_is_refused(
    reports: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    _artefact(reports, 101, provenance={**HERE, "numba_cache_key": "z" * 12})
    assert _run(monkeypatch, []) == [101]
    assert "numba_cache_key" in capsys.readouterr().out


def test_an_artefact_of_another_commit_is_refused_by_default(
    reports: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    _artefact(reports, 101, provenance={**HERE, "git_commit": "b" * 40})
    assert _run(monkeypatch, []) == [101]
    assert "commit" in capsys.readouterr().out


def test_another_commit_is_accepted_on_request_when_the_kernels_are_the_same(
    reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _artefact(reports, 101, provenance={**HERE, "git_commit": "b" * 40})
    assert _run(monkeypatch, ["--reprendre-autre-commit"]) == []


def test_the_request_does_not_cover_other_kernels(reports: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _artefact(reports, 101, provenance={**HERE, "git_commit": "b" * 40, "numba_cache_key": "z" * 12})
    assert _run(monkeypatch, ["--reprendre-autre-commit"]) == [101]


@pytest.mark.parametrize(
    "provenance",
    [None, {**HERE, "git_dirty": True}, {**HERE, "git_commit": None}, {**HERE, "numba_cache_key": None}],
    ids=["no-provenance", "dirty-tree", "unknown-commit", "unknown-kernels"],
)
def test_an_artefact_that_cannot_say_what_produced_it_is_refused(
    reports: Path, monkeypatch: pytest.MonkeyPatch, provenance: dict | None
) -> None:
    _artefact(reports, 101, provenance=provenance)
    assert _run(monkeypatch, ["--reprendre-autre-commit"]) == [101]


def test_this_tree_unable_to_say_its_own_commit_reuses_nothing(
    reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dirty tree or a missing `git`: nothing says the old artefact came from the same code."""
    _artefact(reports, 101, provenance=HERE)
    assert _run(monkeypatch, [], here={**HERE, "git_dirty": True}) == [101]
