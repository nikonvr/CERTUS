"""Article figure for the OIC 2016 cissoid (2026-11-01, owner): best MF against the number of layers (N <= 50, any
dielectric optical thickness) and against the dielectric optical thickness OT_d = sum of n d over the dielectric layers
(any N <= 50, the contest's cap), with the MF expected under random thickness errors.

Every design of the study's cissoid csv files (columns mats, d_nm) with N <= 50 and every layer >= 3 nm is judged on the
301 points (CERTUS kernel; the records are the oracle's). Lower envelopes: best with N' <= N, best with OT_d' <= OT_d.
Errors: independent, of standard deviation sigma / n on the physical thickness of a dielectric layer (sigma of optical
thickness) and sigma / 2 on a metal layer; root of the mean MF^2 over 300 Monte Carlo draws, the second-order criterion
printed beside it for the record.
usage: python article_figures_cissoid.py OTMAX OUT_DIR
"""

from __future__ import annotations

import csv
import glob
import sys
from pathlib import Path

import cissoid_opt as co
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SIGMAS = (0.2, 0.5)
DIEL = "FLBMTH"


def ot_d(m, d) -> float:
    return float(sum(co.MATS[x].real * t for x, t in zip(m, d, strict=True) if x in DIEL))


def alphas(m, sigma):
    return np.array([sigma / co.MATS[x].real if x in DIEL else sigma / 2.0 for x in m])


def monte_carlo(m, d, sigma, draws=300, seed=1) -> float:
    rng = np.random.default_rng(seed)
    a = alphas(m, sigma)
    return float(np.sqrt(np.mean([co.mf_full(m, np.maximum(d + rng.normal(0.0, a), 0.0)) ** 2 for _ in range(draws)])))


def second_order(m, d, sigma) -> float:
    res, jac = co.res_jac_full(m, d)
    return float(np.sqrt(res @ res + np.sum(alphas(m, sigma) ** 2 * np.sum(jac ** 2, axis=0))))


def designs():
    out, seen = [], set()
    for f in sorted(glob.glob("cissoid_*.csv")):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
        for r in rows:
            if not r.get("mats") or not r.get("d_nm"):
                continue
            m, d = r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])
            if len(m) != len(d) or len(m) > co.N_MAX or d.min() < co.FLOOR - 1e-6 or any(x not in co.MATS for x in m):
                continue
            key = (" ".join(m), round(float(d.sum()), 2))
            if key not in seen:
                seen.add(key)
                out.append((m, d, f))
    return out


def main() -> None:
    otmax, out_dir = float(sys.argv[1]), Path(sys.argv[2])
    pts = [(len(m), ot_d(m, d), co.mf_full(m, d), m, d, f) for m, d, f in designs()]
    print(f"cissoid: {len(pts)} distinct designs with N <= 50 and d >= 3 nm", flush=True)
    rec = next(csv.DictReader(open("cissoid_record_best.csv", encoding="utf-8")))
    rm, rd = rec["mats"].split(), np.array([float(v) for v in rec["d_nm"].split()])
    print(f"  record {float(rec['mf_oracle']):.6f}: N {len(rm)}, OT_d {ot_d(rm, rd):.0f} nm; "
          + "; ".join(f"sigma {sg}: Monte Carlo {monte_carlo(rm, rd, sg):.4f}, second order {second_order(rm, rd, sg):.4f}"
                      for sg in SIGMAS), flush=True)
    rows, best = [], None
    for n in range(1, co.N_MAX + 1):
        cand = [p for p in pts if p[0] == n]
        b = min(cand, key=lambda p: p[2]) if cand else None
        if b is not None and (best is None or b[2] < best[2]):
            best = b
            rows.append((n, b[1], b[2], *[monte_carlo(b[3], b[4], sg) for sg in SIGMAS], b[5]))
    with (out_dir / "cissoid_envelope.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["layers", "ot_d_nm", "mf", *[f"mf_expected_sigma{sg}" for sg in SIGMAS], "source"])
        w.writerows(rows)
    for i, sg in enumerate(SIGMAS):
        k = int(np.argmin([r[3 + i] for r in rows]))
        print(f"  robust optimum at sigma {sg} nm: N {rows[k][0]}, expected {rows[k][3 + i]:.4f} (nominal {rows[k][2]:.4f})",
              flush=True)
    tots = np.linspace(0.0, otmax, 401)[1:]
    srt = sorted(pts, key=lambda p: p[1])
    env_t = []
    for t in tots:
        cand = [p for p in srt if p[1] <= t]
        env_t.append(min(p[2] for p in cand) if cand else np.nan)
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
    ax[0].semilogy([r[0] for r in rows], [r[2] for r in rows], "o-", ms=3, color="C0", label="best design found, any OT")
    for i, sg in enumerate(SIGMAS):
        ax[0].semilogy([r[0] for r in rows], [r[3 + i] for r in rows], "--", color=f"C{1 + i}",
                       label=fr"Monte Carlo, $\sigma_{{OT}}$ = {sg} nm")
    ax[0].semilogy([50], [0.0139], "k*", ms=9, label="contest winner (50 layers)")
    ax[0].semilogy([50], [0.0238], "kx", ms=7, label="Trubetskov 2020, deep search")
    ax[0].set_xlabel("number of layers N")
    ax[0].set_ylabel("MF")
    ax[0].set_xlim(0, 51)
    ax[0].legend(fontsize=7)
    ax[1].semilogy(tots, env_t, "-", color="C0", label="best design found, any N <= 50")
    ax[1].axvline(ot_d(rm, rd), color="grey", ls=":", lw=1)
    ax[1].text(ot_d(rm, rd), ax[1].get_ylim()[1], " record", fontsize=7, va="top")
    ax[1].set_xlabel("dielectric optical thickness (nm)")
    ax[1].set_xlim(0, otmax)
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "cissoid_mf_n_ot.pdf")
    fig.savefig(out_dir / "cissoid_mf_n_ot.png", dpi=150)
    print(f"  figure -> {out_dir / 'cissoid_mf_n_ot.pdf'}; envelope points {len(rows)}", flush=True)


if __name__ == "__main__":
    main()
