"""GUI smoke tests: verify import chains, class instantiation, and report generation.

These tests run headless (no display required) and verify structural integrity
of the GUI modules after refactoring.

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠  NUMBA_DISABLE_JIT : cette variable d'environnement est NÉCESSAIRE ici
   pour tester les imports GUI sans déclencher la compilation JIT (qui peut
   échouer sur Python 3.14 / certaines CI).

   RÈGLES IMPÉRATIVES :
   1. NE JAMAIS utiliser  os.environ["NUMBA_DISABLE_JIT"] = "1"  au niveau
      module — cela contamine TOUS les tests suivants dans le processus,
      y compris les tests physiques qui DÉPENDENT du JIT.
   2. Utiliser UNIQUEMENT la fixture _disable_numba_jit() ci-dessous, qui
      sauvegarde et restaure la variable après exécution du module.
   3. Si un nouveau test de ce fichier échoue de manière non déterministe
      avec des erreurs Numba : vérifier si un autre module a importé
      _certus_physics_impl AVANT que la fixture ne soit active.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import os
import sys
import importlib
import tempfile
import logging

import numpy as np
import pandas as pd
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE — Isolation JIT (module-scoped, auto-restauration)
# ═══════════════════════════════════════════════════════════════════════════════
# PARE-FEU : NE PAS remplacer par un os.environ au niveau module.
#            Voir docstring du module pour les raisons.

@pytest.fixture(autouse=True, scope="module")
def _disable_numba_jit():
    """Disable Numba JIT for deterministic import-chain testing (scoped to this module).

    Saves the previous value and restores it on teardown so that subsequent
    test modules (physics kernels, performance benchmarks) run with JIT enabled.
    """
    _prev = os.environ.get("NUMBA_DISABLE_JIT")
    os.environ["NUMBA_DISABLE_JIT"] = "1"
    yield
    # ── Restauration : critique pour ne pas contaminer les tests suivants ──
    if _prev is None:
        os.environ.pop("NUMBA_DISABLE_JIT", None)
    else:
        os.environ["NUMBA_DISABLE_JIT"] = _prev


# ═══════════════════════════════════════════════════════════════════════════════
# §1  IMPORT CHAIN TESTS — verify all modules import without error
# ═══════════════════════════════════════════════════════════════════════════════

_CORE_MODULES = [
    "certus.core.certus_core",
    "certus.utils.certus_data",
    "certus_physics",
    "certus.spline.spline_pipeline",
    "certus.workers.certus_re_workers",
    "certus.spline.spline_profile_corridors",
    "certus.utils.certus_spline_report",
    "certus.spline.spline_objective",
    "certus.spline.certus_index_spline_core",
    "certus.utils.certus_index_utils",
]

_GUI_MODULES = [
    "certus_ui",
    "CERTUS_INDEX_SPLINE",
    "CERTUS_DESIGN",
    "CERTUS_INDEX",
    "CERTUS_STRAT",
    "CERTUS_RE",
]


@pytest.mark.parametrize("module_name", _CORE_MODULES)
def test_core_module_import(module_name: str) -> None:
    """Core (non-GUI) modules must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize("module_name", _GUI_MODULES)
def test_gui_module_syntax(module_name: str) -> None:
    """GUI modules must at least compile (py_compile) without syntax error."""
    import py_compile

    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        pytest.skip(f"Module {module_name} not found in path")
    py_compile.compile(spec.origin, doraise=True)


# ═══════════════════════════════════════════════════════════════════════════════
# §2  SplineReportBuilder — extracted module coherence
# ═══════════════════════════════════════════════════════════════════════════════


def test_spline_report_context_fields() -> None:
    """SplineReportContext dataclass must have all expected fields."""
    from certus.utils.certus_spline_report import SplineReportContext

    expected = {
        "result",
        "df",
        "spectrum_path",
        "t_is_ratio",
        "sub_name",
        "rmse_fit_lambda_tuple",
        "lam_mask_callable",
        "opt_config",
    }
    actual = set(SplineReportContext.__dataclass_fields__.keys())
    assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"


def test_spline_report_builder_has_build_report() -> None:
    """SplineReportBuilder must expose build_report(auto=bool)."""
    from certus.utils.certus_spline_report import SplineReportBuilder
    import inspect

    sig = inspect.signature(SplineReportBuilder.build_report)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "auto" in params


def test_spline_report_builder_no_result_returns_silently() -> None:
    """build_report(auto=True) with result=None should return without error."""
    from certus.utils.certus_spline_report import SplineReportContext, SplineReportBuilder

    ctx = SplineReportContext(
        result=None,
        df=None,
        spectrum_path="",
        t_is_ratio=True,
        sub_name="SiO2",
        rmse_fit_lambda_tuple=(300.0, 900.0, 1.0),
        lam_mask_callable=lambda lam: np.ones_like(lam),
        opt_config=None,
    )
    builder = SplineReportBuilder(ctx, logger=logging.getLogger("test"))
    # Should not raise
    builder.build_report(auto=True)


def test_spline_report_builder_uses_ctx_spectrum_path() -> None:
    """build_report must use self.ctx.spectrum_path (not self._last_spectrum_path)."""
    import inspect
    from certus.utils.certus_spline_report import SplineReportBuilder

    source = inspect.getsource(SplineReportBuilder.build_report)
    # The bug was: getattr(self, "_last_spectrum_path", ...)
    assert "_last_spectrum_path" not in source, (
        "build_report still references _last_spectrum_path directly on self "
        "(should use self.ctx.spectrum_path after extraction)"
    )
    assert "self.ctx.spectrum_path" in source


