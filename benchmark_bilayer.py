import sys
import json
import numpy as np
import pandas as pd
import os
import time

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

sys.path.insert(0, os.getcwd())

import CERTUS_METAL_BILAYER

def run():
    config_path = r"example\example_metal_bilayer\JSON-metal-bilayer-example.json"
    with open(config_path, "r") as f:
        config = json.load(f)
        
    target_file = config.get("target_file", "")
    target_file = target_file.replace("../1006/", "") # just in case
    if not os.path.exists(target_file):
        target_file = r"example\example_metal_bilayer\CSV-metal-bilayer-example.csv"
        
    df = pd.read_csv(target_file)
    l_array = df.iloc[:, 0].values.astype(float)
    R_array = df.iloc[:, 1].values.astype(float)
    # Filter bounds
    lmin = float(config["filters"]["lmin_filter"])
    lmax = float(config["filters"]["lmax_filter"])
    mask = (l_array >= lmin) & (l_array <= lmax)
    l_array = l_array[mask]
    R_array = R_array[mask]

    params = {
        "target_lambda": l_array,
        "target_r": R_array,
        "substrate_id": 0,
        "num_knots": int(config["material_params"]["num_knots"]),
        "min_knot_dist": float(config["material_params"]["min_knot_dist"]),
        "eM_min": float(config["physical_params"]["eM_min"]),
        "eM_max": float(config["physical_params"]["eM_max"]),
        "eL_nominal": float(config["physical_params"]["eL_nominal"]),
        "eL_variation": float(config["physical_params"]["eL_variation"]),
        "n_infini_min": float(config["material_params"]["n_infini_min"]),
        "n_infini_max": float(config["material_params"]["n_infini_max"]),
        "A_diel_min": float(config["material_params"]["A_diel_min"]),
        "A_diel_max": float(config["material_params"]["A_diel_max"]),
        "nk_min": float(config["material_params"]["nk_min"]),
        "nk_max": float(config["material_params"]["nk_max"]),
        "popsize": int(config["optimization"]["popsize"]),
        "maxiter": int(config["optimization"]["maxiter"]),
        "tol": float(config["optimization"]["tol"]),
        "mutation_min": 0.5,
        "mutation_max": 1.0,
        "recombination": 0.7,
        "updating": "deferred",
    }
    
    params["maxiter"] = 50
    params["maxfeval"] = 20000
    
    if "CERTUS_METAL_ULTRA_WIDE" in os.environ:
        del os.environ["CERTUS_METAL_ULTRA_WIDE"]
        
    os.environ["CERTUS_METAL_INITIAL_MESH_SEED"] = "42"

    if hasattr(CERTUS_METAL_BILAYER, "_build_bilayer_bounds"):
        params["bounds"] = CERTUS_METAL_BILAYER._build_bilayer_bounds(params, l_array, include_eM=True)

    worker = CERTUS_METAL_BILAYER.OptimizationWorker(params)
    
    start_time = time.time()
    
    def on_finished(data):
        elapsed = time.time() - start_time
        result = data["result"]
        fun = float(getattr(result, "fun", float("inf")))
        rmse = float(np.sqrt(max(fun, 0.0)))
        print("--- RESULT_START ---")
        print(f"ELAPSED={elapsed:.2f}s")
        print(f"RMSE={rmse}")
        print(f"X={result.x.tolist()}")
        print("--- RESULT_END ---")

    worker.finished.connect(on_finished)
    worker.run()

if __name__ == "__main__":
    run()
