"""DESIGN's "RMSE vs layers" tab: the RMSE of each Pareto record against its layer count, with tolerance bars."""

from __future__ import annotations

import logging

import numpy as np

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus_physics import Layer


def update_rmse_layers_plot(ui) -> None:
    """Plot the RMSE of each Pareto record against its layer count, with its tolerance band.

    Point: nominal RMSE of the record. Bar: mean +/- 2 sigma of the RMSE over 200 seeded draws where every
    layer gets a Gaussian thickness error whose 2 sigma is 0.1 % of it plus 0.2 nm (owner's request of
    2026-10-23). Bands are cached per record; normal incidence only.
    """
    points = getattr(ui, "rmse_layers_points", None)
    bars = getattr(ui, "rmse_layers_bars", None)
    if points is None or bars is None or getattr(ui, "oblique_mode", False):
        return
    from certus.core.certus_design_tolerance import design_cost_function, rmse_band

    mats = ui._get_materials()
    wls = np.asarray(ui._get_optim_wls(), dtype=np.float64)
    tgts = [t for t in ui._get_tgts() if t.valid()]
    cache = ui.__dict__.setdefault("_rmse_band_cache", {})
    xs, nominal, mean, two_sigma = [], [], [], []
    for n, rec in sorted(ui.pareto_history.items()):
        ep, table = rec.get("ep_rmse"), rec.get("table_rmse")
        if ep is None or not table or len(table) != len(ep) or not tgts or len(wls) == 0:
            continue
        key = (n, float(rec.get("best_rmse", 0.0)), tuple(np.round(np.asarray(ep, dtype=float), 6)), len(wls))
        if key not in cache:
            try:
                stack = [Layer(row["mat"], row["qw"], row["var"]) for row in table]
                cache[key] = rmse_band(design_cost_function(mats, stack, wls, tgts), np.asarray(ep, dtype=float))
            except (*NUMERICAL_FAULT_EXCEPTIONS, KeyError, StopIteration):
                logging.debug("[DESIGN.rmse_layers] band skipped for N=%s", n, exc_info=True)
                continue
        band = cache[key]
        xs.append(float(n))
        nominal.append(band.nominal)
        mean.append(band.mean)
        two_sigma.append(band.two_sigma)
    x = np.asarray(xs, dtype=float)
    points.setData(x, np.asarray(nominal, dtype=float))
    spread = np.asarray(two_sigma, dtype=float)
    bars.setData(x=x, y=np.asarray(mean, dtype=float), top=spread, bottom=spread)
