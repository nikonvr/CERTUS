"""How many ROUNDS did the published cleaning test use? Its command was not recorded. The 'nominal' arm does not use the
detector: the resonant design without its thinnest layer, polished with 15 and with 40 bursts, against the published row
of cleaning_test_trub101.csv.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex NUMBA_NUM_THREADS=8 python cleaning_rounds_probe.py
"""

from __future__ import annotations

import csv
import os
import sys

sys.argv = [sys.argv[0], "1", "15", "1"]
import cleaning_test_trub101 as ct  # noqa: E402
import numpy as np  # noqa: E402


def main() -> None:
    _seq, dt = ct.designs()["resonant"]
    j = int(np.argsort(np.array([float(v) for v in dt.split()]))[0])
    pub = next(r for r in csv.DictReader(open("cleaning_test_trub101.csv", encoding="utf-8"))
               if r["design"] == "resonant" and int(r["removed"]) == j and r["method"] == "nominal")
    print(f"published, layer {j} removed: nominal {float(pub['mf_nominal']):.4f} %, resolved {float(pub['mf_resolved']):.4f} %",
          flush=True)
    for rounds in tuple(int(v) for v in os.environ.get("PROBE_ROUNDS", "15,40").split(",")):
        ct.ROUNDS = rounds
        r = ct.run(("resonant", j, "nominal"))
        print(f"{rounds} rounds: nominal {float(r['mf_nominal']):.4f} %, resolved {float(r['mf_resolved']):.4f} %",
              flush=True)


if __name__ == "__main__":
    main()
