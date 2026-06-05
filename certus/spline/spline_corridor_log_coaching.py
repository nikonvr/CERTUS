#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smart-coaching log helpers for INDEX_SPLINE corridor pipeline.

Extracted from ``spline_profile_corridors`` (verbose log-only helpers) to keep
that module focused on numerical/statistical logic.

Public API (re-exported by ``spline_profile_corridors`` for backward
compatibility):

- :func:`log_coaching_uncertainty_parameter_guide`
- :func:`log_coaching_corridor_pipeline_skip_empty`
- :func:`_log_coaching_corridor_outcome`
- :func:`_log_coaching_corridor_failure`
- :func:`_log_coaching_bootstrap_outcome`
- :func:`_log_coaching_reg_sensitivity_outcome`
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # avoid circular import at runtime
    from certus.spline.spline_profile_corridors import ProfileCorridorConfig


log = logging.getLogger("CERTUS")
_LOG_PREFIX = "INDEX_SPLINE [CORRIDORS d]"


def log_coaching_uncertainty_parameter_guide() -> None:
    """Static reminder: when reading logs, map UI / cfg settings to interpretation."""

    log.info("%s ━━━ Parameter guide (acceptance envelope, profiling in d) ━━━", _LOG_PREFIX)

    log.info(
        "%s • RMSE_ref + Delta: with **scientific** corridor (default), RMSE_ref = **spectral_rmse_best_value** "
        "+ polished nominal curve; threshold = RMSE_ref + Delta; no widening towards the solver curve. "
        "Without scientific mode: RMSE_ref = masked spectrum of base curves + legacy widening possible.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • alpha (heuristic mode): RMSE(refit at fixed d) <= alpha x RMSE_opt (ref segments / dict). "
        "Closer to 1 -> narrower d interval. Typ. 1.02-1.10.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • max_span_nm: max |d - d_opt| explored on each side. If both steps hit the limit, "
        "widen span; in alpha mode tighten alpha near d_opt; in RMSE_ref+Delta mode increase Delta if the threshold is too strict.",
        _LOG_PREFIX,
    )

    log.info(
        '%s • step_nm: continuation step. Too large -> risk of "skipping" the threshold boundary; '
        "too small -> more refits (time). Bisection refine (refine_boundary) helps if step > 0.5 nm.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • RMSE Reference: in absolute mode -> always recalculate on base curves (see profile_d_rmse_ref_source). "
        "In alpha / auto-sigma LR mode -> preference ``spectral_rmse_segments`` then dict ``rmse``.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • **Refit at fixed d**: the lines \"RMSE after refit\" measure an n,L re-optimization (corridor budget). "
        "They can exceed the reference depending on the mode; in RMSE_ref+Delta mode the reference is the nominal curve.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • Auto-raising of the threshold (**heuristic alpha mode only**, if enabled): if the central refit exceeds "
        "alpha x RMSE_ref, the effective threshold can rise - see profile_d_auto_relaxed_threshold. **Inactive** in RMSE_ref+Delta.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • LR mode + sigma_T/sigma_R: interpretation close to a likelihood-ratio test if sigma reflects instrumental noise "
        "(T, R fractions). Auto sigma uses the same RMSE reference as the alpha threshold (segments then dict).",
        _LOG_PREFIX,
    )

    log.info(
        "%s • Residual sigma(lambda) (LR): weights points by |residual|; useful for heteroscedastic noise. "
        "``scale`` controls amplitude; floor depends on RMSE_opt.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • n_starts / jitter: if refits often fail (okfits=0) or RMSE looks wrong, raise n_starts or jitter "
        "to escape local minima in fixed-d optimizations.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • Refit budget: ``corridor_profile_d_polish_maxfun`` (INDEX-SPLINE: 2500 default in UI); "
        "None or <=0 = same as run polish_maxfun. Increase if « STOP: … EXCEEDS LIMIT »; "
        "decrease for a faster local d scan.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • Bootstrap: larger B stabilizes quantiles; bootstrap sigma should match real data noise. "
        "block_len > 1 for spectral correlation; quick_refit is faster but can bias if maxfun is too low.",
        _LOG_PREFIX,
    )

    log.info(
        "%s • Regularization scan (REG-SENS): if corridor width varies strongly with ln(k) weight, "
        "uncertainty on n,k is very sensitive to regularization - report a range, not a single value.",
        _LOG_PREFIX,
    )

    log.info("%s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", _LOG_PREFIX)


