"""Helpers partages par les tests.

This module exists so that tests can import utility functions WITHOUT
passer par ``from conftest import ...``. Cet import par nom nu n'est pas fiable : le
depot contains several ``conftest.py`` (tests/, tests/ui/, ...) and, in the absence of
``__init__.py``, the module name ``conftest`` designates the one which was imported EN
PREMIER par pytest. Selon les repertoires passes en ligne de commande, c'est
``tests/ui/conftest.py`` qui gagnait, d'ou un ImportError a la collecte.

Un conftest.py sert a declarer des fixtures, pas a exposer une bibliotheque.
"""

from __future__ import annotations

import numpy as np

__all__ = ["compute_spectrum_simple"]


def compute_spectrum_simple(layers, wavelengths):
    """High-level wrapper: List[Layer] + wavelengths -> R array.

    Uses low-level TMM kernel with realistic clues (n=1.5 per layer,
    derived from qwot). For structural tests only.
    """
    from certus.core._certus_physics_impl import compute_TMM_generic as _tmm

    n_sub = complex(1.52)
    n0 = complex(1.0)
    n_layers = len(layers)
    d_arr = np.array([layer.qwot * 137.5 for layer in layers])  # QWOT -> nm approximatif
    n_arr = np.array([complex(1.5, 0.0)] * n_layers)
    r_out = np.empty(len(wavelengths))
    for i, wavelength in enumerate(wavelengths):
        k0 = 2.0 * np.pi / wavelength
        r_out[i], _ = _tmm(k0, d_arr, n_arr, n0, n_sub)
    return r_out
