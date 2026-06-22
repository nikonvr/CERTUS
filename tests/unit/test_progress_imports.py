import importlib
import pytest

MODULES_TO_CHECK = [
    "certus.core.certus_re_objectives",
    "certus.core.certus_strat_config",
    "certus.metal.certus_metal_common",
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

@pytest.mark.parametrize("module_name", MODULES_TO_CHECK)
def test_progress_snapshot_imports_are_present(module_name):
    """Verify that build_progress_snapshot and StepState are imported in the module."""
    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        pytest.fail(f"Failed to import module {module_name}: {e}")
        
    assert hasattr(mod, "build_progress_snapshot"), f"build_progress_snapshot is missing in {module_name}"
    assert hasattr(mod, "StepState"), f"StepState is missing in {module_name}"
