"""Un resultat porte ce qui l'a produit : le commit, les versions, la plateforme (DAT-01).

Mesure le 2026-09-30 : sur les 1 451 fichiers JSON de `reports/`, AUCUN ne portait le commit, la plateforme ni
les versions de Python, de NumPy ou de Numba (trois nommaient une version). Un resultat que personne ne peut
rattacher au code qui l'a donne ne se rejoue pas, et ne se compare pas d'une version a l'autre.

`certus.core.certus_metrology.provenance()` en dit assez pour relancer ; `scripts/_artefact.avec_provenance` la
met dans le dictionnaire d'un resultat ; les ecrivains de resultats des campagnes et des sondes (les deux
campagnes d'intervalles font a elles seules 1 082 des 1 451 fichiers) et le rapport d'observabilite de STRAT
la portent maintenant.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _artefact import avec_provenance, ecrire_json  # noqa: E402


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "--no-optional-locks", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


@pytest.fixture(autouse=True)
def _ask_git_again():
    from certus.core.certus_metrology import git_state

    git_state.cache_clear()
    yield
    git_state.cache_clear()


# =============================================================================
# The provenance itself
# =============================================================================


def test_the_provenance_says_which_code_and_which_environment() -> None:
    from certus.core.certus_metrology import provenance

    p = provenance()

    assert set(p) >= {
        "certus_version", "git_commit", "git_dirty", "python", "numpy", "scipy", "numba", "platform", "machine",
        "generated_at_utc",
    }
    assert p["python"] == ".".join(map(str, sys.version_info[:3]))
    assert p["numpy"] not in ("", "unknown")
    assert p["numba"] not in ("", "unknown")
    assert p["platform"]
    assert datetime.fromisoformat(p["generated_at_utc"]).tzinfo is not None
    json.dumps(p)  # a report can carry it


def test_the_commit_is_the_one_of_the_checkout() -> None:
    from certus.core.certus_metrology import provenance

    expected = _git("rev-parse", "HEAD")
    if expected is None:
        pytest.skip("no git or no repository here")

    p = provenance()

    assert re.fullmatch(r"[0-9a-f]{40}", p["git_commit"])
    assert p["git_commit"] == expected
    assert isinstance(p["git_dirty"], bool)


def test_a_change_to_a_tracked_file_makes_the_checkout_dirty(tmp_path, monkeypatch) -> None:
    # In a repository of its own, so that no test touches the real one.
    from certus.core import certus_metrology

    if _git("--version") is None:
        pytest.skip("no git here")
    repo = tmp_path / "repo"
    (repo / "certus" / "core").mkdir(parents=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("one\n")
    for args in (["init", "-q"], ["add", "tracked.txt"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    fake_module = repo / "certus" / "core" / "certus_metrology.py"
    fake_module.write_text("")
    monkeypatch.setattr(certus_metrology, "__file__", str(fake_module))

    certus_metrology.git_state.cache_clear()
    clean = certus_metrology.git_state()
    tracked.write_text("two\n")
    certus_metrology.git_state.cache_clear()
    dirty = certus_metrology.git_state()

    assert re.fullmatch(r"[0-9a-f]{40}", clean[0])
    assert clean[1] is False
    assert dirty == (clean[0], True)


def test_a_frozen_build_has_no_repository_and_asks_none(monkeypatch) -> None:
    from certus.core import certus_metrology

    def no_process(*_a, **_k):
        raise AssertionError("a frozen build must not start git")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(certus_metrology.subprocess, "run", no_process)

    assert certus_metrology.provenance()["git_commit"] is None
    assert certus_metrology.provenance()["git_dirty"] is None


def test_no_git_is_no_commit_and_not_an_error(monkeypatch) -> None:
    from certus.core import certus_metrology

    def no_git(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(certus_metrology.subprocess, "run", no_git)

    assert certus_metrology.git_state() == ("", None)
    assert certus_metrology.provenance()["git_commit"] is None


def test_the_run_context_of_the_application_carries_the_commit() -> None:
    from certus.core.certus_metrology import RunContext, RunManifest

    expected = _git("rev-parse", "HEAD")
    context = RunContext.create(app_id="CERTUS_TEST", app_version="test")

    manifest = RunManifest(run_context=context).to_dict()

    assert manifest["git_commit"] == (expected or "")
    assert "git_dirty" in manifest


# =============================================================================
# The writers
# =============================================================================


def test_a_dictionary_receives_its_provenance_and_its_owner_keeps_his_own() -> None:
    mine = {"verdict": "ok", "n": 3}

    written = avec_provenance(mine)

    assert written["verdict"] == "ok" and written["n"] == 3
    assert written["provenance"]["python"] == ".".join(map(str, sys.version_info[:3]))
    assert "provenance" not in mine  # a copy


def test_what_is_not_a_dictionary_or_already_has_one_is_left_alone() -> None:
    plans = [{"a": 1}, {"b": 2}]
    already = {"provenance": {"commit": "chosen by the writer"}, "x": 1}

    assert avec_provenance(plans) is plans
    assert avec_provenance(already) is already


def test_ecrire_json_writes_the_provenance(tmp_path) -> None:
    written = ecrire_json(tmp_path / "result.json", {"verdict": "deposable"})

    data = json.loads(written.read_text(encoding="utf-8"))

    assert data["verdict"] == "deposable"
    assert data["provenance"]["numpy"] not in ("", "unknown")


#: The scripts whose results fill `reports/` (the two campaigns of intervals alone, 1 082 files of 1 451).
RESULT_WRITERS = [
    "campagne_intervalles.py",
    "controle_negatif.py",
    "serie_echelle_r75.py",
    "probe_anchor_noise.py",
    "probe_anchor_noise_pipeline.py",
    "probe_block_wls.py",
    "probe_blocs_vs_plantage.py",
    "probe_dp_vs_truth.py",
    "probe_functional_stability.py",
    "probe_spectral_error.py",
    "probe_tp_admissibilite.py",
    "probe_turning_points.py",
    "probe_resolution_exigee.py",
    "probe_prefixe_optique.py",
    "probe_destructif_dp_top_k.py",
    "profil_monitorabilite.py",
]


@pytest.mark.parametrize("name", RESULT_WRITERS)
def test_the_script_writes_its_result_through_the_provenance(name) -> None:
    tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))

    imported = any(
        isinstance(node, ast.ImportFrom) and node.module == "_artefact" and any(a.name == "avec_provenance" for a in node.names)
        for node in ast.walk(tree)
    )
    dumps = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
    ]
    wrapped = [
        node
        for node in dumps
        if node.args and isinstance(node.args[0], ast.Call) and getattr(node.args[0].func, "id", "") == "avec_provenance"
    ]

    assert imported, f"{name} does not import avec_provenance: its results carry nothing"
    assert wrapped, f"{name} never writes a result through avec_provenance"


def test_the_observability_report_of_strat_carries_the_provenance(tmp_path, monkeypatch) -> None:
    import certus.core.certus_strat_solvers as solvers

    monkeypatch.setattr(solvers, "get_resource_path", lambda name: str(tmp_path))

    solvers._export_phase_a_observability_json({"export_observability_json": True}, {"n": 3})

    [report] = tmp_path.glob("STRAT_observability_*.json")
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["n"] == 3
    assert data["provenance"]["python"] == ".".join(map(str, sys.version_info[:3]))
