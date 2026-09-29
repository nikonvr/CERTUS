"""The script PyInstaller starts in the frozen suite (`certus_hub.spec`).

Everything it does is in `certus.core.certus_frozen_entry`: the hub, or the module named after
`--run-module`. It lives here and not in `certus/core/` on purpose: PyInstaller puts the folder of
its entry script FIRST on its search path, and `certus/core/` holds a `certus_substrate_index.py`
of its own, which then took the place of the root script `certus_substrate_index.py` in the build:
`--run-module certus_substrate_index` ran a library module as `__main__`, did nothing, and exited 0.
"""

import multiprocessing
import sys

from certus.core.certus_frozen_entry import main

if __name__ == "__main__":
    # First, before anything else: a child of `multiprocessing` starts as this same executable.
    multiprocessing.freeze_support()
    sys.exit(main())
