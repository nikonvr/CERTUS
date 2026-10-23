"""The share of a plan's error that comes from the index uncertainty (A11, `strat_index_share_top_k`, off by default).

WHY. STRAT exists to find a strategy little sensitive to the index error (owner, 2026-10-20), and nothing showed how sensitive a
plan is. Same plan, same draws (C2), the configured index corridor, then a corridor of zero:

    index share = 1 - mean RMSE^2(corridor 0) / mean RMSE^2(configured corridor)

at the nominal noise level, over the draws that complete under both (the measurement of
reports/STRAT_r75_leviers_bonne_mere_2026-10-20/outils/index_share.py.txt, paired here draw by draw). 0 means the index error adds
nothing; 0.6 means 60 % of the plan's mean squared error comes from it.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: Offset of `robustness_seed` for the draws of this measurement: disjoint from the ranking and local-search seeds.
INDEX_SHARE_SEED_OFFSET: int = 7_300_003


def top_k(params: dict[str, Any]) -> int:
    """How many of the best strategies get their index share: 0 (the default) computes nothing."""
    return int(params.get("strat_index_share_top_k", 0) or 0)


def index_share(on: list[tuple[np.ndarray, np.ndarray]], off: list[tuple[np.ndarray, np.ndarray]], level: int) -> dict[str, Any]:
    """The share from two evaluations of one plan on the same draws: `on` under the configured corridor, `off` under zero."""
    (r_on, s_on), (r_off, s_off) = on[level], off[level]
    both = ~np.asarray(s_on, dtype=bool) & ~np.asarray(s_off, dtype=bool)
    if not np.any(both):
        return {"index_share": None, "rmse2_index_on": None, "rmse2_index_off": None}
    m_on = float(np.mean(np.asarray(r_on, dtype=np.float64)[both] ** 2))
    m_off = float(np.mean(np.asarray(r_off, dtype=np.float64)[both] ** 2))
    return {"index_share": 1.0 - m_off / m_on if m_on > 0.0 else None, "rmse2_index_on": m_on, "rmse2_index_off": m_off}
