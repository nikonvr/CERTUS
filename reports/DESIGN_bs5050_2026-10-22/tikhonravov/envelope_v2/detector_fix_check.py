"""Does the fixed CERTUS detector (threeline_track.poles with TRACK_STEPS=localmax, TRACK_MULTISTART=dense) find the same
resonances as Code 1 fixed (hidden_resonances.find_poles)? On the designs of
OE_resonances/dataset/synthesis/long_wave_pass_search_with_poles.csv: the number of resonances of each, and the largest
wavelength difference between matched poles.
usage: SEARCH_TARGET=highpass TRACK_DETECT=complex TRACK_STEPS=localmax TRACK_MULTISTART=dense \
       python detector_fix_check.py OE_CODE_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import threeline_track as tt

sys.path.insert(0, sys.argv[1])
import hidden_resonances as hr  # noqa: E402

BANDS = [(400, 540, 0.0), (560, 700, 1.0)]


def target_fn(lam):
    return next((t for a, b, t in BANDS if a <= lam <= b), 0.0)


def main() -> None:
    same = diff = 0
    worst = 0.0
    path = Path(sys.argv[1]).parent / "dataset" / "synthesis" / "long_wave_pass_search_with_poles.csv"
    for r in csv.DictReader(open(path, encoding="utf-8")):
        seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
        a = sorted(p[0] for p in tt.poles(seq, d))
        b = sorted(p[0] for p in hr.find_poles([2.35 if m == "H" else 1.45 for m in seq], d,
                                               [(x, y) for x, y, _t in BANDS], target_fn))
        if len(a) == len(b):
            same += 1
            worst = max([worst, *(abs(x - y) for x, y in zip(a, b, strict=True))])
        else:
            diff += 1
            print(f"  {r['layers']} layers, OT {r['ot_nm']}: CERTUS {[round(x, 3) for x in a]}, Code 1 "
                  f"{[round(x, 3) for x in b]}", flush=True)
    print(f"{same} designs with the same number of resonances (largest wavelength difference {worst:.1e} nm), "
          f"{diff} different", flush=True)


if __name__ == "__main__":
    main()
