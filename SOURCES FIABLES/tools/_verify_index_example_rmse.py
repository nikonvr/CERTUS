"""INDEX verification: final RMSE on a spectrum file (same paths as UI).

Usage:
  python tools/_verify_index_example_rmse.py
  python tools/_verify_index_example_rmse.py --sapphire
  python tools/_verify_index_example_rmse.py --file "PATH/H800-sapphire-RTrelNB.xlsx"
  python tools/_verify_index_example_rmse.py --file ... --thickness-nm 2800 --sapphire
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

# Project directory (parent of tools/)
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtWidgets import QApplication

    QApplication(sys.argv)

    from certus.core.certus_core import SUBSTRATE_LIST, wait_warmup

    wait_warmup()

    from CERTUS_INDEX import CertusIndexApp

    csv_path = str(Path(_ROOT) / "example" / "CSV-index-example.csv")

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--file",
        default=None,
        help="CSV/XLSX spectrum (default: example/CSV-index-example.csv)",
    )
    ap.add_argument(
        "--sapphire",
        action="store_true",
        help="Force Al2O3 substrate (combo index 3), otherwise default UI = SiO2",
    )
    ap.add_argument(
        "--thickness-nm",
        type=float,
        default=None,
        metavar="D",
        help="Known layer thickness: bound min=max=D (nm), e.g. 2800",
    )
    args = ap.parse_args()

    spectrum_path = args.file if args.file else csv_path

    win = CertusIndexApp()
    win.load_file(spectrum_path)

    if args.sapphire:
        win.cb_sub.setCurrentIndex(3)
        win._on_substrate_changed(3)

    if args.thickness_nm is not None:
        d_nm = float(args.thickness_nm)
        win.sb_dmin.setValue(d_nm)
        win.sb_dmax.setValue(d_nm)

    print("=== Effective settings before optimization ===")
    print(f"  File: {spectrum_path}")
    print(f"  Substrate: {SUBSTRATE_LIST[win.cb_sub.currentIndex()]} (combo index {win.cb_sub.currentIndex()})")
    print(f"  lambda min/max: {win.sb_lmin.value():.1f} - {win.sb_lmax.value():.1f} nm")
    print(f"  Thickness bounds: {win.sb_dmin.value():.1f} - {win.sb_dmax.value():.1f} nm")
    print(f"  T/Tsub normalized: {win.chk_normalized.isChecked()}")
    print(f"  High precision: {win.chk_high_precision.isChecked()}")
    print(f"  FFT thickness seed: {getattr(win, '_estimated_thickness_nm', None)}")
    print()

    loop = QEventLoop()
    # H800 pipeline: TLU then IR (auto popup Yes after 5 s) — can exceed 15 min.
    timeout_ms = 2_700_000

    def quit_loop() -> None:
        loop.quit()

    QTimer.singleShot(timeout_ms, quit_loop)

    def poll() -> None:
        if win.latest_results is not None:
            loop.quit()

    poller = QTimer()
    poller.timeout.connect(poll)
    poller.start(800)

    win.run_optimization()
    loop.exec()
    poller.stop()

    if win.latest_results is None:
        print("Failed: no OptimizationResults (timeout or error - see logs).")
        return 2

    res = win.latest_results
    rmse = math.sqrt(max(0.0, float(res.final_mse)))
    print("=== Result ===")
    print(f"  Final RMSE (sqrt(final_mse)): {rmse:.6f}")
    print(f"  Optimal thickness: {res.optimal_thickness:.2f} nm")
    if res.tlu_params is not None:
        t = res.tlu_params
        print(f"  TLU : Eg={t.Eg:.4f} eV  E0={t.E0:.4f} eV  eps_inf={t.eps_inf:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
