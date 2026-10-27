"""AO 46, 704 (2007) §2: remove layers < 10 nm one by one, thinnest first, by giving them a neighbour's index; reoptimize."""
import csv
import sys
from pathlib import Path

import numpy as np

V2 = Path(__file__).resolve().parent
sys.path.insert(0, str(V2))
import search as s  # noqa: E402

for want in (int(a) for a in sys.argv[1:]):
    row = next(r for r in csv.DictReader(open(V2 / "curve_free_s1.csv", encoding="utf-8")) if int(r["layers"]) == want)
    seq, d = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
    qw = lambda q, x: float(np.sum(x * np.array([4 * s.N_IDX[m] for m in q]) / s.L0))  # noqa: E731
    print(f"N={len(seq)} start RMSE {s.oracle_rmse(seq, d):.3e} QWOT {qw(seq, d):.2f} thin {np.sort(d)[:4].round(1)}")
    while np.min(d) < 10.0 and len(seq) > 2:
        i = int(np.argmin(d))
        j = i - 1 if i > 0 else i + 1
        seq, d = s.normalize(seq[:i] + seq[j] + seq[i + 1:], d, 0.0)
        d, r = s.polish(seq, d, 0.1, max_nfev=2000)
        print(f"  -> N={len(seq)} RMSE {s.oracle_rmse(seq, d):.3e} QWOT {qw(seq, d):.2f} thinnest {np.min(d):.1f}")
