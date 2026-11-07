"""Three-line filter: the resonances hidden between the grid points, handled without a finer grid (2026-11-01, owner:
"how to free oneself from ultra-narrow peaks without an incredibly fine grid?").

The nominal grid misses peaks narrower than its step; a uniform grid fine enough to see them costs 270 007 points
(0.001 nm), and the optimizer then narrows them (threeline_refine_probe.out: 0.012 -> 0.004 nm, |E|^2 x4). Here the
peaks are followed where they are. A scan of the bands every SCAN nm, with T only, finds every local maximum of |T - T'|
above THR and narrower than FWHM_MAX; between scans, polishes of BURST iterations work on the 277 nominal points plus,
for each peak, its resonance followed through its pole -- the zero of n0 B + C in the complex plane, reached by Newton
from the pole of the burst's start, so that the merit stays a function of the thicknesses and a peak cannot slip out of
a window (a first version searched the top on the real axis around a fixed anchor: the optimizer moved the peaks
away instead of lowering them) -- giving its wavelength lambda_r and its FWHM, and:
  quad   -- a window of 61 points over +-6 FWHM centred on lambda_r, weighted as the 1 nm points (step / 1 nm): the
            integral of the peak, i.e. the MF of a resolved grid, at the cost of the window;
  height -- lambda_r alone, counted as one nominal point: the MF the nominal grid would give with a point on the peak,
            a charge that no longer falls when the peak narrows. At the top dT/dlambda = 0, so the derivative of its
            residual with respect to the thicknesses is the ordinary one at that wavelength (envelope theorem).
Each round is judged on the nominal grid, on 0.001 nm and on 0.0002 nm steps (grid_study.GRIDS), with the largest |E|^2
in the stack at the highest peak (CERTUS field module, field_grid_link.e2max).
env TRACK_DETECT=complex finds the peaks without any fine scan: the phase of t along lambda + i GAMMA on the nominal
points of each band (complex_plane_detect.py: a step of pi at every resonance, however narrow), then Newton on the zero of
n0 B + C in the complex plane from each step (the pole: the resonance's wavelength and, from its imaginary part, its
width), the oracle's characteristic matrices at complex wavelength.
usage: SEARCH_TARGET=threeline python threeline_track.py MODE IN.csv ROW OUT.csv   (ROW: "best" by mf_oracle, or index)
       SEARCH_TARGET=threeline python threeline_track.py batch MODE OUT.csv   (grid_study.candidates, TRACK_WORKERS)
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import bs5050_grid as bg
import complex_plane_detect as cp
import field_grid_link as fl
import grid_study as gs
import numpy as np
from scipy.optimize import least_squares

THR, FWHM_MAX, SCAN, BURST = 1e-3, 0.5, 0.0002, 30
ROUNDS = int(os.environ.get("TRACK_ROUNDS", "15"))
DETECT, GAMMA = os.environ.get("TRACK_DETECT", "scan"), 1.0
#: env TRACK_MULTISTART=1 (2026-11-02): Newton from 5 points across each phase step (x0 + 0, -1, -0.5, 0.5, 1 nm), so that
#: two close poles in one step are both found (a broad pole at 429.15 nm hid a 0.008-nm one at 431.19 nm); unset: from x0 alone.
#: env TRACK_MULTISTART=dense (2026-11-03, with TRACK_STEPS=localmax of complex_plane_detect): Newton every GAMMA/4 over
#: +-2.5 GAMMA of each step, as Code 1 since its fix; close poles about 2 nm apart are then all found (oblique_*.out).
MULTISTART = {"1": (0.0, -1.0, -0.5, 0.5, 1.0),
              "dense": tuple(np.arange(-2.5, 2.51, 0.25) * GAMMA)}.get(os.environ.get("TRACK_MULTISTART", "0"), (0.0,))
NOM = gs.GRIDS["nominal"]
W_NOM = float(np.sqrt(1.0 / len(NOM["k0"])))
PASS = [(a, b) for a, b, t in gs.s._bands if t == 1.0]
WIN = np.linspace(-6.0, 6.0, 61)


def target(wls):
    return np.array([1.0 if any(a <= w <= b for a, b in PASS) else 0.0 for w in np.atleast_1d(wls)])


def err(seq, d, wls, jac=False):
    """T - T' at the wavelengths (and its Jacobian), unit weights."""
    wls = np.atleast_1d(np.asarray(wls, dtype=float))
    g = gs.kernel_grid(wls, target(wls))
    g["sqw"] = np.ones(len(wls))
    r, j = bg.res_jac(seq, d, g)[:2]
    return (r, j) if jac else r


