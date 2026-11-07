"""OIC 2016 B1 (cissoid): relax the index of K dielectric layers, then pull it back to the allowed indices (2026-10-31).

The owner: optimize on a constant index free per layer, then converge to the nearest dielectric. Which layers: the K
whose index derivative |d MF^2 / d n| is largest at the start (K = 0 or >= the dielectric count: all of them).
Steps: least squares on (all thicknesses, the K indices in [1.38, 2.45]) on the 301 points, with a penalty
sqrt(mu) * (n - nearest allowed index) whose mu climbs geometrically from MU0 to 1 in STEPS steps; then every index
snaps to the nearest allowed one, the thicknesses are polished on the 301 points and the oracle judges.
The index derivative is a finite difference (the kernel gives dR/dd only); R itself comes from the same kernel.
usage: python cissoid_relax_n.py IN.csv OUT.csv K STEPS
"""

from __future__ import annotations

import csv
import sys
import time

import cissoid_opt as co
import numpy as np
from scipy.optimize import least_squares

ALLOWED = {m: n for m, n in co.MATS.items() if not np.iscomplex(n)}
LETTERS, NS = list(ALLOWED), np.array(list(ALLOWED.values()), dtype=float)


def reflect(d, nvec):
    nm = np.tile(np.asarray(nvec, dtype=complex), (len(co.W_FULL), 1))
    r, _t, dr, _dt = co.compute_oblique_rt_and_grads_analytic(d, nm, co.NSUB_FULL, co.W_FULL, np.arange(len(d)), 0.0,
                                                              True)
    return r, dr


def main() -> None:
    src, dst, k, steps = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    r0 = next(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    mats, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    n0 = np.array([co.MATS[m] for m in mats], dtype=complex)
    diel = [i for i, m in enumerate(mats) if m in ALLOWED]
    t0 = time.time()
    # layers to relax: largest |d MF^2 / d n| at the start
    r, _ = reflect(d0, n0)
    e = (r - co.TGT_FULL) * co.SCALE_FULL
    grads = []
    for i in diel:
        n1 = n0.copy()
        n1[i] += 1e-4
        e1 = (reflect(d0, n1)[0] - co.TGT_FULL) * co.SCALE_FULL
        grads.append(abs(float(e1 @ e1 - e @ e)) / 1e-4)
    order = np.argsort(grads)[::-1]
    free = sorted(diel[j] for j in (order if k <= 0 or k >= len(diel) else order[:k]))
    print(f"K {len(free)} of {len(diel)} dielectrics, steps {steps}; relaxed layers {free}", flush=True)

    hi_d = np.array([co.HI_METAL if np.iscomplex(co.MATS[m]) else co.HI_DIEL for m in mats])
    nf = len(free)

    def unpack(x):
        nvec = n0.copy()
        nvec[free] = x[len(d0):]
        return x[:len(d0)], nvec

    def fun(x, mu):
        d, nvec = unpack(x)
        rr, _ = reflect(d, nvec)
        xn = x[len(d0):]
        near = NS[np.argmin(np.abs(xn[:, None] - NS[None, :]), axis=1)]
        return np.concatenate([(rr - co.TGT_FULL) * co.SCALE_FULL, np.sqrt(mu) * (xn - near)])

    def jac(x, mu):
        d, nvec = unpack(x)
        _rr, dr = reflect(d, nvec)
        j = np.zeros((len(co.W_FULL) + nf, len(x)))
        j[:len(co.W_FULL), :len(d0)] = dr * co.SCALE_FULL[:, None] if np.ndim(co.SCALE_FULL) else dr * co.SCALE_FULL
        base = fun(x, 0.0)[:len(co.W_FULL)]
        for c in range(nf):
            x1 = x.copy()
            x1[len(d0) + c] += 1e-6
            j[:len(co.W_FULL), len(d0) + c] = (fun(x1, 0.0)[:len(co.W_FULL)] - base) / 1e-6
        j[len(co.W_FULL):, len(d0):] = np.sqrt(mu) * np.eye(nf)
        return j

    x = np.concatenate([d0, n0[free].real])
    lo = np.concatenate([np.full(len(d0), co.FLOOR), np.full(nf, NS.min())])
    hi = np.concatenate([hi_d, np.full(nf, NS.max())])
    for mu in [0.0, *np.geomspace(1e-6, 1.0, steps)]:
        sol = least_squares(fun, np.clip(x, lo, hi), jac=jac, bounds=(lo, hi), args=(mu,), max_nfev=200)
        x = sol.x
        res = fun(x, 0.0)[:len(co.W_FULL)]
        print(f"mu {mu:.1e}: MF {np.linalg.norm(res):.5f}, max |n - allowed| "
              f"{np.max(np.abs(x[len(d0):][:, None] - NS[None, :]).min(axis=1)):.3f} ({time.time() - t0:.0f} s)", flush=True)
    d, _ = unpack(x)
    snapped = list(mats)
    for c, i in enumerate(free):
        snapped[i] = LETTERS[int(np.argmin(np.abs(NS - x[len(d0) + c])))]
    changed = [f"{i}{mats[i]}->{snapped[i]}" for i in free if snapped[i] != mats[i]]
    m2, d2 = co.normalize(snapped, d, 0.0)
    m3, d3, f = co.polish_full((m2, d2, co.FLOOR))
    o = co.oracle_mf(m3, d3)
    print(f"snap: {len(changed)} changed {changed}; 301-point polish {f:.5f}, oracle {o:.5f}, N {len(m3)} "
          f"({time.time() - t0:.0f} s)", flush=True)
    row = {"k": len(free), "steps": steps, "changed": " ".join(changed), "layers": len(m3), "mf_kernel": f, "mf_full": f,
           "mf_oracle": o, "metals": "".join(x for x in m3 if x in "AUN"), "physical_nm": float(d3.sum()),
           "mats": " ".join(m3), "d_nm": " ".join(f"{v:.4f}" for v in d3)}
    with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    main()
