"""Three-line filter: CERTUS gradual evolution against Trubetskov, AO 59, A75 (2020), Fig. 5, up to TOT_MAX.

Inputs: gradual_classic.csv, gradual_deep4.csv, gradual_deep4_cont.csv (designs, oracle MF) and
trubetskov2020_fig5_digitized.csv (their markers, read from the vector graphics of the PDF).
Cleaning as in Trubetskov 2020 ("only layers with thicknesses less than 5 nm were removed"): layers under 5 nm
(physical) are dropped, equal neighbours merged, then the design is re-optimized at the same TOT with d >= 5 nm;
MF judged by the oracle.

usage: python compare3line.py TOT_MAX
outputs: compare3line.txt, threeline_compare.png, threeline_layers.png
"""

from __future__ import annotations

import csv
import sys

import gradual as g
import matplotlib
import numpy as np
import search as s

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FLOOR = 5.0


def load(name: str) -> list[dict]:
    f = s.HERE / name
    if not f.exists():
        return []
    with f.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def clean(seq: str, d: np.ndarray, tot: float):
    """Drop layers under FLOOR nm and re-optimize at the same TOT until none appears, then a last polish with
    d >= FLOOR."""
    for _ in range(10):
        seq, d = s.normalize(seq, d, FLOOR)
        d, _r = g.polish_tot(seq, d, tot)
        if d.min() >= FLOOR:
            break
    seq, d = s.normalize(seq, d, FLOOR)
    st = s.Stack.of(seq)
    n = np.array([s.N_IDX[m] for m in seq])
    d = s.least_squares(lambda x: np.append(st.res_jac(x)[0], g.TOT_W * (n @ x - tot) / tot), np.maximum(d, FLOOR),
                        jac=lambda x: np.vstack([st.res_jac(x)[1], g.TOT_W * n / tot]), bounds=(FLOOR, np.inf),
                        method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=400).x
    return seq, d, s.oracle_rmse(seq, d)


