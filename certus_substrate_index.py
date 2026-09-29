"""
CERTUS SUBSTRATE INDEX
Entry script of the substrate index tool, the one the hub launches. The tool itself lives in
certus.ui.certus_substrate_ui.
"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

# Setup sys.path to locate dependencies correctly
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    from certus.ui.certus_substrate_ui import main

    main()