def scan(seq, d):
    """[lambda, FWHM, height] of every local maximum of |T - T'| above THR and narrower than FWHM_MAX, band by band."""
    found = []
    for a, b, _t in gs.s._bands:
        w = np.linspace(a, b, round((b - a) / SCAN) + 1)
        e = np.abs(np.concatenate([err(seq, d, w[idx]) for idx in np.array_split(np.arange(len(w)), -(-len(w) // 20000))]))
        for k in np.where((e[1:-1] > e[:-2]) & (e[1:-1] >= e[2:]) & (e[1:-1] > THR))[0] + 1:
            lo, hi = k, k
            while lo > 0 and e[lo] > e[k] / 2:
                lo -= 1
            while hi < len(e) - 1 and e[hi] > e[k] / 2:
                hi += 1
            if w[hi] - w[lo] < FWHM_MAX:
                lam, fw = float(w[k]), float(max(w[hi] - w[lo], 2 * SCAN))
                keep(seq, d, found, newton(seq, d, 1.0 / lam + 0.5j * fw / lam ** 2), a, b, lam)
    return found


def newton(seq, d, s0):
    """The zero of n0 B + C (air, glass 1.52) reached by Newton from the complex wavenumber s0: a pole of t."""
    ns = [complex(fl.N_IDX[m]) for m in seq]

    def y(s):
        b, c = cp.oracle.stack_matrix(ns, d, 1.0 / s) @ np.array([1.0 + 0.0j, 1.52 + 0.0j])
        return b + c

    s = complex(s0)
    for _ in range(40):
        step = y(s) / ((y(s + 1e-10) - y(s - 1e-10)) / 2e-10)
        s -= step
        if abs(step) < 1e-15:
            break
    return s


def lam_fwhm(s):
    """(wavelength, FWHM) in nm of the resonance whose pole is the complex wavenumber s."""
    return 1.0 / s.real, 2.0 * s.imag / s.real ** 2


def keep(seq, d, found, s, a, b, near):
    """Add (lambda, FWHM, height, pole) to found when the pole is a resonance of the band [a, b] near `near`."""
    lam, fwhm = lam_fwhm(s)
    if abs(lam - near) < 3.0 * GAMMA and a <= lam <= b and 0.0 < fwhm < FWHM_MAX:
        h = float(abs(err(seq, d, [lam])[0]))
        if h > THR and all(abs(lam - p[0]) > 1e-6 for p in found):
            found.append((lam, fwhm, h, s))


def poles(seq, d):
    """(lambda, FWHM, height, pole) of the resonances narrower than FWHM_MAX inside the bands, found from the nominal
    points: steps of the phase of t along lambda + i GAMMA, then Newton on their poles."""
    found: list = []
    for a, b, _t in gs.s._bands:
        w = np.arange(float(a), b + 1e-9, 1.0)
        if len(w) < 5:
            continue
        dphi = np.gradient(cp.phase_t(seq, d, w + 1j * GAMMA), w)
        for x0, _area in cp.steps(w, dphi, GAMMA):
            for dx in MULTISTART:
                keep(seq, d, found, newton(seq, d, 1.0 / (x0 + dx)), a, b, x0)
    return found


#: env TRACK_PEAK=top (2026-11-03): in height mode the wavelength charged is the top of the peak of |T - T'|, reached from
#: 1/Re(sigma_p) by Newton on its derivative; there dT/dlambda = 0 and the Jacobian at fixed wavelength is the total one.
#: 1/Re(sigma_p) is not the top (0.001 nm off for a 0.17-nm pole), and that Jacobian was then wrong by 18-66 %, enough to
#: stall the trust region (stall_jacobian_probe.py). Unset, unchanged.
PEAK = os.environ.get("TRACK_PEAK", "pole")


def top(seq, d, lam, fwhm):
    """Top of the peak of |T - T'| near lam: Newton on its derivative, central differences of step fwhm / 50."""
    h = fwhm / 50.0
    for _ in range(8):
        e = np.abs(err(seq, d, [lam - h, lam, lam + h]))
        d1, d2 = (e[2] - e[0]) / (2 * h), (e[2] - 2 * e[1] + e[0]) / h ** 2
        if d2 >= 0.0:  # not a maximum there: keep the wavelength reached
            break
        step = float(np.clip(-d1 / d2, -fwhm / 2, fwhm / 2))
        lam += step
        if abs(step) < 1e-9:
            break
    return lam


def polish(mode, seq, d, peaks):
    """Each peak followed through its pole (Newton from the anchor of the burst), so that it cannot slip away."""
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            r, j = bg.res_jac(seq, x, NOM)[:2]
            lf = [lam_fwhm(newton(seq, x, p[3])) for p in peaks]
            if PEAK == "top" and mode == "height":
                lf = [(top(seq, x, c, fw), fw) for c, fw in lf]
            if mode == "quad":
                wls = np.concatenate([c + fw * WIN for c, fw in lf])
                wts = np.concatenate([np.full(len(WIN), np.sqrt(abs(fw) * (WIN[1] - WIN[0]))) for _c, fw in lf])
            else:
                wls, wts = np.array([c for c, _fw in lf]), np.ones(len(lf))
            if len(wls):
                rp, jp = err(seq, x, wls, jac=True)
                r = np.concatenate([r, W_NOM * wts * rp])
                j = np.vstack([j, W_NOM * wts[:, None] * jp])
            memo[key] = (r, j)
        return memo[key]

    sol = least_squares(lambda x: both(x)[0], np.maximum(d, gs.FLOOR), jac=lambda x: both(x)[1],
                        bounds=(gs.FLOOR, np.inf), method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15,
                        max_nfev=BURST)
    return np.maximum(sol.x, gs.FLOOR)


def main() -> None:
    mode, src, pick, dst = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    assert mode in ("quad", "height", "nominal")
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    r0 = min(rows, key=lambda r: float(r["mf_oracle"])) if pick == "best" else rows[int(pick)]
    seq, d = r0["seq"], np.array([float(v) for v in r0["d_nm"].split()])
    out = track(mode, seq, d, log=True)
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


def track(mode, seq, d, rounds=ROUNDS, log=False, precise=False) -> list[dict]:
    """Rounds of detection and polish, every round judged; mf_tracked is the method's own merit (the nominal points
    and the peaks found, each counted as one point), the only one used to choose a round. In optional top mode,
    judging and field sampling use the real maximum, as does polish(), rather than the pole's wavelength estimate.
    The explicit nominal control uses the same bursts without adding peaks. precise saves round-trip thicknesses;
    its default leaves the historical six-decimal export unchanged."""
    ns = [fl.N_IDX[m] for m in seq]
    t0 = time.time()
    out = []
    for rnd in range(rounds + 1):
        peaks = [] if mode == "nominal" else (poles(seq, d) if DETECT == "complex" else scan(seq, d))
        if PEAK == "top" and mode == "height":
            positions = [(top(seq, d, lam, fw), fw, pole) for lam, fw, _height, pole in peaks]
            peaks = [(lam, fw, float(abs(err(seq, d, [lam])[0])), pole) for lam, fw, pole in positions]
        nom, res, chk = (gs.mf(seq, d, gs.GRIDS[g]) for g in ("nominal", "resolved", "check"))
        mft = float(np.sqrt(nom ** 2 + 1e4 * sum(p[2] ** 2 for p in peaks) / len(NOM["k0"])))
        hi = max(peaks, key=lambda p: p[2]) if peaks else None
        e2 = fl.e2max(ns, d, hi[0])[0] if hi else 0.0
        if log:
            print(f"{mode} round {rnd}: {len(peaks)} peaks, highest {100 * hi[2] if hi else 0:.2f} % "
                  f"(FWHM {hi[1] if hi else 0:.4f} nm, |E|^2 {e2:.0f}); MF nominal {nom:.4f} %, tracked {mft:.4f} %, "
                  f"0.001 nm {res:.4f} %, 0.0002 nm {chk:.4f} % ({time.time() - t0:.0f} s)", flush=True)
        out.append({"mode": mode, "round": rnd, "peaks": len(peaks), "highest": f"{hi[2] if hi else 0:.6f}",
                    "fwhm": f"{hi[1] if hi else 0:.5f}", "e2max": f"{e2:.1f}", "mf_nominal": f"{nom:.6e}",
                    "mf_tracked": f"{mft:.6e}", "mf_resolved": f"{res:.6e}", "mf_check": f"{chk:.6e}",
                    "t_s": f"{time.time() - t0:.0f}", "seq": seq,
                    "d_nm": " ".join(format(v, ".17g" if precise else ".6f") for v in d)})
        if precise:
            out[-1].update({key: format(value, ".17g") for key, value in
                            (("highest", hi[2] if hi else 0.0), ("fwhm", hi[1] if hi else 0.0), ("e2max", e2),
                             ("mf_nominal", nom), ("mf_tracked", mft), ("mf_resolved", res), ("mf_check", chk))})
        if rnd < rounds:
            d = polish(mode, seq, d, peaks)
    return out


def track_task(task) -> list[dict]:
    mode, seq, d_text = task
    return track(mode, seq, np.array([float(v) for v in d_text.split()]))


def batch(mode, dst) -> None:
    """track() on every candidate of grid_study.candidates (the steps of the resolved envelopes within the budget),
    TRACK_WORKERS at once; the round of least mf_tracked of each appended to dst as it ends."""
    todo = gs.candidates()
    t0 = time.time()
    print(f"{len(todo)} designs, {mode}, detection {DETECT} -> {dst}", flush=True)
    with ProcessPoolExecutor(int(os.environ.get("TRACK_WORKERS", "6"))) as pool:
        futs = {pool.submit(track_task, (mode, r["seq"], r["d_nm"])): r for r in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            r, rows = futs[fut], fut.result()
            b = min(rows, key=lambda q: float(q["mf_tracked"]))
            row = {"source": r["source"], "layers": r["layers"], "tot_before": r["tot"],
                   "tot": f"{gs.s.total_ot(r['seq'], np.array([float(v) for v in b['d_nm'].split()])):.1f}",
                   "mf_nominal_before": r["mf_nominal"], "mf_resolved_before": r["mf_resolved"],
                   **{key: b[key] for key in ("round", "peaks", "highest", "fwhm", "e2max", "mf_nominal", "mf_tracked",
                                              "mf_resolved", "mf_check", "seq", "d_nm")}}
            new = not os.path.exists(dst)
            with open(dst, "a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row))
                if new:
                    w.writeheader()
                w.writerow(row)
            print(f"  {k}/{len(todo)} N {r['layers']}: resolved {float(r['mf_resolved']):.4f} -> {float(b['mf_resolved']):.4f} %"
                  f" (nominal {float(b['mf_nominal']):.4f}, highest peak {100 * float(b['highest']):.2f} %, round {b['round']})"
                  f" ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "batch":
        batch(sys.argv[2], sys.argv[3])
    else:
        main()
