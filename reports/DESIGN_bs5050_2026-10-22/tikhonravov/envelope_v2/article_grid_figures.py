"""Figures of the grid section of the article (2026-11-01, owner: show didactically why the wavelength grid matters,
each problem optimized on its nominal grid and on a resolved one; tie the hidden resonances to field enhancement).

grid_mechanisms: what the nominal grid sees and misses, one mechanism per problem. (a) 50/50: our 35-layer design
polished on the 80 nominal points, against the same design optimized on 1601 points, T - 50 % from 400 to 520 nm,
where an interference fringe lambda^2 / (2 TOT) spans two grid steps. (b) Three-line filter: our 109-layer design (MF
0.0145 % on the 277 points) around its resonance at 405.467 nm, hidden between the 1 nm points, and the same design
polished on a 0.005 nm grid. (c) Cissoid: R at the corner of 550 nm, the record (optimized on the 301 points) and the
same design polished on 0.1 nm steps (cissoid_resolved.py), against the exact target. Spectra by the oracle.
field_trap: |E|^2 (incident wave = 1) inside the three-line design at 405 nm (a grid point) and at 405.467 nm (the
hidden resonance), and inside the design polished on 0.005 nm at its resonance (CERTUS field module).
{kind}_two_grids: the frontiers MF(N) and MF(OT) on both grids, from grid_study.py and cissoid_resolved.py.
usage: python article_grid_figures.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import article_spectra as asp
import cissoid_opt as co
import matplotlib
import numpy as np

from certus.core.certus_field_core import calculate_electric_field

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HL = {"H": 2.35, "L": 1.45}
oracle = co.oracle


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def arr(text):
    return np.array([float(v) for v in text.split()])


def spectrum(ns, d, wls, which):
    vals = [oracle.rt_stack(w, [complex(n) for n in ns], np.asarray(d), complex(1.0), complex(1.52)) for w in wls]
    return np.array([v[0] if which == "R" else v[1] for v in vals])


def designs():
    """The designs of the figures: 50/50 (35 layers, 1601 and 80), three-line (nominal, 0.005 nm), cissoid (record and
    its repolish on 0.1 nm)."""
    b35 = next(r for r in rows("curve_mono_free.csv") if int(r["layers"]) == 35)
    b80 = next(r for r in rows("grid_bs5050_repolish.csv")
               if r["source"] == "curve_mono_free.csv" and int(r["layers_before"]) == 35)
    t0 = min(rows("gradual_deep2_cont_seed89_clean2.csv"), key=lambda r: float(r["mf_oracle"]))
    t5 = next(r for r in rows("threeline_refine_probe.csv") if float(r["grid_nm"]) == 0.005)
    rec = next(iter(rows("cissoid_record_best.csv")))
    rep = min(rows("resolved_cissoid_repolish.csv"), key=lambda r: float(r["mf_nominal_before"]))
    return {"5050_1601": (b35["seq"], arr(b35["d_nm"])), "5050_80": (b80["seq"], arr(b80["d_nm"])),
            "3l_nom": (t0["seq"], arr(t0["d_nm"])), "3l_005": (t5["seq"], arr(t5["d_nm"])),
            "cis_rec": (rec["mats"].split(), arr(rec["d_nm"])), "cis_res": (rep["mats"].split(), arr(rep["d_nm"]))}


def grid_mechanisms(ds, out) -> None:
    fig, ax = plt.subplots(1, 3, figsize=(15.0, 3.8))
    # (a) 50/50
    w = np.arange(400.0, 520.0001, 0.05)
    g80 = np.linspace(400.0, 1200.0, 80)
    g80 = g80[g80 <= 520.0]
    for key, col, lab in (("5050_1601", "C0", "optimized on 1601 points"), ("5050_80", "C3", "optimized on 80 points")):
        seq, d = ds[key]
        ax[0].plot(w, 100 * (spectrum([HL[m] for m in seq], d, w, "T") - 0.5), color=col, lw=0.9, label=lab)
    seq, d = ds["5050_80"]
    ax[0].plot(g80, 100 * (spectrum([HL[m] for m in seq], d, g80, "T") - 0.5), "o", color="C3", ms=4,
               label="the 80 nominal points")
    ax[0].set_xlabel("wavelength (nm)")
    ax[0].set_ylabel("T - 50 (%)")
    ax[0].set_title("(a) 50/50, 35 layers: fringes faster than the grid", fontsize=9)
    ax[0].legend(fontsize=7)
    # (b) three-line filter
    w = np.arange(404.0, 407.0001, 0.0005)
    for key, col, lab in (("3l_nom", "C0", "optimized on the 1 nm grid (0.0145 %)"),
                          ("3l_005", "C3", "polished on a 0.005 nm grid")):
        seq, d = ds[key]
        ax[1].plot(w, 100 * spectrum([HL[m] for m in seq], d, w, "T"), color=col, lw=0.9, label=lab)
    seq, d = ds["3l_nom"]
    g1 = np.arange(404.0, 408.0)
    ax[1].plot(g1, 100 * spectrum([HL[m] for m in seq], d, g1, "T"), "o", color="C0", ms=5, label="the nominal points")
    ax[1].set_xlabel("wavelength (nm)")
    ax[1].set_ylabel("T (%)  (target 0)")
    ax[1].set_title("(b) three-line filter, 109 layers: a resonance between two points", fontsize=9)
    ax[1].legend(fontsize=7)
    # (c) cissoid
    w = np.arange(546.0, 554.0001, 0.01)
    ax[2].plot(w, 100 * co.exact_target(w), color="0.5", lw=2.0, label="target (exact cissoid)")
    for key, col, lab in (("cis_rec", "C0", "optimized on the 301 points"), ("cis_res", "C3", "polished on 0.1 nm steps")):
        m, d = ds[key]
        ax[2].plot(w, 100 * spectrum([co.MATS[x] for x in m], d, w, "R"), color=col, lw=0.9, label=lab)
    m, d = ds["cis_rec"]
    g1 = np.arange(546.0, 555.0)
    ax[2].plot(g1, 100 * spectrum([co.MATS[x] for x in m], d, g1, "R"), "o", color="C0", ms=4, label="the nominal points")
    ax[2].set_xlabel("wavelength (nm)")
    ax[2].set_ylabel("R (%)")
    ax[2].set_title("(c) cissoid, record: a target with a corner", fontsize=9)
    ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "grid_mechanisms.pdf")
    fig.savefig(out / "grid_mechanisms.png", dpi=150)


def field_profile(seq, d, wl):
    """(OT from the substrate, |E|^2) inside the stack, incident wave = 1 (CERTUS field module)."""
    types = [0 if m == "H" else 1 for m in seq]
    qw = [4.0 * HL[m] * t / 500.0 for m, t in zip(seq, d, strict=True)]
    z, e2, ep_air_first, _i, _a = calculate_electric_field(2.35, 1.45, 1.52, 500.0, float(wl), qw, types, 1.0, 40)
    n_air_first = [HL[m] for m in seq][::-1]
    edges = np.concatenate([[0.0], np.cumsum(ep_air_first)])
    ot_edges = np.concatenate([[0.0], np.cumsum(np.array(ep_air_first) * np.array(n_air_first))])
    layer = np.clip(np.searchsorted(edges, z, side="right") - 1, 0, len(seq) - 1)
    ot_from_air = ot_edges[layer] + (z - edges[layer]) * np.array(n_air_first)[layer]
    return ot_edges[-1] - ot_from_air, e2


def field_trap(ds, out) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    for key, wl, col, lab in (("3l_nom", 405.0, "0.5", "405 nm, a nominal grid point"),
                              ("3l_nom", 405.467, "C0", "405.467 nm, the hidden resonance (FWHM 0.012 nm)"),
                              ("3l_005", 405.4674, "C3", "polished on 0.005 nm: its resonance (FWHM 0.004 nm)")):
        x, e2 = field_profile(*ds[key], wl)
        ax.semilogy(x, e2, color=col, lw=0.8, label=lab)
    ax.set_xlabel("optical thickness from the substrate (nm)")
    ax.set_ylabel(r"$|E|^2$ (incident wave = 1)")
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "field_trap.pdf")
    fig.savefig(out / "field_trap.png", dpi=150)


def envelope(pts, key):
    """Lower envelope: for each value v of key (N or OT), the design with the least own-grid MF among key <= v."""
    srt = sorted(pts, key=lambda p: p[key])
    out, best = [], None
    for p in srt:
        if best is None or p["mf"] < best["mf"]:
            best = p
            out.append((p[key], p))
    return out


def stairs(ax, env, xmax, col, ls, lab, other=False):
    xs = [x for x, _p in env if x <= xmax] + [xmax]
    ys = [(p["mf_other"] if other else p["mf"]) for x, p in env if x <= xmax]
    if ys:
        ax.step(xs, [*ys, ys[-1]], where="post", color=col, ls=ls, lw=1.1, label=lab)


def two_grids(ax_n, ax_t, pts_nom, pts_res, labels, refs, xmax_n, xmax_t, unit, extra=None) -> None:
    """Draw one problem's frontiers MF(N) on ax_n and MF(OT) on ax_t, on both grids."""
    for ax, key, xmax in ((ax_n, "n", xmax_n), (ax_t, "t", xmax_t)):
        for pts, col, (lab_own, lab_other) in ((pts_nom, "C0", labels[0]), (pts_res, "C3", labels[1])):
            if not pts:
                continue
            env = envelope(pts, key)
            stairs(ax, env, xmax, col, "-", lab_own)
            stairs(ax, env, xmax, col, ":", lab_other, other=True)
        for lab, n, t, mf, mk in refs:
            x = n if key == "n" else t
            if x is not None and x <= xmax:
                ax.plot([x], [mf], mk, color="k", ms=7, label=lab)
        for lab, n, t, mf, mk in extra or []:
            x = n if key == "n" else t
            if x is not None and x <= xmax:
                ax.plot([x], [mf], mk, color="C3", ms=7, label=lab)
        ax.set_yscale("log")
        ax.set_xlim(0, xmax + (1 if key == "n" else 0))
        ax.set_ylabel(unit)
    ax_n.set_xlabel("number of layers N")
    ax_n.legend(fontsize=6.3)


