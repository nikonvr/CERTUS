"""Spectral figures of the article (2026-11-01, owner), computed by the independent judge (tests/oracle/tmm_reference.py)
except the dense three-line curves (CERTUS kernel, `dense_t`, every 0.002 nm, so that the resonances hidden between the
1 nm points show).

teaser: the three-line filter on its 277 points and between them: our best design (0.0145 %, 109 layers) and
Trubetskov's deep-search design (0.0128 %, 101 layers, read from his Fig. 4, 2020), whole band and 400-430 nm.
designs_spectra: the best designs of the three problems, spectra (top) and index profiles against the optical thickness
from the substrate (bottom). 50/50: T - 50 % of our 35-layer design and of the published 34-layer one (Tikhonravov et al.
1996), 1601 points. Three-line: T around the first passband, both designs. Cissoid: R of the record every 0.1 nm against
the target, with the 5-95 % band of 200 Monte Carlo draws of the errors of the article (sigma_OT 0.2 nm on the
dielectric layers, half of it on the physical thickness of the metal layers).
usage: python article_spectra.py OUT_DIR
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import bs5050_grid as bg
import cissoid_opt as co
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HL = {"H": 2.35, "L": 1.45}
PASS = ((445, 455), (505, 515), (635, 645))
BANDS = (*PASS, (400, 440), (460, 500), (520, 630), (650, 700))  # the three-line bands of search.py
oracle = co.oracle


def spectrum(ns, d, wls, which):
    vals = [oracle.rt_stack(w, [complex(n) for n in ns], np.asarray(d), complex(1.0), complex(1.52)) for w in wls]
    return np.array([v[0] if which == "R" else v[1] for v in vals])


def dense_t(ns, d, wls, chunk=20000) -> np.ndarray:
    """T at many wavelengths by the CERTUS kernel (residuals against a zero target, unit weights), by chunks."""
    seq = "".join("H" if n == HL["H"] else "L" for n in ns)
    out = []
    for idx in np.array_split(np.arange(len(wls)), -(-len(wls) // chunk)):
        g = bg.kernel_grid(len(idx))
        g.update(k0=2.0 * np.pi / wls[idx], tgt=np.zeros(len(idx)), sqw=np.ones(len(idx)))
        out.append(bg.res_jac(seq, d, g)[0])
    return np.concatenate(out)


def row(path, pick=None):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    r = pick(rows) if pick else rows[-1]
    return r["seq"] if "seq" in r else r["mats"], np.array([float(v) for v in r["d_nm"].split()])


def profile(ax, mats, d, nfun, title):
    """Refractive index against the optical thickness counted from the substrate (owner, 2026-11-01); a metal layer
    has no optical thickness on this axis (as on the cissoid's frontier axis) and is drawn as a vertical line."""
    ot = [nfun(m) * t if nfun(m) is not None else 0.0 for m, t in zip(mats, d, strict=True)]
    z = np.concatenate([[0.0], np.cumsum(ot)])
    for i, m in enumerate(mats):
        n = nfun(m)
        if n is None:  # a metal layer
            ax.axvline(z[i], color="0.2" if m == "A" else "0.6", lw=1.6)
        else:
            ax.plot([z[i], z[i + 1]], [n, n], color="C0", lw=1.2)
            if i + 1 < len(mats) and nfun(mats[i + 1]) is not None:
                ax.plot([z[i + 1], z[i + 1]], [n, nfun(mats[i + 1])], color="C0", lw=0.6)
    ax.set_xlabel("optical thickness from the substrate (nm)")
    ax.set_ylabel("refractive index")
    ax.set_title(title, fontsize=9)


def teaser(out, ours, theirs) -> None:
    wl = np.arange(400.0, 700.0001, 0.002)
    t_ours, t_pub = dense_t([HL[m] for m in ours[0]], ours[1], wl), dense_t([HL[m] for m in theirs[0]], theirs[1], wl)
    grid = np.concatenate([np.arange(a, b + 1.0) for a, b in BANDS])
    t_grid = dense_t([HL[m] for m in ours[0]], ours[1], grid)
    fig, ax = plt.subplots(1, 2, figsize=(13.0, 3.9), gridspec_kw={"width_ratios": [1.7, 1.0]})
    for a, lo, hi in ((ax[0], 400.0, 700.0), (ax[1], 400.0, 430.0)):
        for p, q in PASS:
            a.axvspan(p, q, color="0.9", lw=0)
        m = (wl >= lo) & (wl <= hi)
        a.plot(wl[m], 100 * t_pub[m], color="C1", lw=0.6, rasterized=True,
               label=f"Trubetskov 2020, {len(theirs[0])} layers: MF 0.0128 % on the points")
        a.plot(wl[m], 100 * t_ours[m], color="C0", lw=0.6, rasterized=True,
               label=f"ours, {len(ours[0])} layers: MF 0.0145 % on the points")
        g = (grid >= lo) & (grid <= hi)
        a.plot(grid[g], 100 * t_grid[g], "k.", ms=2.5 if a is ax[1] else 1.2, label="the 277 points of the problem")
        a.set_xlim(lo, hi)
        a.set_xlabel("wavelength (nm)")
        a.set_ylabel("T (%)")
    ax[0].set_title("(a) the whole band: target T = 1 in the grey passbands, 0 elsewhere", fontsize=9)
    ax[1].set_title("(b) 400-430 nm: resonances between the points", fontsize=9)
    ax[0].legend(fontsize=7, loc="center right")
    fig.tight_layout()
    fig.savefig(out / "teaser.pdf")
    fig.savefig(out / "teaser.png", dpi=150)


def designs(out, five, pub, three, theirs, cis) -> None:
    fig, ax = plt.subplots(2, 3, figsize=(15.0, 7.2))
    # 50/50
    wl = np.linspace(400.0, 1200.0, 1601)
    t_ours, t_pub = spectrum([HL[m] for m in five[0]], five[1], wl, "T"), spectrum([HL[m] for m in pub[0]], pub[1], wl, "T")
    ax[0, 0].plot(wl, 100 * (t_pub - 0.5), color="C1", lw=0.8, label=f"Tikhonravov et al. 1996, {len(pub[0])} layers")
    ax[0, 0].plot(wl, 100 * (t_ours - 0.5), color="C0", lw=1.0, label=f"ours, {len(five[0])} layers")
    ax[0, 0].set_xlabel("wavelength (nm)")
    ax[0, 0].set_ylabel("T - 50 (%)")
    ax[0, 0].set_title("(a) 50/50 beamsplitter", fontsize=9)
    ax[0, 0].legend(fontsize=7)
    profile(ax[1, 0], five[0], five[1], lambda m: HL[m], f"(d) 50/50, ours ({len(five[0])} layers)")
    print(f"50/50: max |T-0.5| ours {np.abs(t_ours - 0.5).max():.2e}, published {np.abs(t_pub - 0.5).max():.2e}", flush=True)
    # three-line filter, first passband
    wl = np.arange(430.0, 470.0001, 0.002)
    ax[0, 1].axvspan(*PASS[0], color="0.9", lw=0)
    ax[0, 1].plot(wl, 100 * dense_t([HL[m] for m in theirs[0]], theirs[1], wl), color="C1", lw=0.8,
                  label=f"Trubetskov 2020, {len(theirs[0])} layers")
    ax[0, 1].plot(wl, 100 * dense_t([HL[m] for m in three[0]], three[1], wl), color="C0", lw=0.8,
                  label=f"ours, {len(three[0])} layers")
    ax[0, 1].set_xlabel("wavelength (nm)")
    ax[0, 1].set_ylabel("T (%)")
    ax[0, 1].set_title("(b) three-line filter, first passband", fontsize=9)
    ax[0, 1].legend(fontsize=7)
    profile(ax[1, 1], three[0], three[1], lambda m: HL[m], f"(e) three-line, ours ({len(three[0])} layers)")
    # cissoid
    m, d = cis
    ns = [co.MATS[x] for x in m]
    wl = np.linspace(400.0, 700.0, 3001)
    rng = np.random.default_rng(1)
    a = np.array([0.2 / float(np.real(co.MATS[x])) if not np.iscomplex(co.MATS[x]) else 0.1 for x in m])
    draws = np.array([spectrum(ns, np.maximum(d + rng.normal(0.0, a), 0.0), co.W_FULL, "R") for _ in range(200)])
    ax[0, 2].fill_between(co.W_FULL, 100 * np.percentile(draws, 5, axis=0), 100 * np.percentile(draws, 95, axis=0),
                          color="C2", alpha=0.3, lw=0, label=r"5-95 % under errors, $\sigma_{OT}$ = 0.2 nm")
    ax[0, 2].plot(wl, 100 * co.exact_target(wl), color="0.4", lw=2.2, label="target (cissoid)")
    ax[0, 2].plot(wl, 100 * spectrum(ns, d, wl, "R"), color="C0", lw=0.7, label="record, MF 0.00921")
    ax[0, 2].set_xlabel("wavelength (nm)")
    ax[0, 2].set_ylabel("R (%)")
    ax[0, 2].set_title("(c) OIC 2016 cissoid", fontsize=9)
    ax[0, 2].legend(fontsize=7)
    profile(ax[1, 2], m, d, lambda x: None if np.iscomplex(co.MATS[x]) else float(np.real(co.MATS[x])),
            "(f) cissoid record (lines: Ag dark, Ni light)")
    fig.tight_layout()
    fig.savefig(out / "designs_spectra.pdf")
    fig.savefig(out / "designs_spectra.png", dpi=150)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    five = row("curve_mono_free.csv", lambda rs: next(r for r in rs if int(r["layers"]) == 35))
    cfg = json.load((co.s.ROOT / "example" / "example_design"
                     / "JSON-design-reference-tikhonravov-1996-published-design.json").open(encoding="utf-8"))
    pseq = "".join(x["mat"] for x in cfg["front"])
    pub = (pseq, np.array([x["qw"] * float(cfg["l0"]) / 4.0 / HL[x["mat"]] for x in cfg["front"]]))
    three = row("gradual_deep2_cont_seed89_clean2.csv", lambda rs: min(rs, key=lambda r: float(r["mf_oracle"])))
    theirs = row("fig4_2020_designs.csv", lambda rs: min(rs, key=lambda r: float(r["mf_oracle"])))
    rec = next(csv.DictReader(open("cissoid_record_best.csv", encoding="utf-8")))
    cis = (rec["mats"].split(), np.array([float(v) for v in rec["d_nm"].split()]))
    teaser(out, three, theirs)
    designs(out, five, pub, three, theirs, cis)
    print("teaser.pdf and designs_spectra.pdf ->", out, flush=True)


if __name__ == "__main__":
    main()
