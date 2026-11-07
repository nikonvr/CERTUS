"""Systematic test (owner 2026-11-07): for each promising CLEANED cissoid design (valid: <=50 layers, >=3 nm, no gold),
run a needle-heavy search (floor 0.1 nm during search, window around its thickness), then clean the result to 3 nm
and 50 layers at the very end. Results: deep_needle_sweep.log and deep_needle_results.csv."""
import csv
import glob
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Users/Fabien/AppData/Local/Programs/Python/Python315/python.exe"
ENV = dict(os.environ, OPENBLAS_NUM_THREADS="1")
MIN_SEARCH, K = 30, 6  # minutes per candidate, candidates per run
def log(msg):
    with (HERE / "deep_needle_sweep.log").open("a", encoding="utf-8") as h:
        h.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
def pool():
    out = []
    for f in glob.glob(str(HERE / "CL_*_clean.csv")):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
        except Exception:
            continue
        for r in rows:
            try:
                if "U" in r["mats"] or int(r["layers"]) > 50 or float(r["thinnest_nm"]) < 3.0:
                    continue
                out.append((float(r["mf_oracle"]), float(r["physical_nm"]), r))
            except Exception:
                pass
    out.sort(key=lambda t: t[0])
    picked, seen = [], []
    for mf, t, r in out:
        if any(abs(t - s) < 150 for s in seen):
            continue  # one candidate per ~150 nm
        seen.append(t)
        picked.append((mf, t, r))
        if len(picked) >= K:
            break
    return picked
cands = pool()
log(f"start: {len(cands)} candidates: " + ", ".join(f"{mf:.4f}@{t:.0f}" for mf, t, _ in cands))
for i, (mf0, t0, r) in enumerate(cands):
    tag = f"DN_{i}_{int(t0)}"
    seed = HERE / f"seed_{tag}.csv"
    with seed.open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["mf", "layers", "physical_nm", "mats", "d_nm"])
        w.writerow([r["mf_oracle"], r["layers"], r["physical_nm"], r["mats"], r["d_nm"]])
    log(f"{tag}: start {mf0:.5f} at {t0:.0f} nm, N {r['layers']}; search {MIN_SEARCH} min")
    subprocess.run([PY, "cissoid_ultimate.py", "--mode", "run", "--axis", "phys", "--floor", "0.1", "--nmax", "50",
                    "--pop", "30", "--tag", tag, "--minutes", str(MIN_SEARCH), "--workers", "6", "--seeds", str(seed),
                    "--only-seeds", "--window", f"{max(t0 - 400, 2000):.0f}:{t0 + 400:.0f}",
                    "--moves", "needle:6,needle_diel:3,jitter:1,swap:1", "--rng", str(i + 7)],
                   cwd=HERE, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not (HERE / f"{tag}_best.csv").exists():
        log(f"{tag}: no output")
        continue
    subprocess.run([PY, "clean_multi.py", "--designs", f"{tag}_best.csv", "--axis", "phys", "--floor", "3", "--nmax", "50",
                    "--tag", f"CL_{tag}", "--minutes", "10", "--workers", "6"],
                   cwd=HERE, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rr = list(csv.DictReader(open(HERE / f"CL_{tag}_clean.csv", encoding="utf-8")))
    if rr:
        b = min(rr, key=lambda x: float(x["mf_oracle"]))
        log(f"{tag}: CLEANED {float(b['mf_oracle']):.5f} at {float(b['physical_nm']):.0f} nm, N {b['layers']}, thinnest {float(b['thinnest_nm']):.2f} (start {mf0:.5f})")
    else:
        log(f"{tag}: nothing valid after cleaning")
log("sweep end")
