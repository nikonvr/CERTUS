"""The parameter budget of a reverse-engineering result: what the fit was allowed to move, block by block.

Ported from ``certus_re`` (Zenodo, concept DOI 10.5281/zenodo.22756244, ``dof.count_free_parameters``). A residual alone
says nothing about an inversion: enough released parameters fit anything, and an index correction that improves a fit
is the very quantity one claims to measure. Every block is listed, the held ones too, so that a zero is never ambiguous
between "not used" and "held on purpose", and the number that limits an inversion is derived from it: the data points
per released parameter.

The count is read off the result itself (which blocks it carries) and off the switches that pin a block inside the
solver (``re_refine_h`` / ``re_refine_l`` pin the knots of a material at zero, with the default of the bounds builder,
``_build_p2_bounds``). It describes the result as fitted, not the run: a phase-1 result released the thicknesses alone
even when later phases released more.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _block(name: str, count: int, status: str) -> dict[str, Any]:
    return {"name": name, "count": int(count), "status": status}


def parameter_budget(result: dict[str, Any], cfg: dict[str, Any], n_data: int | None) -> dict[str, Any]:
    """Blocks released to produce ``result``, their total, and the data points per released parameter.

    ``n_data`` is the number of data residuals (the thickness uncertainty counts them); ``None`` when unknown.
    """
    ep = np.asarray(result.get("ep", []), dtype=np.float64).ravel()
    dh = np.asarray(result.get("re_dH_knots", []), dtype=np.float64).ravel()
    dl = np.asarray(result.get("re_dL_knots", []), dtype=np.float64).ravel()
    has_splines = dh.size > 0 and dl.size > 0
    refine_h = bool(cfg.get("re_refine_h", False))
    refine_l = bool(cfg.get("re_refine_l", False))
    blocks = [_block("layer thicknesses", ep.size, "released")]
    for name, knots, refined in (("index correction H", dh, refine_h), ("index correction L", dl, refine_l)):
        if not has_splines:
            blocks.append(_block(name, 0, "tabulated indices, no correction"))
        elif refined:
            blocks.append(_block(name, knots.size, f"released, {knots.size} spline knots on Re(n)"))
        else:
            blocks.append(_block(name, 0, "held at zero"))
    node_free = has_splines and (refine_h or refine_l)
    blocks.append(_block("spline node lambda2", 1 if node_free else 0, "released" if node_free else "held"))
    if result.get("re_sub_cauchy_a0") is not None:
        blocks.append(_block("substrate Cauchy", 3, "released"))
    else:
        blocks.append(_block("substrate Cauchy", 0, "tabulated substrate"))
    knots_deg = np.asarray(result.get("re_p4_beam_ap_knots_deg", []), dtype=np.float64).ravel()
    if knots_deg.size == 0:
        blocks.append(_block("beam aperture", 0, "not modelled (no cone average)"))
    else:
        blocks.append(_block("beam aperture", knots_deg.size, f"released, {knots_deg.size} plateaus in lambda"))
    n_free = sum(b["count"] for b in blocks)
    per_parameter = float(n_data) / n_free if n_data is not None and n_free else None
    return {
        "blocks": blocks,
        "n_free_parameters": int(n_free),
        "n_data_points": None if n_data is None else int(n_data),
        "points_per_free_parameter": per_parameter,
    }


def attach_parameter_budget(top_result: dict[str, Any] | None, cfg: dict[str, Any], logger: Any) -> None:
    """Store the budget of the retained result under ``parameter_budget`` and log it, block by block."""
    if top_result is None:
        return
    uncertainty = top_result.get("thickness_uncertainty") or {}
    budget = parameter_budget(top_result, cfg, uncertainty.get("n_data"))
    top_result["parameter_budget"] = budget
    per = budget["points_per_free_parameter"]
    logger.info(
        "RE parameter budget of the retained result: %d free parameters, %s data points, %s per free parameter",
        budget["n_free_parameters"],
        "?" if budget["n_data_points"] is None else budget["n_data_points"],
        "?" if per is None else f"{per:.1f}",
    )
    for block in budget["blocks"]:
        logger.info("RE   %-22s %3d  %s", block["name"], block["count"], block["status"])
