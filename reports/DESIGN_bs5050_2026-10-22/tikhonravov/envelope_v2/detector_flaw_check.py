"""Does the one-step-per-run detector explain the hidden resonances left by the search with the poles charged (Sec. 7.3,
57 of 143 designs on the long-wave pass, 8 of 144 on the M target)? For every design of
OE_resonances/dataset/synthesis/*_search_with_poles.csv, the resonances found on the nominal 1-nm grid by Code 1 before
the fix (one step per positive run, 5 Newton starts; backup hidden_resonances_code1_2026-11-02_before_localmax.py)
and after it (one step per local maximum, starts every 0.25 nm over +-2.5 nm), split by whether the design hides
resonances (resolved MF more than 1.2 times the nominal one). The CERTUS detector that drove the charge segments like
the old one. Measurement only; nothing of the paper changes.
usage: python detector_flaw_check.py OE_CODE_DIR
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, sys.argv[1])
import hidden_resonances as new  # noqa: E402

spec = importlib.util.spec_from_file_location("old", Path(__file__).with_name(
    "hidden_resonances_code1_2026-11-02_before_localmax.py"))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

DATA = Path(sys.argv[1]).parent / "dataset" / "synthesis"
TARGETS = {"long_wave_pass": ([(400, 540, 0.0), (560, 700, 1.0)]),
           "spectral_m": ([(400, 449, 0.0), (450, 650, None), (651, 700, 0.0)])}


def m_target(lam):
    return float(np.interp(lam, [450, 500, 550, 600, 650], [0, 0.5, 0.25, 0.5, 0]))


def main() -> None:
    for name, bands in TARGETS.items():
        def target_fn(lam, bands=bands):
            for a, b, t in bands:
                if a <= lam <= b:
                    return m_target(lam) if t is None else t
            return 0.0

        stats = {True: [0, 0, 0], False: [0, 0, 0]}  # hidden: [designs, designs with more poles found, extra poles]
        for r in csv.DictReader(open(DATA / f"{name}_search_with_poles.csv", encoding="utf-8")):
            nl = [2.35 if m == "H" else 1.45 for m in r["seq"]]
            d = np.array([float(v) for v in r["d_nm"].split()])
            ab = [(a, b) for a, b, _t in bands]
            n_old = len(old.find_poles(nl, d, ab, target_fn))
            n_new = len(new.find_poles(nl, d, ab, target_fn))
            hidden = float(r["mf_resolved_pct"]) > 1.2 * float(r["mf_nominal_pct"])
            s = stats[hidden]
            s[0] += 1
            s[1] += n_new > n_old
            s[2] += max(0, n_new - n_old)
        for hidden in (True, False):
            n, more, extra = stats[hidden]
            print(f"{name}, designs {'hiding' if hidden else 'not hiding'} resonances: {n}; the fixed detector finds more "
                  f"resonances in {more} of them ({extra} more in all)", flush=True)


if __name__ == "__main__":
    main()
