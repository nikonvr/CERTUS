"""Why |E|^2 = 3000 at a 0.38-% peak (classical design, charged) but 3 at a 0.33-% peak (deep design, charged)?
OE paper, 2026-11-03 (suggestion of a reader: an asymmetric Fabry-Perot, whose peak T = 4 g G / (g + G)^2 is small when
its couplings g << G to the two outer media are unequal, keeps a narrow width set by G).

For the highest remaining resonance of each charged design (Code 1, find_poles): T at the top, FWHM, the turn of the
phase of r over +-5 FWHM seen from the air and from the substrate, and the largest |E|^2 in the stack (incident wave = 1)
for light coming from the air and from the substrate. A resonance strongly coupled to one side turns the phase of r on
that side by about 2 pi and fills with light coming from that side; light from the weak side hardly enters.
usage: python field_side_probe.py
"""

import csv
import sys
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parents[6] / "OE_resonances" / "code"
sys.path.insert(0, str(CODE))
import hidden_resonances as hr  # noqa: E402

BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
         (650, 700, 0.0)]
N0, NS = 1.0, 1.52


def target_fn(lam):
    return next((t for a, b, t in BANDS if a <= lam <= b), 0.0)


def front(n_layers, d, lam, n_exit):
    """[B; C] at the front for layers listed from the exit medium (Macleod), real wavelength."""
    b, c = 1.0 + 0j, complex(n_exit)
    for n, t in zip(n_layers, d, strict=True):
        de = 2 * np.pi * n * t / lam
        b, c = np.cos(de) * b + 1j * np.sin(de) / n * c, 1j * n * np.sin(de) * b + np.cos(de) * c
    return b, c


def field_max(n_layers, d, lam, n_in, n_exit, samples=40):
    """Largest |E|^2 inside the stack relative to the incident wave, layers listed from the exit medium."""
    e, h, best = 1.0 + 0j, complex(n_exit), 0.0
    for n, t in zip(n_layers, d, strict=True):
        for z in np.linspace(0.0, t, samples):
            de = 2 * np.pi * n * z / lam
            best = max(best, abs(np.cos(de) * e + 1j * np.sin(de) / n * h) ** 2)
        de = 2 * np.pi * n * t / lam
        e, h = np.cos(de) * e + 1j * np.sin(de) / n * h, 1j * n * np.sin(de) * e + np.cos(de) * h
    e_inc = (n_in * e + h) / (2 * n_in)
    return best / abs(e_inc) ** 2


def phase_turn(n_layers, d, lam, fwhm, n_in, n_exit):
    w = np.linspace(lam - 5 * fwhm, lam + 5 * fwhm, 2001)
    r = []
    for x in w:
        b, c = front(n_layers, d, x, n_exit)
        r.append((n_in * b - c) / (n_in * b + c))
    ph = np.unwrap(np.angle(np.array(r)))
    return float(ph.max() - ph.min())


for name, path, e2_paper in (("deep, charged", "threeline_track_height_trub101.csv", 3),
                             ("classical, charged", "threeline_track_height_classical103.csv", 3000)):
    row = list(csv.DictReader(open(path, encoding="utf-8")))[-1]
    seq, d = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
    nl = [{"H": 2.35, "L": 1.45}[m] for m in seq]
    lam, fwhm, h, _s = max(hr.find_poles(nl, d, [(a, b) for a, b, _ in BANDS], target_fn), key=lambda p: p[2])
    top = hr.top_of_peak(nl, d, lam, fwhm, target_fn)
    t_top = float(hr.transmittance(nl, d, [top])[0])
    rev_n, rev_d = nl[::-1], d[::-1]
    print(f"{name}: resonance at {top:.4f} nm, FWHM {fwhm:.4f} nm, T at the top {100 * t_top:.3f} % "
          f"(coupling ratio g/G about {t_top / 4:.2e})")
    print(f"   phase turn of r over +-5 FWHM: from the air {phase_turn(nl, d, top, fwhm, N0, NS):.2f} rad, "
          f"from the substrate {phase_turn(rev_n, rev_d, top, fwhm, NS, N0):.2f} rad")
    print(f"   max |E|^2: light from the air {field_max(nl, d, top, N0, NS):.1f} (paper: {e2_paper}), "
          f"from the substrate {field_max(rev_n, rev_d, top, NS, N0):.1f}")
