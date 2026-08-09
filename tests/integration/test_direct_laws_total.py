"""Ancien test d'optimisation directe Cauchy + Lorentz (run_continuous_optimization).



This PGlobal 19D path and the analytical laws overlay have been removed from the project.

The recommended pipeline is adaptive spline + sigma mesh polish (PWL/cubic spline).

"""



import logging

import os

import sys
from pathlib import Path



sys.path.insert(0, str(Path(__file__).resolve().parents[2]))



from certus.core.certus_core import setup_logging





def run_direct_test() -> None:

    setup_logging(log_file="logs/test_direct_laws_total.log")

    logger = logging.getLogger("CERTUS")

    logger.warning(

        "test_direct_laws_total : run_continuous_optimization supprimé - "

        "utiliser la GUI INDEX_SPLINE ou worker_spline_optimization."

    )





if __name__ == "__main__":

    run_direct_test()

