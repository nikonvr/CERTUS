from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_release_workflow_runs_critical_guardrails() -> None:
    repo = Path(__file__).resolve().parents[2]
    workflow = repo / ".github" / "workflows" / "release-windows.yml"
    assert workflow.exists(), "Workflow release-windows.yml manquant"
    text = workflow.read_text(encoding="utf-8")

    required_tokens = [
        "tests/unit/test_seed_contract_global.py",
        "tests/unit/test_certus_services.py",
        "tests/unit/test_release_guardrails.py",
        "python tools/release_checks.py",
        "python tools/release_checks.py --check-frozen",
        "python tools/release_checks.py --check-frozen-run",
        "./tools/smoke_release.ps1",
    ]
    missing = [tok for tok in required_tokens if tok not in text]
    assert not missing, "Guardrails non branchés dans le workflow: " + ", ".join(missing)


@pytest.mark.unit
def test_critical_guardrail_files_exist() -> None:
    repo = Path(__file__).resolve().parents[2]
    required_files = [
        repo / "tests" / "unit" / "test_seed_contract_global.py",
        repo / "tests" / "unit" / "test_certus_services.py",
        repo / "tools" / "release_checks.py",
        repo / "tools" / "smoke_release.ps1",
    ]
    missing = [str(p.relative_to(repo)) for p in required_files if not p.exists()]
    assert not missing, "Fichiers garde-fou manquants: " + ", ".join(missing)

