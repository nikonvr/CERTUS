"""
Test headless CERTUS INDEX SPLINE
Calls worker_spline_optimization directly without a UI thread.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
import certus_physics
import threading
import numpy as np


def test_spline_headless():
    print("TEST SPLINE STARTING!")

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    certus_physics.warmup_physics()
    print("warmup_physics done")

    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
    from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization

    spline_app = CertusIndexSplineApp()
    print("CertusIndexSplineApp created")

    example_xlsx = Path("example/example_index_spline/TSIO2-1700-1.xlsx").resolve()
    spline_app._on_load(path=str(example_xlsx))
    print(f"Spectrum loaded: {len(spline_app.df)} rows")

    # Build config
    cfg = spline_app._build_opt_config(notify=False)
    if cfg is None:
        print("ERROR: _build_opt_config returned None")
        sys.exit(1)

    print(f"Config OK: n_seg={cfg.n_seg}, d=[{cfg.d_lo:.0f}, {cfg.d_hi:.0f}] nm, local_only={cfg.spline_local_only}")

    # Run optimization directly (synchronous, no QThread)
    stop_event = threading.Event()

    def progress_cb(pct, msg=""):
        print(f"  [{pct:3.0f}%] {msg}")

    def live_cb(payload):
        if isinstance(payload, dict):
            rmse = payload.get("rmse")
            d = payload.get("d_nm")
            if rmse is not None:
                print(f"  live: d={d:.1f}nm, RMSE={rmse:.6f}")

    print("Running worker_spline_optimization (local only)...")
    result = worker_spline_optimization(cfg, stop_event,
                                        progress_cb=progress_cb,
                                        live_cb=live_cb)

    print("\nHEADLESS SPLINE DONE.")
    if isinstance(result, dict):
        rmse = result.get("rmse")
        d_nm = result.get("d_nm")
        n_at_visible = None
        n_at_ir = None
        # Try to get index values
        n_arr = result.get("n_arr") or result.get("n_fit") or result.get("n")
        lam_arr = result.get("lam_nm") if "lam_nm" in result else result.get("lam")
        if lam_arr is None:
            lam_arr = result.get("lam_grid")
        if n_arr is not None and lam_arr is not None:
            lam_arr = np.asarray(lam_arr)
            n_arr = np.asarray(n_arr)
            # ~550nm (visible)
            idx_vis = np.argmin(np.abs(lam_arr - 550))
            n_at_visible = float(n_arr[idx_vis])
            # ~2000nm (IR)
            idx_ir = np.argmin(np.abs(lam_arr - 2000))
            if idx_ir < len(n_arr):
                n_at_ir = float(n_arr[idx_ir])
        print(f"RMSE       : {rmse}")
        print(f"Thickness  : {d_nm} nm")
        print(f"n(550nm)   : {n_at_visible}")
        print(f"n(2000nm)  : {n_at_ir}")
        print("Result keys:", list(result.keys()))
    else:
        print(f"No dict result: {type(result)}")
        sys.exit(1)


if __name__ == "__main__":
    test_spline_headless()
    os._exit(0)
