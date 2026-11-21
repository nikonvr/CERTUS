"""How well the wavelength grid of DESIGN resolves the merit of a design, for each way of sizing it (2026-11-21).

For the two Tikhonravov 1996 files (34 layers, 400-1200 nm, T = 0.5; the first holds the starting design, the second the
published one): the grid of Points / Target (the file's), and the automatic grid sized by the design's TOT alone, by the
file's max_layers (TOT ceiling by the degrees of freedom), and the latter refined by ``refine_grid``. Merit = the RMSE of
DESIGN on the grid, weighted as its cost (``prepare_targets_vectorized``: target weight times the Delta ln(lambda)
quadrature); reference = the same on 40 001 points uniform in wavenumber. CERTUS's own window, materials and TMM.

    python reports\\design_auto_grid_limits_2026-11-21\\mesure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

FILES = ("JSON-design-reference-tikhonravov-1996.json", "JSON-design-reference-tikhonravov-1996-published-design.json")
DENSE = 40001


def merit_functions(app):
    """The squared residual (target weight included) for ``refine_grid``, and the RMSE of DESIGN on a grid."""
    from certus.core.certus_design_worker_utils import optim_grid_indices
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside
    from certus_physics import prepare_targets_vectorized

    mats, stack = app._get_materials(), app._get_front_stack()
    ep = np.ascontiguousarray(np.asarray(app.ep_current, dtype=np.float64))
    active = [t for t in app._get_tgts() if t.valid()]

    def transmission(lam: np.ndarray) -> np.ndarray:
        empty_back = np.empty((len(lam), 0), dtype=np.complex128)
        lam, substrate, front, _back = optim_grid_indices(np.asarray(lam, dtype=np.float64), mats, stack, None, empty_back,
                                                          float_dtype=np.float64, complex_dtype=np.complex128)
        _r, t = calculate_RT_no_backside(ep, front, np.ascontiguousarray(substrate, dtype=np.complex128), lam)
        return np.asarray(t, dtype=np.float64)

    def squared_residual(lam: np.ndarray) -> np.ndarray:
        from certus.core.certus_design_auto_grid import target_values_and_weights

        vals, weights = target_values_and_weights(active, lam)
        return weights * (transmission(lam) - vals) ** 2

    def rmse(lam: np.ndarray) -> float:
        lam = np.sort(np.asarray(lam, dtype=np.float64))
        vals, weights = prepare_targets_vectorized(lam, active)
        return float(np.sqrt(np.sum(weights * (transmission(lam) - vals) ** 2) / np.sum(weights)))

    return active, squared_residual, rmse


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    from certus.core.certus_design_auto_grid import refine_grid
    from certus.ui.certus_design_ui import CertusDesignApp

    _qt = QApplication.instance() or QApplication(sys.argv)  # kept: a discarded QApplication aborts the first widget
    print("file | grid | TOT nm (QWOT) from | points | RMSE grid | RMSE dense | error on the RMSE")
    for name in FILES:
        app = CertusDesignApp()
        app.load_config(str(ROOT / "example" / "example_design" / name))
        active, f, rmse = merit_functions(app)
        lo, hi = active[0].lmin, active[0].lmax
        ref = rmse(1.0 / np.linspace(1.0 / hi, 1.0 / lo, DENSE))
        l0 = app.l0_spin.value()
        short = "published" if "published" in name else "start"
        cap = app.max_layers_spin.value()

        def row(label: str, wls: np.ndarray, tot: float | None, source: str, ref: float = ref, short: str = short,
                rmse=rmse, l0: float = l0) -> None:
            value = rmse(wls)
            tot_text = f"{tot:.0f} ({4.0 * tot / l0:.1f}) {source}" if tot is not None else "-"
            print(f"{short} | {label} | {tot_text} | {wls.size} | {value:.5e} | {ref:.5e} | {abs(value / ref - 1.0):.2%}")

        row(f"Points / Target {app.points_per_target_spin.value()}", app._get_optim_wls(), None, "")
        app.auto_grid_check.setChecked(True)
        app.max_layers_spin.setValue(0)
        tot, source = app.core_manager._auto_grid_tot(active)
        row("auto, no limit", app._get_optim_wls(), tot, source)
        app.max_layers_spin.setValue(cap)
        tot, source = app.core_manager._auto_grid_tot(active)
        base = app._get_optim_wls()
        row(f"auto, max layers {cap}", base, tot, source)
        print(f"{short} | label | {app.auto_grid_points_label.text()}")
        refined = refine_grid([(lo, hi)], base, f, rel_tol=0.01)
        row(f"auto, max layers {cap}, refined ({refined.rounds} rounds)", refined.wavelengths, tot, source)
        app.close()
        app.deleteLater()


if __name__ == "__main__":
    main()
