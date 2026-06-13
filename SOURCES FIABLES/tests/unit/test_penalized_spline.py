import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import logging

from PyQt6.QtWidgets import QApplication

# Configure a basic logger to display console output
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TestSpline")

# Import local CERTUS modules (skip if SplineOptimizationWorker removed)
import pytest
from CERTUS_INDEX import OptimizationConfig, DataType, OptimizationWorker
try:
    from CERTUS_INDEX import SplineOptimizationWorker
except ImportError:
    SplineOptimizationWorker = None
if SplineOptimizationWorker is None:
    pytest.skip("SplineOptimizationWorker not in CERTUS_INDEX", allow_module_level=True)


def main():
    QApplication(sys.argv)

    file_path = Path("example") / "RTNBrel-sapphire.xlsx"
    if not file_path.exists():
        print(f"Error: Could not find file {file_path}")
        return

    print(f"Loading data from {file_path}")
    df = pd.read_excel(str(file_path))

    # Typical column preprocessing
    if "T (%)" in df.columns:
        df["T"] = df["T (%)"] / 100.0
    elif "T" in df.columns and df["T"].max() > 1.5:
        df["T"] = df["T"] / 100.0

    if "R (%)" in df.columns:
        df["R"] = df["R (%)"] / 100.0
    elif "R" in df.columns and df["R"].max() > 1.5:
        df["R"] = df["R"] / 100.0

    if not "lambda" in df.columns:
        if "Wavelength (nm)" in df.columns:
            df["lambda"] = df["Wavelength (nm)"]
        elif "Wavelength, nm" in df.columns:
            df["lambda"] = df["Wavelength, nm"]

    print("Columns:", df.columns.tolist())
    print("Data ranges:", df["lambda"].min(), "-", df["lambda"].max(), "nm")

    # Target config creation
    # substrate Sapphire (id 2)
    c = OptimizationConfig(
        target_data=df,
        data_type=DataType.BOTH,
        substrate="Sapphire (Al2O3)",
        thickness_min=2800.0,
        thickness_max=3200.0,
        lambda_min=df["lambda"].min(),
        lambda_max=df["lambda"].max(),
        use_normalized=True,
        lambda_max_fit=2200.0,  # Phase 1 constraint
    )

    print("\n--- PHASE 1: TLU Constrained (<2200nm) ---")
    worker1 = OptimizationWorker(c, logger=logger)

    tlu_res = None

    def on_worker1_finished(res):
        nonlocal tlu_res
        tlu_res = res

    worker1.finished.connect(on_worker1_finished)

    # Run synchronously for this script test
    worker1.run()

    # Retrieving TLU result
    if not tlu_res:
        print("TLU failed!")
        return

    print(f"TLU Thickness: {tlu_res.optimal_thickness:.2f} nm")
    print(f"TLU RMSE: {np.sqrt(tlu_res.final_mse):.6f}")

    print("\n--- PHASE 2: Penalized Spline IR (>2200nm) ---")
    # Restore normal config without constraint
    tlu_res.config.lambda_max_fit = None

    worker2 = SplineOptimizationWorker(
        tlu_res.config, tlu_res, num_tlu_knots=7, logger=logger
    )
    worker2.perform_thickness_scan = True
    worker2.alpha_smoothness = 1.0

    spline_res = None

    def on_worker2_finished(res):
        nonlocal spline_res
        spline_res = res

    worker2.finished.connect(on_worker2_finished)

    # Run synchronously
    worker2.run()

    if not spline_res:
        print("Spline failed!")
        return

    print(f"Final Spline Thickness: {spline_res.optimal_thickness:.2f} nm")
    print(f"Final Spline RMSE: {np.sqrt(spline_res.final_mse):.6f}")
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()
