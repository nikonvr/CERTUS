"""Thickness uncertainties of a reverse-engineering result, read off the Jacobian of the data alone.

Ported from ``certus_re`` (Zenodo, concept DOI 10.5281/zenodo.22756244, ``solve._covariance``): the covariance of the
least-squares solution, ``s^2 (J^T J)^+``, with ``J`` the Jacobian of the weighted DATA residuals. The regularisation
rows of the RE objective (QWOT channel, Tikhonov on the spline knots, index envelope) select the solution but are not
measurements; counting them would shrink the error bars by the weight of a choice.

The inverse is taken through the singular values. A direction the data do not constrain is reported as such, and the
thicknesses it involves get no error bar (``nan``) rather than one that is too small. ``s^2 = chi^2 / (m - n)`` widens
the bars when the model does not reproduce the data within their weights -- the honest direction -- and is reported
next to them rather than folded in silently.

What the bars are NOT: the thicknesses vary with the dispersion corrections held at their fitted values, so the bars
are conditional on the indices -- a lower bound when the indices were fitted as well. And finite local bars do not
establish global identifiability.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def least_squares_covariance(
    jac: np.ndarray, residual: np.ndarray, n_parameters: int
) -> tuple[np.ndarray | None, float, int, str]:
    """Covariance ``s^2 (J^T J)^+`` of a weighted least-squares solution, through the SVD of ``J``.

    Returns ``(covariance, s2, n_unconstrained, note)``. A parameter with any weight on a direction the data leave
    free gets ``nan`` in its row and column.
    """
    residual = np.asarray(residual, dtype=np.float64).ravel()
    m = int(residual.size)
    dof = max(m - int(n_parameters), 1)
    scale = float(residual @ residual) / dof
    if jac is None or np.asarray(jac).size == 0:
        return None, scale, int(n_parameters), "no Jacobian available"
    jac = np.asarray(jac, dtype=np.float64)
    _, singular, vt = np.linalg.svd(jac, full_matrices=False)
    threshold = np.finfo(np.float64).eps * max(jac.shape) * (singular[0] if singular.size else 0.0)
    keep = singular > threshold
    v = vt[keep].T
    covariance = scale * (v * (1.0 / singular[keep] ** 2)) @ v.T
    n_dropped = int(np.count_nonzero(~keep)) + max(int(n_parameters) - int(singular.size), 0)
    note = ""
    if n_dropped:
        constrained = np.sum(vt[keep] ** 2, axis=0) if np.any(keep) else np.zeros(int(n_parameters))
        free = (1.0 - constrained) > 1e-10
        covariance[free, :] = np.nan
        covariance[:, free] = np.nan
        note = (
            f"the Jacobian is rank deficient: {n_dropped} of {int(n_parameters)} directions are not constrained "
            f"by the data; the {int(np.count_nonzero(free))} thicknesses they involve get no error bar"
        )
    return covariance, scale, n_dropped, note


def thickness_uncertainty_report(jac: np.ndarray, residual: np.ndarray, thickness_nm: np.ndarray) -> dict[str, Any]:
    """Per-layer one-sigma thickness uncertainty, in nm and relative, with the counts that make it readable."""
    thickness_nm = np.asarray(thickness_nm, dtype=np.float64).ravel()
    n = int(thickness_nm.size)
    m = int(np.asarray(residual).size)
    covariance, scale, n_dropped, note = least_squares_covariance(jac, residual, n)
    if covariance is None:
        sigma = np.full(n, np.nan)
    else:
        diag = np.diag(covariance)
        sigma = np.where(np.isfinite(diag) & (diag >= 0.0), np.sqrt(np.abs(diag)), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        relative = np.where(thickness_nm > 0.0, sigma / thickness_nm, np.nan)
    return {
        "sigma_nm": [float(x) for x in sigma],
        "relative": [float(x) for x in relative],
        "scale_s2": float(scale),
        "n_data": m,
        "n_parameters": n,
        "data_points_per_parameter": float(m) / float(n) if n else float("nan"),
        "unconstrained_directions": int(n_dropped),
        "note": note,
        "conditional_on": "dispersion corrections and beam aperture held at their fitted values",
    }


def thickness_uncertainty_at(
    result: dict[str, Any],
    *,
    mse_grad: Any,
    wt_spectral: np.ndarray,
    correc_nominal: tuple,
    p2_to_correc: Any,
    re_state: dict[str, Any],
) -> dict[str, Any] | None:
    """The report at one RE result: its thicknesses, with its own dispersion corrections and beam aperture.

    The residuals must be those of the model that produced the result. A phase-4 result carries its aperture knots and
    is evaluated with them; any other result is evaluated without the cone average. The shared aperture state is set for
    the evaluation and restored after it. ``None`` when the result cannot be reproduced faithfully (no thicknesses, or
    aperture knots that do not match the context's).
    """
    ep = np.asarray(result.get("ep", []), dtype=np.float64).ravel()
    if ep.size == 0:
        return None
    dh = np.asarray(result.get("re_dH_knots", []), dtype=np.float64).ravel()
    dl = np.asarray(result.get("re_dL_knots", []), dtype=np.float64).ravel()
    if dh.size > 0 and dl.size > 0:
        correc = p2_to_correc(result, result.get("re_sub_cauchy_a0") is not None)
    else:
        correc = correc_nominal
    knots_deg = np.asarray(result.get("re_p4_beam_ap_knots_deg", []), dtype=np.float64).ravel()
    knots_nm = np.asarray(result.get("re_p4_beam_ap_knots_nm", []), dtype=np.float64).ravel()
    state_deg = np.asarray(re_state["re_aperture_knots"], dtype=np.float64)
    state_nm = np.asarray(re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64)
    if knots_deg.size and (knots_deg.size != state_deg.size or (knots_nm.size and knots_nm.size != state_nm.size)):
        return None
    saved = (re_state["is_phase4"], state_deg.copy(), state_nm.copy())
    try:
        re_state["is_phase4"] = bool(knots_deg.size)
        if knots_deg.size:
            re_state["re_aperture_knots"][:] = knots_deg
            if knots_nm.size:
                re_state["re_p4_beam_knots_lam_nm"][:] = knots_nm
        out = mse_grad(ep, wt_spectral, True, correc, return_residuals=True, data_only=True)
    finally:
        re_state["is_phase4"] = saved[0]
        re_state["re_aperture_knots"][:] = saved[1]
        re_state["re_p4_beam_knots_lam_nm"][:] = saved[2]
    if out is None or len(out) < 4:
        return None
    return thickness_uncertainty_report(out[3], out[2], ep)


def attach_thickness_uncertainty(top_result: dict[str, Any] | None, compute: Any, logger: Any) -> None:
    """Compute the report at the retained result, store it under ``thickness_uncertainty`` and log it, layer by layer."""
    if top_result is None or compute is None:
        return
    try:
        report = compute(top_result)
    except (ArithmeticError, ValueError, np.linalg.LinAlgError):
        logger.warning("RE thickness uncertainty: not computed (numerical failure).", exc_info=True)
        return
    if report is None:
        logger.info("RE thickness uncertainty: not computed (the retained result cannot be re-evaluated as fitted).")
        return
    top_result["thickness_uncertainty"] = report
    logger.info(
        "RE thickness uncertainty, 1 sigma, from the data rows alone (%s): s^2=%.4g, %d data points for %d "
        "thicknesses (%.1f per thickness)%s",
        report["conditional_on"], report["scale_s2"], report["n_data"], report["n_parameters"],
        report["data_points_per_parameter"], f"; {report['note']}" if report["note"] else "",
    )
    ep = np.asarray(top_result.get("ep", []), dtype=np.float64).ravel()
    for i, (d, s) in enumerate(zip(ep, report["sigma_nm"], strict=False), start=1):
        logger.info("RE   layer %d: %.3f nm +/- %.3f nm", i, float(d), float(s))