def robustness(out) -> None:
    """The nominal frontier MF(N) of each problem and its Monte Carlo expectation under random errors, from the
    {kind}_envelope.csv files of article_figures.py and article_figures_cissoid.py (judged on the study's grid); for the
    three-line filter, from threeline_mc_resolved.csv when it exists: the same designs and draws judged on 0.001 nm
    steps, the nominal frontier kept for reference."""
    fig, ax = plt.subplots(1, 3, figsize=(15.0, 3.8))
    for a, (kind, title, unit) in zip(ax, (("bs5050", "(a) 50/50, 1601 points", "RMSE"),
                                           ("threeline", "(b) three-line filter, 277 points", "MF (%)"),
                                           ("cissoid", "(c) cissoid, 301 points", "MF")), strict=True):
        if kind == "threeline" and Path("threeline_mc_resolved.csv").exists():
            env = rows("threeline_mc_resolved.csv")
            n = [int(r["layers"]) for r in env]
            a.semilogy(n, [float(r["mf_nominal"]) for r in env], "o-", ms=3, color="C0",
                       label="best design on 1 nm steps, no errors")
            a.semilogy(n, [float(r["mf_resolved"]) for r in env], ":", color="C0", label="the same on 0.001 nm steps")
            for sg, ls, col in (("0.2", "--", "C1"), ("0.5", "-.", "C2")):
                a.semilogy(n, [float(r[f"mc_resolved_sigma{sg}"]) for r in env], ls, color=col,
                           label=fr"Monte Carlo on 0.001 nm steps, $\sigma_{{OT}}$ = {sg} nm")
            a.set_title("(b) three-line filter, errors judged on 0.001 nm steps", fontsize=9)
            a.legend(fontsize=6.5)
        else:
            env = rows(out / f"{kind}_envelope.csv")
            n = [int(r["layers"]) for r in env]
            a.semilogy(n, [float(r["mf"]) for r in env], "o-", ms=3, color="C0", label="best design, no errors")
            for sg, ls, col in (("0.2", "--", "C1"), ("0.5", "-.", "C2")):
                a.semilogy(n, [float(r[f"mf_expected_sigma{sg}"]) for r in env], ls, color=col,
                           label=fr"Monte Carlo, $\sigma_{{OT}}$ = {sg} nm")
            a.set_title(title, fontsize=9)
        a.set_xlabel("number of layers N")
        a.set_ylabel(unit)
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "robustness.pdf")
    fig.savefig(out / "robustness.png", dpi=150)


