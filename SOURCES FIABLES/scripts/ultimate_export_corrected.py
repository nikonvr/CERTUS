"""ULTIMATE EXCEL EXPORT (Fixing µm -> nm and Physics).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# --- DEFENSIVE MOCKING --- (To allow headless import of core)
class MockModule(MagicMock):
    def __getattr__(self, name): return MagicMock()

m_ui = MockModule()
sys.modules["PyQt6"] = m_ui
sys.modules["PyQt6.QtCore"] = m_ui
sys.modules["PyQt6.QtGui"] = m_ui
sys.modules["PyQt6.QtWidgets"] = m_ui
sys.modules["pyqtgraph"] = m_ui
sys.modules["pyqtgraph.exporters"] = m_ui
sys.modules["certus_ui"] = m_ui
sys.modules["certus_reset_framework"] = m_ui

import numpy as np
import pandas as pd
from threading import Event

# Root path
_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _root)

from certus.core.certus_core import setup_logging
from certus.utils.certus_data import read_data_file_robust
from certus_physics import (
    get_n_substrate_array_by_id,
    calculate_bare_substrate_RT,
    warmup_physics,
)
from certus.spline.certus_index_spline_core import (
    normalize_spectrum_dataframe,
    run_spline_adaptive_mesh_loop,
    SplineOptConfig,
    DataType,
)
def run():
    print("Démarrage de l'optimisation CORRECTE (Headless)...")
    setup_logging(log_file="logs/ultimate_export_corrected.log")
    
    data_path = "example/IR/tosmo/TOTAL.xlsx"
    df = read_data_file_robust(data_path)
    df = normalize_spectrum_dataframe(df)
    
    # --- AUTO-DETECTION UNITÉS (nm vs µm) ---
    lam_vals = df["lambda"].values
    if np.nanmax(lam_vals) < 100:
        print(f"[NOTE] Conversion µm -> nm détectée (max={np.nanmax(lam_vals):.2f})")
        df["lambda"] *= 1000.0
    
    lam_nm = df["lambda"].values
    t_raw = df["T"].values
    
    # 3 = Sapphire (Al2O3)
    n_sub = get_n_substrate_array_by_id(3, lam_nm)
    warmup_physics()

    # Configuration Haute Fidélité
    cfg = SplineOptConfig(
        lam_nm=lam_nm, t_exp=t_raw, n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        # Épaisseur estimée pour cet échantillon IR (3000 nm)
        d_lo=2800.0, d_hi=3200.0,
        weight_t=1.0, t_is_ratio=True,
        # Budget suffisant pour convergence
        pglobal_max_iter=35, polish_maxfun=8000,
    )

    stop = Event()
    print("Spline adaptive mesh (overlay lois analytiques inclus dans worker_spline_optimization)...")
    best = run_spline_adaptive_mesh_loop(cfg, knots_start=4, knots_max=10, stop_event=stop)

    if best:
        t_sub_theo = calculate_bare_substrate_RT(lam_nm, n_sub)
        t_ratio_exp = t_raw / np.maximum(t_sub_theo, 1e-6)
        
        # On exporte l'Excel avec les bons labels et les bonnes valeurs
        # On garde les nm internes mais on peut remettre en µm pour la colonne si besoin
        df_spec = pd.DataFrame({
            "Wavelength (nm)": lam_nm,
            "n_film": best["n_lam"],
            "k_film": best["k_lam"],
            "Ratio_Exp": t_ratio_exp,
            "Ratio_Theo": best["t_theo"]
        })
        df_sum = pd.DataFrame({
            "Indicateur": ["RMSE Finale", "Epaisseur (nm)", "Loi n", "Loi log k"],
            "Valeur": [best["rmse"], best["d_nm"], best.get("law_n_id","-"), best.get("law_L_id","-")]
        })
        
        with pd.ExcelWriter("total_result.xlsx", engine="openpyxl") as writer:
            df_spec.to_excel(writer, sheet_name="Spectre", index=False)
            df_sum.to_excel(writer, sheet_name="Résumé", index=False)
        
        print(f"[OK] Fichier CORRIGÉ total_result.xlsx généré avec RMSE={best['rmse']:.6e}")
    else:
        print("[ERR] Échec du pipeline.")

if __name__ == "__main__":
    run()