def log_coaching_corridor_pipeline_skip_empty() -> None:
    """When the pipeline got no corridor: short reminder to tie to [PROFILE] logs / cfg."""

    log.info(
        "%s [COACH] SKIP/EMPTY: see the lines above [CORRIDORS d] (centre_fail, too_few_valid, rmse_meta_invalid). "
        "Leads: RMSE_ref+Delta mode -> increase Delta or refit budget; alpha mode -> relax alpha; LR -> conf/sigma; "
        "max_span_nm, step_nm, n_starts/jitter, polish_maxfun.",
        _LOG_PREFIX,
    )


def _log_coaching_corridor_outcome(
    *,
    pconf: "ProfileCorridorConfig",
    use_lr: bool,
    use_abs_delta: bool = False,
    d0: float,
    d_arr: np.ndarray,
    rm_arr: np.ndarray,
    rmse_opt: float,
    rmse_thresh: float,
    polish_maxfun: int,
    base_result: dict,
) -> None:
    """Interpret profiling outcome and suggest settings (INFO logs)."""

    _ = polish_maxfun  # reserved for future messages (budget shown elsewhere)

    log.info("%s ━━━ Smart Coaching: Result Analysis & Feedback ━━━", _LOG_PREFIX)

    npt = d_arr.size

    dmin = float(np.min(d_arr)) if npt else float("nan")

    dmax = float(np.max(d_arr)) if npt else float("nan")

    width = float(dmax - dmin) if npt and np.isfinite(dmin) and np.isfinite(dmax) else float("nan")

    max_sp = float(pconf.max_span_nm)

    eps_nm = max(0.05, 0.02 * max_sp)

    _rmse_boundary = float(np.nanmax(rm_arr)) if (npt and rm_arr.size) else float("nan")
    _rmse_reached = (
        np.isfinite(_rmse_boundary)
        and np.isfinite(rmse_thresh)
        and rmse_thresh > 0.0
        and _rmse_boundary >= 0.85 * rmse_thresh
    )

    touch_lo = bool(
        npt and np.isfinite(d0) and np.isfinite(dmin) and (d0 - dmin) >= max_sp - eps_nm and not _rmse_reached
    )

    touch_hi = bool(
        npt and np.isfinite(d0) and np.isfinite(dmax) and (dmax - d0) >= max_sp - eps_nm and not _rmse_reached
    )

    if touch_lo and touch_hi:
        log.info(
            "%s -> THICKNESS CORRIDOR CAPPED: Interval hit max_span_nm limits (+/-%.3g nm) on both sides. "
            "ACTION: Your model strongly lacks thickness sensitivity. The n/k curves adapt almost perfectly to any subset "
            "of d. Consider physically fixing d via external measurement, or heavily decrease K-nodes (decrease degrees of freedom).",
            _LOG_PREFIX,
            max_sp,
        )

    elif not touch_lo and not touch_hi and npt >= 5 and not use_lr:
        log.info(
            "%s -> THICKNESS SENSITIVE: Both boundaries are threshold-limited, span ~ %.4g nm over %d evaluated points. "
            "ACTION: Good physical constraint. To squeeze the envelope, decrease 'rmse_abs_tolerance'. To explore broader local minima, increase it.",
            _LOG_PREFIX,
            width,
            npt,
        )

    if not use_lr and npt <= 2:
        log.info(
            "%s -> FEW VALID POINTS (%d): Often only d_opt stays inside the RMSE tube; lateral refits may be rejected by the threshold, or reverted to the nominal seed when spectral RMSE would degrade after the fixed-d refit.",
            _LOG_PREFIX,
            npt,
        )

    elif npt <= max(3, pconf.min_valid_points + 1) and not use_lr:
        log.info(
            "%s -> HIGHLY CONSTRAINED (Only %d valid points): The threshold rejected almost all refits. "
            "ACTION: Either your global minimum is very sharp (excellent spectral data), or the refits are getting stuck "
            "in numeric artifacts. If the model seems noisy, increase 'corridor_profile_d_maxfun_override' to >= 3000 to allow deeper local L-BFGS-B relaxation.",
            _LOG_PREFIX,
            npt,
        )

    if npt > 40 and width >= 2.0 * max_sp - 2 * eps_nm:
        log.info(
            "%s -> WIDE DEGENERATIVE VALLEY: Many admissible points across the full range. "
            "ACTION: The inversion is mathematically degenerate. n(lam) and d are perfectly coupled. "
            "You cannot determine d and n simultaneously with certainty on this subset. Force d externally.",
            _LOG_PREFIX,
        )

    if rm_arr.size and npt >= 3:
        rm_spread = float(np.nanmax(rm_arr) - np.nanmin(rm_arr))

        if np.isfinite(rm_spread) and rm_spread < 1e-6:
            log.info(
                "%s -> FLAT COST FUNCTION: RMSE varies by < 1e-6 over the sampled thickness window. "
                "ACTION: Severe decoupling issue. Substrate variations or backside inaccuracies are dominating the cost function "
                "making the film thickness invisible to the solver.",
                _LOG_PREFIX,
            )

    if not use_abs_delta:
        rs = base_result.get("spectral_rmse_segments")

        rm_dict = float(base_result.get("rmse", float("nan")))

        if (
            np.isfinite(rmse_opt)
            and rs is not None
            and np.isfinite(float(rs))
            and np.isfinite(rm_dict)
            and float(rs) > 0
        ):
            rel = abs(rm_dict - float(rs)) / float(rs)

            if rel > 0.4:
                log.info(
                    "%s -> RMSE DEVIATION WARNING: Dict RMSE (%.6g) and solver internal RMSE (%.6g) diverged significantly (|Delta|/solver ~ %.2f). "
                    "ACTION: Disable aggressive post-processing steps (like nonlinear alpha) prior to corridor generation to restore consistency.",
                    _LOG_PREFIX,
                    rm_dict,
                    float(rs),
                    rel,
                )

    log.info(
        "%s • NOTE: The n(lambda) and k(lambda) ribbons are deterministic max/min envelopes obtained strictly via multi-thickness L-BFGS-B relaxation. "
        "Strict bayesian interpretation requires empirical noise mapping.",
        _LOG_PREFIX,
    )

    log.info("%s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", _LOG_PREFIX)


