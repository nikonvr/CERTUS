"""INDEX must hand the objective a substrate k aligned with the fitted wavelengths (audit 2026-11-15, M-L5a).

`k_sub_data` is built on the FULL file grid; `_prepare_run_inputs` masks the wavelengths to [lambda_min, lambda_max]
and used to pass `k_sub_data` whole, so the objective read k_sub[i] with the masked index i: with lambda_min raised by
150 nm, the k of 350 nm was used at 500 nm and the modelled T moved by up to 0.50.
"""

import logging
from types import SimpleNamespace

import numpy as np
import pandas as pd

from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy
from CERTUS_INDEX import DataType, OptimizationConfig


def test_the_objective_gets_the_substrate_k_of_the_fitted_wavelengths() -> None:
    lam = np.arange(250.0, 1001.0, 1.0)
    k_sub_full = 1e-3 * np.exp(-(lam - 250.0) / 80.0)
    df = pd.DataFrame({"lambda": lam, "T": np.full(lam.shape, 0.5)})
    cfg = OptimizationConfig(
        target_data=df,
        data_type=DataType.TRANSMISSION,
        substrate="Sapphire (Al2O3)",
        thickness_min=10.0,
        thickness_max=500.0,
        lambda_min=400.0,
        lambda_max=1000.0,
        k_sub_data=k_sub_full,
        substrate_thickness_nm=0.5e6,
    )
    worker = SimpleNamespace(logger=logging.getLogger("test"), thickness_initial=None)
    wls, _n_sub, _t, _r, _ex, obj = IndexOptimizationStrategy._prepare_run_inputs(worker, cfg)
    assert obj.k_sub_data.shape == wls.shape
    np.testing.assert_array_equal(obj.k_sub_data, k_sub_full[np.isin(lam, wls)])
