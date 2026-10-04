"""The front stack of the RE snapshot workbook, with what the retained result says about its thicknesses.

While the stack holds the thicknesses of the retained RE result, each layer carries its one-sigma uncertainty (from the
data rows alone, ``certus_re_uncertainty``) and the parameter budget of the fit follows the stack
(``certus_re_budget``). Once a thickness is edited the bars no longer describe the stack, and neither is written.
"""

from __future__ import annotations

from typing import Any

import numpy as np

SIGMA_HEADER = "sigma(d) (nm), 1 sigma, data rows only"
BUDGET_TITLE = "PARAMETER BUDGET (retained RE result)"


def retained_report_for(report: dict[str, Any] | None, ep: Any) -> dict[str, Any] | None:
    """``report`` (remembered at the end of the run, with its thicknesses) if the stack still holds them, else ``None``."""
    if not report:
        return None
    current = np.asarray(ep, dtype=np.float64).ravel()
    return report if np.array_equal(current, report["ep"]) else None


def write_front_stack(ws: Any, front_stack: list, ep: Any, retained: dict[str, Any] | None) -> None:
    """The front stack rows and its total thickness, then the sigma column and the budget when ``retained`` is given."""
    sigma = list((retained.get("thickness_uncertainty") or {}).get("sigma_nm") or []) if retained else []
    ws.append(["#", "Material", "QWOT", "Thickness (nm)", "Variable"] + ([SIGMA_HEADER] if sigma else []))
    for i, layer in enumerate(front_stack):
        row = [i + 1, layer.mat, layer.qwot, ep[i] if i < len(ep) else 0, "Yes" if layer.var else "No"]
        if sigma:
            row.append(float(sigma[i]) if i < len(sigma) and np.isfinite(sigma[i]) else "n/a")
        ws.append(row)
    if len(ep) > 0:
        ws.append([])
        ws.append(["Total Thickness (nm)", float(np.sum(ep))])
    budget = retained.get("parameter_budget") if retained else None
    if budget:
        ws.append([])
        ws.append([BUDGET_TITLE])
        ws.append(["Block", "Free parameters", "Status"])
        for block in budget["blocks"]:
            ws.append([block["name"], block["count"], block["status"]])
        ws.append(["Total free parameters", budget["n_free_parameters"]])
        ws.append(["Data points", budget["n_data_points"]])
        ws.append(["Points per free parameter", budget["points_per_free_parameter"]])
