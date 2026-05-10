"""Smoke INDEX SPLINE : imports critiques (chaîne modules + classe GUI)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.index_spline_smoke


def test_import_spline_module_chain() -> None:
    import certus_index_spline_core  # noqa: F401
    import spline_finalize  # noqa: F401
    import spline_objective  # noqa: F401
    import spline_pipeline  # noqa: F401
    import spline_presets  # noqa: F401
    import spline_smart_init  # noqa: F401
    import spline_visual_utils  # noqa: F401
    import spline_workers  # noqa: F401

    from certus_index_spline_core import SplineOptConfig  # noqa: F401
    from spline_pipeline import worker_spline_optimization  # noqa: F401
    from spline_workers import worker_auto_best_split_knot_refinement  # noqa: F401

    assert callable(worker_spline_optimization)
    assert callable(worker_auto_best_split_knot_refinement)
    assert SplineOptConfig is not None


def test_import_certus_index_spline_app() -> None:
    from CERTUS_INDEX_SPLINE import CertusIndexSplineApp  # noqa: F401

    assert CertusIndexSplineApp is not None
