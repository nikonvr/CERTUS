"""Garde-fou d'intégrité du squelette d'interface (Étape 1.2).

Vérifie qu'aucun contrôle interactif ne disparaît lors des refactorings.
Les ajouts de contrôles sont permis (enrichissement) ; les suppressions
nécessitent une mise à jour explicite de la référence ux_skeleton.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from scripts.audit_ux_certus import MODULES, _run_worker

SKELETON_BASELINE_PATH = Path(__file__).parent / "ux_skeleton.json"


def _load_skeleton_baseline() -> dict[str, list[str]]:
    with open(SKELETON_BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


SKELETON_BASELINE = _load_skeleton_baseline()


@pytest.mark.parametrize("app_name", list(MODULES.keys()))
def test_no_interactive_control_disappears_from_skeleton(app_name: str) -> None:
    """Every control recorded in the baseline must remain present.

    Additions are allowed; removals require updating ux_skeleton.json in the same commit.
    """
    baseline_controls = set(SKELETON_BASELINE[app_name])
    row = _run_worker(app_name, 1920, 1080)
    assert "ERROR" not in row, f"Audit worker failed for {app_name}: {row.get('ERROR')}"

    current_controls = set(row.get("skeleton", []))
    missing = baseline_controls - current_controls

    # Report how the measurement went, not just its verdict. A window that was
    # still building reports a stable-looking count that is simply short, and the
    # bare "missing control" wording sent a reader hunting a code regression that
    # did not exist (2026-09-04, CERTUS_DESIGN: fails inside the full suite,
    # matches the baseline exactly when the same file runs alone).
    assert not missing, (
        f"Missing control(s) detected in {app_name} skeleton:\n"
        + "\n".join(f"  - {c}" for c in sorted(missing))
        + f"\n  [harness] stable={row.get('skeleton_stable')} "
        f"settle={row.get('skeleton_settle_s')}s "
        f"controls={len(current_controls)}/{len(baseline_controls)} "
        f"window={row.get('window')} font={row.get('font_family')}@{row.get('font_point')}"
    )
