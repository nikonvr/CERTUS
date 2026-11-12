"""The spectral weights of the RMSE, in a file that imports nothing of CERTUS.

INDEX, DESIGN and RE weigh a spectral residual the same way. The function lived in the utilities of INDEX, so the
DESIGN workers and the RE helpers imported a module of another program for it, and the analytic gradient, in the
physics layer, imported a layer above its own. It is here, under all of them;
`certus.utils.certus_index_utils` imports it back, so `from certus.utils.certus_index_utils import
spectral_rmse_weights` still works.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


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

    # Compute log(lambda) inter-distances

    log_lam = np.log(np.maximum(lam, 1e-9))

    # Central gradient (trapezoidal scheme)

    w = np.zeros_like(log_lam)

    w[1:-1] = 0.5 * (log_lam[2:] - log_lam[:-2])

    w[0] = log_lam[1] - log_lam[0]

    w[-1] = log_lam[-1] - log_lam[-2]

    # Work with absolute values to handle decreasing grids

    w = np.abs(w)

    # Normalization: the sum of weights is equal to the number of points

    # to keep the RMSE consistent with the usual physical scale.

    sw = np.sum(w)

    if sw > 0:
        w = w * (float(n) / sw)

    else:
        w = np.ones_like(lam)

    return w