def frontiers(out) -> None:
    """The three problems' frontiers on both grids in one figure: MF(N) on top, MF(OT) below."""
    fig, ax = plt.subplots(2, 3, figsize=(15.5, 8.0))
    # 50/50: the study's designs (optimized on 1601 points) and their repolish on the 80 nominal points
    g = rows("grid_bs5050_repolish.csv")
    nom = [{"n": int(r["layers"]), "t": float(r["tot"]), "mf": float(r["mf_nominal"]), "mf_other": float(r["mf_resolved"])}
           for r in g]
    res = [{"n": int(r["layers_before"]), "t": float(r["tot_before"]), "mf": float(r["mf_resolved_before"]),
            "mf_other": float(r["mf_nominal_before"])} for r in g]
    two_grids(ax[0, 0], ax[1, 0], nom, res,
              (("optimized and judged on 80 points (nominal)", "same designs judged on 1601 points"),
               ("optimized and judged on 1601 points (resolved)", "same designs judged on 80 points")),
              [("Tikhonravov et al. 1996, judged on 1601 points", 34, 3924.0, 1.765e-4, "*")], 35, 4000.0, "RMSE")
    ax[0, 0].set_title("(a) 50/50 beamsplitter", fontsize=9)
    ax[1, 0].set_xlabel("optical thickness (nm)")
    # three-line filter: the study's designs (all optimized on the nominal grid) ranked by either grid, and those
    # cleaned of their hidden resonances (threeline_track.py batch height); the probe design re-optimized on 0.001 nm
    g = rows("grid_threeline_judged.csv")
    nom = [{"n": int(r["layers"]), "t": float(r["tot"]), "mf": float(r["mf_nominal"]), "mf_other": float(r["mf_resolved"])}
           for r in g]
    res = [{"n": int(r["layers"]), "t": float(r["tot"]), "mf": float(r["mf_resolved"]), "mf_other": float(r["mf_nominal"])}
           for r in g]
    if Path("grid_threeline_tracked.csv").exists():
        res += [{"n": int(r["layers"]), "t": float(r["tot"]), "mf": float(r["mf_resolved"]),
                 "mf_other": float(r["mf_nominal"])} for r in rows("grid_threeline_tracked.csv")]
    cl = rows("threeline_track_height_trub101.csv")[-1]
    t1 = float(np.sum(arr(cl["d_nm"]) * np.array([HL[m] for m in cl["seq"]])))
    two_grids(ax[0, 1], ax[1, 1], nom, res,
              (("best on 1 nm steps (nominal, 277 points)", "same designs judged on 0.001 nm steps"),
               ("best on 0.001 nm steps (resolved)", "same designs judged on 1 nm steps")),
              [("Trubetskov 2020, 101 layers, on 1 nm steps", 101, 14168.0, 0.0128, "*"),
               ("the same, judged on 0.001 nm steps", 101, 14168.0, 0.348, "x")], 120, 15000.0, "MF (%)",
              extra=[("the same, cleaned of its hidden resonances", len(cl["seq"]), t1, float(cl["mf_resolved"]), "D")])
    ax[0, 1].set_title("(b) three-line filter", fontsize=9)
    ax[1, 1].set_xlabel("optical thickness (nm)")
    # cissoid: every design of the study and its repolish on 0.1 nm steps, and the descent on that grid
    g = rows("resolved_cissoid_repolish.csv")
    nom = [{"n": int(r["layers"]), "t": float(r["ot_d_before"]), "mf": float(r["mf_nominal_before"]),
            "mf_other": float(r["mf_resolved_before"])} for r in g]
    res = [{"n": int(r["layers"]), "t": float(r["ot_d_after"]), "mf": float(r["mf_resolved_after"]),
            "mf_other": float(r["mf_nominal_after"])} for r in g]
    if Path("resolved_cissoid_descent.csv").exists():
        last = rows("resolved_cissoid_descent.csv")[-1]
        res.append({"n": int(last["layers"]), "t": float(last["ot_d_nm"]), "mf": float(last["mf_oracle"]),
                    "mf_other": float(last["mf_nominal"])})
    two_grids(ax[0, 2], ax[1, 2], nom, res,
              (("optimized and judged on 301 points (nominal)", "same designs judged on 0.1 nm steps"),
               ("re-optimized and judged on 0.1 nm steps (resolved)", "same designs judged on 301 points")),
              [("contest winner (nominal)", 50, None, 0.0139, "*")], 50, 22000.0, "MF")
    ax[0, 2].set_title("(c) OIC 2016 cissoid", fontsize=9)
    ax[1, 2].set_xlabel("dielectric optical thickness (nm)")
    fig.tight_layout()
    fig.savefig(out / "two_grids.pdf")
    fig.savefig(out / "two_grids.png", dpi=150)


