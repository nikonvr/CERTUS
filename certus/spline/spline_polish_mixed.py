"""L-BFGS-B call of the spline polish, with the optional finite-difference prefix (``spline_polish_fd_prefix_maxfun``).

With a prefix > 0 and the analytic gradient in use, a finite-difference pass runs first, then the analytic one from its
end with the remaining budget: the exact gradient alone can settle in a nearby worse local minimum (chantier 21, TOTAL
example). With a prefix of 0, or without the analytic gradient, the single call is the one the polish always made.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.optimize import OptimizeResult, minimize

_OPTIONS = {"ftol": 1e-12, "gtol": 1e-9}


def minimize_polish(
    fun: Callable,
    fun_fd: Callable,
    x0: np.ndarray,
    jac: bool | None,
    bounds: list[tuple[float, float]],
    maxfun_total: int,
    fd_prefix: int,
    callback: Callable,
) -> OptimizeResult:
    """Run the polish L-BFGS-B; ``fun_fd`` returns the cost alone, ``fun`` the cost and gradient when ``jac`` is True."""
    if not (jac and fd_prefix > 0):
        return minimize(fun, x0, method="L-BFGS-B", jac=jac, bounds=bounds,
                        options={"maxfun": int(maxfun_total), **_OPTIONS}, callback=callback)
    res_fd = minimize(fun_fd, x0, method="L-BFGS-B", jac=None, bounds=bounds,
                      options={"maxfun": int(min(fd_prefix, maxfun_total)), **_OPTIONS}, callback=callback)
    nfev_fd = int(getattr(res_fd, "nfev", 0))
    maxfun_rest = int(maxfun_total) - nfev_fd
    if maxfun_rest <= 0:
        return res_fd
    res = minimize(fun, np.asarray(res_fd.x, dtype=np.float64).ravel().copy(), method="L-BFGS-B", jac=jac,
                   bounds=bounds, options={"maxfun": maxfun_rest, **_OPTIONS}, callback=callback)
    res.nfev = int(getattr(res, "nfev", 0)) + nfev_fd
    return res
