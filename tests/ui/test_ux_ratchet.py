"""Cliquet UX (Étape 1.1) : interdit mécaniquement qu'une métrique UX ne se dégrade.

Pour améliorer un chiffre, régénérer la référence DANS LE MÊME CHANGEMENT.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from scripts.audit_ux_certus import MODULES, _run_worker

BASELINE_1920_PATH = Path(__file__).parent / "ux_baseline.json"
BASELINE_1366_PATH = Path(__file__).parent / "ux_baseline_1366.json"

LOWER_IS_BETTER = (
    "btn_narrow",
    "btn_short",
    "btn_no_tooltip",
    "input_no_tooltip",
    "n_long_labels",
    "marketing_tabs",
    "panel_hscroll_px",
    "left_min_px",
)
HIGHER_IS_BETTER = (
    "tables_sortable",
    "tables_resizable",
    "n_shortcuts",
    "plot_pct",
)


def _load_baseline(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return {r["app"]: r for r in rows}


BASELINE_1920 = _load_baseline(BASELINE_1920_PATH)
BASELINE_1366 = _load_baseline(BASELINE_1366_PATH)


@pytest.mark.parametrize("app_name", list(MODULES.keys()))
@pytest.mark.parametrize(
    "width,height,baseline_dict",
    [
        (1920, 1080, BASELINE_1920),
        (1366, 768, BASELINE_1366),
    ],
    ids=["1920x1080", "1366x768"],
)
def test_no_ux_metric_ever_gets_worse(
    app_name: str, width: int, height: int, baseline_dict: dict[str, dict]
) -> None:
    """A UX ratchet: metrics may improve, never degrade.

    To improve a figure, regenerate the baseline IN THE SAME CHANGE and say so.
    An unexplained baseline update is the thing this test exists to prevent.
    """
    baseline = baseline_dict[app_name]
    current = _run_worker(app_name, width, height)

    assert "ERROR" not in current, f"Audit failed for {app_name}: {current.get('ERROR')}"

    # Configuration integrity checks:
    assert current["font_family"] == baseline["font_family"], (
        f"Font family changed for {app_name}: {current['font_family']} != {baseline['font_family']}"
    )
    assert current["qpa_platform"] == baseline["qpa_platform"], (
        f"QPA platform changed for {app_name}: {current['qpa_platform']} != {baseline['qpa_platform']}"
    )
    assert current["window"] == baseline["window"], (
        f"Window size changed for {app_name}: {current['window']} != {baseline['window']}"
    )

    regressions = []

    for k in LOWER_IS_BETTER:
        if k in baseline and k in current and baseline[k] is not None and current[k] is not None:
            base_v = float(baseline[k])
            curr_v = float(current[k])
            if curr_v > base_v:
                regressions.append(f"{k}: {curr_v} > {base_v} (baseline)")

    for k in HIGHER_IS_BETTER:
        if k in baseline and k in current and baseline[k] is not None and current[k] is not None:
            base_v = float(baseline[k])
            curr_v = float(current[k])
            if curr_v < base_v:
                regressions.append(f"{k}: {curr_v} < {base_v} (baseline)")

    assert not regressions, (
        f"UX regression(s) detected for {app_name} @ {current['window']}!\n"
        + "\n".join(f"  - {r}" for r in regressions)
    )
