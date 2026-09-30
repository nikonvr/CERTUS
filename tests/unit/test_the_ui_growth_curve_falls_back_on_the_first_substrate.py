"""The growth curve of the STRAT window takes its substrate fallback from the first entry of the index database.

`simulate_detailed_growth_for_ui` reads the substrate index of each block from `clues_at_wl` (wavelength -> indices). A block
whose wavelength is not in the database, or whose substrate is below 1.001 (no substrate), falls back on the substrate of the
FIRST wavelength of the database, and on 1.52 when the database is empty. The first entry used to be read with
`list(clues_db.keys())[0]` (an `IndexError` on an empty database, caught); it is now `next(iter(...))` (a `StopIteration`,
caught too): these tests pin both cases, the empty one being the one a careless `next(iter(...))` would let through.
"""

from __future__ import annotations

import numpy as np

from certus.utils.certus_strat_service import simulate_detailed_growth_for_ui

BLOCK_WL = 560.0  # not in any database below: the block falls back
NO_SUBSTRATE = {"nSub_custom": 1.0}  # a substrate of 1.0 is "no substrate": the fallback takes over


def _curve(clues) -> np.ndarray:
    strategy = {"strategy": {"blocks": [{"wavelength": BLOCK_WL, "start": 0, "end": 2}]}}
    opti = {"p_thick_nominal": [50.0, 80.0], "clues_at_wl": clues}
    return np.asarray(simulate_detailed_growth_for_ui(strategy, opti, NO_SUBSTRATE)["y"])


def test_an_empty_database_falls_back_on_1_52_and_does_not_raise() -> None:
    from_empty = _curve({})

    from_1_52 = _curve({500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52}})

    np.testing.assert_allclose(from_empty, from_1_52)


def test_the_fallback_is_the_substrate_of_the_first_wavelength_of_the_database() -> None:
    clues = {500.0: {"H": 2.3, "L": 1.45, "substrate": 1.90}, 700.0: {"H": 2.3, "L": 1.45, "substrate": 1.60}}

    from_first = _curve(clues)

    np.testing.assert_allclose(from_first, _curve({500.0: {"H": 2.3, "L": 1.45, "substrate": 1.90}}))
    assert not np.allclose(from_first, _curve({}))  # 1.90 is not the 1.52 of the empty database
    assert not np.allclose(from_first, _curve({700.0: {"H": 2.3, "L": 1.45, "substrate": 1.60}}))  # and not the last entry
