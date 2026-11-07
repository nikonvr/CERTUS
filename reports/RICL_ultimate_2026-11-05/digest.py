"""One-screen status of the RICL 48 h campaign (2026-11-05): current stage, last progress line, and for the
three-line TOT continuum the comparison with Trubetskov 2020 Fig. 5 (best published value at equal or smaller TOT).
Reads files only; no computation beyond comparisons. usage: python digest.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG5 = HERE.parent / "DESIGN_bs5050_2026-10-22" / "tikhonravov" / "envelope_v2" / "trubetskov2020_fig5_digitized.csv"


def tail(path: Path, pattern: str, n: int = 1) -> list[str]:
    if not path.exists():
        return []
    lines = [x for x in path.read_text(encoding="utf-8", errors="replace").splitlines() if re.search(pattern, x)]
    return lines[-n:]


def threeline_vs_trubetskov(tag: str) -> str:
    p = HERE / f"{tag}_curve.csv"
    if not p.exists() or not FIG5.exists():
        return ""
    with FIG5.open(encoding="utf-8") as h:
        pub = [(float(r["total_ot_nm"]), float(r["mf_percent"])) for r in csv.DictReader(h)]
    with p.open(encoding="utf-8") as h:
        cur = [(float(r["key"]), float(r["mf"]), int(r["layers"])) for r in csv.DictReader(h)]
    ratios = []
    for t, m, _n in cur:
        prev = [v for tt, v in pub if tt <= t + 1e-9]
        if prev and t >= 1500:
            ratios.append((m / min(prev), t))
    if not ratios:
        return ""
    below = sum(q < 1 for q, _t in ratios)
    worst = max(ratios)
    at = {t: (m, n) for t, m, n in cur}
    hi = at.get(14150.0)
    hi_txt = f"; at 14150 nm: {hi[0]:.5f} % N {hi[1]} (Trubetskov deep 0.0128 at 14171)" if hi else ""
    return (f"{tag}: {len(cur)} points; below the published best at TOT<=T on {below}/{len(ratios)} points "
            f"(T>=1500 nm); worst ratio {worst[0]:.3f} at {worst[1]:.0f} nm{hi_txt}")


def main() -> None:
    log = HERE / "orchestrate.log"
    starts = tail(log, r"stage \S+ start", 1)
    ends = tail(log, r"stage \S+ end", 1)
    print("last start:", starts[0][:120] if starts else "-")
    print("last end  :", ends[0][:120] if ends else "-")
    m = re.search(r"stage (\S+) start", starts[0]) if starts else None
    if m:
        tag = m.group(1)
        for line in tail(HERE / f"{tag}.log", r"round|BEST|end", 2):
            print("  ", line[:200])
    for tag in ("S_tl_tot2", "S_tl_tot"):
        txt = threeline_vs_trubetskov(tag)
        if txt:
            print(txt)
            break


if __name__ == "__main__":
    main()
