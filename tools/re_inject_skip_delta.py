#!/usr/bin/env python3
"""
List symbols that would be injected if the legacy `vars(certus_re_helpers)` copy
still existed, or print zero when ARCH-1 removed the injector.

Requires a working tree: imports `CERTUS_RE` (loads PyQt, etc.) then compares
`CERTUS_RE._RE_INJECT_SKIP` (if present) to public names on `certus_re_helpers`.

Usage (from repo root):
  python tools/re_inject_skip_delta.py
  python tools/re_inject_skip_delta.py --count-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="print only the number of remaining injected names",
    )
    args = parser.parse_args()

    import certus_re_helpers as h

    import CERTUS_RE as cre

    if not hasattr(cre, "_RE_INJECT_SKIP"):
        msg = (
            "# ARCH-1: `vars(certus_re_helpers)` injector removed; "
            "no _RE_INJECT_SKIP on CERTUS_RE."
        )
        if args.count_only:
            print(0)
        else:
            print(msg)
        return 0

    skip = cre._RE_INJECT_SKIP
    public = {k for k in vars(h) if not k.startswith("__")}
    remaining = sorted(public - set(skip))

    if args.count_only:
        print(len(remaining))
        return 0

    print(f"# remaining_injected={len(remaining)}  (certus_re_helpers public={len(public)}  skip={len(skip)})")
    for name in remaining:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
