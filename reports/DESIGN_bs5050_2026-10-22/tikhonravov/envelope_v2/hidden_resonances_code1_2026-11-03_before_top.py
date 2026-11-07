"""Hidden resonances of an optical coating, found from the complex plane and charged at their poles.

Minimal reference implementation for the paper "In thick coatings, the wavelength grid is part of the design problem"
(normal incidence, non-dispersive lossless materials, transmittance targets). Requires NumPy and SciPy only.

Steps (Sec. 5 of the paper):
  1. detect  -- phase of the amplitude transmission t on lambda + i*gamma at the points of the design grid; each step of
                pi marks a resonance, however narrow;
  2. locate  -- Newton iterations on Y = eta0*B + C = 0 in the complex wavenumber plane, started from several points
                across each step, give the poles (wavelength = 1/Re(sigma), FWHM = 2 Im(sigma)/Re(sigma)^2);
  3. charge  -- least-squares polish on the grid points plus one real wavelength per resonance (its peak, Re of the
                pole, re-located by Newton as the thicknesses change): each resonance counts as one more grid point.

Conventions: refractive index n - ik (k >= 0), layer 1 on the substrate, incidence from the ambient medium,
characteristic matrices as in H. A. Macleod, Thin-Film Optical Filters.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def char_y(n_layers, d, wl, n0=1.0, ns=1.52):
    """Y = eta0*B + C and T for wavelengths wl (real or complex, array), layers listed from the substrate."""
    wl = np.atleast_1d(np.asarray(wl, dtype=complex))
    b = np.ones_like(wl)
    c = np.full_like(wl, ns)
    for n, t in zip(n_layers, d, strict=False):  # from the substrate outwards: [B; C] <- M_j [B; C]
        delta = 2.0 * np.pi * n * t / wl
        cs, sn = np.cos(delta), np.sin(delta)
        b, c = cs * b + 1j * sn / n * c, 1j * n * sn * b + cs * c
    y = n0 * b + c
    return y, 4.0 * n0 * np.real(ns) / np.abs(y) ** 2


def transmittance(n_layers, d, wl, n0=1.0, ns=1.52):
    return char_y(n_layers, d, wl, n0, ns)[1]


def merit(n_layers, d, wl, target):
    """RMS deviation of T from the target, in percent."""
    return 100.0 * float(np.sqrt(np.mean((transmittance(n_layers, d, wl) - target) ** 2)))


def phase_steps(n_layers, d, wl_grid, gamma=1.0):
    """Wavelengths of the steps of pi of arg t along lambda + i*gamma, sampled on wl_grid (sorted, one band): every local
    maximum of the derivative of the phase that exceeds its running median by 0.25/gamma, one per bump."""
    y, _ = char_y(n_layers, d, wl_grid + 1j * gamma)
    dphi = np.gradient(np.unwrap(-np.angle(y)), wl_grid)
    base = np.array([np.median(dphi[max(0, k - 40):k + 41]) for k in range(len(dphi))])
    ex = np.concatenate([[-np.inf], dphi - base, [-np.inf]])
    k = np.where((ex[1:-1] > ex[:-2]) & (ex[1:-1] >= ex[2:]) & (ex[1:-1] > 0.25 / gamma))[0]
    return [float(wl_grid[i]) for i in k]


def newton_pole(n_layers, d, sigma0, iters=50):
    """Zero of Y in the complex wavenumber plane, from sigma0 (1/nm)."""
    s = complex(sigma0)
    for _ in range(iters):
        h = 1e-10
        f = char_y(n_layers, d, 1.0 / s)[0][0]
        df = (char_y(n_layers, d, 1.0 / (s + h))[0][0] - char_y(n_layers, d, 1.0 / (s - h))[0][0]) / (2 * h)
        step = f / df
        s -= step
        if abs(step) < 1e-15:
            break
    return s


def find_poles(n_layers, d, bands, target_fn, gamma=1.0, max_fwhm=0.5, min_height=1e-3):
    """Resonances (wavelength, FWHM, |T - target| at the peak, pole) narrower than max_fwhm in the target bands.

    bands: list of (lambda_min, lambda_max) in nm, sampled every 1 nm for the detection; target_fn(lambda) -> target T.
    """
    found = []
    for a, b in bands:
        w = np.arange(float(a), b + 1e-9, 1.0)
        if len(w) < 5:
            continue
        for x0 in phase_steps(n_layers, d, w, gamma):
            for dx in np.arange(-2.5, 2.51, 0.25) * gamma:  # starts across the bump: close poles can share one
                s = newton_pole(n_layers, d, 1.0 / (x0 + dx))
                lam, fwhm = 1.0 / s.real, 2.0 * s.imag / s.real ** 2
                if not (abs(lam - x0) < 3 * gamma and a <= lam <= b and 0.0 < fwhm < max_fwhm):
                    continue
                h = abs(float(transmittance(n_layers, d, [lam])[0]) - target_fn(lam))
                if h > min_height and all(abs(lam - p[0]) > 1e-6 for p in found):
                    found.append((lam, fwhm, h, s))
    return found


def charge_poles(n_layers, d, wl, target, bands, target_fn, rounds=40, burst=30, floor=0.1, gamma=1.0, verbose=True):
    """Rounds of detection and least-squares polish on wl plus one point per resonance, followed through its pole."""
    d = np.asarray(d, dtype=float).copy()
    w0 = 1.0 / np.sqrt(len(wl))
    for rnd in range(rounds):
        poles = find_poles(n_layers, d, bands, target_fn, gamma)
        if verbose:
            hi = max((p[2] for p in poles), default=0.0)
            print(f"round {rnd}: {len(poles)} resonances, highest {100 * hi:.2f} %, "
                  f"MF on the grid {merit(n_layers, d, wl, target):.4f} %", flush=True)
        anchors = [p[3] for p in poles]

        def residuals(x, anchors=anchors):
            r = (transmittance(n_layers, x, wl) - target) * w0
            extra = []
            for s0 in anchors:  # each resonance followed through its pole
                s = newton_pole(n_layers, x, s0, iters=8)
                lam = 1.0 / s.real
                extra.append((float(transmittance(n_layers, x, [lam])[0]) - target_fn(lam)) * w0)
            return np.concatenate([r, extra])

        sol = least_squares(residuals, np.maximum(d, floor), bounds=(floor, np.inf), method="trf", x_scale="jac",
                            max_nfev=burst)
        d = np.maximum(sol.x, floor)
    return d


if __name__ == "__main__":  # demonstration: the re-created 101-layer three-line filter (Appendix A of the paper)
    import csv
    import sys
    import time

    rows = list(csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else "three_line_101_recreated.csv")))
    idx = {"H": 2.35, "L": 1.45}
    nl = [idx[r["material"]] for r in rows]
    d0 = np.array([float(r["thickness_nm"]) for r in rows])
    bands = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
             (650, 700, 0.0)]

    def target_fn(lam):
        return next((t for a, b, t in bands if a <= lam <= b), 0.0)

    wl = np.concatenate([np.arange(a, b + 1.0) for a, b, _t in bands])
    tg = np.array([target_fn(x) for x in wl])
    wr = np.concatenate([np.linspace(a, b, round((b - a) / 0.001) + 1) for a, b, _t in bands])
    tr = np.array([target_fn(x) for x in wr])

    def resolved(d):
        return 100.0 * np.sqrt(np.mean(np.concatenate([(transmittance(nl, d, wr[k:k + 20000]) - tr[k:k + 20000]) ** 2
                                                        for k in range(0, len(wr), 20000)])))

    print(f"as given: MF on the 277 points {merit(nl, d0, wl, tg):.4f} %, resolved (0.001 nm) {resolved(d0):.4f} %")
    for lam, fwhm, h, _s in find_poles(nl, d0, [(a, b) for a, b, _t in bands], target_fn):
        print(f"  resonance at {lam:.4f} nm, FWHM {fwhm:.4f} nm, {100 * h:.2f} %")
    t0 = time.time()
    d1 = charge_poles(nl, d0, wl, tg, [(a, b) for a, b, _t in bands], target_fn, rounds=40)
    print(f"after the charge ({time.time() - t0:.0f} s): MF on the 277 points {merit(nl, d1, wl, tg):.4f} %, "
          f"resolved {resolved(d1):.4f} %")
