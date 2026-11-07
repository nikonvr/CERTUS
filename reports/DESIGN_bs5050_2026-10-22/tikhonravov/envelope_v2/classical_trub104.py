"""Trubetskov's classical 104-layer three-line design (Appl. Opt. 59, A75, 2020, Fig. 4), as re-created in
fig4_2020_designs.csv, measured for Table 2 of the method paper (2026-11-02, owner: measure it). Judge: the paper's
Code 1 (hidden_resonances.py, NumPy only, independent of CERTUS): MF on the 277 points and on 0.001, 0.0002 and
0.0001 nm steps (band edges included); the poles found from the 277 points alone (phase of t on lambda + 1i nm, then
Newton); the highest peak checked by a direct scan. |E|^2 at that peak and at the nearest grid point: CERTUS field
module (article_grid_figures.field_profile). The same design judged by CERTUS: variants_fig4_2020.out.
usage: python classical_trub104.py OE_CODE_DIR [DESIGNS.csv]   (row "classical"; default fig4_2020_designs.csv,
       fig4_2020_classical_nolsub.csv: the same without its substrate-side L layer, classical_nolsub.py; or a
       threeline_track.py output, whose last round is judged)
"""

from __future__ import annotations

import csv
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])
import hidden_resonances as hr  # noqa: E402

N_IDX = {"H": 2.35, "L": 1.45}
BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
         (650, 700, 0.0)]


def target_fn(lam):
    return next((t for a, b, t in BANDS if a <= lam <= b), 0.0)


def judged(nl, d, h):
    """MF (%) on steps of h nm in every band, edges included (h = 1: the 277 points), and the number of wavelengths."""
    s2, n = 0.0, 0
    for a, b, t in BANDS:
        w = np.linspace(a, b, round((b - a) / h) + 1)
        for k in range(0, len(w), 20000):
            s2 += float(np.sum((hr.transmittance(nl, d, w[k:k + 20000]) - t) ** 2))
        n += len(w)
    return 100.0 * np.sqrt(s2 / n), n


def scan(nl, d, lam, fwhm):
    """Peak wavelength, peak T and FWHM of T from a direct scan of +-5 FWHM around lam."""
    w = np.linspace(lam - 5 * fwhm, lam + 5 * fwhm, 20001)
    t = hr.transmittance(nl, d, w)
    k = int(np.argmax(t))
    above = np.where(t >= t[k] / 2)[0]
    return float(w[k]), float(t[k]), float(w[above[-1]] - w[above[0]])


def main() -> None:
    path = sys.argv[2] if len(sys.argv) > 2 else "fig4_2020_designs.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    # a threeline_track.py output (one row per round): its last round
    r = rows[-1] if "round" in rows[0] else next(r for r in rows if r["design"] == "classical")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    nl = [N_IDX[m] for m in seq]
    ot = sum(n * t for n, t in zip(nl, d, strict=True))
    print(f"{path}: classical N{len(seq)}, OT {ot:.1f} nm, max OT shift {float(r.get('max_shift_nm', 'nan')):.2f} nm, "
          f"layer 1 (substrate side) {seq[0]} {d[0]:.2f} nm, layer 2 {seq[1]} {d[1]:.2f} nm", flush=True)
    for h in (1.0, 0.001, 0.0002, 0.0001):
        t0 = time.time()
        mf, n = judged(nl, d, h)
        print(f"MF on {h:g} nm steps ({n} wavelengths): {mf:.4f} %  [{time.time() - t0:.0f} s]", flush=True)
    t0 = time.time()
    poles = sorted(hr.find_poles(nl, d, [(a, b) for a, b, _t in BANDS], target_fn), key=lambda p: -p[2])
    print(f"poles found from the 277 points ({time.time() - t0:.0f} s): {len(poles)}", flush=True)
    for lam, fwhm, hgt, s in poles:
        print(f"  {lam:.4f} nm  FWHM {fwhm:.5f} nm  |T - target| {100 * hgt:.2f} %  Im(lambda_p) "
              f"{(1.0 / s).imag:.6f} nm", flush=True)
    if not poles:
        return
    lam, fwhm = poles[0][0], poles[0][1]
    xs, ts, fs = scan(nl, d, lam, fwhm)
    print(f"direct scan of the highest: peak {xs:.4f} nm, T {100 * ts:.2f} %, FWHM {fs:.5f} nm", flush=True)
    import article_grid_figures as agf

    for wl in (xs, float(round(xs))):
        _x, e2 = agf.field_profile(seq, d, wl)
        print(f"max |E|^2 at {wl:.4f} nm: {float(np.max(e2)):.0f}", flush=True)


if __name__ == "__main__":
    main()
