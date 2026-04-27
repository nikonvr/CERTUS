"""Direct smoke tests for `_certus_physics_impl` (P1-12: kernel reachability, not only via `certus_physics`)."""

from __future__ import annotations

import numpy as np
import numpy.testing as npt

from _certus_physics_impl import get_nk_cauchy_wrapper


def test_get_nk_cauchy_wrapper_one_wavelength() -> None:
    wls = np.array([500.0], dtype=np.float64)
    n4, n7 = 1.50, 1.45
    n = get_nk_cauchy_wrapper(n4, n7, wls)
    assert n.shape == (1,)
    inv_400 = 1.0 / (400.0 * 400.0)
    inv_700 = 1.0 / (700.0 * 700.0)
    b = (n4 - n7) / (inv_400 - inv_700)
    a = n4 - b * inv_400
    wl = float(wls[0])
    expected = a + b / (wl * wl)
    npt.assert_allclose(float(n[0]), expected, rtol=0.0, atol=1e-9)