def main() -> None:
    tot_max = float(sys.argv[1])
    trub = load("trubetskov2020_fig5_digitized.csv")
    tc = sorted((float(r["total_ot_nm"]), float(r["mf_percent"])) for r in trub if r["method"] == "classical")
    td = sorted((float(r["total_ot_nm"]), float(r["mf_percent"])) for r in trub if r["method"] == "deep")
    runs = {"classical": load("gradual_classic.csv"), "deep": load("gradual_deep4.csv") + load("gradual_deep4_cont.csv")}
    out = [f"three-line filter, CERTUS gradual evolution vs Trubetskov 2020 Fig. 5, TOT <= {tot_max:.0f} nm",
           "kind  TOT  N  MF_oracle%  | cleaned (>= 5 nm): N  MF%  | Trubetskov same kind, best within +-150 nm"]
    pts: dict[str, list] = {}
    for kind, rows in runs.items():
        ref = tc if kind == "classical" else td
        seen = {}
        for r in rows:  # the continuation repeats its first TOT: keep the last design of each TOT
            seen[round(float(r["total_ot_nm"]))] = r
        for tot in sorted(seen):
            r = seen[tot]
            if tot > tot_max:
                continue
            seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
            mf = float(r["mf_oracle"])
            row = [kind, tot, len(seq), mf]
            if (tot >= 6000 and tot % 500 == 0) or abs(tot - 9700) < 1:
                cs, _cd, cr = clean(seq, d, tot)
                row += [len(cs), 100 * cr]
                pts.setdefault(kind + "_clean", []).append((tot, 100 * cr))
            pts.setdefault(kind, []).append((tot, mf))
            near = [y for x, y in ref if abs(x - tot) <= 150]
            if len(row) > 4:
                theirs = f"{min(near):.4f}" if near else "-"
                out.append(f"{kind:9s} {tot:6d} {row[2]:4d} {mf:8.4f} | {row[4]:4d} {row[5]:8.4f} | {theirs}")
    # 2026-10-28: fixed-N envelope search started from the gradual designs (campaign9, arm A), best design per 100 nm
    # of TOT, oracle MF; the design nearest each multiple of 500 nm is also cleaned at 5 nm
    arm_a = load("front_3line_none_foc70-100_free_s1.csv")
    if arm_a:
        out.append("fixed-N search from the gradual designs (arm A): TOT  N  MF_oracle%  | cleaned: N  MF%  | Trubetskov deep")
        done = set()
        for r in sorted(arm_a, key=lambda r: float(r["total_ot_nm"])):
            tot = float(r["total_ot_nm"])
            if tot < 6000 or tot > tot_max:
                continue
            mf = float(r["mf_oracle"])
            pts.setdefault("armA", []).append((tot, mf))
            key = round(tot / 500)
            if key in done:
                continue
            done.add(key)
            seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
            cs, _cd, cr = clean(seq, d, tot)
            pts.setdefault("armA_clean", []).append((tot, 100 * cr))
            near = [y for x, y in td if abs(x - tot) <= 150]
            theirs = f"{min(near):.4f}" if near else "-"
            out.append(f"armA      {tot:6.0f} {len(seq):4d} {mf:8.4f} | {len(cs):4d} {100 * cr:8.4f} | {theirs}")
    (s.HERE / "compare3line.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    def xy(a):
        return [p[0] for p in a], [p[1] for p in a]

    ax.semilogy(*xy(tc), "x", color="tab:orange", ms=5, label="Trubetskov 2020 Fig. 5, classical (digitized)")
    ax.semilogy(*xy(td), "s", mfc="none", color="tab:red", ms=4, label="Trubetskov 2020 Fig. 5, deep search")
    ax.semilogy(*xy(pts["classical"]), "x", color="tab:green", ms=4, label="CERTUS classical")
    ax.semilogy(*xy(pts["deep"]), "o", mfc="none", color="tab:blue", ms=4, label="CERTUS deep search K=4")
    if "deep_clean" in pts:
        ax.semilogy(*xy(pts["deep_clean"]), "D", color="tab:blue", ms=5, label="CERTUS deep, layers < 5 nm removed")
    if "armA" in pts:
        ax.semilogy(*xy(pts["armA"]), "^", mfc="none", color="tab:purple", ms=4,
                    label="CERTUS gradual + fixed-N search")
        ax.semilogy(*xy(pts["armA_clean"]), "^", color="tab:purple", ms=6, label="same, layers < 5 nm removed")
    ax.semilogy([9687.5], [0.191], "k*", ms=11, label="Tikhonravov 2012: N=75, MF 0.191")
    ax.set_xlim(0, tot_max + 300)
    ax.set_ylim(0.01, 100)
    ax.set_xlabel("Total optical thickness, nm")
    ax.set_ylabel("Merit function, %")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7.5)
    ax.set_title("Three-line filter: CERTUS vs Trubetskov 2020 Fig. 5 (oracle MF)", fontsize=9)
    fig.tight_layout()
    fig.savefig(s.HERE / "threeline_compare.png", dpi=150)

    deep = {round(float(r["total_ot_nm"])): r for r in runs["deep"]}
    fig, axs = plt.subplots(2, 1, figsize=(7.5, 5), sharex=True)
    for ax, want in zip(axs, (9700, min(int(tot_max), max(deep))), strict=True):
        tot = min(deep, key=lambda t: abs(t - want))
        r = deep[tot]
        seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
        ot = d * np.array([s.N_IDX[m] for m in seq])
        ax.bar(np.arange(1, len(seq) + 1), ot, color=["tab:red" if m == "H" else "tab:blue" for m in seq])
        ax.set_ylabel("Optical thickness, nm")
        ax.set_title(f"CERTUS deep: TOT {tot} nm, N {len(seq)}, MF {float(r['mf_oracle']):.3f} % "
                     "(layers from the substrate; red H, blue L)", fontsize=8)
    axs[-1].set_xlabel("Layer number")
    fig.tight_layout()
    fig.savefig(s.HERE / "threeline_layers.png", dpi=150)


if __name__ == "__main__":
    main()
