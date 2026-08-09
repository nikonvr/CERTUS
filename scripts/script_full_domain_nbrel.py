"""


Complete INDEX chain on NBrel: TLU (lambda<=2200) + phase 2 IR (lambda>2200) -> spectrum 350-5200 nm.


Displays the final RMSE T_rel over the entire file (measurement points).





Usage (from the project root):


  python tests/script_full_domain_nbrel.py


  python tests/script_full_domain_nbrel.py --lambda-min 1000


  python tests/script_full_domain_nbrel.py --no-clip


"""





from __future__ import annotations





import argparse


import json


import logging


from pathlib import Path


import sys





_ROOT = Path(__file__).resolve().parent.parent


sys.path.insert(0, str(_ROOT))


sys.path.insert(0, str(_ROOT / "tests"))





from PyQt6.QtWidgets import QApplication  # noqa: E402





_QT_APP = QApplication.instance() or QApplication([])





import benchmark_tosmo_nb_sapphire as bench  # noqa: E402





logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


logger = logging.getLogger("full_domain_nbrel")





NBREL = _ROOT / "example" / "IR" / "tosmo" / "NBrel sur sapphire .xlsx"








def main() -> int:


    ap = argparse.ArgumentParser(description="TLU + IR sur tout le domaine NBrel, RMSE finale")


    ap.add_argument(


        "--lambda-min",


        type=float,


        default=None,


        help="Couper les lambda < valeur (défaut : tout le spectre fichier)",


    )


    ap.add_argument(


        "--no-clip",


        action="store_true",


        help="Ne pas contraindre T_rel dans [0,1]",


    )


    ap.add_argument(


        "--path",


        default=NBREL,


        help="Fichier Excel lambda, T_rel",


    )


    args = ap.parse_args()





    input_path = Path(args.path)

    if not input_path.is_file():


        logger.error("File not found: %s", input_path)


        return 2





    clip = not args.no_clip


    r = bench.run_one(


        "NBrel sur sapphire",


        str(input_path),


        phase2=True,


        lambda_min_cut=args.lambda_min,


        clip_trel=clip,


    )





    out_path = _ROOT / "reports" / "full_domain_nbrel_result.json"


    out_path.parent.mkdir(parents=True, exist_ok=True)


    with out_path.open("w", encoding="utf-8") as f:


        json.dump(r, f, indent=2, ensure_ascii=False, default=str)





    fd = r.get("final_diagnostic_sur_fichier") or {}


    rmse_g = fd.get("rmse_Trel_global_sur_fichier")


    d_nm = r.get("phase2_thickness_nm") or r.get("phase1_thickness_nm")





    print("")


    print("=" * 60)


    print("  NBrel - chaine complete TLU + IR (tout le domaine fichier)")


    print("=" * 60)


    print(f"  Fichier      : {input_path.resolve(strict=False)}")


    print(f"  lambda_min   : {args.lambda_min}")


    print(f"  clip T_rel   : {clip}")


    print(f"  Ep. finale   : {d_nm:.2f} nm" if d_nm is not None else "  Ep. : N/A")


    print(f"  RMSE moteur p1: {r.get('phase1_rmse_reported_moteur', 'N/A')}")


    print(f"  RMSE moteur p2: {r.get('phase2_rmse_reported_moteur', 'N/A')}")


    print("-" * 60)


    print(f"  RMSE T_rel GLOBALE (tous points mesure) : {rmse_g}")


    print("    -> compare |T_pred - T_meas| / T_rel sur la grille export df_results")


    if fd.get("bands_nm"):


        print("  Par bandes (diagnostic) :")


        for b in fd["bands_nm"]:


            print(f"    {b.get('name')}: RMSE={b.get('rmse_Trel')}  {b.get('nm')}")


    if fd.get("pire_point"):


        pp = fd["pire_point"]


        print(f"  Pire point : lambda={pp.get('lambda_nm')} nm  |err|={pp.get('abs_err')}")


    print("=" * 60)


    print(f"  JSON detail : {out_path}")


    print("")





    if "error_phase1" in r or "error_phase2" in r:


        return 1


    return 0








if __name__ == "__main__":


    sys.exit(main())


