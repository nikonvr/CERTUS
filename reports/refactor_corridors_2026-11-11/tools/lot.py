"""Corridor refactoring: the control lot (LOT of REFACTOR_PLAN.md, section 3), run after the main test of each sub-phase.

    python reports/refactor_corridors_2026-11-11/tools/lot.py [more test files ...]

Runs, in one pytest call, the test files of the lot and those the finished phases created. Run it from the root of the
tree, alone: nothing else at the same time.
"""

from __future__ import annotations

import subprocess
import sys

U = "tests/unit/"
LOT = [
    U + "test_the_corridors_split_keeps_every_name_and_the_layering_where_it_was.py",
    U + "test_gui_smoke.py",
    U + "test_self_attributes_are_defined.py",
    U + "test_project_imports_resolve.py",
    U + "test_the_architecture_debt_only_shrinks.py",
    U + "test_a_module_that_was_in_an_import_cycle_imports_first_and_alone.py",
    U + "test_mwir_gui_flow.py",
    U + "test_post_opt_option_unlock.py",
    "tests/integration/test_suite_ui_instantiation.py",
    U + "test_certus_is_written_in_english.py",
    U + "test_tests_destroy_the_windows_they_build.py",
    # created by the phases of the refactoring
    U + "test_refactor_guard_compares_two_class_surfaces.py",
    U + "test_the_corridor_mixins_declare_what_they_read_on_the_window.py",
    U + "test_no_module_shadows_the_standard_library.py",
    U + "test_the_index_spline_shared_names_have_one_definition.py",
    U + "test_the_corridor_slices_hold_the_methods_they_were_given.py",
    U + "test_spectral_knot_markers.py",
]

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", *LOT, *sys.argv[1:], "-q", "--no-cov"]))
