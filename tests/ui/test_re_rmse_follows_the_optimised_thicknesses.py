"""After an RE run, the RMSE of the title is computed on the optimised thicknesses (audit 2026-11-15, M-L6b).

Loading a workbook stores its thicknesses in ``_re_loaded_exact_ep``, which ``_compute_re_rmse`` reads first. The end of
the run wrote the optimised thicknesses to ``ep_current`` only: the title and the export metadata kept the RMSE of the
initial design.
"""

from __future__ import annotations

import importlib

import numpy as np
import pytest

MODULE = "certus.ui.certus_re_workers_mixin"


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    win.load_reverse_engineering_from_path("example/example_RE/reverse_sample.xlsx")
    yield win
    win.close()


def test_the_rmse_after_a_run_uses_the_optimised_thicknesses(re_window, monkeypatch) -> None:
    win = re_window
    mod = importlib.import_module(MODULE)
    loaded = np.asarray(win._re_loaded_exact_ep, dtype=np.float64).copy()
    optimised = loaded + 7.0

    seen: list[np.ndarray] = []

    def _record(ep, *_args, **_kwargs) -> float:
        seen.append(np.asarray(ep, dtype=np.float64).copy())
        return 0.0

    monkeypatch.setattr(mod, "_re_rmse_oblique_weighted", _record)
    monkeypatch.setattr(mod, "QTimer", type("_NoTimer", (), {"singleShot": staticmethod(lambda *_a, **_k: None)}))
    monkeypatch.setattr(win, "_show_re_results_window", lambda *_a, **_k: None)
    monkeypatch.setattr(win, "_schedule_eval", lambda *_a, **_k: None)

    win._on_re_done(
        {
            "ok": True,
            "ep0": loaded,
            "results": [{"label": "run", "rmse": 0.01, "ep": optimised, "nfev": 3, "success": True}],
        }
    )
    np.testing.assert_array_equal(win.ep_current, optimised)

    win._compute_re_rmse(0.0, 0.0, 0.0)
    assert seen, "_compute_re_rmse did not reach the spectral RMSE"
    np.testing.assert_array_equal(seen[-1], optimised)
