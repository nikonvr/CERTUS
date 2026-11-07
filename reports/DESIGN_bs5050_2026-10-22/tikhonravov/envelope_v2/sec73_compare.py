"""Sec. 7.3 of the method paper, redone (sec73.sh, seed 9, no substrate-side L layer): arm A, the search on the grid
(its judged designs, then its best design of each N cured), against arm B, the search with the poles charged.
One rule for both arms: the judged designs of nominal MF below 5 %, as in Figs. 1 and 4 (the night's text of 1-2 Nov
counted A without it, 96 of 202, and B with it, 10 of 194; with it for both, 96 of 194 and 10 of 194).
usage: python sec73_compare.py [mshape|highpass]
"""

from __future__ import annotations

import csv
import re
import sys

T = sys.argv[1] if len(sys.argv) > 1 else "mshape"


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def hidden(rs):
    return sum(float(r["mf_resolved"]) > 1.2 * float(r["mf_nominal"]) for r in rs)


def best(rs, key):
    r = min(rs, key=lambda x: float(x[key]))
    return f"{float(r[key]):.4f} % ({r['layers']} layers, OT {float(r['ot_nm']) / 1000:.2f} um)"


def main() -> None:
    a = [r for r in rows(f"nolsub_{T}_threshold_s9.csv") if float(r["mf_nominal"]) < 5.0]
    b = [r for r in rows(f"poles3_nolsub_{T}_threshold_s9.csv") if float(r["mf_nominal"]) < 5.0]
    c = rows(f"nolsub_{T}_cure_archive_s9.csv")
    for tag, f in (("A", f"nolsub_{T}_search_s9.out"), ("B", f"poles3_nolsub_{T}_search_s9.out")):
        print(f"{tag} search: {re.search(r'end after \d+ rounds', open(f, encoding='utf-8').read()).group()}")
    total = re.search(r"total (\d+) s", open(f"nolsub_{T}_cure_archive_s9.out", encoding="utf-8").read()).group(1)
    print(f"A: {hidden(a)} of {len(a)} designs hide resonances; best resolved {best(a, 'mf_resolved')}")
    print(f"A cured ({len(c)} designs, best of each N; {total} s on 6 workers): best resolved {best(c, 'resolved_after')}")
    print(f"B: {hidden(b)} of {len(b)} designs hide resonances; best resolved {best(b, 'mf_resolved')}")


if __name__ == "__main__":
    main()
