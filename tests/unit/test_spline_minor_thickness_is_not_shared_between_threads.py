"""The film thickness of the corridor ratios is never shared between threads (audit 2026-11-15, L4-m5).

``_ratio_theoretical_from_nk`` and its two siblings wrote the thickness into a module-level buffer, then called a
``nogil`` kernel that reads it. The +d and -d walks of the corridor run in two threads at different thicknesses: one
thread could compute its T with the thickness of the other.
"""

from __future__ import annotations

import threading

import numpy as np

from certus.utils import certus_index_utils as iu

LAM = np.linspace(400.0, 900.0, 401)
N = np.full(LAM.size, 2.1)
K = np.full(LAM.size, 1e-4)
NSUB = np.full(LAM.size, 1.46 + 0j)
FUNCS = ("_ratio_theoretical_from_nk", "_transmittance_absolute_from_nk", "_reflectance_ratio_theoretical_from_nk")


def test_no_module_level_thickness_buffer_is_left() -> None:
    assert not hasattr(iu, "_THICK_BUF")


def _walk(func, name: str, d: float, expected: dict, errors: list[str]) -> None:
    for _ in range(60):
        if not np.array_equal(func(LAM, N, K, d, NSUB), expected[d]):
            errors.append(f"{name} at {d} nm")
            return


def test_two_threads_at_two_thicknesses_get_their_own_spectra() -> None:
    for name in FUNCS:
        func = getattr(iu, name)
        expected = {d: func(LAM, N, K, d, NSUB) for d in (180.0, 420.0)}
        errors: list[str] = []

        threads = [threading.Thread(target=_walk, args=(func, name, d, expected, errors)) for d in (180.0, 420.0)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
