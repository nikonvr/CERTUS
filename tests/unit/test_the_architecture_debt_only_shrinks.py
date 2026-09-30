"""The architecture debt is a list, and the list only shrinks.

Four kinds of debt are named in tests/architecture_debt.json, each measured by scripts/metrics.py:

* `aretes_montantes`: an import, at module level, of a higher layer by a lower one. The layers (`COUCHES`) run
  domain < physics < core = utils < metal = spline < workers < ui. The audit of 2026-09-29 counted 47.
* `cycles`: modules that cannot be imported one without the others, at run time. The audit counted 4 (8 with the imports
  that only a type checker reads).
* `fonctions_longues` (over 300 lines), `fonctions_complexes` (complexity over 60): 52 and 20 at the audit.
* `fichiers_longs` (over 1 500 lines): 23.

A NEW entry fails the test, and so does one that has grown; an entry that was paid (or whose measure went down) must be
corrected in the same commit, so the gain is locked in and cannot come back unnoticed. `python scripts/metrics.py
--dette tests/architecture_debt.json` writes the file as it should be.

Edges and functions are named, not counted: swapping an old edge for a new one, or splitting a function while a
neighbour grows, leaves a count where it was, and only the names see it. Function-level imports are not counted (they run
later, they are the usual remedy), and neither, for the cycles, are those under `if TYPE_CHECKING:` (they never run, and
they are the standard way to break a cycle: certus_ui_utils.py documents its own). The layering still sees them.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEBT = json.loads((ROOT / "tests" / "architecture_debt.json").read_text(encoding="utf-8"))


def _metrics():
    spec = importlib.util.spec_from_file_location("certus_scripts_metrics_for_debt", ROOT / "scripts" / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


metrics = _metrics()
MEASURED = metrics.dette(metrics.sources_certus(ROOT))

REGENERATE = "python scripts/metrics.py --dette tests/architecture_debt.json"
CEILINGS = {
    "fonctions_longues": "lines (a function over 300 lines: extract named pieces, as the plan does)",
    "fonctions_complexes": "complexity (over 60: split the branches into named functions)",
    "fichiers_longs": "lines (a file over 1 500 lines: split it by responsibility)",
}


# =============================================================================
# Edges and cycles: the set is exact
# =============================================================================


def test_no_new_import_breaks_the_layering() -> None:
    new = sorted(set(MEASURED["aretes_montantes"]) - set(DEBT["aretes_montantes"]))

    assert not new, (
        "a lower layer now imports a higher one at module level. Import it inside the function that needs it, or move "
        f"what it needs to the lower layer (certus/domain/constants.py did that for the physics): {new}"
    )


def test_a_paid_edge_leaves_the_list() -> None:
    paid = sorted(set(DEBT["aretes_montantes"]) - set(MEASURED["aretes_montantes"]))

    assert not paid, f"these edges no longer exist: remove them from tests/architecture_debt.json ({REGENERATE}): {paid}"


def test_no_new_import_cycle() -> None:
    listed = {tuple(c) for c in DEBT["cycles"]}
    new = sorted({tuple(c) for c in MEASURED["cycles"]} - listed)

    assert not new, (
        "modules that now import one another when they are imported (a cycle). Break it with an import inside the "
        f"function that needs it, or under `if TYPE_CHECKING:` when only an annotation needs it: {new}"
    )


def test_a_broken_cycle_leaves_the_list() -> None:
    listed = {tuple(c) for c in DEBT["cycles"]}
    paid = sorted(listed - {tuple(c) for c in MEASURED["cycles"]})

    assert not paid, (
        "these cycles are gone, or changed members (a smaller cycle is a new entry, and the old one goes): "
        f"update tests/architecture_debt.json ({REGENERATE}): {paid}"
    )


# =============================================================================
# Sizes: a ceiling per offender
# =============================================================================


@pytest.mark.parametrize("section", CEILINGS)
def test_no_new_offender_joins_the_list(section) -> None:
    new = {name: size for name, size in MEASURED[section].items() if name not in DEBT[section]}

    assert not new, f"new entries in `{section}`, measured in {CEILINGS[section]}. Split them before they are committed: {new}"


@pytest.mark.parametrize("section", CEILINGS)
def test_no_offender_has_grown(section) -> None:
    grown = {
        name: f"{DEBT[section][name]} -> {size}" for name, size in MEASURED[section].items() if size > DEBT[section].get(name, size)
    }

    assert not grown, f"`{section}` grew, in {CEILINGS[section]}: {grown}"


@pytest.mark.parametrize("section", CEILINGS)
def test_an_offender_that_was_paid_leaves_the_list(section) -> None:
    paid = sorted(set(DEBT[section]) - set(MEASURED[section]))

    assert not paid, f"under the threshold or gone: remove them from `{section}` ({REGENERATE}): {paid}"


@pytest.mark.parametrize("section", CEILINGS)
def test_a_reduced_offender_lowers_its_ceiling(section) -> None:
    lowered = {
        name: f"{DEBT[section][name]} -> {size}" for name, size in MEASURED[section].items() if size < DEBT[section].get(name, size)
    }

    assert not lowered, (
        f"`{section}` went down: write the new ceilings in the same commit, so the gain stays ({REGENERATE}): {lowered}"
    )
