# -*- coding: utf-8 -*-
"""
CERTUS CURVE SMOOTHER
Thin facade delegator for the Curve Smoother app.
"""

from __future__ import annotations
import sys
import multiprocessing
from pathlib import Path

# Setup sys.path to locate dependencies correctly
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus.utils.certus_curve_smoother import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
