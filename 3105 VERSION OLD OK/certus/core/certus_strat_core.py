# =============================================================================
# CERTUS STRAT - Core numerical and physics logic
# =============================================================================
import sys
import os
from pathlib import Path

from certus.core import certus_strat_config, certus_strat_objectives, certus_strat_solvers

for _mod in (certus_strat_config, certus_strat_objectives, certus_strat_solvers):
    for _k, _v in _mod.__dict__.items():
        if not _k.startswith("__"):
            globals()[_k] = _v