def test_spline_report_required_symbols_importable() -> None:
    """All symbols used by build_report must be importable from certus.utils.certus_spline_report."""
    from certus.utils.certus_spline_report import (
        SplineReportContext,
        SplineReportBuilder,
        _mergesort_order_lambda,
        _get_script_dir,
        _get_substrate_n_array_spline,
    )

    # K_MAX_LIMIT must be available in the module scope
    import certus.utils.certus_spline_report as mod

    assert hasattr(mod, "K_MAX_LIMIT"), "K_MAX_LIMIT not found in certus_spline_report"
    assert hasattr(mod, "build_spline_objective_masked_grid"), (
        "build_spline_objective_masked_grid not found"
    )
    assert hasattr(mod, "spline_objective_mse_on_masked_grid"), (
        "spline_objective_mse_on_masked_grid not found"
    )
    assert hasattr(mod, "enforce_min_k_corridor_half_width"), (
        "enforce_min_k_corridor_half_width not found"
    )


def test_mergesort_order_lambda() -> None:
    """_mergesort_order_lambda must return stable sort indices."""
    from certus.utils.certus_spline_report import _mergesort_order_lambda

    lam = np.array([500.0, 300.0, 700.0, 300.0])
    order = _mergesort_order_lambda(lam)
    assert np.array_equal(lam[order], np.array([300.0, 300.0, 500.0, 700.0]))
    # Stability: first 300 should come before second 300
    assert order[0] == 1
    assert order[1] == 3


def test_mergesort_order_lambda_empty() -> None:
    """_mergesort_order_lambda with empty array returns empty indices."""
    from certus.utils.certus_spline_report import _mergesort_order_lambda

    order = _mergesort_order_lambda(np.array([]))
    assert order.size == 0


# ═══════════════════════════════════════════════════════════════════════════════
# §3  MIXIN / CLASS COHERENCE — verify class hierarchy after extraction
# ═══════════════════════════════════════════════════════════════════════════════


def test_index_spline_app_inherits_all_mixins() -> None:
    """CertusIndexSplineApp must inherit from all expected mixins."""
    from CERTUS_INDEX_SPLINE import CertusIndexSplineApp

    mro_names = [cls.__name__ for cls in CertusIndexSplineApp.__mro__]
    expected_mixins = [
        "_ExcelExportMixin",
        "_MeshOptimizationMixin",
        "_ConfigBuilderMixin",
        "_CorridorWorkerMixin",
        "_PlotMixin",
        "_UIBuilderMixin",
        "_CorridorExportMixin",
        "_RunMixin",
        "_DataMixin",
        "_CorridorGenMixin",
        "_SettingsMixin",
        "_CorridorControlMixin",
    ]
    for mixin in expected_mixins:
        assert mixin in mro_names, f"Missing mixin in MRO: {mixin}"


def test_spline_report_accessible_from_index_spline() -> None:
    """SplineReportContext and SplineReportBuilder must be importable from CERTUS_INDEX_SPLINE."""
    from CERTUS_INDEX_SPLINE import SplineReportContext, SplineReportBuilder

    assert SplineReportContext is not None
    assert SplineReportBuilder is not None


def test_excel_export_mixin_has_export_method() -> None:
    """_ExcelExportMixin must have the export_excel method."""
    from CERTUS_INDEX_SPLINE import CertusIndexSplineApp

    assert hasattr(CertusIndexSplineApp, "export_excel")


# ═══════════════════════════════════════════════════════════════════════════════
# §4  CROSS-MODULE REFERENCE TESTS — verify no broken references
# ═══════════════════════════════════════════════════════════════════════════════


def test_spline_pipeline_has_copy() -> None:
    """spline_pipeline must have _copy (import copy as _copy) at module level."""
    import certus.spline.spline_pipeline as spline_pipeline

    assert hasattr(spline_pipeline, "_copy"), (
        "spline_pipeline._copy missing — the import was likely removed by deduplication"
    )
    assert hasattr(spline_pipeline._copy, "deepcopy")


def test_certus_design_physics_import_unified() -> None:
    """CERTUS_DESIGN must import all physics symbols from a single import block."""
    import py_compile
    from pathlib import Path

    # Just verify it compiles — the merged import is syntactically valid
    design_path = Path("CERTUS_DESIGN.py").resolve()
    py_compile.compile(str(design_path), doraise=True)

    # Verify the key symbols are accessible
    src = design_path.read_text(encoding="utf-8")
    # Count 'from certus_physics import (' blocks
    import re

    blocks = re.findall(r"^from certus_physics import \(", src, re.MULTILINE)
    # Should be 2 (the merged one + the wrapper one for calc_spectrum_*)
    assert len(blocks) == 2, (
        f"Expected exactly 2 'from certus_physics import (' blocks, found {len(blocks)}"
    )


def test_auto_clean_neighbor_pull_no_copy_error() -> None:
    """The auto_clean tests must not fail with NameError on _copy (regression guard)."""
    from certus.spline.spline_pipeline import _copy

    assert _copy.deepcopy([1, 2, 3]) == [1, 2, 3]
