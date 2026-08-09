"""

Test pipeline CERTUS sur mesure R,T sur substrat sapphire (Excel).

Default: example/NB on sapphire.xlsx (otherwise path as argument).

  Phase 1: TLU (like the app - two stages if lambda_max>2500 and lambda_min<2200).

  --full: continues phase 2 “Global IR” (like the app after the dialogue).



Without --full: stop after phase 1 (fast, enough to validate the file).

"""



from __future__ import annotations



import argparse

import logging

from pathlib import Path

import sys

import time



import numpy as np

import pandas as pd

from PyQt6.QtCore import QEventLoop, QThread, Qt

from PyQt6.QtWidgets import QApplication



#Before CERTUS import: QApplication + strong reference (otherwise QEventLoop without QCoreApplication)

_QT_APP = QApplication.instance() or QApplication([])



_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(_ROOT))



from CERTUS_INDEX import (  # noqa: E402

    IRGlobalModelWorker,

    OptimizationConfig,

    OptimizationWorker,

    DataType,

    substrateMode,

)



logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

logger = logging.getLogger("test_pipeline")



_DEFAULT_XLSX = _ROOT / "example" / "NB sur sapphire.xlsx"

_FALLBACK_XLSX = _ROOT / "example" / "RTNBrel-sapphire.xlsx"





def _load_rtnb_excel(path: str) -> pd.DataFrame:

    """lambda, R, T - scale 0-1 (divided by 100 if data is in %)."""

    df = pd.read_excel(path, header=0, engine="openpyxl")

    if df.shape[1] < 3:

        raise ValueError(f"{path}: besoin d'au moins 3 colonnes (lambda, R, T)")

    df = df.iloc[:, :3].copy()

    df.columns = ["lambda", "R", "T"]

    for c in ("R", "T"):

        col = pd.to_numeric(df[c], errors="coerce")

        if len(col) and np.nanmax(col) > 1.1:

            col = col / 100.0

        df[c] = col

    df["lambda"] = pd.to_numeric(df["lambda"], errors="coerce")

    df = df.dropna(subset=["lambda", "R", "T"])

    return df.sort_values("lambda").reset_index(drop=True)





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



    #Slots executed on the QEventLoop thread (QueuedConnection required here)

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





def main() -> int:

    ap = argparse.ArgumentParser(description="Test NB / sapphire.xlsx dans CERTUS INDEX")

    ap.add_argument(

        "path",

        nargs="?",

        default=None,

        help="Fichier Excel (3 colonnes : lambda nm, R, T). Défaut: example/NB sur sapphire.xlsx",

    )

    ap.add_argument(

        "--full",

        action="store_true",

        help="Enchaîner phase 2 IR (Sellmeier+k, long)",

    )

    ap.add_argument(

        "--no-fallback",

        action="store_true",

        help="Ne pas utiliser RTNBrel-sapphire.xlsx si le fichier demandé est absent",

    )

    args = ap.parse_args()



    xlsx = Path(args.path) if args.path else _DEFAULT_XLSX

    if not xlsx.is_file():

        if not args.no_fallback and _FALLBACK_XLSX.is_file():

            logger.warning(

                "Fichier absent: %s - utilisation du jeu de référence %s",

                xlsx,

                _FALLBACK_XLSX,

            )

            xlsx = _FALLBACK_XLSX

        else:

            logger.error("File not found: %s", xlsx)

            return 2



    abspath = str(xlsx.resolve(strict=False))

    logger.info("Measurement file: %s", abspath)



    df_full = _load_rtnb_excel(str(xlsx))

    lam_min = float(df_full["lambda"].min())

    lam_max = float(df_full["lambda"].max())

    logger.info(

        "Données: %d pts, lambda ∈ [%.0f, %.0f] nm",

        len(df_full),

        lam_min,

        lam_max,

    )



    two_stage = lam_max > 2500.0 and lam_min < 2200.0

    lambda_max_fit = 2200.0 if two_stage else None

    if two_stage:

        logger.info(

            "Pipeline deux étages (TLU <=2200 nm puis IR) - comme CERTUS INDEX."

        )

    else:

        logger.info("A single TLU stage over the entire selected range.")



    config = OptimizationConfig(

        target_data=df_full,

        substrate="Sapphire (Al2O3)",

        substrate_mode=substrateMode.STANDARD,

        data_type=DataType.BOTH,

        thickness_min=2000.0,

        thickness_max=4000.0,

        lambda_min=lam_min,

        lambda_max=lam_max,

        source_file=abspath,

        use_normalized=True,

        weight_T=1.0,

        weight_R=1.0,

        high_precision=False,

        lambda_max_fit=lambda_max_fit,

    )



    worker1 = OptimizationWorker(config, logger=logger)

    tlu_res, err1, elapsed1 = _run_worker(worker1)

    if err1:

        logger.error("Phase 1: %s", err1)

        return 1



    rmse1 = float(np.sqrt(tlu_res.final_mse)) if tlu_res.final_mse >= 0 else 0.0

    logger.info(

        "Phase 1 (TLU): %.1f s | RMSE=%.6f | d=%.1f nm",

        elapsed1,

        rmse1,

        tlu_res.optimal_thickness,

    )



    if not two_stage or not args.full:

        logger.info(

            "Terminé (--full non demandé ou plage sans deux étages). "

            "Fichier Excel chargé et phase 1 OK."

        )

        return 0



    #Phase 2: same preparation as CertusIndexApp._on_tlu_constrained_finished (without dialog)

    tlu_res.config.lambda_max_fit = None

    tlu_res.config.target_data = df_full.copy()

    tlu_res.config.lambda_min = lam_min

    tlu_res.config.lambda_max = lam_max



    worker2 = IRGlobalModelWorker(tlu_res.config, tlu_res, logger=logger)

    final_res, err2, elapsed2 = _run_worker(worker2)

    if err2:

        logger.error("Phase 2 IR: %s", err2)

        return 1



    rmse2 = float(np.sqrt(final_res.final_mse)) if final_res.final_mse >= 0 else 0.0

    logger.info("=" * 60)

    logger.info(

        "Phase 2 (IR global): %.1f s | RMSE=%.6f | d=%.1f nm",

        elapsed2,

        rmse2,

        final_res.optimal_thickness,

    )

    logger.info("=" * 60)



    THRESHOLD = 0.05

    if rmse2 >= THRESHOLD:

        logger.warning("RMSE phase 2 >= %.3f (seuil indicatif)", THRESHOLD)

    return 0





if __name__ == "__main__":

    sys.exit(main())

