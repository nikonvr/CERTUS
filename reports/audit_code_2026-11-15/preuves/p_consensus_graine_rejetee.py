"""Audit M-L2: what a consensus score becomes when one seed is rejected (infinite score).

Drives the real helpers of `certus_strat_consensus` the way `certus_strat_robustness` does: three seeds, one rejected.
    python reports/audit_code_2026-11-15/preuves/p_consensus_graine_rejetee.py
"""

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from certus.core import certus_strat_consensus as c  # noqa: E402

for name, scores in (("stable, 3 seeds kept", [0.0080, 0.0081, 0.0082]),
                     ("one seed rejected (inf)", [0.0070, np.inf, 0.0071]),
                     ("all seeds rejected", [np.inf, np.inf, np.inf])):
    kept: list[float] = []
    cache: dict = {}
    for k, s in enumerate(scores):
        c._store_and_consume_consensus_score(robustness_score_cache=cache, cache_key=(name, k), score_c=s, seed_scores=kept)
    skipped = c._should_skip_consensus_registration(kept)
    stats = None if not kept else c._consensus_seed_score_stats(kept)
    print(f"{name:26s} seeds={scores} -> kept={kept} skip_registration={skipped} (mean, std, worst)={stats}")
print("\n_should_skip_consensus_registration source:\n" + inspect.getsource(c._should_skip_consensus_registration))
