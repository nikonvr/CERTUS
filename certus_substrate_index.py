# -*- coding: utf-8 -*-
"""
CERTUS SUBSTRATE INDEX
Thin facade delegator for the Substrate Index characterization app.
"""

from __future__ import annotations
import sys
import multiprocessing
from pathlib import Path

# Setup sys.path to locate dependencies correctly
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import certus.core.certus_substrate_index as _csi
for _k, _v in _csi.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v



if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    pass

