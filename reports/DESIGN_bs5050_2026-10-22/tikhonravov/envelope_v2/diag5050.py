"""Why gradual evolution beats the envelope search on the three-line filter but not on the 50/50 splitter (2026-10-28).

Hypotheses and their tests:
H1 each method wins on its own axis (envelope: best RMSE at fixed N, TOT free; gradual: best MF at fixed TOT, N free)
   -> `axes`: both methods, both problems, against N and against TOT (existing data, no new design).
H2 the gradual 50/50 designs are under-converged (polish capped at 300 evaluations, RMSE near 1e-5)
   -> `repolish`: the same designs polished with 3000 evaluations, at imposed TOT and free.
H3 gradual evolution is a good refiner but a poor explorer on a broadband target (one trajectory, early basin)
   -> `seed`: writes the envelope N=37 design as a resume file for gradual.py (needles and growth from it).

usage: SEARCH_TARGET=bs5050 python diag5050.py repolish | seed ;  python diag5050.py axes
outputs: diag5050_repolish.txt, diag5050_seed37.csv, diag5050_axes.png
"""

from __future__ import annotations

import csv
import os
import sys

import numpy as np

CMD = sys.argv[1]
if CMD == "axes":
    os.environ.setdefault("SEARCH_TARGET", "threeline")  # only the paths and the oracle-free columns are used
import gradual as g  # noqa: E402
import search as s  # noqa: E402

QW = 125.0  # nm, optical thickness of one QWOT unit at 500 nm


def rows(name: str) -> list[dict]:
    f = s.HERE / name
    if not f.exists():
        return []
    with f.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def design(r: dict):
    return r["seq"], np.array([float(v) for v in r["d_nm"].split()])


def repolish() -> None:
    assert s.TARGET == "bs5050"
    src = rows("gradual_bs5050_deep4.csv") or rows("gradual_bs5050_deep4_partial.csv")
    out = ["50/50 gradual designs: RMSE as found, polished at imposed TOT with 3000 evaluations, polished free (TOT free)",
           "TOT  N  rmse_found  rmse_tot3000  rmse_free3000  TOT_free"]
    for r in src:
        tot = float(r["total_ot_nm"])
        if tot < 3000 or round(tot) % 200:
            continue
        seq, d = design(r)
        r0 = s.rmse(seq, d)
        _dt, rt = g.polish_tot(seq, d, tot, max_nfev=3000)
        df, rf = s.polish(seq, d, 0.0, max_nfev=3000)
        out.append(f"{tot:6.0f} {len(seq):3d} {r0:.4e} {rt:.4e} {rf:.4e} {s.total_ot(seq, df):7.1f}")
        print(out[-1], flush=True)
    (s.HERE / "diag5050_repolish.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def seed() -> None:
    r = next(r for r in rows("curve_mono_free.csv") if int(r["layers"]) == 37)
    seq, d = design(r)
    with (s.HERE / "diag5050_seed37.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["seq", "d_nm"])
        w.writeheader()
        w.writerow({"seq": seq, "d_nm": r["d_nm"]})
    print(f"seed N {len(seq)} TOT {s.total_ot(seq, d):.1f} rmse {s.rmse(seq, d):.4e}")


def axes() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def env(name):  # envelope curves: (N, TOT, RMSE)
        return [(int(r["layers"]), QW * float(r["total_qwot"]), float(r["rmse_1601_oracle"])) for r in rows(name)]

    def grad(*names):  # gradual runs: (N, TOT, RMSE)
        return [(int(r["layers"]), float(r["total_ot_nm"]), float(r["mf_oracle"]) / 100) for n in names for r in rows(n)]

    data = {"three-line": (env("curve_3line_foc45-85_free_s1.csv"),
                           grad("gradual_deep4.csv", "gradual_deep4_cont.csv")),
            "50/50": (env("curve_mono_free.csv"), grad("gradual_bs5050_deep4.csv"))}
    fig, axs = plt.subplots(2, 2, figsize=(9, 6.5))
    for row, (name, (e, gr)) in zip(axs, data.items(), strict=True):
        for ax, k, lab in zip(row, (0, 1), ("Number of layers N", "Total optical thickness, nm"), strict=True):
            ax.semilogy([p[k] for p in e], [p[2] for p in e], "o", mfc="none", ms=4, label="envelope search (fixed N)")
            ax.semilogy([p[k] for p in gr], [p[2] for p in gr], "x", ms=4, label="gradual evolution (fixed TOT)")
            ax.set_xlabel(lab)
            ax.set_ylabel("RMSE")
            ax.set_title(name, fontsize=9)
            ax.grid(True, which="both", alpha=0.3)
            ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(s.HERE / "diag5050_axes.png", dpi=150)


if __name__ == "__main__":
    {"repolish": repolish, "seed": seed, "axes": axes}[CMD]()
