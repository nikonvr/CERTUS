#!/usr/bin/env python3
"""Build script scaffold for Numba AOT exports (#42).

Current step: validates that numba.pycc is importable and documents
the migration entry-point for future kernel exports.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CERTUS Numba AOT extension (scaffold).")
    parser.add_argument("--check", action="store_true", help="Only verify AOT prerequisites.")
    args = parser.parse_args()

    if importlib.util.find_spec("numba.pycc") is None:
        print("[AOT] numba.pycc unavailable.")
        return 2

    if args.check:
        print("[AOT] prerequisites OK (numba.pycc importable).")
        return 0

    print("[AOT] scaffold only: no compiled exports declared yet.")
    print("[AOT] next step: register hot kernels in _certus_physics_kernels_aot.py and export via numba.pycc.CC.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
