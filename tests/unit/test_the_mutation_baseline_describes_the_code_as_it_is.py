"""`tests/mutation_baseline.json` describes the code as it is: a baseline that points at a line that moved says nothing.

The pilot of the mutation runner (`scripts/mutation_pilot.py`, S3.6) was played on three modules on 2026-10-01; its result
is committed, with the survivors that were judged equivalent and the reason of each. The run itself takes minutes and
is not part of the suite. What is: this file checks, in a second, that the baseline still describes the modules
it names. If one of them gains or loses a construct that can be mutated, or a judged survivor's line changes, the
baseline is stale: the test fails, and the way out is to rerun the pilot and judge the new survivors, not to edit a number.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads((ROOT / "tests" / "mutation_baseline.json").read_text(encoding="utf-8"))
MODULES = sorted(BASELINE["modules"])


def _load():
    spec = importlib.util.spec_from_file_location("certus_scripts_mutation_pilot_baseline", ROOT / "scripts" / "mutation_pilot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mp = _load()


def _faults(module: str):
    return mp.iter_mutants((ROOT / module).read_text(encoding="utf-8-sig"), module)


@pytest.mark.parametrize("module", MODULES)
def test_the_baseline_names_a_module_that_exists(module):
    assert (ROOT / module).is_file()


@pytest.mark.parametrize("module", MODULES)
def test_the_module_still_offers_the_faults_the_baseline_counted(module):
    posed = len(_faults(module))
    counted = BASELINE["modules"][module]["mutants"]
    assert posed == counted, f"{module} offers {posed} faults, the baseline counted {counted}: rerun scripts/mutation_pilot.py"


@pytest.mark.parametrize("module", MODULES)
def test_the_counts_add_up_and_the_score_is_what_they_say(module):
    numbers = BASELINE["modules"][module]
    assert numbers["mutants"] == numbers["killed"] + numbers["timeout"] + numbers["survived"] + numbers["error"]
    caught, survived = numbers["killed"] + numbers["timeout"], numbers["survived"]
    assert numbers["score"] == pytest.approx(caught / (caught + survived), abs=1e-4)


@pytest.mark.parametrize("module", MODULES)
def test_every_survivor_is_judged_and_none_is_hidden(module):
    judged = [a for a in BASELINE["accepted_survivors"] if a["module"] == module]
    assert len(judged) == BASELINE["modules"][module]["survived"]
    assert all(a["reason"].strip() for a in judged)


def test_every_judged_survivor_is_still_a_fault_the_tool_poses_on_a_line_that_exists():
    posed = {mp.survivor_key({"module": m.module, "text": m.text, "kind": m.kind, "old": m.old, "new": m.new}) for module in MODULES for m in _faults(module)}
    stale = [a for a in BASELINE["accepted_survivors"] if mp.survivor_key(a) not in posed]
    assert not stale, f"survivors whose line changed or went away: {[(a['module'], a['text']) for a in stale]}"


@pytest.mark.parametrize("module", MODULES)
def test_the_tests_of_the_baseline_see_more_than_those_that_came_before(module):
    """`avant` is the score before the tests of the limits; the baseline never records less than it."""
    assert BASELINE["modules"][module]["score"] > BASELINE["avant"][module]["score"]
