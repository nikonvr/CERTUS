"""The OIC 2025 B.1 score that the DESIGN window shows (`certus.core.certus_contest_scores`) is the oracle score.

The window scores its stack by material name; the spectra come from the CERTUS kernels through the immersion of
`certus.domain.immersion`. The score must equal the one computed from the independent oracle directly in the cube of
index 1.80, and the rules must be checked on the indices of the materials.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_contest_oic2025_b1_score import _oracle_spectra, _random_design, _score

from certus.domain import contest_oic2025_b1 as b1


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_score_shown_by_design_is_the_oracle_score(seed) -> None:
    # `certus.core.certus_contest_scores.oic2025_b1_score` scores a stack of the window (materials by name); it must
    # give the score of the oracle computed directly in the cube, and check the contest rules.
    from certus.core.certus_contest_scores import oic2025_b1_score
    from certus.physics.certus_opt_tmm import Material

    n, d = _random_design(4, seed, d_max=8.0)
    mats = {"H": Material(b1.MATERIALS["H"], b1.MATERIALS["H"]), "M": Material(b1.MATERIALS["M"], b1.MATERIALS["M"])}
    names = ["H" if x == b1.MATERIALS["H"] else "M" for x in n]
    shown, legal = oic2025_b1_score(mats, names, d)
    s_oracle = _score(lambda w, p: _oracle_spectra(n, d, w, p))
    assert np.isfinite(shown.total)
    assert shown.total == pytest.approx(s_oracle.total, rel=1e-9)
    assert (shown.n_rs_at_least_99, shown.n_ts_at_least_99) == (s_oracle.n_rs_at_least_99, s_oracle.n_ts_at_least_99)
    assert legal
    mats["X"] = Material(1.90, 1.90)  # not a contest material
    assert not oic2025_b1_score(mats, [*names[:-1], "X"], d)[1]
