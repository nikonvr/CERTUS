"""The modules that report progress through the shared tracker can resolve its two names.

build_progress_snapshot and StepState live in certus.utils.certus_progress_tracker. A module
whose code uses them must import them. The check used to demand the names in every listed
module, used or not: it kept a dead import alive in certus_metal_common, which uses neither
(found on 2026-09-28 while removing unused imports, R9).
"""

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("build_progress_snapshot", "StepState")

MODULES_TO_CHECK = [
    "certus.core.certus_re_objectives",
    "certus.core.certus_strat_config",
    "certus.spline.certus_index_spline_corridors",
    "certus.spline.certus_index_spline_execution",
    "certus.spline.certus_index_spline_settings",
    "certus.ui.certus_index_spline_manualmesh_mixin",
    "certus.workers.certus_design_workers_needle_strat",
    "certus.workers.certus_design_workers_strat",
    "certus.workers.certus_index_workers_ir_strat",
    "certus.workers.certus_index_workers_opt_strat",
    "certus.workers.certus_re_workers_context",
    "certus.workers.certus_strat_workers_pipeline",
]


def _used_names(module_name: str) -> set[str]:
    path = ROOT / (module_name.replace(".", "/") + ".py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


@pytest.mark.parametrize("module_name", MODULES_TO_CHECK)
def test_progress_snapshot_imports_are_present(module_name):
    """Every listed module uses both names, and can resolve them."""
    mod = importlib.import_module(module_name)
    used = _used_names(module_name)
    for name in NAMES:
        assert name in used, f"{module_name} no longer uses {name}: take it off the list"
        assert hasattr(mod, name), f"{name} is used but missing in {module_name}"
