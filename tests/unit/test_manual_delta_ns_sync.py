from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import numpy.testing as npt

from CERTUS_INDEX_SPLINE import CertusIndexSplineApp
from certus.spline.certus_index_spline_core import DataType, SplineOptConfig

from certus.utils.certus_index_utils import _transmittance_absolute_from_nk

from certus.spline.spline_pipeline import _should_skip_manual_insert_for_equal_mesh, _sync_theoretical_tr_from_nk_dict


def test_sync_theoretical_tr_uses_effective_substrate_index_from_result() -> None:
    lam_nm = np.array([500.0, 700.0, 900.0], dtype=np.float64)
    n_sub_base = np.array([1.45, 1.46, 1.47], dtype=np.float64)
    n_sub_effective = n_sub_base + 0.08
    n_lam = np.array([1.80, 1.82, 1.85], dtype=np.float64)
    k_lam = np.array([1.0e-3, 1.2e-3, 1.4e-3], dtype=np.float64)
    d_nm = 180.0

    cfg = SplineOptConfig(
        substrate_name="Test",
        weight_r=0.0,
        weight_t=1.0,
        d_hi=300.0,
        d_lo=50.0,
        n_seg=2,
        data_type=DataType.TRANSMISSION,
        n_sub=n_sub_base.copy(),
        r_exp=None,
        t_exp=np.array([0.0, 0.0, 0.0], dtype=np.float64),
        lam_nm=lam_nm.copy(),
        substrate_n_base=n_sub_base.copy(),
        substrate_n_offset=0.08,
    )
    out = {
        "lam_nm": lam_nm.copy(),
        "n_lam": n_lam.copy(),
        "k_lam": k_lam.copy(),
        "d_nm": d_nm,
        "n_sub_effective": n_sub_effective.copy(),
    }

    _sync_theoretical_tr_from_nk_dict(cfg, out, reason="unit_test_delta_ns")

    expected_effective = _transmittance_absolute_from_nk(lam_nm, n_lam, k_lam, d_nm, n_sub_effective)
    expected_base = _transmittance_absolute_from_nk(lam_nm, n_lam, k_lam, d_nm, n_sub_base)

    npt.assert_allclose(out["t_theo"], expected_effective, rtol=0.0, atol=1e-12)
    assert not np.allclose(out["t_theo"], expected_base, rtol=0.0, atol=1e-12)