def _log_coaching_corridor_failure(
    *,
    reason: str,
    pconf: "ProfileCorridorConfig",
    use_lr: bool,
    rmse_opt: float,
    rmse_thresh: float,
    d0: float,
) -> None:

    _ = pconf, use_lr, rmse_opt, rmse_thresh  # reserved context

    log.info("%s ━━━ Smart Coaching: Failure Analysis (%s) ━━━", _LOG_PREFIX, reason)

    if reason == "rmse_meta_invalid":
        log.info(
            "%s -> INVALID METRIC: RMSE_opt or threshold is NaN. "
            "ACTION: Your primary spline optimization mathematically crashed or diverged prior to running corridors. "
            "Check for impossible targets (like T_exp < 0 or > 1) or structurally invalid n_sub.",
            _LOG_PREFIX,
        )

    elif reason == "centre_fail":
        log.info(
            "%s -> CENTER DENIED: The optimal thickness (d_opt) fell outside its own calculated threshold after a local L-BFGS-B pass. "
            "ACTION: This means your threshold is too tight (statistical noise dominates) or the refit hit a local trap. "
            "To fix: increase 'corridor_profile_d_maxfun_override', slightly relax 'rmse_abs_tolerance', or ensure 'n_starts' >= 2 to break out of traps.",
            _LOG_PREFIX,
        )

    elif reason == "too_few_valid":
        log.info(
            "%s -> TOO FEW VALID POINTS: The optimization walked away from the center (d_opt ~ %.4f nm) but immediately hit a wall. "
            "ACTION: The cost valley is incredibly steep or the search step is too large. "
            "To fix: reduce 'corridor_profile_d_step_nm' to capture the extremely narrow valley, or gracefully accept that this thickness constraint is laser-sharp.",
            _LOG_PREFIX,
            float(d0),
        )

    log.info("%s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", _LOG_PREFIX)


