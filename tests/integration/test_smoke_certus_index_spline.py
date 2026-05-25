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


def test_live_index_monitor_ui(qapp) -> None:
    from certus_index_spline_ui import LiveIndexMonitor
    from unittest.mock import MagicMock
    import numpy as np

    # Ensure mock/None elements are supported safely
    dialog = LiveIndexMonitor(None)
    assert dialog is not None

    # Test updating coordinates
    lam = np.array([400.0, 500.0, 600.0])
    n = np.array([2.1, 2.0, 1.9])
    k = np.array([1e-4, 1e-5, 1e-6])
    dialog.update_indices(lam, n, k, d_nm=150.0)
    assert dialog.lbl_d.text() == "d = 150.0 nm"
    dialog.close()

