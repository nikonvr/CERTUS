"""Fill the valid cissoid envelope gap by gap (owner 2026-11-06 21:00). For each thickness window: seed = best cleaned
valid design whose thickness is nearest the window centre; search 25 min (floor 0.1 during search, 50 layers, all
materials except gold, window only); then clean to 3 nm and 50 layers at the end. Results: fill_envelope.log."""
import csv
import glob
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Users/Fabien/AppData/Local/Programs/Python/Python315/python.exe"
WINDOWS = [(3000, 4500), (9500, 10000), (11000, 12500), (4500, 6000)]
MIN = 25
env = dict(os.environ, OPENBLAS_NUM_THREADS="1")
def log(msg):
    with (HERE / "fill_envelope.log").open("a", encoding="utf-8") as h:
        h.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
def valid_pool():
    pts = []
    for f in glob.glob(str(HERE / "CL_*_clean.csv")):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
        except Exception:
            continue
        for r in rows:
            try:
                t = float(r.get("physical_nm") or 0)
                m = float(r["mf_oracle"])
                if t > 0 and int(r["layers"]) <= 50 and float(r["thinnest_nm"]) >= 3.0 and "U" not in r["mats"]:
                    pts.append((t, m, r))
            except Exception:
                pass
    return pts
def busy():
    out = subprocess.run(["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'cissoid_ultimate' } | Measure-Object).Count"], capture_output=True, text=True)
    try:
        return int(out.stdout.strip() or 0) > 0
    except ValueError:
        return False
while busy():
    time.sleep(60)
log("start: the two running searches have ended")
for lo, hi in WINDOWS:
    pool = valid_pool()
    c = (lo + hi) / 2
    cand = [p for p in pool if lo <= p[0] <= hi] or pool
    best = min(cand, key=lambda p: (abs(p[0] - c), p[1])) if cand else None
    if best is None:
        log(f"{lo}-{hi}: no seed")
        continue
    seed = HERE / f"seed_fill_{lo}_{hi}.csv"
    with seed.open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["mf", "layers", "physical_nm", "mats", "d_nm"])
        r = best[2]
        w.writerow([r["mf_oracle"], r["layers"], r["physical_nm"], r["mats"], r["d_nm"]])
    st = float(best[0])
    wlo, whi = min(lo, st) - 60, max(hi, st) + 60  # the search window must contain its seed
    tag = f"FILL_{lo}_{hi}"
    log(f"{lo}-{hi}: seed {best[1]:.5f} at {best[0]:.0f} nm; search {MIN} min")
    subprocess.run([PY, "cissoid_ultimate.py", "--mode", "run", "--axis", "phys", "--floor", "0.1", "--nmax", "50", "--pop", "30",
                    "--tag", tag, "--minutes", str(MIN), "--workers", "6", "--seeds", str(seed), "--only-seeds",
                    "--window", f"{wlo:.0f}:{whi:.0f}", "--rng", str(lo)], cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([PY, "clean_multi.py", "--designs", f"{tag}_best.csv", "--axis", "phys", "--floor", "3", "--nmax", "50",
                    "--tag", f"CL_{tag}", "--minutes", "10", "--workers", "6"], cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rr = list(csv.DictReader(open(HERE / f"CL_{tag}_clean.csv", encoding="utf-8")))
    if rr:
        b = min(rr, key=lambda x: float(x["mf_oracle"]))
        log(f"{lo}-{hi}: VALID best {float(b['mf_oracle']):.5f} at {float(b['physical_nm']):.0f} nm, N {b['layers']}, thinnest {float(b['thinnest_nm']):.2f}")
    else:
        log(f"{lo}-{hi}: nothing valid after cleaning")
log("sweep end")
