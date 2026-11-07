"""Article figures (2026-11-01, owner): best MF against the number of layers (any total optical thickness) and against
the total optical thickness TOT (any number of layers), with the expected MF under random optical-thickness errors.

Robustness: root of the mean MSE over 300 Monte Carlo draws of independent errors of standard deviation
alpha_i = sigma_OT / n_i on the thicknesses, for every design of the N envelope; the second-order criterion of the
article, E[MSE(d + e)] = MSE(d) + sum_i alpha_i^2 ||dr/dd_i||^2, is printed beside it (it holds on the 50/50, within
1.5 %, and fails on the three-line filter: 0.60 against 1.81 at N = 67, sigma 0.5 nm). MF* curves are lower envelopes
(best with N' <= N, best with TOT' <= TOT), monotone by construction (the certificate of the audit section).
usage: SEARCH_TARGET=bs5050 python article_figures.py bs5050 NMAX TOTMAX OUT_DIR
       SEARCH_TARGET=threeline python article_figures.py threeline NMAX TOTMAX OUT_DIR
"""

from __future__ import annotations

import csv
import glob
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import search as s  # noqa: E402

SIGMAS = (0.2, 0.5)  # nm of optical thickness


def mf_of(seq, d) -> float:
    """The problem's merit function: RMSE for the 50/50, MF in % (100 x RMSE) for the three-line filter."""
    return s.rmse(seq, d) * (100.0 if s.TARGET == "threeline" else 1.0)


def robust(seq, d, sigma) -> float:
    res, jac, _c = s.Stack.of(seq).res_jac(np.asarray(d, dtype=float))
    alpha = sigma / np.array([s.N_IDX[m] for m in seq])
    e_mse = float(res @ res + np.sum(alpha ** 2 * np.sum(jac ** 2, axis=0)))
    return np.sqrt(e_mse) * (100.0 if s.TARGET == "threeline" else 1.0)


def monte_carlo(seq, d, sigma, draws=400, seed=1) -> float:
    rng = np.random.default_rng(seed)
    alpha = sigma / np.array([s.N_IDX[m] for m in seq])
    mse = [s.rmse(seq, np.maximum(d + rng.normal(0.0, alpha), 0.0)) ** 2 for _ in range(draws)]
    return np.sqrt(np.mean(mse)) * (100.0 if s.TARGET == "threeline" else 1.0)


