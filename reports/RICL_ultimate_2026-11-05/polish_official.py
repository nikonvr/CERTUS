"""Re-polish a resolved-judge curve on the OFFICIAL contest grid (301 points, CISSOID_JUDGE unset) and report the
contest MF, then clean to 3 nm and 50 layers (owner 2026-11-07). Usage: python polish_official.py CIS_res2_curve.csv TAG"""
import csv
import os
import sys

os.environ.pop("CISSOID_JUDGE", None)
os.environ["CIS_AXIS"] = "phys"
import engine_multi as M  # noqa: E402
import numpy as np  # noqa: E402

src, tag = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(src, encoding="utf-8")))
out = []
for r in rows:
    s = r["mats"].replace(" ", "")
    d = np.array([float(v) for v in r["d_nm"].split()])
    t = float(d.sum())
    before = M.oracle_mf(s, d)
    x, _, _ = M.lm(s, d, t, 0.1, 300)
    s1, x1 = M.normalize(s, x, 1e-3)
    x1, _, _ = M.lm(s1, x1, t, 0.1, 300)
    out.append((float(r["key"]), before, M.oracle_mf(s1, x1), len(s1), float(x1.min()), t, s1, x1))
print("polished", len(out), "keys; contest MF before -> after polish (examples):")
for k, b, a, n, th, _t, _, _ in out[::max(1, len(out) // 6)]:
    print(f"  {k:7.0f} nm  {b:.5f} -> {a:.5f}  N {n}  thinnest {th:.2f}")
with open(f"{tag}_polished.csv", "w", newline="", encoding="utf-8") as h:
    w = csv.writer(h)
    w.writerow(["key", "mf", "mf_oracle", "layers", "thinnest_nm", "physical_nm", "mats", "d_nm"])
    for k, _b, a, n, th, t, s1, x1 in out:
        w.writerow([k, f"{a:.12g}", f"{a:.12g}", n, f"{th:.6f}", f"{t:.4f}", s1, " ".join(f"{v:.9f}" for v in x1)])
print("written", f"{tag}_polished.csv")
