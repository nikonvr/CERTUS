"""`certus_strat_robustness.py` was split into a facade and eight modules (audit v2, plan S5.2); nothing that imported from it may notice.

It held 3 482 lines, three functions over 300 lines, and sat in the import cycle of the strat modules (tests/architecture_debt.json).
The code of each moved function is the SAME to the AST (the splitting tool compared them one by one before writing), so what can go wrong
is the wiring, and that is what this file pins:

* every name that the old module defined is still an attribute of it, and IS the object the new module defines (a patch, a pickle by
  reference and `from certus.core.certus_strat_robustness import x` all go through there);
* the functions that look up the names the tests patch (`_test_strategy_robustness_task`, `_calculate_strategy_spectral_resolution`,
  `get_safe_worker_count`, `calculate_RT_vectorized_real_HL`) are still DEFINED in the facade: a module that imports such a name binds it
  once and never sees the patch;
* none of the new modules imports a module of the strat cycle at module level (they do it inside the function that needs it), else
  the cycle grows by eight modules and the ratchet of the architecture debt would see a new cycle;
* the task a worker runs is found again by its qualified name in a fresh process.
"""

from __future__ import annotations

import ast
import importlib
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "certus" / "core"
FACADE = "certus.core.certus_strat_robustness"
PARTS = sorted(p.stem for p in CORE.glob("certus_strat_robustness_*.py"))

#: The modules of the import cycle of the strat code (the one entry of `cycles` in tests/architecture_debt.json).
CYCLE = {
    "certus.core.certus_strat_config",
    "certus.core.certus_strat_consensus",
    "certus.core.certus_strat_core",
    "certus.core.certus_strat_objectives",
    "certus.core.certus_strat_pipeline",
    "certus.core.certus_strat_ranking",
    "certus.core.certus_strat_robustness",
    "certus.core.certus_strat_solvers",
    "certus.core.certus_strat_utils",
    "certus.utils.certus_strat_service",
}

#: Looked up in the module namespace by the tests that patch them (tests/unit/test_certus_strat_coherence.py): these functions stay put.
LOOK_UP_IN_THE_FACADE = (
    "_execute_robustness_tasks",
    "run_final_simulation_block",
    "_prepare_robustness_nominal_optics",
    "_expand_with_resolution_variants",
)


#: Module globals that a function REBINDS (`global x`): they live in the part and the facade holds no copy (an immutable copy goes stale).
REBOUND_FLAGS = ("_SLIT_PHASE_A_WARNED",)


