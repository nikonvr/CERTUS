"""Contest scores of a DESIGN stack, computed with the kernels of CERTUS.

OIC 2025, Problem B.1 (Kruschwitz, Trubetskov and Keck, Appl. Opt. 65(5), A12-A21, 2026): the coating lies between
two prisms of index 1.80 and is lit at 45 degrees in the prism. The score itself is `certus.domain.contest_oic2025_b1`;
here the spectra it needs are computed, the immersion being translated by `certus.domain.immersion.to_air_equivalent`
(no transfer-matrix formula is written here, CLAUDE.md rule 7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from certus.domain import contest_oic2025_b1 as b1
from certus.domain.immersion import to_air_equivalent
from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized


def _indices(mats: Mapping[str, Any], names: Sequence[str], wls: np.ndarray) -> np.ndarray:
    """Layer indices on `wls`, one column per layer."""
    return np.stack([np.asarray(mats[name].get_nk(wls), dtype=np.complex128) for name in names], axis=1)


def oic2025_b1_score(mats: Mapping[str, Any], names: Sequence[str], thicknesses_nm: np.ndarray) -> tuple[b1.B1Score, bool]:
    """Score of Problem B.1 of the OIC 2025 contest for a stack, and whether it keeps the contest rules.

    Args:
        mats: the materials of the window (objects with `get_nk`).
        names: the material of each layer, from the side of the incident light.
        thicknesses_nm: physical thicknesses, nm.

    Returns:
        The score and its parts, and True if the stack has at most 100 layers, at most 20 um and only the
        contest materials. The prisms are those of the contest (index 1.80), whatever the substrate of the window.
    """
    d = np.asarray(thicknesses_nm, dtype=np.float64)
    names = list(names)
    if len(names) != d.size:
        raise ValueError("one material per layer is needed")
    grid = b1.contest_grid()
    lines = np.array(b1.LINES_NM, dtype=np.float64)
    n_prism = b1.INCIDENT_INDEX
    spectra = {}
    for key, wls in (("grid", grid), ("lines", lines)):
        n_eq, d_eq, n_sub_eq = to_air_equivalent(
            _indices(mats, names, wls), d, np.full(wls.size, complex(n_prism, 0.0)), n_prism
        )
        for pol in ("s", "p"):
            spectra[key, pol] = calc_spectrum_oblique_vectorized(wls, n_eq, d_eq, n_sub_eq, b1.ANGLE_DEG, pol)
    rs, ts = spectra["grid", "s"]
    score = b1.b1_score(rs, ts, spectra["lines", "s"][1], spectra["lines", "p"][1])
    n_real = np.array([float(np.real(mats[name].get_nk(np.array([550.0]))[0])) for name in names])
    return score, b1.within_contest_rules(d, n_real)