def cure(out) -> None:
    """The three-line design of 109 layers as optimized on the nominal grid, polished on 270 007 points (0.001 nm,
    threeline_refine_probe.py) and with its resonances charged by their height (threeline_track.py height, 40 rounds):
    T over 400-430 nm every 0.0005 nm (CERTUS kernel), and |E|^2 in the stack at each one's highest stop-band peak."""
    t0 = min(rows("gradual_deep2_cont_seed89_clean2.csv"), key=lambda r: float(r["mf_oracle"]))
    p1 = next(r for r in rows("threeline_refine_probe.csv") if float(r["grid_nm"]) == 0.001)
    tr = rows("threeline_track_height40_ours109.csv")[-1]
    cases = [("optimized on the 1 nm grid: 0.0145 % on it, 0.378 % resolved", t0, "C0"),
             ("polished on 0.001 nm steps (270 007 points): 0.157 %", p1, "C1"),
             (f"resonances charged by their height (277 + 3 points): {float(tr['mf_resolved']):.3f} %", tr, "C2")]
    w = np.arange(400.0, 430.0001, 0.0005)
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 3.9), gridspec_kw={"width_ratios": [1.25, 1.0]})
    for label, r, col in cases:
        seq, d = r["seq"], arr(r["d_nm"])
        t = asp.dense_t([HL[m] for m in seq], d, w)
        ax[0].plot(w, 100 * t, color=col, lw=0.7, rasterized=True, label=label)
        lam = float(w[int(np.argmax(t))])
        x, e2 = field_profile(seq, d, lam)
        ax[1].semilogy(x, e2, color=col, lw=0.7, label=f"at {lam:.3f} nm: max {e2.max():.0f}")
    g = np.arange(400.0, 431.0)
    seq, d = tr["seq"], arr(tr["d_nm"])
    ax[0].plot(g, 100 * asp.dense_t([HL[m] for m in seq], d, g), "k.", ms=3, label="the nominal points")
    ax[0].set_xlabel("wavelength (nm)")
    ax[0].set_ylabel("T (%)  (target 0)")
    ax[0].set_title("(a) the stop band 400-430 nm of the 109-layer design", fontsize=9)
    ax[0].legend(fontsize=7)
    ax[1].set_xlabel("optical thickness from the substrate (nm)")
    ax[1].set_ylabel(r"$|E|^2$ (incident wave = 1)")
    ax[1].set_title("(b) the field at each design's highest peak", fontsize=9)
    ax[1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "cure.pdf")
    fig.savefig(out / "cure.png", dpi=150)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    cure(out)
    robustness(out)
    frontiers(out)
    ds = designs()
    grid_mechanisms(ds, out)
    field_trap(ds, out)
    print("figures written to", out, flush=True)


if __name__ == "__main__":
    main()