def _log_coaching_bootstrap_outcome(
    *,
    B: int,
    n_ok: int,
    p: float,
    mode: str,
    qref: int,
    d_lo_q: float,
    d_hi_q: float,
) -> None:

    _ = mode

    log.info("%s ━━━ Smart Coaching: Bootstrap Uncertainty ━━━", _LOG_PREFIX)

    frac = n_ok / max(B, 1)

    if frac < 0.5:
        log.info(
            "%s -> LOW BOOTSTRAP YIELD (%.0f%% OK): Most synthetic samples failed to converge. "
            "ACTION: Your model is highly brittle to noise. To increase stability: check if the applied 'sigma_T' / 'sigma_R' noise "
            "is drastically overestimating actual spectrometer noise. Also, heavily increase 'corridor_bootstrap_quick_refit_maxfun' to give synthetic fits more breathing room.",
            _LOG_PREFIX,
            100.0 * frac,
        )

    if 0 < qref < 2000:
        log.info(
            "%s -> SHALLOW REFIT (maxfun=%d): The quick refit budget is extremely modest. "
            "ACTION: Bootstrap might be generating artificially wide uncertainty bounds due to premature stopping. "
            "Raise 'corridor_bootstrap_quick_refit_maxfun' to >= 4000 to ensure synthetic samples reach their true physical minima.",
            _LOG_PREFIX,
            qref,
        )

    spread = d_hi_q - d_lo_q

    if np.isfinite(spread) and spread > 1e-6:
        log.info(
            "%s -> DISPERSION RESULT (p=%.2f): [%s, %s] nm (span ~ %.3g nm). "
            "ACTION: This represents the conditional uncertainty given the assumed spline constraints. If the span is huge, "
            "your spectrum simply lacks enough interference fringes to resolve thickness securely against optical index.",
            _LOG_PREFIX,
            float(p),
            f"{d_lo_q:.4f}",
            f"{d_hi_q:.4f}",
            spread,
        )

    log.info("%s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", _LOG_PREFIX)


def _log_coaching_reg_sensitivity_outcome(
    *,
    weights: np.ndarray,
    d_lo: np.ndarray,
    d_hi: np.ndarray,
    nw: np.ndarray,
    kw: np.ndarray,
) -> None:

    log.info("%s ━━━ Smart Coaching: Regularization Profile ━━━", _LOG_PREFIX)

    if weights.size < 2:
        return

    w = np.asarray(weights, dtype=np.float64).ravel()

    lo = np.asarray(d_lo, dtype=np.float64).ravel()

    hi = np.asarray(d_hi, dtype=np.float64).ravel()

    nwa = np.asarray(nw, dtype=np.float64).ravel()

    kwa = np.asarray(kw, dtype=np.float64).ravel()

    if lo.size == w.size and hi.size == w.size:
        widths = hi - lo

        m = np.isfinite(widths)

        if np.any(m):
            wmin = float(np.nanmin(widths[m]))

            wmax = float(np.nanmax(widths[m]))

            rw = wmax / max(wmin, 1e-30)

            if rw > 3.0:
                log.info(
                    "%s -> REGULARIZATION DEPENDENCE (Varies by ~%.2f×): Your thickness uncertainty is heavily linked to "
                    "the smoothness penalty applied to k. "
                    "ACTION: Do not report a single value. You MUST report thickness bounds conditionally based on expected physical smoothness.",
                    _LOG_PREFIX,
                    rw,
                )

    if nwa.size == w.size and np.any(np.isfinite(nwa)):
        pos = nwa[np.isfinite(nwa) & (nwa > 0)]

        if pos.size:
            rn = np.nanmax(nwa) / max(np.nanmin(pos), 1e-30)

            if rn > 2.5:
                log.info(
                    "%s -> n(lambda) CORRIDOR DEPENDS ON REGULARIZATION (Varies by ~%.2f×). "
                    "ACTION: The width of your index envelope expands massively if ln(k) is heavily smoothed. Review physical consistency.",
                    _LOG_PREFIX,
                    rn,
                )

    if kwa.size == w.size and np.any(np.isfinite(kwa)):
        posk = kwa[np.isfinite(kwa) & (kwa > 0)]

        if posk.size:
            rk = np.nanmax(kwa) / max(np.nanmin(posk), 1e-30)

            if rk > 2.5:
                log.info(
                    "%s -> k(lambda) CORRIDOR EXTREMELY DEPENDENT ON REGULARIZATION (Varies by ~%.2f×). "
                    "ACTION: The extinction bounds are mostly an artifact of the regularization term, not your actual data topology. "
                    "Proceed with extreme caution when interpreting k-confidence intervals.",
                    _LOG_PREFIX,
                    rk,
                )

    log.info("%s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", _LOG_PREFIX)