def top_level_names(path: Path) -> list[str]:
    """What a module DEFINES at its top level: functions, classes, assigned names (not its imports)."""
    names = []
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                names += [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
    return names


def test_the_split_has_the_eight_parts_the_facade_names():
    assert PARTS == [
        "certus_strat_robustness_diagnostics",
        "certus_strat_robustness_gate",
        "certus_strat_robustness_noise",
        "certus_strat_robustness_rate",
        "certus_strat_robustness_results",
        "certus_strat_robustness_slit",
        "certus_strat_robustness_task",
        "certus_strat_robustness_wrappers",
    ]


@pytest.mark.parametrize("part", PARTS)
def test_every_name_that_a_part_defines_is_the_same_object_in_the_facade(part):
    module = importlib.import_module(f"certus.core.{part}")
    facade = importlib.import_module(FACADE)
    defined = top_level_names(CORE / f"{part}.py")
    assert defined, f"{part} defines nothing"
    for name in defined:
        if name in REBOUND_FLAGS:
            continue  # tested below: the facade must NOT hold a copy of a flag that its function rebinds
        assert hasattr(facade, name), f"{FACADE}.{name} is gone (defined in {part})"
        mine, theirs = getattr(module, name), getattr(facade, name)
        assert mine is theirs or (isinstance(mine, (int, float, str, tuple, bool)) and mine == theirs), (part, name)


def test_a_flag_that_a_function_rebinds_has_no_stale_copy_in_the_facade():
    """`phase_a_slit_profiles` writes `global _SLIT_PHASE_A_WARNED`: a copy in the facade would show the value of the import, forever."""
    facade = importlib.import_module(FACADE)
    slit = importlib.import_module("certus.core.certus_strat_robustness_slit")
    for name in REBOUND_FLAGS:
        assert hasattr(slit, name)
        assert not hasattr(facade, name), f"{FACADE}.{name} would be a stale copy"


def test_a_mutable_cache_is_one_dictionary_for_the_part_and_the_facade():
    """A cache that was a module global must not become two: a copy in the facade would be filled by nobody."""
    facade = importlib.import_module(FACADE)
    noise = importlib.import_module("certus.core.certus_strat_robustness_noise")
    slit = importlib.import_module("certus.core.certus_strat_robustness_slit")
    assert facade._SOBOL_NOISE_CACHE is noise._SOBOL_NOISE_CACHE
    assert facade._SLIT_PROFILE_CACHE is slit._SLIT_PROFILE_CACHE


def test_the_functions_that_look_up_the_patched_names_are_defined_in_the_facade():
    facade = importlib.import_module(FACADE)
    for name in LOOK_UP_IN_THE_FACADE:
        assert getattr(facade, name).__module__ == FACADE, f"{name} left the facade: a patch of the facade would no longer reach it"


def test_the_patched_names_are_read_from_the_facade_namespace():
    """The four names are free variables of those functions (module globals), not imported inside them."""
    tree = ast.parse((CORE / "certus_strat_robustness.py").read_text(encoding="utf-8-sig"))
    wanted = {
        "_execute_robustness_tasks": {"_test_strategy_robustness_task", "_calculate_strategy_spectral_resolution"},
        "run_final_simulation_block": {"get_safe_worker_count", "_test_strategy_robustness_task"},
        "_prepare_robustness_nominal_optics": {"calculate_RT_vectorized_real_HL"},
        "_expand_with_resolution_variants": {"_calculate_strategy_spectral_resolution"},
    }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            read = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            assert wanted.pop(node.name) <= read, node.name
            local_imports = {a.asname or a.name for n in ast.walk(node) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
            assert not local_imports & {"_test_strategy_robustness_task", "_calculate_strategy_spectral_resolution"}, node.name
    assert not wanted, f"not found in the facade: {sorted(wanted)}"


@pytest.mark.parametrize("part", PARTS)
def test_no_part_imports_a_module_of_the_strat_cycle_at_module_level(part):
    tree = ast.parse((CORE / f"{part}.py").read_text(encoding="utf-8-sig"))
    offenders = [
        (node.module, node.lineno) for node in tree.body if isinstance(node, ast.ImportFrom) and node.module in CYCLE
    ] + [(a.name, node.lineno) for node in tree.body if isinstance(node, ast.Import) for a in node.names if a.name in CYCLE]
    assert not offenders, f"{part} joins the import cycle (import it inside the function that needs it): {offenders}"


def test_a_part_does_not_import_the_facade():
    for part in PARTS:
        text = (CORE / f"{part}.py").read_text(encoding="utf-8-sig")
        assert "from certus.core.certus_strat_robustness import" not in text, part
        assert "import certus.core.certus_strat_robustness\n" not in text, part


def test_the_task_of_a_worker_is_pickled_by_its_qualified_name_and_found_again():
    facade = importlib.import_module(FACADE)
    task = facade._test_strategy_robustness_task
    assert task.__module__ == "certus.core.certus_strat_robustness_task"
    assert pickle.loads(pickle.dumps(task)) is task


def test_a_fresh_interpreter_finds_the_task_and_the_facade_without_the_test_session():
    code = (
        "import pickle, sys;"
        "from certus.core.certus_strat_robustness import _test_strategy_robustness_task as t, run_final_simulation_block as r;"
        "assert pickle.loads(pickle.dumps(t)) is t;"
        "assert t.__module__.endswith('_task') and r.__module__ == 'certus.core.certus_strat_robustness';"
        "sys.exit(0)"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-800:]
