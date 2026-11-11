"""CERTUS-INDEX-SPLINE - the static helpers of the window, as plain functions: what a result dictionary says of the fit, how a mesh of knots and its changes are written in the log, the grids. The mixins of the window call them here; the window keeps each one as a static method of the same name, the very function (moved out of certus_index_spline_eventsextras_mixin.py and certus_index_spline_manualmesh_mixin.py). A leaf of the group: it imports no module of the window."""

from __future__ import annotations

import numpy as np


def _rmse_from_result_dict(d: dict) -> float:
    """RMSE displayable for comparison (priority to  rmse  key, else ?MSE)."""

    r = d.get("rmse")

    if r is not None and np.isfinite(float(r)):
        return float(r)

    m = float(d.get("mse", float("nan")))

    if np.isfinite(m):
        return float(np.sqrt(max(m, 0.0)))

    return float("inf")
