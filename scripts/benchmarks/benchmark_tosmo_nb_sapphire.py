"""


Benchmark INDEX : deux jeux T_rel (Nb₂O₅ ~2950 nm sur sapphire), pipeline TLU + IR.


Fichiers : example/IR/tosmo/H800-sapphire-TrelNB.xlsx, NBrel sur sapphire .xlsx


"""





from __future__ import annotations





import json


import logging


from pathlib import Path


import sys


import time





import numpy as np


import pandas as pd


from PyQt6.QtCore import QEventLoop, QThread, Qt


from PyQt6.QtWidgets import QApplication





# Référence obligatoire : sans elle, le wrapper PyQt peut être GC -> plus de QCoreApplication pour QEventLoop


_QT_APP: QApplication | None = QApplication.instance() or QApplication([])





_ROOT = Path(__file__).resolve().parents[2]


sys.path.insert(0, str(_ROOT))





from CERTUS_INDEX import (  # noqa: E402


    IRGlobalModelWorker,


    OptimizationConfig,


    OptimizationWorker,


    DataType,


    substrateMode,


    SUBSTRATES,


    get_n_substrate_array_by_id,


)


from _certus_physics_impl import (  # noqa: E402


    calculate_bare_substrate_RT,


    calculate_RT_single_layer_backside_array,


)





logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


logger = logging.getLogger("benchmark_tosmo")





FILES = [


    (


        "H800-sapphire-TrelNB",


        str(_ROOT / "example" / "IR" / "tosmo" / "H800-sapphire-TrelNB.xlsx"),


    ),


    (


        "NBrel sur sapphire",


        str(_ROOT / "example" / "IR" / "tosmo" / "NBrel sur sapphire .xlsx"),


    ),


]








def load_trel(


    path: str,


    lambda_min: float | None = None,


    clip_trel: bool = False,


) -> pd.DataFrame:


    df = pd.read_excel(path, header=0, engine="openpyxl")


    if df.shape[1] < 2:


        raise ValueError(f"{path}: besoin lambda + T_rel")


    df = df.iloc[:, :2].copy()


    df.columns = ["lambda", "T"]


    t = pd.to_numeric(df["T"], errors="coerce")


    if len(t) and np.nanmax(t) > 1.1:


        t = t / 100.0


    df["T"] = t


    df["lambda"] = pd.to_numeric(df["lambda"], errors="coerce")


    df = df.dropna(subset=["lambda", "T"])


    df = df.sort_values("lambda").reset_index(drop=True)


    if lambda_min is not None:


        df = df[df["lambda"] >= float(lambda_min)].reset_index(drop=True)


    if clip_trel:


        df = df.copy()


        df["T"] = df["T"].clip(0.0, 1.0)


    return df








def data_quality_Trel(df: pd.DataFrame) -> dict:


    """Signale T_rel hors [0,1] (physiquement suspects pour T/T_sub)."""


    t = df["T"].to_numpy()


    n_tot = len(t)


    n_hi = int(np.sum(t > 1.0 + 1e-6))


    n_lo = int(np.sum(t < 0.0 - 1e-6))


    t_max = float(np.nanmax(t)) if n_tot else float("nan")


    t_min = float(np.nanmin(t)) if n_tot else float("nan")


    return {


        "n_points": n_tot,


        "Trel_gt_1_count": n_hi,


        "Trel_lt_0_count": n_lo,


        "Trel_max": t_max,


        "Trel_min": t_min,


        "warning": n_hi > 0 or n_lo > 0,


    }








def _run_worker(worker):


    out = [None]


    err = [None]


    loop = QEventLoop()


    thr = QThread()


    worker.moveToThread(thr)


    thr.started.connect(worker.run)





    def _ok(res):


        out[0] = res


        loop.quit()





    def _bad(msg):


        err[0] = msg


        loop.quit()





    worker.finished.connect(_ok, Qt.ConnectionType.QueuedConnection)


    worker.error.connect(_bad, Qt.ConnectionType.QueuedConnection)


    worker.finished.connect(thr.quit)


    worker.finished.connect(worker.deleteLater)


    thr.finished.connect(thr.deleteLater)


    t0 = time.time()


    thr.start()


    loop.exec()


    thr.wait(600_000)


    return out[0], err[0], time.time() - t0