def load_rows(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if not r.get("seq") or not r.get("d_nm"):
            continue
        seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
        out.append((seq, d))
    return out


def designs():
    """(label, seq, d) of every design of the problem found in the study files."""
    if s.TARGET == "bs5050":
        files = ["curve_mono_free.csv", "gradual_bs5050_deep4.csv", "diag5050_seed37.csv"]
    else:
        files = sorted(set(glob.glob("front_3line_*free*.csv") + glob.glob("curve_3line_*free*.csv")
                           + [f for f in glob.glob("gradual_*.csv") if "bs5050" not in f]))
    out = []
    for f in files:
        if Path(f).exists():
            out += [(f, seq, d) for seq, d in load_rows(f)]
    return out


def reference():
    """The published reference design: (label, N, TOT, MF), and its layers when the study holds them."""
    if s.TARGET == "bs5050":
        # the authors' published design (example/example_design, with their permission), recomputed on our grid;
        # best_tikh_r1.json is DESIGN's result on their problem (8.6e-5, 26.4 QWOT), not their design
        cfg = json.load((s.ROOT / "example" / "example_design"
                         / "JSON-design-reference-tikhonravov-1996-published-design.json").open(encoding="utf-8"))
        seq = "".join(x["mat"] for x in cfg["front"])
        d = np.array([x["qw"] * float(cfg["l0"]) / 4.0 / s.N_IDX[x["mat"]] for x in cfg["front"]])
        return [("Tikhonravov et al. 1996 (34 layers)", len(seq), s.total_ot(seq, d), mf_of(seq, d), seq, d)]
    # Trubetskov 2020, Fig. 5 (published MF in %): two points of the classical curve and the deep optimum
    return [("Trubetskov 2020, Fig. 5", None, 3802.0, 6.298, None, None),
            ("Trubetskov 2020, Fig. 5", None, 6306.0, 1.548, None, None),
            ("Trubetskov 2020, deep search (101 layers)", 101, 14168.0, 0.0128, None, None)]


def main() -> None:
    kind, nmax, totmax, out_dir = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), Path(sys.argv[4])
    assert kind == s.TARGET, "set SEARCH_TARGET to the same problem"
    out_dir.mkdir(parents=True, exist_ok=True)
    pts = []
    for label, seq, d in designs():
        n = sum(1 for x in d if x > s.DEAD) if s.TARGET == "bs5050" else len(seq)
        pts.append((n, s.total_ot(seq, d), mf_of(seq, d), seq, d, label))
    print(f"{kind}: {len(pts)} designs read", flush=True)
    refs = reference()
    for lab, n, tot, mf, *_ in refs:
        print(f"  reference {lab}: N {n}, TOT {tot:.0f} nm, MF {mf:.4g}", flush=True)
    # lower envelopes
    ns = list(range(1, nmax + 1))
    env_n, best = [], None
    for n in ns:
        cand = [p for p in pts if p[0] == n]
        b = min(cand, key=lambda p: p[2]) if cand else None
        if b is not None and (best is None or b[2] < best[2]):
            best = b
        env_n.append(best)
    tots = np.linspace(0.0, totmax, 401)[1:]
    env_t, srt = [], sorted(pts, key=lambda p: p[1])
    for t in tots:
        cand = [p for p in srt if p[1] <= t]
        env_t.append(min(cand, key=lambda p: p[2]) if cand else None)
    # robustness on the designs of the N envelope (distinct designs only)
    rob = {}
    worst = 1.0
    for p in {id(p): p for p in env_n if p is not None}.values():
        rob[(p[0], round(p[1]))] = [monte_carlo(p[3], p[4], sg, draws=300) for sg in SIGMAS]
        worst = max(worst, rob[(p[0], round(p[1]))][-1] / robust(p[3], p[4], SIGMAS[-1]))
    print(f"  largest Monte Carlo / second-order ratio on the envelope (sigma {SIGMAS[-1]} nm): {worst:.2f}", flush=True)
    for ref in refs:
        if ref[4] is not None:
            print("  reference Monte Carlo: " + ", ".join(f"sigma {sg}: {monte_carlo(ref[4], ref[5], sg, draws=300):.3g}" for sg in SIGMAS))
    # Monte Carlo check on three designs of the envelope
    checks = [p for p in env_n if p is not None][:: max(1, len([p for p in env_n if p is not None]) // 3)][:3]
    for p in checks:
        sg = SIGMAS[-1]
        print(f"  MC check N {p[0]}: second order {robust(p[3], p[4], sg):.4g}, Monte Carlo {monte_carlo(p[3], p[4], sg):.4g}"
              f" (sigma {sg} nm)", flush=True)
    # numbers for the text
    rows = []
    for n, p in zip(ns, env_n, strict=True):
        if p is not None and p[0] == n:
            r = rob[(p[0], round(p[1]))]
            rows.append((n, p[1], p[2], *r))
    with (out_dir / f"{kind}_envelope.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["layers", "tot_nm", "mf", *[f"mf_expected_sigma{sg}" for sg in SIGMAS]])
        w.writerows(rows)
    for sg_i, sg in enumerate(SIGMAS):
        k = int(np.argmin([r[3 + sg_i] for r in rows]))
        print(f"  robust optimum at sigma {sg} nm: N {rows[k][0]}, expected MF {rows[k][3 + sg_i]:.4g} "
              f"(nominal {rows[k][2]:.4g}); at the largest N {rows[-1][0]}: expected {rows[-1][3 + sg_i]:.4g}", flush=True)
    # figure
    unit = "MF (%)" if kind == "threeline" else "RMSE"
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
    ax[0].semilogy([r[0] for r in rows], [r[2] for r in rows], "o-", ms=3, color="C0", label="best design, any TOT")
    for sg_i, sg in enumerate(SIGMAS):
        ax[0].semilogy([r[0] for r in rows], [r[3 + sg_i] for r in rows], "--", color=f"C{1 + sg_i}",
                       label=fr"Monte Carlo, $\sigma_{{OT}}$ = {sg} nm")
    low = 0.6 * min([r[2] for r in rows] + [ref[3] for ref in refs])
    for lab, n, _tot, mf, *_ in refs:
        if n is not None and n <= nmax:
            ax[0].semilogy([n], [mf], "k*", ms=9, label=lab)
        elif n is not None:
            ax[0].annotate(f"{lab.split(',')[0]}: {mf:g} at N = {n} $\\rightarrow$", xy=(nmax, mf),
                           xytext=(0.45 * nmax, mf), fontsize=7, va="center")
    ax[0].set_xlabel("number of layers N")
    ax[0].set_ylabel(unit)
    ax[0].set_xlim(0, nmax)
    ax[0].legend(fontsize=7)
    ok = [(t, p) for t, p in zip(tots, env_t, strict=True) if p is not None]
    ax[1].semilogy([t for t, _ in ok], [p[2] for _, p in ok], "-", color="C0", label="best design, any N")
    for lab, _n, tot, mf, *_ in refs:
        if tot <= totmax:
            ax[1].semilogy([tot], [mf], "k*", ms=9, label=lab if lab not in [a.get_label() for a in ax[1].lines] else None)
        else:
            ax[1].annotate(f"{lab.split(',')[0]}: {mf:g} at {tot:.0f} nm $\\rightarrow$", xy=(totmax, mf),
                           xytext=(0.5 * totmax, mf), fontsize=7, va="center")
    ax[0].set_ylim(bottom=low)
    ax[1].set_ylim(bottom=low)
    if kind == "threeline":
        ax[1].axvline(500.0 ** 2 / (2 * 10.0), color="grey", ls=":", lw=1)
        ax[1].text(500.0 ** 2 / (2 * 10.0), ax[1].get_ylim()[1], r" $\lambda^2/2\Delta\lambda$", fontsize=7, va="top")
    ax[1].set_xlabel("total optical thickness TOT (nm)")
    ax[1].set_xlim(0, totmax)
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / f"{kind}_mf_n_tot.pdf")
    fig.savefig(out_dir / f"{kind}_mf_n_tot.png", dpi=150)
    print(f"  figure -> {out_dir / (kind + '_mf_n_tot.pdf')}", flush=True)


if __name__ == "__main__":
    main()