def test_apply_manual_substrate_offset_preview_refreshes_curve_without_worker() -> None:
    class _Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, value: str) -> None:
            self.text = str(value)

    class _Harness:
        @staticmethod
        def _post_optimization_ready_status(status_text):
            return CertusIndexSplineApp._post_optimization_ready_status(status_text)

        @staticmethod
        def _format_post_optimization_status(display, fallback_result=None):
            return CertusIndexSplineApp._format_post_optimization_status(display, fallback_result)

        def __init__(self, cfg: SplineOptConfig, n_sub_base: np.ndarray) -> None:
            self._last_run_cfg = cfg
            self._last_result = None
            self._last_worker_result = None
            self._worker = None
            self._n_sub_base = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()
            self.logger = None
            self.lbl_status = _Label()
            self.plot_calls: list[tuple[dict, str]] = []
            self.table_calls: list[dict | None] = []

        def _build_opt_config(self, notify: bool = False):
            _ = notify
            return self._last_run_cfg

        def _baseline_substrate_n_for_result(self, result: dict, *, lam_override=None):
            lam_src = lam_override if lam_override is not None else result.get("lam_nm")
            lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
            return lam.copy(), self._n_sub_base.copy()

        def _decorate_result_with_substrate_offset(self, result: dict, *, n_sub_base: np.ndarray, delta_ns: float):
            return CertusIndexSplineApp._decorate_result_with_substrate_offset(
                result,
                n_sub_base=n_sub_base,
                delta_ns=delta_ns,
            )

        def _plot_result(self, result: dict, *, plot_source: str = "maj") -> None:
            self.plot_calls.append((dict(result), str(plot_source)))

        def _refresh_data_table(self, result_override: dict | None = None) -> None:
            self.table_calls.append(dict(result_override) if isinstance(result_override, dict) else result_override)

    lam_nm = np.array([500.0, 700.0, 900.0], dtype=np.float64)
    n_sub_base = np.array([1.45, 1.46, 1.47], dtype=np.float64)
    n_lam = np.array([1.80, 1.82, 1.85], dtype=np.float64)
    k_lam = np.array([1.0e-3, 1.2e-3, 1.4e-3], dtype=np.float64)
    d_nm = 180.0
    delta_ns = 0.02

    cfg = SplineOptConfig(
        substrate_name="Sapphire (Al2O3)",
        weight_r=0.0,
        weight_t=1.0,
        d_hi=300.0,
        d_lo=50.0,
        n_seg=2,
        data_type=DataType.TRANSMISSION,
        n_sub=n_sub_base.copy(),
        r_exp=None,
        t_exp=np.array([0.0, 0.0, 0.0], dtype=np.float64),
        lam_nm=lam_nm.copy(),
        substrate_n_base=n_sub_base.copy(),
        substrate_n_offset=0.0,
    )
    seed = {
        "lam_nm": lam_nm.copy(),
        "n_lam": n_lam.copy(),
        "k_lam": k_lam.copy(),
        "d_nm": d_nm,
        "mse": 1.0e-4,
        "substrate_name": "Sapphire (Al2O3)",
        "t_theo": _transmittance_absolute_from_nk(lam_nm, n_lam, k_lam, d_nm, n_sub_base),
    }

    harness = _Harness(cfg, n_sub_base)

    ok = CertusIndexSplineApp._apply_manual_substrate_offset_preview(harness, seed, delta_ns)

    assert ok is True
    assert harness._worker is None
    assert len(harness.plot_calls) == 1
    assert harness.plot_calls[0][1] == "manual_delta_ns_preview"
    assert len(harness.table_calls) == 1
    assert isinstance(harness._last_result, dict)
    assert isinstance(harness._last_worker_result, dict)

    preview = harness._last_result
    n_sub_effective = n_sub_base + delta_ns
    expected_effective = _transmittance_absolute_from_nk(lam_nm, n_lam, k_lam, d_nm, n_sub_effective)

    npt.assert_allclose(preview["n_sub_base"], n_sub_base, rtol=0.0, atol=1e-12)
    npt.assert_allclose(preview["n_sub_effective"], n_sub_effective, rtol=0.0, atol=1e-12)
    npt.assert_allclose(preview["t_theo"], expected_effective, rtol=0.0, atol=1e-12)
    assert not np.allclose(preview["t_theo"], seed["t_theo"], rtol=0.0, atol=1e-12)

    data_th_stub = SimpleNamespace(
        df=None,
        logger=None,
        _lam_piecewise_report_grid_nm=CertusIndexSplineApp._lam_piecewise_report_grid_nm,
    )
    out = CertusIndexSplineApp._prepare_data_th_tab_series(data_th_stub, preview)
    assert out is not None
    lam_g, _, _, _, ns_g, _, _ = out
    idx = [int(np.where(np.isclose(lam_g, x))[0][0]) for x in lam_nm]
    npt.assert_allclose(ns_g[idx], n_sub_effective, rtol=0.0, atol=1e-12)

    assert "Available actions: Manual knots / Corridors" in harness.lbl_status.text


def test_equal_mesh_skip_policy_can_be_forced_for_manual_reopt() -> None:
    sk = np.asarray([1.0 / 2500.0, 1.0 / 1800.0, 1.0 / 900.0], dtype=np.float64)
    sk_new_same = sk.copy()

    assert (
        _should_skip_manual_insert_for_equal_mesh(
            sk_new_same,
            sk,
            offset_changed=False,
            force_reopt=False,
        )
        is True
    )
    assert (
        _should_skip_manual_insert_for_equal_mesh(
            sk_new_same,
            sk,
            offset_changed=True,
            force_reopt=False,
        )
        is False
    )
    assert (
        _should_skip_manual_insert_for_equal_mesh(
            sk_new_same,
            sk,
            offset_changed=False,
            force_reopt=True,
        )
        is False
    )


def test_open_manual_dialog_triggers_baseline_preopt_on_existing_mesh() -> None:
    """Verify that sigma_knots in the seed result are converted to lambda_nm for the baseline pre-opt."""
    sigma_knots = np.asarray([1.0 / 900.0, 1.0 / 700.0, 1.0 / 500.0], dtype=np.float64)
    result = {"sigma_knots": sigma_knots.copy(), "d_nm": 150.0, "mse": 1e-6, "t_theo": [], "lam_nm": []}

    sigma_base = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
    assert sigma_base.size >= 2, "Test prereq: need at least 2 knots"

    lam_base_nm = (1.0 / np.maximum(sigma_base, 1e-30)).tolist()

    # The produced lambda list should be in 1-to-1 correspondence with sigma_knots (inverted)
    expected_lam = sorted([900.0, 700.0, 500.0])
    npt.assert_allclose(sorted(lam_base_nm), expected_lam, rtol=1e-9)