def _T_rel_pred_on_wavelengths(res, wls_tgt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:


    """T_rel prédit aux longueurs d'onde demandées (interp nk depuis df_results)."""


    df = res.df_results


    wl0 = df["lambda"].to_numpy(dtype=np.float64)


    n0 = df["n_calc"].to_numpy()


    k0 = df["k_calc"].to_numpy()


    n_c = np.interp(wls_tgt, wl0, n0, left=n0[0], right=n0[-1])


    k_c = np.interp(wls_tgt, wl0, k0, left=k0[0], right=k0[-1])


    sub_id = SUBSTRATES[res.config.substrate]["id"]


    n_sub = get_n_substrate_array_by_id(sub_id, wls_tgt)


    _, t_calc = calculate_RT_single_layer_backside_array(


        wls_tgt, n_c, k_c, res.optimal_thickness, n_sub


    )


    t_sub = calculate_bare_substrate_RT(wls_tgt, n_sub)


    with np.errstate(divide="ignore", invalid="ignore"):


        t_rel = np.where(t_sub > 1e-6, t_calc / t_sub, np.nan)


    return t_rel, t_sub








def diagnose_T_rel(res, df_meas: pd.DataFrame, lambda_max_fit: float | None) -> dict:


    """


    RMSE global + par bandes sur les **points du fichier** (pas la grille interne).


    Aide à voir si la dégradation vient de l’IR (>2200) ou du fit TLU (<=2200).


    """


    wls = df_meas["lambda"].to_numpy(dtype=np.float64)


    tgt = df_meas["T"].to_numpy(dtype=np.float64)


    pred, _ = _T_rel_pred_on_wavelengths(res, wls)


    err = pred - tgt


    m = np.isfinite(pred) & np.isfinite(tgt)


    if not np.any(m):


        return {"error": "no_valid_points"}





    def _rmse(mask: np.ndarray) -> tuple[float, int]:


        mm = m & mask


        n = int(np.sum(mm))


        if n < 3:


            return float("nan"), n


        return float(np.sqrt(np.mean((pred[mm] - tgt[mm]) ** 2))), n





    lam_min, lam_max = float(wls.min()), float(wls.max())


    bands: list[dict] = []





    # Fenêtre réellement ajustée en phase 1 (TLU) : lambda <= 2200 dans la plage fichier


    tlu_hi = min(2200.0, lam_max)


    tlu_lo = lam_min


    if tlu_lo < tlu_hi:


        rmse_b, nb = _rmse((wls >= tlu_lo) & (wls <= tlu_hi))


        bands.append(


            {


                "name": "bande_TLU_phase1",


                "nm": [round(tlu_lo, 1), round(tlu_hi, 1)],


                "rmse_Trel": rmse_b,


                "n_pts": nb,


                "note": "coût PGLOBAL phase 1 si deux étages (lambda<=2200)",


            }


        )





    if lam_max > 2200.0:


        rmse_b, nb = _rmse(wls > 2200.0)


        bands.append(


            {


                "name": "IR_seulement_gt_2200",


                "nm": [2200.0, round(lam_max, 1)],


                "rmse_Trel": rmse_b,


                "n_pts": nb,


                "note": "surtout modèle Sellmeier+k phase 2",


            }


        )





    if lam_max > 2500.0:


        rmse_b, nb = _rmse(wls > 2500.0)


        bands.append(


            {


                "name": "IR_long_gt_2500",


                "nm": [2500.0, round(lam_max, 1)],


                "rmse_Trel": rmse_b,


                "n_pts": nb,


            }


        )





    # Comparaison directe H800 vs NBrel sur un tronçon commun


    common_lo, common_hi = max(1000.0, lam_min), min(2200.0, lam_max)


    if common_lo < common_hi:


        rmse_b, nb = _rmse((wls >= common_lo) & (wls <= common_hi))


        bands.append(


            {


                "name": "troncon_commun_1000_2200_si_disponible",


                "nm": [round(common_lo, 1), round(common_hi, 1)],


                "rmse_Trel": rmse_b,


                "n_pts": nb,


                "note": "compare H800 et NBrel sur la même plage",


            }


        )





    # Bande UV courte (mesures fiables typiquement 350-1000 nm)


    uv_lo, uv_hi = max(350.0, lam_min), min(1000.0, lam_max)


    if uv_lo < uv_hi:


        rmse_b, nb = _rmse((wls >= uv_lo) & (wls <= uv_hi))


        bands.append(


            {


                "name": "uv_350_1000_sur_fichier",


                "nm": [round(uv_lo, 1), round(uv_hi, 1)],


                "rmse_Trel": rmse_b,


                "n_pts": nb,


                "note": "RMSE T_rel sur points du fichier dans [max(350,lambda_min), min(1000,lambda_max)]",


            }


        )





    rmse_global = float(np.sqrt(np.mean((pred[m] - tgt[m]) ** 2)))


    i_worst = int(np.nanargmax(np.abs(err)))


    worst = {


        "lambda_nm": round(float(wls[i_worst]), 2),


        "abs_err": round(float(abs(err[i_worst])), 6),


        "T_meas": round(float(tgt[i_worst]), 6),


        "T_pred": round(float(pred[i_worst]), 6),


    }





    return {


        "rmse_Trel_global_sur_fichier": rmse_global,


        "mean_abs_err": float(np.mean(np.abs(err[m]))),


        "max_abs_err": float(np.max(np.abs(err[m]))),


        "lambda_max_fit_phase1": lambda_max_fit,


        "bands_nm": bands,


        "pire_point": worst,


    }








def run_one(


    label: str,


    path: str,


    phase2: bool,


    lambda_min_cut: float | None,


    clip_trel: bool,


) -> dict:


    abspath = str(Path(path).resolve())


    df = load_trel(path, lambda_min=lambda_min_cut, clip_trel=clip_trel)


    lam_min = float(df["lambda"].min())


    lam_max = float(df["lambda"].max())


    two_stage = lam_max > 2500.0 and lam_min < 2200.0


    lambda_max_fit = 2200.0 if two_stage else None





    q = data_quality_Trel(df)


    if q["warning"]:


        logger.warning(


            "[%s] Qualité T_rel: %d points >1, %d points <0 (max=%.4f min=%.4f) - "


            "RMSE et épaisseur peuvent être faussés.",


            label,


            q["Trel_gt_1_count"],


            q["Trel_lt_0_count"],


            q["Trel_max"],


            q["Trel_min"],


        )





    logger.info(


        "[%s] %d pts, lambda∈[%.0f, %.0f] nm | deux étages=%s",


        label,


        len(df),


        lam_min,


        lam_max,


        two_stage,


    )





    config = OptimizationConfig(


        target_data=df,


        data_type=DataType.TRANSMISSION,


        substrate="Sapphire (Al2O3)",


        substrate_mode=substrateMode.STANDARD,


        thickness_min=2500.0,


        thickness_max=3400.0,


        lambda_min=lam_min,


        lambda_max=lam_max,


        source_file=abspath,


        use_normalized=True,


        weight_T=1.0,


        weight_R=1.0,


        high_precision=False,


        lambda_max_fit=lambda_max_fit,


    )





    w1 = OptimizationWorker(config, logger=logger)


    tlu_res, err1, t1 = _run_worker(w1)


    if err1:


        return {"label": label, "error_phase1": err1}





    rmse1 = float(np.sqrt(tlu_res.final_mse)) if tlu_res.final_mse >= 0 else 0.0


    d1 = float(tlu_res.optimal_thickness)


    diag1 = diagnose_T_rel(tlu_res, df, lambda_max_fit)





    out = {


        "label": label,


        "file": abspath,


        "data_quality_Trel": q,


        "lambda_min_cut_nm": lambda_min_cut,


        "clip_trel_0_1": clip_trel,


        "phase1_rmse_reported_moteur": rmse1,


        "phase1_diagnostic_sur_fichier": diag1,


        "phase1_thickness_nm": d1,


        "phase1_seconds": round(t1, 1),


    }





    if not phase2 or not two_stage:


        out["note"] = "phase2_skipped" if not phase2 else "single_stage_no_ir"


        out["final_diagnostic_sur_fichier"] = diag1


        return out





    tlu_res.config.lambda_max_fit = None


    tlu_res.config.target_data = df.copy()


    tlu_res.config.lambda_min = lam_min


    tlu_res.config.lambda_max = lam_max





    w2 = IRGlobalModelWorker(tlu_res.config, tlu_res, logger=logger)


    final_res, err2, t2 = _run_worker(w2)


    if err2:


        out["error_phase2"] = err2


        return out





    rmse2_rep = float(np.sqrt(final_res.final_mse)) if final_res.final_mse >= 0 else 0.0


    diag2 = diagnose_T_rel(final_res, df, None)


    out.update(


        {


            "phase2_rmse_reported_moteur": rmse2_rep,


            "phase2_diagnostic_sur_fichier": diag2,


            "phase2_thickness_nm": float(final_res.optimal_thickness),


            "phase2_seconds": round(t2, 1),


            "final_diagnostic_sur_fichier": diag2,


        }


    )


    return out








def prescan_nbrel(path: str) -> list[dict]:


    """


    Sans optimisation : qualité des données NBrel pour chaque coupe (lambda_min, clip).


    Permet de choisir quels essais lancer avant PGLOBAL.


    """


    rows: list[dict] = []


    lambda_mins = [None, 400.0, 500.0, 600.0, 800.0, 1000.0]


    for lm in lambda_mins:


        for clip in (False, True):


            df = load_trel(path, lambda_min=lm, clip_trel=clip)


            if len(df) == 0:


                continue


            w = df["lambda"].to_numpy(dtype=np.float64)


            q = data_quality_Trel(df)


            n_uv = int(np.sum((w >= 350.0) & (w <= 1000.0)))


            rows.append(


                {


                    "lambda_min_cut_nm": lm,


                    "clip_trel_0_1": clip,


                    "n_pts": len(df),


                    "lambda_nm_range": [float(w.min()), float(w.max())],


                    "n_pts_band_350_1000": n_uv,


                    "Trel_warning": q["warning"],


                    "Trel_gt_1_count": q["Trel_gt_1_count"],


                }


            )


    return rows








def main() -> int:


    import argparse





    ap = argparse.ArgumentParser()


    ap.add_argument(


        "--phase1-only",


        action="store_true",


        help="TLU seulement (bande utile <=2200 nm si spectre large)",


    )


    ap.add_argument(


        "--lambda-min",


        type=float,


        default=None,


        metavar="NM",


        help="Couper les lambda plus petits (ex. 1000 pour aligner NBrel sur H800)",


    )


    ap.add_argument(


        "--clip-trel",


        action="store_true",


        help="Contraint T_rel dans [0,1] avant fit (points >1 ou <0)",


    )


    ap.add_argument(


        "--only-nbrel",


        action="store_true",


        help="Ne lancer que NBrel sur sapphire .xlsx",


    )


    ap.add_argument(


        "--prescan",


        action="store_true",


        help="NBrel uniquement : tableau statistique (coupe lambda, clip) sans PGLOBAL",


    )


    ap.add_argument(


        "--search-phase1",


        action="store_true",


        help="NBrel : enchaîne des essais phase 1 jusqu'à RMSE < seuil (voir --target-rmse)",


    )


    ap.add_argument(


        "--target-rmse",


        type=float,


        default=0.04,


        metavar="X",


        help="Seuil pour --search-phase1 (RMSE global sur fichier, défaut 0.04)",


    )


    args = ap.parse_args()


    phase2 = not args.phase1_only





    file_list = FILES


    if args.only_nbrel:


        file_list = [FILES[1]]





    if args.prescan or args.search_phase1:


        label, path = FILES[1]


        if not Path(path).is_file():


            logger.error("Introuvable: %s", path)


            return 1


        if args.prescan:


            rows = prescan_nbrel(path)


            print("\n--- PRESCAN NBrel (aucun PGLOBAL) ---\n")


            for r in rows:


                print(json.dumps(r, ensure_ascii=True))


            print(


                "\nIndice : privilégier une ligne avec assez de points en 350-1000 nm "


                "et peu de T_rel > 1 (ou activer clip sur la ligne correspondante).\n"


            )


            return 0





        if args.search_phase1:


            # Ordre : cas physiques plausibles d’abord, coupes plus agressives ensuite


            trials: list[tuple[float | None, bool, str]] = [


                (None, False, "plein spectre, pas de clip"),


                (None, True, "plein spectre, clip [0,1]"),


                (500.0, False, "lambda>=500 nm"),


                (500.0, True, "lambda>=500 nm + clip"),


                (800.0, False, "lambda>=800 nm"),


                (1000.0, False, "lambda>=1000 nm (comme H800)"),


            ]


            thr = float(args.target_rmse)


            for lm, clip, note in trials:


                logger.info(


                    "========== SEARCH phase1 | %s | lambda_min=%s clip=%s ==========",


                    note,


                    lm,


                    clip,


                )


                r = run_one(


                    label,


                    path,


                    phase2=False,


                    lambda_min_cut=lm,


                    clip_trel=clip,


                )


                if "error_phase1" in r:


                    logger.error("Echec: %s", r["error_phase1"])


                    continue


                diag = r.get("phase1_diagnostic_sur_fichier")


                if not isinstance(diag, dict):


                    continue


                rmse = diag.get("rmse_Trel_global_sur_fichier")


                if rmse is None:


                    continue


                logger.info(


                    "RMSE global fichier = %.6f (seuil %.6f)",


                    float(rmse),


                    thr,


                )


                if float(rmse) <= thr:


                    out_path = _ROOT / "reports" / "benchmark_tosmo_nb_sapphire_search_hit.json"


                    out_path.parent.mkdir(parents=True, exist_ok=True)


                    r["search_note"] = note


                    r["search_target_rmse"] = thr


                    with out_path.open("w", encoding="utf-8") as f:


                        json.dump(r, f, indent=2, ensure_ascii=True)


                    print(f"\nOK : RMSE <= {thr} | JSON : {out_path}\n")


                    print(json.dumps(r, indent=2, ensure_ascii=True))


                    return 0


            print(


                f"\nAucun essai n'a atteint RMSE <= {thr}. "


                "Augmenter --target-rmse ou ajuster manuellement --lambda-min / --clip-trel.\n"


            )


            return 1





    results = []


    for label, path in file_list:


        if not Path(path).is_file():


            logger.error("Introuvable: %s", path)


            results.append({"label": label, "error": "file_not_found"})


            continue


        logger.info("========== %s ==========", label)


        results.append(


            run_one(


                label,


                path,


                phase2=phase2,


                lambda_min_cut=args.lambda_min,


                clip_trel=args.clip_trel,


            )


        )





    suf = "_nbrel" if args.only_nbrel else ""


    if args.lambda_min is not None:


        suf += f"_lmin{int(args.lambda_min)}"


    if args.clip_trel:


        suf += "_clip"


    out_path = _ROOT / "reports" / f"benchmark_tosmo_nb_sapphire{suf}.json"


    out_path.parent.mkdir(parents=True, exist_ok=True)


    with out_path.open("w", encoding="utf-8") as f:


        json.dump(results, f, indent=2, ensure_ascii=False)





    print("\n--- RESUME JSON ---")


    for r in results:


        # Windows cp1252 : éviter UnicodeEncodeError sur la console


        print(json.dumps(r, indent=2, ensure_ascii=True))


    print(f"\nJSON ecrit : {out_path}")





    print("\n--- LECTURE : pourquoi un RMSE peut être moins bon ---\n")


    print_interpretation(results, phase2)





    # Seuil indicatif (RMSE global sur les points du fichier)


    thr = 0.04


    ok = True


    for r in results:


        if "error" in r or "error_phase1" in r:


            ok = False


            continue


        diag = r.get("final_diagnostic_sur_fichier") or r.get("phase1_diagnostic_sur_fichier")


        if not isinstance(diag, dict) or "rmse_Trel_global_sur_fichier" not in diag:


            ok = False


            continue


        if diag["rmse_Trel_global_sur_fichier"] > thr:


            ok = False


    return 0 if ok else 1








def print_interpretation(results: list, phase2: bool) -> None:


    """Compare les deux jeux et indique où chercher la dégradation (TLU vs IR)."""


    by_label = {r.get("label"): r for r in results if "label" in r}





    def _bands(r: dict) -> list | None:


        d = r.get("final_diagnostic_sur_fichier") or r.get("phase1_diagnostic_sur_fichier")


        if not isinstance(d, dict):


            return None


        return d.get("bands_nm")





    def _rmse_band(br: dict, name: str) -> float | None:


        for b in br or []:


            if b.get("name") == name:


                v = b.get("rmse_Trel")


                return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


        return None





    print(


        "• Phase 1 (TLU) n’ajuste que les lambda <= 2200 nm (si spectre > 2500 nm et lambda_min < 2200). "


        "La phase 2 refit n, k en IR avec un modèle global (Sellmeier + k empirique)."


    )


    print(


        "• H800 : pas de données < 1000 nm -> le TLU ne voit que [1000, 2200] nm. "


        "NBrel : mesure dès ~350 nm -> le TLU est mieux contraint ; l’épaisseur et n,k "


        "VIS sont en général plus stables, ce qui aide aussi l’IR."


    )


    if phase2:


        print(


            "• Si le RMSE global explose après la phase 2 alors que la phase 1 était bonne : "


            "regarde IR_seulement_gt_2200 / IR_long_gt_2500 - souvent bruit IR, modèle k, ou "


            "peu de structure dans T(lambda) en IR."


        )





    h = by_label.get("H800-sapphire-TrelNB")


    n = by_label.get("NBrel sur sapphire")


    if h and n and "error_phase1" not in h and "error_phase1" not in n:


        bh, bn = _bands(h), _bands(n)


        r_h = _rmse_band(bh, "troncon_commun_1000_2200_si_disponible")


        r_n = _rmse_band(bn, "troncon_commun_1000_2200_si_disponible")


        if r_h is not None and r_n is not None:


            print(


                f"\n• Sur le tronçon commun ~1000-2200 nm : RMSE H800={r_h:.6f}, NBrel={r_n:.6f}. "


                "Si proches, l’écart global vient surtout d’ailleurs (ex. lambda<1000 sur NBrel ou IR)."


            )


        r_ir_h = _rmse_band(bh, "IR_seulement_gt_2200")


        r_ir_n = _rmse_band(bn, "IR_seulement_gt_2200")


        if phase2 and r_ir_h is not None and r_ir_n is not None:


            print(


                f"• IR lambda>2200 nm (après pipeline complet) : RMSE H800={r_ir_h:.6f}, NBrel={r_ir_n:.6f}."


            )





    print(


        "\nChamp utile : `bands_nm` dans le JSON (RMSE par bande), "


        "`pire_point` = lambda où |T_pred-T_meas| est maximal.\n"


    )








if __name__ == "__main__":


    sys.exit(main())


