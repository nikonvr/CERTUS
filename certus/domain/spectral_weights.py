"""The spectral weights of the RMSE, in a file that imports nothing of CERTUS.

INDEX, DESIGN and RE weigh a spectral residual the same way. The function lived in the utilities of INDEX, so the
DESIGN workers and the RE helpers imported a module of another program for it, and the analytic gradient, in the
physics layer, imported a layer above its own. It is here, under all of them;
`certus.utils.certus_index_utils` imports it back, so `from certus.utils.certus_index_utils import
spectral_rmse_weights` still works.

`spectral_rmse_weights_banded` gives the same weights to a grid that covers several separate bands (DESIGN's targets):
a point next to a gap between two bands no longer takes the width of the gap as its own (2026-11-13: on two bands of
108 points, 400-500 and 1000-1100 nm, the two points beside the gap held 68.6 % of the total weight).
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import numpy.typing as npt


def _log_widths(lam: np.ndarray) -> np.ndarray:
    """Width in ln(lambda) that the trapezoidal scheme gives each point of ``lam`` (two points at least), unnormalized:
    half of the two neighbouring intervals inside, the whole of the single one at each end."""

    log_lam = np.log(np.maximum(lam, 1e-9))

    w = np.zeros_like(log_lam)

    w[1:-1] = 0.5 * (log_lam[2:] - log_lam[:-2])

    w[0] = log_lam[1] - log_lam[0]

    w[-1] = log_lam[-1] - log_lam[-2]

    # Absolute values: a decreasing grid gives the same widths

    return np.abs(w)


def spectral_rmse_weights(lam: npt.ArrayLike, weight_space: str = "log") -> np.ndarray:
    """Trapezoidal quadrature weights on ln(lambda) for spectral RMSE.

    Compensates non-uniform sampling density so that RMSE is not biased
    toward densely sampled spectral regions.

    Parameters
    ----------
    lam : array_like
        Wavelengths in nm (any order).
    weight_space : str, optional
        Reserved for future use. Currently always ``"log"``.

    Returns
    -------
    np.ndarray
        Weight array (same size as *lam*), normalized so that ``sum(w) == len(lam)``.
    """

    lam = np.asarray(lam, dtype=np.float64).ravel()

    n = lam.size

    if n < 2:
        return np.ones_like(lam)

    w = _log_widths(lam)

    # Normalization: the sum of weights is equal to the number of points

    # to keep the RMSE consistent with the usual physical scale.

    sw = np.sum(w)

    if sw > 0:
        w = w * (float(n) / sw)

    else:
        w = np.ones_like(lam)

    return w


def spectral_rmse_weights_banded(lam: npt.ArrayLike, bands: Iterable[tuple[float, float]]) -> np.ndarray:
    """``spectral_rmse_weights`` for a grid laid over separate spectral bands (lmin, lmax), such as DESIGN's targets.

    The scheme gives each point half of the interval to each neighbour. Between two bands, that interval is a gap that
    belongs to no band: the two points beside it took its width as weight. Here the grid is cut where two consecutive
    points both lie in bands but no single band holds both, and each piece gets its own trapezoidal widths; the weights
    are then normalized together (their sum is the number of points). A point alone in its piece gets the median width
    of the others. A grid with no such cut (one band, adjacent or overlapping bands, or a grid that has points in the
    gap) gets exactly ``spectral_rmse_weights(lam)``.
    """

    lam = np.asarray(lam, dtype=np.float64).ravel()

    merged: list[tuple[float, float]] = []
    for lo, hi in sorted((float(lo), float(hi)) for lo, hi in bands if float(hi) >= float(lo)):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    if lam.size < 2 or len(merged) < 2:
        return spectral_rmse_weights(lam)

    limits = np.asarray(merged, dtype=np.float64)
    order = np.argsort(lam, kind="stable")

    ordered = lam[order]

    lo, hi = limits[:, 0], limits[:, 1]

    covered = np.any((ordered[:, None] >= lo) & (ordered[:, None] <= hi), axis=1)

    joined = np.any((ordered[:-1, None] >= lo) & (ordered[1:, None] <= hi), axis=1)

    cuts = np.flatnonzero(covered[:-1] & covered[1:] & ~joined) + 1

    if cuts.size == 0:
        return spectral_rmse_weights(lam)

    starts = np.concatenate(([0], cuts))

    ends = np.concatenate((cuts, [ordered.size]))

    widths = np.zeros_like(ordered)

    for start, end in zip(starts, ends, strict=True):
        if end - start >= 2:
            widths[start:end] = _log_widths(ordered[start:end])

    alone = starts[ends - starts == 1]

    positive = widths[widths > 0]

    widths[alone] = float(np.median(positive)) if positive.size else 1.0

    total = float(np.sum(widths))

    weights = widths * (float(ordered.size) / total) if total > 0 else np.ones_like(widths)

    out = np.empty_like(weights)

    out[order] = weights

    return out
