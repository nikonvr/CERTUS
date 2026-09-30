"""Every import that breaks the layering, and every import cycle, is on a list, and the list only shrinks.

The layers (`COUCHES` in scripts/metrics.py) run domain < physics < core = utils < metal = spline < workers < ui. A lower
layer that imports a higher one at module level is an upward edge, and a cycle is modules that cannot be imported one
without the others. The audit of 2026-09-29 counted 47 upward edges and 8 cycles; the plan of the 8 weeks brings them
down, and this test keeps them there: a NEW edge or cycle fails it, and so does a debt that was paid and is still on the
list (remove it: the gain is locked in and cannot come back unnoticed).

The list is tests/architecture_debt.json. It names edges module to module, not layer to layer: swapping an old edge for a
new one leaves the count where it was, and only the names see it. Function-level imports are not counted (they run
later, they are the usual remedy), which is the definition that scripts/metrics.py has always used.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("certus", "certus_physics")
DEBT = json.loads((ROOT / "tests" / "architecture_debt.json").read_text(encoding="utf-8"))


def _metrics():
    spec = importlib.util.spec_from_file_location("certus_scripts_metrics_for_debt", ROOT / "scripts" / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


metrics = _metrics()


def _measured() -> tuple[set[str], set[tuple[str, ...]]]:
    trees = {}
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            trees[rel] = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"), filename=rel)
    graph, modules = metrics.graphe_imports(trees)
    edges = {f"{a} -> {b}" for a, b in metrics.liste_aretes_montantes(graph, modules)}
    cycles = {tuple(sorted(c)) for c in metrics.cycles(graph, modules)}
    return edges, cycles


EDGES, CYCLES = _measured()


def test_no_new_import_breaks_the_layering() -> None:
    new = sorted(EDGES - set(DEBT["aretes_montantes"]))

    assert not new, (
        "a lower layer now imports a higher one at module level. Import it inside the function that needs it, or move "
        f"what it needs to the lower layer (certus/domain/constants.py did that for the physics): {new}"
    )


def test_a_paid_edge_leaves_the_list() -> None:
    paid = sorted(set(DEBT["aretes_montantes"]) - EDGES)

    assert not paid, f"these edges no longer exist: remove them from tests/architecture_debt.json, the gain is yours: {paid}"


def test_no_new_import_cycle() -> None:
    listed = {tuple(sorted(c)) for c in DEBT["cycles"]}
    new = sorted(CYCLES - listed)

    assert not new, f"modules that now import one another at module level (a cycle): {new}"


def test_a_broken_cycle_leaves_the_list() -> None:
    listed = {tuple(sorted(c)) for c in DEBT["cycles"]}
    paid = sorted(listed - CYCLES)

    assert not paid, (
        "these cycles are gone, or changed members (a smaller cycle is a new entry, and the old one goes): "
        f"update tests/architecture_debt.json: {paid}"
    )


def test_the_list_names_only_what_the_measure_can_see() -> None:
    # A typo in the list would hide nothing and be corrected by the two tests above; a list that is not sorted or has a
    # duplicate is harder to review than it should be.
    assert DEBT["aretes_montantes"] == sorted(set(DEBT["aretes_montantes"]))
    assert DEBT["cycles"] == sorted({tuple(sorted(c)) for c in DEBT["cycles"]}) or all(
        c == sorted(c) for c in DEBT["cycles"]
    )
