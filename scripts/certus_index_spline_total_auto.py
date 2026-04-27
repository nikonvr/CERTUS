import os
import sys
from pathlib import Path

# Mocks UI minimum pour import core en mode headless
from unittest.mock import MagicMock
mock_ui = MagicMock()
mock_ui.setup_gui_exception_handling = lambda: None
mock_ui.CertusBaseApp = MagicMock
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()
sys.modules["PyQt6.QtGui"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = MagicMock()
sys.modules["pyqtgraph"] = MagicMock()
sys.modules["certus_ui"] = mock_ui
sys.modules["certus_reset_framework"] = MagicMock()

# Ajout du repertoire parent au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import logging
from threading import Event

from certus_core import setup_logging
from certus_data import read_data_file_robust
from certus_physics import (
    get_n_substrate_array_by_id,
    calculate_T_substrate_array,
    warmup_physics,
)
from certus_index_spline_core import (
    substrate_id_from_name,
    normalize_spectrum_dataframe,
    worker_spline_optimization,
    SplineOptConfig,
    DataType,
)

def run_ultimate_validation():
    # Force mode headless pour Qt (secours)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    
    setup_logging(log_file="logs/besttotal_validation.log")
    logger = logging.getLogger("CERTUS")
    logger.info("=== RELANCE BATCH HAUTE FIDELITE (Objet: 0.0148 RMSE) ===")

    # 1. Chargement des data
    data_path = "example/IR/tosmo/TOTAL.xlsx"
    df_raw = read_data_file_robust(data_path)
    df = normalize_spectrum_dataframe(df_raw)
    
    # Auto-detection m vs nm
    lam = df["lambda"].values
    if np.nanmax(lam) < 100:
        logger.info(f"Conversion m -> nm detectee (max={np.nanmax(lam):.2f})")
        lam *= 1000.0
    
    t_raw = df["T"].values
    
    # 3 = Sapphire
    n_sub = get_n_substrate_array_by_id(3, lam)
    warmup_physics()

    # Configuration EXACTE du batch a succes
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=t_raw,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=3,
        d_lo=2800.0,
        d_hi=3200.0,
        weight_t=1.0,
        weight_r=0.0,
        r_exp=None,
        substrate_name="Sapphire (Al2O3)",
        t_is_ratio=True,
        pglobal_max_iter=35,
        polish_maxfun=8000,
        pglobal_max_feval=120000,
        pglobal_local_search_budget=35000,
    )

    stop = Event()
    print("Demarrage de l'optimization (Spline 12 nuds)...")
    
    # Phase Spline (12 nuds par defaut dans worker_spline_optimization si n_seg=11)
    # On utilise le worker direct
    best_spline = worker_spline_optimization(
        cfg, stop_event=stop, progress_cb=lambda p, m: print(f"{float(p) / 100.0:.2f}% - {m}")
    )

    best = best_spline

    # --- EXPORT FINAL MULTI-SHEETS ---
    try:
        t_sub_theo = calculate_T_substrate_array(np.asarray(lam), np.asarray(n_sub))
        t_ratio_exp = t_raw / np.maximum(t_sub_theo, 1e-6)
        
        # Feuille Spectre
        df_spec = pd.DataFrame({
            "Wavelength (nm)": lam,
            "n_film": best["n_lam"],
            "k_film": best["k_lam"],
            "Ratio_Exp": t_ratio_exp,
            "Ratio_Theo": best["t_theo"]
        })
        
        # Feuille Parametres (Le vecteur x de 19 values)
        x_values = best.get("x", np.zeros(19))
        df_params = pd.DataFrame({
            "Indice": np.arange(len(x_values)),
            "Valeur_Parametre": x_values
        })
        
        # Feuille Resume
        df_sum = pd.DataFrame({
            "Indicateur": [
                "RMSE Finale", 
                "Epaisseur (nm)", 
                "Loi n retenue", 
                "Loi log k retenue", 
                "Nombre knots (K)"
            ],
            "Valeur": [
                best["rmse"], 
                best["d_nm"], 
                best.get("law_n_id", "Spline"), 
                best.get("law_L_id", "Spline"), 
                len(best.get("sigma_knots", []))
            ]
        })
        
        with pd.ExcelWriter("besttotal.xlsx", engine="openpyxl") as writer:
            df_spec.to_excel(writer, sheet_name="Spectre", index=False)
            df_params.to_excel(writer, sheet_name="Parms_19D", index=False)
            df_sum.to_excel(writer, sheet_name="Resume", index=False)
            
        print(f"[OK] Fichier besttotal.xlsx genere avec RMSE {best['rmse']:.6f}")
        
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"[ERR] Echec de l'export Excel : {e}")

if __name__ == "__main__":
    run_ultimate_validation()
